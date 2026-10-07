#!/bin/sh
# MagiV2（GPU）。ComfyUIの試作が全部終わってから流す
cd "$(dirname "$0")"
while [ ! -f p08_rough/out_b/gen.json ]; do sleep 20; done
M="C:/Users/sanka/AppData/Local/Temp/claude/C--01-work-00-Git-manga-editor-desu/84025cf5-0085-4a9b-b194-d841a5ced85c/scratchpad/venv_magi/Scripts/python.exe"
mkdir -p p06_magi/out
echo "== magi $(date +%T)"
"$M" common/magi.py p06_magi/out/magi.json p06_magi/synth/rect.png p06_magi/synth/diag_row.png p06_magi/synth/diag_many.png p06_magi/synth/overlap_bleed.png \
  p02_instruction/out/two_people_*.png p02_instruction/out/three_people_*.png p10_page/out/*panels_*.png \
  /c/01_work/00_Git/kaguya-m2m/testdata/naname /c/01_work/00_Git/kaguya-m2m/testdata/視線誘導 > p06_magi/out/run.log 2>&1
echo "exit $? $(date +%T)"
