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

`updateContent()`は`data-i18n`要素に対し`element.innerHTML = translation`するだけで、
**属性の翻訳には対応していない**。`data-i18n="[title]keyName"`のような記法は無効で、
キー文字列がそのまま本文に差し込まれ`material-icons`のリガチャが壊れる。
ツールチップは`data-tip`属性に置き、`addTooltipsByAttribute()`（tippy.js）で登録する:
```html
<i class="material-icons" data-tip="keyName">tune</i>
```
`setLanguage()`が`removeTooltips()`→再登録まで面倒を見るため、要素を増やしても
登録処理を書き足す必要はない。

### 後から差し込んだDOMへの翻訳適用
モーダルやフローティングウィンドウを`insertAdjacentHTML`等で後から追加した場合、
その中の`data-i18n`要素は起動時の`updateContent()`より後に生えるため未翻訳になる。
自前で翻訳を当てるときは以下を守る:

- **走査範囲を挿入したコンテナ配下に限定する**。`document.querySelectorAll('[data-i18n]')`
  で全体を走査すると、既に翻訳済みの他モジュールのUIまで巻き込んで上書きする。
- **`textContent`ではなく`innerHTML`を使う**。翻訳値には`&#128295;`のような
  HTML実体参照やタグが含まれるものがあり、`textContent`だとそれが文字列のまま表示される
  （`updateContent()`本体も`innerHTML`）。

```javascript
const root=$('fm-modalOverlay');
root.querySelectorAll('[data-i18n]').forEach(el=>{
el.innerHTML=i18next.t(el.getAttribute('data-i18n'));
});
```

## プリセット型サイドバーパネル（preset-panel.css）
「プリセットを選んで設定を調整する」パネル（効果・ペン・トーン・画像テキスト）の共通構造。
一覧の出し方が2通りある:

| 型 | 使うパネル | 理由 |
|----|-----------|------|
| 一覧をパネルに常時置く | 効果 | 押した後の挙動が4通りあり、グループ見出しで違いを示す必要がある |
| 今のプリセットだけ置く（`preset-current`） | ペン・トーン・画像テキスト | 一度に使うのは1つだけ。一覧を常時置くと設定が画面外へ押し出される |

### A. 一覧を常時置く型

```html
<div class="left_area preset-panel" id="..." style="display: none;">
  <div class="area-header preset-panel-header">
    <span class="pp-title" data-i18n="..."></span>
    <a class="pp-help" href="..." target="_blank" data-tip="help"><i class="material-icons">help_outline</i></a>
  </div>
  <div class="preset-panel-body">          <!-- ここだけがスクロールする -->
    <div class="preset-group-header">
      <span data-i18n="..."></span>
      <span class="preset-group-hint" data-i18n="..."></span>
    </div>
    <div class="preset-section">           <!-- 適用範囲が効く範囲を囲みで示す -->
      <div class="preset-list">
        <button class="preset-item">
          <span class="preset-item-name">
            <span data-i18n="..."></span>
            <i class="material-icons preset-item-mark" data-tip="...">tune</i>
          </span>
          <img class="preset-item-thumb" src="..." alt="">
        </button>
      </div>
    </div>
    <div id="..-settings"></div>           <!-- 一覧を消さず下に出す -->
  </div>
  <button class="preset-panel-foot" data-action="..."></button>
</div>
```

守る点:
- **一覧は1列**。2列にするとサムネイルが小さくなり、Color2BW系4種のような
  見た目でしか区別できないプリセットが判別不能になる
- **一覧に`max-height`を付けない**。パネル本体（`preset-panel-body`）だけを
  スクロールさせる。一覧側にも付けると二重スクロールになる
- **設定は一覧と入れ替えず下に出す**。入れ替えると他のプリセットへ切り替えられなくなる
- **押した後の挙動が違うものには`preset-item-mark`を付ける**
  （`tune`=設定してから適用 / `visibility`=プレビュー付き / `open_in_new`=別ウィンドウ）
- 適用範囲など「対象を選ぶUI」は、それが効く項目だけを含む`preset-section`の内側に置く
- 文字を入れてから実行する型（プロンプトパネル）は`preset-section`の中に
  `preset-field-label` / `preset-field-input` / `preset-check` /
  `preset-sub-button`（前段の操作） / `preset-apply-button`（主操作） /
  `preset-status`（実行中の表示）を並べる。適用範囲は効果と同じ
  `effect-scope-label` + `input-group-multi effect-scope-group`を使い、
  パネルごとに見た目を作り分けない
- **チェックボックスの`<label>`に`data-i18n`を付けない。** `updateContent()`が
  `innerHTML`ごと差し替えて`<input>`が消える。内側に`<span data-i18n>`を置く

### B. 今のプリセットだけ置く型（preset-panel.js）

```html
<div class="left_area preset-panel" id="tool-area" style="display: none;">
  <div class="area-header preset-panel-header">
    <span class="pp-title" data-i18n="side-label-pen"></span>
  </div>
  <button class="preset-current" id="penPresetCurrent"
          data-action="openPresetPicker" data-preset-kind="pen" data-tip="presetCurrentHintToggle">
    <span class="preset-current-row">
      <span class="preset-current-name" data-i18n="presetNotSelected"></span>
      <span class="preset-current-swap">
        <i class="material-icons">unfold_more</i><span data-i18n="presetChange"></span>
      </span>
    </span>
    <img class="preset-current-thumb" alt="" hidden>   <!-- 未選択の間は出さない -->
  </button>
  <div class="preset-panel-body" id="tool-settings"></div>   <!-- ここだけがスクロールする -->
</div>
```

