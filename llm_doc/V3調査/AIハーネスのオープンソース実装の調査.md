# AIハーネスのオープンソース実装の調査（調査日 2026-10-08）

V3 の「1作業（例：1コマの作画）＝生成→検査→作り直し→評価→人の判断待ち」と、その上の工程の進行（企画→構成→設定資料→ネーム→作画→仕上げ→総合→書き出し）に、既製のハーネスから何を持ち込むかを調べた。

取得方法の注意
- 版・公開日・ライセンスは PyPI と npm の登録情報、GitHub のリポジトリ情報（スター数は 2026-10-08 時点）、リポジトリの LICENSE ファイルで確かめた。
- 仕組みの説明は公式文書を WebFetch で読んだ（小型モデルが抜き出して返す方式。原文との一字一句の照合はしていない）。一部はソースを直接読んだ（「ソース確認」と書いたもの）。Temporal の Python SDK は `v3/server/.venv` に入っている 1.34.0 のソースを読んだ。
- 文書にもソースにも当たれなかったことは「未検証」と書く。どれもこの環境で動かしてはいない。

---

## 1. 結論

- **土台は Temporal のまま。他の実行基盤（LangGraph の実行・DBOS・Restate・Hatchet・Inngest・Prefect・Dagster）は入れない。** どれも「途中から再開できる実行」を自前で持っており、Temporal と二重になる。Temporal 側の LangGraph 連携ですら「耐久性は Temporal が持つので、LangGraph の保存先はメモリのものを使え」と書いている（ソース確認）。
- **持ち込むのは型（パターン）。** 主なものは次の6つ。
  1. 1作業を1ワークフロー、工程を親ワークフローにする（Temporal のサンプル・OpenAI Agents SDK 連携と同じ形）。AI の呼び出しは1回ずつアクティビティにする。
  2. 人の判断は Update で受ける（受け付けたかどうかを呼び出し側にすぐ返せる。検証で弾いた判断は履歴に残らない）。上流の変更の通知は Signal で送る。
  3. 「品質の作り直し」の回数は、通信の失敗の再試行（RetryPolicy）とは別に、ワークフローの変数で数える。
  4. 取り消しは協調式（次の区切りで止まる）と割り切り、画面に「取り消し中」を出す（Prefect の CANCELLING、Inngest・DBOS・OpenHands とも、走っている1段は止めずに次の区切りで止める）。
  5. 「古い」は実行の状態ではなく結果に付く印にする。上流の版の組を結果ごとに記録し、比べて決める（Dagster の Unsynced と同じ考え方）。
  6. 進み具合（ComfyUI の段数・途中画像）は Temporal の履歴に流さず、PostgreSQL と SSE などの別の道で画面に送る。
- **ライブラリとして足すもの**は、画面のグラフ描画だけ。**Cytoscape.js（MIT）＋ cytoscape-dagre（MIT）** を勧める。入れ子のレイアウトが要るときだけ elkjs（EPL-2.0）を足す。ただし、進み具合の主な画面はグラフでなく、ページとコマの一覧（表）に状態の色を付ける方が読みやすい（推測）。グラフは「どこが古くなったか」「何が何を止めているか」を見せる所に絞る。
- Temporal の新しい機能のうち、ワークフローの一時停止（Workflow Pause）は「pre-release」でサーバー 1.30 以上と設定が要る。今の V3 のように Signal と `wait_condition` で自前の一時停止を持つ方がよい。

---

## 2. V3 が今持っているもの（`v3/server/` を読んだ）

- `generation_queue/generation_workflow.py`：呼び出し1件を1ワークフローにしている。`resume` の Signal と `wait_condition` で止めて再開、アクティビティは `heartbeat_timeout=30秒`、上限・予算に当たると `waiting_limit` / `waiting_budget` にする。
- `service_call_activity.py`：呼び出し中は別タスクでハートビートを送り続けている。
- `queue_names_and_priority.py`：Temporal の `Priority` を使っている。Python SDK 1.34 の `Priority` には `priority_key`（1〜5、小さいほど先）と `fairness_key`（64バイトまで）・`fairness_weight` がある（ソース確認）。作品ごとの公平さは `fairness_key` で表せる。ただし、自前で立てるサーバーでは設定（`matching.enableFairness` など）が要り、文書によって「Public Preview」と「GA」の記載が食い違う。
- 状態の名前（ソースに出てくるもの）：`queued` `running` `waiting_limit` `waiting_budget` `stopped` `cancelled` `done` `failed`。
- compose の Temporal は `temporalio/temporal:1.9.1`（CLI の開発用サーバー）。中のサーバーの版は未検証。

---

## 3. 候補ごとの調査

