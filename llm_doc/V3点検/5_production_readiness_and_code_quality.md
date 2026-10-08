# 監査5：本番で動かせるか・コードの質（v3-server-plan / 6026d6c）

読むだけで調べた。コードと文書は変えていない。行番号は `v3/server/src/v3server/` からの相対（ほかは明記）。
分類：足りない／磨けていない／高度化が要る。重さ：必須（原稿を預かる前に要る）／重要／後で。
「文書既知」は `llm_doc/V3サーバーの土台.md` 9章に書いてあるもの。書いていないものは「文書に無い」と付けた。

## 0. 測ったもの

| 項目 | 結果 |
|---|---|
| 試験 | `uv run --with pytest-cov pytest --cov=v3server`：**290 passed, 12 skipped**（136秒）。飛ばしたのは本物の ComfyUI 10件・検出器2件（`V3_TEST_COMFYUI_URL`・`V3_TEST_DETECTOR_URL` が無い） |
| 網羅率 | **全体 82%**（9,713行中 1,719行が未実行）。pyproject は変えていない（`--with` で一時的に入れた） |
| ruff | プロジェクトに ruff の設定も dev 依存も無い。手元の `ruff`（利用者側の設定）で `uv run ruff check` → **179件**（うち115件は自動で直せる。並べ替え45・型注記の書き方25など）。既定の規則（`uvx ruff check src tests`）では139件 |
| ruff の中で中身があるもの | F821 2件（`comfy_graphs/text_to_image_graph.py:79-80` の `'DiffusionSettings'`・`'Extras'` が import されていない。注記の文字列なので実行時には落ちない）、B006 1件（`http_routes/settings_and_search_routes.py:58`）、DTZ005 1件（`http_routes/http_app_factory.py:78`）、F811 9件（試験の fixture の名前の重なり）。B023 16件（`panel_layout/panel_geometry.py:129-134`）は同じ周回の中でしか呼ばないので誤検出 |
| 型 | 型の検査器は設定されていない。`uv run --with mypy mypy src/v3server --ignore-missing-imports` → **221件／45ファイル**（union-attr 101・arg-type 75）。実害の確認できたものは無いが、注記が実体と違う箇所がある（`print_export/page_render.py:323` は `Image` と書いて `(Image, int)` を返す、`operations/operation_submit_and_undo.py:104,114` は `OpBase` に `type` が無い） |
| 型注記の量 | 関数807個のうち、戻り値の注記が無いもの約267個（口の関数のほとんど） |
| except Exception | 7か所。全部、巻き戻してから投げ直すか、理由を記録してから失敗として返す。握りつぶしは無い |
| TODO/FIXME | 0件 |
| 長い関数 | 70行以上は4つ（`print_export/page_render.py:356 render_page` 161行、`panel_layout/constrained_tier_layout.py:111` 112行、`generation_queue/service_call_activity.py:100 call_service` 88行、`lock_rules.py:51 acquire` 73行）。複雑度10超は12関数 |

## 1. しっかりしているところ（短く）

- 正本を変える道が1本：`operations/operation_submit_and_undo.py:84 submit` が作品の行を `SELECT … FOR UPDATE`（`:28`）で取り、権限（OpenFGA）→ロック→適用→出来事の追記を1つのトランザクションで行う。`events` は `(work_id, seq)` に一意の制約（`canonical_tables/event_and_lock_tables.py:27`）。取り消しの二重実行も行のロックの中で確かめている（`:96-102`）。同時に送る試験もある（`tests/integration/test_ops.py:84`）
- OpenFGA の書き込みと DB の確定がずれたときの打ち消し（`operation_submit_and_undo.py:121-127`、`http_routes/work_routes.py:59-65`）
- 設定は既定値を置かず、無ければ起動時か使う時に止める（`server_settings.py`）。CLAUDE.md の「fallback禁止」と合っている
- 移行：NOT NULL を足す列は全部 `server_default` 付き（0002・0003・0005・0006）。試験の度に `downgrade base → upgrade head` を通す（`tests/integration/conftest.py:27-36`）
- 書き出したファイルの取得は、記録にある名前だけを返す（`http_routes/export_routes.py:104`）。パスの抜け道は見当たらない。絵のパスは sha256 の名前で作る（`image_file_storage.py:37`）
- 生成した PNG から指示文の欄を外してから置く（`image_intake.py:46`）
- 予算の上限（`generation_queue/service_call_activity.py:129`）、自動で別の先へ回さない（`docker/litellm.yaml`）

