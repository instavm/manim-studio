# manim-studio

Prompt → OpenAI writes a Manim scene → renders on InstaVM → MP4.

**Live:** https://crafty-resilient-grebe.instavm.site/

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Architecture

- FastAPI app on a long-lived InstaVM VM (`manimstudio/app.py`).
- Each render spawns a short-lived VM from a pre-built base image
  (`manim==0.20.1` + cairo/pango/ffmpeg). Cold start ~15s.
- Long-poll job API (`/api/jobs`, `/api/jobs/{id}/poll`).

## Files

```
manimstudio/
  app.py            FastAPI app + long-poll endpoints
  generator.py      OpenAI prompt → manim scene → render on InstaVM
  db.py             SQLite job store
  static/           UI
scripts/
  deploy.py         Provision app VM, push code, start systemd unit
  setup_vault.py    Store OpenAI key in InstaVM vault
docker/
  Dockerfile        Public manim base image (instavm/manim-base:0.20.1)
.snapshot_id        Optional: private snapshot UUID (gitignored)
```

## Setup
Get InstaVM key: [https://dashboard.instavm.io](https://dashboard.instavm.io/auth/signup)
and OpenAI key: https://platform.openai.com
```
bash
pip install -U instavm openai fastapi uvicorn
export INSTAVM_API_KEY=...
export OPENAI_API_KEY=...

# one-time: store openai key in instavm vault
python scripts/setup_vault.py

# deploy (uses the public manim base image by default)
python scripts/deploy.py
```

## Tuning

- Render VM: `memory_mb=2048, vcpu_count=2` in `generator.py`.
- Base image: `MANIM_BASE_OCI_IMAGE` (default `instavm/manim-base:0.20.1`).

## Known gotchas

- `deploy.py::find_or_create_vm` checks `status in ("running","starting","ready")`
  but the API returns `"active"` — so each deploy spawns a fresh VM. Cosmetic.
- Share subdomain is randomly assigned by InstaVM.