### 3.1 LangGraph（MIT、1.2.14・2026-10-06、スター 42.9k）
- **ループと状態**：状態（型付きの辞書）を持つグラフ。ノードは「スーパーステップ」単位でまとめて動き、その境目ごとにチェックポイントを残す。再開できるのはこの境目からだけ。
- **保存先**：チェックポインター。メモリ・SQLite・PostgreSQL（`langgraph-checkpoint-postgres` 3.1.2）・MongoDB など。1ステップの中で成功したノードの書き込みも残すので、別のノードが失敗しても成功分はやり直さない。
- **保存の強さ**：`durability` を実行ごとに選ぶ。`exit`（終わったときだけ保存。途中で落ちると戻せない）、`async`（裏で保存。落ちると最新の分を失うことがある）、`sync`（次のステップの前に必ず保存）。
- **人の判断**：ノードの中で `interrupt(値)` を呼ぶと止まり、`Command(resume=値)` で同じ `thread_id` を渡して再開する。**再開するとノードは頭から動き直す**ので、`interrupt` より前の副作用は2回走る。1つのノードに複数の `interrupt` を置くと、順番で対応づけるので、条件で飛ばすと崩れる。検証の繰り返しを `while` と `interrupt` で書くと、再開のたびに前の回を全部やり直す（文書の注意）。
- **取り消し**：ライブラリ単体には走行中の取り消しの口は無い。サーバー（Agent Server）側に `interrupt`（止めてチェックポイントを残す）と `rollback`（走行とチェックポイントを消す）がある。
- **時間をさかのぼる**：`get_state_history` で過去の状態を並べ、`update_state` で書き換えた新しいチェックポイントを作り、そこから分岐できる。分岐後のノードは LLM の呼び出しも含めて再実行される。
- **画面への送り方**：`stream_mode` に `values`（毎回の全状態）`updates`（差分）`messages`（トークン）`custom`（ノードが書いた任意の値）`checkpoints` `tasks`（開始・終了・失敗）`debug`。入れ子のグラフは `subgraphs=True`。
- **見せ方**：グラフは Mermaid の文として出せる。LangGraph Studio はグラフ・通ったノード・途中の状態・時間をさかのぼるを見せるが、LangSmith に結び付いている。サーバー（`langgraph-api`、0.15.3）は **Elastic License 2.0** で、MIT ではない。
- **Temporal との組み合わせ**：`temporalio.contrib.langgraph`（Python SDK 1.34 に同梱、**experimental**）。ノードをアクティビティとして動かす。「耐久性は Temporal が持つので PostgreSQL などのチェックポインターは要らない。`interrupt` を使うならメモリのものを使え」。ストリームは `custom` のモードだけ、少なくとも1回の配信（再試行で重複する）、Store は使えない（ソース確認）。

### 3.2 Temporal（サーバー MIT・v1.32.0・2026-09、スター 23.5k／Python SDK MIT・1.34.0・2026-09-30）
- **ループと状態**：ワークフローのコードそのものが状態。外の世界に触る処理（LLM・ComfyUI・DB）はアクティビティにする。履歴（イベントの列）を再生して状態を作り直すので、ワークフローのコードは決定的でなければならない。
- **保証**：完了したアクティビティの結果は履歴に残り、再生では呼び直さない。アクティビティ自体は少なくとも1回（途中で落ちれば再試行）。アクティビティの既定の再試行は「無制限・指数で間隔を延ばす」。`maximum_attempts` は「まれ。普通はタイムアウトで縛れ」と文書にある。`non_retryable` の `ApplicationError` は再試行しない。ワークフローは既定で再試行しない。
- **人の判断（メッセージ）**：
  - Query：読むだけ。履歴に残らない。終わったワークフローにも（保持期間内なら）聞ける。
  - Signal：送りっぱなし。値を返せない。履歴に残る。
  - Update：受け付けたか弾いたかを待てて、値も返せる。検証関数（同期・読むだけ）で弾くと、受け付けのイベントは履歴に残らない。受け付けた Update は耐久的で、修正を出した後でも結果を取れる。
  - `wait_condition(条件, timeout)` で止まって待つ。返り値の前やワークフローの切り替え前に `all_handlers_finished` を待つ（ソースに関数あり）。
  - Update-with-start：無ければ起動してから Update を処理する。V3 はすでに `WithStartWorkflowOperation` を使っている。
- **取り消し**：ワークフローの取り消しは「頼む」もので、コード側で後始末できる（`terminate` は即時で後始末なし）。アクティビティへの取り消しは**ハートビートを送ったときにしか届かない**。ハートビートを送らないアクティビティは取り消せない。アクティビティの取り消しの扱いは `TRY_CANCEL` / `WAIT_CANCELLATION_COMPLETED` / `ABANDON`（ソース確認）。子ワークフローにも `ChildWorkflowCancellationType` がある（ソース確認）。
- **タイムアウトとハートビート**：Schedule-To-Start（列で待つ長さ）、Start-To-Close（1回の実行の長さ）、Schedule-To-Close（再試行を含めた全体）、Heartbeat（ハートビートの間隔の上限）。ハートビートには進み具合を載せられ、再試行のときに続きから始められる。ハートビートの送信は間引かれる（タイムアウトの 80%、未設定なら 30秒、最大 60秒）。
- **止める・戻す**：
  - アクティビティの一時停止：再試行の予定を止める。Python SDK 1.34 のクライアントに `pause` / `unpause` がある（ソース確認）。解除すると回数とハートビートの中身は残る。止めている間も Schedule-To-Close は進む。
  - ワークフローの一時停止：**pre-release**。サーバー 1.30.0 以上で `frontend.WorkflowPauseEnabled`、CLI 1.6.0 以上、UI 2.47.2 以上。止めている間、Signal は記録されて後で処理、Update と Query は弾かれる、タイマーは進む、走っているアクティビティは止まらない。
  - Reset：今の実行を終わらせ、履歴の指定位置から新しい実行を始める。
