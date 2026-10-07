# Manga2Manga計画

既存の漫画をフォルダ単位で読み込み、コマとセリフを残して絵を再生成する。
`llm_doc/次期サーバー化計画.md` の**工程D「既存の漫画を読み込んでフル再生成」の実施計画**にあたる。

調査日 2026-08-29。規模 L（大）。

---

## 次期サーバー化計画との関係

### 埋まった穴

`次期サーバー化計画.md` の工程Dは、前半2つが**未検証・最大の穴**とされていた。今回の調査でここが埋まった。

| 工程Dの項目 | 以前の状態 | 調査後 |
|---|---|---|
| ページ画像 → コマ分割の検出 | **未検証。最大の穴** | MagiV2 で成立。1ページ約1.3秒。**ただし CUDA 必須・モデル3.9GB** |
| 吹き出しの検出 | **未検証** | YOLOv8m で成立。1ページ約0.12秒・モデル50MB。種別7分類も出る |
| セリフのOCR | 漫画特化OCRは実在 | manga-ocr で成立。1ページ約1.3秒・モデル116MB。縦書きはモデル側が対応 |
| タグ抽出 → プロンプト化 | 実測済み（ブラウザ内53ms） | 変更なし |
| 生成 → コマへフィット | 実測済み | 変更なし |

**「後半は揃っていて、前半2つを測れば成立するかが決まる」という判断に対する答えは、成立する。**
ただし**コマ検出だけは GPU が要る**。ブラウザ内推論には載らない（MagiV2 3.9GB）。

吹き出し検出（50MB）と OCR（116MB）は、サイズ上はブラウザ内推論に載る見込みがある。
将来 ONNX 化できれば、**サーバー依存をコマ検出だけに縮められる**。ただし ONNX 変換の可否は**未検証**。

### サーバー化の結論とは矛盾しない

`次期サーバー化計画.md` 4章の結論は「サーバー化は必須ではない。判断の分かれ目は利用者に起動手順を課すかの一点」である。

**本計画はこの結論を変えない。**

- アプリ本体は `file://` のまま。**HTTP 配信しない**（3.3「ダウンロードして index.html を開くだけ」は失われない）
- サーバーは ComfyUI と同じ**任意起動の外部サービス**。起動しなければこの機能が無効になるだけで、他は全て従来どおり動く
- `CLAUDE.md` の必須要件（`file://` 動作）を変更しない

つまり本計画は「サーバー化」ではなく、**GPU が要る処理だけを外部サービスに出す**話である。
ComfyUI を外部に置いているのと同じ構図で、新しい前提を持ち込まない。

### 前提として残る2つ

`次期サーバー化計画.md` 5章の土台A・Bが、そのまま本計画の前提になる。

| 土台 | 本計画との関係 |
|---|---|
| **A: ページ工程（Queue の永続化）** | **Phase 4（再生成）の前提。** 1コマ数分 × ページ分で数時間になる。`js/ai/queue/task-queue.js` は保存も復元も無く、リロードで積んだものが全部消える（2026-08-31 確認）。**これが無いと Phase 4 は実用にならない** |
| **B: 話者と、吹き出し⇄コマの紐付け** | **解析側が両方返す。** 吹き出しは `panel_number` でコマに、話者は `speaker_char_id` で吹き出しに紐づく。ただしエディタ内部でこれを保持する仕組みは無いので、`commonProperties` への登録で作る（後述） |

土台Cのブラウザ内推論は本計画では使わないが、0.1 のとおり将来サーバー依存を縮める道になる。

---

## 概要

既存の漫画画像をフォルダ単位で読み込み、コマ・セリフ・人物を解析する。コマは Canvas 上のコマ割りとして、セリフは吹き出しとして再配置し、絵だけを AI で再生成する。

画像解析そのものは既存プロジェクト `manga-scenario-builder`（以下 manga-analyzer）のパイプラインを使う。本リポジトリには解析コードもモデルも持ち込まない。

**主要機能は `file://` のまま動く。** サーバーは ComfyUI や Ollama と同じ「起動していれば使える外部サービス」として扱う。

---

## 構成

### プロセス構成

```
[ブラウザ file://]  manga-editor-desu
        |
        | fetch (Origin: null) / WebSocket
        v
[127.0.0.1:8770]    manga-editor-server      ← 本リポジトリに新設
        |                    ^
        |                    └── MCP (stdio) ── [Claude Code]
        | HTTP（サーバー間。CORS 無関係）
        v
[127.0.0.1:8765]    manga-analyzer           ← 無改造で使う（別リポジトリ）
                     (CUDA / モデル)
```

### 3つの層の役割

| 層 | 責務 | GPU | 本リポジトリ |
|---|---|---|---|
| ブラウザ | 描画・編集。`file://` で動く | 不要 | ○ |
| **manga-editor-server** | **エディタのサーバー機能全般。** 形式変換、ローカルファイル操作、Claude Code 連携 | 不要 | ○（新設） |
| manga-analyzer | 漫画画像の解析（モデル推論） | **必須** | ×（別リポジトリ・無改造） |

### 機能をどちらのサーバーに置くかの判断基準

**この基準を守る限り、新しいサーバー機能の置き場で迷うことはない。**

| 置き場 | 条件 |
|---|---|
| **manga-analyzer** | 画像を見てモデルが何かを判定する。GPU が要る。エディタ以外からも使える汎用の解析である |
| **manga-editor-server** | エディタのデータ形式・UI・ファイル配置を知っている。GPU が不要。エディタのためだけに存在する |

`manga-editor-server` に将来入るもの（例）:

- MangaImport 形式への変換（本件）
- ローカルフォルダの列挙・参照画像の一括取り込み
- プロジェクトファイルのディスク保存・一覧・世代管理
- サーバー側での書き出し（PDF、連番画像）
- インストール済みフォントの列挙
- Claude Code 向け MCP ツール

`manga-analyzer` に足すもの: **本件では無し。**

### この構成を選ぶ理由

当初 `manga-analyzer` にエディタ向け router と MCP を足す案を検討したが、以下の理由で採らない。

- 解析専用プロジェクトにエディタ固有の関心事が混ざる
- **エディタにしか属さないサーバー機能の置き場が無い。** 本件以外のサーバー機能を作るたびに置き場を決め直すことになる
- 本リポジトリの機能が、別リポジトリへの改変を前提にしてしまう

自前サーバーを挟むことで得られる具体的な利点:

1. **`manga-analyzer` を無改造で使える。** ブラウザは 8765 に一切触らない。サーバー間通信は CORS の対象外なので、analyzer に `CORSMiddleware` を足す必要が消える
2. **`Origin: null` を許可するサーバーが自分のものだけになる。** 任意の Web ページから解析サーバーを叩けてしまう懸念が、自分の管理下に収まる
3. **「サーバー連携機能が使えるか」が1つの真偽値になる。** ユーザーから見て起動するものが1つで済む（analyzer は解析実行時にだけ必要）
4. **解析バックエンドを差し替えられる。** 別の解析器やリモート GPU に向け替えても、ブラウザ側は変わらない
5. スキーマ変換が Python 側に閉じる。JS は完成品の1形式だけを知ればよい

### コスト

Python 環境が2つ必要になる。ただし `manga-editor-server` の依存は `fastapi` / `uvicorn` / `httpx` / `mcp` のみで、**torch も CUDA も要らない**。venv 作成は数十秒で終わる。

`99_server.py` / `99_server.bat` は削除する（`99_server.bat` は存在しない `01_server.py` を呼んでおり、現状すでに動作しない）。

### アプリ本体を HTTP 配信してはいけない

`file://` と `http://localhost` ではオリジンが変わり、IndexedDB / localStorage が別物になる（`llm_doc/chrome.md:25-27`）。HTTP 配信に切り替えるとユーザーの既存プロジェクトと設定が全部見えなくなる。`manga-editor-server` は **API 専用**とし、静的ファイル配信は行わない。

---

## 解析パイプラインの実測

manga-analyzer のタスク列と実測値（45ページ・162コマ、`_data/log/` の PERF 出力より）。

| 経路 | タスク列 | LLM | モデル計 | 時間 |
|---|---|---|---|---|
| コマのみ | `image_import → panel_detection` | 不要 | 約3.9GB | 約1分 |
| **コマ＋セリフ** | `image_import → panel_detection → bubble_detection → text_ocr` | **不要** | **約4.1GB** | **約2.5分** |
| 話者・演出まで | ＋ `vision_analysis` 以降 | llama-server 必須（VRAM 24GB） | ＋約8GB | 約28分 |

**本機能の既定は「コマ＋セリフ」経路。** LLM を起動せずに済み、実用的な待ち時間に収まる。話者推定は任意の上位モードとする。

| 処理 | 手法 | 1ページ |
|---|---|---|
| コマ検出 | MagiV2 (`ragavsachdeva/magiv2`) | 約1.3秒 |
| 吹き出し検出 | YOLOv8m (`ogkalu/comic-speech-bubble-detector-yolov8m`) | 約0.12秒 |
| OCR | manga-ocr（縦書きはモデル側が対応） | 約1.3秒 |

**CUDA 必須。** `BaseTask._require_cuda()` が CPU 実行を明示的に禁止している。GPU の無い環境ではこの機能を出さない。

### 使う manga-analyzer の既存 API（追加不要）

| 用途 | エンドポイント |
|---|---|
| 起動確認 | `GET /health` |
| フォルダ読み込み | `POST /api/projects/{id}/load-path` |
| 解析実行 | `POST /api/projects/{id}/run/{phase_index}` |
| 進捗 | `WS /ws/projects/{id}/progress` |
| 結果取得 | `GET /api/projects/{id}/data/{task_name}` / `data-bulk` |
| 画像 | `GET .../image/{page}` / `.../crop/{spread}/{panel}` |

---

## 中間フォーマット MangaImport v1

ブラウザと `manga-editor-server` が合意する唯一の形式。analyzer の中間タスク JSON（7本）はブラウザに一切露出させない。

**座標はすべて 0.0〜1.0 の正規化値、ページ画像基準、左上原点。**
`canvas.width` はウィンドウ依存で環境ごとに変わるため、ピクセル値を持ってはいけない（`js/canvas-manager.js:66-70`）。

