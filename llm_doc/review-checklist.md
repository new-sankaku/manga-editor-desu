# レビューチェックリスト

ユーザーから修正ポイントの確認を求められた際に見落とされた項目を蓄積する。
同じ問題が繰り返される場合は回数をインクリメントして優先度の目安とする。

**上限100項目。超過時は回数0の古い項目から削除する。**

## チェック項目

| # | カテゴリ | チェック内容 | 回数 |
|---|---------|-------------|------|
| 1 | DOM | innerHTML代入時にサニタイズしているか | 0 |
| 2 | DOM | テンプレートリテラルで組み立てたHTMLにユーザー入力が混入しないか | 0 |
| 3 | 保存 | 追加したパラメータがSETTINGS_SCHEMA/BASEPROMPT_SCHEMAに含まれているか | 0 |
| 4 | 保存 | 新規オブジェクト属性をcommonPropertiesに追加したか | 0 |
| 5 | i18n | 新規UI文言にi18nキーを設定し8言語分の翻訳を追加したか | 0 |
| 6 | 履歴 | 一時オブジェクトにsetNotSave/excludeFromLayerPanelを設定したか | 0 |
| 7 | UI | 固定幅(px)ではなくフレキシブルレイアウトにしているか | 0 |
| 8 | UI | 既存の表示・表記と統一されているか | 0 |
| 9 | fallback | エラー時にfallback値で動作を続行していないか（fallback禁止） | 1 |
| 10 | file:// | file://プロトコルで動作するか（fetch等HTTP前提APIを使っていないか） | 0 |
| 11 | ログ | console.logではなくSimpleLoggerを使っているか。デバッグ時もlogger.trace等を使いログレベル変更で対応する | 1 |
| 12 | 命名 | 変数名がcamelCaseか、APIレスポンスのキーを変換していないか | 0 |
| 13 | format | npm run formatで崩れるスペースを入れていないか | 0 |
| 14 | GUID | 新規オブジェクトにguidを付与しているか | 0 |
| 15 | イベント | EventDelegatorのパターンに従っているか（直接addEventListenerしていないか） | 0 |
| 16 | 履歴 | ループやcanvas.add/remove連続呼び出しでsaveStateByManual()が都度発火しないか。都度発火すると大量の履歴スナップショットが生成され、メモリの圧迫・履歴保存による画面の固まり・Undo/Redoで無意味な操作が発生する。複数操作はwithoutHistory(fn)で囲み最後に1回だけ保存（同一タスク内のイベントは自動集約されるが、非同期をまたぐ処理は集約されない） | 1 |
| 17 | 性能 | forループ等でオブジェクトのプロパティを連続変更する際、毎回canvas.renderAll()を呼んでいないか。都度呼ぶとオブジェクト数×ループ回数分の再描画が走りUIがフリーズする。ループ外で最後に1回だけ呼ぶ | 1 |
| 18 | ログ | Errorオブジェクトを文字列化する際にJSON.stringifyを使っていないか。Errorのmessage/name/stackは非列挙プロパティのためJSON.stringifyでは`{}`になる。`instanceof Error`で判定し`error.name + error.message`等で展開する | 1 |
| 19 | ログ | 各ファイルで`new SimpleLogger()`していないか。ロガーは`js/core/logger.js`に集約定義し、各ファイルではグローバル変数として参照する | 1 |
| 20 | 非同期 | `_comfyUIExecProvider`等のグローバル変数に依存するURL/認証情報を、長時間のawait（WebSocket待機等）をまたいで使っていないか。非同期処理中に別タスクがグローバル変数を上書きし、別プロバイダのURLに接続してしまう。関数冒頭でサーバーアドレス・認証情報をローカル変数にキャプチャして使う | 2 |
| 21 | fallback | グローバル変数が未設定のときデフォルト値（`'local'`等）にフォールバックしていないか。`_comfyUIExecProvider`がnullのときキーを`'local'`にする、`comfyObjectInfoListMap.get(key)\|\|comfyObjectInfoListMap.get('local')`のように別キーにフォールバックする等はすべて暗黙のfallback。awaitなしで呼ばれたasync関数ではグローバル変数が既にクリアされているため、呼び出し元で値を事前キャプチャして引数で渡す | 1 |
| 22 | 履歴 | オブジェクト属性を`obj.left=100`のように直接代入するUIハンドラで`commitHistory()`/`commitHistoryDebounced()`を呼んでいるか。canvasイベントが発火せず、自動コミット網（`_set`フック）も直接代入は検知できないため履歴に残らず、次のUndoが1つ前の操作まで巻き戻る。連続入力（スライダー・キーリピート）は必ずdebounce版を使う | 1 |
| 23 | 履歴 | `changeDoNotSaveHistory()`の解除漏れがないか。非同期コールバックをまたぐ場合はtry/finallyで囲む。解除漏れは以降の全操作が履歴に残らなくなり、Undoが大きく巻き戻る。同期処理は`withoutHistory(fn)`を使う | 1 |
| 24 | 履歴 | 一時的なUI用オブジェクト（クロップ枠等）に`setNotSave`/`excludeFromLayerPanel`/`excludeFromExport`を設定し、`addByNotSave`/`removeByNotSave`で追加削除しているか。通常のadd/removeでは無意味な履歴が積まれる | 1 |
| 25 | 履歴 | 画像を差し替える効果（glfxフィルタ等）で、非同期の完了後にコミットしているか。`setElement()`は`set()`を通らないため自動コミット網で検知できず、抑止スコープも非同期コールバックには効かない。プレビューのまま履歴に残らないと次のUndoが1つ前の操作まで巻き戻る | 1 |
