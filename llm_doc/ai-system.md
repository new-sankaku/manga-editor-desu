# AI生成システム

## アーキテクチャ
```
ai-management.js（ルーター）
├─ provider/
│   ├─ ai-provider.js（基底クラス）
│   ├─ local-sdwebui-provider.js
│   ├─ local-comfyui-provider.js
│   ├─ runpod-comfyui-provider.js
│   ├─ falai-provider.js
│   ├─ llm-provider.js（LLM基底クラス。OpenAI互換chat/completions）
│   ├─ grok-provider.js
│   ├─ ollama-provider.js
│   └─ provider-registry.js（プロバイダ登録・ロール割り当て）
├─ queue/
│   ├─ task-queue.js（並行実行制御）
│   └─ generation-task-manager.js（aiTaskMap）
├─ comfyui/（ワークフロー、エディタ、v2）
├─ sdwebui/（設定、API呼び出し）
├─ inpainting/（マスクエディタ、ワークフロー）
├─ angle/（カメラアングルエディタ、Three.js使用）
├─ role/（ロール割り当てUI）
├─ ui/
│   ├─ unified-settings-window.js（APIサービス設定）
│   ├─ model-settings-window.js（モデル・ワークフロー設定フローティングウインドウ）
│   └─ ai-ui-util.js
├─ prompt/auto/（自動プロンプト生成）
├─ prompt/panel-composition.js（役割→構図タグ、SDXLバケット）
├─ prompt/llm/llm-story-service.js, -ui.js（ストーリー→コマのプロンプト）
└─ prompt/prompt-apply.js（コマへの書き込みとページ送り）
```

## プロバイダ基底クラス（ai-provider.js）
```javascript
class AIProvider{
  async executeT2I(layer,spinnerId)
  async executeI2I(layer,spinnerId)
  async executeRembg(layer,spinnerId)
  async executeUpscale(layer,spinnerId)
  async executeInpaint(layer,spinnerId)
  async executeAngle(layer,spinnerId,anglePrompt)
  async fetchModels()
  async fetchSamplers()
  async fetchUpscalers()
}
```

## TaskQueue（task-queue.js）
Promise-based並行実行。プロバイダ別にキューが分かれる。
| キュー | 対象 | 並行数 |
|--------|------|--------|
| `sdQueue` | SD WebUI | 1 |
| `comfyuiQueue` | ComfyUI | 1 |
| `falaiQueue` | Fal AI | 1-10 |
| `grokQueue` | Grok | 1-10 |
| `ollamaQueue` | Ollama | 1-10 |

## ロール割り当て（provider-registry.js）
タスク種別ごとにどのプロバイダを使うか設定。行の定義は`ROLE_MATRIX_ROWS`（ai-roles.js）に
集約してあり、マトリクスUIと接続状態チェックの両方がこれを参照する。

- T2I, I2I, UP, BG, IP, ANG, TAG
- LLM系: `Text2Prompt`（文章を英語プロンプト化）, `Image2Prompt_LLM`（画像からプロンプト化）,
  `Text2Text`（セリフの推敲・翻訳）
- `ROLE_NONE`（`'none'`）を選ぶとそのロールは無効。`getProviderForRole()`が
  アクティブプロバイダへフォールバックせず即nullを返すため、関連ボタンも消える
- 未設定（`'default'`）はアクティブプロバイダへのフォールバック。マトリクスのラジオは
  `getProviderForRole()`の実際の戻り値で初期選択する。特定列をハードコードで
  選択すると、表示と実際の呼び出し先がずれるため

## LLMプロバイダ（llm-provider.js）
GrokもOllamaもOpenAI互換の`/v1/chat/completions`で叩けるため、本体は`LLMProvider`に集約し、
サブクラスは接続先・認証ヘッダ・モデルselectのidだけを返す。

```javascript
class LLMProvider extends AIProvider{
  getBaseUrl()                                   // 例: https://api.x.ai/v1
  getModelSelectIds()                            // {text:'grokModelText',vision:'grokModelVision'}
  async chat(messages,options)                   // options.vision=true でvisionモデルを使う
  buildTextMessages(systemPrompt,userPrompt)
  buildVisionMessages(systemPrompt,userPrompt,imageDataUrl)
  async fetchModels()                            // GET /v1/models → 両selectに反映
  async heartbeat()
}
```

