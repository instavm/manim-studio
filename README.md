# manim-studio

Prompt → OpenAI writes a Manim scene → renders on InstaVM → MP4.

**Live:** https://outgoing-lively-anaconda.instavm.site/

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Architecture

- FastAPI app on a long-lived InstaVM VM (`manimstudio/app.py`).
- Each render spawns a short-lived VM from a pre-built snapshot
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
.snapshot_id        UUID of the manim base snapshot (gitignored)
```

## Setup

```bash
pip install -U instavm openai fastapi uvicorn
export INSTAVM_API_KEY=...
export OPENAI_API_KEY=...

# one-time: store openai key in instavm vault
python scripts/setup_vault.py

# build manim base snapshot (one-time, ~5 min)
# writes snapshot UUID to .snapshot_id
# (see prior session for builder script)

python scripts/deploy.py
```

## Tuning

- Render VM: `memory_mb=2048, vcpu_count=2` in `generator.py`.
  2 GB is enough for `manim -qh` (720p). Going higher OOM'd the host worker.
- Snapshot path is env-gated: `MANIM_BASE_SNAPSHOT_ID`. Unset to fall
  back to the slow apt+pip path.

## Known gotchas

- `deploy.py::find_or_create_vm` checks `status in ("running","starting","ready")`
  but the API returns `"active"` — so each deploy spawns a fresh VM. Cosmetic.
- Share subdomain is randomly assigned by InstaVM.