- **長く続く実行**：履歴は 10,240 イベントで警告、51,200 イベントで強制終了。Update 2,000 件・Signal 10,000 件を超えても強制終了。`is_continue_as_new_suggested()` を見て Continue-As-New で切り替える（ハンドラーの中で切り替えない）。
- **画面への送り方**：Query で今の状態を取る、または Workflow Streams（`temporalio.contrib.workflow_streams`、**experimental**）。後者は Signal で書き込み、Update の長いポーリングで読み、SSE に橋渡しする。1往復およそ 100ms、ワークフローから書いた分は重複なし（ソース確認）。Signal を使うので、上の Signal の件数の上限に関わる（推測）。
- **AI 向けの連携**：
  - OpenAI Agents SDK 連携（`OpenAIAgentsPlugin`）：エージェントのループはワークフロー、モデルの呼び出しはアクティビティ。人の承認は `HostedMCPTool` の `require_approval` と Signal/Update で待つ。ストリーミングは experimental。
  - Python SDK 1.34 に同梱の連携：`openai_agents` `langgraph` `google_adk_agents` `strands` `deepagents` `langsmith` `workflow_streams` など（ソース確認）。
  - temporal-ai-agent（MIT、スター 781）：ワークフローが「LLM・人とのやり取り・道具の実行」の3つのループを回す。人とのやり取りは Signal と Query。LLM は LiteLLM 経由。長い会話は履歴が膨らむので、大きな中身は外に置いて ID だけ渡す方法（claim check）を勧めている。
- **見せ方**：Web UI（MIT、Svelte）にタイムライン表示がある。2023年の記事では vis-timeline で作ったとあるが、今の `package.json` の依存には vis-timeline も他のグラフ用ライブラリも無い（作り替えたと思われる。中身は未検証）。運用者向けの画面で、作家向けの画面には向かない。

### 3.3 DBOS Transact（MIT、3.2.0・2026-09-29、スター 1.6k）
- PostgreSQL（または SQLite）に手順ごとの結果を残す、ライブラリだけのやり方。手順は「少なくとも1回、完了後は再実行しない」。DB のトランザクションだけが「ちょうど1回」。
- 取り消しは次の手順の頭で効く（走っている手順は終わるまで待つ。`preemptible` の印を付けた非同期の手順だけ即時）。`resume_workflow` は最後に完了した手順から、`fork_workflow` は指定の手順から新しい ID で走らせ直す。
- 人の判断は `send`/`recv`（ワークフローからの送信はちょうど1回、外からは冪等キーで）と `set_event`/`get_event`。画面へは `write_stream`（ワークフローからはちょうど1回、手順からは少なくとも1回）。
- 管理画面（Conductor / Console）は**独自ライセンス**で、本番や商用で自分で立てるにはライセンスキーが要る。

### 3.4 Restate（サーバーは BSL 1.1、v1.7.13・2026-10-01、スター 4.5k／Python SDK 1.0.5）
- サーバーが手順の記録（ジャーナル）を持ち、ハンドラーは HTTP で呼ばれる。
- 人の判断：Awakeable（ID を外に渡し、外から HTTP で解決か拒否。拒否すると待っている側に終わりのエラー）、ワークフローの Promise、名前付きの Signal。
- 取り消しは呼び出しの木の葉から順に、次の `await` で終わりのエラーとして届き、親が補償処理（saga）を書く。`kill` は補償処理なしで即時。再試行が多すぎると一時停止になり、人が再開する。
- BSL の追加の許可：自社のサービスを動かす本番利用は許されている。他社に Restate の API を開く有料サービスは不可。

### 3.5 Inngest と AgentKit（サーバーは SSPL＋将来 Apache-2.0、inngest 4.22.0／AgentKit Apache-2.0、0.13.2・2025-11-13、スター 940）
- 関数の中の `step.run` ごとに結果を残す。人の判断は `step.waitForEvent`（期限つき、イベントの中身で対象を照合）。
- 取り消しは期限・`cancelOn` のイベント・一括取り消し。**走っている手順は最後まで走り、後ろの手順を止める**。済んだ外の副作用は戻らない。
- 画面へは Realtime（チャンネルとトピック、React のフック）。Python の送信は beta。
- AgentKit は TypeScript のみで、最終公開が 2025-11 と止まり気味。

### 3.6 Hatchet（MIT、SDK 1.41.1・2026-09-24、スター 8.1k）
- 耐久タスクは完了した部分を記録に残し、落ちても続きから。待つ（時間・イベント、どちらか早い方）か、子タスクを作る。人の承認の部分は再生しない。
- 取り消しは協調式（Python は `ctx.exit_flag` など、タスクが自分で見て止まる）。一時停止は「新しい実行を始めない」だけで、走っているものは止めない。
- 画面へは `put_stream` と購読。**購読の前に送られたものは捨てられる**。

### 3.7 Prefect（Apache-2.0、3.8.8・2026-10-06、スター 24k）と ControlFlow・Marvin
- 状態：`SCHEDULED` `PENDING` `RUNNING` `COMPLETED` `FAILED` `CANCELLED` `CRASHED` `PAUSED` `CANCELLING`（ソース確認）。**コードの失敗（FAILED）と実行環境が落ちた（CRASHED）を分け、取り消しを頼んだがまだ止まっていない（CANCELLING）を持つ**のが参考になる。
- 人の判断：`pause_flow_run` / `suspend_flow_run` に `wait_for_input`（Pydantic の型）を渡すと、Prefect の画面に入力欄が出る。suspend は実行環境を片付けて抜ける。
- ControlFlow は**アーカイブ済み**（Marvin に統合）。Marvin 3.2.7（2026-03）。

