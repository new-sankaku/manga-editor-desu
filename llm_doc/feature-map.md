# 機能マップ（技術者向け）

カテゴリ別に「どの機能を、どのファイルが、どう処理しているか」を引くための一覧。
利用者向けの機能紹介は `README_JP.md` の「全機能一覧」と `html/docs/features*.html` が正。
個別の仕組みの詳細は各行の「詳細」に挙げた `llm_doc/` を参照する。

- パスは `js/` からの相対
- 「入口」は処理の起点になる関数・オブジェクト。grep の検索語として使う

---

## 1. 基盤

| 機能 | 処理 | 主なファイル | 入口 |
|---|---|---|---|
| キャンバス | fabric.js の Canvas を1枚持ち、ページ切替時に中身を差し替える。WebGL が使えれば WebGL 描画 | `core/settings.js`, `fabric/fabric-management.js` | `canvas` |
| 移動・変形時の追従 | オブジェクト変更時にコマのクリップパスと連結オブジェクトの位置を更新 | `fabric/fabric-management.js` | `updateOnModification`, `updateClipPath` |
| 原稿サイズ・ズーム | mm 指定の原稿サイズからキャンバス寸法を算出、表示倍率を調整 | `canvas-manager.js` | `applyPageSizeMm`, `resizeCanvas`, `adjustCanvasSize` |
| 操作モード | 選択・ペン・ナイフ・トーン等の排他モードを1か所で切替 | `ui/util/mode-manager.js`, `ui/util/mode-change.js` | `ModeManager`, `toggleMode` |
| クリック委譲 | `data-action` 属性でボタンの処理を割り当て | `ui/util/event-delegator.js` | `EventDelegator` |
| ショートカット | hotkeys で登録。Undo/Redo、コピー&ペースト、矢印移動 | `shortcut.js` | `hotkeysMap` |
| ログ・エラー | レベル付きロガー、未捕捉例外の受け口 | `core/logger.js`, `core/global-error-handler.js` | `SimpleLogger` |
| 設定 | 画面上の設定値をスキーマで定義し localStorage へ自動保存・復元・リセット | `project-management.js` | `SETTINGS_SCHEMA`, `saveSettingsLocalStrage`, `resetAllSettings` |
| 起動処理 | 設定復元→自動保存の復元確認などを順に実行 | `project-management.js` | `runBootSequence` |
| PWA | Service Worker 登録、キャッシュ削除、インストールボタン制御 | `core/service/worker-register.js`, `/service-worker.js` | `isPWAEligible` |
| 汎用ユーティリティ | オブジェクト種別判定、画像変換（webp化・切り抜き・data URL化）、スクリプト遅延読込 | `core/util/fabric-util.js`, `core/util/image-util.js`, `core/util/load-util.js` | `isPanel`, `ImageUtil` |

詳細: `project-structure.md`, `ui-patterns.md`, `coding-rules.md`

---

## 2. ページ・コマ

| 機能 | 処理 | 主なファイル | 入口 |
|---|---|---|---|
| コマ割りテンプレート | SVG テンプレートを読み、多角形のコマとしてキャンバスへ展開。一覧は遅延読込 | `svg/manga-panels-image-*.js`, `sidebar/speechBubble/speech-bubble-effect.js`, `sidebar/panel/panel-template.js` | `lazyLoadVerticalPanels`, `loadBookSize` |
| 図形コマ | 正方形・長方形・台形・多角形・星・ハートを生成 | `sidebar/panel/panel-template.js` | `addShape`, `addSquareBySize` |
| ナイフ | 引いた線と多角形の交点を求めて2つの多角形へ分割。余白分だけ両側を後退させる | `sidebar/panel/knife/*` | `splitPolygon`, `changeKnifeMode` |
| ランダムカット | 縦横のカット数・傾き・ばらつきから分割線を生成し、複数ページにも適用 | `panel/random-cut.js` | `rundomPanelCut`, `generateMultipage` |
| 画像のコマへの配置 | ドロップ位置のコマを探し、コマに合わせて拡縮しクリップパスで切り抜く | `sidebar/panel/panel-manager.js` | `putImageInFrame`, `findPanelUnderPoint` |
| コマとオブジェクトの連結 | 画像・テキストをコマにリンクし、コマ移動に追従させる。複製時に再リンク | `sidebar/panel/panel-manager.js` | `relinkToPanelUnderObject`, `releasePanelLink` |
| グリッド | 間隔可変のグリッド描画とスナップ | `panel/grid.js` | `toggleGrid`, `snapToGrid` |
| ページ管理 | 下部バーに各ページのサムネイルと JSON を保持し、切替時に保存→読込。並べ替え | `ui/bottom-bar.js` | `btmProjectsMap`, `btmNavigatePage` |

