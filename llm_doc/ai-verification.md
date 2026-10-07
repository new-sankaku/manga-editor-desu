# AI機能案の検証結果

2026-08-29に、AI機能の追加案（86件）に対して「未検証」と印を付けた前提を、
コードと実機で確かめた記録。**案そのものはここに書かない。確かめた事実だけを残す。**

検証環境: ComfyUI 0.27.0（127.0.0.1:8188、ノード2943クラス）/ Chrome（`file://`で実測）/
SD WebUIは未起動のため未確認。

---

## 1. 実害が出ている不具合

### 1.1 Inpaintのマスクが効いていない

**症状**: マスクで囲った所だけを描き直すはずが、マスクが完全に無視される。

原因が**2つ独立にあり、どちらか片方だけでも致命的**。両方直さないと直らない。

#### 原因A: 置換の順序ではなく、置換の仕組みそのもの

`updateNodesByInputName()`（`comfyui-workflow-builder.js:44-72`）は class_type を見ず、
**`image` という入力名を持つ全ノード**を同じ値で書き換える。
`Inpaint_SDXL.json` の LoadImageMask も入力名が `image` なので、
プレースホルダ `inpaint_mask.png` が元画像のファイル名に潰される。
その後に走る `updateValueByTargetValue("inpaint_mask.png", ...)`
（同:81-101、ノードを再帰走査する文字列全置換）は、探す対象が既に無い。

呼び出し側は2経路あり、**両方とも同じ順序**:
- `comfyui-util.js:20-24`
- `inpaint-workflow.js:32-35`

**順序を入れ替えても直らない。** 入力名一致は class_type を見ないため、
先にマスクを差し込んでも後から `image` で上書きされる（シミュレーションで確認済み）。

#### 原因B: マスクのチャンネルが合っていない

`Inpaint_SDXL.json` の LoadImageMask は `"channel":"alpha"` を指定している。
一方アプリが送るマスクは `getMaskAsBlackWhite()`（`inpaint-mask.js:151-171`）が作る
**白黒・アルファ一律255の不透明PNG**（塗った所=白、他=黒）。

ComfyUI の LoadImageMask はアルファチャンネルを読むとき値を反転する。
アルファが全面255なら、マスクは**全面0**になる。

実測（`LoadImageMask` → `MaskToImage` → 出力画素を測定）:

| channel | 塗った所の平均 | それ以外の平均 | 結果 |
|---|---|---|---|
| `alpha` | 0.0 | 0.0 | 全面0。マスクとして機能しない |
| `red` | 255.0 | 0.0 | 意図どおり（塗った所が対象） |

**つまり原因Aを直しても、`channel` が `alpha` のままなら全面0のままになる。**

#### 実際に何が起きるか（実測）

512x512の画像（左半分赤・右半分青・中央に緑の四角）と、中央だけを対象にしたマスクで、
SDXLのInpaintを2通り流して画素の変化量を測った（0〜765スケール）。

| | マスク内の平均変化 | マスク外の平均変化 |
|---|---|---|
| A: アプリの置換後（マスクノードが元画像を指す） | 22.0 | 3.5 |
| B: マスクが正しく渡った場合 | 18.6 | 297.6 |

Aは**どこもほとんど変わらない**。全面0のマスクは `VAEEncodeForInpaint` で何も消さず、
`noise_mask` も0になるため、KSamplerの結果が元画像で上書きされる。
**Inpaintを実行しても元の絵がそのまま返る。**

（BでマスクN外が変わっているのは、テスト用マスクを「中央だけ不透明」で作ったため。
alphaチャンネルの反転により外側が対象になった。この向きの話は原因Bと同じ問題。）

#### 直し方

1. ワークフローの LoadImageMask を `"channel":"red"` にする（実測で確認済み）
2. `image` の一括上書きがマスクノードに当たらないようにする。
   ワークフロー側に `%mask%` のようなプレースホルダを置き、
   `updateValueByTargetValue()` だけで差し込む形にすると、
   既存の `%prompt%` と同じ流儀になり、他のワークフローを壊さない

#### 対応済み（2026-08-29）

- `comfyui-inpaint-default-workflows.js` の LoadImageMask を
  `"image":"%mask%"` / `"channel":"red"` に変更。あわせて `ckpt_name` を
  実在する `illustrious\\waiIllustriousSDXL_v160.safetensors` に変更（1.2の対応）
- `comfyui-workflow-builder.js` の `updateNodesByInputName()` に
  「値が `%...%` 形式なら書き換えない」判定（`isPlaceholderValue()`）を追加。
  プレースホルダは `updateValueByTargetValue()` でのみ差し込む、という
  `%prompt%` と同じ規則を1か所で効かせている。class_typeごとの分岐は入れていない
- 差し込みキーワードは `COMFY_MASK_PLACEHOLDER`（`%mask%`）として
  `comfyui-workflow-builder.js` に定義。呼び出し2経路
  （`comfyui-util.js` の Inpaint 分岐 / `inpaint-workflow.js`）の両方が同じ定数を使う
- 保存済みワークフロー（IndexedDB）は既定ワークフローを更新しても上書きされないため、
  旧形式が残る。`migrateLegacyMaskPlaceholder()` を追加し、
  **`image` が旧プレースホルダ `inpaint_mask.png` のままの LoadImageMask ノードだけ**を
  `%mask%` / `red` へ書き換える。対象を旧プレースホルダに限定しているので、
  ユーザーが独自のファイル名・channel に変えたノードは触らない。
  呼び出しは2経路とも `image` の一括上書きより前
- Node上で新形式・旧形式・独自形式の3通りを流して置換結果を確認済み。
  新形式・旧形式はどちらも `image=元画像` / `mask=アップロードしたマスク` / `channel=red` になる。
  **ComfyUI実機での再実行は未実施**

#### 実機での確認（2026-08-29、ComfyUI 0.27.0）

修正後のコードで実際に生成し、直ったことを確認した。

**測り方**: `comfyui-workflow-builder.js` と `comfyui-inpaint-default-workflows.js` を
そのままNodeで読み、`inpaint-workflow.js:generate()` と同じ置換順
（`migrateLegacyMaskPlaceholder()` → seed/denoise → `image` → `%mask%` → `%prompt%` → `%negative%`）
を通して出た最終JSONを `/prompt` へ投げた。**ワークフローの組み直しはしていない。**
「修正前」は同じ画像・マスクのまま、`channel` を `alpha` に戻し、
マスクノードの `image` を元画像のファイル名に差し替えたもの（＝原因A・Bが揃った状態）。

- 画像: 512x512、左半分=赤 / 右半分=青 / 中央192pxの正方形=緑
- マスク: 中央の正方形だけ白、他は黒、アルファ一律255のRGBA
  （`getMaskAsBlackWhite()` が作る形と同じ）
- プロンプト `a yellow flower` / denoise 0.75 / seed 12345固定

| | マスク内 | マスク外 |
|---|---|---|
| 修正前 | 10.8 | 4.9 |
| 修正後 | **213.8** | 8.7 |

（元画像からの平均変化量。0〜765スケール＝`|dR|+|dG|+|dB|`）

修正前は**マスク内外ともほぼ変化なし**。出力は元の絵とほぼ同一で、症状のとおり。
修正後はマスク内だけが約20倍動き、外は8.7（VAEの往復ぶんの誤差）に収まっている。
目視でも、緑の正方形だけが黄色く描き直され、赤・青の背景は残っていた。

塗り替え範囲がマスクよりわずかに広いのは `VAEEncodeForInpaint` の `grow_mask_by:6` による。
ワークフロー定義どおりの挙動で、不具合ではない。

再現スクリプトはセッションのスクラッチパッドに置いた
（`build_wf.py` = 実コードでワークフローを組む / `e2e_inpaint.py` = 実行と計測）。


### 1.2 有効なワークフローのうち3本がモデル欠落で動かない

`comfyuiDefaultWorkflows` で `enabled:true` の6本のうち、3本が実在しないモデルを参照している。
（初回の記録では5本中2本としていたが、`ComfyUI_T2I_BySDXL` を数え落としていた。下の「その3」を参照）

