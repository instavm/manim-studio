"""Render instavm_egress.py inside an InstaVM sandbox and pull back the mp4."""
import os, sys, time
from instavm import InstaVM

api_key = os.environ["INSTAVM_API_KEY"]
LOCAL_SCRIPT = "/Users/manish/Work/3b1bhosted/instavm_egress.py"
REMOTE_SCRIPT = "/tmp/instavm_egress.py"
OUT_LOCAL = "/Users/manish/Work/3b1bhosted/InstaVMEgress.mp4"

with InstaVM(api_key=api_key, timeout=1800) as client:
    print(">> session:", client.get_session_info())

    print(">> probing env")
    print(client.execute("uname -a && python3 --version && which ffmpeg || true", language="bash"))

    print(">> installing system deps")
    print(client.execute(
        "set -e; export DEBIAN_FRONTEND=noninteractive; "
        "sudo apt-get update -qq && "
        "sudo apt-get install -y -qq libcairo2-dev libpango1.0-dev pkg-config "
        "python3-dev ffmpeg build-essential 2>&1 | tail -20",
        language="bash",
    ))

    print(">> installing manim")
    print(client.execute("pip install --quiet --upgrade pip && pip install --quiet manim 2>&1 | tail -10",
                          language="bash"))
    print(client.execute("python3 -c 'import manim; print(manim.__version__)'", language="bash"))

    print(">> uploading scene")
    client.upload_file(LOCAL_SCRIPT, REMOTE_SCRIPT)

    print(">> rendering (high quality)")
    print(client.execute(
        f"cd /tmp && manim -qh --disable_caching {REMOTE_SCRIPT} InstaVMEgress 2>&1 | tail -40",
        language="bash",
    ))

    print(">> locating output")
    find = client.execute("find /tmp/media -name 'InstaVMEgress*.mp4' -printf '%p\\n' 2>/dev/null", language="bash")
    print(find)
    # parse the stdout
    out = find.get("stdout") if isinstance(find, dict) else str(find)
    candidate = next((l.strip() for l in out.splitlines() if l.strip().endswith(".mp4")), None)
    if not candidate:
        print("!! no mp4 found"); sys.exit(1)
    print(">> remote file:", candidate)

    print(">> downloading")
    client.download_file(candidate, local_path=OUT_LOCAL)
    print(">> saved to:", OUT_LOCAL)