詳細: `layer-structure.md`

---

## 3. 吹き出し・テキスト

| 機能 | 処理 | 主なファイル | 入口 |
|---|---|---|---|
| 吹き出しテンプレート | SVG を読み込み、内側の矩形を算出してテキストを中に配置。テキスト変更時に吹き出しを再計算 | `svg/speechbubble.js`, `sidebar/speechBubble/speech-bubble-text.js`, `speech-bubble-effect.js` | `changeSpeechBubbleSVG`, `speechBubbleTextChaged` |
| カスタム吹き出し | 座標指定・フリーハンドで輪郭を作り、JSTS で重なった図形を合成 | `sidebar/speechBubble/speech-bubble-freehand.js` | `createSpeechBubble`, `mergeOverlappingShapes` |
| 縦書き | Textbox を拡張した縦書きクラスで1文字ずつ配置 | `sidebar/text/vertical-textbox.js`, `vertical-text.js` | `VerticalTextbox` |
| テキスト書式 | 色・縁取り・背景・揃え・CSS 効果（ネオン、グラデーション等） | `sidebar/text/text-effect.js` | `updateTextControls`, `applyCSSTextEffect` |
| テキスト装飾 | 同じ文字を複数層重ねて描き、縁取り・影を表現。プリセットは値表 | `sidebar/text/text-decor.js`, `text-decor-presets.js` | `textDecorApply`, `TEXT_DECOR_PRESETS` |
| 画像テキスト | SVG フィルタで装飾した文字を作り画像としてキャンバスへ置く。新方式は値表＋汎用ドライバ、旧方式は1種1ファイル | `sidebar/text/text-2-manager.js`, `text/custom/*` | `switchText2`, `T2_EFFECT_PRESETS`, `t2GenericCreateSvg` |
| フォント | 内蔵フォント一覧、OS フォント検出、Web フォント URL・ファイル追加 | `core/font/*`, `ui/font/user-font-manager.js`, `db/user-font-repository.js` | `FontSelectorManager`, `FontDetector`, `fmUserFontManager` |
| プロジェクトフォント | 使用フォントを集計して保存し、読込時に復元。無いフォントは通知 | `core/font/project-font.js` | `buildProjectFontData`, `restoreProjectFonts` |
| アイコン | Material アイコン（fonts.gstatic.com）を検索し SVG としてキャンバスへ追加 | `core/svg/google-icon-helper.js` | `searchIcon`, `addToCanvas` |

詳細: `text-decoration.md`, `balloon-geometry.md`

---

## 4. 描画・効果

| 機能 | 処理 | 主なファイル | 入口 |
|---|---|---|---|
| ペン | fabric のブラシを拡張（マーカー、インク、クレヨン、スプレー等）。描いたパスをグループ化して1オブジェクトに | `sidebar/pen/pen-tools.js`, `pen/original-brush.js`, `pen/fabric/brushes/*` | `switchPencilType`, `finalizeGroup` |
| モザイク・消しゴム | 専用ブラシで描画 | `sidebar/pen/pen-tools.js` | `getMosaicBrush` |
| トーン | 別キャンバスに網点・ノイズ・雪・流線・集中線を描画し画像として配置。ドラッグで範囲・中心を指定 | `sidebar/tone/*` | `switchMangaTone`, `generateTone`, `focusLine` |
| モノクロ変換 | フィルタを段階的に適用して白黒・トーン化。選択画像／ページ／全ページの範囲で一括適用 | `sidebar/effect/c2bw_tone.js`, `c2c.js`, `effect-batch.js`, `effect-manager.js` | `runMangaEffectByScope`, `effectApplyToAllPages` |
| GLFX フィルタ | glfx.js の共有 WebGL キャンバスで画像にフィルタを適用 | `ui/control/glfx-control.js`, `ui/glfx-ui.js` | `glfxApplyFilterToObject`, `GLFX_FILTER_META` |
| ブレンド | 選んだレイヤーを PixiJS で合成し結果を画像化 | `layer/blend/blend.js` | `blendCanvasesWithPixi`, `selectBlendMode` |
| 暗部補正 | 画像の暗部を持ち上げる | `core/util/image-util.js` | `enhanceDarkToImage` |
| 切り抜き | 切り抜きモードで矩形を指定し画像を置換 | `ui/util/mode-change.js` | `startCropMode`, `completeCrop` |
| プリセット選択 | ペン・トーン・画像テキスト・GLFX・テキスト装飾を一覧から検索して選択 | `ui/preset-picker.js`, `ui/preset-panel.js` | `PresetPicker`, `PRESET_PANELS` |

詳細: `tone-conversion.md`

---

