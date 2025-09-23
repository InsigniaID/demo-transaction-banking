FROM python:3.11.13-alpine3.22
WORKDIR /app

COPY . /app/

RUN apk add --no-cache \
    gcc \
    g++ \
    musl-dev \
    python3-dev \
    librdkafka-dev \
    cmake \
    pkgconf \
    make

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH="/root/.local/bin:$PATH"

RUN uv sync