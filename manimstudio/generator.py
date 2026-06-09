"""Manim scene generation + rendering inside an InstaVM session.

Flow per job:
    draft via OpenAI -> upload to fresh InstaVM session -> render
    on failure: send error + last code back to OpenAI for a fix, retry
"""
from __future__ import annotations
import os, re, asyncio, traceback, shutil, contextlib
from typing import Callable, Awaitable
from openai import OpenAI
from instavm import InstaVM

OPENAI_API_KEY  = os.environ["OPENAI_API_KEY"]
INSTAVM_API_KEY = os.environ["INSTAVM_API_KEY"]
OPENAI_MODEL    = os.environ.get("OPENAI_MODEL", "gpt-4o")
MAX_ATTEMPTS    = int(os.environ.get("MAX_ATTEMPTS", "3"))
VIDEO_DIR       = os.environ.get("VIDEO_DIR", "/app/manimstudio/videos")
RENDER_TIMEOUT  = int(os.environ.get("RENDER_TIMEOUT", "600"))

os.makedirs(VIDEO_DIR, exist_ok=True)
_openai = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You write Manim Community Edition (v0.20+) scenes that render to a video.

HARD RULES:
- Output EXACTLY one fenced ```python ... ``` block. No prose.
- Single file. First line: `from manim import *` plus `import numpy as np` if you use np.
- One Scene subclass named `Generated` with a `construct(self)` method.
- DO NOT use Tex, MathTex, Title, Brace.get_text/get_tex, or anything that invokes LaTeX. LaTeX is unavailable.
- For mathematical notation, use Text(...) with unicode characters (π, ², ³, ≈, ∫, Σ, →, ←, ∞ etc.).
- Use Group(...) instead of VGroup(...) when mixing ImageMobject/Group-only mobjects; otherwise VGroup is fine.
- Keep scenes 10-30 seconds, 1080p60 friendly. Use self.wait(...) between beats.
- Use a dark background. ALWAYS quote color hexes as strings: self.camera.background_color = "#0e1117"
  Never write a bare `#xxxxxx` literal anywhere in the code — Python treats `#` as a comment.
  Every Manim color must be either a string like "#ff8800" or a named color constant like YELLOW, BLUE, WHITE.
- Prefer high-contrast colors. Avoid font="..." overrides (use default).
- Never call self.embed(), never read files, never network.
- Code must run unchanged with: manim -qh scene.py Generated

ALLOWED MOBJECTS / CONSTRUCTS (use ONLY these; do NOT invent or import others):
  Shapes:     Circle, Dot, Square, Rectangle, RoundedRectangle, Triangle, RegularPolygon,
              Polygon, Ellipse, Line, Arrow, DoubleArrow, Arc, Annulus, AnnularSector
  Text:       Text, MarkupText, Paragraph  (NOT Tex/MathTex)
  Image-ish:  ImageMobject is NOT available — do not use it
  Groups:     VGroup, Group
  Axes/plots: Axes, NumberPlane, NumberLine, ParametricFunction, FunctionGraph
  3D:        ThreeDAxes, Sphere, Cube, Cone, Cylinder, Torus, Surface, ParametricSurface (only inside ThreeDScene)
  Updaters: add_updater / remove_updater
ALLOWED ANIMATIONS:
  Create, Uncreate, Write, Unwrite, FadeIn, FadeOut, FadeTransform, Transform,
  ReplacementTransform, MoveToTarget, GrowFromCenter, ShrinkToCenter, DrawBorderThenFill,
  Indicate, Flash, Circumscribe, ApplyMethod, Rotate, MoveAlongPath, ShowPassingFlash
DO NOT use: Shield, Lock, Key, Cloud, Phone, Computer, Server, Database, Padlock, Briefcase,
  Person, User, Document, File — these are NOT real Manim mobjects.
  Build such concepts compositionally from the allowed shapes (e.g. a phone = RoundedRectangle
  with a small Circle for the camera; a shield = a rounded Polygon; a lock = a Rectangle with
  an Arc on top). If you cannot build it from the allowed shapes, use a Text(...) label instead.
