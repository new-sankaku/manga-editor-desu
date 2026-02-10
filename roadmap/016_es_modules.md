# 016: ES Modules化

## 規模: XL (特大)

## 概要
グローバル変数ベースの現在のアーキテクチャをES Modulesに段階的に移行し、
依存関係の明確化と名前衝突の排除を実現する。

## 該当箇所
- `js/`配下の全ファイル（約150ファイル）
- `.eslintrc.json`（`sourceType: "script"` → `"module"`）

## 現状の問題
- 全ての関数・変数がグローバルスコープに存在
- ESLintで`no-undef: off`にせざるを得ない（グローバル参照のため）
- ファイル間の依存関係が暗黙的で、スクリプトの読み込み順序に依存
- 同名関数やスペルの揺れで名前衝突のリスクがある
- IDEのコード補完やリファクタリング支援が効きにくい

## 修正内容
### 移行戦略（段階的アプローチ）

#### Phase 1: ユーティリティ層
- `js/core/logger.js` → export/import
- `js/core/util/` → export/import
- `js/db/` → export/import
- これらは他ファイルへの依存が少なく移行しやすい

#### Phase 2: データ層
- `js/svg/`（SVGデータ）→ export
- `js/ai/prompt/`（プロンプトデータ）→ export

#### Phase 3: 機能モジュール
- `js/sidebar/`の各機能 → クラスまたはモジュールに
- `js/ai/`の各AI連携 → モジュール化
- `js/layer/` → モジュール化

#### Phase 4: コア層
- `js/fabric/fabric-management.js` → イベントモジュール
- `js/shortcut.js` → ショートカットモジュール
- `js/canvas-manager.js` → キャンバスモジュール
- `js/project-management.js` → プロジェクトモジュール

### 互換レイヤー
- 移行期間中は`window.functionName = functionName`でグローバルからもアクセス可能に
- 全ての移行完了後に互換レイヤーを削除

## 前提条件
- 015（ビルドパイプライン）の完了が先行する

## 影響範囲
- プロジェクト全体
- 最も大規模な変更であり、長期的な移行プロジェクトとなる
