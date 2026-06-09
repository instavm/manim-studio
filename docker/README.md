# manim-base image

Reproducible base image used by `manimstudio/generator.py` to render scenes
on InstaVM. Mirrors the Debian 12 + Python 3.13 + manim 0.20.1 + cairo/pango
+ ffmpeg setup that originally lived in a private InstaVM snapshot.

## Build & push

```bash
docker buildx build --platform linux/amd64 \
  -t instavm/manim-base:0.20.1 \
  -t instavm/manim-base:latest \
  --push docker/
```

## Use

`scripts/deploy.py` uses this image by default. Override with:

```bash
export MANIM_BASE_OCI_IMAGE=instavm/manim-base:0.20.1   # default
```

On first deploy `ensure_snapshot()` bakes it into an InstaVM snapshot
(~5 min) and caches the id in `.snapshot_id`.
