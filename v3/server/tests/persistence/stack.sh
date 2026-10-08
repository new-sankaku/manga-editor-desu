#!/usr/bin/env bash
# 保存と再起動の確かめ（v3/web/test/persistence_e2e.mjs）が使う、ほかの作業と分けた一式を動かす。
# 既製品は compose.persistence.yaml（名前 v3pe・口はほかの作業と重ならない番号）。
# 口のサーバー（uvicorn）・作業者（偽の LLM・検出器。fake_workers_main.py）・偽の ComfyUI は別々のプロセスで、
# 起動は手元で動かすとき（V3サーバーの土台 1.1）と同じ設定（dev_header・絵は手元のフォルダ）。
#
#   stack.sh up | down | wipe | restart-infra | migrate | start api|workers|comfy | stop api|workers|comfy | status | pytest <引数>
#
# 置き場：PE_DIR（既定 /tmp/v3pe）。絵・書き出し・ログ・pid をここに置く。
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER="$(cd "$HERE/../.." && pwd)"
V3="$(cd "$SERVER/.." && pwd)"
PE_DIR="${PE_DIR:-/tmp/v3pe}"
API_PORT="${V3PE_API_PORT:-8961}"
COMFY_PORT="${V3PE_COMFY_PORT:-8963}"
export V3PE_PG_PORT="${V3PE_PG_PORT:-55961}"
export V3PE_TEMPORAL_PORT="${V3PE_TEMPORAL_PORT:-57961}"
export V3PE_OPENFGA_PORT="${V3PE_OPENFGA_PORT:-58991}"
export OPENFGA_PRESHARED_KEY="${OPENFGA_PRESHARED_KEY:-v3pe-preshared-key-0123456789}"
export V3_DATABASE_URL="postgresql+psycopg://v3:v3@127.0.0.1:${V3PE_PG_PORT}/v3"
export V3_TEMPORAL_ADDRESS="127.0.0.1:${V3PE_TEMPORAL_PORT}"
export V3_OPENFGA_URL="http://127.0.0.1:${V3PE_OPENFGA_PORT}"
# LLM は偽物（作業者の中で差し替える）。口の設定に要るので、届かない住所を入れておく
export V3_LITELLM_URL="http://127.0.0.1:9"
export V3_AUTH_MODE=dev_header
export V3_IMAGE_STORE=local
export V3_IMAGE_DIR="$PE_DIR/images"
export V3_EXPORT_DIR="$PE_DIR/exports"
export V3_FONT_DIR="${V3_FONT_DIR:-/usr/share/fonts/opentype/ipafont-mincho}"
export V3_NODE_EXECUTABLE="${V3_NODE_EXECUTABLE:-$(command -v node)}"
export V3_PSD_WRITER_SCRIPT="$V3/psd_writer/write_layered_psd.js"
export V3_TEXT_RENDER_SCRIPT="$V3/psd_writer/render_text.js"
export V3_REQUEST_MAX_BYTES=268435456
export V3_IMAGE_MAX_PIXELS=89478485
export V3_PSD_MAX_LAYERS=1000
export V3_LOCK_TTL_SECONDS=900
export V3_CURRENT_APP_IMPORT_MAX_BYTES=1073741824
COMPOSE=(docker compose -f "$HERE/compose.persistence.yaml")
mkdir -p "$PE_DIR/images" "$PE_DIR/exports" "$PE_DIR/run"

cmd_of() {
  case "$1" in
    api) echo "uv run uvicorn v3server.http_routes.http_app_factory:app --host 127.0.0.1 --port $API_PORT" ;;
    workers) echo "uv run python tests/persistence/fake_workers_main.py" ;;
    comfy) echo "uv run python tests/persistence/fake_comfy_main.py --port $COMFY_PORT --steps ${V3PE_COMFY_STEPS:-20} --step-seconds ${V3PE_COMFY_STEP_SECONDS:-0.3}" ;;
    *) echo "知らないプロセス: $1" >&2; exit 2 ;;
  esac
}

start() {
  local name="$1" pidf="$PE_DIR/run/$1.pid"
  if [[ -f "$pidf" ]] && kill -0 "$(cat "$pidf")" 2>/dev/null; then echo "$name は動いている"; return; fi
  cd "$SERVER"
  # setsid で別のプロセスの組にする（止めるときに uv の子の python まで一緒に止める）
  setsid bash -c "exec $(cmd_of "$name")" >>"$PE_DIR/run/$name.log" 2>&1 &
  echo $! >"$pidf"
}

stop() {
  local name="$1" pidf="$PE_DIR/run/$1.pid" sig="${2:-TERM}"
  [[ -f "$pidf" ]] || return 0
  local pid; pid="$(cat "$pidf")"
  kill "-$sig" -- "-$pid" 2>/dev/null || true
  for _ in $(seq 1 100); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
  kill -KILL -- "-$pid" 2>/dev/null || true
  rm -f "$pidf"
}

case "${1:-}" in
  up) "${COMPOSE[@]}" up -d --wait postgres temporal openfga ;;
  down) "${COMPOSE[@]}" down ;;
  wipe) "${COMPOSE[@]}" down -v; rm -rf "$PE_DIR" ;;
  restart-infra) "${COMPOSE[@]}" restart postgres temporal openfga ;;
  migrate) cd "$SERVER" && uv run alembic upgrade head ;;
  grant-admin) cd "$SERVER" && uv run python -m v3server.admin_command_line grant-admin "$2" ;;
  start) start "$2" ;;
  stop) stop "$2" "${3:-TERM}" ;;
  # この一式の PostgreSQL（v3_test）・Temporal・OpenFGA で pytest を流す。作業者（workers）は先に止める
  # （同じ Temporal の待ち行列を、v3 のデータベースを見る作業者が取ってしまうため。V3サーバーの土台 1.1）
  pytest) shift; stop workers; cd "$SERVER" && exec uv run pytest "$@" ;;
  status) for n in api workers comfy; do f="$PE_DIR/run/$n.pid"; if [[ -f "$f" ]] && kill -0 "$(cat "$f")" 2>/dev/null; then echo "$n up"; else echo "$n down"; fi; done ;;
  *) echo "使い方: $0 up|down|wipe|restart-infra|migrate|grant-admin <名>|start <名>|stop <名> [信号]|status" >&2; exit 2 ;;
esac
