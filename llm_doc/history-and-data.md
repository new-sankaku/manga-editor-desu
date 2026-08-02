# 履歴管理と画像データ保存

## 履歴管理（Undo/Redo）
実装は`js/layer/image-history-management.js`。

### 基本方針
- **1ユーザー操作＝1履歴エントリ**。同一タスク内で発生した複数のcanvasイベントは自動で1件に集約される
- 履歴は非同期コミット（0msタイマー）。同期的に`stateStack`を読む処理の前には`flushHistory()`を呼ぶ
- 直前の状態とJSONが同一なら積まない（重複除去）。そのため`commitHistory()`は空振りしても無害
- 履歴の保存（`captureState`）と復元（`applyHistoryState`）の完了時に`btmScheduleThumbnailRefresh()`でページサムネイルを自動更新する

### API
| 関数 | 用途 |
|------|------|
| `commitHistory()` | 1操作の完了時に呼ぶ。集約＋重複除去つき |
| `commitHistoryDebounced(ms)` | スライダー・連続キー入力・文字入力など連続操作用（既定500ms） |
| `saveState()` / `saveStateByManual()` | `commitHistory()`のエイリアス（既存互換） |
| `flushHistory()` | 保留中のコミットを即時実行。プロジェクト保存やundo前に使用 |
| `captureState()` | 抑止フラグを無視して即時保存。ベースライン確保など特殊用途のみ |
| `withoutHistory(fn)` | **推奨**。fn実行中だけ履歴保存を抑止。try/finallyで例外時も必ず解除 |
| `changeDoNotSaveHistory()` / `changeDoSaveHistory()` | 低レベルAPI。深さカウンタ方式でネスト可 |
| `getHistoryChangeCounter()` | 抑止中も増える変更検知カウンタ（ドラッグ判定に使用） |

### 保存の粒度
連続操作でスナップショットが量産されないよう、記録の単位を操作単位に固定している。

| 操作 | 発火するイベント | 履歴の単位 |
|------|-----------------|-----------|
| ドラッグ移動・拡縮・回転 | `object:moving`等は履歴対象外。`object:modified`が終了時に1回 | ドラッグ1回＝1件 |
| スライダー（不透明度・線幅・フォントサイズ・角度等） | `input`が連続発火 | `commitHistoryDebounced()`で入力停止から500ms後に1件 |
| 矢印キー移動（長押し含む） | `keydown`が連続発火 | 同上。押しっぱなしでも1件 |
| 文字入力 | `text:changed`が1文字ごと | 同上。加えて編集終了時に1件 |
| ボタン1回の操作（重ね順、反転、表示切替等） | なし | `commitHistory()`で即1件 |
| glfxの色彩フィルタ（明るさ・コントラスト・色相・彩度等） | なし（非同期でsetElement） | スライダー停止から700ms後に1件 |
| エフェクトの一括適用（白黒・薄いカラー化・黒強調） | なし（非同期でsetElement） | ページ内の全枚数で1件 |
| 背景色 | なし（canvasの属性） | 入力停止から500ms後に1件 |
| フォント変更 | なし | `commitHistory()`で即1件 |

履歴対象のイベントは`object:added` / `object:modified` / `object:removed` /
`path:created` / `canvas:cleared`のみ。`object:moving`・`object:scaling`・
`object:rotating`は対象外なので、ドラッグ中に保存が走ることはない。

### コミット漏れの保険（自動コミット網）
`fabric.Object.prototype._set`をフックし、`set()`でオブジェクトが変化したら
`canvasDirtyUnlocked`を立てる。`pointerup` / `keyup` / `change`（capture）で
このフラグが立っていれば`commitHistoryDebounced()`を1回だけ予約する。
個別ハンドラで`commitHistory()`を呼び忘れても、操作の区切りで履歴に残る。

- 抑止中（`withoutHistory`内）の変更はフラグを立てない。glfxのライブプレビュー等が
  勝手に履歴化されるのを防ぐため
- `selectable`・`evented`・`lockMovement*`等の操作モード用の属性は`HISTORY_IGNORE_KEYS`で
  除外。ナイフモード切替等で無意味な履歴が積まれるのを防ぐため
- **`obj.left=100`のような直接代入は`set()`を通らないため検知できない。**
  直接代入するハンドラは明示的に`commitHistory()`を呼ぶこと