```json
{
  "format": "manga-editor-import",
  "version": 1,
  "source": {
    "folder": "C:/manga/ep01",
    "analyzed_at": "2026-08-29T12:00:00+09:00",
    "level": "panel_text"
  },
  "pages": [
    {
      "index": 0,
      "source_file": "001.jpg",
      "width": 2122,
      "height": 3018,
      "panels": [
        {
          "id": "p1_1",
          "reading_order": 1,
          "shape": "normal",
          "is_bleed": false,
          "points": [[0.02,0.01],[0.98,0.01],[0.98,0.33],[0.02,0.33]],
          "crop_url": "/api/imports/{id}/panel/1/1/image",
          "tags": [],
          "characters": []
        }
      ],
      "balloons": [
        {
          "id": "b1_1",
          "panel_id": "p1_1",
          "reading_order": 1,
          "type": "normal",
          "bbox": {"x":0.10,"y":0.05,"w":0.20,"h":0.10},
          "tail": {"x":0.15,"y":0.16},
          "text": "前回といえば…",
          "vertical": true,
          "outside_panel": false,
          "speaker": null,
          "speaker_confidence": null,
          "excluded": false,
          "exclusion_reason": null
        }
      ]
    }
  ],
  "characters": []
}
```

### 設計上の決め事

- **`points` は多角形。** MagiV2 は現状 bbox のみ返すので当面は4頂点だが、斜めコマ対応（analyzer 側 `llm_doc/斜めコマ対応Lora.md`）が入ったときにフォーマットを変えずに済ませる
- **`excluded` のセリフを削除しない。** analyzer は自信の低い OCR 結果を消さず `excluded` + `exclusion_reason` を残す設計になっている。エディタ側もこれを踏襲し、区別して置くかユーザーに選ばせる
- **`text` は必ず OCR の実測値。** analyzer は Vision LLM が返したセリフを採用せず、OCR 実測と Jaccard 類似度で突き合わせてメタ情報のみ LLM 側を採る。幻覚セリフを持ち込まないこの方針をそのまま引き継ぐ
- **`speaker` は上位モードでのみ埋まる。** 既定の「コマ＋セリフ」経路では常に `null`

### 元データとの対応（変換は manga-editor-server 側）

| MangaImport | 由来 |
|---|---|
| `panels[].points` | `panel_detection` の `PanelInfo.bbox`（ページ絶対px）をページ幅高で除算 |
| `panels[].shape` / `is_bleed` | `PanelInfo.shape` (`normal`/`bleed`/`inferred`) / `is_bleed` |
| `panels[].reading_order` | `PanelInfo.panel_number`（コマの読み順は `panel_detection` 内で確定済み） |
| `balloons[].type` | `BubbleInfo.bubble_type` |
| `balloons[].bbox` | `BubbleInfo.bbox` を正規化 |
| `balloons[].text` | `text_ocr.json` の `bubble_texts[bubble_id]` |
| `balloons[].tail` | `bubble → magiv2_text_idx → text_tail_associations → tails[idx].center` |
| `balloons[].speaker` | `speech_attribution.json` の `speaker_char_id`（上位モードのみ） |
| `characters[]` | `character_identification.json` の `clusters[]`（上位モードのみ） |

**`page_side` は使わない。** analyzer は見開き前提で `right`/`left`/`across` を持つが、エディタは単ページ単位で扱う。見開き画像1枚の場合は `manga-editor-server` 側で左右に分割してから MangaImport に載せる。

---

## manga-editor-server（新設）

### 配置

```
server/
  pyproject.toml
  manga_editor_server/
    __init__.py
    app.py                HTTP アプリ（ブラウザ向け。CORS 設定を持つ唯一の場所）
    mcp_entry.py          MCP（stdio）エントリポイント
    analyzer_client.py    manga-analyzer への薄いクライアント
    manga_import.py       analyzer スキーマ → MangaImport v1 変換
    import_jobs.py        非同期ジョブ管理と進捗中継
    local_files.py        ローカルフォルダ列挙
50_start_server.bat
```

**HTTP と MCP は入口が違うだけで、同じ変換ロジックを共有する。** ツールを追加したいときに片方だけ実装が進む状態を作らない。

### HTTP API（ブラウザ向け）

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/api/capabilities` | 疎通確認と能力申告 |
| GET | `/api/folders?path=` | ローカルフォルダ一覧 |
| POST | `/api/imports` | 解析開始。`{folder_path, level}` → `{import_id}` を即時返却 |
| GET | `/api/imports/{id}` | 状態 `{status, progress, current_step}` |
| WS | `/ws/imports/{id}` | 進捗ストリーム（analyzer の WS を中継） |
| GET | `/api/imports/{id}/result` | MangaImport v1 JSON |
| GET | `/api/imports/{id}/page/{n}/image` | ページ原画像（analyzer から中継） |
| GET | `/api/imports/{id}/panel/{p}/{n}/image` | コマ切り出し（analyzer から中継） |

`capabilities` の応答例:

```json
{
  "server": "manga-editor-server",
  "version": "1.0.0",
  "formats": ["manga-editor-import/1"],
  "analyzer": {
    "reachable": true,
    "cuda": true,
    "levels": ["panel", "panel_text"],
    "llm_running": false
  }
}
```

- **`analyzer.reachable: false`** → 取り込み機能は無効。ただしサーバー自体は動いているので、他のサーバー機能は使える
- **`analyzer.cuda: false`** → 同じく無効
- **`levels` は analyzer が実際に回せる経路のみ。** llama-server が動いていなければ `full` を含めない

### CORS とセキュリティ

`Origin: null` を許可するのは**このサーバーだけ**。

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Editor-Token"],
)
```

`Origin: null` の許可は、ユーザーが開いた任意の Web ページからもこのサーバーを叩けることを意味する。緩和策:

- **`127.0.0.1` バインド限定**（`0.0.0.0` にしない）
- **起動時生成のトークンを全 API で要求**。トークンはコンソールに表示し、ユーザーがエディタの設定欄へ貼る（ComfyUI の認証ヘッダと同じ扱い）
- **ローカルファイルの読み取り範囲を、ユーザーが設定した既定フォルダ配下に限定する。** `/api/folders` に任意パスを渡してディスク全体を走査できる状態にしない

### フォルダの指定方法

**ブラウザは仕様上ファイルの絶対パスを取得できない。** `input[webkitdirectory]` でも相対パスしか得られないため、どの手段でもサーバーにフォルダ位置を伝えられない。

→ `GET /api/folders` で**サーバー側がフォルダを列挙し、ブラウザはその一覧から選ぶ**。

---

## エディタ側の実装

### ファイル配置

```
js/import/manga-import-client.js    サーバー疎通・API 呼び出し・JSON 検証
js/import/manga-import-apply.js     MangaImport → Canvas 流し込み
js/import/manga-import-ui.js        取り込みダイアログ・進捗
css/ui/manga-import.css
```

ES Modules ではなくグローバル前提の `<script defer>`。`index.html:2470` 付近に、参照される側が先になる順で追加。**URL に `?v=7.x` を付ける**（Service Worker が `.js` をキャッシュ優先で持つため、上げないと更新が届かない）。

### 取り込みの2経路

1. **サーバー経由**: `manga-editor-server` が起動していれば、フォルダ選択 → 解析 → 取り込みまで一気に行う
2. **JSON ファイル読み込み**: Claude Code や CLI が書き出した MangaImport JSON を `<input type="file">` で読む。**サーバー起動なしで動く**

2 を用意することで、`file://` 主義を崩さずに済む。解析済みデータを他人と受け渡すこともできる。

### 流し込み手順

```
withoutHistory(() => {
  ページごとに:
    loadBookSize(page.width, page.height, false, true)   // 元画像の縦横比を渡す
    btmWaitForPageReady()                                 // 必須
    cw = canvas.getWidth(), ch = canvas.getHeight()

    コマごとに:
      poly = new fabric.Polygon(points.map(p => ({x: p[0]*cw, y: p[1]*ch})),
                                {isPanel: true, strokeUniform: true,
                                 objectCaching: false, ...})
      setText2ImageInitPrompt(poly)
      setPanelValue(poly)
      canvas.add(poly)
      poly.fill = ...        // add の後（object:added が fill を上書きするため）
      poly.selectable = false

    吹き出しごとに:
      createSpeechBubbleFromImport({svg, left, top, width, text, vertical})
});
updateLayerPanel();
saveStateByManual();
```

### 実装上の罠（調査で確認済み）

| 罠 | 対処 |
|---|---|
| `object:added` が `isPanel` の `fill` を `rgba(255,255,255,0.25)` に無条件上書き（`js/fabric/fabric-management.js:311-313`） | `canvas.add()` の**後**に fill を設定 |
| `putImageInFrame()` が内部で `saveStateByManual()` を呼ぶ | `withoutHistory()` で囲む。履歴は全スナップショット方式なので、刻むほど保存ファイルが線形に肥大する |
| `chengeCanvasByGuid()` 直後にオブジェクトが0件 | `btmWaitForPageReady()` で待つ |
| 縦横を独立に正規化するとページのアスペクト比が違うときコマが歪む | `loadBookSize()` に元画像の縦横比を渡してページ自体を合わせる |
| `commonProperties` 未登録のプロパティは保存で消える | 後述の通り登録する |
| `getText('x') \|\| '既定'` は効かない（未定義でもキー文字列が返る） | 既定値のフォールバックに使わない |
| `data-i18n="[title]key"` 記法は使えない | ツールチップは `data-tip` + tippy |

### commonProperties への追加

`js/core/settings.js:77-102` の配列に追加する。ここに列挙しないプロパティは `customToJSON()` の対象外になり、保存時に消える。

```
importSourceFile     元画像のファイル名
importPageIndex      元ページ番号
importPanelId        元コマID
importBalloonId      元吹き出しID
importReadingOrder   読み順
importBubbleType     解析が判定した吹き出し種別
importOcrText        OCR 原文（ユーザーが書き換えても原文を残す）
importSpeakerId      話者 char_id（上位モードのみ）
```

これで保存・再読込後も「どの原稿のどのコマか」が残り、再生成やセリフ差し替えの基準になる。

---

## 吹き出しの再配置

### 方式

**SVG テンプレート方式（`customType: speechBubbleSVG`）を使う。** フリーハンド方式（`speech-bubble-freehand.js`）は座標指定こそできるが、追随に必要な `freehandBubbleGrid` 等が `commonProperties` に未登録で、**保存→再読込で文字の追随が壊れる**ため採用しない。