## 2. 認証とアカウント

### 2-1 ログインが無い（足りない／必須／文書既知）
- 根拠：`http_routes/http_dependencies.py:29-35`。`V3_DEV_AUTH=1` のとき `X-V3-User` の値をそのまま利用者にする。名前を書き換えれば誰にでもなれる。`.env.example` は `V3_DEV_AUTH=1` が入った状態
- 画面は利用者名を localStorage に入れて毎回付ける（`v3/web/js/api.js:3-29`）
- なぜ困るか：1人で手元で使う以外では、他人の原稿が全部読める・変えられる
- 足りないもの：セッション（クッキーかトークン）、OIDC のつなぎ（Keycloak・Ory は p54 で比べただけ）、ログアウト・期限、利用者の表（利用者は OpenFGA の文字列だけで、DB に利用者の行が無い）、招待、メールの確認

### 2-2 CSRF・CORS・セキュリティの見出しが未設計（足りない／重要／文書に無い）
- 今は自作の見出しで認証しているので CSRF は起きない。クッキーのセッションに替えた時点で CSRF 対策が要る。`CORSMiddleware` も、`Content-Security-Policy`・`X-Frame-Options` などの見出しも無い（`http_routes/http_app_factory.py` 全体）
- 画面の進み具合はポーリング。理由は「EventSource は X-V3-User を付けられない」（`v3/web/js/app.js:351`）。ログインの方式がリアルタイム通知の方式も縛っている

### 2-3 作者がいなくなる・役の管理の口（足りない／重要／文書既知）
- 役を付ける・外す口が `members` の GET（`work_routes.py:130`）以外に見当たらず、操作経由のみ。作者が自分を外すと管理者がいなくなる（文書9章）
- `system:main` の admin を付ける手段は `admin_command_line.py` だけ（網羅率55%）

## 3. 置き場（絵のファイル）

### 3-1 アップロードを丸ごとメモリに読む・大きさの上限が無い（足りない／必須／文書に無い）
- 根拠：`http_routes/image_file_routes.py:56` `await image.read()`、PSD は `export_routes.py:123` `await psd.read()`、検出器も `v3/detector_server/src/*/detector_http_app.py:50` `upload.file.read()`。リクエストの大きさの上限、画素数の上限（`Image.MAX_IMAGE_PIXELS` の設定）、PSD の層の数の上限はどこにも無い（grep で0件）
- なぜ困るか：Pillow の既定は約8,900万画素を超えると警告、その2倍で止める。`inspect_image` は `verify()` と大きさを読むだけで、展開はしない。展開は後の縮小画像（`image_generation_routes.py:263`）・ペン・書き出しで起きるので、そこでメモリを食い潰す。PSD は psd-tools が層を全部展開する
- 必要なもの：本体の大きさの上限（逆プロキシか ASGI の中間層）、画素数・層の数の上限、ストリームで一時ファイルへ書いてから確かめる

### 3-2 権限を確かめる前にファイルを置き、記録を確定する（足りない／必須／文書に無い）
- 根拠：`http_routes/image_file_routes.py:53-56` は `can_view` だけを確かめて `take_in_image` を呼ぶ。`image_intake.py:68-86` はファイルを置き、判定の記録を **その場で commit** する。編集の権限は後の `submit`（登録）で初めて確かめる
- なぜ困るか：見るだけの役（viewer・client）でも、何度でも大きなファイルをサーバーの円盤に書け、`image_intake_screenings` の行も積める。断られても消えない
- 同じ形：`export_routes.py:139` の PSD の取り込みは層ごとに `take_in_image`（=commit）してから最後に `submit` する。途中で断られると、置いたファイルと記録だけが残る

### 3-3 参照されなくなったファイルを片付ける仕組みが無い（足りない／重要／文書に無い）
- 根拠：`unlink`・`rmtree`・`os.remove` が src に0件。ファイルは sha256 の名前で置くだけ（`image_file_storage.py:53-61`）
- 3-2 の断られたファイル、生成の途中失敗（4-2）、取り消した登録の絵がたまり続ける。容量の上限（作品ごと・利用者ごと）も無い