- **`setElement()`による画像差し替え（glfxフィルタ等）も`set()`を通らない**ため検知できない。
  非同期完了後に明示的にコミットすること
- **canvasの属性（背景色等）はオブジェクトではない**ため検知できない

### 抑止スコープの注意
- 抑止は**深さカウンタ**。内側の`changeDoSaveHistory()`で外側の抑止が解除されることはない
- 非同期コールバックをまたぐ抑止は、コールバック側を`try{}finally{changeDoSaveHistory();}`で囲む
- 抑止中に呼ばれた`commitHistory()`は破棄される。抑止区間の結果を残したい場合は解除後に呼ぶ
- `initImageHistory()`は抑止深さを0にリセットし、必ずベースライン1件を残す

### 復元処理（undo/redo）
- `canvas.loadFromJSON()`が非同期のため、復元中は`isHistoryRestoring`で全保存をブロック
- 復元中の追加undo/redoはキューされ、完了後に順次実行（連打しても履歴が壊れない）
- コールバックはtry/finallyで必ずロック解除。30秒のウォッチドッグつき

### ドラッグ操作
`mouse:down`で抑止＋プレビュー用に`opacity=0.5`、`mouse:up`で復帰。
fabric.jsは`object:modified`を`mouse:up`より**先に**発火するため、
`getHistoryChangeCounter()`の差分で「ドラッグ中に変更があったか」を判定し、
`mouse:up`後に1件だけコミットする。単なるクリックでは重複除去により履歴は増えない。
`originalOpacity`が残っているオブジェクトは`customToJSON()`が元のopacityに戻して保存する。

### 削除+追加を連続する場合
中間状態を履歴に残さない。

### オブジェクト単位の履歴除外
`saveHistory`プロパティで個別オブジェクトを履歴保存から除外できる。

```javascript
setNotSave(obj)  // obj.saveHistory=false を設定
isSaveObject(event)  // saveHistory==falseなら保存スキップ
```

**除外されるオブジェクトの例:**
- 一時的なUI要素（初期メッセージテキスト）
- 吹き出しフリーハンド描画中の一時シェイプ・制御点
- コマ割り背景・プレースホルダー
- ナイフツールのアニメーション線
- AI処理中の一時クローンオブジェクト（c2c, inpaint等）

**関連プロパティ:**
| プロパティ | 用途 |
|-----------|------|
| `saveHistory=false` | 履歴保存から除外 |
| `excludeFromLayerPanel=true` | レイヤーパネルに非表示 |

**履歴を記録せずにadd/removeするヘルパー:**
```javascript
addByNotSave(obj)    // changeDoNotSave→add→changeDoSave
removeByNotSave(obj) // changeDoNotSave→remove→changeDoSave
```

### 例: オブジェクト置き換え
```javascript
withoutHistory(function(){
canvas.remove(oldObject);
canvas.add(newObject);
});
saveStateByManual();
```

### 例: オブジェクト属性の変更（UIハンドラ）
canvasイベントが発火しない属性変更は履歴に残らないため、操作の区切りで明示的にコミットする。
```javascript
activeObject.set("fill",color);
canvas.renderAll();
commitHistoryDebounced();  // スライダー等の連続入力
```
```javascript
canvas.bringForward(activeObject);
canvas.requestRenderAll();
commitHistory();           // 単発のボタン操作
```

## 画像データ保存
- `imageMap`には`data:` URLまたはJSON文字列のみ保存
- `blob:` URLはセッション限りのため保存禁止
- 保存時`convertImageMapBlobUrls()`で`blob:`→`data:`に変換済み
- オブジェクト（2D配列等）は`JSON.stringify()`で文字列化して保存

## パラメータ保存

### ストレージ使い分け
| バックエンド | 用途 |
|-------------|------|
| `localStorage` | アプリ設定、basePrompt、サイドバーツール値（軽量・同期アクセス） |
| `localforage`(IndexedDB) | auto-save、フォント、ワークフロー、統計（大容量・非同期） |

### アプリ設定（project-management.js）
`localStorage`キー`localSettingsData`に全設定を一括JSON保存。

- `SETTINGS_SCHEMA` … UI要素IDとデフォルト値の定義（API URL、キャンバス、パネル色、吹き出し、テキスト等）
- `BASEPROMPT_SCHEMA` … AI生成パラメータ（prompt, negative, seed, cfg, width, height, sampler, steps, model, hr_*）
- `roleAssignments` … プロバイダのロール割り当て

