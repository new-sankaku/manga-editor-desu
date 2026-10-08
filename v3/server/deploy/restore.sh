#!/usr/bin/env bash
# 控えから、空の新しい環境へ戻す（V3サーバーの土台 1.4.4）。
#   deploy/restore.sh <env ファイル> <compose の project 名> <控えのフォルダ名（V3_BACKUP_HOST_DIR の中）>
# - 戻し先の project には volume が1つも無いこと。あれば止める（今のデータの上に重ねない）。
# - env ファイルは、控えを取った元と同じパスワードと鍵（POSTGRES_PASSWORD・V3_OIDC_CLIENT_SECRET・V3_S3_*）にする。
#   データベースの利用者のパスワードと Keycloak の client の秘密は、控えの中に入っている値が使われる。
# - V3_PUBLIC_URL も元と同じにする（Keycloak の戻り先の住所は控えの中の realm にある）。
# - PostgreSQL は控えと同じ版（16）で戻す。
set -euo pipefail

ENV_FILE=$1
PROJECT=$2
NAME=$3
HERE=$(cd "$(dirname "$0")" && pwd)
envval() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2-; }
dc() { docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$HERE/../compose.prod.yaml" "$@"; }

BUCKET=$(envval V3_S3_BUCKET)
SRC="$(envval V3_BACKUP_HOST_DIR)/$NAME"
[ -f "$SRC/postgres/base.tar.gz" ] || { echo "控えが無い: $SRC/postgres/base.tar.gz" >&2; exit 1; }
if [ -n "$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT")" ]; then
  echo "project $PROJECT には volume がある。空の環境にだけ戻す" >&2
  exit 1
fi

echo "1/3 PostgreSQL のデータのフォルダを控えから作る"
dc run --rm --no-deps -T --user root --entrypoint bash -v "$SRC/postgres:/restore:ro" postgres -c '
  set -euo pipefail
  cd /var/lib/postgresql/data
  tar xzf /restore/base.tar.gz
  mkdir -p pg_wal
  tar xzf /restore/pg_wal.tar.gz -C pg_wal
  chown -R postgres:postgres . && chmod 700 .'

echo "2/3 絵の置き場に控えを戻す"
dc up -d --wait seaweedfs
dc run --rm -T rclone mkdir "images:$BUCKET"
dc run --rm -T rclone copy "/backup/$NAME/images" "images:$BUCKET"
dc run --rm -T rclone check "/backup/$NAME/images" "images:$BUCKET" --one-way --download

echo "3/3 全部を立てる（移行・Temporal の表・名前空間・バケットは、あれば何もしない）"
dc up -d --no-build --wait
echo "戻した。deploy/check_production_stack.py の verify と fingerprint で確かめる"
