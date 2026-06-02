# 外部ページ読み込みフォーマット仕様

外部ツールから生成したマンガページを Manga Editor DESU に取り込むためのデータ形式仕様。

## ステータス

| 形式 | 状態 | 経路 |
|---|---|---|
| `pages/pXXX_page.json` (レイヤー構造保持) | **実装済み** | `js/ui/project-loader.js` |
| 既存 `*.lz4` プロジェクトファイル | 実装済み | `js/project-management.js` |

レイヤー構造を保ったページを外部生成する場合は、本ドキュメントの JSON 形式を使ってください。

## 前提: アプリ内部のレイヤーモデル

- **1 レイヤー = 1 fabric.js オブジェクト**。グループも 1 レイヤー扱い
- レイヤーは `guid` で一意に識別される (UUID v4)
- **親子関係は親オブジェクトの `guids[]` 配列が子の GUID を保持する**双方向リンク (子は `relatedPoly` で親を参照)
- パネル (コマ) 配下の画像は `clipPath` で親形状にマスクされる
- 種別判定は fabric 標準の `type` プロパティと独自 `customType` / `isPanel` フラグの組み合わせ

主なレイヤー種別:

| 種別 | 判定 | アイコン |
|---|---|---|
| パネル/コマ | `isPanel=true` | crop_landscape |
| 画像 | `type="image"` | image |
| テキスト | `type` ∈ `i-text`, `text`, `textbox`, `vertical-textbox` | text_fields |
| ベクターパス | `type="path"` | gesture |
| 吹き出し | `customType="speechBubbleSVG"` | chat_bubble_outline |
| フリーハンド吹き出し | `customType="freehandBubblePath"` | chat_bubble_outline |
| グループ | `type="group"` (`customType` 無し) | folder |

## ディレクトリ構成

プロジェクトを開いたときに以下を想定:

```
<選択フォルダ>/
└── pages/
    ├── p001_page.json    # ページ定義 (このドキュメントの対象)
    ├── p002_page.json
    ├── p003_page.svg     # SVG 1枚で済むページは SVG でも可 (PR #2 仕様)
    └── assets/
        ├── image-001.png
        ├── image-002.webp
        └── bubble-1.svg
```

- ファイル名規則: `pXXX_page.{json|svg}` (XXX は 3 桁以上の数字推奨、ローダは `parseInt` でソート)
- `assets/` 配下に画像など外部参照ファイルを配置。`page.json` 内では **`page.json` からの相対パス**で参照する
- `.json` と `.svg` を混在させた場合、両方が同じページ番号で存在したら `.json` を優先する想定 (実装時に確定)

## ページ JSON スキーマ

### トップレベル

```json
{
  "version": "1.0",
  "pageSize": { "width": 1024, "height": 1280 },
  "canvasGuid": "550e8400-e29b-41d4-a716-446655440000",
  "basePrompt": {
    "text2img_prompt": "masterpiece, best quality",
    "text2img_negative": "low quality",
    "text2img_seed": -1
  },
  "layers": [ /* レイヤー配列 */ ]
}
```

| キー | 必須 | 型 | 説明 |
|---|---|---|---|
| `version` | ◯ | string | 仕様バージョン。当面 `"1.0"` |
| `pageSize` | ◯ | `{width, height}` | キャンバスサイズ (px) |
| `canvasGuid` | ✕ | UUID | 省略時はローダ側で `generateGUID()` |
| `basePrompt` | ✕ | object | AI 生成の基本プロンプト。省略可 |
| `layers` | ◯ | array | レイヤー定義。**奥から手前への順**で並べる (配列先頭が最背面) |

### レイヤー共通フィールド

すべてのレイヤーで使う共通フィールド:

| キー | 必須 | 型 | 説明 |
|---|---|---|---|
| `guid` | ◯ | UUID | レイヤー一意 ID |
| `type` | ◯ | string | fabric.js の `type` (`image`, `rect`, `polygon`, `path`, `textbox`, `vertical-textbox`, `group` 等) |
| `customType` | ✕ | string | 独自種別 (`speechBubbleSVG`, `freehandBubblePath` 等)。`type` で識別できる場合は省略 |
| `name` | ✕ | string | レイヤー名 (UI 表示用)。省略時は種別ベースで自動生成 |
| `left`, `top` | ◯ | number | 配置座標 (px) |
| `width`, `height` | △ | number | 種別による。画像/矩形は必須、テキストは省略可 |
| `scaleX`, `scaleY` | ✕ | number | デフォルト 1.0 |
| `angle` | ✕ | number | 回転角度 (度)。デフォルト 0 |
| `opacity` | ✕ | number | 0.0〜1.0。デフォルト 1.0 |
| `visible` | ✕ | boolean | デフォルト true |
| `selectable` | ✕ | boolean | デフォルト true |
| `guids` | ✕ | string[] | 子レイヤーの guid 配列 (親子関係) |
| `relatedPoly` | ✕ | UUID | 親レイヤーの guid (子からの逆参照) |