SVG 方式は本体 SVG Group ＋ `Textbox` ＋ 内接矩形の3点セットで、文字位置は吹き出し内部の最大内接矩形から自動決定される。縦書きは `VerticalTextbox` に切り替わる。

### 種別の対応表

解析が返す `bubble_type` を、既存のテンプレート分類（`js/svg/speechbubble.js` の接頭辞）に写す。

| `bubble_type` | テンプレート接頭辞 | 備考 |
|---|---|---|
| `normal` | `01_normal` | |
| `shout` | `12_!` | 爆発型 |
| `whisper` | `10__silent` | 破線 |
| `monologue` | `20_other` | |
| `narration` | `11_rect` | 角型 |
| `inverted` | `11_rect` | 黒地。塗りを反転 |
| `none` | — | 吹き出しを作らずテキストのみ配置 |

各分類の中のどのテンプレートを使うかは、設定で既定を1つ選べるようにする。

### 引数付き生成関数の新設

既存の `loadSpeechBubbleSVGReadOnly(svgString, name)`（`js/sidebar/speechBubble/speech-bubble-effect.js:164`）は、位置を `placeNewObject()` 任せ、サイズを `canvas.width*0.35` 固定、文字・フォント・色を DOM 直読みで決めており、**戻り値もない**。一括生成には使えない。

既存関数はそのまま残し、引数付きの派生関数を新設する。

```
createSpeechBubbleFromImport({svgString, left, top, width, height,
                              text, vertical, fill}) -> Promise<fabric.Object>
```

内部で `createSpeechBubbleMetrics()`（`speech-bubble-text.js:143`）をそのまま使い、DOM から読んでいた箇所だけを引数に差し替える。既存の呼び出し側は変更しない。

### しっぽの向き

**analyzer はしっぽの座標しか持たない**（`tails: list[BBox]`、角度・方向のフィールドなし）。向きは、しっぽ中心と吹き出し中心の位置関係からエディタ側で8方位に量子化して推定し、その向きを持つテンプレートを選ぶ。

### 吹き出しの読み順

`reading_order.json` は依存宣言に `vision_analysis`（LLM）が入っており、既定の「コマ＋セリフ」経路では得られない可能性がある。

→ **`manga-editor-server` 側で同じロジックを実装する。** 内容は単純:

1. Y 中心の差が「コマ高さ × 0.3」以内の吹き出しを同一行にまとめる
2. 行を上→下にソート
3. 行内を中心 X の降順（右→左）にソート

analyzer が `reading_order` を返した場合はそちらを優先する。

---

## 再生成

取り込み直後の状態は「コマ（Polygon）＋吹き出し＋セリフ」だけで、絵は空。ここから既存の T2I をそのまま回す。

- **コマのプロンプト初期値**: `setText2ImageInitPrompt(poly)` の直後に、解析で得たコマのタグ（`wd_tagging`、上位モードのみ）とキャラの `appearance_prompt` を上書きする
- **生成は必ず既存の TaskQueue 経由**にする。コマ単位で `T2I(layer, spinner)` を呼ぶ既存経路をそのまま使う
- **配置は `putImageInFrame(img, cx, cy, false, false, true, panel)`**（`js/sidebar/panel/panel-manager.js:136`）。第7引数に対象コマを渡せば座標判定を飛ばして確実にそのコマへ入る。AI 生成画像と同じ経路
- **元コマ画像を i2i / 参照画像として使うモードは既定 OFF** の設定項目とする

---

## サーバー起動検知と機能の ON/OFF

### 疎通

1. `SETTINGS_SCHEMA`（`js/project-management.js:291` 付近）に2行追加

```javascript
editorServerUrl:   {id: 'editorServerUrl',   default: 'http://127.0.0.1:8770'},
editorServerToken: {id: 'editorServerToken', default: ''},
```

これだけで保存・復元・自動保存の対象になる。UI は `index.html:2196-2215` の Ollama 行と同型で追加し、`us-tag-local` タグを使用サービス表と接続先表の**両方に手で**付ける。

**analyzer の URL はエディタの設定に持たない。** analyzer は `manga-editor-server` の設定で指定する。ブラウザは analyzer の存在を知らなくてよい。

2. 疎通は既存の `apiHeartbeat()`（`js/ai/ai-management.js:234`、15秒間隔）に相乗りし、`GET /api/capabilities` を叩く
3. 状態バッジは `#ExternalService_Heartbeat_Container`（`index.html:1831`）に追加

**CORS 拒否とサーバー停止はブラウザ上でどちらも `TypeError` になり区別できない。** 既存の `_probeReachable()`（`mode:'no-cors'` で再投擲）で切り分ける実装をそのまま使い、「接続できません」に丸めない。

### 機能の出し分け

判定を1か所に集約する。`isPWAEligible()`（`js/core/service/worker-register.js:1-18`）と同型。

```javascript
function getMangaImportAvailability() {
  // -> {ok: true}
  //  | {ok: false, reason: 'no-server'      , message: ...}
  //  | {ok: false, reason: 'no-token'       , message: ...}
  //  | {ok: false, reason: 'no-analyzer'    , message: ...}
  //  | {ok: false, reason: 'no-cuda'        , message: ...}
  //  | {ok: false, reason: 'format-version' , message: ...}
}
```

UI 側はこの1関数だけを見る。判定条件が増えてもここだけ直せばよい。

**利用できないときはメニューを隠さず、無効化して理由を表示する。** 既存の `{ok:false, message}` を返すパターン（`js/ai/reference/reference-generator.js:31`）に合わせる。黙って別の動作にすること（fallback）はしない。

**JSON ファイル読み込み経路は常に有効。** サーバーが無くても取り込み自体はできる。

### 進捗表示

- **`aiTaskMap` / `createSpinner()` は使わない。** レイヤー GUID 必須で、フォルダ解析には対応しない
- **`js/ui/overlay-progress.js` を使う。** `OP_showLoading()` → `OP_updateLoadingState()` → `OP_hideLoading()`。キャンセルは `OP_isCancelled()` を毎回見る協調方式
- **進捗の取得に `setTimeout` ポーリングを使わない。** 非表示タブで1分間隔まで間引かれる。`WS /ws/imports/{id}` を使う（WebSocket は CORS の対象外で、ComfyUI 相手に `file://` から繋がる実績がある）
- Toast は完了・失敗時のみ（同一内容を `×N` にまとめる仕様のため進捗に向かない）

---

## Claude Code 連携

`manga-editor-server` の MCP エントリポイントを **stdio トランスポート**で公開し、`.mcp.json` を本リポジトリにコミットする。

```json
{
  "mcpServers": {
    "manga-editor": {
      "command": "python",
      "args": ["-m", "manga_editor_server.mcp_entry"],
      "env": {
        "MANGA_ANALYZER_URL": "${MANGA_ANALYZER_URL:-http://127.0.0.1:8765}"
      }
    }
  }
}
```

**HTTP ではなく stdio を選ぶ理由**: ポートも認証も要らず、Claude Code がプロセスの起動と終了を管理する。**HTTP サーバーが起動していなくても Claude Code から使える。** 変換ロジックは `app.py` と共有する。

### ツール

**戻り値は軽量メタデータのみ。** MCP の出力には既定で約26,000トークンの上限があり、解析結果をそのまま返す設計は破綻する。

| ツール | 戻り値 |
|---|---|
| `list_source_folders(path?)` | フォルダ名の配列 |
| `start_import(folder_path, level)` | `{import_id}` を即時返却 |
| `get_import_status(import_id)` | `{status, progress, current_step}` |
| `get_import_summary(import_id)` | ページ数・コマ数・セリフ数・キャラ数のみ |
| `get_page_analysis(import_id, page)` | **1ページ分だけ**のコマ・セリフ |
| `export_editor_json(import_id, out_path)` | ファイルに書き出し、**パスを返す** |

- **長時間処理は分割必須。** MCP ツールの既定タイムアウトは30秒。「開始 → ID返却 → 状態問い合わせ」に分ける
- **画像は base64 で返さない。** ファイルパスを返す

### Claude Code からブラウザ側は触れない

`file://` のページは Chrome 拡張から一切操作できない。Claude Code とエディタの連携は**ファイル経由の間接連携のみ**とする。`export_editor_json` が書き出した MangaImport JSON を、エディタが `<input type="file">` で読む。

---

## 段階

| Phase | 内容 | 依存 |
|---|---|---|
| 1 | MangaImport v1 スキーマ確定 / `manga-editor-server` の骨格（capabilities・folders・CORS・トークン） | — |
| 2 | analyzer 中継と MangaImport 変換 / ブラウザ側の疎通・設定・状態バッジ / JSON ファイル読み込み経路 / コマ流し込み | 1 |
| 3 | 引数付き吹き出し生成関数 / 種別対応表 / 縦書き・テキスト流し込み | 2 |
| 4 | 再生成（プロンプト初期値、TaskQueue 経由の一括生成） | 3 ＋ **土台A: Queue の永続化** |
| 5 | MCP エントリポイントと `.mcp.json` | 1 |

Phase 2 まででコマ割りの取り込みが完成し、単体で価値が出る。

---

## 該当箇所

### 削除

- `99_server.py`、`99_server.bat`

### 新規

- `server/`（`manga_editor_server` パッケージ、`pyproject.toml`）
- `50_start_server.bat`
- `js/import/manga-import-client.js`、`manga-import-apply.js`、`manga-import-ui.js`
- `css/ui/manga-import.css`
- `.mcp.json`
- `llm_doc/manga-import.md`（形式仕様とサーバー責務の境界）

### 修正

| ファイル | 内容 |
|---|---|
| `js/core/settings.js:77-102` | `commonProperties` に `import*` を8件追加 |
| `js/project-management.js:291` 付近 | `SETTINGS_SCHEMA` に URL・トークンを追加 |
| `js/ai/ai-management.js:234` | `apiHeartbeat()` に `manga-editor-server` を追加 |
| `js/sidebar/speechBubble/speech-bubble-effect.js` | `createSpeechBubbleFromImport()` を新設（既存関数は変更しない） |
| `index.html` | 設定行、状態バッジ、`<script>` 追加（`?v=` 更新） |
| `js/ui/third/base-translation/base-*.js` | 8言語ぶんの文言 |
| `service-worker.js:2` | `CACHE_VERSION` 更新 |
| `.gitignore` | `server/.venv` |

### manga-analyzer（別リポジトリ）

**変更なし。**

---

## 未確認・リスク

