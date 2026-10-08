#!/usr/bin/env bash
# 控えを取る（V3サーバーの土台 1.4.4）。動かしたままでよい。
#   deploy/backup.sh <env ファイル> <compose の project 名>
# 出力: <V3_BACKUP_HOST_DIR>/<UTC の時刻>/
#   postgres/base.tar.gz・pg_wal.tar.gz・backup_manifest  PostgreSQL のサーバー全部（v3・openfga・keycloak・temporal・temporal_visibility）
#   images/<先頭2文字>/<sha256>                           絵の置き場（SeaweedFS のバケット）の全部
#   manifest.txt                                          取った時刻・版・数
#
# 揃え方
# - データベースは pg_basebackup で、サーバー全部を同じ時点で取る（データベースごとに pg_dump すると時点がずれ、
#   作品（v3）と役（openfga）が食い違うことがある）。
# - 絵は DB の後に取る。絵は中身の sha256 が名前で、置いた物は書き換えず、消す仕組みも無い（V3サーバーの土台 3.3）。
#   だから DB の控えが指す絵は、後から取った絵の控えに必ず入っている。絵を消す仕組みを足すときは、この順を崩さないように
#   「控えの保持期間より古い物だけ消す」にする。
# - 書き出したファイル（exports の volume）は取らない。書き出しを流し直せば作れる。
# - .env.prod（パスワードと鍵）は控えに入れない。別の安全な所に置く。戻すときに同じ値が要る。
set -euo pipefail

ENV_FILE=$1
PROJECT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
envval() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2-; }
dc() { docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$HERE/../compose.prod.yaml" "$@"; }

PG_USER=$(envval POSTGRES_USER)
BUCKET=$(envval V3_S3_BUCKET)
BACKUP_DIR=$(envval V3_BACKUP_HOST_DIR)
NAME=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$BACKUP_DIR/$NAME"
mkdir -p "$OUT"

echo "1/3 PostgreSQL（pg_basebackup）"
dc exec -T postgres rm -rf /tmp/v3-backup
dc exec -T postgres pg_basebackup -U "$PG_USER" -D /tmp/v3-backup -Ft -z -X stream -c fast --manifest-checksums=SHA256
dc cp postgres:/tmp/v3-backup "$OUT/postgres"
dc exec -T postgres rm -rf /tmp/v3-backup

echo "2/3 絵の置き場（rclone）"
dc run --rm -T rclone copy "images:$BUCKET" "/backup/$NAME/images"

echo "3/3 記録"
{
  echo "taken_at_utc=$NAME"
  echo "project=$PROJECT"
  echo "postgres=$(dc exec -T postgres postgres --version)"
  echo "alembic=$(dc exec -T postgres psql -U "$PG_USER" -d v3 -Atc 'select version_num from alembic_version')"
  echo "images=$(find "$OUT/images" -type f | wc -l)"
  (cd "$OUT/postgres" && sha256sum ./*)
} > "$OUT/manifest.txt"
echo "$OUT"
