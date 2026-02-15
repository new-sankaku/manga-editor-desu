[English](https://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker) |
[日本語](https://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker/blob/main/README_JP.md) |
[中文](https://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker/blob/main/README_CN.md)

# Manga Editor Desu! Pro Edition
**ジェネリック漫画！！作れる！！時短漫画！！AIで！！**

ComfyUIと接続して、コマ割りから画像生成・仕上げまで一つのツールで完結する漫画制作Webアプリケーションです。

<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/01_mainpage.webp" width="700">

---

## このツールを使う理由

### &#x1f310; インストール不要 - ブラウザだけで動く
デモサイトを開けばすぐに使い始められます。ローカルにダウンロードすればオフラインでも動作します。アカウント登録もサーバーも不要です。

&#x1f517; [デモサイトで今すぐ試す](https://new-sankaku.github.io/manga-editor-desu/)

### &#x1f3a8; AI画像生成と直結 - コマの中で直接生成
ComfyUIと接続すれば、コマを選んでプロンプトを入力するだけ。生成された画像は自動的にコマにフィットします。独自のWorkflowにも対応しています。

### &#x1f9e9; 初心者もプロも - 自分のレベルに合った使い方
プリセットのコマ割りを選ぶだけで漫画ページが完成します。慣れてきたらナイフツールで自由にコマを切ったり、レイヤーやブレンドモードで本格的な編集も可能です。

### &#x1f4b0; 完全無料・オープンソース
機能制限なし。すべての機能を無料で利用できます。ローカルで完結するためデータが外部に送信されることもありません。

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

## AI画像生成の対応状況

| バックエンド | 対応モデル | 備考 |
|-------------|-----------|------|
| ComfyUI | SD1.5, SDXL, Pony, Flux1 | 独自Workflowにも対応 |
| WebUI | SD1.5, SDXL, Pony | |
| Forge | SD1.5, SDXL, Pony, Flux1 | |

*A1111/Forgeの開発が不透明なため、今後はComfyUIのみをサポートする予定です。

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

- **多言語対応**: 英語、日本語、韓国語、フランス語、中国語、ロシア語、スペイン語、ドイツ語
- **ページプリセット**: プリセットされたコミックパネルのレイアウト
- **パネル**: パネルの作成とカスタマイズ。形状、色、線の幅などを調整可能
- **吹き出し**: 40種類以上の吹き出しスタイル、各スタイルは背景色、線の色、透明度の設定が可能
- **カスタム吹き出し**: 座標指定、フリーハンドで吹き出しを作成。線の種類は7種類。スムージング処理もあり
- **ランダムカット**: 縦と横のカット数、傾斜角度、線開始位置を指定したランダムなパネルカット機能
- **複数ページ作成**: ランダムカットの情報を使用して複数ページを丸ごとカットする機能
- **オートフィット**: コミックパネル内に生成された画像やドロップされた画像は自動的に適切にスケールおよびトリミング
- **オーバーレイ**: フレーム外にドロップされた画像をオーバーレイとして表示
- **レイヤー**: グラフィックデザイナーやアーティストに馴染みのあるレイヤーとして画像、テキスト、パネルを管理
- **画像編集機能**: 角度、位置、スケール、反転などの調整
- **画像エフェクト**: セピア、グレースケール、ガンマ、ぼかし、ビビランス、ピクセル化
- **画像エフェクト(Glfx)**: アンシャープマスク、ズームブラー、ドットスクリーン、六角ピクセレート、インク、色相/彩度
- **テキスト**: 縦書き、横書き、太字、影、輪郭、ネオン、コミックに適した様々なフォント
- **画像テキスト**: プリセット化された画像のテキスト
- **トーン機能**: 漫画の背景で良くあるトーン機能
- **ブレンドモード**: Adobe Photoshopなどにあるブレンドモードを25種類
- **グロー**: 画像輪郭へのグロー効果
- **アンドゥ/リドゥ**: 編集中に自由に変更を元に戻すまたはやり直し
- **プロジェクトの保存/読み込み**: 作業中のプロジェクトを保存および読み込み
- **設定の保存/読み込み**: 変更した設定を保存および読み込み
- **画像のエクスポート**: 完成したページを印刷やデジタル配信に適した形式でエクスポート
- **Text2Image**: ComfyUI/WebUI/Forgeを介してパネル内で直接画像を生成
- **Image2Image**: WebUIを介してパネル内で直接画像を生成
- **プロンプトキュー**: 異なるキャラクターバージョンを生成するためにプロンプトを一括キュー
- **ペン/消しゴムツール**: 線の幅、色、スタイル、影の変更。線や画像の一部を消去
- **キャンバスのズームイン/ズームアウト**: キャンバスの拡大縮小表示

</details>

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

ありがとうございます！