### 種別ごとの追加フィールド

#### 画像 (`type="image"`)

```json
{
  "guid": "uuid-image-1",
  "type": "image",
  "src": "assets/image-001.png",
  "left": 15, "top": 25,
  "width": 290, "height": 390,
  "relatedPoly": "uuid-panel-1"
}
```

- `src`: `page.json` からの相対パス。`assets/...` を推奨。`data:` URL も許容
- `clipPath`: 省略可。指定が無く `relatedPoly` がパネルを指す場合、ローダがパネル形状から自動生成

#### パネル/コマ (矩形/多角形, `isPanel=true`)

```json
{
  "guid": "uuid-panel-1",
  "type": "polygon",
  "isPanel": true,
  "left": 10, "top": 20,
  "width": 300, "height": 400,
  "points": [
    {"x": 0, "y": 0},
    {"x": 300, "y": 0},
    {"x": 300, "y": 400},
    {"x": 0, "y": 400}
  ],
  "fill": "rgb(255,255,255)",
  "stroke": "rgb(0,0,0)",
  "strokeWidth": 2,
  "guids": ["uuid-image-1"]
}
```

- 矩形パネルは `type="rect"` + `width`/`height` のみで OK
- 多角形 (`type="polygon"`) は `points` を必須
- `guids` に配下画像の guid を列挙すると、その画像はパネル形状でクリップされる

#### テキスト (`type="textbox"` または `type="vertical-textbox"`)

```json
{
  "guid": "uuid-text-1",
  "type": "textbox",
  "text": "セリフ本文",
  "left": 320, "top": 100,
  "fontSize": 20,
  "fontFamily": "Noto Sans JP",
  "fill": "rgb(0,0,0)",
  "textAlign": "center",
  "lineHeight": 1.2
}
```

- 縦書きは `type="vertical-textbox"`
- フォントは `js/core/font/` に登録済みのもの推奨。未登録だと別フォントにフォールバックされない (fallback禁止方針)

#### 吹き出し (`customType="speechBubbleSVG"`)

吹き出しはテキストと SVG パスの組合せ。グループ単位で定義:

```json
{
  "guid": "uuid-bubble-1",
  "type": "group",
  "customType": "speechBubbleSVG",
  "left": 310, "top": 90,
  "guids": ["uuid-bubble-rect", "uuid-bubble-text"],
  "children": [
    {
      "guid": "uuid-bubble-rect",
      "type": "path",
      "d": "M 0 0 L 100 0 L 100 50 L 50 60 L 0 50 Z",
      "fill": "white",
      "stroke": "black",
      "strokeWidth": 2
    },
    {
      "guid": "uuid-bubble-text",
      "type": "textbox",
      "text": "こんにちは！",
      "left": 10, "top": 10,
      "fontSize": 16
    }
  ]
}
```

#### ベクターパス (`type="path"`)

```json
{
  "guid": "uuid-path-1",
  "type": "path",
  "d": "M 0 0 Q 50 -20 100 0",
  "left": 100, "top": 200,
  "fill": "transparent",
  "stroke": "rgb(0,0,0)",
  "strokeWidth": 3
}
```

#### グループ (`type="group"`)

任意レイヤーをまとめる汎用コンテナ。`customType` 無し。`children` 配列で子を内包する。

## 親子関係の記述

**冗長だが両方を必須**にする:

1. 親レイヤーの `guids` に子の guid を列挙
2. 子レイヤーの `relatedPoly` に親の guid を設定
3. 子レイヤーは `layers` トップレベル配列に置く**か** 親の `children` 配列に置く (どちらでも可、ローダ側で正規化)

例:

```json
{
  "layers": [
    {
      "guid": "panel-A",
      "type": "rect",
      "isPanel": true,
      "guids": ["img-A"]
    },
    {
      "guid": "img-A",
      "type": "image",
      "src": "assets/img-a.png",
      "relatedPoly": "panel-A"
    }
  ]
}
```