- テキスト用と画像認識用でモデルを別々に選べる（`getModelId('text')` / `getModelId('vision')`）
- `stream:false`固定。タイムアウトは`LLM_REQUEST_TIMEOUT_MS`（AbortController）
- 失敗時はフォールバックせず例外を投げる。呼び出し側で明示的に通知すること

### Grok（grok-provider.js）
- `https://api.x.ai/v1`、`Authorization: Bearer <key>`
- **ブラウザ直叩き可**。`access-control-allow-origin: *` を返すため`file://`（`Origin: null`）でも通る

### Ollama（ollama-provider.js）
- 既定`http://127.0.0.1:11434` + `/v1`。APIキー不要
- **`OLLAMA_ORIGINS`の設定が必須。** 未設定だと`Origin: null`のリクエストは403で拒否される。
  手順は`html/API_Help/llm_settings.html`（設定画面の「?」とHelpメニューから開く）

### 接続失敗の切り分け（classifyFailure）
ブラウザではCORS拒否とサーバー停止がどちらも同じ`TypeError`になり区別できない。
そこで通常のfetchが失敗したら`mode:'no-cors'`でもう一度投げ、
opaqueレスポンスが返る＝サーバーは生きている＝CORS拒否、と判定する。

- 判定結果は`setConnectionNotice(kind)`で設定画面の`#ollamaConnNotice` / `#grokConnNotice`に表示
- CORS拒否を「接続できません」と丸めない。原因が違えば対処も違うため

### モデル一覧の自動取得とトースト
**起動時の自動取得は使用サービス表で選ばれているLLMだけに行う**（`llmFetchModelsIfInUse()`）。
Ollamaは接続先URLに既定値が入っているため、無条件に取得すると「なし」にしていても
起動のたびに接続を試みてエラートーストが出る。
**設定ウィンドウを開いた時はロール未割り当てでも接続情報が入っていれば取得する**
（`llmFetchModelsIfConfigured()` / `isConfigured()`）。割り当て前にモデルを選べないと設定が完了しないため。
どちらも`{silent:true}`なのでトーストは出ない。

| 呼び出し | 条件 | 失敗時 |
|----------|------|--------|
| 起動時 | 使用中かつモデル未取得（`hasLoadedModels()`） | 画面内の警告のみ（`{silent:true}`） |
| 設定ウインドウを開いた時 | 接続情報が入力済みかつモデル未取得 | 画面内の警告のみ（`{silent:true}`） |
| 再取得ボタン・APIキー/URLの変更 | 常に | 警告＋トースト |

`hasLoadedModels()`は取得成否のフラグ（`_modelsLoaded`）で判定する。select内の`<option>`数では判定しない
（取得失敗時も保存済みの選択値のoptionを残すため、数では区別できない）。

heartbeat（15秒毎）も`getInUseProviders()`が対象なので、「なし」のサービスには接続しない。

### モデル選択値の保持
selectの`<option>`はAPI取得後に作られるため、リロード直後は保存値に対応するoptionが存在しない。
`el.value=保存値`は無言で`''`になり、設定の自動保存でlocalStorage側まで潰れるため、
復元・再構築のどちらも`applySettingValue()`（project-management.js）でoptionを補ってから選択する。
取得中の一時表示（`_showFetchingState()`）で消える選択値は`_pendingValues`に退避して復元する。
詳細は`history-and-data.md`の「selectの復元」を参照。

## ストーリー→コマのプロンプト（prompt/llm/llm-story-service.js, -ui.js）
左パネル「プロンプト」の入口。ストーリー1本と、キャンバス上のページ数・コマ数・
コマ配置をLLMへ渡して各コマのプロンプトを作る。ロールは`Text2Prompt`。
範囲は`storyApplyScope`で「1コマ / 1ページ / 全ページ」。

LLM呼び出しは3種類。いずれも`response_format:{type:'json_object'}`で受け、
**欠けた分を黙って埋めずエラーにする**。

| 呼び出し | 入力 | 出力 |
|----------|------|------|
| `llmStorySheets(story)` | ストーリー | `{"characters":[...],"locations":[...]}` → 1行1件のテキスト2本 |
| `llmStoryPagePlan(story,pageInfos)` | ストーリー＋各ページのコマ数 | `[{page,summary,place}]`（`place`は`location / time`を1行に繋いだもの） |
| `llmStoryPanelPrompts(context)` | ページのあらすじ＋場所＋前後ページ＋コマ配置＋キャラ表＋ロケ表 | `{entries:[{prompt,role}],warning}` |

