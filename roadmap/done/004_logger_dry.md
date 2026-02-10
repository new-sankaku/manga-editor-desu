# 004: Loggerの重複コードをDRY化

## 規模: S (小)

## 概要
`SimpleLogger`の各ログメソッド（trace/debug/info/warn/error およびそれぞれのWithStack版）が
ほぼ同一のコードを10回繰り返している。共通処理を抽出してコード量を削減する。

## 該当箇所
- `js/core/logger.js`

## 現状の問題
- 10個のメソッド（trace, debug, info, warn, error, traceWithStack, debugWithStack, infoWithStack, warnWithStack, errorWithStack）がほぼ同一のロジックを持つ
- 引数解析、メッセージフォーマット、出力処理がすべてコピペ
- 約280行 → 共通化で約80行程度に削減可能

## 修正内容
- 引数解析とメッセージフォーマットを共通関数に抽出
- 各ログレベルのメソッドはレベル判定と出力先の切り替えのみに
- withStack版は共通のスタックトレース付加処理を使用

## 影響範囲
- Logger APIの外部インターフェースは変更なし。内部実装のみ。
