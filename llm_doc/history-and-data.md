# 履歴管理と画像データ保存

## 履歴管理（Undo/Redo）
- 削除+追加を連続する場合、中間状態を履歴に残さない
- `changeDoNotSaveHistory()` / `changeDoSaveHistory()`で一時無効化
- 最終結果のみ`saveStateByManual()`で保存

### ドラッグ確定時の履歴保存（fabric-management.js）
`mouse:down`（半透明表示開始）〜`mouse:up`の間はグローバルに履歴保存が無効。Fabricは`object:modified`を`mouse:up`より**先に**発火するため、移動・拡縮・回転の確定は`object:modified`リスナーでは保存されない。代わりに`mouse:up`ハンドラ内で`e.transform.actionPerformed`が真の場合に`saveStateByManual()`を1回呼んで保存している。ドラッグ確定の履歴挙動を変える場合はこの1か所を修正する。
### オブジェクト単位の履歴除外
`saveHistory`プロパティで個別オブジェクトを履歴保存から除外できる。

```javascript
setNotSave(obj)  // obj.saveHistory=false を設定
setSave(obj)     // obj.saveHistory=true に復帰
isSaveObject(event)  // saveHistory==falseなら保存スキップ（undefined/trueは保存対象）
```

**注意:** `isSaveObject`は`event.target.saveHistory`が`false`の場合のみ除外する。`true`と`undefined`はどちらも保存対象。過去に`true`を除外扱いするロジック不備があり、`setSave`で復帰したオブジェクトの移動確定が履歴に残らないバグがあった。

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

**注意:** `setNotSave(obj)`で除外したオブジェクトを恒久的に残す場合は、処理完了後に`setSave(obj)`で必ず戻す。戻し忘れると以後の移動・変形が履歴に残らず、UNDOで巻き戻りすぎる（例: 初回画像追加で画像ごと消える）。復帰済みの箇所: `putImageInFrame`、`initialPutImage`（panel-manager.js）、ナイフ分割の`polygon1`/`polygon2`と失敗時の`panel`再追加（knife-split-engine.js）。`setNotSave`で追加した恒久オブジェクトを新設する場合は必ず`setSave`復帰を対で書く。

### 例: オブジェクト置き換え
```javascript
changeDoNotSaveHistory();
canvas.remove(oldObject);
canvas.add(newObject);
changeDoSaveHistory();
saveStateByManual();
```

### 画像テキスト（T2系エフェクト）の履歴保存
画像テキストは更新のたびに削除+再作成されるが、履歴には最終結果のみ1エントリ保存する。
`js/sidebar/text/custom/custom-text-util.js`の共通ヘルパー経由で行う:

```javascript
t2_removeSvgImage(obj)  // removeByNotSaveで履歴抑止しつつ削除
t2_addSvgImage(svgNode,left,top,onCreated)  // 履歴抑止でadd→saveStateByManualで1エントリ保存
```

addは`FileReader`+`fabric.Image.fromURL`の非同期コールバック内で実行されるため、
抑止フラグの操作は全てコールバック内の同期ブロックに収めている（非同期跨ぎの抑止は禁止）。

### ボトムバーサムネイルの更新（bottom-bar.js）
編集時のサムネイル反映は`saveState()`とundo/redo完了時の`btmScheduleThumbnailRefresh()`（500msデバウンス）の1機構に集約。
軽量なcanvas.toDataURL（縮小倍率）で`<img>`と`btmProjectsMap`の`imageLink`のみ更新し、`blob`（保存データ）は触らない。
`blob`の更新はページ切替・自動保存時の`btmSaveProjectFile`が担当。ページ切替（`chengeCanvasByGuid`）開始時は`btmCancelThumbnailRefresh()`で古いページへの誤反映を防止している。

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
```

### 設定の自動保存
`initSettingsAutoSave()`でUI要素のinput/changeイベントを監視。500msデバウンスで自動保存（`settingsAutoSaveCheckbox`がON時のみ）。

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
- `canvas_info.json` … キャンバスサイズ
- `HASH.img` … 画像データ（ハッシュで重複排除）
- `preview-image.jpeg` … プレビュー

### プロジェクト読み込み（project-management.js）
ロードボタン（Ctrl+Oも同じボタンをclick）の1ハンドラが起点。`multiLoadLz4`/`multiLoadZip`/`processZip`は各ページをボトムバーに登録し、**最初に登録したページのGUIDを返す**。ハンドラは読み込み完了後、サムネイルクリック時と同じ手順（`stateStack.length>=btmSaveStateThreshold`なら現ページを`btmSaveProjectFile`で保存→`chengeCanvasByGuid`→`btmUpdateHandleText`）で1ページ目をキャンバスに表示する。auto-save復元（`recoverPages`）は戻り値を使わず`currentPageGuid`を自前で復元する。

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