### 3.8 Dagster（Apache-2.0、1.13.25・2026-10-01、スター 16k）
- データの「アセット」の実行基盤。参考になるのは**古さの判定**：コードの版（`code_version`）と入力のデータの版から自分のデータの版を作り、最後に作ったときと比べて「Unsynced」の印と理由（例：上流のデータの版が変わった）を出す。印は下流へ自動では伝わらず、各アセットが自分の使った上流の版と比べて決める。作り直しは人が「Materialize unsynced」を押す。

### 3.9 Microsoft AutoGen と Agent Framework
- AutoGen（MIT、0.7.5・2025-09-30、スター 61k）：README に**メンテナンスモード**と明記。新規は Agent Framework へ。
- Agent Framework（MIT、1.20.0・2026-10-02、スター 14k）：スーパーステップ（Pregel 型）で、各ステップの終わりにチェックポイント。保存先はメモリ・ファイル・Azure Cosmos DB の3つで、PostgreSQL は無い。ファイルと Cosmos は pickle を使う（制限つきの読み込み）。図は Graphviz と Mermaid に出せる（ソース確認）。

### 3.10 CrewAI Flows（MIT、1.15.25・2026-10-07、スター 59k）
- `@start` `@listen` `@router` でつなぐ。`@persist` の既定の保存先は SQLite。同じ ID で続きから、別の ID で分岐。`@human_feedback` で人の入力を待ち、LLM が入力を分岐先に振り分ける。
- `flow.plot()` は HTML を出し、中身は **vis-network**（ソース確認）。

### 3.11 Mastra（Apache-2.0、`ee/` 以下だけ別ライセンス、@mastra/core 1.75.0・2026-10-07、スター 28.6k）
- TypeScript。手順の中で `suspend()`、外から `resume()`。入力の型（`resumeSchema`）と止めたときに残す型（`suspendSchema`）を持つ。状態は `running` `waiting` `suspended` `success` `failed` `paused` など。サーバー起動時に走っていた実行を自動で再開する。
- Studio のグラフは各手順の状態をその場で更新する。描画は React Flow（`@xyflow/react`）を使う（package.json で確認）。

### 3.12 PydanticAI と pydantic-graph（MIT、2.54.0・2026-10-03、スター 20.5k）
- pydantic-graph：ノードの戻り値の型が辺になるグラフ。`graph.iter()` で1段ずつ回せる。図は Mermaid の `stateDiagram-v2`。文書自身が「ほとんどのエージェントは普通の Python で足りる」と書いている。
- 耐久化は Temporal・DBOS・Prefect・Restate に任せる連携がある（Temporal は `TemporalDurability` などの名前。人の承認の細部は未検証）。V3 の設計（3.1章）は作業役の候補に PydanticAI を挙げているので、使うならこの Temporal 連携を通す。

### 3.13 OpenHands（MIT、本体 1.11.0／SDK 1.53.0・2026-10-05、スター 90k）
- 会話の状態（ソース確認）：`idle` `running` `paused` `waiting_for_confirmation` `finished` `error` `stuck` `deleting`。状態と出来事の列はファイルに保存し、続きから開ける。
- `pause()` は次の1周の区切りで効き、**LLM の呼び出し中なら終わるまで効かない**。`interrupt()` は非同期の実行なら LLM の呼び出し中でも止め、`paused` にする。`reject_pending_actions(理由)` で人が理由を付けて却下できる。
- 1回の実行の上限（既定 500 周）と、行き詰まりの検出（同じ操作と結果の繰り返し、同じエラーの繰り返し、独り言の繰り返し、2つの操作の交互）を持つ（ソース確認）。

### 3.14 SWE-agent と mini-swe-agent（MIT、スター 20.5k）
- 本体の開発は mini-swe-agent（2.4.6・2026-07-23）に移った。ループは「問い合わせ→操作→結果」を履歴に足すだけで、`step_limit` と `cost_limit`（既定 3.0 ドル）を超えると `LimitsExceeded` で止める。軌跡はファイルに保存する（ソース確認）。

### 3.15 Claude Agent SDK（MIT、Python 0.2.164・2026-10-06、Alpha、スター 8.2k）
- ループ：考える→道具を呼ぶ→結果を返す、を道具の呼び出しが無くなるまで続ける。`max_turns` と `max_budget_usd`。結果の種類は `success` `error_max_turns` `error_max_budget_usd` `error_during_execution` など。セッションは ID で再開・分岐でき、保存先を差し替える口もある。
- フック：`PreToolUse` で `allow` / `deny` / `ask` / `defer`、入力の書き換え。`defer` は「後で再開する」として一回りを終える。複数のフックでは `deny` が勝つ。フックには時間の上限がある（多くは 600秒）。Python では使えないフックがある（`SessionStart` など）。
- V3 では「定額の CLI を非対話で動かす」作業役（設計 3.1章）がこれにあたる。Temporal のアクティビティの中で1回分として動かし、上限は SDK とワークフローの両方で持つ形になる（推測）。

