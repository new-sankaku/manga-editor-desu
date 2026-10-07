#!/bin/sh
cd "$(dirname "$0")"
while [ ! -f p10_page/out/gen.json ]; do sleep 20; done
echo "== p08b $(date +%T)"; (cd p08_rough && mkdir -p out_b && python run_b.py > out_b/run.log 2>&1); echo "exit $? $(date +%T)"
