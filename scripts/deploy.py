"""Deploy Manim Studio to InstaVM.

- Creates a 7-day VM (or reuses one tagged `app=manim-studio`).
- Uploads all source files.
- Installs system deps + Python packages.
- Writes a systemd unit + starts it.
- Creates a public share on port 8000.
- Verifies the share with an external curl.

    python scripts/deploy.py
"""
from __future__ import annotations
import os, sys, time, pathlib, json
from instavm import InstaVM

KEY = pathlib.Path("~/.manim.txt").expanduser().read_text().strip()
OPENAI_KEY = pathlib.Path("~/.3b1b_openai_key.txt").expanduser().read_text().strip()
MANIM_SNAPSHOT_ID = (pathlib.Path(__file__).resolve().parent.parent / ".snapshot_id").read_text().strip() if (pathlib.Path(__file__).resolve().parent.parent / ".snapshot_id").exists() else ""

REPO  = pathlib.Path(__file__).resolve().parent.parent
APP_SRC = REPO / "manimstudio"
REMOTE_APP = "/app/manimstudio"
VM_LIFETIME = 7 * 24 * 3600       # 7 days
APP_TAG = "manim-studio"
SHARE_PORT = 8000

UPLOAD_FILES = [
    "app.py",
    "db.py",
    "generator.py",
    "requirements.txt",
    "static/index.html",
    "static/app.css",
    "static/app.js",
]


def step(msg): print(f"\n== {msg} ==", flush=True)


def find_or_create_vm(client: InstaVM) -> dict:
    for v in client.vms.list():
        meta = v.get("metadata") or {}
        if meta.get("app") == APP_TAG and v.get("status") in ("running", "starting", "ready"):
            print(f"[=] reusing VM {v['vm_id']} (status={v['status']})")
            return v
    step("creating VM (7d lifetime, 4 vCPU, 4 GB)")
    v = client.vms.create(
        wait=True,
        vm_lifetime_seconds=VM_LIFETIME,
        memory_mb=4096,
        vcpu_count=4,
        metadata={"app": APP_TAG, "purpose": "manim-studio frontend"},
    )
    print("[+] vm:", v.get("vm_id"), v.get("status"))
    return v


def install_deps(client: InstaVM):
    step("system deps")
    r = client.execute(
        "set -e; export DEBIAN_FRONTEND=noninteractive; "
        "sudo apt-get update -qq && "
        "sudo apt-get install -y -qq python3-pip >/dev/null 2>&1 && echo ok",
        language="bash",
    )
    assert "ok" in (r.get("stdout") or ""), r

    step("python deps")
    r = client.execute(
        f"python3 -m pip install --quiet --upgrade pip && "
        f"python3 -m pip install --quiet -r {REMOTE_APP}/requirements.txt && "
        f"python3 -c 'import fastapi, openai, instavm, uvicorn; print(\"ok\")'",
        language="bash",
    )
    print(r.get("stdout"))
    assert "ok" in (r.get("stdout") or ""), r


def upload_source(client: InstaVM):
    step("upload source")
    client.execute(f"mkdir -p {REMOTE_APP}/static {REMOTE_APP}/videos", language="bash")
    for rel in UPLOAD_FILES:
        local = APP_SRC / rel
        remote = f"{REMOTE_APP}/{rel}"
        print(f"  {rel}")
        client.upload_file(str(local), remote)


def write_systemd(client: InstaVM):
    step("systemd unit")
    unit = f"""[Unit]
Description=Manim Studio webapp
After=network.target

[Service]
WorkingDirectory={REMOTE_APP}
Environment=OPENAI_API_KEY={OPENAI_KEY}
Environment=INSTAVM_API_KEY={KEY}
Environment=MS_DB_PATH={REMOTE_APP}/jobs.db
Environment=VIDEO_DIR={REMOTE_APP}/videos
Environment=OPENAI_MODEL=gpt-5.4
Environment=MAX_CONCURRENT=4
Environment=MAX_ATTEMPTS=3
Environment=RENDER_TIMEOUT=900
Environment=MANIM_BASE_SNAPSHOT_ID={MANIM_SNAPSHOT_ID}
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/local/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port {SHARE_PORT}
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    payload = repr(unit)
    client.execute(
        f"python3 -c \"open('/etc/systemd/system/manim-studio.service','w').write({payload})\"",
        language="bash",
    )
    client.execute("systemctl daemon-reload", language="bash")
    client.execute("systemctl enable manim-studio.service", language="bash")
    client.execute("systemctl restart manim-studio.service", language="bash")
    time.sleep(2)
    r = client.execute("systemctl status --no-pager manim-studio.service | head -25", language="bash")
    print(r.get("stdout"))


def verify_local(client: InstaVM):
    step("local health probe")
    probe = (
        "import urllib.request, time\n"
        "deadline = time.time() + 30\n"
        "err = None\n"
        "while time.time() < deadline:\n"
        "    try:\n"
        f"        r = urllib.request.urlopen('http://127.0.0.1:{SHARE_PORT}/healthz', timeout=3)\n"
        "        print('HTTP', r.status, r.read().decode())\n"
        "        break\n"
        "    except Exception as e:\n"
        "        err = e\n"
        "        time.sleep(1)\n"
        "else:\n"
        "    raise SystemExit('not healthy: ' + repr(err))\n"
    )
    r = client.execute(probe, language="python")
    print(r.get("stdout") or r.get("stderr"))


def create_share(client: InstaVM, vm: dict) -> str | None:
    step("public share")
    existing = None
    try:
        shares = client.shares.list() if hasattr(client.shares, "list") else []
        for s in shares:
            if s.get("vm_id") == vm["vm_id"] and s.get("port") == SHARE_PORT:
                existing = s
                break
    except Exception:
        pass
    if existing:
        print("[=] reusing share:", existing.get("share_id") or existing.get("id"))
        share = existing
    else:
        share = client.shares.create(port=SHARE_PORT, vm_id=vm["vm_id"], is_public=True)
        print("[+] share:", share)
    url = share.get("url") or share.get("share_url") or share.get("host")
    if not url:
        host = share.get("hostname") or share.get("subdomain")
        if host:
            url = f"https://{host}.instavm.site" if "." not in host else f"https://{host}"
    return url


def main():
    print(">> instavm key tail:", KEY[-6:])
    client = InstaVM(api_key=KEY, timeout=900)
    vm = find_or_create_vm(client)
    session_id = vm.get("session_id")
    if not session_id:
        vm = client.vms.get(vm["vm_id"])
        session_id = vm.get("session_id")
    if not session_id:
        sys.exit("no session_id on VM; cannot SDK-upload")
    client.session_id = session_id
    print(">> bound session:", session_id[:8])

    upload_source(client)
    install_deps(client)
    write_systemd(client)
    verify_local(client)
    url = create_share(client, vm)

    print("\n==================================================")
    print("  Manim Studio is live at:")
    print("    " + (url or "<share returned no url; check share list>"))
    print("==================================================\n")

    if url:
        import urllib.request
        try:
            with urllib.request.urlopen(url + "/healthz", timeout=20) as r:
                print(">> external curl:", r.status, r.read().decode()[:120])
        except Exception as e:
            print(">> external curl FAILED:", e)


if __name__ == "__main__":
    main()
