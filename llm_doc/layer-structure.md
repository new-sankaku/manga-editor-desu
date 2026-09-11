# レイヤー構造

## ホワイトボード往復

`js/layer/whiteboard-integration.js` がpanel/imageのアクションバーから8190を別タブで開く。`wb.apply`は対象ページ・GUIDを照合してから一時画像を置き、本採用時だけ`saveStateByManual()`する。`wbBoardId`、`wbAssetId`、`wbImageUrl`は`commonProperties`に含まれるため、通常のプロジェクト保存・再読込で保持される。破棄では一時画像を削除し、隠していた旧画像を戻す。

## オブジェクト間のリンク機構
| リンク方式 | 方向 | 用途 |
|-----------|------|------|
| `parent.guids[]` | 親→子 | 親が子オブジェクトのGUID一覧を保持 |
| `child.relatedPoly` | 子→親 | 子が親Polygonへの参照を保持 |
| `child.clipPath` | 属性 | 親Polygon形状でマスク |

## 構造図
```
キャンバス (canvasGuid)
├─ Panel1 (guid:A, guids:[B,C])
│  ├─ ImageB (relatedPoly:Panel1, clipPath:Polygon)
│  └─ ImageC (relatedPoly:Panel1, clipPath:Polygon)
└─ SpeechBubble (guid:D, guids:[E,F], customType:speechBubbleSVG)
   ├─ Textbox (guid:E, customType:speechBubbleText)
   └─ Rect (guid:F, customType:speechBubbleRect)
```

## リンク確立の流れ
1. `putImageInFrame()` → `findTargetFrame()`でフレーム特定
2. `moveSettings(img, poly)`:
   - `updateClipPath()` → clipPath設定
   - `img.relatedPoly = poly` → 双方向参照
   - `img._clipPathHandler` → イベントハンドラを保存
   - イベントリスナー登録（moving/scaling/rotating/skewing/modified）
   - `img.removeClipPathListeners()` → リスナーのみ解除（guids維持）
   - `img.removeSettings()` → 完全解除（guidsも削除）
3. `setGUID(parentFrame, img)` → `parent.guids[]`に追加

## updateClipPath(img, poly)
- 親Polygonの形状からclipPathを動的生成
- オブジェクト移動/変形時にリスナー経由で自動呼び出し
- 部分削除後にリスナーを解除しないとclipPathが復活する

## リンク削除の流れ
1. `img.removeSettings()`を呼び出し
2. `removeGUID(relatedPoly, img)` → guids配列から削除
3. イベントリスナー削除
4. `relatedPoly`と`removeSettings`プロパティを削除

`removeSettings()`は`clipPath`そのものを消さない。表示制限ごと外すときは
`releasePanelLink(child)`（`panel-manager.js`）を使う。中で`removeSettings()`を
呼んでから`clipPath=undefined`まで行う。

## リンクを追随させる場所は2つのイベントだけ

`clipPath`は`absolutePositioned:true`で、**置いた時のコマの形と位置のまま固定される**。
`updateClipPath()`は`relatedPoly`から作り直すため、絵だけを動かしても切り抜きは
元のコマの位置に残る。配置・移動・複製・削除の各所へ直しを入れると必ず漏れるので、
次の2つのイベントに寄せてある（`panel-manager.js`のDOMContentLoaded内）。

| イベント | 処理 | 目的 |
|---------|------|------|
| `object:modified` | `relinkToPanelUnderObject(obj)` | 中心座標から所属コマを判定し直す。別のコマなら乗り換え（`releasePanelLink`→`moveSettings`+`setGUID`）、どのコマにも入っていなければ表示制限を外す |
| `object:removed` | `releasePanelChildren(panel)` | コマを消したとき、`guids`の子の表示制限と親子リンクを外す。**子そのものは消さない** |

- 乗り換えの対象は「今`relatedPoly`にコマ（`isPanel`）が入っている子」だけ。
  トーンや図形を親にしているものは触らない
- 複数選択（`activeSelection`）中の子は`left/top`がグループ基準になるため、
  中心は`getAbsoluteCenterPoint()`で取る
- `object:removed`は`canvas.clear()`でも1件ずつ飛ぶ。Undo/Redoの復元は
  一度空にしてから作り直すため、`isHistoryRestoreInProgress()`で抜ける。
  復元後は`resetEventHandlers()`が`guids`からリンクを張り直すので、
  「コマを消す→Undo」で子の切り抜きも戻る
- コマの中身を消さずに残すのは、消すと取り消しづらいため。
  吹き出しは`fabric-management.js`の`object:removed`で親子ごと消えるが、
  絵はコマから出しても意味を持つので揃えていない

## どのコマに入るかの判定

`findTargetFrame(x,y)`（落とし先）も`findPanelUnderPoint(x,y,除外)`（乗り換え先）も、
`isPointInShape()`でコマの**実際の形**を見る。外接矩形で見ると、斜めのコマや
重なったコマではポインタが乗っていないコマに入る。
polygon以外（rect/circle/path）は形の情報を持たないため外接矩形のまま。

## ロックと非表示

- **ロックは`selectable`**。`lockMovementX`等ではない（`llm_doc/review-checklist.md` #47）
- コマは`selectable:false`で生まれる。キャンバス側には理由が出ないため、
  `mouse:over`でカーソルを`not-allowed`にし、押されたら`hintLockedLayer(obj)`で
  レイヤー行の鍵に`.layer-lock-hint`を付けて4秒だけ点滅させる。
  解除の入口は`putMoveLockButton`の鍵1つだけなので、そこへ目を向けさせる
- **非表示のオブジェクトは選択しない。** fabricの当たり判定（`_checkTarget`）が
  `visible`を見るためキャンバスからは掴めないが、レイヤー行のクリックは
  `setActiveObject()`を通るので行側でも弾く。`visibleChange()`は非表示にするとき
  選択を外す。外さないとハンドルだけが宙に残り、Deleteで見えないものが消える。
  `selectable`/`evented`は触らない（`evented`は`commonProperties`に無く保存されない）

## 画像置き換え時の注意
- `layer.relatedPoly`で親Polygonを取得してから新画像を配置
- 元画像は`saveHistory=false`を設定してから削除（履歴に残さない）

## AIタスク進捗管理
`generation-task-manager.js`の`aiTaskMap`でAIタスク状態をグローバル管理する。
`updateLayerPanel()`がDOM全再構築するため、状態をグローバルに保持し毎回再描画する。

### aiTaskMapのデータ構造
```javascript
{taskId, canvasGuid, layerGuid, taskType, status, order, stepValue, stepMax}
```
- `taskType`: T2I, I2I, UP, BG, IP, ANG, TAG
- `status`: waiting → running

### ライフサイクル
1. `registerAiTask(layerGuid, taskType)` → タスク登録（status:waiting）
2. `setCurrentAiTask(taskId)` → 実行開始（status:running）、各プロバイダのqueue.add()内で呼ぶ
3. `updateAiTaskProgress(taskId, value, max)` → ステップ進捗更新
4. `removeAiTask(taskId)` → 完了/キャンセル時に削除、`.finally()`で呼ぶ

### レイヤーパネル描画
`executeUpdate()`内で`renderAiTaskIndicators(detailsDiv, layerGuid)`を呼び出し。
進捗更新は`refreshAiTaskIndicator(taskId)`でDOM直接更新（全再構築を避ける）。

### ページ切り替え対応
`aiTaskMap`に`canvasGuid`を保持。`getAiTasksForLayer()`で現在のキャンバスのタスクのみ取得。
