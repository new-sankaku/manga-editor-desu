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

## フォルダ選択ダイアログ（folder-picker.js）
プロジェクトフォルダを選ぶモーダル。`server_fastapi.py` の `/api/folders` 必須。
```javascript
FolderPicker.open()                  // ダイアログを開く
await FolderPicker.getCurrent()      // 保存済み {path, displayPath, timestamp}
```
- 永続化: `localforage.createInstance({name:'folderPicker'})`、キー `currentProjectPath`
- 閲覧スコープ: バックエンドで $HOME 配下に限定
- メニュー: File > 「プロジェクトを開く」(`#projectFolderOpen`)
- 選択時 `window.ProjectLoader.loadFromFolder(path, displayPath)` を呼ぶ

## プロジェクトローダ（project-loader.js）
選択フォルダ配下の `pages/pXXX_page.json` (XXX は数字) を XXX 数値順にページとして取り込む。仕様は `format.md`。
```javascript
await window.ProjectLoader.loadFromFolder(homeRelativePath, displayPath)
```
- `<選択フォルダ>/pages/` を `/api/files?pattern=^p\d+_page\.json$` で列挙、ファイル名から `parseInt` で数値ソート
- `/api/file` で各 JSON を取得 → `addLayerWithChildren()` で各レイヤーを再帰展開 → `canvas.add` → `btmSaveProjectFile(guid,false)`
- 親 (例: コマ `isPanel=true`) の `children` 配列に子レイヤーを入れる方式。子は canvas に並列 add され、階層は `guids` / `relatedPoly` で保持
- `group` (`type: "group"`) の `children` のみ fabric.Group 内部に統合される
- アセット (画像など) は `assets/...` 相対参照、`/api/file?path=<pagesPath>/<assets相対>` で取得
- 既存 `btmProjectsMap` は全クリアして新規プロジェクトとして再構築
- `pages/` サブフォルダが無い場合は専用エラー (`projectLoaderNoPagesDir`)