### 3-4 読むたびに丸ごとメモリへ・縮小画像を毎回作る（磨けていない／重要／文書に無い）
- 根拠：`image_file_routes.py:113` は `Response(read_image(...))` でファイルを全部メモリに入れて返す（`FileResponse` でない、`ETag`・`Range` なし）。縮小画像は要求のたびに LANCZOS で作り直し、置いておかない（`image_generation_routes.py:269-275`）
- 候補の一覧を開くたびに、原寸の絵を全部読んで縮める

### 3-5 中身の確かめ（磨けていない／後で）
- 読むときに sha256 を確かめない（`image_file_storage.py:64`）。ファイルが壊れても気付かない。DB にある sha256 と置き場の突き合わせの道具も無い

### 3-6 S3互換の置き場が無い・バックアップと戻しが無い（足りない／必須／S3は文書既知、バックアップは文書に無い）
- 置き場は `V3_IMAGE_DIR` の手元のフォルダだけ（`image_file_storage.py:1-2`）。サーバーを2台にできない
- DB（PostgreSQL の正本・OpenFGA の役・Temporal の SQLite）と絵のフォルダを、同じ時点で取って戻す手順・道具が無い。OpenFGA の役は PostgreSQL の別のデータベース（`openfga`）にあり、Temporal は SQLite（`compose.yaml` の temporal）。一方だけ戻すと、権限と作品がずれる

## 4. 安全（データ）

### 4-1 取り消しが、後から他の人がした変更を黙って上書きする（磨けていない／重要／文書に無い）
- 根拠：`operation_submit_and_undo.py:130-140` の `undo` は、出来事に残した逆の操作（変える前の値。`operations/operation_base.py:75`、`operations/human_hand_guard.py:126`）をそのまま当てる。後の出来事が同じ項目を変えたかを確かめる処理が無い（「今の値が、出来事の後の値のままか」を比べない）
- なぜ困るか：共同作業で、Aさんが昔の自分の変更を取り消すと、その後にBさんが同じ吹き出しに入れた文が消える。ロックは取り消しの時点のものしか見ない
- 足すもの：逆の操作に「当てる前の期待値」を持たせ、違えば判断待ちか拒否にする

### 4-2 生成の途中で落ちると、二重に送り二重に登録する（足りない／重要／文書に無い）
- 根拠：`generation_queue/service_call_activity.py:138-161`。外の生成先を呼んだ後、呼び出しの記録（`log("ok")`）の commit と、絵ごとの `submit`（1枚ずつ commit。`:76-85`）と、`job.status="done"` の commit が別々。作業者が途中で落ちると Temporal が activity をやり直し（`generation_workflow.py:77-80`、`resend_limit+1` 回）、もう一度生成先に送る。登録の id は毎回新しい（冪等の鍵が無い）
- なぜ困るか：有料の API なら費用が二重になり、記録に残らない分も出る。4枚中2枚目で断られると、1枚目だけ登録されて依頼は「止まった」になる
- 予算の確かめ（`:129`）は確かめてから送るまでの間に並列の依頼が入るので、上限を超えうる

### 4-3 DB とファイル・OpenFGA の間の部分失敗（磨けていない／重要／文書に無い）
- ファイルは DB の確定より先に置く（3-2・3-3）。逆向きのずれ（DB にあってファイルが無い）は起きにくいが、確かめる道具が無い
- OpenFGA へ書いてから DB を確定する（`operation_submit_and_undo.py:121`）。打ち消しの書き込み自体が失敗する・プロセスが間で落ちると、役だけ残る。直す道具が無い

### 4-4 出来事の形の版が無い（足りない／重要／文書に無い）
- `events.payload`・`inverse` は操作の pydantic の形のまま JSON で残す（`canonical_tables/event_and_lock_tables.py:38-40`）。版の列が無い。取り消しは `op_adapter.validate_python(inverse)`（`operation_submit_and_undo.py:93`）で今の形として読み直すので、操作の項目を変えると古い出来事が取り消せなくなる。移行は表だけを扱い、出来事の中身を移す手順が無い

