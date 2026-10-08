# V3 サーバーのアプリのイメージ。口（uvicorn）と Temporal の作業者は、同じイメージで command だけ変える。
# 文脈は v3/（web と psd_writer も入れるため）。compose.prod.yaml から作る。
#   docker build -f server/deploy/Dockerfile -t v3-app v3/
# 通信を検査する代理を通す環境では、その CA を秘密として渡す（イメージには残らない）:
#   docker build --secret id=build_ca,src=<CA の束> ...
# 版は固定する。上げるときは llm_doc/V3サーバーの土台.md 1.5 の表も直す。

FROM ghcr.io/astral-sh/uv:0.11.32 AS uv

# PSD を書く・文字を絵にする Node の部品（v3/psd_writer）
FROM node:22.23.2-bookworm-slim AS node
WORKDIR /app/psd_writer
COPY psd_writer/package.json ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm install --omit=dev --no-audit --no-fund

FROM python:3.13.15-slim-bookworm AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app/server
COPY server/pyproject.toml server/uv.lock ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY server/alembic.ini ./
COPY server/migrations ./migrations
COPY server/openfga ./openfga
COPY server/src ./src
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    uv sync --frozen --no-dev

FROM python:3.13.15-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /app/psd_writer/node_modules /app/psd_writer/node_modules
COPY psd_writer/package.json psd_writer/*.js /app/psd_writer/
COPY web /app/web
COPY --from=build /app/server /app/server
RUN useradd --system --uid 10001 v3 && mkdir -p /data/exports /data/fonts && chown v3 /data/exports
USER v3
WORKDIR /app/server
# このイメージでは開発用の名乗り方（V3_AUTH_MODE=dev_header）で起動しない（server_settings.py）
ENV PATH=/app/server/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    V3_FORBID_DEV_HEADER=1
CMD ["uvicorn", "v3server.http_routes.http_app_factory:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
