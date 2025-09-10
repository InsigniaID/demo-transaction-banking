FROM python:3.13.3-alpine3.22
WORKDIR /app

COPY . /app/

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH="/root/.local/bin:$PATH"

RUN uv sync