| ワークフロー | 参照 | 状態 |
|---|---|---|
| `ComfyUI_I2I_BySD15SDXL`（唯一の有効なI2I） | `illustrious\waiNSFWIllustrious_v50.safetensors` | **無い**（実在は `_v120`） |
| `ComfyUI_Inpaint_BySDXL` | `sd_xl_base_1.0.safetensors` | **無い** |
| `ComfyUI_I2I_Angle_Default` | Qwen一式 | すべて実在 |
| `ComfyUI_Upscaler` | `RealESRGAN_x4plus_anime_6B.pth` | 実在 |
| `ComfyUI_Rembg_ByInspyrenet` | （モデル指定なし） | ノード実在 |

`enabled:false` のものでは `T2I_BySD15_Lora`・`T2I_ByFluxNF4`・`T2I_Qwen_Image_gguf` も参照が壊れている。

**`checkWorkflowNodeVsComfyUI()` は class_type しか照合していない。**
モデルのファイル名は見ていないため、この種の欠落は実行するまで分からない。
ワークフロー設定画面でモデル名も突き合わせると、この手の事故は起動時に見つけられる。

#### 対応（2026-08-29）

**直したもの（1件）**

- `ComfyUI_I2I_BySD15SDXL`（`comfyui-t2i-default-workflows.js`）の `ckpt_name` を
  `illustrious\waiNSFWIllustrious_v50.safetensors` →
  `illustrious\waiNSFWIllustrious_v120.safetensors` に変更。
  実機のcheckpoint一覧に `_v120` があり、同一シリーズで対応が一意に付くため。

**直さなかったもの（対応が推測になるため、近そうなモデルを当てはめていない）**

| ワークフロー | enabled | 壊れている参照 | 実在リスト上の状況 |
|---|---|---|---|
| `ComfyUI_T2I_BySDXL` | **true** | `sd_xl_refiner_1.0_0.9vae.safetensors` (CheckpointLoaderSimple) | 無い。SDXL系で実在するのは `illustrious\waiIllustriousSDXL_v160` / `illustrious\waiNSFWIllustrious_v120` の2本のみで、refinerに相当するものは無い |
| `ComfyUI_T2I_BySD15_Lora` | false | `SD1.0\anime\coffeensfw_v10.safetensors` (ckpt) | 無い。実在のSD1.0系は `RealBackground_v12` / `comiNoirClassicV2` / `yden_v20` の3本で、いずれも用途が対応しない |
| 同上 | false | `vae-ft-mse-840000-ema-pruned.safetensors` (vae) | 無い。VAE一覧にSD1.5向けのものが無い |
| 同上 | false | `SD_1.0\ChinaDressShunV1.safetensors` (lora) | 無い。lora一覧にSD1.5向けが見当たらない |
| `ComfyUI_T2I_ByFluxNF4` | false | `Flux\fluxDevSchnellBaseUNET_fluxSchnellFLANFP8.safetensors` (CheckpointLoaderNF4) | 無い。Flux系で実在するのは `flux-2-klein-base-4b-fp8.safetensors` だがこれはUNETLoader用で、NF4のcheckpointとしては使えない。`CheckpointLoaderNF4` ノード自体の存在も未検証 |

**1.2の表に追記が要る点**

`ComfyUI_T2I_BySDXL` も `enabled:true` で、上表のとおりcheckpointが実在しない。
**モデル欠落で動かない有効ワークフローは2本ではなく3本**（T2I_BySDXL / I2I_BySD15SDXL / Inpaint_BySDXL）。

**`ComfyUI_T2I_Qwen_Image_gguf` は壊れていなかった**（`enabled:false`）。
`qwen-image-Q4_K_S.gguf`（UnetLoaderGGUF）・`qwen_2.5_vl_7b_fp8_scaled.safetensors`（CLIPLoader）・
`qwen_image_vae.safetensors`（VAELoader）はいずれも実在する。
同じく `ComfyUI_T2I_Z_Image_turbo`（`enabled:false`）の3参照も全て実在。

**有効ワークフローのモデル参照 突き合わせ結果（2026-08-29）**

| ワークフロー | 参照 | 判定 |
|---|---|---|
| `ComfyUI_Rembg_ByInspyrenet` | モデル指定なし | — |
| `ComfyUI_T2I_BySDXL` | `sd_xl_refiner_1.0_0.9vae.safetensors` | **無い** |
| `ComfyUI_I2I_BySD15SDXL` | `illustrious\waiNSFWIllustrious_v120.safetensors` | 実在（今回修正） |
| `ComfyUI_Upscaler` | `RealESRGAN_x4plus_anime_6B.pth` | 実在 |
| `ComfyUI_I2I_Angle_Default` | `qwen_image_edit_2511_bf16` / `qwen_2.5_vl_7b_fp8_scaled` / `qwen_image_vae` / `Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16` / `qwen-image-edit-2511-multiple-angles-lora` | 全て実在 |

（`ComfyUI_Inpaint_BySDXL` は別対応のため本項では扱っていない）

#### 対応（2026-08-29 その2）: 起動前にモデル名を照合する

`checkWorkflowNodeVsComfyUI()` にモデル名（＝選択肢が列挙されている入力）の照合を足した。
class_typeの照合が通ったあとに走る。

- 引数を「class_typeの配列」から**ワークフロー本体**へ変更（値の照合にノードIDと入力名が要る）。
  呼び出しは `comfyui-management.js` の `comfyuiSelectWorkflow()` と
  `inpaint-workflow.js` の2経路。どちらも同じ関数を通るので、
  生成・背景削除・アップスケール・Inpaintのすべてに効く
- 照合本体は `comfyCollectValueMismatches(workflow,objectInfo)`
  （`comfyui-object-info-repository.js`）。エディタ側も同じ関数を呼ぶ
- 通知は既存のノード欠落と同じ導線（トースト＋右サイドバーの案内）。
  案内は `ComfyUIGuide.showValueErrorGuide()` を新設した。
  `sampler_name` / `scheduler` も同じ仕組みで引っかかるため、
  文言は「モデルが無い」ではなく「ComfyUI側に無い値」で統一している

**実測した `/object_info` の形**（ComfyUI 0.27.0、2943クラス）

選択肢を持つ入力の形は1つではなかった。両方に対応しないと取りこぼす。

| 形 | 件数 | 例 |
|---|---|---|
| `[[選択肢...],{メタ}]` | 2434 | `CheckpointLoaderSimple.ckpt_name` |
| `["COMBO",{options:[選択肢...]}]` | 448 | `UpscaleModelLoader.model_name` |

照合から外した入力（**通したいからではなく、起動時には正解が確定しないから**）:

| 外す条件 | 件数 | 理由 |
|---|---|---|
| `isPlaceholderValue()`が真 | — | `%prompt%` 等は実行時に差し込む。照合すると必ず不一致 |
| `image_upload`/`file_upload`/`video_upload`/`audio_upload` | 8/2/2/1 | LoadImageの`image`は実行時にアプリが差し込むファイル名 |
| `remote` | 1 | ComfyUIのフロントが後から取りに行くため一覧が空 |

選択肢0件の入力（旧25件・新14件。`StyleModelLoader.style_model_name` 等）は
**不一致として報告する**。実測ではすべて「モデルフォルダが空」であり、
そこを指しているワークフローは実際に動かない。

**検証**（`/object_info` の実データ＋既定ワークフロー18本をNodeで通した）

- 有効ワークフローで検出されたのは `ComfyUI_T2I_BySDXL` の
  `sd_xl_refiner_1.0_0.9vae.safetensors` の1件のみ。
  上の表で「直さなかったもの」に挙げた壊れた参照と一致する
- 誤検出0件。`LoadImage.image`（`RealESRGAN_00001_.png` 等）・
  `filename_prefix` の `%date:...%`・`sampler_name`/`scheduler` の正しい値・
  `seed`/`cfg` などの数値は、いずれも報告されない
- 手で作ったワークフローで、`%model%` / `%mask%` は素通り、
  存在しない `sampler_name` は検出、ノード欠落ノードの入力は
  値としては報告されない（ノード欠落側で報告）ことを確認
- **ComfyUI実機での生成実行は未実施**（照合結果の突き合わせまで）

**ワークフロー設定画面**（`comfyui-workflow-editor-tab.js`）