## 5. レイヤー・履歴・オブジェクト操作

| 機能 | 処理 | 主なファイル | 入口 |
|---|---|---|---|
| レイヤーパネル | キャンバスのオブジェクトを階層（コマ→中身）で一覧化。名前編集、表示切替、ロック | `layer/layer-management.js` | `updateLayerPanel`, `processLayerHierarchy` |
| レイヤーのボタン | 個別ダウンロード、背景削除、高解像度化、画像→プロンプト等をレイヤー行に付与 | `layer/layer-button.js` | `putRembgButton`, `putUpscalerButton` |
| Undo/Redo | 変更ごとにキャンバス JSON を履歴スタックへ積む。画像は別マップで重複排除。ページ切替で履歴は消える | `layer/image-history-management.js`, `shortcut.js` | `stateStack`, `undoByUser`, `withoutHistory` |
| 右クリックメニュー | 選択オブジェクトの上にスライダー・色・サブメニュー付きのメニューを表示 | `ui/canvas-object-menu.js` | `showObjectMenu` |
| 値の同期 | 選択したオブジェクトの値を各パネルの入力欄へ反映 | `ui/control/object-control-sync.js` | `syncObjectControls` |
| フローティングウインドウ | ドラッグ移動できる窓の共通処理 | `layer/floating-window-management.js` | `makeDraggable` |

詳細: `layer-structure.md`, `history-and-data.md`

---

## 6. 保存・書き出し

| 機能 | 処理 | 主なファイル | 入口 |
|---|---|---|---|
| プロジェクト保存 | 全ページの JSON・画像をまとめて LZ4 で圧縮し `.lz4` を出力 | `core/compression/project-compression.js`, `core/compression/lz4.js` | `btmSaveProjectFile`, `FileCompressor` |
| プロジェクト読込 | `.lz4` / `.zip` を展開し、全置換か現在ページのみかを選んで読込 | `core/compression/project-compression.js`, `project-management.js` | `loadLz4BlobProjectFile`, `askProjectLoadMode` |
| 自動保存 | 一定間隔で状態ハッシュを比較し、変化があれば IndexedDB（localforage）へ保存。起動時に復元を提案 | `core/auto-save.js` | `AutoSaveManager` |
| 未保存警告 | 保存時点のスナップショットと比較し、離脱時に警告 | `core/unsaved-guard.js` | `UnsavedGuard` |
| PNG 書き出し | 原稿サイズ(mm)×DPI から倍率を求めて `toDataURL` で出力。グリッドは一時的に外す | `core/util/image-util.js` | `getOutputPixelSize`, `getCropAndDownloadLinkByMultiplier` |
| SVG 書き出し | キャンバスを SVG 化してダウンロード | `project-management.js` | `svgDownload` |

詳細: `history-and-data.md`

---

## 7. AI 画像生成

| 機能 | 処理 | 主なファイル | 入口 |
|---|---|---|---|
| プロバイダ | 共通基底クラスを継承した7種（WebUI/Forge、ComfyUI ローカル/RunPod、Fal.ai、Google Nano Banana、Grok、Ollama） | `ai/provider/*` | `AIProvider`, `providerRegistry` |
| ロール割り当て | 処理（T2I、I2I、Inpaint、高解像度化、背景削除、アングル、画像→プロンプト等）ごとに使うプロバイダを指定。表 UI で編集 | `ai/role/ai-roles.js`, `ai/role/role-assignment-ui.js` | `AI_ROLES`, `roleAssignmentUI` |
| タスクキュー | プロバイダ別キューで同時実行数を制限。レイヤー上に進捗とキャンセルを表示 | `ai/queue/*`, `ai/ai-management.js` | `TaskQueue`, `aiTaskMap`, `cancelAiTask` |
| T2I / I2I | コマ（レイヤー）単位でプロンプトを送り、結果をコマに配置 | `ai/ai-management.js`, `ai/sdwebui/*`, `ai/comfyui/*` | `T2I`, `sdwebuiGenerateImage`, `comfyUIExecWithProvider` |
| ComfyUI ワークフロー | API 形式のワークフローを保存・編集。プレースホルダを置換して送信し、WebSocket で進捗を受ける。object_info でノード入力を検証 | `ai/comfyui/v2/*`, `ai/comfyui/util/*` | `ComfyUIWorkflowEditor`, `ComfyUIWorkflowBuilder`, `comfyuiConnect` |
| インペイント | マスクを描き、専用ワークフローで部分再生成（ComfyUI のみ） | `ai/inpainting/*` | `openInpaintEditor`, `InpaintWorkflow` |
| アングル生成 | three.js のカメラウィジェットで角度を指定し、I2I で描き直し（ComfyUI のみ） | `ai/angle/*` | `openAngleEditor`, `CameraWidget` |
| 高解像度化・背景削除 | ロールに割り当てたプロバイダで実行し画像を置換 | `ai/sdwebui/sdwebui-single-call-api.js`, `ai/comfyui/v2/comfyui_workflow/*` | `sdwebuiRemoveBackground` |
| 画像→プロンプト | WebUI の CLIP / DeepDanbooru、または LLM で画像からタグを取得 | `ai/sdwebui/sdwebui-multi-call-api.js`, `ai/prompt/llm/llm-prompt-service.js` | `sdwebuiInterrogate`, `llmImage2Prompt` |
| 参照画像 | キャラ・場所等の設定資料をプロジェクト／ベース(IndexedDB)の2層で管理し、コマに割り当てて Nano Banana へ複数画像として送る | `ai/reference/*`, `db/reference-repository.js` | `ReferenceSheetStore`, `ReferenceCollector`, `referenceSheetWindow` |
| 設定画面 | プロバイダ接続・モデル選択の統合設定ウインドウ | `ai/ui/*`, `ai/ai-settings.js` | `unifiedSettingsWindow`, `modelSettingsWindow` |

