# AI生成システム

## アーキテクチャ
```
ai-management.js（ルーター）
├─ provider/
│   ├─ ai-provider.js（基底クラス）
│   ├─ local-sdwebui-provider.js
│   ├─ local-comfyui-provider.js
│   ├─ runpod-comfyui-provider.js
│   ├─ falai-provider.js
│   └─ provider-registry.js（プロバイダ登録・ロール割り当て）
├─ queue/
│   ├─ task-queue.js（並行実行制御）
│   └─ generation-task-manager.js（aiTaskMap）
├─ comfyui/（ワークフロー、エディタ、v2）
├─ sdwebui/（設定、API呼び出し）
├─ inpainting/（マスクエディタ、ワークフロー）
├─ angle/（カメラアングルエディタ、Three.js使用）
├─ role/（ロール割り当てUI）
├─ ui/
│   ├─ unified-settings-window.js（APIサービス設定）
│   ├─ model-settings-window.js（モデル・ワークフロー設定フローティングウインドウ）
│   └─ ai-ui-util.js
└─ prompt/auto/（自動プロンプト生成）
```

## プロバイダ基底クラス（ai-provider.js）
```javascript
class AIProvider{
  async executeT2I(layer,spinnerId)
  async executeI2I(layer,spinnerId)
  async executeRembg(layer,spinnerId)
  async executeUpscale(layer,spinnerId)
  async executeInpaint(layer,spinnerId)
  async executeAngle(layer,spinnerId,anglePrompt)
  async fetchModels()
  async fetchSamplers()
  async fetchUpscalers()
}
```

## TaskQueue（task-queue.js）
Promise-based並行実行。プロバイダ別にキューが分かれる。
| キュー | 対象 | 並行数 |
|--------|------|--------|
| `sdQueue` | SD WebUI | 1 |
| `comfyuiQueue` | ComfyUI | 1 |
| `falaiQueue` | Fal AI | 1-10 |

## ロール割り当て（provider-registry.js）
タスク種別ごとにどのプロバイダを使うか設定。
- T2I, I2I, UP, BG, IP, ANG, TAG

## ObjectInfo（ComfyUIノード定義）
ワークフローのノードが接続先ComfyUIに存在するかを`checkWorkflowNodeVsComfyUI()`で照合する。
照合元は`comfyObjectInfoRepo_local` / `comfyObjectInfoRepo_runpod`（IndexedDB）。

- **未取得だと全ノードが「存在しない」と判定され、生成・背景削除・アップスケールが
  一律に中断される。** 取得は`comfyui_monitorConnection_v2()`の接続確立時のみで、
  この監視はモデル・ワークフロー設定ウィンドウを開くまで開始されない
- そのため`checkWorkflowNodeVsComfyUI()`は未取得なら`fetchAndSaveComfyObjectInfo()`で
  その場で`/object_info`を取得する。起動直後でも動くようにするため
- 取得できなかった場合は「全ノード欠落」ではなく接続エラーとして通知する。
  ノード名を並べると原因を誤認させるため
- 監視ループは`comfyMonitorStarted`で1本に制限。複数動くと接続状態の変化を
  取り合ってObjectInfoの更新が走らないことがある。ループ内は例外を握りつぶす
  （例外でループが終了するとObjectInfoが二度と更新されない）

## デフォルトワークフロー
`comfyuiDefaultWorkflows`（comfyui-default-workflows.js）をDOMContentLoaded時に
IndexedDBへ登録する。`getEnabledWorkflowByType(type)`は該当typeで`enabled`のものを返す。
有効なワークフローが無い場合はnullを返すので、呼び出し側で明示的に弾くこと。

## タスクライフサイクル（generation-task-manager.js）
→ `layer-structure.md`のAIタスク進捗管理セクション参照

## ComfyUI プロバイダ切り替え（comfyui-management.js）
`_comfyUIExecProvider` グローバル変数でリクエスト単位のプロバイダを制御する。
```javascript
async function comfyUIExecWithProvider(provider, fn){
  _comfyUIExecProvider = provider;
  try { return await fn(); }
  finally { _comfyUIExecProvider = null; }
}
```
- `getComfyUIServerAddress()` / `getComfyUIAuthHeaders()` / `getComfyUIProviderTag()` はすべて `_comfyUIExecProvider || providerRegistry.getActive()` を参照
- `comfyUIUrls` は Proxy で、プロパティアクセスのたびに `getComfyUIServerAddress()` を呼ぶ動的URL
- **注意**: `fn()` 内で長時間の await（WebSocket待機等）を行うと、その間に別の非同期タスク（ワークフローエディタ更新等）が `comfyUIExecWithProvider` を呼び `_comfyUIExecProvider` を上書きする。await 後に `comfyUIUrls.*` や `comfyuiFetch()` を使うと別プロバイダのURLに接続してしまう
- **対処**: 関数冒頭で `getComfyUIServerAddress()` / `getComfyUIAuthHeaders()` をローカル変数にキャプチャし、await後はそのローカル変数を使って直接 `fetch()` する

## ComfyUI v2ワークフロー
- `comfyui-workflow-repository.js` でワークフロー保存/読み込み（ファクトリパターン）
  - `createWorkflowRepository(providerKey)` でプロバイダー別インスタンス生成
  - `comfyUIWorkflowRepo_local` / `comfyUIWorkflowRepo_runpod`
- `comfyui-object-info-repository.js` でノード情報キャッシュ（同様のファクトリパターン）
  - `comfyObjectInfoRepo_local` / `comfyObjectInfoRepo_runpod`
- `comfyui-workflow-editor.js` でビジュアルエディタ（オプションで providerKey, workflowRepo, objectInfoRepo, provider, containerEl を受け取る）
- デフォルトワークフロー: t2i, inpaint, angle, upscale, rembg

## モデル設定フローティングウインドウ（model-settings-window.js）
3タブ構成：
1. **ComfyUI Workflow** — Local ComfyUIのワークフロー管理（ObjectInfo: comfyUIPageUrl）
2. **RunPod ComfyUI Workflow** — RunPod ComfyUIの独立ワークフロー管理（ObjectInfo: runpodComfyUIUrl）
3. **SD WebUI** — モデル・サンプラー等のSD WebUI固有コントロール

各タブは遅延初期化。ComfyUIタブはそれぞれ独立した `ComfyUIWorkflowEditor` + `ComfyUIWorkflowWindow` インスタンスを持つ。