| 項目 | 内容 | 対処 |
|---|---|---|
| **モデルのライセンス** | MagiV2 / YOLOv8（ultralytics は AGPL-3.0）等の利用条件が analyzer 側に一切記載されておらず、検証された形跡がない | 本リポジトリにモデルを同梱しない構成にすることで影響を切り離す。analyzer 側で別途確認が必要 |
| **`reading_order` の依存** | 依存宣言に `vision_analysis`（LLM）が入っており、軽量経路で得られるか未確認 | `manga-editor-server` 側に同じロジックを実装する前提で設計。analyzer が返せば優先 |
| **VRAM 下限** | 「コマ＋セリフ」経路の最低 VRAM が記載されていない | `capabilities` で `cuda` は判定できるが容量は判定できない。実測が必要 |
| **見開き画像の分割** | analyzer は見開き前提の `page_side` を持つが、単ページ入力との切り分けが未確認 | Phase 1 で確認し、必要なら `manga-editor-server` 側で分割する |
| **MCP SDK の API 詳細** | 調査で得たコード例の裏取りが不十分 | Phase 5 の実装時に公式 SDK で確認 |
| **`Origin: null` 許可の影響範囲** | 任意の Web ページからローカルサーバーを叩けるようになる | `127.0.0.1` バインド限定 + トークン必須 + 読み取り範囲の限定 |
| **Python 環境が2つ** | インストール手順が増える | `manga-editor-server` は torch を要求しない軽量構成にする |

---

## 関連

- `llm_doc/layer-structure.md` — GUID 連携、リンク機構
- `llm_doc/history-and-data.md` — 履歴スタック、data:URL 制約
- `llm_doc/ai-system.md` — 疎通監視、プロバイダ構成
- `llm_doc/ai-verification.md` — `file://` の実測表
- `llm_doc/chrome.md` — オリジンの分離
- `roadmap/030_storyboard_mode.md` — ネーム機能との関係（要検討）

---
---

# 付録: 調査結果（2026-08-29 実施）

設計の根拠であり、実装時の一次資料。

**この調査でやったこと**: 両リポジトリのコードとログを読んだ。
**やっていないこと**: 解析パイプラインを自分で実行していない。処理時間は既存の実行ログの記録であり、当方の実測ではない。
確認済みの事実と推測を区別して記載する。未確認は未確認と書く。

---

## A. manga-analyzer（`C:\01_work\00_Git\manga-scenario-builder`）

### A-1. 構成

| 項目 | 内容 |
|---|---|
| 言語 | Python 3.11+（`src/manga_analyzer/`、141ファイル）+ TypeScript（`frontend/`、Vanilla + esbuild） |
| 実行形態 | CLI（`manga-analyzer`、click）と FastAPI サーバー（`manga-analyzer gui`、ポート8765） |
| ビルド | hatchling。`requirements.txt` / ルート `package.json` は無く、依存は `pyproject.toml` の optional-dependencies |
| 起動 | `20_start_server.bat` → `src/manga_analyzer/gui.py` |

依存グループ:

- 基本: `pillow`, `numpy`, `pydantic>=2`, `click`, `natsort`, `rich`
- `gpu`: `torch`, `manga-ocr>=0.1.8`, `opencv-python`, `ultralytics`, `transformers>=5.3,<6.0`, `scikit-learn`, `timm`, `dghs-imgutils>=0.8`, `onnxruntime-gpu`
- `gui`: `fastapi`, `uvicorn[standard]`
- `generation` / `finetune`: `peft`, `outlines`, `unsloth`, `trl`, `datasets`

パイプラインはタスク単位（`src/manga_analyzer/tasks/`、40ファイル）。各タスクが `BaseTask` を継承し、前タスクの JSON を読んで自タスクの JSON を
`_data/output/{project}/{work_id}/{episode}/intermediate/{task}.json` へ保存する冪等設計。

### A-2. コマ検出（`panel_detection`）

**MagiV2 単独。OpenCV の二値化・輪郭抽出・ハフ変換はコマ検出には使っていない**（吹き出し種別判定にのみ使用）。

- モデル: `ragavsachdeva/magiv2`（`model_registry.py:DEFAULT_MAGIV2_MODEL`）
- ローダ: `tasks/magiv2_model_loader.py` の `_get_magiv2_model()`。`AutoModel.from_pretrained(..., trust_remote_code=True)`。transformers 5.x では `compat/transformers_shim.py` の `load_magiv2_for_transformers_v5()` に切替（重みキーリネーム + TimmBackboneConfig 注入）
- 推論: `tasks/panel_local_inference.py:_detect_panels_in_image()` が `model.predict_detections_and_associations([img_array])` を1ページずつ呼ぶ
- 前処理: EXIF 補正 → `convert("L").convert("RGB")`（グレースケール化してから RGB）
- **CUDA 必須。** `BaseTask._require_cuda()`（`base_task.py:308`）が CPU 実行を明示的に禁止。OOM 時は `empty_cache` + `gc.collect` して1回だけリトライ

MagiV2 の戻り8フィールド: `panels`, `texts`, `characters`, `tails`, `text_character_associations`, `text_tail_associations`, `character_cluster_labels`, `is_essential_text`

**後処理（自前ロジック）** — `tasks/panel_bbox_conversion.py`

- `raw_bboxes_to_bbox_list()`: xyxy → 画像内クリップ → `BBox(x, y, width, height)`
- `convert_raw_panels_to_panel_infos()`: **ページ面積の2%未満のコマ候補を除外**。端から5px 以内に接していれば `is_bleed=True` / `shape="bleed"`
- `determine_page_side()`: 見開き1枚画像のとき、幅が画像幅の60%超なら `across`、それ以外は中心 X で `right`/`left`

**検出漏れ補完** — `tasks/panel_grid_inference.py`

- `_generate_grid_candidates()`: 検出済みコマの辺の X/Y で仮想グリッドを作り、どのコマにも覆われていないセルを列方向に連結して矩形化
- `_filter_grid_candidates()`: **面積がページの10%以上、幅・高さがそれぞれ画像の7%以上**の矩形だけを `is_inferred=True` / `shape="inferred"` として追加

**コマの読み順は `panel_detection` の中で確定**し、`PanelInfo.panel_number` に入る（行分割 → 行は上から下、行内は右から左。縦連続の補正あり）。

### A-3. 吹き出し検出（`bubble_detection`）

`tasks/bubble_detection.py`（678行）

- **YOLOv8m**: `ogkalu/comic-speech-bubble-detector-yolov8m` の `comic-speech-bubble-detector.pt`（ultralytics `YOLO`）。`imgsz=1024`、既定 `conf=0.3` / `iou=0.5`
- クラスは2つ: `{0: "text_bubble", 1: "text_free"}`
- `_assign_to_panel()`: 吹き出しの**中心点が入るコマ**のうち重なり面積が最大のものへ割り当て。どのコマにも入らない `text_free` は `OutsidePanelText` へ回す

**吹き出し種別 `BubbleType`**（`models/enums.py`）: `normal` / `shout` / `whisper` / `monologue` / `narration` / `inverted` / `none`

判定は `_classify_bubble_type(page_img, bbox)`（staticmethod）で、**OpenCV の形状特徴のみ**で決める。

1. 枠付近の平均輝度が 80 未満 → `inverted`（黒地白文字）
2. Otsu 二値化 → `RETR_EXTERNAL` で最大輪郭
3. circularity(4πA/P²)・rectangularity(A/外接矩形)・convexity(A/凸包)・凸包欠陥数・whisper スコアを算出
4. 凸包欠陥6個以上 かつ convexity が 0.85 未満 → `shout` / whisper スコアが 0.35 超 → `whisper` / rectangularity が 0.88 超 かつ convexity が 0.95 超 → `narration` / rectangularity 0.65〜0.88 かつ convexity 0.92 超 かつ circularity 0.85 未満 → `monologue` / それ以外 `normal`

whisper スコアは輪郭上を約80点サンプリングし「明暗切替回数×0.6 + 明部割合×0.4」で破線らしさを測る。

**しっぽ（tail）**

- MagiV2 が `tails: list[BBox]` を返し、`MagiV2PageDetection` に**ページ絶対座標の bbox として保存**（`models/magiv2.py`）
- 対応は `text_tail_associations: list[(text_idx, tail_idx)]`。吹き出し側は `magiv2_text_idx`（IoU 0.3以上でマッチ）を持つので
  `bubble → magiv2_text_idx → text_tail_associations → tails[idx]` で辿れる
- **角度・方向のフィールドは無い。** `speech_attribution.py:_find_tail_center` が `tails[tail_idx].center` を返し、そこから各顔の中心までのユークリッド距離が最小の人物を話者にしている

### A-4. OCR（`text_ocr`）

- **manga-ocr**（`from manga_ocr import MangaOcr`）。モデル ID `jzhang533/manga-ocr-base-2025`（`model_registry.py:DEFAULT_OCR_MODEL`）
- **縦書きは manga-ocr 自体が対応**。アプリ側に縦書き専用処理（回転・行分割等）は一切無い。`img.crop(bbox)` して渡すだけ
- 後処理: 全角から半角への変換、1文字のみ・約物のみはノイズとして破棄
- 除外フィルタ `_apply_exclusion_filters()`: 検出信頼度が `ocr_confidence_threshold`(既定0.5) 未満 / 英数字を含む / 2文字以下 のいずれかで
  `excluded=true` と `exclusion_reason` を付与。**削除はせず理由を残す**

**セリフとメタ情報の採り分け**（`vision_analysis.py:_parse_result`）

OCR 結果は `bubble_texts: {bubble_id: str}` として吹き出し ID に直結する。さらに Vision LLM が返した `dialogues` と OCR 実測テキストを
**文字集合の Jaccard 類似度0.3以上**でマッチさせ、**テキストは OCR 側・メタ情報（話者仮 ID、吹き出し種別、文字サイズ演出）は LLM 側**を採用する。
LLM の幻覚セリフを採らないための設計。

### A-5. 人物・話者

**手法**

1. 顔検出: YOLOv8 `Fuyucchi/yolov8_animeface` / `yolov8x6_animeface.pt`。**切り出し済みコマ画像**に対して実行（既定 conf=0.3、iou=0.5）
2. 埋め込み: CCIP `ccip-caformer-24-randaug-pruned`（deepghs、ONNX、`dghs-imgutils` 経由）
3. クラスタリング → `char_001`, `char_002` … を自動採番