詳細: `ai-system.md`, `ai-verification.md`, `reference-image.md`

---

## 8. プロンプト・LLM

| 機能 | 処理 | 主なファイル | 入口 |
|---|---|---|---|
| ストーリー→コマのプロンプト | ストーリーからキャラ・場所を抽出→ページ割り→コマごとのプロンプトの順に LLM を呼ぶ。範囲はコマ／ページ／全ページ | `ai/prompt/llm/llm-story-service.js`, `llm-story-ui.js` | `llmStorySheets`, `llmStoryPagePlan`, `llmStoryPanelPrompts` |
| ネームから一括生成 | 既存のコマ配置を読み順で並べ、ページ内全コマのプロンプトを生成。構図の偏りを検出 | `ai/prompt/llm/llm-storyboard-service.js`, `llm-storyboard-ui.js` | `llmStoryboard`, `sortPanelsInReadingOrder`, `findPanelRhythmProblem` |
| テキスト→タグ | 自然文を LLM でタグ列へ変換 | `ai/prompt/llm/llm-prompt-service.js`, `llm-prompt-ui.js` | `llmText2Prompt` |
| 構図タグ・サイズ | コマの役割から構図タグを付け、縦横比から SDXL の解像度バケットを選ぶ | `ai/prompt/panel-composition.js` | `pickPanelSDXLBucket`, `compositionJoin` |
| コマへの書き込み | 生成したプロンプトをコマへ反映し、画風の接尾語を付ける | `ai/prompt/prompt-apply.js` | `promptApplyToPanel`, `promptApplyToOrderedPanels` |
| プロンプト入力 | Tagify でタグ入力・あいまい検索 | `ui/util/tagify-util.js`, `ui/ai/auto-prompt-ui.js` | `initializeTagify` |
| 検索・置換 | プロジェクト全体のプロンプトを一括置換 | `ui/prompt-manager.js` | `openPromptChangeFloatingWindow` |
| 画像プロンプトヘルパー | サンプル画像付きのタグ辞書から選択 | `ui/imagePromptHelper/*` | `iphInitializeUI` |
| 自動生成（シナリオ） | シナリオ表からページ構成とプロンプトを乱択して一括生成 | `ai/prompt/auto/*` | `autoMultiGenerate`, `autoMultiPromptSet` |

詳細: `manga-page-guideline.md`, `prompt-composition.md`

---

## 9. 統計・その他

| 機能 | 処理 | 主なファイル | 入口 |
|---|---|---|---|
| ダッシュボード | 生成時間・時間帯別・日別の記録、タグ頻度と共起、ワードクラウド、外部 API 利用料の推定。JSON/CSV 出力 | `dashboard/*` | `DashboardUI`, `PerformanceStorage`, `PromptFrequencyStorage`, `ApiCostStorage` |
| 多言語 | i18next で8言語。`<html lang>` も同期 | `ui/third/i18next.js`, `ui/third/base-translation/*` | `updateContent` |
| チュートリアル | サイドバーパネルごとのガイドツアー、ComfyUI 導入ガイド | `ui/tutorial.js` | `TutorialManager`, `ComfyUIGuide` |
| 通知・進捗 | トースト（重複集約・上限管理）、全画面の進捗オーバーレイ、確認ダイアログ | `ui/toast.js`, `ui/overlay-progress.js`, `ui/util/confirm-dialog.js` | `createToast`, `OP_showLoading`, `showConfirmDialog` |
| 自己テスト | 主要ユーティリティの簡易テスト | `core/debug.js` | `TestRunner` |
