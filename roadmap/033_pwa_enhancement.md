# 033: PWA強化

## 規模: M (中)

## 概要
現在ほぼ空のService Workerに適切なキャッシュ戦略を実装し、
完全オフライン動作を実現する。002の発展版。

## 関連
- [002](002_fix_service_worker.md): Service Workerの修正（002の案Bを発展させた内容）

## 該当箇所
- `service-worker.js`
- `manifest.json`
- `index.html`（Service Worker登録部分）

## 現状の問題
- `manifest.json`でPWAとして宣言されているが、Service Workerのキャッシュ処理が無効化されている
- オフライン環境で一切動作しない
- インストール可能なPWAとして認識されない（キャッシュ未実装のため）

## 修正内容
### Phase 1: キャッシュ戦略の実装
- 静的アセット（CSS/JS/画像/フォント/SVG）をCache First戦略でキャッシュ
- バージョン管理によるキャッシュ更新機構
- `install`イベントで主要アセットを事前キャッシュ
- `activate`イベントで古いキャッシュを削除

### Phase 2: オフラインフォールバック
- ネットワーク不可時のフォールバック処理
- CDNリソースのローカルフォールバック（Chart.js, Masonry等）
- オフライン状態のユーザー通知

### Phase 3: インストール体験の改善
- `manifest.json`の最適化（アイコンサイズの充実、カテゴリ設定）
- インストールプロンプトの適切なタイミング表示
- アプリ更新通知

### キャッシュ対象の分類
| カテゴリ | 戦略 | 対象 |
|----------|------|------|
| アプリ本体 | Cache First + バージョン更新 | HTML, CSS, JS |
| フォント | Cache First（長期） | font/, Font Awesome |
| 画像/SVG | Cache First | アイコン, UI用SVG |
| AI API | Network Only | SD WebUI, ComfyUI |

## 制約事項
- `file://`プロトコルでの動作が必須
- `file://`ではService Workerが登録できない（ブラウザのセキュリティ制限）
- PWA機能は`http://`/`https://`環境（GitHub Pages等）でのみ有効
- `file://`環境では従来通りService Workerなしで動作するよう、登録処理に分岐を入れる

## 影響範囲
- オフライン動作
- 初回以降の読み込み速度
- PWAインストール体験