**`character_identification.json`** — トップレベル3キー: `clusters` / `faces` / `face_crop_paths`

- `faces[]`: `face_id`, `panel_number`, `spread_number`, `x`, `y`, `width`, `height`, `embedding`, `magiv2_cluster_label`
  - **`x`/`y` はコマ相対座標**（ページ座標ではない）。ページ座標にするには `panel.bbox` を足す
  - `embedding` は base64 float16 文字列
- `clusters[]`: `char_id`, `character_name`, `face_ids`, `representative_face_id`, `appearance_prompt`
- `face_crop_paths`: `{char_id: [顔切り出し画像のパス, …]}`
- `character_name` は Vision LLM が推定するが、**実サンプルでは4クラスタ全て `null`**

**`speech_attribution.json`** — **ルートがリスト**（トップレベルキー無し）

```json
[{"bubble_id": 1, "panel_number": 1, "speaker_char_id": "char_002",
  "attribution_source": "sole_character", "confidence": 1.0}]
```

- **話者の紐付けは吹き出し ID（`bubble_id`）単位**で全件出る（実サンプル337件）
- `attribution_source`: `sole_character`(1.0) / `tail`(0.95) / `magiv2`(0.9) / `spatial`(0.8〜0.2) / `magiv2_sole_character`(0.75) / `magiv2_tail`(0.7) / `magiv2_spatial`(0.6〜0.15)

### A-6. 吹き出しの読み順（`reading_order`）

**`reading_order.json`** — トップレベルキーは **panel_key の文字列**（`spread_number * 1000 + panel_number`、例 `"3002"` は見開き3のコマ2）

```json
{"3002": {"panel_number": 2, "page_number": 4,
          "bubble_order": [{"bubble_id": 12, "reading_sequence": 1},
                           {"bubble_id": 15, "reading_sequence": 2}]}}
```

読み順は `bubble_order[].reading_sequence`（コマ内1始まり）。

ロジック:

1. Y 中心の差が「コマ高さ × 0.3」以内の吹き出しを同一行にグルーピング
2. 行を上から下にソート
3. 行内を中心 X の降順（右から左）にソート
4. `is_outside_panel=true` の吹き出しは対象外

### A-7. 出力 JSON スキーマ（実物）

**`panel_detection`** — `models/panel.py:PanelInfo`。座標は**ページ画像のピクセル絶対座標**（左上原点、整数）。正規化されない。

```json
{"panel_number": 1, "bbox": {"x": 4, "y": 0, "width": 2122, "height": 3018},
 "page_number": 1, "spread_number": 1, "shape": "bleed", "page_side": "right",
 "is_bleed": true, "is_cross_spread": false, "is_inferred": false,
 "reading_order_confident": true, "row_index": 0, "corrected_reading_order": null}
```

**`bubble_detection.json`** — トップレベル2キー `{"bubbles": [...], "outside_texts": [...]}`

```json
{"bubble_id": 1, "bbox": {"x": 191, "y": 2502, "width": 1534, "height": 475},
 "bubble_type": "normal", "detection_source": "yolo_bubble", "page_number": 2,
 "panel_number": 1, "spread_number": 2, "position_in_panel": "bottom",
 "confidence": 0.6016, "excluded": false, "exclusion_reason": null,
 "is_connected": false, "is_outside_panel": false, "magiv2_text_idx": 3}
```

- `detection_source`: `yolo_bubble`（クラス0）/ `yolo_free`（クラス1だがコマ内に入ったもの）
- `position_in_panel`: `top`/`bottom`/`left`/`right`/`center`（左右は `page_side` で反転）
- `is_connected`: 同一コマ内で矩形間距離が最小辺の30%未満の吹き出しがあれば true

`outside_texts[]`（`OutsidePanelText`）:

```json
{"text": null, "text_type": null, "detection_source": "yolo_free",
 "excluded": false, "exclusion_reason": null, "position": "right_margin",
 "bbox": {"x": 1574, "y": 1277, "width": 527, "height": 456}, "page_number": 4}
```

`position`: `top`/`bottom`/`left_margin`/`right_margin`/`between_panels`（`BBox.position_on_page()`）

**`text_ocr.json`** — トップレベル3キー

```json
{"bubble_texts": {"1": "前回といえば…", "2": "…"},
 "bubbles": [BubbleInfo の配列（excluded と exclusion_reason が更新済み）],
 "outside_texts": [text が埋まった OutsidePanelText]}
```

**`text_classification.json`** — 同じ3キー。差分は `outside_texts[].text_type` と `excluded` / `exclusion_reason` が確定すること。
`OutsidePanelTextType`: `narration` / `monologue` / `pillar`（柱テキスト）/ `noise` / `nonsense`。
柱テキストのみ位置ベースで先に確定し、残りを GPU 上の `Qwen/Qwen3.5-2B` が分類する。

**`final_aggregation.json`** — `output_path` の1キーのみ。実体は別ファイル `output.json`。そのトップレベルキー:

```
total_pages, total_spreads, spreads, scenes, characters,
emotion_curve, tempo_curve, opening_structure, ending_structure,
big_spread_panels, synopsis, narrative_structure, art_style,
version_info, scenario_char_id_map
```

`output.json` の中だけ、`PanelPlacement` として**見開き全体を 0〜1000 に正規化**した座標に変換される
（`aggregation_spread_builder.py:_build_spread_analyses`、`_COORDINATE_NORMALIZE_RANGE = 1000`）。
右ページの X に左ページ幅を足して1枚の見開き平面へ写像している。

```json
{"panel_number": 1, "x": 557, "y": 30, "w": 354, "h": 177, "shape": "normal", "page_side": "right"}
```

**本計画では `output.json` を使わない。** 見開き前提の正規化はエディタの単ページ運用と合わないため、
中間タスクのピクセル座標を `manga-editor-server` 側でページ基準 0.0〜1.0 に変換する。

### A-8. モデルと処理時間

**モデルは同梱ゼロ、全て実行時に `hf_hub_download` で自動ダウンロード。**

| 経路 | 合計サイズ概算 |
|---|---|
| コマ検出のみ | 約3.9GB（MagiV2） |
| コマ＋吹き出し＋OCR | 約4.1GB（＋ YOLOv8 50MB ＋ manga-ocr 116MB） |
| フル解析 | ＋ 約8GB（WD Tagger 1.2GB、CCIP 144MB、顔 YOLO 187MB、GGUF 6.5GB） |

**処理時間**（README・llm_doc に記載無し。`_data/log/manga-analyzer.log.2026-04-06` の PERF 出力の記録。当方の実測ではない）

| 処理 | 1ページあたり |
|---|---|
| MagiV2（コマ検出） | 約1.3秒（45ページ61秒）＋ モデルロード11秒 |
| YOLOv8 吹き出し | 約0.12秒 ＋ ロード0.4秒 |
| manga-ocr | 約1.3秒（吹き出し数に比例）＋ ロード3.2秒 |
| Vision LLM（9B） | 1コマ2〜7秒 → 約13秒/ページ |

45ページ・162コマで、フル解析 約28分 / コマ＋吹き出し＋OCR のみ 約2.5分。

**VRAM**: `llm_doc/知見.md` に「RTX 3090 (24GB) で llama-server 27B Q4_K_M（約19GB）と Worker Server を同居」との記載があり、
**フル解析は24GB以上**が前提。コマ＋吹き出し＋OCR のみの下限値は記載が無く**未確認**。

### A-9. タスク依存と最小経路

```
コマ検出だけ         : image_import → panel_detection
コマ＋吹き出し＋OCR  : image_import → panel_detection → bubble_detection → text_ocr
```

- **どちらも GPU 上の LLM・llama-server の起動は不要。**
- コマ画像ファイルが要るなら `panel_crop` を足す（画像保存のみ、モデル不要）
- `bubble_detection` が要求するのは `pages` / `panels` / `magiv2_detections` のみ。`panel_crop` も `wd_tagging` も不要
- **LLM が必要になる境界は `text_classification` から**（コマ外テキストの種別判定に Qwen3.5-2B）。吹き出しの OCR テキストには不要なので上記2構成では外せる
- `vision_analysis` 以降（`reading_order`, `spread_analysis`, `character_identification`, `speech_attribution`, `scene_segmentation`, `final_aggregation`）は全て llama-server 必須

### A-10. 使える HTTP API（既存・追加不要）

| 用途 | エンドポイント |
|---|---|
| 起動確認 | `GET /health` |
| フォルダ読み込み | `POST /api/projects/{id}/load-path` |
| フォルダ一覧・選択 | `GET /api/projects/{id}/folders` / `POST .../select-folder` |
| 解析実行 | `POST /api/projects/{id}/run/{phase_index}` |
| 中止 | `POST /api/projects/{id}/cancel` |
| 進捗 | `WS /ws/projects/{id}/progress` |
| 結果取得 | `GET /api/projects/{id}/data/{task_name}` / `data-bulk` / `data-batch` |
| 画像 | `GET .../image/{page}` / `.../crop/{spread}/{panel}` / `.../face/{char_id}` |
| 状態 | `GET /api/projects/{id}/status` / `error-log` / `interrupted-tasks` |
| スキーマ自己記述 | `GET /api/schemas` / `GET /api/schema/{model_name}` |

**`gui.py:136` には GZipMiddleware しか無く、`CORSMiddleware` が無い。**
本計画ではブラウザが 8765 を直接叩かないため、この点は問題にならない。

---

## B. manga-editor-desu

### B-1. コマ（パネル）

コマの実体は **`fabric.Polygon` ＋ `isPanel:true`**。判定は `isPanel(obj)`（`js/core/util/fabric-util.js:13`、`obj.isPanel` を見るだけ）。

SVG ひな形の読み込みでも `path` 要素は頂点を抽出して `fabric.Polygon` に作り直している（`js/sidebar/panel/panel-manager.js:505`）。
`path` 以外（rect 等）はそのまま `isPanel=true` を付けて追加（同 `:530-546`）。
ただし `isPointInShape()`（`fabric-util.js:87`）は polygon 以外では外接矩形にフォールバックするため、**流し込みでは必ず Polygon で作る**。

