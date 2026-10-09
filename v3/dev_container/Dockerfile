# 手元の Windows から、V3 のサーバーと試験を Linux で動かすための作業用のコンテナ（llm_doc/V3サーバーの土台.md 1.1.1）。
# 入れる物：Python 3.13・uv・Node 22・Playwright とブラウザ（画面の試験）・明朝のフォント（組版の試験）・
# docker の CLI と compose・socat（通し試験 e2e が、試験用の compose を自分で起こして、そのポートへつなぐ）。
# リポジトリは載せない（動かすときに /repo へ bind する）。仮想環境は /venv（ボリューム）に作る。
#   docker build -t v3dev v3/dev_container
FROM node:22-bookworm-slim AS node
FROM ghcr.io/astral-sh/uv:0.9.21 AS uv
FROM docker:27-cli AS dockercli
FROM python:3.13-slim-bookworm
COPY --from=uv /uv /bin/uv
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
ENV UV_PROJECT_ENVIRONMENT=/venv UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1 PATH=/venv/bin:$PATH \
    NODE_PATH=/usr/local/lib/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
# Playwright の版は CI（.github/workflows/v3-server.yml）と同じにする
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && apt-get update && apt-get install -y --no-install-recommends curl git socat fonts-ipafont-mincho \
 && npm install -g --no-audit --no-fund playwright@1.56.1 \
 && node /usr/local/lib/node_modules/playwright/cli.js install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/* /root/.npm
WORKDIR /repo/v3/server
CMD ["sleep", "infinity"]