同じ関数で照合し、バナーと該当入力に印を出す。
ここで分かったのは、**照合の有無以前に既存の描画が値を壊していた**こと。
selectの選択肢はComfyUIの一覧だけで作られ、ワークフローの値がその中に無いと
先頭の選択肢が選ばれた見た目になる。`setupInputListeners()` は描画直後に
`input.value` をワークフローへ書き戻すため、**壊れているモデル名が黙って
別のモデル名に置き換わる**。現在値を `⚠ 値` として選択肢の先頭に足し、
選び直すまで変わらないようにした。

#### 1.2b 置換されないプレースホルダが残っている

`comfyuiReplacePlaceholders()`（`comfyui-util.js`）が置換するのは
`%prompt%` / `%negative%` / `%AnglePrompt%` / `inpaint_mask.png` と
`updateNodesByInputName` 経由の `seed` / `noise_seed` / `width` / `height` / `image` / `denoise` だけ。
以下はどこでも置換されず、そのままComfyUIへ送られる（いずれも `enabled:false`）。

- `ComfyUI_T2I_ByFluxDiffusion`: `unet_name: "%model%"`
- `ComfyUI_T2I_ByFluxSimple`: `ckpt_name: "%model%"`
- `ComfyUI_T2I_ByFluxNF4`: `sampler_name: "%sampler%"`

有効化するならプレースホルダの置換元を用意するか、実在モデル名を直書きする必要がある。

#### 対応（2026-08-29 その3）: `ComfyUI_T2I_BySDXL` のcheckpoint

上で「対応が推測になる」として保留した1件を、ワークフローの中身を読んだうえで直した。

**`SDXL.json` はrefinerを使うワークフローではなかった。** checkpointが1本（ノード4）、
KSamplerも1本の単段構成で、`sd_xl_refiner_1.0_0.9vae.safetensors` は
**ベースモデルの位置に置かれていただけ**だった。refiner単体をdenoise 1.0の空latentから
回す形になっており、動いていたとしても本来の使い方ではない。
SDXLアーキテクチャのcheckpointであれば差し替えが成り立つ。

`comfyui-t2i-default-workflows.js:817` を
`illustrious\\waiIllustriousSDXL_v160.safetensors` に変更した。選んだ理由:

- SDXLアーキテクチャで、同ワークフローの `CLIPTextEncodeSDXL` と噛み合う
- 実在するSDXL系2本のうちNSFWでない方
- 同ファイルの310行・580行（`SDXL_faceDetailer` 系）が既に同じモデルを参照しており、
  エスケープの書き方も含めて揃う。Inpaintの修正先とも同一

Nodeで評価したランタイム値が `illustrious\waiIllustriousSDXL_v160.safetensors` となり、
実機のcheckpoint一覧と完全一致することを確認した。

**`SDXL_Refiner.json`（`enabled:false`）は直していない。** こちらは base + refiner の
本物の2段構成で、base（`sd_xl_base_1.0_0.9vae.safetensors`）・
vae（`sdxl_vae.safetensors`）・refiner（`sd_xl_refiner_1.0.safetensors`）の3つとも欠落。
refinerに相当するcheckpointが実機に1本も無く、実在する2本はいずれもIllustrious系の
finetuneでrefinerの代わりにはならない。無効なので実害は無い。

HuggingFaceからのダウンロードは可能（認証不要、CreativeML Open RAIL++-M、
refiner 6.08GB＋base 6.94GB＝約13GB）。ただし base段が素のSDXL 1.0である以上、
有効化するとIllustriousではなくSDXL 1.0で生成することになり、漫画用途では
現行より落ちる見込み。**refinerがイラスト系finetuneの出力を良くするかは未検証。**
2026-08-29時点では入れない判断。

#### 有効ワークフローの最終確認（2026-08-29、実機のlive `/object_info`）

新しい `comfyCollectValueMismatches()` に既定ワークフロー18本を通した結果。

| ワークフロー | enabled | ノード | 値 |
|---|---|---|---|
| `inspyrenet.json` | true | OK | OK |
| `SDXL.json` | true | OK | OK |
| `SD15_SDXL.json` | true | OK | OK |
| `Upscaler.json` | true | OK | OK |
| `Inpaint_SDXL.json` | true | OK | OK |
| `Angle_QwenEdit.json` | true | OK | OK |
| `SDXL_faceDetailer.json` / `SDXL_faceDetailer_Lora.json` | false | OK | OK |
| `FluxSimple.json` / `FluxDiffusion.json` | false | OK | OK |
| `Z_Image_turbo.json` / `Qwen_Image_gguf.json` | false | OK | OK |
| `SDXL_Lora.json` | false | OK | ckpt `sdXL_v10VAEFix` / lora `detailed(sdxl)` が欠落 |
| `SDXL_Refiner.json` | false | OK | ckpt 2本 + vae `sdxl_vae` が欠落 |
| `SD15.json` | false | OK | ckpt `dreamshaper_8` が欠落 |
| `SD15_VAE.json` | false | OK | ckpt `dreamshaper_8` / vae `vae-ft-mse-840000-ema-pruned` が欠落 |
| `SD15_Lora.json` | false | OK | ckpt / vae / lora の3件が欠落 |
| `FluxNF4.json` | false | **`CheckpointLoaderNF4` が無い** | — |

**有効な6本はすべてノード・モデルとも欠落ゼロ。** 残る欠落は無効な6本のみ。

`ComfyUI_T2I_ByFluxNF4` については、上で「`CheckpointLoaderNF4` ノード自体の存在も未検証」と
していたが、**このノードは実機に存在しない**ことが確定した。モデル名以前に動かない。


### 1.3 ワークフローエディタのTypeに `I2I_Angle` が無い

`comfyuiTypes`（`comfyui-workflow-editor-tab.js:2`）は
`["T2I","I2I","REMBG","Upscaler","Inpaint"]` の5種のみ。
Angleワークフローのタブを開くと選択肢に一致がなく先頭の `T2I` が選ばれた状態になる。
そのまま保存するとタイプが変わる可能性がある。

#### 対応（2026-08-29）

`comfyuiTypes` の固定配列を廃止し、生成側が引ける種別
`COMFYUI_WORKFLOW_TYPE_KEYS`（`comfyui-management.js`）から
`getComfyuiWorkflowTypes()` で取り出す形にした。種別の定義が1か所になったので、
今後種別を足してもエディタ側の追記漏れは起きない。
`COMFYUI_WORKFLOW_TYPE_KEYS` は `defer` で後から読まれるため、参照はタブ描画時に行う。

加えて、一覧に無いTypeを持つワークフローを開いた場合は、そのTypeを選択肢に追加して
選択状態を保つようにした（selectが先頭を指して保存でTypeが失われるのを防ぐ）。

Typeは翻訳せず種別名をそのまま出す既存表示に合わせたので、翻訳キーの追加は不要。
`I2I_Angle` は既存の `Upscaler` より長いため、
`.comfui-tab-type-dropdown` の `width:20%` を `width:auto` + `max-width:40%` に変えた。

未対応（別件・全種別に共通）: `comfyui-workflow-editor.js` の `onTabEnabledChanged()` は
`tab.workflow.type===type` を見ているが、`tab.workflow` はワークフローJSONで `type` を持たない。
この比較は常に false で、実質何もしていない。ラジオの排他は
`comfyui-workflow-editor-tab.js` 側のDOM操作で成立しているため実害は出ていない。

---

### 1.4 既定ワークフローを直しても、既に使っている人には届かない

**2026-08-29にアプリを開いて分かった。1.1〜1.3の修正の効きが、新規インストールに限られる。**

`addDefaultWorkflows()`（`comfyui-workflow-editor.js:116-131`）は
`existsByName()` で**名前が一致したら何もしない**。
既定ワークフローの定義を直しても、IndexedDB（`workflowStorage_local`）に
同じ名前で保存済みのものがあれば、そちらが使われ続ける。
`comfyuiSelectWorkflow()` も `getEnabledWorkflowByType()` も保存側を読む。

実際に開いた環境（保存日 2026-08-22）の有効ワークフローは、修正後も以下のままだった。

| ワークフロー | 保存されている値 | 実機 |
|---|---|---|
| `SDXL.json` (T2I) | `sd_xl_refiner_1.0_0.9vae.safetensors` | 無い |
| `SD15_SDXL.json` (I2I) | `illustrious\waiNSFWIllustrious_v50.safetensors` | 無い |
| `Inpaint_SDXL.json` (Inpaint) | `sd_xl_base_1.0.safetensors` | 無い |

