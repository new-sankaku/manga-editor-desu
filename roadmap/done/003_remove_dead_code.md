# 003: コメントアウトされたコードの削除

## 規模: S (小)

## 概要
複数のファイルにコメントアウトされた`console.log`やデッドコードが散在しているので整理する。

## 該当箇所
- `js/layer/image-history-management.js` (複数箇所の`// console.log(...)`)
- `js/layer/layer-management.js` (`// console.time(...)`)
- `js/canvas-manager.js`
- `js/fabric/fabric-management.js`

## 修正内容
- コメントアウトされた`console.log`/`console.time`の削除
- 使用されていないデッドコードの削除
- Loggerへの置き換えが必要な箇所は置き換え対応

## 影響範囲
- コードの可読性向上のみ。機能への影響なし。