**どの範囲でも必ず「構成 → コマ」の順で通す。** 1コマ / 1ページ範囲も
`llmStoryPagePlan(story,[{page:1,panelCount:N}])`を先に通す。ストーリー全文を
そのまま1ページ分として渡すと、どのコマにも情報を詰め込もうとして緩急が消えるため。
圧縮結果はプレビュー上部（`llmStoryPlanNote`）に必ず出す。黙って圧縮したまま進めない。

**場面転換はコード側で判定する。** `place`が前のページと違えば場面転換とみなし、
そのページの1コマ目に`establishing`を要求する（`findPanelRhythmProblem`の第2引数）。
1ページ目は必ず場面の始まり。選択コマだけの範囲はページ先頭とは限らないので対象外。
判定は文字列一致だけで行うため、プレビューの「場所 / 時間」欄を直すと判定も追随する。

**各ページのコマ生成には前後のページを渡す。** 前ページを知らないと
ページ境界の場面転換が分からず、転換直後に引きの絵を置く判断ができない。
`prevSummary` / `prevPlace` / `nextSummary`を`llmStoryPanelPrompts`のcontextへ入れる。

- コマの並べ替え（`sortPanelsInReadingOrder`）・レイアウト要約（`buildPanelLayoutSummary`）・
  コマ応答のパース（`parseStoryboardResponse`）・役割の検証と再依頼（`requestPanelPrompts`）は
  **llm-storyboard-service.jsの関数をそのまま使う**。同じ処理を二重に持たない
- **キャラ表は各コマのプロンプトへそのままコピーさせる。** これがないとコマごとに
  見た目が変わる。空でも動く（任意項目）
- **ロケ表（`storyLocationInput`）も同じくそのままコピーさせる。** 同じ場所のコマで
  背景タグが揺れると場所が飛んで見える。キャラ表と1回の呼び出しでまとめて抽出する
  （`llmStorySheets`／ボタンは`llmStoryExtractSheets`）
- 画風タグ（`storyArtStyle`）はLLMに書かせず`promptApplyToPanel()`が足す。
  毎回書かせると揺れるため。既に入っているタグは足さない（追記で重ならない）
- 1コマ / 1ページは構成1回＋コマ1回。**全ページは「採寸の送り」→ページ構成→
  プレビュー→「全ページ分を並列生成」→「書き込みの送り」**。ページ送りは2回。
  ページをまたいでfabricオブジェクトの参照は持てないため、書き込む側では
  コマを取り直す
- **LLM呼び出しをページ送りの内側でawaitしない。** そうするとページ送りに
  直列化され、プロバイダごとの「同時実行数」設定（`grokConcurrency`等）が効かない。
  コマ配置（`buildPanelLayoutSummary`）はキャンバスを開かないと取れないが、
  LLM呼び出し自体はその結果のデータしか使わない。だから
  **採寸（送り1回目）→ 全ページ分をまとめてキューへ投入 → 書き込み（送り2回目）**
  に分ける。実際に何本同時に走るかは`TaskQueue`の設定が決める
  （Grokは上げてよい。Ollamaはローカルなので既定の1のまま。ユーザー設定に委ねる）
- 並列生成は`llmStoryGeneratePagePrompts()`。**1ページの失敗で全ページ分を捨てない**よう
  成否はページ単位で受ける（`{page,guid,panelResult}` / `{page,guid,error}`）
- 採寸してから書き込むまでにコマを増減された場合は、**コマ数が合わないページを
  書かずに`storySkippedPages`で報告する**。ずれたまま入れると別のコマ用の
  プロンプトが別のコマに入る。黙って部分適用しない
- **生成結果は必ずプレビューウインドウに出し、編集してから「追記」「置き換え」を選ばせる。**
  黙って書き換えない。全ページはページ構成の段階でプレビューする
- 中止（`OP_isCancelled`）はページの境界で見る。中止ボタンの`clearAllQueues()`が
  待機中のLLM呼び出しを落とすため、例外時も`OP_isCancelled()`なら中止として扱う
- 書き込み側とページ送りは`prompt/prompt-apply.js`（→`history-and-data.md`）

自動生成パネルの「ネームから一括生成」（`llm-storyboard-ui.js`）は
1ページ分だけを扱う従来の入口で、こちらの「1ページ」範囲と機能が重なる。

## LLMプロンプト生成（prompt/llm/）
`llm-prompt-service.js`がLLM呼び出し、`llm-prompt-ui.js`がフローティングウインドウ。