**マスクだけは影響を受けない。** 保存済みの `Inpaint_SDXL.json` は
LoadImageMask が `{"image":"inpaint_mask.png","channel":"alpha"}` の旧形式のままだが、
`migrateLegacyMaskPlaceholder()` が実行時に揃えるため結果は正しくなる。
実際にアプリ上で保存済みデータへ実コードの置換順を当てて確認した:

```
LoadImage      → {"image":"REAL_IMAGE.png","upload":"image"}
LoadImageMask  → {"image":"REAL_MASK.png","channel":"red","upload":"image"}
```

**モデル名には同じ移行を入れていない。** 旧既定値を実装に埋め込むことになり、
ユーザーが自分で変えた値まで書き換える危険があるため。
その代わり、1.2で足した照合が実行前に止めて具体名を出す。
**利用者は設定画面で選び直す必要がある。**

`Delete` を押しても既定からは戻らない。`markDefaultWorkflowDeleted()` が
localStorage の `deletedDefaultWorkflows_<provider>` に名前を積むため。

#### 判断: 保存済みワークフローは上書きしない（2026-08-29、ユーザー決定）

**「既定に戻す」導線は作らない。設定画面で選び直す。**

既定ワークフロー定義に対する今回の変更は、差分を取ると**5行しかない**。

| 変更 | 種類 | 保存済みデータへの影響 |
|---|---|---|
| `Inpaint_SDXL` ckpt `sd_xl_base_1.0` → `illustrious\\waiIllustriousSDXL_v160` | モデル名 | 選び直しが要る |
| `SDXL.json` ckpt `sd_xl_refiner_1.0_0.9vae` → 同上 | モデル名 | 選び直しが要る |
| `SD15_SDXL.json` ckpt `waiNSFWIllustrious_v50` → `_v120` | モデル名 | 選び直しが要る |
| `Inpaint_SDXL` LoadImageMask `image` → `%mask%` | 構造 | **不要**（実行時に移行） |
| `Inpaint_SDXL` LoadImageMask `channel` → `red` | 構造 | **不要**（実行時に移行） |

構造の2件は `migrateLegacyMaskPlaceholder()` が実行時に揃えるため、
保存済みデータのままで正しく動く。**残りはモデル名だけ。**

モデル名は環境ごとに違い、**利用者が意図して選んでいるもの**である。
新しい既定値を自動で有効にすると、その選択を黙って奪うことになる。
既定の更新を保存済みデータへ流し込む仕組みは作らない。

**取るべき導線**: 1.2で足した照合が実行前に止め、
設定画面のバナーと `⚠ <値>` が該当箇所を名指しする。利用者はそこで選び直す。

### 1.5 UIの実機確認（2026-08-29）

Chrome拡張は `file://` のページを扱えない。`navigate` だけでなく
`javascript_tool` / `read_page` / スクリーンショットも同じエラーで拒否される
（`llm_doc/chrome.md` の記述より制約が強い）。
`python -m http.server` でローカルに出して確認した。
DOM・CSS・ドロップダウンの中身はプロトコルに依存しないが、
`file://` 固有の挙動はこの方法では見ていない。

確認できたこと:

- `getComfyuiWorkflowTypes()` → `["T2I","I2I","REMBG","Upscaler","Inpaint","I2I_Angle"]`。
  旧 `comfyuiTypes` は消えている
- 18タブすべてのTypeドロップダウンに `I2I_Angle` が入っている
- **`Angle_QwenEdit.json` の選択値が `I2I_Angle`**（1.3の症状が解消）。
  他も `inspyrenet.json`→REMBG / `SD15_SDXL.json`→I2I /
  `Upscaler.json`→Upscaler / `Inpaint_SDXL.json`→Inpaint と正しい
- 欠落のあるワークフローに警告バナーが出る。文言は
  「⚠ ワークフローに、ComfyUI側に無い値を指している項目があります」＋解決法＋該当箇所
  （`#4 CheckpointLoaderSimple.ckpt_name = sd_xl_refiner_1.0_0.9vae.safetensors`）
- 該当する入力ラベルに `comfui-input-label-warning` が付く
- selectが現在値を `⚠ <値>` として先頭に保持している。
  黙って別名に置き換わる既存の不具合は解消（`sd_xl_refiner_1.0_0.9vae` /
  `detailed(sdxl)` / `sdXL_v10VAEFix` / `sd_xl_base_1.0_0.9vae` / `sdxl_vae` で確認）
- コンソールのエラーは ServiceWorker の MIME type のみ。
  `python -m http.server` が `.js` を `text/plain` で返すためで、アプリ側の問題ではない


## 2. ComfyUI環境の実測（2026-08-29）

### 2.1 ノード

「実在するか要確認」としていたものは**全部あった**（2943クラス）。

- ControlNet: `ControlNetLoader` / `ControlNetApplyAdvanced` / `SetUnionControlNetType` ほか、
  ACN（Advanced-ControlNet）系一式
- 前処理: `DWPreprocessor` / `OpenposePreprocessor` / `AnimeLineArtPreprocessor` /
  `LineArtPreprocessor` / `DepthAnythingV2Preprocessor` / `CannyEdgePreprocessor` / `HEDPreprocessor` /
  `Manga2Anime_LineArt_Preprocessor` / `AnimeFace_SemSegPreprocessor` / `MeshGraphormer-DepthMapPreprocessor`
- 背景除去: `InspyrenetRembg` / `InspyrenetRembgAdvanced` / `BiRefNet` / `BiRefNetRMBG` / `BiRefNet_Hugo` /
  `LayerMask: RemBgUltra`
- セグメンテーション: `SAMLoader` / `SAM3Segmentation` / `Sam2Segmentation` /
  `GroundingDinoSAMSegment (segment anything)`
- 検出・修復: `UltralyticsDetectorProvider` / `FaceDetailer` / `UltimateSDUpscale`
- **タグ付け: `WD14Tagger|pysssss` / `camie_tagger_mira` / `cl_tagger_mira`**
- ポーズ編集: `easy poseEditor`

**`WD14Tagger|pysssss` が存在する意味は大きい。**
アプリのロール定義上 tagger は SD WebUI 専用だが（3.1参照）、
ComfyUI側にはタグ付けノードがあるので、ワークフローとして組めば
ComfyUI単独でも「生成した絵にどのタグが立つか」を測れる。

### 2.2 モデル

| 種別 | 件数 | 備考 |
|---|---|---|
| checkpoints | 5 | SD1.0系3、illustrious系2。**SDXL baseもPonyも無い** |
| unet(diffusion_models) | 11 | `qwen_image_edit_2511_bf16` / `z_image_turbo_bf16` / flux / wan など |
| loras | 92 | `qwen-image-edit-2511-multiple-angles-lora` 実在。`CleanLineArt` もある |
| controlnet | 85 | `lineart_anime` / `scribble` / `openpose` / `softedge` / `canny`（SD15・SDXL両方）/ `OpenPoseXL2` / IP-Adapter |
| upscale_models | 4 | `RealESRGAN_x4plus_anime_6B` / `RealESRGAN_x4plus` / `4x-UltraSharp` / `SwinIR_4x` |
| vae | 11 | |
| ultralytics検出器 | 1 | `bbox/face_yolov8m.pt` のみ。**手の検出モデルは無い** |
| SAM | 2 | `sam_vit_b` / `sam_vit_h` |

意味するところ:

- **ControlNet系の案（ラフ→コマ絵、ポーズ指定）はモデルが揃っている。**
  `lineart_anime` と `scribble` と `OpenPoseXL2` が全部ある
- **Upscalerの選択肢追加は今日できる。** `4x-UltraSharp` と `SwinIR_4x` が既にある
- **手の破綻検出はモデル追加が要る。** 顔検出しか入っていない

### 2.3 Qwen-Image-Edit 2511 は日本語の指示を解する（実測）

登録済みAngleワークフローから MultiAngle LoRA を外した「汎用の指示編集」構成で、
同じ内容の指示を英語と日本語で与え、結果を数値で比べた。
指示は「背景を単色の赤にする」。画像の周辺10%の帯の色を測れば、効いたかが客観的に出る。

元画像は公園の背景（周辺帯 R=105 G=181 B=108、緑が優位で赤の優位は-40）。