一覧・見出し・サムネイルは`PRESET_PANELS`（`js/ui/preset-panel.js`）に1か所だけ持ち、
カードもピッカーも同じ定義から作る。項目を増やすときはここだけを直す。

守る点:
- **カードの更新は各マネージャが元から持つ「activeを付け外しする1か所」からだけ呼ぶ**
  （`switchPencilType` / `switchMangaTone` / `switchText2Ui`）。切り替え経路ごとに
  `presetPanelSetActive()`を書き足すと更新漏れになる。
  `clearPenActiveButton()`/`clearActiveToneButton()`は`presetPanelClearActive()`の入口として残す
  （`ModeManager.pencil.disable()`等、パネル外からも呼ばれるため）
- **使用中かどうかをカードに出す**（`.preset-current.is-active`）。一覧を畳んだ分、
  ここを省くと描画モードに入っているかがパネルから読み取れなくなる
- **未選択の間はプリセット名を出さない**（`presetNotSelected`）。最初の1件を
  既定として見せると、押していないものが選ばれているように誤認させる
- **選び直しの結果はボタン時代と同じ**。使用中のものをもう一度選べばペン／トーンは終了する。
  一覧を畳むとこれが見えなくなるため`data-tip`で示す

## プリセットピッカー（preset-picker.js）
項目数が多く`<select>`では選びにくい一覧をポップアップで選ばせる。
`<select>`を値の保持元として残したまま、見た目だけ差し替えるのが基本形:

```javascript
PresetPicker.openFromSelect($("glfxFilter"), getText("glfxFilterPickerTitle"));
```

`openFromSelect()`は`<option>`から一覧を組み立て、選択時に`select.value`へ代入して
`change`イベントを発火する。**既存のchangeハンドラがそのまま動く**ため、
項目を増やすときは`<select>`だけを直せばよい（一覧を二重に持たない）。

任意の一覧を出す場合:
```javascript
PresetPicker.open({
  title: getText("..."),
  items: [{value:"a", label:"A", hint:"説明"}],
  currentValue: "a",
  onPick: function(value){ /* ... */ }
});
```

閉じる操作は「×ボタン」「Escape」「ピッカーの外をクリック」の3つ。
外側クリックは`document`のmousedown（capture）1か所で判定する
（暗幕はパネルの右側しか覆っていないため、暗幕への`click`だけでは
サイドバー側のクリックを拾えない）。`pointerdown`ではなくmousedownなのは、
pointerdownの時点で暗幕を消すと直後のmousedownが下のキャンバスに届くため。

注意点:
- カードに表示中の名前は`<option>`のtextContentから写す。名前を別に持つと
  項目追加時の修正漏れになる
- 写した表示名は`updateContent()`の対象外なので、言語切替時に取り直す
  （`changeLanguage()`から`glfxSyncFilterCard()`を呼んでいる）
- 後から`innerHTML`で差し込んだ`data-i18n`要素は`applyLabelTranslations()`では
  翻訳されない（あちらは`data-i18n-label`専用）。`updateContent()`を呼ぶ

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

操作の分担:

| 操作 | 関数 | 結果 |
|------|------|------|
| 種類を選ぶ | `switchText2(type)` | 選択中の画像テキストがあればその現物を差し替え。無ければ設定を切り替えるだけ |
| 挿入する | `text2Insert()` | ここだけがキャンバスに1つ増やす |
| 値を変える | `updateText2()` | 編集対象（`t2GetCurrentObject()`）を作り直す。対象が無ければ何もしない |

守る点:
- **「選ぶ」で増やさない**。選ぶたびに新規作成すると、既定位置(50,100)固定のため
  同じ場所に重なって増え、見た目が変わらないまま履歴とレイヤーだけが増える
- **`t2_xxx_deleteSvg()`はキャンバスから消さない**。組み立て用変数と
  `nowT2XxxStr`をnullにするだけ。現物を消すのは`t2BeginReplace()`
- **`imageTextParams`はDOMの入力要素から集める**（`t2CollectParams()`）。
  `sidebarValueMap`は利用者が触った項目しか持たないため、そこから集めると
  未変更の項目が欠け、別のオブジェクトを選び直したときに前の値が画面に残る
- **選び直しでは種類が同じでも必ず値を入れ替える**。`nowText2===type`のときに
  何もしないと、アアアを選んだあとイイイを選んでもアアアの値が表示され続ける
- **textareaの中身をHTMLに埋め込まない**。`addTextArea()`は翻訳された既定文
  専用で、利用者の入力を埋めると`</textarea>`を含む文字でDOMが壊れる。
  記憶した文字は`switchText2Ui()`が代入で戻す

## 外部ライブラリ
`file://`で動作させるため、実行に必要なライブラリは`third/`に同梱する。
CDN参照だとオフラインで読み込みに失敗し、jscolorなら色ピッカーが
ただのテキスト入力に化ける。
同梱済み: jscolor / tagify / stacktrace / three.js
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
