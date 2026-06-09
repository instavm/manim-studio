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

On first deploy, `ensure_snapshot()` calls `snapshots.create(oci_image=...)`
to bake a per-account InstaVM snapshot from the public image (~5 min),
then caches the snapshot id in `.snapshot_id` so subsequent deploys reuse
it. Renders use the cached snapshot.

InstaVM snapshots are account-scoped and not directly shareable, so the
OCI image is the portable artifact — every account bakes its own snapshot
from the same public image.