| 機能 | ロール | 入口 |
|------|--------|------|
| 文章→タグ | `Text2Prompt` | プロンプトパネルの「文章から生成」ボタン（Generateの隣） |
| 画像→タグ | `Image2Prompt_LLM` | レイヤーのアクションバー（DeepDanbooru/CLIPの隣、`actLlmTag`） |

- どちらも出力は`normalizeTagOutput()`を通す。コードフェンス・箇条書き記号を除去し、
  改行をカンマに変換して大小文字を無視した重複排除を行う。空になったらエラーにする
- 画像→タグは`sdwebuiInterrogate`と同じ挙動。`layer.text2img_prompt`へ追記し、
  `refreshPromptPanel(layer)`（auto-prompt-ui.js）でパネルを描き直す
- 文章→タグは生成結果を一度ウインドウに表示し、「設定」「追記」をユーザーが選ぶ。
  黙って上書きしない
- キャンセルは`updateAiTaskCancelInfo(spinnerId,{queueName:provider.id})`。
  `_getQueueByName()`（spinner.js）に`grok` / `ollama`を登録済み
- システムプロンプトは`LLM_TEXT2PROMPT_SYSTEM` / `LLM_IMAGE2PROMPT_SYSTEM`に定数化。
  「タグのみ出力」「存在しない作品名・キャラ名を作らない」を明示している

## ネーム→コマ一括生成とコマの役割（llm-storyboard-service.js / -ui.js）
あらすじ1本からページ内の全コマ分のプロンプトを生成する。入口は
左パネル「自動プロンプト」内の「ネームから一括生成」ボタン。ロールは`Text2Prompt`。
**システムプロンプトの本体（`buildPanelSystemPrompt()`）はストーリー側と共有する。**
片方だけ直して食い違うのを防ぐため。

- `sortPanelsInReadingOrder(panels,rightToLeft)`で読み順に並べる。
  上端でソート→先頭コマの縦帯に中心Yが入るものを同じ段とみなす→段内をleftでソート
  （右→左がデフォルト。チェックボックスで左→右に切替可）。帯は広げない。広げると
  背の高いコマが後続の段を飲み込んでしまうため
- `buildPanelLayoutSummary()`が各コマの形状・キャンバス比・面積シェア・
  `bleed`（断ち切り＝紙面端に接する）・`first` / `last`をLLMに渡す。
  これで「大ゴマ＝引きの見せ場、小ゴマ＝リアクション、断ち切り＝広がり」の配分が効く
- **タグを直接書かせず、先にコマの役割（`role`）を宣言させる。**
  `MANGA_PANEL_ROLE_NAMES` = establishing / scenery / insert / full / medium / closeup / impact。
  役割を挟まないと、どのコマもキャラのバストアップに収束してページの緩急が消える
- **役割の配分をコード側で検証する**（`findPanelRhythmProblem(entries,sceneChange)`）。
  - 人物なしコマの枚数: `requiredEmptyPanelCount()`が4コマ以上で1枚、7コマ以上で2枚を要求し、
    `MANGA_EMPTY_ROLES`かつ`no humans`タグ付きのコマを数える
  - 場面転換: `sceneChange`が真なら1コマ目の役割が`establishing`であること
  
  違反があれば`requestPanelPrompts()`が内容を添えて**1度だけ**作り直す。
  2度目も守られなければ結果は返すが`warning`を必ず画面に出す。黙って通さない
- 応答は`response_format:{type:'json_object'}`（`chat`の`options.jsonObject`）で
  `{"panels":[{"index":1,"role":"...","prompt":"..."}]}`固定。`parseStoryboardResponse()`が
  1..Nの全indexが揃っているか検証し、欠けていたら**欠番を挙げてエラー**にする。
  足りない分を埋めたり黙って部分適用したりしない。知らない役割名は空にする
  （近い役割へ寄せると人物なしコマを数え違えるため）
- **構図タグ（wide shot / upper body / close-up / from above / dutch angle /
  looking at viewer など）はLLMに書かせない。** 役割から書き込み側が足すので、
  ここでも書かせると「引きのコマにupper body」のように打ち消し合う（→構図タグの節）
- **人数タグ（1girl / 2girls / solo）はコマ側で決める。** キャラ表には入れさせない。
  2人のコマでキャラ表を2つ並べると`1girl`が2回入り、soloへの偏りと噛み合って破綻する