| 関数 | 場所 | 適性 |
|---|---|---|
| `addShape(points, options)` | `js/sidebar/panel/panel-template.js:150` | 内部で `scale = min(canvasW/3/shapeW, canvasH/3/shapeH)` を強制（`:161-163`）。任意サイズは作れない |
| `addSquareBySize(width, height)` | `panel-template.js:50` | ページ全面1コマ専用。ただし**手順はこれを踏襲するのが最短**（`:76-103`） |
| `loadSVGPlusReset(svgString, isLand)` | `panel-manager.js:441` | SVG 文字列を作れば任意レイアウトを一括投入可能 |
| `blindSplitPanel(panel, isVertical)` | `js/sidebar/panel/knife/knife-split-engine.js:12` | 分割位置はランダム |
| `splitPolygon(polygon)` | `knife-split-engine.js:114` | グローバル `currentKnifeLine` を直線として jsts で分割 |

**既存テンプレート**: データ `js/svg/manga-panels-image-vertical.js`（`MangaPanelsImage_Vertical`）と `manga-panels-image-landscape.js`（`{name, svg}` の配列）。
描画は `populateVerticalPanels()` / `populateLandscapePanels()`（`js/sidebar/speechBubble/speech-bubble-effect.js:225, :261`）。
ランダム生成は `rundomPanelCut()`（`js/panel/random-cut.js:1`）、複数ページ一括は `generateMultipage()`（同 `:67`）。

**罠**: `js/fabric/fabric-management.js:311-313` の `object:added` ハンドラが、
**`isPanel` のオブジェクトの `fill` を `rgba(255,255,255,0.25)` に無条件で上書きする。**

### B-2. コマへの画像の入れ方

**clipPath 方式**。マスク画像でも別レイヤーでもない。

- `moveSettings(img, poly)`（`js/fabric/fabric-management.js:173`）が中核。`updateClipPath()`（`:230`）がコマの頂点を
  `calcTransformMatrix()` で絶対座標に変換し、`absolutePositioned:true` の `fabric.Polygon` を `img.clipPath` に代入。
  コマが `path` 型のときは `updatePathClipPath()`（`:268`）
- 双方向リンク: `img.relatedPoly = poly` と `parent.guids[]`（`setGUID()`, `fabric-util.js:282`）
- `moving/scaling/rotating/skewing/modified` の各イベントに再計算ハンドラを張る

**入口**:

```
putImageInFrame(imgOrSvg, x, y, isNotActive, notReplace, isFit, targetLayer)
```
`js/sidebar/panel/panel-manager.js:136`（実体は内部関数 `placeObject`、`:149`）

- **`targetLayer` に fabric オブジェクトを渡すと座標判定を飛ばして確実にそのコマへ入る。** 渡さない場合は `findTargetFrame(x,y)`（`:219`）で最前面から形状判定
- `isFit=true` のとき、コマ中心に合わせて `scaleToFit = Math.max(横比,縦比) * 1.05` でコマを覆う
- 名前は「対象コマ名 ＋ In Image」が自動で付く
- **内部で `saveStateByManual()` まで呼ぶ。** 一括投入時は `withoutHistory()` で囲む必要がある

**AI 生成画像が置かれるまで**: `T2I(layer, spinner)`（`js/ai/ai-management.js:132`）→ プロバイダ → 完了コールバックで
`calculateCenter(layer)`（`js/layer/layer-management.js:481`）→ `putImageInFrame(result, cx, cy, false, false, true, layer)`
（`js/ai/comfyui/comfyui-management.js:378-380`、`js/ai/provider/cloud-image-provider.js:86-92`、`js/ai/sdwebui/sdwebui-single-call-api.js:29`）

**リンクの追随は2イベントのみ**。`panel-manager.js` の DOMContentLoaded 内で
`object:modified` → `relinkToPanelUnderObject(obj)`（`:276`）、`object:removed` → `releasePanelChildren(panel)`（`:334`）に集約。
個別の配置処理でリンクを張り直す必要は無い。

### B-3. 吹き出し（2系統）

**(a) SVG テンプレート方式 ← 採用**

- 生成: `loadSpeechBubbleSVGReadOnly(svgString, name)` — `js/sidebar/speechBubble/speech-bubble-effect.js:164`
- データ: `SpeechBubble` 配列（`js/svg/speechbubble.js`、`{name, svg}`）。接頭辞で分類 — `01_normal` / `10__silent` / `11_rect` / `12_!` / `20_other` / `90_focus`
- **テキストは内包ではなく別オブジェクト3点セット** — `createSpeechBubbleMetrics(svgObj, svgData)`（`js/sidebar/speechBubble/speech-bubble-text.js:143`）

| オブジェクト | 型 | customType | 備考 |
|---|---|---|---|
| 本体 | SVG Group | `speechBubbleSVG` | `guids:[textGuid, rectGuid]` を持つ親 |
| 文字 | `fabric.Textbox` または `VerticalTextbox` | `speechBubbleText` | `targetObject` で本体を逆参照 |
| 内接矩形 | `fabric.Rect` | `speechBubbleRect` | `excludeFromLayerPanel:true`, `evented:false` |

- 文字位置は `parseSvg()`（`speech-bubble-text.js:7`）で SVG をグリッド化し、`findLargestRectangle()` で**吹き出し内部の最大内接矩形**を求めて決定
- 位置追随は `updateObjectPositions(svgObject, immediate)`（同 `:302`）
- **縦書き**: `getSelectedValueByGroup("sbTextGroup")` が `"Horizontal"` 以外なら縦書き。`VerticalTextbox`（`js/sidebar/text/vertical-text.js`）を使い、
  `width` ではなく `height` に内接矩形サイズを渡す（`speech-bubble-text.js:209-232` 縦、`:243-268` 横）
- **引数化されていない**: 位置は `placeNewObject(obj)`（`js/sidebar/text/text-effect.js:258`）任せ、サイズは `svgObject.scaleToWidth(canvas.width*0.35)` 固定（`speech-bubble-effect.js:178`）、
  文字・フォント・色は DOM 直読み（`fontSelector`, `fontSizeSlider`, `fontStrokeWidthSlider`, `textColorPicker`, `textOutlineColorPicker`, `sbTextGroup`）
- **しっぽは SVG の形に埋め込み済み。向き・長さのパラメータは存在しない**
- **一括生成は不可**: `fabric.loadSVGFromString` のコールバック内で完結し**戻り値も無い**

**(b) フリーハンド方式 ← 不採用**

- 生成: `createSpeechBubble(geometry)` — `js/sidebar/speechBubble/speech-bubble-freehand.js:86`。jsts の Geometry を渡すと
  `fabric.Path`（`isSpeechBubble:true`, `jstsGeom` 保持）を生成。Geometry は `createJSTSPolygon(points)`（同 `:199`）で任意点列から作れる
- テキストは `createFreehandBubbleMetrics(bubble)`（同 `:612`）が別 Rect と別 Textbox で付ける
- **不採用の理由**: `freehandBubbleGrid` / `freehandBubbleScale` / `freehandBubbleRect*` / `freehandBubbleOffset*` が
  **`commonProperties` に含まれていない**（grep で不在を確認済み）。保存して再読込すると失われ、文字の追随が壊れる。
  (a) の `speechBubble*` は全て登録済み

**補足**: `llm_doc/balloon-geometry.md` はチェックリストのみの文書で、スーパー楕円・オフセット多角形・周期ノイズの**実装はコードに存在しない**
（`superellipse` 等で全文検索して該当なし）。

### B-4. レイヤーパネル整合と GUID

**`canvas.add()` は禁止ではない。** 全経路が使っている。むしろ通さないと `object:added` ハンドラ群が動かない。

| 場所 | 処理 |
|---|---|
| `js/fabric/fabric-management.js:29-37` | `saveInitialState(obj)` — 再フィット用 `initial` を自動付与 |
| 同 `:112` | 履歴コミット予約（`saveStateByListener`） |
| 同 `:145` | レイヤーハイライト |
| 同 `:301-313` | 空ページ案内文の削除、`isPanel` の `fill` 強制上書き |

呼ぶべき順:

1. `canvas.add(obj)`
2. `updateLayerPanel()` — `js/layer/layer-management.js:129`（60ms デバウンス。一括投入なら最後に1回で十分）
3. 親子を作るなら `setGUID(parent, child)` — `js/core/util/fabric-util.js:282`
4. コマに入れるなら `moveSettings(child, panel)` — `js/fabric/fabric-management.js:173`（`putImageInFrame` を使えば3と4をまとめて実行）

**GUID 採番**: `getGUID(obj)` — `fabric-util.js:314`。未採番なら `generateGUID()`（`:328`）で発行して `obj.guid` に格納。
自前で UUID を生成せず、必ずこれを通す。

**永続化されるのは `guid` と `guids` だけ。** 復元後の親子リンク再構築は `resetEventHandlers()`（`js/layer/image-history-management.js:561`）が
`obj.guids` を辿って `moveSettings()` をやり直す。`relatedPoly` や `clipPath` を直接 JSON に書いても復元されない。

### B-5. 保存・読込フォーマット

形式は `.lz4`（複数ページは blob 連結）。`.zip` も読込のみ対応。

アーカイブ内容（`js/core/compression/project-compression.js:1-38`）:

| ファイル | 内容 |
|---|---|
| `state_000000.json` … | **履歴スタック全件**（差分ではなく全スナップショット） |
| `<sha256>.img` | 画像の data:URL 文字列（本体） |
| `canvas_info.json` | `{width, height, pageWidthMm, pageHeightMm}` |
| `text2img_basePrompt.json` / `fonts.json` / `reference_sheets.json` / `preview-image.jpeg` | |

画像は data:URL のまま持たず、`customToJSON()`（`js/layer/image-history-management.js:304`）が `obj.src` を SHA256 に置換して `.img` へ分離し、
読込時に `restoreImage()`（同 `:336`）が戻す。

**外部 JSON のインポート経路は存在しない。** 読込は `.zip` と `.lz4` のみ（`js/project-management.js:73-170`）。
ただし `askProjectLoadMode()`（`:179`、置換と追加の選択ダイアログ）と `clearAllProjectPages()`（`:171`）は流用可能。

### B-6. 複数ページ

ページは `canvasGuid` 単位の独立プロジェクト blob。実体は `btmProjectsMap`（`js/ui/bottom-bar.js:2`、**挿入順がページ順**）。

