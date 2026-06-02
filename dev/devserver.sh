#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LABEL="com.manga-editor.devserver"
PLIST_TEMPLATE="$SCRIPT_DIR/${LABEL}.plist.template"
PLIST_INSTALLED="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/manga-editor"
DOMAIN="gui/$(id -u)"
SERVICE="$DOMAIN/$LABEL"

UV_PATH="$(command -v uv 2>/dev/null || true)"
if [ -z "$UV_PATH" ]; then
    UV_PATH="/opt/homebrew/bin/uv"
fi

render_plist() {
    mkdir -p "$LOG_DIR"
    mkdir -p "$(dirname "$PLIST_INSTALLED")"
    sed \
        -e "s|{{UV_PATH}}|$UV_PATH|g" \
        -e "s|{{PROJECT_DIR}}|$PROJECT_DIR|g" \
        -e "s|{{LOG_DIR}}|$LOG_DIR|g" \
        "$PLIST_TEMPLATE" > "$PLIST_INSTALLED"
}

is_loaded() {
    launchctl print "$SERVICE" >/dev/null 2>&1
}

cmd="${1:-help}"

case "$cmd" in
    install)
        render_plist
        if is_loaded; then
            launchctl bootout "$SERVICE" || true
        fi
        launchctl bootstrap "$DOMAIN" "$PLIST_INSTALLED"
        launchctl kickstart -k "$SERVICE" || true
        echo "Installed: $LABEL -> http://localhost:8125"
        echo "Logs: $LOG_DIR/devserver.{out,err}.log"
        ;;
    uninstall)
        if is_loaded; then
            launchctl bootout "$SERVICE" || true
        fi
        rm -f "$PLIST_INSTALLED"
        echo "Uninstalled: $LABEL"
        ;;
    start)
        launchctl kickstart "$SERVICE"
        ;;
    stop)
        launchctl kill SIGTERM "$SERVICE" || true
        ;;
    restart)
        launchctl kickstart -k "$SERVICE"
        ;;
    status)
        if is_loaded; then
            launchctl print "$SERVICE" | sed -n '1,40p'
        else
            echo "$LABEL is not loaded. Run: $0 install"
        fi
        ;;
    logs)
        tail -F "$LOG_DIR/devserver.out.log" "$LOG_DIR/devserver.err.log"
        ;;
    *)
        cat <<EOF
Usage: $0 {install|uninstall|start|stop|restart|status|logs}

  install    plistを ~/Library/LaunchAgents/ に展開し launchd に登録・起動
  uninstall  launchd から登録解除し plist を削除
  start      サービス開始
  stop       サービス停止
  restart    再起動 (kickstart -k)
  status     状態表示
  logs       ログを tail -F

ポート: 8125  (http://localhost:8125)
コード変更時の自動再起動は uvicorn --reload が担当
EOF
        ;;
esac