### 3.16 ComfyUI（GPL-3.0、スター 136k）
- 待ち行列はプロセスのメモリにあり（`PromptQueue`、履歴は最大 10,000 件）、**再起動すると消える**（ソース確認）。
- `POST /interrupt`：`prompt_id` を付けると、それが今走っているときだけ止める。付けないと全体を止める。止めるのは協調式で、サンプラーの1段ごとの進み具合の呼び出しの中で確かめている。`POST /queue` で待ち行列から消す・全部消す（ソース確認）。
- WebSocket の通知：`status` `execution_start` `execution_cached` `executing` `progress`（値と最大）`progress_state`（ノードごとに `pending` `running` `finished` `error`）`executed` `execution_success` `execution_error` `execution_interrupted`。途中画像はバイナリで、メタデータ付きの形もある（ソース確認）。
- 公式の画面（ComfyUI_frontend、GPL-3.0、Vue と PrimeVue と Pinia）は、これらを受けてノードごとの進み具合を持つ（ソース確認）。描き方の細部は未検証。

### 3.17 画像生成に向けたハーネス
- 「生成→検査→作り直し→評価→人の判断」を1つにまとめた画像生成用のオープンソースのハーネスは、見つからなかった（探し方は検索と GitHub の検索。見落としはありうる）。
- 近いもの：InvokeAI（Apache-2.0、6.14.2・2026-09-27、スター 28k）
  - 待ち行列は SQLite。状態は `pending` `in_progress` `waiting` `completed` `failed` `canceled`。優先度、作り直しの元の番号（`retried_from_item_id`）を持つ（ソース確認）。
  - **起動時に `in_progress` と `waiting` をすべて `canceled` にする**（ソース確認）。続きからは再開しない。
  - キャンバスの「ステージングエリア」で候補を前後に送り、採用・選んだものを捨てる・全部捨てる・ギャラリーへ保存（ソース確認）。V3 の候補選びの画面の参考になる。
- SwarmUI（スター 4.6k）は複数の ComfyUI をつなぎ先として束ねる。仕組みは未検証。

---

## 4. 基本機能ごとの比較

| 機能 | Temporal（V3 の土台） | LangGraph | DBOS | 他で参考になる所 |
|---|---|---|---|---|
| 内側の繰り返し | ワークフローの普通のループ。回数は変数 | 条件つきの辺で戻る | 普通のループ | OpenHands の行き詰まり検出 |
| 人や上流からの割り込み | Signal / Update | `interrupt()` | `send` / `recv` | Restate の Awakeable |
| 取り消し（1段・1作業・工程） | ワークフロー・アクティビティ・子ワークフローごと。アクティビティはハートビートが要る | サーバーの `interrupt` / `rollback` | 次の手順の頭で効く | Inngest・Hatchet も協調式 |
| 落ちた後の再開 | 履歴の再生で自動 | `sync` なら最後のステップから | 最後に完了した手順から | InvokeAI は再開しない |
| タイムアウトとハートビート | 4種のタイムアウトとハートビート | なし（呼び出し側の仕事） | ワークフローの期限 | Claude Agent SDK のフックの期限 |
| 予算と回数の上限 | 自前（変数）。再試行は RetryPolicy | 自前 | 自前 | Claude Agent SDK・mini-swe-agent は組み込み |
| 走行中の上限の変更 | Update（検証つき）で変数を変える | `update_state` | 未検証 | なし |
| 承認・理由つきの却下・人の直し | Update の引数で表す | `Command(resume=...)` | イベント | OpenHands の `reject_pending_actions(理由)`、Prefect の入力欄 |
| 古さの印 | なし（自前） | なし | なし | Dagster の Unsynced |
| 時間をさかのぼる・分岐 | Reset（履歴の位置から） | チェックポイントから分岐 | `fork_workflow` | CrewAI の `restore_from_state_id` |

---

## 5. V3 への勧め

### 5.1 型として持ち込むもの
1. **ワークフローの切り方**：工程を親ワークフロー、1作業を子ワークフロー、AI と ComfyUI の呼び出し1回をアクティビティにする。工程を取り消すと子に取り消しが伝わる。子の取り消しの扱い（`ChildWorkflowCancellationType`）と親が終わったときの扱い（`ParentClosePolicy`）は試験で確かめる（未検証）。
2. **作業の中の繰り返し**：生成→検査→作り直しの回数、評価、予算の使った分はワークフローの変数に持つ。RetryPolicy は通信の失敗だけに使い、品質の作り直しに使わない（再試行は「同じ入力で同じ呼び出し」のため）。同じ失敗が続いたら文脈を捨てて出直す・止める（設計 10章）は、OpenHands の行き詰まり検出と同じ形で書ける。
3. **人の判断は Update**：「採用」「却下（理由）」「人が直した版を登録」「上限を変える」を Update にし、検証関数で「もう決まっている」「上限が使った分より小さい」などを弾く。弾いた操作は履歴に残らず、画面にすぐ理由を返せる。
4. **上流の変更は Signal**：作業のワークフローに「上流が変わった」を送る。走っている試行を取り消して始め直すか、終わらせて「古い」を付けるかは作業の種類で決める（設計 13章「指示の変更」は取り消して始め直す）。
5. **待ちには期限**：判断待ちは `wait_condition(条件, timeout)` で待ち、期限が来たら知らせる（締切の扱いは `V3細部の決めごと.md`）。
6. **取り消しは協調式で、画面に「取り消し中」を出す**：ComfyUI のアクティビティは取り消しを受けたら `POST /interrupt`（`prompt_id` 付き）と、待ち行列にあれば `POST /queue` の `delete` を送る。止まるのは次のサンプラーの1段なので、すぐには止まらない。ハートビートが届くまでの間も「取り消し中」と見せる。
7. **古さは結果の印**：結果（版）ごとに「使った上流の版の組」と「プロンプト・モデル・設定の版」を記録し、上流が変わったら比べて「古い」を付ける。下流へ順に伝えるのでなく、各結果が自分の入力と比べる（Dagster と同じ）。人の確定印のある結果は古くなっても上書きしない（決めごと 5.4）。
8. **進み具合は Temporal の外で送る**：ComfyUI の段数・途中画像・LLM のトークンは、アクティビティから PostgreSQL（または通知の仕組み）に書き、SSE で画面へ送る。状態の切り替わり（順番待ち→実行中→判断待ち…）は、今のようにアクティビティで DB に書く。Workflow Streams は experimental で、Signal の件数の上限に関わるので使わない。
9. **画像は ID で渡す**：アクティビティの入出力とワークフローの状態には画像の置き場所の ID だけを載せる（temporal-ai-agent の勧めと同じ）。Temporal の1件の中身の大きさの上限は未検証。
10. **長い工程は切り替える**：工程の親ワークフローで `is_continue_as_new_suggested()` を見て Continue-As-New する。1作業のワークフローは短く保つ。
11. **やり直し・分岐は DB の版で**：「この版から別案」は Temporal の Reset でなく、正本の版を元に新しい作業を始める形にする。Reset はその後の進み具合を捨てるので、作品のデータの戻しには向かない。
12. **候補選びの画面**：InvokeAI のステージングエリアの形（前後に送る・採用・選んだものを捨てる・全部捨てる）を判断待ちの画面に使う。

