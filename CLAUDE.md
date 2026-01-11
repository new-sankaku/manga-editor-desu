# プロジェクト注意事項

## ブラウザ自動化ツールの制限
- `mcp__claude-in-chrome__navigate` は `file://` プロトコルを正しく処理できない
- ローカルHTMLを開く場合はサーバーを起動すること

## ローカルサーバーの起動方法
```bash
python 99_server.py
```
- ポート: 8000
- URL: http://localhost:8000

## 読込禁止フォルダ
以下のフォルダは検索から除外し読み込まないこと:
- json_js
- test
- third
- 01_build
- 02_images_svg
- 03_images
- 99_doc
- font

## コーディング規約の注意事項
- APIレスポンスのプロパティ名（例: `response.prompt_id`）はAPI仕様に従う必要があり、camelCaseに変更してはいけない
- 変数名はcamelCaseを使用する（例: `var promptId = response.prompt_id;`）
- インデントは禁止（タブやスペースによる字下げをしない）
- 無くても良い半角スペースは削除する

## フォーマットスクリプト
JSファイルからインデントと不要なスペースを削除するスクリプト:
```bash
npm run format
```
削除対象:
- 行頭のインデント
- 行末の空白
- 演算子周りのスペース
- カンマ/セミコロン後のスペース
- 括弧内側のスペース

保持対象:
- 文字列リテラル内のスペース
- コメント内のスペース
- 改行