- 生成結果はコマ単位のtextareaでプレビューし、編集してから「設定」「追記」を選ぶ。
  コマ番号の下に役割名（引き・情景…）を出し、ページの緩急を目で確認できるようにする。
  textareaにフォーカスすると該当コマがキャンバス上で選択され、対応を確認できる

## 構図タグ（panel-composition.js）
漫画のコマの構図と、画像生成モデルが既定で描く構図の差を埋める。
**画風タグ（`appendMangaStyleSuffix`）と同じくLLMには書かせず、書き込み側で決め打つ。**
偏りを埋めるのが目的なので、毎回同じ強さで入っていないと意味がないため。

差の実態（Danbooruのポスト数）:
`cowboy_shot` 831,263 / `upper_body` 1,165,014 に対し `wide_shot` 23,183、
`very_wide_shot` 2,190。`looking_at_viewer` は 4,793,726 で全体の過半数。
**何も指定しないと「1人・膝上・正面・カメラ目線」に落ちる。** 漫画のコマが取らない構図。

- 入口は左パネル「プロンプト」内の「構図タグを足す」。作品傾向のプリセットは
  `general` / `seinen` / `shonen` / `shojo` / `adult` / `none`。
  `PANEL_COMPOSITION_BASE`（役割ごとの土台）を`PANEL_COMPOSITION_PRESETS`が上書きする
- **プリセットは欄を書き換えるだけで、真実は画面の欄**（`storyCompositionTags` /
  `storyCompositionNegative`）。1行1役割の`role: tag, tag`形式。何が足されるかを
  隠さないため、プレビューの各コマにも読み取り専用で併記する（`.llm-panel-composition`）
- 知らない役割名は黙って捨てず`storyPromptStatus`に出す。捨てると効いていないことに
  気付けない
- **ネガティブはLLMが作らないので置き換える相手がいない。** 手書きのネガティブを
  消さないよう常に足す側に回る。ポジティブに入っているタグは打ち消し合うので除く
- 前回足した分は`panel.text2img_composition`（`commonProperties`に登録）に覚えておき、
  次に書き込む前に外す。**役割が変わって作り直したとき、前の役割のタグが残らないように。**
  同じ役割で2回押しても結果は変わらない
- 「生成サイズをコマの形に合わせる」（既定オフ）で`PANEL_SDXL_BUCKETS`から最寄りの
  学習解像度を選び`text2img_width/height`へ入れる。**横長コマに引きの絵を割り当てても、
  正方形で生成して嵌めると上下が切られて結局バストアップに見えるため。**
  極端な帯コマは端のバケットに寄せて生成し、コマ側で切り出す
- 追加・削除は`promptApplyToPanel()`の1か所だけ。ネーム窓とストーリー→コマの
  両方がここを通るので、片方だけ効かない状態にならない

## セリフ支援（llm-dialogue-service.js / -ui.js）
選択中のテキストオブジェクトに対して推敲・口調変更・文字数調整・翻訳を行う。
入口は左パネル「テキスト」内の「セリフを整える」ボタン。ロールは`Text2Text`。

- 対象は`canvas.getActiveObject()`が`isText()`のもの。`.text`は
  `i-text` / `text` / `textbox` / `vertical-textbox`（`fabric.IText`継承）で共通
- 文字数調整の上限は`estimateTextCapacity()`が吹き出しの実サイズから概算して初期値に入れる。
  縦書き（`isVerticalText`）は1行の文字数と行数を入れ替えて計算する。
  あくまで目安なので**画面に目安値を出したうえでユーザーが編集できる**ようにしている
- 反映は`applyDialogueText()`に集約。`set('text')`→`initDimensions()`→`setCoords()`→
  `commitHistory()`→`updateLayerPanel()`。ボタン1回の操作なので履歴は即1件
  （レイヤー名がテキスト先頭20文字なのでパネル更新も要る）
- 反映前に対象オブジェクトがまだキャンバスに存在するか確認する。
  生成中に削除された場合に消えたオブジェクトへ書き込まないため
- 出力は`normalizeDialogueOutput()`で前後の引用符とコードフェンスのみ除去する。
  セリフ本文には手を入れない

## 接続状態の表示
`#ExternalService_Heartbeat_Container`のチップは`getInUseProviders()`が対象。
`ROLE_MATRIX_ROWS`の各ロールについて`getProviderForRole()`を引き、**実際に選ばれている
サービスだけ**を返す。「なし」や未対応（—）の行しかないサービスは接続チェックしない。
使用サービス表のチェック状態と接続状態の表示を一致させるため。
チップの`title`にはオフライン時の理由（`getStatusReason()`）が入る。

