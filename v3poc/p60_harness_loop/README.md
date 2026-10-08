# P60 ハーネスの作業の流れ（進行役）と、その画面

生成→検査→作り直し→評価→確認待ちを、Temporal のワークフローで動かす試作です。結果は `llm_doc/V3検証の結果.md` の P60 の節と `out/result.json` にあります。

## 中身
| ファイル | 役目 |
|---|---|
| `harness_workflows.py` | 進行役。`StageWorkflow`（工程 S0〜S7、S4 でコマごとに子ワークフロー）と `WorkUnitWorkflow`（1回の作業） |
| `harness_activities.py` | 活動。文脈を組む・候補1枚の生成・検査・評価役・版の確定・取り消しの後片付け・ネームとページの検査 |
| `regen_rules.py` | 検査の結果から次の回の語句を決める（(a) の「検査の結果を使う作り直し」） |
| `comfy_client.py` | ComfyUI への送信。依頼の番号を呼ぶ側で決め、同じ番号があれば送らない。取り消しは `/queue` の削除と `/interrupt` |
| `p60_page.py` | 1ページ3コマのネームを v3/server の形で組み、v3/server の `name_checks` を掛ける。ページの絵を組む |
| `worker.py` | 作業者（別のプロセス。試験で落とす） |
| `api_server.py` | 画面の口（FastAPI）。Temporal の query・describe と ComfyUI の websocket から状態を返し、操作を signal・update・cancel で送る |
| `screen/index.html` | 画面。Cytoscape.js 3.30.2＋cytoscape-dagre 2.5.0（dagre 0.8.5） |
| `shoot.mjs` | Playwright で画面を開いて撮る・ボタンを押す |
| `mock_comfy.py` | 【モック】口だけ ComfyUI と同じ物。b〜s はこれで流した（CPU の ComfyUI が1枚1〜10分で流しきれないため）。絵は (a) で本物が作った絵から seed と文で選ぶ。絵の良し悪しに関わる数は未検証 |
| `infra.py` | Temporal（docker の `p60-temporal`、口 64260）・ComfyUI（63260）・検出器（63261）の起動と停止 |
| `run.py`・`scenarios.py` | 測定の場面 a・b・c・d・i・s・e と、まとめ（collect） |

## 動かし方
前提：ComfyUI（CPU、SD1.5 を分けた3つ）と、その venv。`COMFY_DIR` で場所を指す（p56 と同じ）。検出器は `v3/detector_server` の `.venv` を使う。Claude の CLI。

```
# 1. 試作の Python（v3/server の venv のパッケージを読むだけで借り、websockets だけ足す）
S=<作業用フォルダ>/p60            # 既定は harness_config.py の SCRATCH。P60_SCRATCH で変える
uv venv -p v3/server/.venv/bin/python $S/venv_api
echo "import site; site.addsitedir('<リポジトリ>/v3/server/.venv/lib/python3.13/site-packages')" > $S/venv_api/lib/python3.13/site-packages/v3server_venv.pth
uv pip install -p $S/venv_api/bin/python websockets==15.0.1
mkdir -p $S/../empty_llm          # Claude の CLI を呼ぶ空のフォルダ（P60_LLM_DIR）

# 2. Temporal・ComfyUI・検出器を立てる（v3 の compose の Temporal は使わない）
cd v3poc/p60_harness_loop
$S/venv_api/bin/python infra.py start --fresh

# 3. 画面の CDN の写し（Playwright の Chromium は中継の証明書を持たないので、同じ版を curl で取って差し替える）
mkdir -p $S/cdn && cd $S/cdn && curl -sO https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js \
  && curl -sO https://cdn.jsdelivr.net/npm/dagre@0.8.5/dist/dagre.min.js \
  && curl -sO https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.js && cd -

# 4. 測る（作業者と画面の口は run.py が立てる）。場面は順に流す。ComfyUI は1件ずつなので並べても速くならない
$S/venv_api/bin/python run.py a          # 検査の結果を使う作り直し と seed だけの作り直し（本物の ComfyUI）
# b〜s はモックの ComfyUI で流した：本物を止めてからモックを立て、作業者を立て直す
$S/venv_api/bin/python -c "import infra; infra._kill('comfy'); infra.kill_worker()"
P60_COMFY_MOCK=1 P60_MOCK_STEP_SEC=3 $S/venv_api/bin/python -c "import infra; infra.start_comfy(); infra.start_worker()"
P60_COMFY_MOCK=1 $S/venv_api/bin/python run.py b c d i s e collect

# 5. 画面だけ見る：ブラウザで http://127.0.0.1:63262/?stage=<工程のID>（作業だけなら ?unit=<IDの頭>）

# 6. 止める（作業者・画面の口・検出器・ComfyUI・Temporal）
$S/venv_api/bin/python infra.py stop
```

- `out/part_<場面>.json`：場面ごとの記録。`out/result.json`：まとめ。`out/*.png`：画面の絵。`out/run.log`：流した記録。
- 数えるための記録（作業用フォルダ）：`prompt_posts.jsonl`（/prompt に送った回）、`registrations.jsonl`（置き場への登録・取り下げ・版）、`claude_calls.jsonl`（Claude の CLI の呼び出しと費用）。
- 絵の置き場は作業用フォルダの `store/`（リポジトリに入れない）。