```javascript
saveSettingsLocalStrage(silent)  // 全UIから値を収集→localStorage保存
loadSettingsLocalStrage()        // localStorage→UI要素に復元
applySettingValue(el,val)        // 復元時の値設定。selectはoptionを補ってから選択する
```

### selectの復元（applySettingValue）
モデル一覧などAPI取得後に`<option>`が生成されるselectは、復元時点で選択肢が存在しない。
`el.value=保存値`はマッチするoptionが無いと**無言で`''`になる**ため、そのままだと自動保存で
localStorage側の保存値まで空で上書きされ、選択が二度と戻らない。
`applySettingValue()`は該当optionが無い場合に保存値のoptionを生成してから選択する。
LLMプロバイダの`_populateSelect()`も同じ関数を使い、取得失敗時も選択値を保持する。

### 設定の自動保存
`initSettingsAutoSave()`でUI要素のinput/changeイベントを監視。500msデバウンスで自動保存（`settingsAutoSaveCheckbox`がON時のみ）。
**全項目を一括で保存するため、DOM上で空になっている項目は空のまま保存される。**

### サイドバーツール値（sidebar-ui.js）
localStorageキー別にMap保存。500msデバウンス。
- `sidebarValues` … 汎用ツール設定
- `penValues` … ブラシ設定
- `effectValues` … エフェクト設定

### AI生成パラメータの階層
1. **basePrompt**（グローバル）… `core/settings.js`にデフォルト定義。UI変更で即時反映（`base-event-listener.js`）
2. **per-layer**（オブジェクト属性）… `t2iInit`/`i2iInit`のデフォルト。`-2`=base使用、`-1`=base使用
3. **保存時** … `canvas.toJSON(commonProperties)`でオブジェクト属性としてシリアライズ

### commonProperties（settings.js）
`canvas.toJSON()`で保存されるカスタムプロパティ一覧:
- レイヤー制御: `excludeFromLayerPanel`, `isPanel`, `isIcon`, `customType`, `selectable`
- AI生成: `text2img_prompt`, `text2img_negative`, `text2img_seed`, `text2img_width`, `text2img_height`, `text2img_samplingMethod`, `text2img_samplingSteps`
- GUID連携: `guids`, `guid`, `canvasGuid`
- 吹き出し: `isSpeechBubble`, `speechBubbleGrid`, `speechBubbleScale`等
- 位置復元: `initial`, `clipPath.initial`, `baseScaleX`, `baseScaleY`, `lastLeft`, `lastTop`

### プロジェクトファイル（project-compression.js）
LZ4圧縮で以下を保存:
- `text2img_basePrompt.json` … basePromptのスナップショット
- `state_XXXXXX.json` … キャンバス状態（`customToJSON()`出力）
- `canvas_info.json` … キャンバスサイズ＋原稿サイズ（`pageWidthMm` / `pageHeightMm`）
- `fonts.json` … 使用中フォントのメタ情報（`name` / `type` / `url`）
- `HASH.img` … 画像データ（ハッシュで重複排除）
- `preview-image.jpeg` … プレビュー

**履歴状態の判定は `state_` プレフィックスで行う。** 除外リスト方式にすると
メタファイルを追加するたびに状態として読み込まれてしまう。
読み込み側は `loadLz4BlobProjectFile()` と `generation-task-manager.js` の2箇所。

### 実行環境をまたぐときの注意
- キャンバスの`width`/`height`は**コンテナにフィットさせた後のピクセルサイズ**であり
  ウィンドウ依存。オブジェクト座標もこの空間に入る
- 読み込み時に`resizeCanvas()`が`obj.initial.canvasWidth/Height`を基準に比例スケール
  するため、別環境でもレイアウトは相似形で再現される
- `obj.initial`は再フィットの基準点。`resizeCanvas()`内で更新してはいけない
- 出力ピクセルサイズは**原稿サイズ(mm)×DPI**で決まる（`getCropAndDownloadLink()`）。
  ウィンドウサイズには依存しない
- `devicePixelRatio`は描画バッファにのみ影響し、座標にも出力サイズにも影響しない。
  **画像生成用のデータURL生成でDPIを掛けてはいけない**（環境で送信解像度が変わる）