## アセット参照

- `src`, `d` (path), `points` (polygon) 以外で外部ファイルを参照する場合は `assets/<相対パス>` を使う
- ローダはバックエンド `/api/file?path=<HOME相対>` で取得し、内部で data URL 化して `imageMap` に登録する (既存実装と整合)
- HOME 外参照は 403 で拒否される

## 完全な例

`pages/p001_page.json`:

```json
{
  "version": "1.0",
  "pageSize": { "width": 1024, "height": 1280 },
  "layers": [
    {
      "guid": "panel-1",
      "type": "polygon",
      "isPanel": true,
      "name": "Top Panel",
      "left": 32, "top": 32,
      "width": 960, "height": 400,
      "points": [
        {"x": 0, "y": 0},
        {"x": 960, "y": 0},
        {"x": 960, "y": 400},
        {"x": 0, "y": 400}
      ],
      "fill": "rgb(255,255,255)",
      "stroke": "rgb(0,0,0)",
      "strokeWidth": 3,
      "guids": ["bg-1"]
    },
    {
      "guid": "bg-1",
      "type": "image",
      "name": "Background",
      "src": "assets/bg-cafe.png",
      "left": 32, "top": 32,
      "width": 960, "height": 400,
      "relatedPoly": "panel-1"
    },
    {
      "guid": "bubble-1",
      "type": "group",
      "customType": "speechBubbleSVG",
      "name": "Hero Bubble",
      "left": 500, "top": 80,
      "guids": ["bubble-1-shape", "bubble-1-text"],
      "children": [
        {
          "guid": "bubble-1-shape",
          "type": "path",
          "d": "M 0 0 L 200 0 L 200 80 L 130 90 L 100 110 L 80 90 L 0 80 Z",
          "fill": "white",
          "stroke": "black",
          "strokeWidth": 2
        },
        {
          "guid": "bubble-1-text",
          "type": "textbox",
          "text": "やあ、久しぶり！",
          "left": 20, "top": 20,
          "width": 160,
          "fontSize": 18,
          "fontFamily": "Noto Sans JP",
          "textAlign": "center"
        }
      ]
    }
  ]
}
```

ディレクトリ:

```
my-project/
└── pages/
    ├── p001_page.json
    └── assets/
        └── bg-cafe.png
```

## 制約と既知の落とし穴

- **GUID 重複**: 別ページで同じ guid を使うと既存ページの参照が崩れる可能性。ページごとにユニーク推奨
- **画像形式**: PNG/JPG/WebP/SVG/GIF。読み込み後は内部で WebP 変換される (`js/core/util/image-util.js:imgFile2webpFile`)
- **フォント**: 登録済みフォント名でないと描画が破綻する場合あり。事前にフォント登録 (`js/db/user-font-repository.js`) を済ませる
- **clipPath の動的生成**: パネル子画像で `clipPath` を省略するとローダが `relatedPoly` から生成するが、複雑形状では誤差が出る可能性
- **fabric カスタムプロパティ**: `commonProperties` (`js/core/settings.js`) に未登録のプロパティはシリアライズ往復で失われる。新規プロパティは仕様改訂で追加

## 実装概要

`js/ui/project-loader.js` 内の関数:

| 関数 | 役割 |
|---|---|
| `loadProjectPagesFromFolder(folderPath, displayPath)` | `pages/pXXX_page.json` を列挙して取り込み |
| `addJsonAsPage(pageJson, pagesBasePath)` | 新規 GUID + canvas.clear → 各レイヤー enliven → btmSaveProjectFile |
| `enlivenLayer(spec, pagesBasePath)` | `type` で分岐して fabric オブジェクトを生成 (group は再帰) |
| `resolveSrc(src, pagesBasePath)` | 相対パスは `/api/file?path=<HOME相対>` に解決 (data:/http(s) はそのまま) |

未対応 (将来):
- 親子関係 (`guids` / `relatedPoly`) を読み取って fabric object のフラグとして保持はするが、clipPath の動的再生成はしていない
- `children` 配列方式のみサポート。`layers` トップレベルに flat に置いて `relatedPoly` で繋ぐ方式は今後対応

## 仕様変更ポリシー

- `version` フィールドで管理。後方互換性を破る変更はメジャー、追加的変更はマイナー
- フィードバック歓迎。Issue / PR にて議論