| 指示 | 結果の周辺帯 | 赤の優位 | 元画像からの差 |
|---|---|---|---|
| `change the background to a solid red color` | R=199 G=26 B=27 | +173 | **+213** |
| `背景を単色の赤色に変えてください` | R=188 G=22 B=23 | +165 | **+205** |

**日本語でも英語とほぼ同じだけ効く。** プロンプトを英語に訳す処理は要らない。
CLAUDE.mdの「LLMプロンプトは日本語で書く」方針と衝突しない。

**ただし遅い。** この環境（RAM 51GB）での実測は**1回あたり5〜6分**
（英語381秒、日本語302秒。初回はモデル読み込みを含む）。
比較用にSDXLのT2Iは20ステップ30秒だった。

設計上の意味:

- 指示編集はキューに積む前提の機能にする。押して待たせる操作にはできない
- **表情差分をN通り一括生成する案は、6通りで30分以上かかる計算になる。**
  そのままでは実用にならない。Lightning LoRAの4ステップでこの時間なので、
  ステップ数ではなくモデルの大きさが効いている。fp8などの軽い重みが要る

---

## 3. アプリ側の構造（コードで確定）

### 3.1 ロールの割り当て

`roles`（`ai-roles.js:19-62`）の実際:

| プロバイダ | 持つロール |
|---|---|
| A1111 (SD WebUI) | Text2Image / Image2Image / **Image2Prompt_DEEPDOORU** / **Image2Prompt_CLIP** / RemoveBG / **ADetailer** / PutPrompt / PutSeed |
| COMFYUI / RUNPOD_COMFYUI | Text2Image / RemoveBG / Upscaler / Image2Image / Inpaint / I2I_Angle |
| FAL_AI | Text2Image / Image2Image / Upscaler / RemoveBG |
| GOOGLE_IMAGE | Text2Image / Image2Image |
| GROK / OLLAMA | Text2Prompt / Image2Prompt_LLM |

**tagger（DeepDanbooru・CLIP）と ADetailer は SD WebUI にしか割り当てられていない。**
ComfyUI にこれらのロールは無い。
「生成→タグで検査→やり直し」の類はSD WebUI併用が前提になる
（ただしComfyUI側にノードはあるので、ワークフローとして組む道はある。2.1参照）。

### 3.2 tagger の戻り値

`sdwebuiInterrogate()`（`sdwebui-multi-call-api.js:170-210`）:

- 返るのは `result.caption` という**カンマ区切りの文字列だけ**。確信度は付かない
- **結果をコマのプロンプトに追記する**:
  `layer.text2img_prompt = layer.text2img_prompt + ", " + result.caption`

検査目的で呼ぶとプロンプトが汚れる。**書き戻さない版が別に要る。**

### 3.3 その他（確定）

| 項目 | 確認結果 | 根拠 |
|---|---|---|
| コマのプロンプト | **全コマが必ず持つ**（中身は空のことがある）。生成時に必ず初期化される | `setText2ImageInitPrompt()` を `panel-manager.js:531`、`panel-template.js:98/178/279/310`、`knife-split-engine.js:314-315` が呼ぶ |
| 読み順の計算 | **既にある**。行バンド化→左右ソート。`rightToLeft` はUIのチェックボックスから効く | `sortPanelsInReadingOrder()` `llm-storyboard-service.js:218-248`、`llm-story-ui.js:171-172` |
| テンポ検査 | 既存は**2件**（「全コマに人物」「場面転換の直後がestablishingでない」） | `findPanelRhythmProblem()` 同:291-314 |
| セリフの話者 | **存在しない**。吹き出しは SVG / Text / Rect が `setGUID` で相互リンクするだけ | `speech-bubble-text.js:275-284` |
| 吹き出しとコマの紐付け | **無い**。`relatedPoly` は画像↔コマ専用。所属は座標推定になる | `fabric-management.js:184`、`panel-manager.js:277-288` |
| 縦書きの行数・字送り | **アプリが持っている**（`_wrapText` / `_textLines` / `measureLine` / `__charBounds`） | `vertical-textbox.js:228-438` |
| 1ロールに複数プロバイダ | **不可**。割り当てUIがラジオボタン | `role-assignment-ui.js:57` |
| プロバイダ横断の並列 | **可能**。キューはプロバイダごとに独立（各concurrency=1） | `ai-management.js:2-7` |
| 参照画像の上限 | 14枚で例外を投げる。加えて18MBのペイロード上限 | `reference-collector.js:7-8,372,386` |
| 参照画像の役割 | `source` / `character` / `background` / `prop` / `other` の5種。「前のコマ」は無い | 同:17-23 |
| 複数画像のアップロード | **既に実績がある**。Inpaintが画像とマスクを別々に送る。ファイル名は時刻＋連番で衝突しない | `comfyui-management.js:310-320`、`comfyui-util.js:54-70` |
| Danbooruタグ件数辞書 | **同梱されていない**。ただし閉じた語彙は手作業で件数確認済み | `llm-storyboard-service.js:21` |

### 3.4 複数画像を別ノードへ渡せるか

**渡せる。** `updateValueByTargetValue()` はノードを再帰走査する文字列全置換なので、
LoadImage の値に `%image_char%` のようなプレースホルダを書いておけば個別に差し込める。
`updateNodesByInputName()` の「入力名一致で全ノード」という制約は受けない。
既存の `%prompt%` と同じ流儀で、プレースホルダを持たない既存ワークフローは影響を受けない。

---

### 3.x Upscalerのモデル選択は「仕組みはあるが繋がっていない」（2026-08-31 確認）

実機に4本入っているが、ComfyUIのワークフローが使っているのは1本だけ。

```
4x-UltraSharp.pth              未使用
RealESRGAN_x4plus.pth          未使用
RealESRGAN_x4plus_anime_6B.pth Upscaler.json が使用中（焼き込み）
SwinIR_4x.pth                  未使用
```

**選択肢を作る仕組みは既にある。** `comfyuiFetchUpscaler()`
（`comfyui-management.js:510`）が `/object_info` の `UpscaleModelLoader.model_name` を読み、
`updateUpscalerDropdown()` でドロップダウンを埋めている。

**しかしそのドロップダウン（`text2img_hr_upscaler`）を読んでいるのは
`sdwebui-settings.js:151` だけ**で、SD WebUI の hires-fix 用。
ComfyUI側は `ComfyUI_Upscaler` の `model_name` に焼き込まれたままで、
生成時に差し替える経路が無い。

**ワークフローを4本並べるのは誤り。** 中身は `model_name` 一行しか違わない。
既存のドロップダウンをComfyUI側へ繋ぎ替えるのが正しい。
選択肢は `/object_info` から取るので、後からモデルを足しても自動で選べる。


## 4. ブラウザの実測（`file://` で実行）

| 項目 | 結果 |
|---|---|
| base64からのWASM実体化 | **OK**（`third/lz4/` と同じ方式） |
| `fetch()` でのローカル読み込み | FAIL（想定どおり） |
| **Blob URL からの Web Worker** | **OK**（2026-08-29 再測。下の訂正を参照） |
| Blob URL の **module** Worker（`{type:"module"}`） | FAIL |
| 動的import: 隣に置いた `./mod.mjs` | **FAIL**（`Failed to fetch dynamically imported module`） |
| `<script type="module" src="./mod.mjs">` | FAIL（onerror） |
| **動的import: `blob:` URL のモジュール** | **OK** |
| **動的import: `data:` URL のモジュール** | **OK** |
| `blob:` モジュールの中から別の `blob:` を import | **OK** |
| 動的import: `http://127.0.0.1`（CORS付き） | OK |
| `importmap` | 対応 |
| `getImageData`（data: URL の画像） | **OK** |
| `getImageData`（`file://` の画像） | FAIL（SecurityError: canvas汚染） |
| IndexedDB | OK |
| 音声合成 | OK（23音声、うち日本語5） |
| WebGPU | 利用可 |
| WebGL2 | OK |
| `crossOriginIsolated` | false |
| `SharedArrayBuffer` | **undefined** |

意味するところ:

#### 訂正（2026-08-29）: Workerは動く。前回の「FAIL」は測定側のバグだった

初回の `filetest.html` は Worker を作ったあと **`postMessage()` を呼んでいなかった**。
返事が来るはずのない状態で3秒待ってタイムアウトし、それを「Workerが動かない」と記録していた。
`postMessage()` を足して測り直したところ **OK（`21*2=42`）**。

