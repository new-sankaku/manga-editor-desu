#!/bin/sh
# 画像生成の試作を順に流す（ComfyUIは1件ずつ処理するため、並べずに順番に）
cd "$(dirname "$0")"
while [ ! -f p02_instruction/out/gen.json ]; do sleep 20; done
for p in p03_determinism p05_protect p08_rough p09_identity p07_color; do
  mkdir -p $p/out
  echo "== $p $(date +%T)"; (cd $p && python run.py > out/run.log 2>&1); echo "exit $? $(date +%T)"
done