### 5.2 ライブラリとして持ち込むもの
- **Temporal Python SDK（使用中）**。足すのは同梱の連携だけ。作業役に OpenAI Agents SDK か PydanticAI を使うなら、その Temporal 連携（OpenAI Agents SDK の連携はストリーミングが experimental）を使う。
- **Cytoscape.js ＋ cytoscape-dagre**（画面、7章）。
- 作業の中の時間の流れ（試行ごとの開始・終了）を横棒で見せたいなら vis-timeline（Apache-2.0 か MIT、8.5.4）が候補。要るかは画面の試作で決める（未検証）。

### 5.3 持ち込まないもの
| 対象 | 理由 |
|---|---|
| LangGraph を進行役にする | Temporal と再開の仕組みが二重になる。`interrupt` で再開するとノードが頭から走る。サーバーは Elastic License 2.0、Studio は LangSmith に結び付く。Temporal の連携は experimental |
| DBOS・Restate・Hatchet・Inngest・Prefect・Dagster | Temporal と同じ役目。Restate は BSL、Inngest のサーバーは SSPL、DBOS の管理画面は独自ライセンス |
| AutoGen | メンテナンスモード |
| Agent Framework・CrewAI | 保存先に PostgreSQL が無い（Agent Framework）、既定が SQLite（CrewAI）。複数のエージェントの会話で進める作りで、V3 の「進行はプログラム、AI は作業の中身だけ」（設計 3章）と合わない |
| Mastra・Inngest AgentKit | TypeScript。サーバーは Python |
| Temporal のワークフローの一時停止 | pre-release。今の Signal での一時停止で足りる |
| ComfyUI の待ち行列を正本にする | メモリにあり、再起動で消える。Temporal の待ち行列を前に置く今の形を続ける |

---

## 6. 画面に出す状態の名前

実行の状態（1つだけ取る）と、結果に付く印（いくつでも付く）を分ける。英語の名前は今のサーバーにあるものを優先した。日本語は今の文書の言葉（判断待ち・止まったもの・古い）に合わせた。

**実行の状態**
| 名前（画面） | サーバーの値 | 意味 | 参考 |
|---|---|---|---|
| 順番待ち | `queued` | 送り先が空くのを待っている | 今のサーバー |
| 実行中 | `running` | 生成・検査・評価のどれか。「作画 3/5回目・検査中」のように段階と回数を添える | — |
| 上限で待機 | `waiting_limit` | 回数・同時実行の上限 | 今のサーバー |
| 予算で待機 | `waiting_budget` | 予算の上限 | 今のサーバー |
| 判断待ち | （新規）`awaiting_review` | 人の採用・却下を待つ | Mastra の suspended、OpenHands の waiting_for_confirmation |
| 一時停止 | （新規）`paused` | 人が止めた | OpenHands・Prefect |
| 取り消し中 | （新規）`cancelling` | 取り消しを頼んだが、まだ止まっていない | Prefect の CANCELLING |
| 再試行中 | （新規）`retrying` | 通信の失敗や worker の停止のあと、同じ呼び出しをやり直している。回数を添える | Temporal の UI の再試行の表示 |
| 止まった | `stopped` | 上限回数に達した・判定できない・拒否された。理由を添える | 今のサーバー、決めごと 4.5 |
| 失敗 | `failed` | 直さないと進めないエラー | 今のサーバー |
| 取り消し済み | `cancelled` | — | 今のサーバー |
| 完了 | `done` | 採用まで済んだ | 今のサーバー |