### 4-5 移行の試験は空の DB だけ（磨けていない／後で）
- `conftest.py:33-36` は空の DB で下げて上げるだけ。データの入った DB での移行、本番の手順（止めずに上げる・戻す）は試していない

## 5. セキュリティ

### 5-1 口ごとの権限の抜け（足りない／重要／文書に無い）
57口を全部見た。多くは口か操作の窓口で OpenFGA を確かめる。抜け・順番の問題は次の通り。
- `GET /services`（`http_routes/service_routes.py:84-94`）：権限を見ない。ログインした誰でも、全部のつなぎ先の `endpoint`（社内の ComfyUI の住所など）・月の予算・利用規約・処理ごとの費用を読める
- `POST /works/{id}/images`・`/panels/{id}/image`：3-2 の通り、確かめる権限が `can_view`
- `GET /works/{id}`（`work_routes.py:73-113`）：作品の `can_view` だけで、全ページ・全文字・全ペンの線・赤入れ・設定資料を返す。ページ単位の権限（`openfga/model.fga` の `page`）や、依頼主・翻訳者に見せる範囲の区別は使われない
- `extract-characters`（`ai_job_routes.py:59-66`）・`annotations/{id}/job`（`:80-86`）・`replace_panel_image`（`image_file_routes.py:91`）は、権限を確かめる前に作品の中身を読む。断られるので漏れはしないが、存在の有無で返す番号が変わる
- 試験で 403 を確かめるのは4ファイル9か所だけ（`grep "== 403" tests`）。役ごと・口ごとの拒否の表の試験は無い

### 5-2 送り先の制限が自己申告（足りない／重要／文書に無い）
- `allowed_destinations.py:13-16`：`location == "local"` ならどの作品からも送ってよい。`location` は登録時に人が書く値で、`endpoint` の住所と照らさない（`service_routes.py:34-42` の `endpoint: str | None`、URL の形も確かめない）
- 管理者だけが登録できるので SSRF の入口は狭いが、誤って外の API を `local` と登録すると、作品の「送ってよい先」の制限（方針7・11章）を素通りする

### 5-3 API の鍵の扱い（磨けていない／重要／文書に無い）
- LLM の鍵は LiteLLM の設定と `.env` にあり、サーバーは全部の呼び出しで1つのマスターキーを使う（`service_senders/litellm_sender.py:30`）。作品・利用者ごとの仮想キーや上限は使っていない。鍵の入れ替え・秘密の置き場（Vault など）の決まりも無い
- ComfyUI の送り先に鍵を付ける欄が無い（`endpoint` だけ）

### 5-4 部品が無認証で外に開いている（足りない／必須／文書に無い）
- `compose.yaml`：PostgreSQL（利用者・合言葉とも `v3`）、OpenFGA（認証の設定なし）、Temporal、LiteLLM が全部 `0.0.0.0` の固定ポートで開く（`docker compose ps` で確認：`0.0.0.0:58080->8080` など）。OpenFGA に直接書けば、誰でも作者の役を付けられる

### 5-5 回数の上限が無い（足りない／重要／文書に無い）
- 回数を絞る仕組みが依存にも中間層にも無い。生成の枚数（`image_generation_routes.py:99` `le=MAX_COUNT`）と予算だけ。ログイン後の総当たり・生成の連打・大きなアップロードの連打を止められない
- `GET /works/{id}/events` の `limit` に上限が無い（`work_routes.py:157-160`、`limit: int = 200`）。ペンの線の数・点の数にも上限が無い（`operations/pen_stroke_operations.py:84,162` は `min_length` だけ）

## 6. 性能と規模

### 6-1 非同期の口の中で重い処理を同期で行う（磨けていない／重要／文書に無い）
- `to_thread`・`run_in_executor`・`run_in_threadpool` が src に0件。`async def` の口の中で、Pillow の縮小（`image_generation_routes.py:269`）、マスクの描画（`:284`）、PSD の読み込みと層の合わせ（`export_routes.py:119-130`）、画素の消しゴム（`pen_stroke_routes.py`）、ファイルの読み書き（`image_file_storage.py`）を行う。1人が大きな PSD を戻すと、その間サーバーの全員が止まる
- 書き出しの本体は Temporal の作業者で動く（`print_export/export_workflow.py`）ので、こちらは対象外

