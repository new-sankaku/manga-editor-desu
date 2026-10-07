#!/bin/sh
# p20〜p26 の画像を順に作る（ComfyUIは1件ずつ処理するので並べない）
cd "$(dirname "$0")"
for p in p20_layers p21_hands p22_balloon p23_two_chara p24_deform p25_style_light p26_edit; do
  echo "== $p"; python $p/run.py || echo "!! $p failed"
done
echo "== all done"