**結果に付く印**
| 名前（画面） | 意味 |
|---|---|
| 古い | 使った上流の版が今の版と違う。理由（どの上流が変わったか）を添える |
| 人が直した | 人の確定印がある。自動で上書きしない |
| 却下 | 人が却下した。理由を添える |
| 検査の失敗 | 赤の角丸（決めごと 5.1） |

- 「止まった」と「失敗」の分け方：Prefect は FAILED（コードの失敗）と CRASHED（実行環境が落ちた）を分ける。Temporal では worker が落ちても自動で再開するので、V3 では CRASHED にあたるものは「再試行中」になる（推測）。

---

## 7. グラフ描画ライブラリ（React を使わない、手元に置いて読み込む）

V3 の画面は React を使わず、ライブラリは `v3/web/vendor/` に置いて CDN を使わない（`V3画像生成の機能と画面.md`）。大きさは jsDelivr から1ファイルを取ったときのバイト数（圧縮前）。

| ライブラリ | ライセンス・版 | 描き方 | 大きさ | 入れ子 | 自動の配置 | 合うか |
|---|---|---|---|---|---|---|
| **Cytoscape.js** | MIT・3.34.3（2026-09） | canvas | 435KB（min） | あり（`parent`） | 組み込み（breadthfirst など）、拡張で dagre・ELK | ◎ 依存なし。セレクターとクラスで状態ごとの色を付けられる。`<script>` で読める |
| cytoscape-dagre | MIT・4.0.1（2026-08） | — | 46KB（min） | — | 上から下・左から右の層の配置 | ◎ Cytoscape.js の配置に足す |
| elkjs | **EPL-2.0** または GPL-3.0・0.12.0（2026-07） | なし（位置の計算だけ） | 1.6MB（bundled） | `hierarchyHandling: INCLUDE_CHILDREN` で入れ子ごと配置 | layered（ポート対応） | ○ 工程の中に作業を入れ子で並べるなら最も整う。重い。EPL は手を入れたファイルを公開する条件（ライセンス本文の読み込みは未検証）。cytoscape-elk（MIT・2.3.0）でつなげる |
| JointJS（@joint/core） | MPL-2.0・4.3.3（2026-09） | SVG | 474KB（min） | あり | `@joint/layout-directed-graph`（dagre） | △ 図を編集する道具向き。高度な配置やミニマップなどは有料の JointJS+ |
| vis-network | Apache-2.0 か MIT・10.1.2（2026-08） | canvas | 652KB（min） | 塊にまとめる機能のみ（未検証） | 物理演算が既定、階層の配置もある | △ CrewAI が使う。物理演算の動きは状態の一覧に向かない（推測） |
| AntV X6 | MIT・3.1.8（2026-08） | SVG・HTML | 583KB（min） | あり | 別パッケージ | △ 編集向き。文書は中国語が中心 |
| AntV G6 | MIT・5.1.1（2026-05） | canvas など | 1.4MB（min） | あり | 多数 | △ 大きい |
| Mermaid | MIT・12.1.0（2026-10） | SVG（文から図） | 5.5MB（min） | subgraph | あり | × 状態が変わるたびに描き直しになる。LangGraph・pydantic-graph・Agent Framework の図の出力先。文書の図には使える |
| dagre（@dagrejs/dagre） | MIT・3.1.1（2026-08） | なし（位置の計算だけ） | 49KB（min） | 限られる | 層の配置 | ○ 自前の SVG で描くときの配置計算 |
| d3-dag | MIT・1.2.2（2026-07） | なし | 143KB（min） | なし | Sugiyama など | △ 自前の SVG で描くとき |

勧め
- **Cytoscape.js ＋ cytoscape-dagre** を第一とする。状態はクラス（`queued` `running` `awaiting_review` …）で色と形を変え、工程を親ノードにして作業を入れ子にする。
- 入れ子のまま整った配置が要るときに限り elkjs を足す（1.6MB と EPL を受け入れられるかを先に決める）。
- 進み具合の主な画面は、グラフでなく「ページ×コマ」の表やカードに状態の色を付ける方が読みやすい（推測）。工程は一本道なので、グラフで見せる価値があるのは「上流を変えたときにどこが古くなるか」と「何が後ろの工程を止めているか」（決めごと 5.2 の並び）。どちらを先に作るかは画面の試作で決める。
- Fabric.js（決定済み）はキャンバスの編集用で、状態のグラフには使わない。描画の仕組みが別になるので混ぜない（推測）。

---

## 8. 未検証の一覧
- どのライブラリも、この環境で動かしていない。
- compose の Temporal 開発用サーバー（CLI 1.9.1）の中のサーバーの版と、Priority・公平さ・アクティビティの一時停止が使えるか。
- 子ワークフローの取り消しが親から伝わるときの細かい振る舞い（`ChildWorkflowCancellationType`・`ParentClosePolicy` の既定）。
- Temporal の1件の中身（payload）と履歴の大きさの上限。
- Temporal Web UI の今のタイムラインの作り（vis-timeline をやめた理由と今の描き方）。
- PydanticAI の Temporal 連携での人の承認の細部。
- Restate のサーバーの今の Python SDK との組み合わせ、Hatchet の保存先の構成。
- vis-network の入れ子の機能、elkjs の EPL-2.0 の条件の細部。
- ComfyUI の公式画面がノードの進み具合をどう描くか。SwarmUI の束ね方。
- 「画像生成に特化したハーネスは無い」は探した範囲での話。

---

## 出典