### 6-2 作品を丸ごと1回で返す（高度化が要る／重要／文書に無い）
- `GET /works/{id}`（`work_routes.py:73-113`）は、作品の全表を絞り込み無しで返す。抜いた行（`removed`）も、全ペンの線の全点（`pen_strokes.points`）も入る。ページ・話ごとの取り方、差分の取り方（`head_seq` 以降だけ）が無い。200ページ・線数万本で数十MBになる
- 検索（`operations/text_search_and_replace.py:48-61`）は該当の表を全部読んで Python で部分一致を探す。索引も全文検索も使わない

### 6-3 作品ごとの行ロックで全部の書き込みが1列に並ぶ（高度化が要る／後で）
- ペンの1本、ロックの取得・解放（`lock_rules.py:111-119` も出来事を足す）まで、作品の行の `FOR UPDATE` を取る。共同作業の人数が増えると待ちが伸びる。正しさのための設計なので、測ってから決める

### 6-4 出来事の表が伸び続ける（高度化が要る／後で）
- 出来事は消さず、スナップショットや畳み込みも無い。ペンの線は点の列を `payload` と `pen_strokes` の両方に持つ。`undoes_event_id` に索引が無く（`event_and_lock_tables.py:44`）、取り消しのたびに作品の出来事を探す（`operation_submit_and_undo.py:97-99`）
- 一覧の多くはページ分けが無い（`/works/{id}/jobs`・`/images`・`/locks`・`/services`）。ページ分けがあるのは `events` だけ

## 7. 運用

### 7-1 記録・数値・追跡が入っていない（足りない／重要／文書既知）
- `logging` を使うのは2ファイルだけ（`service_senders/comfyui_sender.py:42`、`generation_queue/queue_worker_main.py:27`）。口のアクセス記録、要求の id、だれが何をしたかの監査の記録（出来事以外。つなぎ先の変更は出来事に残らない＝文書既知）、数値（Prometheus など）、追跡（OpenTelemetry）は無い。p55 の Langfuse もつないでいない

### 7-2 ヘルスチェックが中身を見ない（磨けていない／重要／文書に無い）
- `GET /health`（`http_app_factory.py:76-78`）は時刻を返すだけ。DB・OpenFGA・Temporal・置き場のフォルダ・作業者が生きているかを見ない。時刻も時差なし（DTZ005）

### 7-3 本番の形が無い（足りない／必須／一部文書既知）
- アプリ本体は compose に入っていない（`compose.yaml:1`「手元で uv run で動かす」）。Dockerfile・プロセスの管理・TLS・逆プロキシの設定が無い
- Temporal は開発用（SQLite。文書既知）。PostgreSQL の合言葉は固定値
- 設定の確かめは起動時に4つの住所だけ。`image_dir` などは使う時に初めて止まる（`server_settings.py:26-37`）。起動直後に「絵の口が使えない」状態に気付けない
- 上げ方：移行を当てる順番（作業者とアプリと Alembic）、OpenFGA のモデルの切り替え（`openfga_permissions.py:108-114` は起動のたびにハッシュで比べて書く。2台同時起動で競う）の手順が無い

## 8. API の作り

### 8-1 エラーの形が3通り（磨けていない／重要／文書に無い）
- V3 のエラーは `{"code","detail"}`（`http_app_factory.py:61-63`）。`HTTPException` は `{"detail"}`（`http_dependencies.py:32-34`）。pydantic の検証は `{"detail":[...]}` で同じ 422（`Invalid` も 422）。OpenFGA・httpx の失敗（`openfga_permissions.py:52` `raise_for_status`）は 500 の素の文字列。画面（`v3/web/js/api.js:36-38`）は `detail` だけ見る

### 8-2 応答の型が無い・版が無い（磨けていない／重要／文書に無い）
- `response_model` が0か所。全部 `dict` を返すので、OpenAPI の応答の形は空。画面は手で書いたパスで呼び、OpenAPI から作った型を使わない（`v3/web/js/api.js`）
- `/v1` などの版の前置きが無い

