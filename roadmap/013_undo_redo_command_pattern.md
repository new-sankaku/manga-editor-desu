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

---

## 実現可能性の検討

### 結論: 技術的には可能だが、実用上かなり困難

### 現在の仕組み（おさらい）
毎回 `canvas.toJSON()` で全オブジェクトをシリアライズ → `stateStack` に積む → Undo時は `canvas.loadFromJSON()` で丸ごと復元。ただし`imageMap`でハッシュ化して画像データは重複排除済みなので、各状態のサイズ自体はそこまで巨大ではない。

### コマンドパターンが難しい理由

#### 1. `loadFromJSON` がオブジェクトを再生成する
Fabric.jsの `loadFromJSON()` はJSONから新しいオブジェクトインスタンスを生成する。つまりUndo前のオブジェクト参照とUndo後の参照は別物。コマンドパターンは「同じオブジェクトに対して execute/undo する」前提だが、Fabric.jsはその前提と相性が悪い。

#### 2. 変更前の状態を取得する手段がない
`ModifyObjectCommand` には「変更前の値」と「変更後の値」が必要。しかしFabric.jsの `object:modified` イベントは変更後の状態しか提供しない。変更前の値を取得するには、`mouse:down` 時点で全プロパティをスナップショットしておく必要がある。

#### 3. このプロジェクト固有の複雑さ
```
親Polygon (guids:[B,C])
├─ 子Image (relatedPoly → 親, clipPath, イベントリスナー)
└─ 子Image (relatedPoly → 親, clipPath, イベントリスナー)
```
- `relatedPoly`（子→親の参照）
- `clipPath`（動的に生成されるマスク）
- イベントリスナー（moving/scaling/rotating/skewing/modified）
- speechBubbleのテキスト参照

これらはJSONにシリアライズできないランタイム参照。Undoのたびに `resetEventHandlers()` で再構築している。コマンドパターンでもこの再構築は避けられない。

#### 4. 呼び出し箇所が多すぎる
`saveStateByManual()` がプロジェクト全体に散らばっていて、それぞれが「何を変更したか」の情報を持っていない。全箇所を「適切なCommandオブジェクトの生成」に書き換える必要がある。

#### 5. `changeDoNotSaveHistory` パターンの移行
現在の「履歴一時停止 → 複数操作 → 再開 → 手動保存」パターンが大量にある。これらすべてを `GroupCommand` に変換する必要があるが、操作の種類ごとに異なるCommandクラスが必要になる。

### 現実的な代替案
`imageMap`によるハッシュ化で既に最大の問題（画像データの重複）は解決済み。残りの課題に対しては:

| 課題 | 現実的な対策 |
|------|-------------|
| メモリ消費 | `stateStack`の上限を設ける（古いものを破棄） |
| 復元速度 | 差分圧縮（前の状態との差分だけ保存） |
| `imageMap`が縮まない | 参照カウントで未使用データを解放 |

スナップショット方式のままで最適化する方が、コマンドパターンへの全面書き換えよりはるかに現実的。

### まとめ
- コマンドパターン自体はFabric.jsでも不可能ではない
- ただしFabric.jsの設計思想（JSON丸ごとシリアライズ/デシリアライズ）と根本的に相性が悪い
- このプロジェクトの複雑なオブジェクト関係（clipPath, relatedPoly, guids）がさらに難易度を上げている
- **ロードマップ013は「夢はあるが現実的ではない」案と判断**
- 代わりにスナップショット方式の最適化（スタック上限、差分圧縮、imageMap GC）の方が費用対効果が高い
