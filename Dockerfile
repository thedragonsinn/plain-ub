FROM python:3.12.7-slim-bookworm

ENV PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app/

RUN apt -qq update && apt -qq upgrade -y && \
    apt -qq install -y --no-install-recommends \
    apt-utils \
    build-essential coreutils \
    curl \
    ffmpeg \
    mediainfo \
    neofetch \
    git \
    wget && \
    pip install -U pip setuptools wheel && \
    git config --global user.email "98635854+thedragonsinn@users.noreply.github.com" && \
    git config --global user.name "thedragonsinn"

EXPOSE 8080 
 
CMD bash -c "$(curl -fsSL https://raw.githubusercontent.com/thedragonsinn/plain-ub/main/docker_start.sh)"
