#!/bin/sh
# 名前空間 default を作る（あれば何もしない）。アプリと作業者は default を使う。
set -eu
if temporal operator namespace describe --namespace default >/dev/null 2>&1; then
  echo "名前空間 default はある"
else
  temporal operator namespace create --namespace default --retention "$V3_TEMPORAL_RETENTION"
fi
