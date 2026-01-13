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

## コメントに関する注意事項
- コード内のコメントは基本的に不要
- JSファイルの先頭にファイルの概要（どういう処理がまとまっているか）のみ記載する
- JSDocスタイルの関数コメントは不要

## ログ出力に関する注意事項
- `console.log`は使用禁止。代わりに`js/core/logger.js`のLoggerを使用すること
- 各モジュールで`SimpleLogger`を使ってロガーを作成する
- 例: `var canvasLogger = new SimpleLogger('canvas', LogLevel.DEBUG);`
- ログレベル: TRACE, DEBUG, INFO, WARN, ERROR, SILENT
- 使用例: `canvasLogger.debug("message");`, `canvasLogger.error("error message");`

## 履歴管理（Undo/Redo）に関する注意事項
- 画像の削除と追加を連続で行う場合、中間状態が履歴に残らないようにすること
- `changeDoNotSaveHistory()`と`changeDoSaveHistory()`で履歴保存を一時的に無効化する
- 最終結果のみ`saveStateByManual()`で履歴に保存する
- 例: オブジェクトを置き換える場合
```javascript
changeDoNotSaveHistory();
canvas.remove(oldObject);
canvas.add(newObject);
changeDoSaveHistory();
saveStateByManual();
```
- `activeObject.saveHistory = false;`でオブジェクト単位で履歴保存を無効化することも可能

## 画像データの保存に関する注意事項
- `imageMap`に保存するデータは必ず`data:` URLまたはJSON文字列にすること
- `blob:` URLは一時的な参照であり、セッション終了後やオリジン変更時に無効になる
- `blob:` URLをそのまま保存すると、プロジェクトファイル読込時に画像が復元できなくなる
- 保存時に`convertImageMapBlobUrls()`で`blob:` URLを`data:` URLに変換している
- オブジェクト（2D配列など）を保存する場合は`JSON.stringify()`で文字列化すること

## 翻訳の追加方法
- 翻訳は `js/ui/third/i18next.js` の `const resources` に追加する
- 新しい日付キー（YYYYMMDD形式）でエントリを追加し、既存エントリの上に配置する
- 全10言語（ja, en, ko, fr, zh, ru, es, pt, th, de）に対応すること
- 表示領域に留意するためなるべく短文が望ましい。

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