## ObjectInfo（ComfyUIノード定義）
ワークフローのノードが接続先ComfyUIに存在するかを`checkWorkflowNodeVsComfyUI()`で照合する。
照合元は`comfyObjectInfoRepo_local` / `comfyObjectInfoRepo_runpod`（IndexedDB）。

- **未取得だと全ノードが「存在しない」と判定され、生成・背景削除・アップスケールが
  一律に中断される。** 取得は`comfyui_monitorConnection_v2()`の接続確立時のみで、
  この監視はモデル・ワークフロー設定ウィンドウを開くまで開始されない
- そのため`checkWorkflowNodeVsComfyUI()`は未取得なら`fetchAndSaveComfyObjectInfo()`で
  その場で`/object_info`を取得する。起動直後でも動くようにするため
- 取得できなかった場合は「全ノード欠落」ではなく接続エラーとして通知する。
  ノード名を並べると原因を誤認させるため
- 監視ループは`comfyMonitorStarted`で1本に制限。複数動くと接続状態の変化を
  取り合ってObjectInfoの更新が走らないことがある。ループ内は例外を握りつぶす
  （例外でループが終了するとObjectInfoが二度と更新されない）

## デフォルトワークフロー
`comfyuiDefaultWorkflows`（comfyui-default-workflows.js）をDOMContentLoaded時に
IndexedDBへ登録する。`getEnabledWorkflowByType(type)`は該当typeで`enabled`のものを返す。
有効なワークフローが無い場合はnullを返すので、呼び出し側で明示的に弾くこと。

## タスクライフサイクル（generation-task-manager.js）
→ `layer-structure.md`のAIタスク進捗管理セクション参照

## ComfyUI プロバイダ切り替え（comfyui-management.js）
`_comfyUIExecProvider` グローバル変数でリクエスト単位のプロバイダを制御する。
```javascript
async function comfyUIExecWithProvider(provider, fn){
  _comfyUIExecProvider = provider;
  try { return await fn(); }
  finally { _comfyUIExecProvider = null; }
}
```
- `getComfyUIServerAddress()` / `getComfyUIAuthHeaders()` / `getComfyUIProviderTag()` はすべて `_comfyUIExecProvider || providerRegistry.getActive()` を参照
- `comfyUIUrls` は Proxy で、プロパティアクセスのたびに `getComfyUIServerAddress()` を呼ぶ動的URL
- **注意**: `fn()` 内で長時間の await（WebSocket待機等）を行うと、その間に別の非同期タスク（ワークフローエディタ更新等）が `comfyUIExecWithProvider` を呼び `_comfyUIExecProvider` を上書きする。await 後に `comfyUIUrls.*` や `comfyuiFetch()` を使うと別プロバイダのURLに接続してしまう
- **対処**: 関数冒頭で `getComfyUIServerAddress()` / `getComfyUIAuthHeaders()` をローカル変数にキャプチャし、await後はそのローカル変数を使って直接 `fetch()` する

## ComfyUI v2ワークフロー
- `comfyui-workflow-repository.js` でワークフロー保存/読み込み（ファクトリパターン）
  - `createWorkflowRepository(providerKey)` でプロバイダー別インスタンス生成
  - `comfyUIWorkflowRepo_local` / `comfyUIWorkflowRepo_runpod`
- `comfyui-object-info-repository.js` でノード情報キャッシュ（同様のファクトリパターン）
  - `comfyObjectInfoRepo_local` / `comfyObjectInfoRepo_runpod`
- `comfyui-workflow-editor.js` でビジュアルエディタ（オプションで providerKey, workflowRepo, objectInfoRepo, provider, containerEl を受け取る）
- デフォルトワークフロー: t2i, inpaint, angle, upscale, rembg

## モデル設定フローティングウインドウ（model-settings-window.js）
3タブ構成：
1. **ComfyUI Workflow** — Local ComfyUIのワークフロー管理（ObjectInfo: comfyUIPageUrl）
2. **RunPod ComfyUI Workflow** — RunPod ComfyUIの独立ワークフロー管理（ObjectInfo: runpodComfyUIUrl）
3. **SD WebUI** — モデル・サンプラー等のSD WebUI固有コントロール

各タブは遅延初期化。ComfyUIタブはそれぞれ独立した `ComfyUIWorkflowEditor` + `ComfyUIWorkflowWindow` インスタンスを持つ。
