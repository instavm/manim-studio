# manim-base image

Reproducible base image used by `manimstudio/generator.py` to render scenes
on InstaVM. Mirrors the Debian 12 + Python 3.13 + manim 0.20.1 + cairo/pango
+ ffmpeg setup.

## Build & push

```bash
docker buildx build --platform linux/amd64 \
  -t instavm/manim-base:0.20.1 \
  -t instavm/manim-base:latest \
  --push docker/
```

`scripts/deploy.py` uses `instavm/manim-base:0.20.1` by default — no manual
setup needed.
