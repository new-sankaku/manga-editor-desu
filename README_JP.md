[English](https://github.com/new-sankaku/manga-editor-desu) |
日本語 |
[中文](https://github.com/new-sankaku/manga-editor-desu/blob/main/README_CN.md)

## ホワイトボード連携（2026-09-12・Codex）

コマまたは画像レイヤーのアクションバーから「ホワイトボードで描く」を押すと、ローカルのホワイトボード（`127.0.0.1:8190`）へ画像・寸法・文字文脈・盤IDを渡せます。返ってきた画像はまずプレビューされ、「本採用」で通常のUndoとプロジェクト保存へ入り、「破棄」で元へ戻ります。ホワイトボード単独では漫画原稿を書き換えません。

# Manga Editor Desu! Pro Edition
**ジェネリック漫画！！作れる！！時短漫画！！AIで！！**

コマ割りから画像生成・仕上げまで、ブラウザひとつで完結する漫画制作Webアプリケーションです。

<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/01_mainpage.webp" width="700">

---

## このツールを使う理由

### &#x1f310; インストール不要 - ブラウザだけで動く
デモサイトを開けばすぐに使い始められます。ローカルにダウンロードすればオフラインでも動作します。アカウント登録は不要で、アプリ側にサーバーはありません。

&#x1f517; [デモサイトで今すぐ試す](https://new-sankaku.github.io/manga-editor-desu/)

### &#x1f3a8; AI画像生成と直結 - コマの中で直接生成
ComfyUI等と接続すれば、コマを選んでプロンプトを入力するだけ。生成された画像は自動的にコマにフィットします。独自のWorkflowにも対応しています。

### &#x270d; 文章から作る - LLM連携
ストーリーを書けば、コマの形と並びに合わせてコマごとのプロンプトを組み立てます。

### &#x1f9e9; 初心者もプロも - 自分のレベルに合った使い方
プリセットのコマ割りを選ぶだけで漫画ページが完成します。慣れてきたらナイフツールで自由にコマを切ったり、レイヤーやブレンドモードで本格的な編集も可能です。

### &#x1f4b0; 完全無料・オープンソース
機能制限なし。すべての機能を無料で利用できます。作成したプロジェクトがアップロードされることはありません（送信されるものについては[データの取り扱い](#データの取り扱い)をご確認ください）。

---

## クイックスタート

**デモサイト（すぐ使える）**

&#x1f517; [https://new-sankaku.github.io/manga-editor-desu/](https://new-sankaku.github.io/manga-editor-desu/)

**ローカル（より高速に動作）**
```
git clone https://github.com/new-sankaku/manga-editor-desu.git
cd manga-editor-desu
start index.html
```

---

## ドキュメント

- [機能リファレンス](https://new-sankaku.github.io/manga-editor-desu/html/docs/features-ja.html) - 全機能の詳細
- [よくある質問](https://new-sankaku.github.io/manga-editor-desu/html/docs/faq-ja.html) - 導入・保存形式・プライバシー
- [AIバックエンド設定ガイド](https://new-sankaku.github.io/manga-editor-desu/html/docs/ai-setup-ja.html) - CORS設定、APIキー、ワークフロー

---

## AI画像生成の対応状況

AI生成は任意の機能です。編集機能はすべてAIなしで動作します。処理の種類ごとに別のサービスへ振り分けられます。

| サービス | 動作場所 | 対応する処理 | 必要なもの |
|---|---|---|---|
| ComfyUI | ローカル | T2I / I2I / インペイント / 高解像度化 / 背景削除 / アングル再生成 | `--enable-cors-header` |
| RunPod ComfyUI | クラウド | ComfyUIと同じ | PodのURL |
| SD WebUI (A1111 / Forge) | ローカル | T2I / I2I / 背景削除 / CLIP / DeepDanbooru / ADetailer | `--api --cors-allow-origins *` |
| Fal.ai | クラウド | T2I / I2I / 高解像度化 / 背景削除 | APIキー |
| Grok (xAI) | クラウド | 言語モデル処理 | APIキー |
| Ollama | ローカル | 言語モデル処理 | `OLLAMA_ORIGINS` |

ComfyUIの同梱ワークフローは SD1.5 / SDXL / Flux / Z-Image-turbo / Qwen-Image に対応しています。インペイントとアングル再生成はComfyUIのみです。

---

## 主な機能の紹介

### Image Drop
https://github.com/user-attachments/assets/7cf94e6c-fc39-4aed-a0a1-37ca70260fe4

### Speech Bubble (Template)
https://github.com/user-attachments/assets/6f1dae5f-b50f-4b04-8875-f0b07111f2ab

### Image Prompt Helper
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/03_prompthelper.webp" width="700">

### Grid Line / Knife Mode
<div style="display: flex; align-items: flex-start;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/05_gridline.webp" height="350">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/06_knifemode.webp" height="350">
</div>

### Dark Mode
<div style="display: flex; align-items: flex-start;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/09_darkmode.webp" height="350">
</div>

### Blend Mode
<div style="display: flex; align-items: flex-start;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/12_blend.webp" height="350">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/13_blend.webp" height="350">
</div>

### Effect
<div style="display: flex; align-items: flex-start;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/04_gpix01.webp" height="350">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/04_gpix02.webp" height="350">
</div>

### Text, Speech Bubbles, Pen
<div style="display: flex; align-items: flex-start;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/08_speechbubble.webp" height="350">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/07_font.webp" height="350">
</div>

### Support Language
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/02_trans.webp" height="400">

---

<details>
<summary><strong>全機能一覧</strong></summary>

**ページ・コマ**
- **コマ割りテンプレート**: 縦41種・横28種の計69種
- **ナイフツール**: マウスで引いた線に沿ってコマを分割。余白幅0〜75
- **コマ編集モード**: 頂点を動かして台形などに変形
- **図形コマ**: 正方形、縦長・横長の長方形、三角形、五角形、六角形、星形、ハート
- **ランダムカット**: 縦横のカット数、傾斜角度、線のばらつきを指定したランダム分割
- **複数ページ作成**: 2〜50ページを一度に作成
- **ページ管理**: 画面下部のサムネイル列でページ切替・ドラッグ並べ替え。Alt+←/→で移動
- **原稿サイズ**: mm単位で指定。縦・横・カスタム(1〜4096)
- **グリッド**: 間隔調整可能なスナップ用グリッド

**フキダシ・テキスト**
- **フキダシ**: 48種類。線色・背景色・不透明度・線幅を設定可能
- **カスタムフキダシ**: 座標指定・フリーハンドで作成。線種7種、スムージング、角の丸め0〜15回
- **フキダシの結合**: 重なったカスタムフキダシをポリゴン演算で1つの輪郭に統合
- **テキスト**: 縦書き・横書き、太字、塗り・アウトライン・背景色、サイズ7〜150
- **フォント**: 156種類を4カテゴリ（セリフ70・特殊35・説明28・擬音23）に分類
- **フォント追加**: OS内蔵フォント、WebフォントURL、`.ttf/.otf/.woff/.woff2`のアップロード
- **プロジェクトフォント保存**: 使用フォントを記録し読み込み時に復元
- **画像テキスト**: 31種類の装飾スタイル（ネオン、クローム、金属、基板、オーロラ等）

**描画・効果**
- **ペン**: 8種類（マーカー、インク、クレヨン、鉛筆、二重縁取り、円、モザイク、消しゴム）
- **トーン**: 5種類（網点、ノイズ、雪、流線、集中線）
- **モノクロ変換**: 6種類。選択画像・ページ全体・全ページに一括適用可能
- **フィルタ**: 15種類（アンシャープマスク、ズームぼかし、ドットスクリーン、六角ピクセル化、インク、色相/彩度ほか）
- **ブレンドモード**: 25種類を5系統に分類
- **グロー**: 画像輪郭への発光効果
- **変形**: 回転、拡大縮小、傾き、不透明度、左右・上下反転、切り抜き、上下左右の表示制限

**レイヤー・履歴**
- **レイヤー**: 画像・テキスト・コマをレイヤーとして管理。表示切替、移動ロック、順序変更、個別ダウンロード
- **右クリックメニュー**: 変形・スタイル・コマ・操作・表示制限・AIの6グループ
- **アンドゥ/リドゥ**: ページ内は回数無制限（ページ切替で履歴は消去）

**保存・書き出し**
- **プロジェクト保存/読み込み**: 保存は`DESU-Project.lz4`。読み込みは`.lz4`と`.zip`
- **自動保存**: 10〜600秒間隔（既定60秒）。次回起動時に復元を提案
- **画像エクスポート**: 原稿サイズ(mm)×DPI(既定300)でPNG出力。SVG出力にも対応
- **設定の保存/読み込み/リセット**

**AI生成**
- **Text2Image / Image2Image**: コマ内で直接生成・変換
- **インペイント**: マスクを描いて部分再生成（ComfyUIのみ）
- **アングル生成**: 3Dカメラウィジェットで別アングルから描き直し（ComfyUIのみ）
- **高解像度化 / 背景削除**
- **ロール割り当て**: 処理ごとに使用サービスを個別指定
- **ComfyUIワークフロー**: API形式のワークフローを読み込み、ノード入力をその場で編集
- **タスクキュー**: サービスごとの同時実行数1〜10、レイヤー上に進捗表示とキャンセル
- **プロンプト検索・置換**: プロジェクト全体のプロンプトを一括置換

**LLM連携**
- **ストーリーからコマのプロンプト**: 文章からコマごとのプロンプトを生成。コマ/ページ/全ページの範囲指定
- **キャラクター・ロケーション設定の抽出**: ストーリーから自動抽出して一貫性を保つ
- **ネームから一括生成**: 既存のネームからページ内全コマのプロンプトを生成
- **画像からプロンプト化**: 画像を読み取ってタグを追加

**その他**
- **多言語対応**: 英語、日本語、韓国語、フランス語、中国語、ロシア語、スペイン語、ドイツ語の8言語
- **ダッシュボード**: 生成時間、時間帯別アクティビティ、タグ統計、ワードクラウド、連続記録、目標、バッジ、外部API利用料の推定。JSON/CSV出力
- **プリセットピッカー**: ペン・トーン・画像テキスト・GLFXを一覧から検索して選択
- **PWAインストール / オフライン動作**
- **チュートリアル**: 各サイドバーパネルを案内するガイドツアー

</details>

---

## データの取り扱い

アプリ自体にサーバーはなく、作成したプロジェクトがアップロードされることはありません。ただし次の2点は外部へ送信されます。

1. **アクセス解析**: 公開サイトはGoogleアナリティクスを使用しており、ページ閲覧と画面操作が記録されます。
2. **クラウドAIサービス**: RunPod / Fal.ai / Grok を設定した場合、プロンプト、ストーリーやセリフのテキスト、コマの画像が当該サービスへ送信されます。ComfyUI / SD WebUI / Ollama をローカルでのみ使う場合、生成処理はマシン内で完結します。

またページ読み込み時に Google Fonts、cdnjs、unpkg からアセットを取得します。

設定・APIキー・ワークフロー・アップロードしたフォント・自動保存データ・利用統計はブラウザ（localStorage / IndexedDB）に保存されます。**クラウドサービスのAPIキーは暗号化されずに保存される**ため、共用のコンピューターでの入力は避けてください。

---

## インストール
https://github.com/new-sankaku/manga-editor-desu.git
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/02_.webp" width="700">

## 貢献方法
- **バグ報告**: バグを発見した場合は、[Issues](https://github.com/new-sankaku/manga-editor-desu/issues)に新しい問題を作成し、タイトルに**[Bug]**を含めてください。
- **機能提案**: 新しい機能のアイデアがある場合は、[Issues](https://github.com/new-sankaku/manga-editor-desu/issues)に新しい問題を作成し、タイトルに**[Feature Request]**を含めてください。
- **ドキュメント改善**: ドキュメントに誤字やエラーがある場合は、可能な修正を含むプルリクエストを送信してください。また、必要に応じて[Issues](https://github.com/new-sankaku/manga-editor-desu/issues)に追加することもできます。

## コミュニケーション
プロジェクトに関する質問や議論がある場合は、[Issues](https://github.com/new-sankaku/manga-editor-desu/issues)に投稿するか、[Discord](https://discord.gg/XCp7dyHj3N)サーバーに参加してください。

## ライセンス
GNU General Public License v3.0

ありがとうございます！