### フォント（project-font.js）
フォント本体はIndexedDB(`fm-fontStorage`)にありプロジェクトには含まれない。
`fonts.json`に`name`/`type`/`url`を保存し、読み込み時に:
- 登録済み … 何もしない
- 未登録かつ`type==='web'` … `fontManager.registerWebFont(url)`で自動復元
- それ以外（`upload` / `local`）… `missingProjectFonts`に積みToastで明示（黙ってフォールバックしない）

後からフォントを登録すると`applyRecoveredFont()`が該当テキストを再計算して再描画する。
再読み込みは不要。この再描画は履歴に残さない。

保存時は「ローカル登録済みの情報」→「読み込み時に受け取った情報」の順で引き継ぐ。
引き継がないとフォント未登録の環境で保存し直したときに情報が失われる。

### 複数ページ（bottom-bar.js）
`btmProjectsMap` が `{guid: {imageLink, blob}}` を保持し、**Mapの挿入順がページ順**。
ページ切り替えは「現ページを保存 → 対象ページを`loadLz4BlobProjectFile()`」。

- **保存するかの判定は`btmShouldSaveCurrentPage()`（bottom-bar.js）に集約。** 「`btmProjectsMap`に
  登録済み（＝既存ページなのでサムネイル更新が要る）」または「初期メッセージ以外の
  オブジェクトがある」で真。初期メッセージは`isInitMessage:true`で識別する。
  履歴件数（旧`stateStack.length>=2`）で判定すると、キャンバスのリサイズ等で履歴が積まれた
  起動直後の空白ページまでページとして登録されてしまう。ページ切り替え・Templateコマ割り・
  ページ追加・プロジェクト読み込み前の退避・auto-saveはすべてこの関数を通す
- **ページを離れる前に`flushHistory()`が必要。** デバウンス中の変更が確定する前に離れると
  変更が失われる（`btmSaveCurrentPage()`に集約）
- **読み込み中の保存を禁止する。** `isProjectBusy()`が真の間はページ切り替え・ページ削除・
  ページ追加・auto-saveを行わない。読み込み途中のキャンバスを現在ページのblobに
  上書きしてしまうため
- `loadLz4BlobProjectFile()`は冒頭で`cancelPendingHistory()`する。前ページの未確定コミットが
  クリア済みの`imageMap`に前ページの画像を混ぜてしまうため
- **`chengeCanvasByGuid()`のawaitが返ってもキャンバスはまだ構築されていない。**
  内部の`lastRedo()`→`applyHistoryState()`が`canvas.loadFromJSON()`をコールバック方式で
  呼ぶだけで完了を待たないため。直後に`getObjectList()`／`getImageObjectList()`を呼ぶと
  **0件が返る**。ページを開いて中身を触る処理は`isProjectBusy()`がfalseになるまで待つこと
  待ち受けは`btmWaitForPageReady()`（bottom-bar.js）に集約してある
- ページのblobは追加直後だけ`null`。この状態で切り替えるとエラーになるため明示的に弾く
- ページ削除は「表示中なら隣のページへ移動（後ろ優先、最後尾なら前）、全ページが無くなったら
  空ページを表示」。キャンバスに内容を残すと一覧に無いページを編集し続けることになる

### エフェクトの一括適用（sidebar/effect/effect-batch.js）
適用範囲は`effectApplyScope`セレクトで「選択画像 / このページ全部 / 全ページ全部」を切り替える。
1画像への適用は`c2bwApplyToImage` / `c2cApplyToImage` / `enhanceDarkToImage`に集約され、
単体適用と一括適用が同じ経路を通る。

- 対象は`effectIsBatchTarget()`で選別。**非表示・ロック・AI生成中・一時オブジェクト
  （`saveHistory=false` / `excludeFromLayerPanel`）・コマ・アイコンは除外**
- 履歴は`changeDoNotSaveHistory()`〜`changeDoSaveHistory()`で囲み、
  **ページ内の全枚数で1件**。非同期をまたぐため`withoutHistory()`は使えない
- 1枚失敗したら**打ち切って何枚目まで適用したかをToastで出す**。
  握りつぶして次へ進むとどこまで掛かったのか分からなくなる
- 進捗は`OP_showLoading(opts,true)`。`OP_isCancelled()`を画像とページの境界で見る

**全ページ一括はUndoで戻せない。** 履歴はページ単位のキャンバスに紐づくため。
代わりに実行直前の全ページblobを**メモリ上の変数`effectBatchBackup`**へ退避し、
「一括適用前の状態に戻す」ボタン（`effectRestoreBatchBackup()`）で復元する。

