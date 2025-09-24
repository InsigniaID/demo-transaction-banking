FROM python:3.11-slim
WORKDIR /app

COPY . /app/

RUN apt-get update && apt-get install -y \
    curl gcc g++ make cmake pkg-config \
    libssl-dev libsasl2-dev \
    bash

RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && az --version

RUN curl -L https://github.com/confluentinc/librdkafka/archive/refs/tags/v2.11.1.tar.gz -o librdkafka.tar.gz \
    && tar xzf librdkafka.tar.gz \
    && cd librdkafka-2.11.1 \
    && ./configure \
    && make -j$(nproc) \
    && make install

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH="/root/.local/bin:$PATH"

RUN uv sync