**この誤りが「ブラウザ内でAIを動かす案すべて」を保留にしていた根拠だった。**
（→ `review-checklist.md` 199「まず自分の計測側を疑う」）

- **裏スレッドは使える。** classic Worker（Blob URL）は動く。
  `{type:"module"}` の Worker だけが不可なので、Workerに渡すコードは classic 形式にする
- `SharedArrayBuffer` は無いまま（`crossOriginIsolated` false）。
  **WASMのマルチスレッドは使えない**ので `numThreads = 1` は変わらず必要
- 重い推論をWorkerへ逃がせるため、**キャンバスが固まる問題は回避できる**
- **キャンバスの画素読み取りは問題ない。** 生成画像は `data:` URL か
  ページ内で作った blob URL で入るため汚染しない（`getImageData` は本番10箇所以上で稼働中）。
  ただし**ユーザーがローカル画像を `file://` のURLで読み込む経路を作ると汚染する**
- 読み上げによるテンポ検品は、モデル無しで今日から作れる

---

## 4b. ブラウザ内推論は成立する（2026-08-29 実測。結論が変わった）

**onnxruntime-web 1.29.0 を `file://` の classic Worker で動かし、実モデルで推論まで通した。**
「ブラウザ内でAIを動かす案すべて」を保留にしていた根拠は2つとも消えた。

### 4b.1 動かし方（これで通る）

1. `ort.wasm.min.js` / `ort.min.js`（classic script、global `ort`）を `importScripts` で読む
2. Emscriptenグルーの `.mjs` を**文字列から `blob:` URL にして** `env.wasm.wasmPaths = {mjs: blobUrl}`
3. `.wasm` 本体を **`env.wasm.wasmBinary`** に ArrayBuffer で渡す（fetchを一切させない）
4. `env.wasm.numThreads = 1` / `env.wasm.proxy = false`

**既定のままだと失敗する。** 隣に置いた `.mjs` を動的importしようとして
`Failed to fetch dynamically imported module` になる（実測で確認）。

### 4b.2 速度（WD14タガー 311MB、入力 1x448x448x3）

| 実行環境 | ロード | 1枚あたり |
|---|---|---|
| **ブラウザ webgpu**（`file://` / Worker） | 0.9s | **53 ms**（初回 0.6s） |
| ブラウザ wasm 1スレッド（同上） | 1.7s | 6,093 ms |
| ネイティブCPU 1スレッド（python onnxruntime 1.23.2） | 1.4s | 2,039 ms |
| ネイティブCPU 全コア（同上） | 1.2s | 950 ms |
| ComfyUI経由（GPU。8.4の実測） | — | 1,000〜2,000 ms |

別々に作った2枚のページで同じ結果になった（webgpu 53ms / 77ms、wasm 6,093ms / 6,673ms）。
GPUは NVIDIA Lovelace。`navigator.gpu` は **Worker の中からも見える**。

**ブラウザのWebGPUがComfyUI経由より20〜40倍速い。**
ComfyUIの1〜2秒はHTTP往復・画像アップロード・キュー・ノード処理が大半で、
モデルの計算自体は50ms程度だということ。ブラウザから直接叩くとその往復が消える。

**wasm（CPU）には使い道が無い。** ネイティブCPU1スレッドの3倍遅く、
ComfyUI経由よりも遅い。**WebGPUが使えない環境では、この用途では成立しない。**

小さいモデルでは逆転する。`face_landmark`（2.7MB）は wasm 9ms / webgpu 13ms で、
GPUへの転送と起動のコストが計算量を上回る。**モデルの大きさで選ぶ必要がある。**

### 4b.3 実装上の制約（実測で判明）

- **`fetch()` が使えないので、モデルをページに渡す手段は2つしかない。**
  ソースへ埋め込む（base64）か、`<input type="file">` で選んでもらうか。
  311MBは埋め込めないので、**一度選んでもらって IndexedDB に入れて使い回す**形になる。
  ファイル選択からの読み込み自体は動作を確認済み
- **大きいモデルを `postMessage` で往復させると落ちる。**
  311MBのArrayBufferと37MBのランタイム文字列を一緒に送ったところ、Workerが静かに死んだ
  （`onerror` も鳴らない）。**`File` オブジェクトのまま渡し、Worker側で `arrayBuffer()` する。**
  ランタイムは起動時に1回だけ送り、Workerを使い回す
- ランタイム本体（jsep版 `.wasm`）は 27MB。base64で同梱すると **約37MB がリポジトリに乗る**。
  ここは判断が要る。モデルと同じくファイル選択にする手もある
- `{type:"module"}` の Worker は `file://` で動かない。**classic Worker を使う**
- `SharedArrayBuffer` は無いので `numThreads=1` は必須

### 4b.4 まだ確かめていないこと

- **タグの中身が正しいかは見ていない。** 計測は `Float32Array.fill(0.5)` の定数入力で、
  計算量は同じだが出力の妥当性は確認していない。画像の前処理（448x448・チャンネル順・
  正規化）を合わせて、ComfyUI経由の結果と突き合わせる必要がある
- GPUメモリが少ない環境で 311MB が載るか
- WebGPU が使えない環境（古いGPU・ドライバ）でどうするか。
  wasmフォールバックは6秒かかるので**実質的に使えない**


## 5. まだ確かめていないこと

- **SD WebUI 側**（未起動）。tagger の実際の戻り値の内容、ADetailerの挙動
- モデルの絵作りに関する前提すべて。粗い線でのControlNetの効き、
  寄りコマを作るときの元解像度の下限、低denoiseでの画風統一、
  ドラフトと本番のseed再現性、denoiseの綱引き
- アニメ絵での姿勢推定・顔埋め込みの精度
- Fal.ai の ControlNet 対応
- ONNX Runtime Web を実際に載せたときの速度と、モデル重みの読み込み経路
  （`<input type="file">` → IndexedDB を想定しているが未試行）

検証に使ったスクリプトはセッションのscratchpadに置いた。再実行する場合は
ComfyUIを起動した状態で `probe_channel.py`（マスクのチャンネル）と
`probe_inpaint_e2e.py`（Inpaintの端から端まで）が短時間で終わる。

---

## 6. 外部の事実（Web調査。2026-08-29）

一次情報を当たった結果。ローカルでは確かめられないもの。

### 6.1 ONNX Runtime Web はこの制約下でも道がある（ただし穴が1つ）

Workerが動かず `SharedArrayBuffer` も無い環境（4章参照）でも、公式APIで回避できる。

- `ort.env.wasm.numThreads = 1` を明示すると SharedArrayBuffer 判定に入らず、Workerも作らない
- `ort.env.wasm.proxy` は既定 false。そもそも **WebGPU EP はプロキシWorkerと併用不可**＝メインスレッド実行が前提の設計
- **バイト列で渡すAPIが2つある**
  - モデル重み: `InferenceSession.create(buffer: Uint8Array, options?)`
  - ランタイム本体: `env.wasm.wasmBinary`（これを設定すると `wasmPaths` は無視され、.wasmのfetchをスキップできる）
  → `third/lz4/` と同じbase64同梱方式が使える
- UMD（classic script）版 `ort.min.js` / `ort.webgpu.min.js` が dist にあるので `<script src>` で読める

#### 穴は塞がった（2026-08-29 実測）

ORT は Emscripten グルーの `.mjs` を動的importする。これが `file://` で通るかが唯一の穴だった。
実機で測った結果:

| 読み込み方 | 結果 |
|---|---|
| 隣に置いた `./mod.mjs` を `import()` | **FAIL** |
| `<script type="module" src="./mod.mjs">` | **FAIL** |
| **`blob:` URL のモジュールを `import()`** | **OK** |
| **`data:` URL のモジュールを `import()`** | **OK** |
| `blob:` モジュールの中から別の `blob:` を import | **OK** |

**ファイルとして置いた `.mjs` は読めないが、モジュール機構そのものは生きている。**
グルーを**文字列として同梱し、実行時に `blob:` URL へ変換して import させれば通る**。
`third/lz4/` の base64 同梱と同じ考え方で、既にこのリポジトリが採っている方式。

`fetch()` でローカルファイルを読めないため、**同梱は実行時取得ではなくソースへの埋め込みになる**。
ORTのグルーとwasmを合わせたサイズは未計測。