**この退避は永続化しない。リロード・タブを閉じた時点で失われる。**
目的は「今やった一括適用を取り消す」ことだけで次のセッションへ持ち越す必要がなく、
中身は全ページのblobで容量が大きいため。永続化するとブラウザに残り続け、
プロジェクトごとのスロット管理・世代上限・古いものの掃除が別途必要になる。
その旨は`effectRestoreBatchHint`（ボタンのツールチップ）でユーザーにも伝える。

リロードせずにプロジェクトを切り替えると退避だけが残るため、
`effectBackupMatchesCurrentProject()`が退避時のページGUIDと`btmGetGuids()`を
突き合わせて別プロジェクトのものを弾く。ページGUID（`canvasGuid`）は
`commonProperties`に含まれ`state_*.json`としてプロジェクトファイルに保存され、
読み込み後も同じ値が復元されるため識別に使える。
判定はボタンの表示制御（`effectRefreshRestoreButton()`）と復元の実行直前の
**両方**で行う。取り違えると現在のプロジェクトが丸ごと置き換わる。

バックアップが無い間はボタンを`disabled`にし、CSS（`:disabled{display:none}`）で
消す。押せないボタンを灰色で置いておかない。
起動直後はページ未読込で判定できないため、`toggleVisibility()`が効果パネルを
開くたびに`effectRefreshRestoreButton()`を呼び直す。

**確認ダイアログは出さない。** 実行は止めずToastで知らせるだけにする
（Toastは`--z-toast:2000`で進捗オーバーレイ`--z-modal:1000`より上に出る）。
**auto-saveのストアは使えない。** 単一スロットを毎回上書きするうえ、
スキップ判定が表示中ページの履歴状態ハッシュなので次のタイマーで確実に潰れる。

### コマのプロンプトの書き込みとページ送り（ai/prompt/prompt-apply.js）
プロンプトパネル（`prompt-manager-area`）のLLM生成（→`ai-system.md`）が作った
プロンプトを、コマ（`isPanel`）の`text2img_prompt`へ書き込む側。
範囲は`storyApplyScope`で「選択中のコマ / このページのコマすべて / 全ページのコマすべて」。
見た目と構造は効果パネルの適用範囲（`effect-scope-group`）と同じものを使う。

- 1コマへの書き込みは`promptApplyToPanel()`に集約。追記も置き換えも同じ経路を通る。
  追記は既存の末尾のカンマを均して`", "`で繋ぎ、既存が空なら区切りを付けない
- **ロック（`selectable=false`）は除外しない。** ひな形が作るコマは既定でロック状態のため、
  効果と同じ基準で除外すると大半のコマが対象外になる
- 選択範囲は`canvas.getActiveObjects()`を見る。`getActiveObject()`だけだと
  複数選択時にActiveSelectionが返り「コマが選択されていません」になる
- カスタム属性への直接代入は`set()`を通らず自動コミット網に検知されないため、
  ページごとに`saveStateByManual()`で1件だけ積む
- ページ送りは`storyForEachPage(loading,stepText,onPage)`に集約。
  `onPage`はページが完全に読み込まれてから呼ばれ、trueを返したページだけ保存する。
  終わったら開始時のページへ戻す
- 送りの前に`btmSaveCurrentPage()`してから`btmGetGuids()`を取り直す。
  未登録のページを開いたまま送ると、切り替えた時点でその内容ごと失われる
- **全ページはUndoで戻せない**（履歴はページ単位のキャンバスに紐づくため）。
  実行前にトーストで明示する。効果の一括適用と違い画像は変わらず文字が入るだけなので、
  全ページblobの退避は持たない

### auto-save（auto-save.js）
`AutoSaveManager`がlocalforage(`autoSaveStorage`)に定期保存。
- デフォルト60秒間隔（10-600秒で設定可能）
- ページごとに圧縮blobとメタデータを保存
- 起動時に`checkRecovery()`で復旧ダイアログ表示

### その他のlocalforageストア
| インスタンス名 | 用途 |
|---------------|------|
| `fm-fontStorage` | ユーザーフォント（buffer, URL） |
| `workflowStorage` | ComfyUIカスタムワークフロー |
| `objectInfoStorage` | ComfyUIノード定義キャッシュ |
| `MangaEditor_Performance` | 生成時間統計 |
| `MangaEditor_PromptFrequency` | タグ頻度分析 |
