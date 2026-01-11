/**
 * knife-index.js
 * ナイフツールの統合エントリポイント
 * 後方互換性のためのグローバル関数公開
 */

// このファイルは他のすべてのknife-*.jsファイルの後に読み込まれる必要があります
// 依存関係:
// - knife-constants.js
// - knife-state.js
// - knife-geometry.js
// - knife-line-renderer.js
// - knife-split-engine.js
// - knife-mode.js

// すべての必要な関数は各ファイルでグローバルスコープに定義されているため、
// 追加のエクスポート処理は不要です。

// 初期化ログ（デバッグ用、本番環境では削除可）
panelLogger.debug('[Knife] Knife tool modules loaded successfully');