**未検証**: 実際に onnxruntime-web を読み込んで推論を1回通すところまではやっていない。
上記は「妨げになっていた個々の機構が動く」ことを確かめた段階。

出典: https://onnxruntime.ai/docs/tutorials/web/env-flags-and-session-options.html
/ https://onnxruntime.ai/docs/api/js/interfaces/Env.WebAssemblyFlags.html
/ https://github.com/microsoft/onnxruntime/issues/24325

### 6.2 Fal.ai は ControlNet に対応している

- `fal-ai/sdxl-controlnet-union` — canny / depth / openpose / segmentation / teed / normal を**個別フィールド**で受け取る。各々に前処理トグルあり。`/image-to-image`、`/inpainting` のサブエンドポイントもある
- `fal-ai/fast-sdxl-controlnet-canny`（軽量版）、`fal-ai/flux-general`（FLUX系）
- 呼び出しは queue プロトコル。生のHTTPエンドポイントURLは公開ページに明示されておらず、OpenAPIスキーマ経由

出典: https://fal.ai/models/fal-ai/sdxl-controlnet-union/api

### 6.3 ベクタ化はライセンスで選択肢が絞られる

| 候補 | ライセンス | 使えるか |
|---|---|---|
| **ImageTracer.js** | **Public Domain** | **使える**（純JS・wasm不要・Worker不要） |
| esm-potrace-wasm / wasm-potrace / node-potrace | **GPL-2.0** | 使えない（ライセンス伝播。かつESM専用で`file://`不可） |
| @visioncortex/vtracer | MIT | ブラウザ向け配布物が無い（nodejs向けwasmビルド） |
| vectortracer | MIT | ESM配布。`file://` 可否は不明 |

**実質 ImageTracer.js 一択。** potrace系はGPL-2.0なので組み込めない。

### 6.4 漫画特化OCRは実在する（ComfyUIノードは無い）

- `kha-white/manga-ocr`（**Apache-2.0**）。縦書き・ふりがな対応、**吹き出し内の複数行を分割せず1パスで認識**。手書きは不可
- ONNX版 `onnx-community/manga-ocr-base-ONNX` あり。**最小構成（q4f16）で約74MB**
- ブラウザ動作の前例あり（`rDarge/manga-ocr-for-chrome`）。**そこでも「ORTのスレッド数を制限してWorkerのCSP問題を回避」しており、本アプリの制約と方向性が一致する**
- **ComfyUIノードは見つからなかった**（汎用OCRノードのみ）

出典: https://github.com/kha-white/manga-ocr / https://huggingface.co/onnx-community/manga-ocr-base-ONNX

### 6.5 アニメ絵のキャラ同一性判定は「ある」

案の段階で「アニメ絵で使える顔埋め込みは無いかもしれない」と書いたが、**定番が実在する**。

- **CCIP**（Contrastive Anime Character Image Pre-Training、deepghs）。2枚のアニメキャラ画像の同一性を判定する
- 精度: `ccip-caformer_b36-24` で **F1 0.9409 / Precision 0.9383 / Recall 0.9436、閾値 0.2132**
- **ONNX版 `deepghs/ccip_onnx` がある** → ブラウザ持ち込みの現実味がある
- 実運用ではLoRA学習データの誤タグ除去フィルタとして使われている
- **ライセンス注意: 重みは `openrail`**（`deepghs/imgutils` のコードはMITだが重みは別）
- ArcFace / Arc2Face は実写向けで、アニメ絵向けではない

出典: https://huggingface.co/deepghs/ccip_onnx / https://github.com/deepghs/imgutils

### 6.6 背景除去は BiRefNet が髪・イラストで優位（比較は1件のみ）

- **論文レベルの直接比較は存在しない。** BiRefNet論文はInSPyReNetに言及していない
- 数値のある head-to-head は `egeorcun/lucida` の1件のみ（203枚、GT alphaに対するMAE、低いほど良い）

| カテゴリ | InSPyReNet | BiRefNet-HR |
|---|---|---|
| 髪 | 0.0069 | **0.0048** |
| イラスト | 0.0242 | **0.0157** |

- InSPyReNet は複数オブジェクトの物撮り・細線／穴あき構造で相対的に強いとの記述あり
- **中立の第三者ベンチは見つからなかった。**上記はBiRefNetファインチューン側の自己ベンチである点に注意
- ライセンスは両方MIT（ただし学習データに研究限定のものを含む懸念は双方にあり得る）

出典: https://github.com/egeorcun/lucida / https://arxiv.org/html/2401.03407v5

---

## 7. ControlNetで構図をどこまで決められるか（実測。生成30枚）

**大半の条件が n=1。傾向としてしか読めない。** チェックポイントは
`waiIllustriousSDXL_v160` と `SD1.0\yden_v20` の2つのみで、他モデルに一般化できない。

### 7.1 棒人間の生線は使えない

ブラシで描いた棒人間をそのまま scribble / canny に渡す案は**成立しない**。

| ヒント画像 | 強度 | 結果 |
|---|---|---|
| 細線の棒人間 → canny | 1.0 | **線画がそのまま複製される。**WD14が `no humans, still life, monochrome` を返した |
| 太線の棒人間 → scribble | 1.0 | **頭の丸が黒い球として描かれる。**ControlNetは丸を「頭」と解釈しない |
| 太線の棒人間 → scribble | 0.4 | 完全に無視される |

細線＝無視、太線＝そのままコピー、で**中間が無い**。
ヒント画像はモデルの学習形式に合わせる必要がある。
**手描きの棒人間からCOCO-18骨格への変換が必須**で、これはアプリ側の実装コストになる。
つまりこの案は「ブラシで描いた線を渡すだけ」では済まず、
骨格を持つ専用オブジェクト（ポーズ人形）を作る話になる。

### 7.2 OpenPose形式なら位置と大きさは追従する

SDXL + `OpenPoseXL2`、強度1.2。誤差は画面サイズに対する%。

| レイアウト | Δ中心x | Δ頭頂 | Δ足先 | 顔の高さ（実測/指定） |
|---|---|---|---|---|
| 全身・中央 | +0.1% | −5.1% | +4.8% | 12.0 / 11.9 |
| 小さく左下 | −2.1% | −4.4% | +3.7% | 6.4 / 6.6 |

- **強度は1.0〜1.2が要る。** 0.5 / 0.8 では「小さく左下」の指定が無視され、
  素の生成と同じ構図になった条件があった
- **骨格より上下に各5%はみ出すのが定常。** 髪が頭頂キーポイントより上、
  足元の影が足先より下に出るため。コマの縁に寄せるときは、このぶん内側に骨格を置く必要がある

### 7.3 ControlNetは「引く」方向にしか効かない

**これが一番効く発見。**

| | 素の生成 | ControlNetあり |
|---|---|---|
| SDXL | 顔の高さ 20.5% | 6.4〜12.9% |
| SD15 | 顔の高さ 38.9% | 11.6〜29.6% |

**素より寄る（顔を大きくする）方向に成功した条件は1つも無い**（6条件試して全滅）。
顔アップ用に骨格を画面の4倍にして頭だけ入るよう配置しても、
モデルは可視キーポイントの相対配置だけ拾って全身を描いた（指定54%に対し実測15.7〜19.0%）。

**寄りのコマはControlNetでは作れない。** latentのサイズ、プロンプト、切り出しなど別手段が要る。

### 7.4 判定指標の注意

**人物マスクのIoUは当てにならない。** 人物が画面いっぱいのときマスクが全面になり、
寄り絵でも「指定と一致」に見える（顔サイズ29.6に対し指定36.7でIoU 0.99）。
**顔bboxの高さ**のほうが判定として素直だった。

### 7.5 確かめられなかったこと

- 強度を上げると絵が硬くなるか。構図が安定した3点しか比較できず**判断できていない**
  （0.5→1.2でエッジ量+14%、コントラスト−9%だが根拠として弱い。目視では差が分からなかった）
- 顔アップの失敗が OpenPoseXL2 の性質なのか、骨格画像の描き方が学習形式とずれているせいなのか
- 立ち以外の姿勢、複数人、アスペクト比違いは一切試していない

---

## 8. 生成した絵を機械で検査できるか（実測。自前生成20枚）

**サンプルは1モデル・アニメ絵20枚のみ。正解は目視で付けたもので第三者検証はない。**
実写・厚塗り・モノクロ漫画では未検証。

