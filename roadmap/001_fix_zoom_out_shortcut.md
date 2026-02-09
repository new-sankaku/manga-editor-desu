# 001: ズームアウトショートカットのバグ修正

## 規模: S (小)

## 概要
`Ctrl+9`のズームアウトショートカットが、実際には`zoomIn()`を呼び出しているバグを修正する。

## 該当箇所
- `js/shortcut.js` 83-84行目

## 現状の問題
```javascript
hotkeys(hotkeysMap.zoomOut,'all',function (e) {
zoomIn(); // zoomOut() であるべき
e.preventDefault();
});
```

## 修正内容
- `zoomIn()` を `zoomOut()` に変更する

## 影響範囲
- ショートカット操作のみ。他の機能への影響なし。