| 用途 | 関数 |
|---|---|
| 追加・作り直し（**唯一の入口**） | `loadBookSize(width, height, addPanel, newPage)` — `js/sidebar/panel/panel-template.js:8` |
| 切替 | `chengeCanvasByGuid(guid)` — `js/ui/bottom-bar.js:508`（スペル原文ママ） |
| 完了待ち（**必須**） | `btmWaitForPageReady(timeoutMs)` — 同 `:102`。待たないとオブジェクト0件になる |
| 前後移動 | `btmNavigatePage(direction)` — 同 `:129` |
| 保存・登録 | `btmSaveCurrentPage(openDrawer)` — 同 `:78` / `btmRegisterCurrentPage(openDrawer)` — 同 `:93` |
| 一覧 | `btmGetGuids()` / `btmGetGuidIndex()` / `btmGetGuidsSize()` / `btmGetGuidByIndex()` — 同 `:526-547` |
| **全ページ走査（流用推奨）** | `storyForEachPage(loading, stepText, onPage)` — `js/ai/prompt/prompt-apply.js:94`。`onPage(index,total,guid)` が true を返したページだけ保存し、終了後に開始ページへ戻る |

### B-7. 履歴

`withoutHistory` の定義: `js/layer/image-history-management.js:111`

```javascript
function withoutHistory(fn)   // fn() の戻り値をそのまま返す
```

内部は `changeDoNotSaveHistory()`（`:96`、`historyLockDepth++`）→ `try{fn()}finally{changeDoSaveHistory()}`（`:100`）。**カウンタ方式でネスト可能**。

定石は `withoutHistory(...)` で大量の add / remove を囲み、終了後に `commitHistory()`（`:162`）または `saveStateByManual()`（`:260`）を1回。

既存のバッチ処理例:

- ナイフ分割 `js/sidebar/panel/knife/knife-split-engine.js:335-370`（分割一式で履歴1つ）
- ランダムカット `js/panel/random-cut.js:17-40`
- SVG ひな形読込 `js/sidebar/panel/panel-manager.js:443, 563-566`
- コマ一括変更 `js/sidebar/panel/panel-manager.js:786-826`

**注意**: カスタム属性への直接代入は `set()` を通らず自動コミットされないため `saveStateByManual(); flushHistory();` を明示
（`js/ai/prompt/prompt-apply.js:123-125`）。履歴は全スナップショット方式なので、刻むほどファイルが線形に肥大する。

### B-8. キャンバスサイズと座標系

**単位はキャンバス論理ピクセル、原点は左上。DPI の概念は無い。**

- サイズ決定: `resizeCanvasToObject(objectWidth, objectHeight)` — `js/canvas-manager.js:204`。`#canvas-container` の実寸に収まる最大サイズを**比率から**算出。ページ作成の全入口がここを通る。最小 600×400
- 変更 API: `resizeCanvasByNum(w,h)`（同 `:99`、プロジェクト読込時のピクセル直指定）と `resizeCanvas(w,h)`（同 `:108`、全オブジェクトを `initial` 基準で再スケール）
- mm: 既定 148×210（`DEFAULT_PAGE_WIDTH_MM` / `DEFAULT_PAGE_HEIGHT_MM` — 同 `:34-35`）。`derivePageSizeMm(pw,ph)`（同 `:73`）が比率のみから算出し長辺を 297mm 固定。**ピクセルと mm の固定換算係数は無い**
- **`canvas.width` はウィンドウ依存で環境ごとに変わる**（`js/canvas-manager.js:66-70` のコメントも同趣旨）。外部解析結果は 0.0〜1.0 で保持し、流し込み時に `canvas.getWidth()` / `getHeight()` を掛ける
- **縦横を独立に正規化するとアスペクト比の違うページでコマが歪む**

### B-9. commonProperties

`js/core/settings.js:77-102` に定義された**文字列配列**（計約45件）。fabric.js の `canvas.toJSON(propertiesToInclude)` に渡す引数で、
**fabric 標準以外のプロパティのうちここに列挙したものだけが JSON へ書き出される。**

| 使用箇所 | 用途 |
|---|---|
| `js/layer/image-history-management.js:305` | `customToJSON()` — 履歴スナップショット生成（保存の本体） |
| 同 `:359-363` | `restoreImage()` — 復元時の再代入ループ |
| `js/ai/queue/generation-task-manager.js:267` | オフスクリーンキャンバスの JSON 化 |

現在入っているものの概要:

- 種別フラグ: `isPanel` / `isIcon` / `isSpeechBubble` / `customType` / `excludeFromLayerPanel`
- AI 生成の設定: `text2img_prompt` / `text2img_negative` / `text2img_seed` / `text2img_width` / `text2img_height` / `text2img_samplingMethod` / `text2img_samplingSteps` / `tempPrompt` / `tempNegative` / `tempSeed` / `img2imgScale` / `img2img_denoise`
- リンクと識別: `guid` / `guids`

**列挙されていないプロパティは保存時に消える。**

### B-10. `file://` 制約と外部通信

**`file://` オリジンから `http://127.0.0.1` への `fetch` は実際に通っている。** 回避策（プロキシ等）は使っておらず、**全て素の `fetch` の直叩き**。
成立条件はサーバー側が `Access-Control-Allow-Origin` を返すことだけ。
`llm_doc/ai-verification.md:588` の実測表に「動的 import: `http://127.0.0.1`（CORS付き） OK」とある。

| 宛先 | ファイル:行 | 備考 |
|---|---|---|
| ComfyUI（ローカル / RunPod） | `js/ai/comfyui/comfyui-management.js:46` | `comfyuiFetch()` が唯一の入口 |
| ComfyUI `/prompt` | `js/ai/comfyui/v2/comfyui-util-v2.js:402` | **POST ＋ `Content-Type: application/json`**（プリフライト OPTIONS が発生。これが通っている） |
| ComfyUI `/upload/image` | `comfyui-util-v2.js:123`, `comfyui-management.js:438,475` | POST ＋ FormData |
| ComfyUI WebSocket | `js/ai/comfyui/comfyui-management.js:123` | **WebSocket は CORS 対象外なので `file://` でもそのまま繋がる** |
| SD WebUI | `js/ai/sdwebui/sdwebui-multi-call-api.js` 各所 | |
| Ollama | `js/ai/provider/llm-provider.js:63`（chat）/ `:176`（models） | |
| Fal.ai / Google / Grok | `falai-provider.js:74,180,210` / `google-image-provider.js:179` / `grok-provider.js:59` | HTTPS 外部 |

**CORS は回避していない。ユーザーにサーバー側の起動オプションを案内する方式**（`html/docs/ai-setup-ja.html:100,102,117`）。

- ComfyUI: `--enable-cors-header`
- SD WebUI / Forge: `--api --cors-allow-origins *`
- Ollama: `OLLAMA_ORIGINS` に `*`（効かない場合は `null`）— `html/API_Help/llm_settings.html:63,74`

`file://` は `Origin: null` を送るため、サーバー側が `null` または `*` を許可する必要がある。

**Chrome 拡張連携（`llm_doc/chrome.md`）はアプリの実行に一切関与しない。** 開発者が UI を確認するための手順書であり、
拡張は `file://` のページを扱えない（`chrome.md:4-8`）。`js/` 内に `chrome.runtime` 等の参照は無い。

**重要**: `http://` で開いたときと `file://` で開いたときで IndexedDB / localStorage のオリジンが別（`chrome.md:25-27`）。
ローカルサーバーからアプリ本体を配信すると、ユーザーの既存プロジェクトと設定が全部見えなくなる。

### B-11. 疎通監視の既存実装

`js/ai/provider/ai-provider.js`

```
checkModelsEndpointHeartbeat()  :40   モデル一覧 GET で疎通を見る
_probeReachable()               :57   mode:'no-cors' で再投擲
classifyFailure()               :66   opaque が返れば cors、返らねば unreachable
getStatusReason()               :76   チップの title に出す文言
setConnectionNotice(kind,code)  :81   通知欄へ文言とヘルプリンクを描画
```

**ブラウザでは CORS 拒否とサーバー停止がどちらも `TypeError` になり区別できないため、`no-cors` で投げ直して切り分ける**
（`llm_doc/ai-system.md:187-193`）。原因が違えば対処も違うので「接続できません」に丸めない方針。

| 要素 | 場所 |
|---|---|
| 15秒間隔のポーリング | `js/ai/ai-settings.js:140` |
| 本体 | `js/ai/ai-management.js:234` `apiHeartbeat()` |
| 対象の絞り込み | `js/ai/ai-management.js:200` `getInUseProviders()` — ロール表で実際に選ばれているサービスだけ |
| ON/OFF トグル | `apiHeartbeatCheckbox`（`js/project-management.js:296`、既定 true） |
| バッジ描画 | `js/ai/ai-management.js:217` `renderProviderStatusChips()` → `#ExternalService_Heartbeat_Container`（`index.html:1831`、CSS は `css/components.css:297,305`） |

### B-12. 設定の永続化

**保存先**: localStorage キー `localSettingsData` に全設定を一括 JSON。定義は `js/project-management.js:265` からの
`SETTINGS_SCHEMA`。大容量は localforage（IndexedDB）。

**エンドポイント URL 追加の作法**（Ollama が手本）:

1. `index.html:2196-2215` と同型でテーブル行を追加。URL 欄と、その直下に `us-conn-notice` クラスの通知欄。右列に「初期値」「再取得」「?」ボタン
2. `js/project-management.js:291` の `ollamaUrl` と同型で `SETTINGS_SCHEMA` に1行追加 → **これだけで保存・復元・自動保存の対象になる**
3. `js/ai/ai-settings.js:124-136` と同型でイベント登録。「初期値」ボタンは値を入れてから change イベントを発火
4. ローカル / 外部タグ（`us-tag-local`）を**使用サービス表と接続先表の両方に手で**付ける（JS 生成ではない。`llm_doc/ai-system.md:386`）

**`js/ai/ui/unified-settings-window.js` は全46行で、開閉とタブ切替しか持たない。** 値の読み書きは無いので、ここに手を入れる必要はほぼ無い。
自動保存は全項目一括なので、DOM 上で空の項目は空のまま保存される（`llm_doc/history-and-data.md:222`）。

### B-13. i18n

