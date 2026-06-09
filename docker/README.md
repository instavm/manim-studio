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

Set on the app VM (and locally for `render_in_instavm.py`):

```bash
export MANIM_BASE_OCI_IMAGE=instavm/manim-base:0.20.1
```

If both `MANIM_BASE_OCI_IMAGE` and `MANIM_BASE_SNAPSHOT_ID` are set, the OCI
image wins. With neither set the generator falls back to an ephemeral
sandbox and installs manim live (slow).