"""

FIX_PROMPT = """Your previous Manim scene failed to render. Output a corrected, complete
file in a single ```python ... ``` block. Same HARD RULES as before.

ERROR TAIL:
{error}

PREVIOUS CODE:
```python
{code}
```
"""

CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
# Match `= #ffaabb` (unquoted hex used as a value — Python treats # as comment).
_BARE_HEX_ASSIGN = re.compile(r"(=\s*)(#[0-9a-fA-F]{3,8})(\s|$)", re.MULTILINE)
# Match function-arg uses like `color=#ffaabb,` or `color=#fff)`.
_BARE_HEX_KWARG = re.compile(r"(=\s*)(#[0-9a-fA-F]{3,8})(\s*[,)])")

def _patch_known_pitfalls(code: str) -> str:
    code = _BARE_HEX_ASSIGN.sub(lambda m: f'{m.group(1)}"{m.group(2)}"{m.group(3)}', code)
    code = _BARE_HEX_KWARG.sub(lambda m: f'{m.group(1)}"{m.group(2)}"{m.group(3)}', code)
    return code

def _extract_code(text: str) -> str:
    m = CODE_FENCE.search(text)
    raw = (m.group(1) if m else text).strip()
    return _patch_known_pitfalls(raw)


async def _chat(messages, log) -> str:
    log("openai > sending request to %s..." % OPENAI_MODEL)
    def call():
        r = _openai.chat.completions.create(
            model=OPENAI_MODEL, messages=messages, temperature=0.4
        )
        return r.choices[0].message.content
    out = await asyncio.to_thread(call)
    log("openai < response (%d chars)" % len(out))
    return out


async def _render_in_sandbox(code: str, log) -> tuple[bool, str, str | None]:
    """Returns (ok, error_tail_or_empty, local_mp4_path_or_none)."""
    snapshot_id = os.environ.get("MANIM_BASE_SNAPSHOT_ID")
    def work() -> tuple[bool, str, str | None]:
        client = InstaVM(api_key=INSTAVM_API_KEY, timeout=RENDER_TIMEOUT)
        vm = None
        try:
            if snapshot_id:
                log("sandbox > launching from snapshot %s..." % snapshot_id[:8])
                vm = client.vms.create(
                    wait=True, snapshot_id=snapshot_id,
                    memory_mb=2048, vcpu_count=2, vm_lifetime_seconds=1800,
                    metadata={"app": "manim-studio-render"},
                )
                client.session_id = vm["session_id"]
                log("sandbox > vm %s session %s ready" % (vm["vm_id"], vm["session_id"][:8]))
            else:
                # Fallback: ephemeral sandbox, install manim live.
                client.__enter__()
                info = client.get_session_info()
                log("sandbox > session %s ready (no snapshot)" % info["session_id"][:8])
                r = client.execute(
                    "set -e; export DEBIAN_FRONTEND=noninteractive; "
                    "sudo apt-get update -qq && "
                    "sudo apt-get install -y -qq libcairo2-dev libpango1.0-dev "
                    "pkg-config python3-dev ffmpeg build-essential >/dev/null 2>&1 && "
                    "python3 -m pip install --quiet manim==0.20.1 && echo ok",
                    language="bash", timeout=420,
                )
                if "ok" not in (r.get("stdout") or ""):
                    return False, "manim install failed: " + (r.get("stderr") or r.get("stdout") or "")[-2000:], None

            # Tighten egress (best-effort; not all VMs support it the same way)
            try:
                client.set_session_egress(
                    allow_package_managers=True, allow_http=False, allow_https=True,
                    allowed_domains=["pypi.org", "files.pythonhosted.org",
                                     "deb.debian.org", "security.debian.org"],
                )
                log("sandbox > egress narrowed")
            except Exception as e:
                log("sandbox > egress setup skipped: %s" % e)

            # write scene
            log("sandbox > writing scene")
            # Write the scene file locally then upload — using execute+heredoc
            # is brittle because double quotes inside the code (e.g. "#0e1117"
            # color strings) break the bash quoting.
            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
                f.write(code)
                local_scene = f.name
            try:
                client.upload_file(local_scene, "/tmp/scene.py")
            finally:
                with contextlib.suppress(Exception):
                    os.unlink(local_scene)

            log("sandbox > rendering (manim -qh)...")
            # Run render in background, poll for completion file. Avoids the
            # API's per-request execute cap (~5min) for long renders.
            launch = (
                "cd /tmp && rm -f render.done render.exit && "
                "( ( timeout 600 manim -qh --disable_caching scene.py Generated "
                "  > render.log 2>&1 ; echo $? > render.exit ; touch render.done ) "
                "  & disown ) ; echo started"
            )
            r = client.execute(launch, language="bash", timeout=60)
            if "started" not in (r.get("stdout") or ""):
                return False, "failed to launch render: " + (r.get("stderr") or "")[-1000:], None

            import time
            deadline = time.time() + 600
            while time.time() < deadline:
                time.sleep(8)
                p = client.execute(
                    "if [ -f /tmp/render.done ]; then "
                    "  echo DONE; cat /tmp/render.exit; tail -80 /tmp/render.log; "
                    "else echo WAIT; tail -2 /tmp/render.log 2>/dev/null; fi",
                    language="bash", timeout=45,
                )
                out = p.get("stdout") or ""
                if out.startswith("DONE"):
                    lines = out.splitlines()
                    exit_code = (lines[1].strip() if len(lines) > 1 else "?")
                    log_tail = "\n".join(lines[2:])
                    if exit_code != "0" or "Rendered" not in log_tail:
                        return False, log_tail[-3000:], None
                    break
            else:
                return False, "render watchdog timed out after 10 min", None

            log("sandbox > locating mp4")
            r = client.execute(
                "find /tmp/media -name 'Generated*.mp4' -printf '%p\\n'",
                language="bash",
            )
            remote = next(
                (l.strip() for l in (r.get("stdout") or "").splitlines() if l.strip().endswith(".mp4")),
                None,
            )
            if not remote:
                return False, "no mp4 produced", None

            local = os.path.join(VIDEO_DIR, f"{os.urandom(6).hex()}.mp4")
            log("sandbox > downloading -> %s" % os.path.basename(local))
            client.download_file(remote, local_path=local)
            return True, "", local
        finally:
            if vm:
                with contextlib.suppress(Exception):
                    client.vms.delete(vm["vm_id"])
                    log("sandbox > released vm %s" % vm["vm_id"])
            else:
                with contextlib.suppress(Exception):
                    client.__exit__(None, None, None)

    return await asyncio.to_thread(work)


async def generate(prompt: str, log: Callable[[str], None]) -> tuple[bool, str | None, str | None, str | None]:
    """Run draft+render+fix loop. Returns (ok, video_path, code, error)."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Animate the following idea as a Manim scene:\n\n{prompt}"},
    ]
    code = None
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        log(f"attempt {attempt}/{MAX_ATTEMPTS}")
        if attempt == 1:
            raw = await _chat(messages, log)
        else:
            raw = await _chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Original request: {prompt}"},
                    {"role": "user", "content": FIX_PROMPT.format(error=last_error[-1500:], code=code)},
                ],
                log,
            )
        code = _extract_code(raw)
        if not code or "class Generated" not in code:
            last_error = "openai produced no usable code block"
            log("draft > " + last_error)
            continue

        log("draft > %d lines extracted" % code.count("\n"))
        try:
            ok, err_tail, mp4 = await _render_in_sandbox(code, log)
        except Exception as e:
            ok, err_tail, mp4 = False, f"sandbox error: {e}\n{traceback.format_exc()[-1500:]}", None

        if ok:
            log("done. mp4 ready.")
            return True, mp4, code, None
        last_error = err_tail
        # Trim noisy ANSI from error
        last_error = re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", last_error or "")
        log("render < FAILED")
        for line in last_error.splitlines()[-12:]:
            log("  " + line[:220])

    return False, None, code, last_error or "unknown error"
