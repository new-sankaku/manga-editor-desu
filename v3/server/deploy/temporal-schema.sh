#!/bin/sh
# Temporal の表を作る・上げる（temporalio/admin-tools の temporal-sql-tool）。何度流してもよい。
# データベースは postgres-init-prod.sql で作ってある。パスワードは環境変数 SQL_PASSWORD。
set -eu
SCHEMA=/etc/temporal/schema/postgresql/v12
for db in temporal temporal_visibility; do
  if [ "$db" = temporal ]; then dir=$SCHEMA/temporal/versioned; else dir=$SCHEMA/visibility/versioned; fi
  tool="temporal-sql-tool --plugin postgres12 --ep postgres -p 5432 -u $POSTGRES_USER --db $db"
  # 版の表（schema_version）が無いときだけ作る
  if ! $tool update-schema -d "$dir"; then
    $tool setup-schema -v 0.0
    $tool update-schema -d "$dir"
  fi
done
echo "Temporal の表は最新"