### 8.1 結論: タグによる検査は使える。姿勢推定は使えない

| 検査項目 | 結果 | 使えるか |
|---|---|---|
| 距離（距離タグのargmax） | 18/20一致 | **使える** |
| 見切れ（`head_out_of_frame` / `lower_body` / `out_of_frame`） | 5/5捕捉、正常15枚で誤検出0 | **使える** |
| 人数 | 19/20（6人を`5girls`と誤り1件） | **使える**（3人以上は±1想定） |
| カメラ目線（`looking_at_viewer`） | 明確な14枚で14/14、誤検出0 | **使える** |
| 文字の写り込み（`english_text` / `speech_bubble`） | 2/2検出、18枚で誤検出0 | **使える** |
| 顔検出（`face_yolov8m`） | 顔21/21検出、顔なし8枚で誤検出0 | **使える**（余白追加が前提） |
| 姿勢推定（DWPose） | 既定で18枚中7枚のみ。設定変更しても10/18 | **使えない** |

### 8.2 距離の判定は「閾値で立ったか」では駄目

**意図タグは見切れた絵でも立つ。**

| 画像 | 意図 | 実際の絵 | タグ出力 |
|---|---|---|---|
| A01 | full_body | 脚のみ・頭部が枠外 | `full_body` + `head_out_of_frame` |
| B01 | upper_body | 胸部のみ・頭部が枠外 | `upper_body` + `head_out_of_frame` |
| H01 | full_body | スカートと靴のみ | `full_body` + `lower_body` |

`full_body` が立ったから全身が撮れている、とは言えない。
**距離タグ群のargmaxを採り、かつ見切れタグを併用する**必要がある。
この併用で見切れ5枚を全部捕まえ、正常な15枚での誤検出は0だった。

### 8.3 使えないタグ

- `signature` / `artist_name` は文字なし18枚中3枚で誤発火。**写り込み検査に使えない**
- `text` 単体はタグ語彙に無い。`english_text` で代替する

### 8.4 速度（判断に効く）

| 処理 | 時間 |
|---|---|
| SDXL 20step 1024x1024 生成 | 5〜10秒 |
| **WD14Tagger 1回** | **1〜2秒** |
| **face_yolov8m 1回** | **1秒** |
| DWPose | **60〜200秒** |

タグ検査と顔検出は生成のたびに回しても負担にならない。
**DWPoseだけ桁が違う。**生成ごとに回す処理には絶対にできない。

### 8.5 顔検出のbboxには余白が要る

`face_yolov8m` の bbox は目〜鼻を覆う「顔の芯」で、顎・口が外れることがある。
コマの切り出しに使うなら余白を足す前提。
極端な目のアップ（顔が画面より大きい）では検出0。後ろ姿では後頭部を「顔」として検出した
（「頭部領域」としてなら使える）。

### 8.6 タグ件数の辞書はローカルにあった（ただし用途に注意）

`comfyui-wd14-tagger/models/wd-v1-4-moat-tagger-v2.csv`、9,083行。
`tag_id,name,category,count` 形式で count は Danbooru の投稿数
（`1girl` 4,225,150 / `full_body` 463,008 / `cowboy_shot` 336,374）。

**これは「taggerが出力できるラベル集合」であって、画像生成モデルが解釈できるタグ集合ではない。**
プロンプトで使う語34件を照合したところ5件が不在だった
（`rim_lighting` `screentone` `panel` `onomatopoeia` `close_up`）。
`close_up` は存在せず、正しい表記は `close-up`。
**このCSVをプロンプトの門番にすると有効なタグを弾く。**
「taggerの検査対象タグが実在するか」の確認にだけ使える。

### 8.7 確信度は7段階でしか取れない

pysssssのノードはスコアを返さない。閾値を7段階（0.05/0.15/0.25/0.35/0.50/0.70/0.85）で
走らせて「消える閾値」から下限を求めるのがComfyUI経由での最大粒度。
**連続スコアが要るならONNXを直接叩く必要がある**（モデルとCSVはローカルにある）。

### 8.8 副次的な観測: 生成モデルの枠取りは当てにならない

`full body, head to toe, entire body visible` 系のプロンプトで4回試して、
全身が枠内に収まったのは**1回だけ**だった（waiIllustriousSDXL_v160, 20step）。
「フレーミングは指示で効かせるのが難しい」という前提は、20枚の範囲では裏付いた。

---

## 9. 一貫性・画質まわりの前提（実測。生成37枚）

**各実験 n=1系列。**サンプルとして足りる数ではない。

### 9.1 低denoiseのi2iは線を潰さない。しかし画風も寄らない

denoise 0.15〜0.50 で同一プロンプト・同一seedのi2iをかけた結果:

| denoise | ラプラシアン分散（base比） | 元の輪郭の残存率 | 新規に出た輪郭 | SSIM |
|---|---|---|---|---|
| 0.15 | 123% | 99.3% | 7.8% | 0.922 |
| 0.20 | 132% | 99.1% | 9.4% | 0.908 |
| 0.35 | 155% | 97.3% | 13.6% | 0.864 |
| 0.50 | 160% | 94.8% | 17.9% | 0.821 |

**「弱いi2iで線がぼやける」という懸念は外れていた。**
起きるのは劣化ではなく**線が足される**こと。線幅の中央値は全条件で3pxのまま。
顔だけ切り出して見ても同じ傾向で、ぼやけを示す数値は1つも出なかった。

**ただし画風統一には使えない。**
別チェックポイントの絵を種にしてi2iをかけ、狙いの画風へどれだけ進んだかを測った:

| denoise | 画風の進捗（種→狙いを100%として） |
|---|---|
| 0.15 | 3% |
| 0.25 | 4% |
| 0.35 | 6% |
| 0.50 | 13% |

彩度はむしろ逆方向（−14%〜−2%）へ動いた。目視でも4条件すべて種の画風のまま。
**ページ全体に低denoiseを通して絵柄を揃える案は成立しない。**

### 9.2 寄りのコマは元の顔が128px以上あれば作れる

全身絵から顔を切り出し（64/128/256px）→ RealESRGAN ×4 → FaceDetailer:

| 元の顔サイズ | 結果 |
|---|---|
| 64px | **FaceDetailerが別人の顔を作って埋める。**目視でも元と別顔 |
| 128px | 破綻なし。ただしネイティブ生成の1/5のディテール |
| 256px | ネイティブ生成相当（lapvar 751 vs 635） |

**1024幅の全身絵の顔は実測188px** で、128と256の間。つまり:

- 「引き→顔アップ」は破綻はしないが**顔が別人になる前提**
- 「膝上→バストアップ」は顔が300px超になるので範囲内

`FaceDetailer` の `guide_size` は512と1024で差が出なかった。
シャープさを足すのは拡大側で、FaceDetailerの役割は構造の作り直し。

### 9.3 背景を固定して人物を足すのは denoise 0.50〜0.60 で両立する

| denoise | 背景SSIM | 人物が出たか |
|---|---|---|
| 0.30 / 0.40 | 0.891 / 0.848 | 出ない（`no_humans`） |
| **0.50** | **0.799** | **出る** |
| **0.60** | **0.759** | **出る** |
| 0.70 / 0.85 | 0.681 / 0.564 | 出るが背景が崩れる |

目視でも0.50/0.60は同じ教室・同じ机と窓の配置のまま人物が入った。
**ただし余裕は狭い**（人物が出る最小denoiseと背景が崩れ始める点が隣接）。
**人物の位置・大きさ・ポーズは指定できずモデル任せ。**n=1シーン。

### 9.4 白黒化での潰れは一律には起きない

12枚を白黒化して前景/背景の輝度ヒストグラムの重なりを測ったところ、
**境界値だったのは1枚だけ**（夜・雨・濃紺制服）。他11枚は輪郭線が残るため分離した。

**常時走らせる検査としては費用対効果が低い。**
暗い場面・低彩度の場面に限って警告する形なら意味がある。

### 9.5 ドラフト→本生成は「同じ絵が高画質で出る」わけではない

同一seedで8stepと20stepを比べた結果、SSIM 0.45〜0.55
（無関係な絵どうしが0.29なので、まったくの別物ではない）。
**「同じ案の別テイク」程度。**構図案の選別には使えるが、
採用した絵がそのまま高画質で出てくることは期待できない。
