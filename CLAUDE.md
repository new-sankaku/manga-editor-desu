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