- 本体: `js/ui/third/i18next.js:12` の `resources`。8言語（ja, en, ko, fr, zh, ru, es, de）
- ベース訳: `js/ui/third/base-translation/base-{ja,en,ko,fr,zh,ru,es,de}.js`
- **キー命名**: `yyyyMMddHHmmss_SSS`。ブロックキーも同形式で、`mergeResources()`（`i18next.js:8294`）がキー名ソート順に代入するため**日付が新しいブロックが勝つ**
- 書式: 1行1エントリ、新エントリは既存の上へ
- HTML: `data-i18n` 属性（`innerHTML` 代入）。**`[title]` を付ける記法は使えない**（アイコンが壊れる）。ツールチップは `data-tip` と tippy
- JS: `getText("key")`。**未定義でもキー文字列を返すため、論理和で既定値を与える書き方は効かない**
- 落とし穴: ブロックキーの重複は前のブロックを丸ごと消す（確認コマンドは `llm_doc/translation.md:36`）。`npm run check-translations` は言語間の突き合わせのみで、全言語に無いキーは検出されない

### B-14. 機能フラグと条件付き UI

**グローバルな機能フラグの仕組みは無い。** 既存パターンは4つ。

| パターン | 場所 |
|---|---|
| プロバイダの能力メソッド（既定 false、対応する側だけ true） | `js/ai/provider/ai-provider.js:112` `supportsDetachedT2I()`、同 `:122` `supportsReferenceSheets()`。呼び出し側 `js/ai/ai-management.js:144,148` |
| 能力なしのとき**隠さず理由を返す** | `js/ai/reference/reference-generator.js:31`、`js/ai/reference/reference-sheet-window.js:376` が `{ok:false, message}` を返す |
| 選択状態に応じた表示切替 | `js/ai/ui/ai-ui-util.js:70-100` `updateWorkflowType()` が `showById()` / `hideById()` で欄を出し分け |
| **実行環境による無効化** | `js/core/service/worker-register.js:1-18` `isPWAEligible()` が protocol と hostname を見て Service Worker とインストールボタン（同 `:78-89`）を制御。`file://` では自動的に OFF |

### B-15. 画像と大容量データ

- **`data:` URL 制約**: `imageMap` には `data:` URL か JSON 文字列のみ。`blob:` はセッション限りで保存禁止、保存時に `convertImageMapBlobUrls()` で変換（`llm_doc/history-and-data.md:177-182`）
- **canvas 汚染**: `file://` の画像を canvas に読むと `getImageData` が SecurityError（`llm_doc/ai-verification.md:586`）。現状の生成画像は `data:` かページ内 blob なので無事
- **IndexedDB（localforage）**: 8ストア稼働中。`autoSaveStorage`（`js/core/auto-save.js:3`）、`fm-fontStorage`（`js/db/user-font-repository.js:5`）、`MangaEditor_Reference`（`js/db/reference-repository.js:7`）、`workflowStorage`（`js/ai/comfyui/v2/comfyui-workflow-repository.js:174`）、`objectInfoStorage`（`comfyui-object-info-repository.js:123`）、統計3種（`js/dashboard/*-storage.js:3`）。追加時の手本は `js/db/reference-repository.js:4-45`
- **File System Access API と `webkitdirectory` は出現0件**（`js/`, `index.html`, `html/` 全検索）。`<input type="file">` は3か所のみ（`index.html:1766, 2304, 2305`）
- ドラッグ&ドロップの既存受け口: `js/ai/reference/reference-sheet-window.js:1375-1400`。ウインドウ全体で dragover / drop を受け `addFromFiles()` に渡すだけ。**ディレクトリ走査はしていない**
- **`file://` でフォルダ一括読み込みが可能かは未検証。** ただし**ブラウザは仕様上ファイルの絶対パスを取得できない**ため、いずれの手段でもサーバーにフォルダ位置を伝えられない。本計画ではサーバー側でフォルダを列挙する

### B-16. ビルドと配布形態

- npm スクリプトは `lint` / `lint:fix` / `format`（`scripts/remove-spaces.cjs`）/ `check-translations` の4つのみ
- 依存は devDependencies に eslint 系2つ**だけ**。**ランタイム依存ゼロ。** サードパーティは `third/` と `js/ui/third/` にベンダリング済み
- `01_build` はバンドラではなく**SVG アセットの JS 配列化のみ**。`01.svg_build.bat` が `SvgBuilder.py` を3回呼び、`02_images_svg/` の `.svg` を `js/svg/manga-panels-image-{landscape,vertical}.js` と `js/svg/speechbubble.js` に変換する
- **ES Modules ではなくグローバル前提。** `package.json` に `"type":"module"` はあるが、アプリ本体は約100本の `<script defer>` をグローバル変数で繋ぐ構成。`js/` 配下に import / export は無い。`file://` では隣接 `.mjs` の動的 import も `<script type="module">` も失敗するため（`llm_doc/ai-verification.md:582-584`）、この構成は制約由来
- 追加場所は `index.html:2470` 付近の `<script>` 群。AI 系は `js/ai/queue/*` → `js/ai/sdwebui/*` → `js/ai/comfyui/*` → `ai-settings.js` → `ai-management.js` → UI 系の順で、**参照される側が先**
- 版数は `?v=7.x`。CSS は `index.html:311, 2348` 付近の `<link>` に同様
- **Service Worker**: `service-worker.js:2` の `CACHE_VERSION`。`.js` と `.css` はキャッシュ優先なので、**URL の `?v=` を上げないと更新が届かない**（`.html` は stale-while-revalidate なので不要）
- 既存の `99_server.py`（CORS 付き `SimpleHTTPRequestHandler`、ポート8000）は静的配信のみ。`99_server.bat` は存在しない `01_server.py` を呼んでおり**壊れている**

### B-17. 進捗表示

- **`aiTaskMap` 系（`createSpinner` / `js/ai/queue/spinner.js`）は不適。** `createSpinner(layerGuid, taskType)` はレイヤー GUID 必須で、表示先はレイヤーパネルの行内インジケータ（`spinner.js:91` `renderAiTaskIndicators`）
- **使うべきは `js/ui/overlay-progress.js`（全93行）**: `OP_showLoading()` で開始、ループ内で `OP_updateLoadingState()`、終了時 `OP_hideLoading()`。キャンセルは `OP_isCancelled()` を毎回見る協調方式（開始前に `OP_resetCancel()`）
- 並行数の制御が要るなら TaskQueue を1本追加できる。戻りは Promise で、`whenIdle()` で完了待ち
- キューを増やしたら `js/ai/queue/spinner.js:48` `_getQueueByName()` にも足す必要があるが、これは `cancelAiTask` 経由の取消のためなので `aiTaskMap` を使わないなら不要
- **`setTimeout` でのポーリングは禁止**（非表示タブで1分間隔まで間引かれる）
- Toast（`js/ui/toast.js` の `createToast`）は同一内容をまとめる仕様なので進捗には向かない。**完了・失敗時のみ**

### B-18. TaskQueue は永続化していない

`llm_doc/次期サーバー化計画.md:175` に 2026-08-31 確認として記載がある。
`js/ai/queue/task-queue.js` は135行で、配列と Promise と Map だけで動いており、**保存も復元も無い。リロードで積んだものは全部消える。**

本計画の再生成フェーズは1コマ数分 × ページ分になるため、**ここが前提になる**。

---

## C. Claude Code 連携

### C-1. 方式の比較

| 方式 | 向いている用途 | 設定ファイル | 認可 | 配布 |
|---|---|---|---|---|
| **MCP サーバー** | 複数ツール・常時利用・他クライアントとも共有 | `.mcp.json`（project スコープ、コミット可） | 初回のみ `/mcp` で承認 | 容易 |
| Skills | 単発の手順・自動判断が要るもの | `.claude/skills/` の Markdown | 実行時に許可 | 容易 |
| Hooks | イベント駆動の検証・自動化 | `.claude/settings.json` | matcher で制御 | 容易 |

### C-2. トランスポート

| トランスポート | 特徴 | 本件での評価 |
|---|---|---|
| **stdio** | ローカルプロセス・標準入出力。Claude Code がプロセスを起動・終了 | **採用。** ポートも認証も不要。HTTP サーバー未起動でも使える |
| HTTP + SSE（従来型） | SSE 常時接続と `/messages` | 不要 |
| Streamable HTTP（新仕様） | 単一 `/mcp` エンドポイント | 既存 HTTP サーバーに同居させたい場合の選択肢 |

`.mcp.json` のスコープ:

```
local   : ~/.claude.json          個人専用・自動承認・共有不可
project : リポジトリの .mcp.json  クローン後は未承認。/mcp で承認後に自動接続
user    : ~/.claude.json          全プロジェクトで有効
```

環境変数展開は既定値付きの形式で可能。展開はセッション開始時。

### C-3. ツール設計の制約

- **出力上限は既定で約26,000トークン**（環境変数で調整可）。解析結果をそのまま返す設計は破綻する
- **画像や大きな JSON はファイルパスか参照 ID を返す。** base64 で返さない
- **ツールの既定タイムアウトは30秒**（環境変数、ミリ秒）。長時間処理は「開始 → ID 返却 → 状態問い合わせ」に分割する
- Resources（読み取り専用の参照データ）と Tools（実行）を使い分ける

### C-4. ブラウザ側との連携

**Claude Code から `file://` のページを直接操作する手段は無い。** Chrome 拡張は `file://` のページを一切扱えない。
→ **ファイルまたはサーバー経由の間接連携のみ。**

**注意**: 本項の調査で得た Python MCP SDK のクラス名とコード例は裏取りが不十分。実装時に公式 SDK で確認すること。

---

## D. 確定できなかったこと

| 項目 | 状況 |
|---|---|
| モデルのライセンス | manga-analyzer のリポジトリ内に一切記載が無く、検証された形跡も無い。MagiV2 と ultralytics（YOLOv8 のフレームワーク）の条件確認が必要という指摘自体も、リポジトリ内に根拠が無い**推測** |
| `reading_order` の LLM 依存 | 依存宣言に `vision_analysis` が入っているが、実装が実際に何を要求しているかは未確認 |
| 「コマ＋セリフ」経路の VRAM 下限 | 記載なし。実測が必要 |
| 見開き画像の分割 | analyzer は見開き前提の `page_side` を持つが、単ページ入力との切り分けは未確認 |
| `file://` でのフォルダ一括読み込みの可否 | 未検証。ただし絶対パスが取れないため、本計画では回避済み |
| Python MCP SDK の API 詳細 | 裏取り不十分 |
| 解析の出力品質 | パイプラインの構造とログは読んだが、**実際に走らせて結果の妥当性を見ていない**。コマ検出・OCR の精度は未確認 |
