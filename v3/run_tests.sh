#!/usr/bin/env bash
# V3 の試験の組（llm_doc/V3サーバーの土台.md 1.1「試験の組」）
#   v3/run_tests.sh fast   既定。計算の試験・速い統合の試験（同時に流す）・PSD の部品・偽のサーバーと録った答えの画面の試験
#   v3/run_tests.sh full   fast ＋ 本物の Temporal の試験・重い書き出しの試験（pytest の full の印）・本物のサーバーの画面の試験
#   v3/run_tests.sh perf   大きな絵で時間を測る（tests/perf と原稿の画面の速さ）
#   v3/run_tests.sh e2e    保存と起こし直し（v3/web/test/persistence_e2e.mjs。プロセスを止めて起こすので遅い）
# 前もって：v3/server で .env を用意し、compose（PostgreSQL・Temporal・OpenFGA）を動かす。v3/psd_writer で npm ci。
# 画面の試験は NODE_PATH に playwright、PLAYWRIGHT_BROWSERS_PATH にブラウザが要る（無ければ /opt の物を使う）。
# 同時に流す数は V3_TEST_WORKERS（既定は CPU の数。最大 4）。画面の写しは SHOTS=<フォルダ> を付けたときだけ撮る。
set -euo pipefail

SUITE="${1:-fast}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SERVER="$HERE/server"
export NODE_PATH="${NODE_PATH:-/opt/node22/lib/node_modules}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}"
CPUS="$(nproc)"
WORKERS="${V3_TEST_WORKERS:-$(( CPUS < 4 ? CPUS : 4 ))}"
# 本物の ComfyUI・検出器・S3 の試験は住所が無ければ飛ぶ（それぞれの試験の skipif）
PYTEST=(uv run --directory "$SERVER" pytest -q -p no:cacheprovider)

declare -a SUMMARY=()
step() {  # step <名前> <コマンド…>：時間を測って流す
  local name="$1"; shift
  local t0; t0=$(date +%s)
  echo "===== $name"
  "$@"
  SUMMARY+=("$(printf '%5d 秒  %s' $(( $(date +%s) - t0 )) "$name")")
}
summary() { echo; echo "試験の組（$SUITE）"; printf '%s\n' "${SUMMARY[@]}"; }

fast_python() {
  step "計算の試験（tests/unit）" "${PYTEST[@]}" tests/unit
  step "速い統合の試験（tests/integration、${WORKERS} 本同時）" \
    "${PYTEST[@]}" -n "$WORKERS" --dist load -m "not full and not perf" tests/integration
  step "PSD・組版の部品（v3/psd_writer）" npm --prefix "$HERE/psd_writer" test --silent
}

# 試験用のデータベースを作る・消す（.env の V3_DATABASE_URL と同じ PostgreSQL に、名前だけ替えて）
db_admin() {  # db_admin create|drop <名前>  → create のときは住所を出す
  uv run --directory "$SERVER" python - "$1" "$2" <<'PY'
import sys, psycopg
from sqlalchemy.engine import make_url
from v3server.server_settings import Settings
op, name = sys.argv[1], sys.argv[2]
url = make_url(Settings().database_url)
with psycopg.connect(url.set(database="postgres", drivername="postgresql").render_as_string(hide_password=False), autocommit=True) as c:
    c.execute(f'CREATE DATABASE "{name}"' if op == "create" else f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
if op == "create":
    print(url.set(database=name).render_as_string(hide_password=False))
PY
}
# 本物のサーバーを新しいデータベースで起こす（画面の試験の間だけ）。SERVER_PID に入れる
start_real_server() {
  local port="$1" dburl="$2" dir="$3"
  mkdir -p "$dir/images" "$dir/exports"
  local -a envs=(env V3_DATABASE_URL="$dburl" V3_IMAGE_DIR="$dir/images" V3_EXPORT_DIR="$dir/exports" V3_AUTH_MODE=dev_header)
  "${envs[@]}" uv run --directory "$SERVER" alembic upgrade head >"$dir/alembic.log" 2>&1
  "${envs[@]}" uv run --directory "$SERVER" python -m v3server.admin_command_line grant-admin scr-admin
  "${envs[@]}" uv run --directory "$SERVER" uvicorn v3server.http_routes.http_app_factory:app --port "$port" >"$dir/server.log" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 150); do curl -fs "http://127.0.0.1:$port/health" >/dev/null && return 0; sleep 0.2; done
  echo "本物のサーバーが起きなかった（$dir/server.log）"; return 1
}
free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }

case "$SUITE" in
  fast)
    fast_python
    step "画面の試験（偽のサーバー・録った答え）" node "$HERE/web/test/run_ui.mjs" fast
    ;;
  full)
    fast_python
    # 本物の Temporal の名前空間 default を使う。ハーネスの動く見本と同時には流さない（同じ待ち行列の依頼を取り合う）
    step "重い試験（pytest の full の印。本物の Temporal・書き出しの描画）" "${PYTEST[@]}" -m full tests/integration tests/unit
    WORK="$(mktemp -d)"
    STAMP="$(date +%s)_$$"
    UI_DB="v3_ui_$STAMP" DEMO_DB="v3_demo_$STAMP"
    PORT="$(free_port)" DEMO_PORT="$(free_port)"
    cleanup() {
      [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null || true
      [ -n "${DEMO_PID:-}" ] && kill "$DEMO_PID" 2>/dev/null || true
      wait 2>/dev/null || true
      db_admin drop "$UI_DB" >/dev/null || true; db_admin drop "$DEMO_DB" >/dev/null || true
    }
    trap cleanup EXIT
    start_real_server "$PORT" "$(db_admin create "$UI_DB")" "$WORK"
    # ハーネスの動く見本（本物のサーバー・Temporal・作業者。ComfyUI・LLM・検出器は偽物）。操作の口は DEMO_PORT+1
    DEMO_URL="$(db_admin create "$DEMO_DB")"
    V3_DEMO_DATABASE_URL="$DEMO_URL" uv run --directory "$SERVER" python tests/integration/harness_screen_demo.py --port "$DEMO_PORT" >"$WORK/demo.log" 2>&1 &
    DEMO_PID=$!
    for _ in $(seq 600); do grep -q "^READY" "$WORK/demo.log" 2>/dev/null && break; sleep 0.2; done
    grep -q "^READY" "$WORK/demo.log" || { echo "ハーネスの動く見本が起きなかった（$WORK/demo.log）"; exit 1; }
    step "画面の試験（fast ＋ 本物のサーバー・動く見本）" \
      env V3_ORIGIN="http://127.0.0.1:$PORT" CTRL="http://127.0.0.1:$((DEMO_PORT + 1))" node "$HERE/web/test/run_ui.mjs" full
    ;;
  perf)
    step "大きな絵の時間（tests/perf）" env V3_PERF=1 "${PYTEST[@]}" -m perf tests/perf
    step "原稿の画面の速さ（偽のサーバー）" node "$HERE/web/test/run_ui.mjs" perf
    ;;
  e2e)
    E2E="$HERE/web/test/persistence_e2e.mjs"
    [ -f "$E2E" ] || { echo "$E2E がまだ無い"; exit 1; }
    step "保存と起こし直し（persistence_e2e）" node "$E2E"
    ;;
  *)
    echo "組は fast・full・perf・e2e のどれか"; exit 2 ;;
esac
summary