### 8-3 リアルタイムの知らせが無い（足りない／重要／文書に無い）
- SSE・WebSocket が src と web に0件。画面は数秒ごとのポーリング（`v3/web/js/app.js:351-365`、`image_generation_routes.py:4`）。共同作業で他の人の変更・ロック・判断待ちを即座に見せる道が無い。`/events?after=` はあるので、これを流す口を足す余地はある

## 9. コードの質

### 9-1 lint・型の検査が開発の流れに入っていない（磨けていない／重要／文書に無い）
- `pyproject.toml` に ruff・mypy の設定も依存も無い。CI も無い（ワークフローのファイルが見当たらない）。数は0節の通り（ruff 179件、mypy 221件）
- 中身のあるもの：F821（`comfy_graphs/text_to_image_graph.py:79-80`）、mutable の既定値（`settings_and_search_routes.py:58`）、注記と実体の違い（`print_export/page_render.py:323` ほか）

### 9-2 層の混ざり（磨けていない／後で）
- 口の関数に業務の処理が入っている：PSD の取り込み（`export_routes.py:110-151`、座標変換・層ごとの登録まで）、生成の受付（`image_generation_routes.py:118` 複雑度13）。試験は HTTP 越しになり、網羅率も低い（56%）
- 同じ形の重複：作品の中の行を取る処理が `get_in_work` と `_job_in_work`（`job_routes.py:40-44`）で2つ。`row(obj, *fields)` で返す列を口ごとに手で並べている（`work_routes.py:84-113` など）。列を足すたびに複数の口を直す必要があり、CLAUDE.md の「修正漏れを防ぐ」に反しやすい

### 9-3 隠れた fallback
- 見た範囲では無かった。`except Exception` は全部投げ直し。設定にも既定値を置いていない

## 10. 試験

### 10-1 本物の生成先・検出器の試験は流れていない（足りない／重要／文書既知）
- 12件が飛ばされた（0節）。本物の ComfyUI の試験は SD1.5 の小さなモデル（`tests/integration/test_comfyui_real.py:57` `sd15_*_fp16.safetensors`）を前提にし、狙いのモデル（SDXL・制御の部品）は試していない。LiteLLM の送り手は網羅率18%、検出器の送り手は19%

### 10-2 網羅率の低いところ（60%未満）
`operations/held_change_operations.py` 43%、`image_candidate_operations.py` 44%、`panel_frame_operations.py` 47%、`panel_layout_proposal.py` 48%、`panel_layout/panel_frame_editing.py` 49%、`generation_queue/input_image_preparation.py` 51%、`operations/ai_proposal_flow.py` 52%、`psd_import_operations.py` 54%、`admin_command_line.py` 55%、`http_routes/image_generation_routes.py` 56%、`name_check_routes.py` 56%、`text_search_and_replace.py` 57%、`ai_job_routes.py` 59%、`pen_stroke_operations.py` 59%、`service_senders/litellm_sender.py` 18%、`detector_sender.py` 19%
- 判断待ち（人の手を守る仕組みの中心）と、コマの編集・PSD の戻しが半分しか通っていない

### 10-3 試験に無いもの（足りない／重要）
- 権限の拒否の表（5-1）、大きい・壊れたファイル（3-1）、取り消しと他人の変更の衝突（4-1）、作業者が途中で落ちたときのやり直し（4-2）、データの入った DB での移行（4-5）

### 10-4 同時に流すと壊れる（磨けていない／後で）
- 試験は compose の共有の `v3_test` を使い、毎回 `downgrade base` する（`conftest.py:27-36`）。別のセッションと同時に流すと互いの表を消す。今回は他の監査の試験と時間が重なったが、通った（たまたまの可能性がある）。Temporal の待ち行列も共有

## 11. 優先の順（必須だけ）

1. ログインとセッション（2-1）と、部品を外に開かない構成（5-4）
2. アップロードの上限と、権限を確かめてからファイルを置く順番（3-1・3-2）
3. 本番の形：アプリのコンテナ・Temporal の本番構成・TLS（7-3）
4. 置き場の S3 互換化と、DB・OpenFGA・絵を揃えて取るバックアップと戻し（3-6）
