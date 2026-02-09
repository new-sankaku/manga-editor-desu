# 002: Service Workerの修正

## 規模: S (小)

## 概要
Service Workerが登録されているが、fetch処理がコメントアウトされており何も機能していない。
無効化するか、正しいキャッシュ戦略を実装する。

## 該当箇所
- `service-worker.js`

## 現状の問題
- `manifest.json`でPWAとして宣言されているが、Service Workerのキャッシュ処理が無効化されている
- オフライン対応が一切機能しない
- 無意味なfetchインターセプトが残っている

## 修正案
### 案A: Service Worker登録の無効化
- 不要なService Workerの登録を停止する

### 案B: 適切なキャッシュ戦略の実装
- 静的アセット（CSS/JS/画像/フォント）をCache First戦略でキャッシュ
- HTML/APIリクエストはNetwork First戦略
- オフラインフォールバックページの用意

## 影響範囲
- PWAとしてのオフライン動作に関わる
