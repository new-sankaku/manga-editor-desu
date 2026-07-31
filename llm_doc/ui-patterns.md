# UIパターン

## DOM操作ユーティリティ（ui-util.js）
```javascript
const $=(id)=>document.getElementById(id);
hideById(id) / showById(id)
toggleVisibility(target)
selectedById(ids) / unSelectedById(id)
```

## EventDelegator（event-delegator.js）
document-levelのクリック委譲。`data-action`属性でハンドラを呼び分ける。
```html
<button data-action="flipHorizontally">Flip</button>
```
```javascript
EventDelegator.register('flipHorizontally',function(el,e){...});
```

## Toast通知（toast.js）
```javascript
createToast(title,messages,time=4000)
createToastError(title,messages,time=4000)
```
- 成功: `toast-nier`テーマ、エラー: `toast-dbd`テーマ
- Bootstrap Toast APIベース

## モーダル
HTML動的挿入＋CSSオーバーレイ。パターン:
- `position:fixed` + `rgba(0,0,0,0.6)` + backdrop blur
- z-index: `var(--z-modal)` / `var(--z-overlay)`
- レスポンシブ: `max-width:720px; width:90%; max-height:80vh`

## スライダー（custom-html-component.js）
```javascript
setupSlider(slider,classname,addButton=true)
```
スライダーにup/downボタンとラベルを自動付与。

## レイヤーパネル更新（layer-management.js）
`updateLayerPanel()`はデバウンス付き（60ms最小間隔）。
```
updateLayerPanel() → 60ms throttle → executeUpdate() → DOM全再構築
```
- GUID階層でネスト表示
- Material Designアイコンでレイヤー種別を識別
- プレビューサムネイル表示

## CSS変数（root.css）
```css
.dark-mode{
  --color-base:#212121;
  --color-secondary:#333333;
  --color-accent:#810000;
  --color-text-primary:#ffffff;
  --odd-layer:#262626;
  --even-layer:#2c2c2c;
  --layer-active-bg:#3a1a1a;
  --layer-active-border:#a03030;
  --btn-bg:rgba(255,255,255,0.07);
  --btn-hover-bg:rgba(255,255,255,0.15);
}
```

## i18n（i18next.js）
HTML属性での翻訳:
```html
<h3 data-i18n="keyName"></h3>
<input data-i18n-placeholder="keyName">
```
JS内:
```javascript
getText("keyName")  // i18next.t()のラッパー
```

## 永続化
| ストア | 用途 |
|--------|------|
| `localforage` | IndexedDB非同期ストレージ（SettingsRepository, auto-save等） |
| `localStorage` | 設定バックアップ、プロバイダ設定 |
- `SettingsRepository`: TTL付きget/set対応
- `localforage.createInstance({name:'xxx'})` で用途別インスタンス

## ModeManager
操作モード切り替え: SELECT, FREEHAND, KNIFE, PEN各種, CROP
```javascript
ModeManager.getCurrent()
ModeManager.MODE.SELECT
```

## 選択オブジェクトと各パネルの同期（object-control-sync.js）
同じ設定（不透明度・線幅・色・フォントサイズ）が複数のパネルに存在するため、
1箇所で変更した値を他へ反映しないと、次にそのパネルを触ったときに
**表示されている古い値へ飛ぶ**。

```javascript
syncObjectControls(activeObject)  // 共通コントロール・テキスト・コマ・吹き出し・画像テキストへ反映
```
- `selection:created` / `selection:updated` で呼ぶ
- いずれかのパネルで値を変更した直後にも呼ぶ
- jscolorのピッカーは`value`代入では見た目が変わらない。`picker.jscolor.fromString(色)`を使う

## 画像テキスト（text-2-manager.js / custom/）
パラメータ変更のたびにSVGをラスタライズして**オブジェクトを作り直す**。
そのままだと変形・重ね順・GUIDが失われるため、共通ヘルパーで引き継ぐ。

```javascript
const position=t2BeginReplace(nowT2XxxStr);   // 変形とindexを退避し履歴を抑止して削除
nowT2XxxStr=t2PlaceImageTextObject(img,'xxx',left,top);  // 退避した内容を適用し元のindexへ戻す
```
- `imageTextType` / `imageTextParams` をオブジェクトに保存し`commonProperties`に含める
- 選択時は`syncImageTextControls()`がサイドバーを該当種類・値に戻し、
  以降の編集がそのオブジェクトに向くよう`t2_xxx_setCurrent()`を呼ぶ
- これがないと**直前に作った1つしか編集できない**

## 外部ライブラリ
`file://`で動作させるため、実行に必要なライブラリは`third/`に同梱する。
CDN参照だとオフラインで読み込みに失敗し、jscolorなら色ピッカーが
ただのテキスト入力に化ける。
同梱済み: jscolor / tagify / stacktrace / chart.js / wordcloud / three.js
（Google Fontsとflag-iconsは未同梱。読み込めなくても代替表示で機能は動く）

## キャンバスの拡大縮小（canvas-manager.js）
`#canvas-container` に CSS の `transform: scale()` をかける方式。
fabric の `viewportTransform` は使っていない。

```
#resizable-container   overflow:auto   ← スクロールするのはこちら
└ #canvas-container    overflow:hidden ← transform:scale() をかける対象
  └ .canvas-container（fabric生成）
    └ #mangaImageCanvas
```

- **スクロール対象を間違えない。** `#canvas-container` は `overflow:hidden` なので
  `scrollLeft`/`scrollTop` を代入しても何も起きない。`getScrollContainer()` を使う
- **`transform-origin` は `top left`。** 中央基準にすると左と上にはみ出した分が
  スクロール範囲に入らず、端まで表示できなくなる
- 拡大縮小は `applyCanvasZoom(倍率)` に集約。表示中心を保つスクロール補正を行う
- `clientWidth`/`clientHeight` は transform の影響を受けない（レイアウト値）。
  `getBoundingClientRect()` は影響を受ける（表示値）

### 画面座標への変換
表示倍率は状態変数ではなく **DOMから実測** する。

```javascript
const scale=getCanvasDisplayScale();  // canvasRect.width / canvas.getWidth()
const screenX=canvasRect.left+logicalX*scale;
```
はみ出し判定は**ビューポート基準**で行う。キャンバス基準にすると、拡大時に
キャンバス右端が画面外にあってもクランプされず、メニューが画面外に出る。
