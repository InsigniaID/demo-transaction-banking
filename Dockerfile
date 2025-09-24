FROM python:3.11.13-alpine3.22
WORKDIR /app

COPY . /app/

RUN apk add --no-cache \
    bash curl gcc g++ make cmake pkgconf \
    musl-dev python3-dev \
    zlib-dev openssl-dev cyrus-sasl-dev \
    nodejs npm

RUN npm install -g azure-cli \
    && ln -s $(npm root -g)/.bin/az /usr/local/bin/az \
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