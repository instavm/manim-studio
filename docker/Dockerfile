FROM python:3.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential pkg-config \
        libcairo2-dev libpango1.0-dev \
        ffmpeg \
        sudo curl ca-certificates coreutils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && pip install \
        manim==0.20.1 \
        numpy==2.4.6 scipy==1.17.1 networkx==3.6.1 pillow==12.2.0 \
        moderngl==5.12.0 moderngl-window==3.1.1 \
        ManimPango==0.6.1 pycairo==1.29.0 \
        cloup==3.1.0 isosurfaces==0.1.2 mapbox_earcut==2.0.0 \
        pydub==0.25.1 skia-pathops==0.9.2 svgelements==1.9.6

WORKDIR /work
CMD ["bash"]
