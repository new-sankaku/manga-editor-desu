# 011: Fabric.jsイベント管理のリファクタリング

## 規模: M (中)

## 概要
`fabric-management.js`に35以上のイベントリスナーが平面的に並んでおり、
同一イベントに複数のハンドラが登録されている。関心ごとに整理する。

## 該当箇所
- `js/fabric/fabric-management.js`（約645行）

## 現状の問題
- `selection:created`、`mouse:down`、`mouse:up`など同一イベントに複数のハンドラ
- イベントハンドラが番号コメント（1:, 2:, 3:...）で管理されており可読性が低い
- モード（knife, freehand, point, crop, draw）ごとの処理が散在
- 新機能追加時にどのイベントに追記すべきか判断しづらい

## 修正内容
- モードごとにイベントハンドラグループを分離
  - `KnifeEventHandlers`
  - `FreehandEventHandlers`
  - `CropEventHandlers`
  - `SelectionEventHandlers`
- 各グループの有効/無効を`ModeManager`と連動
- 同一イベントの複数ハンドラを1つのディスパッチャに統合

## 影響範囲
- キャンバスの全操作（選択、移動、描画、カット等）
- 慎重なテストが必要
