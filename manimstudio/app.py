"""Manim Studio — FastAPI app.

Endpoints:
    GET  /                         UI
    POST /api/jobs   {prompt}      -> {job_id}
    GET  /api/jobs/{id}            -> snapshot
    GET  /api/jobs/{id}/stream     SSE log + final
    GET  /api/stats/stream         SSE active count + recent
    GET  /videos/{id}.mp4          static mp4
    GET  /healthz
"""
from __future__ import annotations
import os, asyncio, json, secrets, time, contextlib
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import (
    HTMLResponse, JSONResponse, StreamingResponse, FileResponse,
)
from fastapi.staticfiles import StaticFiles

import db
import generator

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
VIDEO_DIR = Path(generator.VIDEO_DIR)
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "4"))
HOURLY_LIMIT_PER_IP = int(os.environ.get("HOURLY_LIMIT_PER_IP", "10"))
VIDEO_TTL_HOURS = int(os.environ.get("VIDEO_TTL_HOURS", "48"))

db.init()

app = FastAPI(title="Manim Studio")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# In-process state — single VM, no horizontal scale, so this is fine.
_render_sem = asyncio.Semaphore(MAX_CONCURRENT)
_log_queues: dict[str, list[asyncio.Queue]] = {}
_stats_subs: list[asyncio.Queue] = []

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
    "Content-Encoding": "identity",
}


# ── helpers ─────────────────────────────────────────────────────────────────
def client_ip(req: Request) -> str:
    fwd = req.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return req.client.host if req.client else "?"


def _publish_log(job_id: str, line: str):
    db.append_log(job_id, line)
    for q in _log_queues.get(job_id, []):
        with contextlib.suppress(Exception):
            q.put_nowait(("log", line))


def _publish_final(job_id: str, payload: dict):
    for q in _log_queues.get(job_id, []):
        with contextlib.suppress(Exception):
            q.put_nowait(("final", payload))


def _broadcast_stats():
    # no-op now that stats is short-polled; kept for symmetry / future use
    pass


# ── worker ──────────────────────────────────────────────────────────────────
async def _run_job(job_id: str, prompt: str):
    log = lambda line: _publish_log(job_id, line)
    db.update_job(job_id, status="drafting")
    _broadcast_stats()
    log(f"queued for render | concurrency cap={MAX_CONCURRENT}")

    async with _render_sem:
        db.update_job(job_id, status="rendering")
        _broadcast_stats()
        try:
            ok, mp4, code, err = await generator.generate(prompt, log)
        except Exception as e:
            ok, mp4, code, err = False, None, None, f"internal: {e}"

        if ok and mp4:
            rel = f"/videos/{Path(mp4).name}"
            db.update_job(job_id, status="done", video_path=mp4)
            _publish_final(job_id, {"ok": True, "video_url": rel})
        else:
            db.update_job(job_id, status="failed", error=(err or "unknown")[:8000])
            _publish_final(job_id, {"ok": False, "error": (err or "unknown")[:2000]})

        _broadcast_stats()


# ── routes ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC / "index.html").read_text()


@app.get("/healthz")
async def healthz():
    return {"ok": True, "active": db.count_active()}


@app.post("/api/jobs")
async def create_job(req: Request):
    body = await req.json()
    prompt = (body or {}).get("prompt", "").strip()
    if not (5 <= len(prompt) <= 2000):
        raise HTTPException(400, "prompt must be 5..2000 chars")

    ip = client_ip(req)
    if db.ip_has_active(ip):
        raise HTTPException(429, "you already have a job in flight; wait for it to finish")
    if db.count_by_ip_since(ip, time.time() - 3600) >= HOURLY_LIMIT_PER_IP:
        raise HTTPException(429, f"hourly limit ({HOURLY_LIMIT_PER_IP}) reached for your IP")

    job_id = secrets.token_urlsafe(9)
    db.create_job(job_id, ip, prompt)
    asyncio.create_task(_run_job(job_id, prompt))
    _broadcast_stats()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    j = db.get_job(job_id)
    if not j:
        raise HTTPException(404)
    if j.get("video_path"):
        j["video_url"] = f"/videos/{Path(j['video_path']).name}"
    return j


@app.get("/api/jobs/{job_id}/poll")
async def poll_job(job_id: str, since: int = 0):
    """Long-poll: returns new log lines (and final state) since the given offset."""
    j = db.get_job(job_id)
    if not j:
        raise HTTPException(404)
    log = j.get("log") or ""
    if since < len(log) or j["status"] in ("done", "failed"):
        delta = log[since:]
        out = {"offset": len(log), "delta": delta, "status": j["status"]}
        if j["status"] == "done" and j.get("video_path"):
            out["video_url"] = f"/videos/{Path(j['video_path']).name}"
        if j["status"] == "failed":
            out["error"] = j.get("error") or "failed"
        return out

    # No new data yet — wait up to 12s for an event or new log line.
    queue: asyncio.Queue = asyncio.Queue()
    _log_queues.setdefault(job_id, []).append(queue)
    try:
        try:
            await asyncio.wait_for(queue.get(), timeout=12)
        except asyncio.TimeoutError:
            pass
    finally:
        _log_queues[job_id].remove(queue)
        if not _log_queues[job_id]:
            _log_queues.pop(job_id, None)

    j = db.get_job(job_id)
    log = (j.get("log") or "")
    out = {"offset": len(log), "delta": log[since:], "status": j["status"]}
    if j["status"] == "done" and j.get("video_path"):
        out["video_url"] = f"/videos/{Path(j['video_path']).name}"
    if j["status"] == "failed":
        out["error"] = j.get("error") or "failed"
    return out


@app.get("/api/stats")
async def stats():
    return {"active": db.count_active(), "recent": db.list_recent(8)}


@app.get("/videos/{name}")
async def video(name: str):
    if "/" in name or ".." in name or not name.endswith(".mp4"):
        raise HTTPException(400)
    p = VIDEO_DIR / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="video/mp4")


def _sse(event: str, data) -> str:
    if not isinstance(data, str):
        data = json.dumps(data)
    return f"event: {event}\ndata: {data}\n\n"


# ── housekeeping: TTL on mp4s ───────────────────────────────────────────────
async def _cleanup_loop():
    while True:
        cutoff = time.time() - VIDEO_TTL_HOURS * 3600
        for p in VIDEO_DIR.glob("*.mp4"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
            except FileNotFoundError:
                pass
        await asyncio.sleep(3600)


@app.on_event("startup")
async def _startup():
    db.reap_orphans()
    asyncio.create_task(_cleanup_loop())
