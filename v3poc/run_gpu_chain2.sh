#!/bin/sh
cd "$(dirname "$0")"
while [ ! -f p07_color/out/result.json ]; do sleep 20; done
for p in p04_size p10_page; do
  mkdir -p $p/out
  echo "== $p $(date +%T)"; (cd $p && python run.py > out/run.log 2>&1); echo "exit $? $(date +%T)"
done