LangGraph
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langgraph/checkpointers
- https://docs.langchain.com/oss/python/langgraph/durable-execution
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/streaming
- https://docs.langchain.com/langsmith/cancel-run
- https://docs.langchain.com/langsmith/studio
- https://pypi.org/project/langgraph/ ・ https://pypi.org/project/langgraph-api/

Temporal
- https://docs.temporal.io/develop/python/message-passing
- https://docs.temporal.io/develop/python/cancellation
- https://docs.temporal.io/develop/python/failure-detection
- https://docs.temporal.io/encyclopedia/detecting-activity-failures
- https://docs.temporal.io/develop/python/continue-as-new
- https://docs.temporal.io/workflow-execution/event
- https://docs.temporal.io/encyclopedia/workflow/workflow-pause
- https://docs.temporal.io/activity-operations/pause
- https://docs.temporal.io/develop/task-queue-priority-fairness
- https://docs.temporal.io/design-patterns/fairness
- https://temporal.io/blog/task-queue-priority-and-fairness-your-task-queue-your-way
- https://docs.temporal.io/develop/python/integrations/openai-agents-sdk
- https://docs.temporal.io/develop/python/workflows/workflow-streams
- https://github.com/temporalio/sdk-python/tree/main/temporalio/contrib （langgraph・workflow_streams の README）
- https://github.com/temporal-community/temporal-ai-agent ・ https://github.com/temporal-community/temporal-ai-agent/blob/main/docs/architecture.md
- https://temporal.io/blog/lets-visualize-a-workflow
- https://github.com/temporalio/ui/blob/main/package.json
- https://github.com/temporalio/temporal/releases

DBOS・Restate・Inngest・Hatchet・Prefect・Dagster
- https://docs.dbos.dev/python/tutorials/workflow-tutorial
- https://docs.dbos.dev/python/tutorials/workflow-communication
- https://docs.dbos.dev/python/tutorials/workflow-management
- https://docs.dbos.dev/production/hosting-conductor
- https://docs.restate.dev/develop/python/awakeables
- https://docs.restate.dev/services/invocation/managing-invocations
- https://github.com/restatedev/restate/blob/main/LICENSE
- https://agentkit.inngest.com/advanced-patterns/human-in-the-loop
- https://www.inngest.com/docs/features/inngest-functions/cancellation
- https://www.inngest.com/docs/features/realtime
- https://github.com/inngest/inngest/blob/main/LICENSE.md
- https://docs.hatchet.run/home/durable-execution
- https://docs.hatchet.run/home/cancellation
- https://docs.hatchet.run/home/streaming
- https://docs.hatchet.run/v1/pausing-workflows
- https://docs.prefect.io/v3/advanced/interactive
- https://github.com/PrefectHQ/prefect/blob/main/src/prefect/client/schemas/objects.py
- https://github.com/PrefectHQ/ControlFlow
- https://dagster.io/docs/guides/build/assets/asset-versioning-and-caching

エージェントの枠組み
- https://github.com/microsoft/autogen （README のメンテナンスモード）
- https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/human-in-the-loop.html
- https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints
- https://github.com/microsoft/agent-framework/blob/main/python/packages/core/agent_framework/_workflows/_viz.py
- https://docs.crewai.com/en/concepts/flows
- https://github.com/crewAIInc/crewAI/tree/main/lib/crewai/src/crewai/flow/visualization
- https://mastra.ai/docs/workflows/suspend-and-resume ・ https://mastra.ai/docs/workflows/overview
- https://github.com/mastra-ai/mastra/blob/main/LICENSE.md
- https://pydantic.dev/docs/ai/graph/graph/
- https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/
- https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/conversation/state.py
- https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py
- https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/conversation/stuck_detector.py
- https://github.com/SWE-agent/SWE-agent ・ https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/agents/default.py
- https://code.claude.com/docs/en/agent-sdk/agent-loop
- https://code.claude.com/docs/en/agent-sdk/hooks

画像生成
- https://github.com/Comfy-Org/ComfyUI/blob/master/server.py
- https://github.com/Comfy-Org/ComfyUI/blob/master/execution.py
- https://github.com/Comfy-Org/ComfyUI/blob/master/main.py
- https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_execution/progress.py
- https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/stores/executionStore.ts
- https://github.com/invoke-ai/InvokeAI/tree/main/invokeai/app/services/session_queue
- https://github.com/invoke-ai/InvokeAI/tree/main/invokeai/frontend/webv1/src/features/controlLayers/components/StagingArea
- https://github.com/mcmonkeyprojects/SwarmUI

グラフ描画
- https://js.cytoscape.org/
- https://github.com/kieler/elkjs ・ https://eclipse.dev/elk/reference/options/org-eclipse-elk-hierarchyHandling.html
- https://www.npmjs.com/package/@joint/core （README の JointJS+ の説明）
- https://www.npmjs.com/package/cytoscape-dagre ・ https://www.npmjs.com/package/cytoscape-elk
- https://www.npmjs.com/package/vis-network ・ https://www.npmjs.com/package/vis-timeline
- https://www.npmjs.com/package/@antv/x6 ・ https://www.npmjs.com/package/@antv/g6
- https://www.npmjs.com/package/mermaid ・ https://www.npmjs.com/package/@dagrejs/dagre ・ https://www.npmjs.com/package/d3-dag
- 大きさ：https://cdn.jsdelivr.net/npm/ の各ファイル（2026-10-08 に取得）
