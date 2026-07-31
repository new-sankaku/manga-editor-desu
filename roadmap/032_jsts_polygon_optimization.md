# 032: JSTSポリゴン計算の高速化

## 規模: M (中)

## 概要
フリーハンド吹き出しのマージ・ナイフツールのコマ分割で使用しているJSTS（Java→JSトランスパイル）を、軽量な代替手法に置き換えて高速化する。

## 該当箇所
- `js/sidebar/speechBubble/speech-bubble-freehand.js` — 吹き出しの重なり判定・マージ (`createJSTSPolygon`, `unionGeometries`, `mergeOverlappingShapes`)
- `js/sidebar/panel/knife/knife-split-engine.js` — ナイフツールのポリゴン分割 (`Polygonizer`)
- `js/core/util/fabric-util.js` — ClipPath用の辺検出 (`detectEdgesWithJSTS`)
- `js/fabric/fabric-management.js` — mouse:up時のJSTS呼び出し、object:moving/scalingでのジオメトリ更新

## 現状の問題
- JSTSはJavaからのトランスパイルで本質的に重い
- ベンチマーク結果: 50ポリゴン(各32頂点)の重なり判定+マージで **6343ms → 228ms (27.8x改善可能)**
- フリーハンド吹き出しを多用すると数百ms〜秒単位の遅延が発生する
- `object:moving`/`object:scaling` でも毎回JSTSジオメトリを再計算している

## 改善案

### 案A: BBox事前フィルタ + Sutherland-Hodgmanクリッピング
- バウンディングボックスで明らかに交差しないペアをスキップ（O(n)→大幅削減）
- Sutherland-Hodgmanアルゴリズムの直接実装でポリゴンマージ
- JSTSの`intersects`/`union`/`simplify`を置き換え
- **ベンチ結果: 228ms (96%改善)**

### 案B: GEOS-WASM
- C言語のGEOSライブラリをWASM化したもの
- JSTSと同等の機能を高速に提供
- ライブラリサイズが大きい（数百KB）のが懸念
- **ベンチ結果: 228〜368ms相当**

### 推奨: 案A（BBox + Sutherland-Hodgman）
- 外部依存なし、ライブラリサイズ増加なし
- ベンチマークで最も高速

## ベンチマーク
- `sample/bench-06-jsts-polygon.html` で実測可能
- 5回実行の外れ値除外3回平均: 現行 6343ms → 改善案A 228ms

## 実装手順
1. `speech-bubble-freehand.js` の `createJSTSPolygon` / `unionGeometries` を代替実装に置き換え
2. `mergeOverlappingShapes` のBBox事前フィルタ追加
3. `knife-split-engine.js` の `Polygonizer` を代替実装に置き換え
4. `fabric-util.js` の `detectEdgesWithJSTS` を代替実装に置き換え
5. `updateJSTSGeometry` / `clearJSTSGeometry` の更新
6. JSTSライブラリの読み込み除去（不要になった場合）

## 注意点
- ポリゴンの自己交差や不正ジオメトリのハンドリングはJSTSが堅牢なので、エッジケースのテストが重要
- `jsts.simplify.TopologyPreservingSimplifier` の代替も必要
- `jsts.precision.GeometryPrecisionReducer` の代替も必要
- ナイフツールの `Polygonizer` は複雑なので段階的に移行推奨
