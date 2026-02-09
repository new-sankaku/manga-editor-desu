# 013: Undo/Redoのコマンドパターン化

## 規模: L (大)

## 概要
現在のUndo/Redoはキャンバス全体のシリアライズ状態をスタックに積む方式。
コマンドパターンに変更し、メモリ効率と操作速度を大幅に改善する。

## 該当箇所
- `js/layer/image-history-management.js`

## 現状の問題
- 毎回`canvas.toJSON()`でキャンバス全体をシリアライズしている
- 高解像度画像を多数含むページでは1状態あたり数MBのメモリを消費
- 状態スタックが深くなるとブラウザのメモリ上限に達しやすい
- Undo/Redo実行時のデシリアライズに時間がかかる
- `imageMap`と状態スタックの同期管理が複雑

## 修正内容
### Phase 1: コマンドインターフェースの定義
- `Command`基底クラス（`execute()`, `undo()`, `redo()`メソッド）
- 各操作タイプのコマンド実装:
  - `AddObjectCommand` / `RemoveObjectCommand`
  - `ModifyObjectCommand`（位置、サイズ、回転等の変更）
  - `ReorderCommand`（レイヤー順序変更）
  - `GroupCommand`（複数操作のアトミック化）

### Phase 2: 既存コードの移行
- `saveStateByManual()`の呼び出し箇所をコマンド生成に置き換え
- `changeDoNotSaveHistory` / `changeDoSaveHistory`パターンをGroupCommandに統合
- imageMapの変更もコマンドとしてトラッキング

### Phase 3: 最適化
- コマンドの圧縮（同一プロパティの連続変更をマージ）
- メモリ上限の設定と古いコマンドの自動破棄

## 影響範囲
- 全てのキャンバス操作（追加/削除/変形/レイヤー操作）
- プロジェクト保存/読み込み（状態復元方式の変更）
- 大規模な変更のため段階的な移行が必須
