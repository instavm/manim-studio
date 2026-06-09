# manim-studio

Prompt → OpenAI writes a Manim scene → renders on InstaVM → MP4.

**Live:** https://elated-capable-pronghorn.instavm.site/

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

```bash
pip install -U instavm openai fastapi uvicorn
export INSTAVM_API_KEY=...
export OPENAI_API_KEY=...

# one-time: store openai key in instavm vault
python scripts/setup_vault.py

# deploy (uses the public manim base image by default)
python scripts/deploy.py
```

## Tuning

- Render VM: `memory_mb=8192, vcpu_count=8` in `generator.py`.
- Base image is env-gated. The deploy script sets a sensible default:
  - `MANIM_BASE_OCI_IMAGE` (default: `instavm/manim-base:0.20.1`) — public Docker Hub image, anyone can use.
  - `MANIM_BASE_SNAPSHOT_ID` — private InstaVM snapshot, account-scoped fallback.
  - If both unset, generator falls back to a slow apt+pip path on every render.

## Known gotchas

- `deploy.py::find_or_create_vm` checks `status in ("running","starting","ready")`
  but the API returns `"active"` — so each deploy spawns a fresh VM. Cosmetic.
- Share subdomain is randomly assigned by InstaVM.
