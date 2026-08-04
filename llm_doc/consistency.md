# キャラ・絵柄・色の固定（SDXL）

コマごとにキャラの顔が変わる、絵柄が変わる、色味が変わる。この3つを可能な限り
止めるための知見。対象はSDXL系（Illustrious / NoobAI-XL / Pony / Animagine 等の
アニメ系ファインチューンを含む）。

**現状のアプリはタグの一致しか持っていない**（→`prompt-composition.md` 8.5章）。
タグでは顔は揃わない。ここから先はアプリ側の機能追加になるので、
何にいくら払うと何が返ってくるのかを先に整理する。

---

## 0. 3つのブレは原因が違う。混ぜて対策しない

| ブレ | 何が原因か | 効く手 |
|---|---|---|
| **キャラ**（顔・髪型・服） | モデルは毎回ゼロから顔を作る。タグは「黒髪ショート」までしか指定できず、顔の造形はseedとノイズが決める | キャラLoRA / 参照画像（IPAdapter） / 顔だけinpaint |
| **絵柄**（線・塗り・トーン・目の描き方） | チェックポイントとプロンプト内の画風語で決まる。キャラLoRAが画風まで持ち込むことも多い | チェックポイント固定 / artist tag / 画風LoRA / LoRAブロックウェイト |
| **色**（彩度・色温度・肌や髪の色） | VAE、2パス目（アップスケール）、プロンプトの微差、そもそもseed | 後処理のカラーマッチ / VAE固定 / パレットを参照画像で与える |

**一番安いのは「絵柄」と「色」で、一番高いのが「キャラ」。**
順番を逆にすると、LoRAを作ったのに絵柄が揃わない、という状態になる。

---

## 1. 段階0 — 追加コストなしで今すぐ効くもの

学習も参照画像も要らない。ここを詰めずに上の段へ行かない。

### 1.1 生成条件を1つも動かさない

同じページ・同じ作品の中で、以下が1つでも変わると絵柄と色が動く。

- チェックポイント（ハッシュまで同じもの）
- VAE（チェックポイント内蔵かどうかも含む。SDXLはfp16でNaNを出す既知の問題があり、
  `sdxl_vae` のfp16 fix版を明示的に読ませる構成が広く使われる）
- サンプラー / スケジューラ / ステップ数 / CFG
- 解像度バケット

**解像度バケットは本アプリでトレードオフになる。** `PANEL_SDXL_BUCKETS`で
コマの形に合わせて解像度を変える機能（既定オフ）は、構図の破綻を防ぐ代わりに
コマ間で絵柄を動かす方向に働く。どちらを取るかはユーザー設定に委ねる話で、
「常にオン」も「常にオフ」も正解ではない。

### 1.2 アニメ系SDXLでは artist tag が画風の主変数

Illustrious XL / NoobAI-XL はDanbooruのタグ体系で学習されており、**artist tag（絵師タグ）が
そのまま画風スイッチとして働く**。NoobAI-XL はIllustrious XLベースに
Danbooru/e621の約1270万枚で再学習したもので、artist tagとキャラタグの recall が広い。
絵師タグのプレビュー集（16,000以上）が公開されている。

- 画風を固定したいなら、**全コマに同じ artist tag（複数の組み合わせでもよい）を
  同じ順で入れる**。本アプリの画風タグ（`storyArtStyle`／`promptApplyToPanel()`が付与）と
  同じ枠で扱える
- **既存キャラのタグが使える作品なら、キャラタグが最強の固定手段**（モデルが顔を知っている）。
  オリジナルキャラでは使えないので、そこはLoRAか参照画像に落ちる

**注意**: これはアニメ系ファインチューン固有の話。素のSDXL 1.0や実写系では効かない。
どのチェックポイントを使っているかで前提が変わる。

### 1.3 キャラ表を先頭に、一字一句同じ文字列で

既に実装済み（`LLM_STORY_SHEET_SYSTEM`）。ただし2点、詰め切れていない。

- **語順を固定する。** 同じタグ集合でも順番が違うと結果は変わる。キャラ表は
  文字列としてコピーさせているので順番は保たれるが、LLMがコマごとに
  取捨選択する運用（顔だけのコマでは服を落とす）では、残ったタグの相対位置は保つこと
- **75トークン境界。** SDXLのテキストエンコードは75トークンごとにチャンク分割される。
  プロンプトが長くなるとキャラ記述が別チャンクへ押し出される。**キャラ表は常に先頭**に
  置けば境界に関わらず第1チャンクに入る（境界をまたいだときの効きの落ち方自体は未検証）

### 1.4 seedは「揃える」のではなく「キャラごとに固定する」

seedを揃えると構図まで似る（→`prompt-composition.md` 8.5章）。漫画では逆効果。
使うなら**キャラ設定画を作るときだけ**固定し、本番のコマは自由にする。

---

## 2. 段階1 — 参照画像（学習なし）

「1枚の設定画に寄せる」方向。LoRAより導入が軽く、効きはLoRAに劣る。

### 2.1 IPAdapter — 中心になる仕組み

参照画像をCLIP Visionで埋め込み、UNetのクロスアテンションへ注入する。
ComfyUIでは `ComfyUI_IPAdapter_plus`（cubiq）が事実上の標準。

**SDXLのモデルとCLIP Visionの対応（間違えると動くが効かない）**

| IPAdapterモデル | 必要なCLIP Vision |
|---|---|
| `ip-adapter_sdxl_vit-h.safetensors` | ViT-H-14 |
| `ip-adapter-plus_sdxl_vit-h.safetensors` | ViT-H-14 |
| `ip-adapter-plus-face_sdxl_vit-h.safetensors` | ViT-H-14 |
| `ip-adapter_sdxl.safetensors` | ViT-bigG-14 |

顔を寄せたいなら `plus-face`、絵全体の雰囲気なら `plus`。

**高度な使い方はここから。**

- **`weight_type` を使い分ける。** 単なる強度ではなく、SDXLのどのブロックへ注入するかを
  変える。`style transfer (SDXL)` は transformer index 6 だけに当てる方式で、
  **構図を持ち込まずに絵柄・色・質感だけを移す**。InstantStyleと同じ考え方。
  `composition (SDXL)` はその逆で構図だけ。`style and composition` は両方。
  `style transfer precise` は両者の混線が少なく、参照画像と生成物が大きく違うときに向く
  - → **絵柄と色のブレ対策には、キャラ用とは別に「画風参照」を1本立てるのが筋がよい**。
    画風見本を1枚決めて、全コマに `style transfer (SDXL)` で当てる
- **`start_at` / `end_at` で効かせる区間を切る。** 序盤は構図を決める区間なので、
  ここに強く当てると構図まで参照に寄る。**顔だけ寄せたいなら中盤以降**に当てる
  （具体的な値は使うモデルと参照画像で変わる。ワークフロー側で調整させる）
- **`attn_mask` で領域を限定する。** 顔の位置にマスクを与えれば、背景や服に
  参照が漏れない。本アプリはinpaintのマスクエディタを既に持っているので、
  仕組みの再利用が効く
- **複数の参照画像を束ねる。** `IPAdapterEncoder` + `combine_embeds`（concat / average 等）で
  正面・横顔・表情違いを1つの埋め込みにできる。1枚だけだとその1枚の角度に引っ張られる
- **2本重ねる。** 「顔＝`plus-face` を顔マスクに」＋「画風＝`style transfer (SDXL)` を全体に」。
  役割を分けると互いを潰さない

**IPAdapterは構図も持ち込む。** コマごとに構図を変えたい漫画では、
weight_type と start_at で「見た目だけ」に絞るのが前提になる。ここを雑にやると
全コマが同じ絵になる。ControlNet（openpose / lineart）と併用して
「見た目は参照、構図はコマの指示」に分けるのが定番。

### 2.2 FaceID / InstantID / PuLID — 実写向け。漫画では要検証

いずれもInsightFace（実写の顔認識ライブラリ）の顔埋め込みを使う。
IP-Adapter FaceID → InstantID → PuLID の順に登場した。InstantIDはSDXL専用。

- FaceIDは `insightface` のインストールが必須で、多くのモデルはペアのLoRAも要る
- 参照画像の質にそのまま依存する。顔が検出できないと動かない

**未検証**: InsightFaceは実写の顔で学習された検出器なので、アニメ絵・漫画絵では
検出に失敗しやすいはず — と言われることが多いが、**一次情報で確認できていない**。
本アプリの絵柄で実際に通るかどうかは、導入前に必ず手元のサンプルで試すこと。
通らなければ、この系統は全部使えない。**通ることを前提に設計しない。**

### 2.3 Reference ControlNet（reference_only）

参照画像のアテンション（attn）や統計量（adain）を直接注入する。追加モデル不要。
ComfyUIでは `ComfyUI-Advanced-ControlNet` の `ACN_ReferenceControlNet`。
`style_fidelity`（既定0.5）と `ref_weight`（既定1.0）を持つ。

- 追加ファイルが要らないのが利点。効きはIPAdapterより不安定という評価が多い
- SDXLでの対応可否はノードの版に依存する。**入れる前にノードの実装で確認すること**

### 2.4 前のコマを種にする（i2i / inpaint）— 実装コスト最小

**このアプリが既に持っている機能だけで一番効くのがここ。**

| やり方 | 何に効く | 現状 |
|---|---|---|
| 同じ場所のコマを、前のコマの低denoise i2iで作る | 背景・色・光の統一に強い | I2I自体は実装済み。「前のコマを種にする」導線が無い |
| 顔だけマスクしてinpaint（参照付き） | 顔の作り直しをコマ単位でやり直せる | inpaint実装済み。参照画像の注入が無い |
| 背景を1枚作って使い回す | 同じ場所は完全に同じ絵になる | 未実装 |
| `FaceDetailer` で顔を再生成 | 顔の破綻を潰す。**同じ参照/LoRAを当てれば固定にもなる** | ワークフロー側に既にノードがある |

生成し直しではなく**部分の作り直し**なので、絵柄も色も動かない。
「毎回ブレる」問題に対して、ブレる面積そのものを減らす手。

---

## 3. 段階2 — LoRA（学習あり）

顔を揃える唯一の実用解。ただし作るコストがかかる。

### 3.1 学習データの作り方（ここで9割決まる）

- 枚数は20〜40枚が目安。50枚前後まで増やす流儀もある
- **正面だけで学習すると横顔・斜めで崩れる。** 正面 / 4分の3 / 横顔 / 見上げ / 見下ろし、
  表情も複数入れる。単一表情だと感情を変えたときに顔が壊れる
- **キャプションの付け方で「焼き付く」か「制御できる」かが決まる。**
  タグを書いた要素はトリガーワードから切り離されて制御可能になり、
  書かなかった要素はキャラの一部として焼き付く。
  → **服を着替えさせたいなら服のタグを書く。顔は書かない**

**オリジナルキャラの立ち上げ（ブートストラップ）**

1. 段階0＋段階1（seed固定 + IPAdapter）で設定画を10〜20枚作る
2. 使えるものだけ手で選ぶ（ここを自動化しない。似ていない絵を混ぜると学習が濁る）
3. それでLoRAを学習する

**多視点（キャラ設定画・ターンアラウンド）の作り方**として、
SDXLではOpenPoseのターンアラウンド用テンプレートで構造を揃える方法、
charturn系LoRA（Illustrious/Pony向けが公開されている）を使う方法がある。

### 3.2 適用時の高度な使い方

- **`strength_model` と `strength_clip` を別々に持つ。** キャラLoRAは
  model側を強め／clip側を弱めにするとタグでの制御が残る、という運用が広く使われる
  （出典のブログでは style 0.6/0.6、character 0.9/0.7 といった出発点が挙がっている。
  **数字はモデルとLoRA次第なので、そのまま定数にしない**）
- **重ねると弱め合う。** キャラLoRA＋画風LoRAを同時に載せると互いに干渉する。
  スタック時は各0.65前後まで落とす、という記述が複数ある
- **LoRAブロックウェイト（LBW）で「顔だけ」効かせる。**
  `ComfyUI-Inspire-Pack` の `LoraLoaderBlockWeight` 等でUNetのブロックごとに強度を変えられる。
  **キャラLoRAが持ち込む画風を切り離すのに使う**。絵柄ブレの主因が
  「キャラLoRAが学習素材の絵柄も覚えている」ケースはよくあるので、ここが効く
- **キャラが2人以上写るコマは混ざる。** LoRAを2つ載せると片方が支配する。
  `Attention Couple`（`ComfyUI-ppm`、SDXL対応）や Regional Prompter で
  領域ごとに条件を分ける。領域分けとLoRAの併用は、LoRAが画面全体に効いてしまう問題が残る

### 3.3 LoRA と 参照画像 の役割分担

> LoRAが「誰か」を担い、IPAdapterが「その人が何をしていてどう配置されているか」を担う。

この整理が実務的に正しい。**両方を同じ目的（顔の固定）に使うと喧嘩する。**
LoRAで顔を固定し、IPAdapterは画風・色・構図の側へ回すのが噛み合う。

---

## 4. 段階3 — 後処理で色を揃える

色のブレは、生成し直すより**後処理で直すほうが確実**。

| 手 | ノード |
|---|---|
| 参照画像へヒストグラムを合わせる | `ImageHistogramMatch+`（ComfyUI_essentials） |
| Reinhard / MVGD などの色転送 | `ColorMatch` / `ColorMatchV2`（ComfyUI-KJNodes） |
| 同系統 | `Runtime44ColorMatch`, `Color Match Image`（ComfyUI-Image-Filters） |

- **ページの基準画像を1枚決めて、そのページの全コマをそれに合わせる**のが素直。
  コマ間の色温度・彩度のズレはこれでほぼ消える
- **アップスケール／2パス目で色が動く**ことが多い。1パス目の出力を参照にして
  カラーマッチを最後に挟むと戻せる
- **モノクロ漫画なら色問題はそもそも消える。** 代わりにトーンの濃さ・線の太さ・
  コントラストがブレる。これは「絵柄」側の問題として扱う（artist tag / 画風LoRA / 画風IPAdapter）

---

## 5. その他の手（採用は要検討）

| 手法 | 中身 | 本アプリでの位置づけ |
|---|---|---|
| **StoryDiffusion（Consistent Self-Attention）** | 同一バッチ内の画像同士でセルフアテンションを共有し、学習なしで登場人物を揃える。漫画生成を想定した研究。ComfyUIでは `ComfyUI_StoryDiffusion` | **1バッチ内でしか効かない**。本アプリはコマを個別に生成しキューで直列化しているので、そのままでは乗らない。乗せるならページ単位で一括生成する構造が要る |
| ConsiStory / StorySync / CharaConsist 等 | 同系統の学習不要手法。マスクした被写体だけアテンションを共有する等 | 実装は研究寄り。ComfyUIノードの成熟度を見てから |
| ReActor等の顔スワップ | 生成後に顔を差し替える | InsightFace依存。2.2と同じ懸念 |
| Textual Inversion / Embedding | 軽量だがSDXLでは効きが弱い評価が多い | 優先度低 |

---

## 6. 本アプリに入れるなら、どの順か

**効果 ÷ 実装コスト**で並べると、roadmapの並び（022 / 027）とは順番が変わる。

| 順 | やること | 効く対象 | 実装 |
|---|---|---|---|
| 1 | **画風タグ（artist tag含む）を全コマへ確実に入れる** | 絵柄 | 済み（`promptApplyToPanel()`）。artist tagを扱う欄を足すだけ |
| 2 | **前のコマを種にしたi2i、背景の使い回し** | 背景・色 | I2Iは実装済み。導線の追加 |
| 3 | **ページ単位のカラーマッチ後処理** | 色 | ComfyUIワークフローに1ノード。基準画像の選択UIだけ |
| 4 | **キャラ表にLoRA名・トリガー・強度を持たせる**（roadmap/027） | キャラ | `LoraLoader`はワークフローに既にある |
| 5 | **キャラ表に参照画像を持たせ、IPAdapterへ流す**（roadmap/022と027） | キャラ・絵柄 | 画像アップロードとワークフロー注入が要る |
| 6 | 顔だけinpaint＋参照 | キャラ | inpaint実装済み。マスクの自動生成が要る |

### 実装上の落とし穴（先に潰すこと）

**`comfyuiReplacePlaceholders()`（js/ai/comfyui/util/comfyui-util.js）の
`updateNodesByInputName({image: ...})` は、`image` という入力を持つ全ノードを書き換える。**
参照画像用に `LoadImage` を2つ目として足すと、**i2i用の画像と参照画像が同じファイル名で
上書きされる**。しかも例外は出ないので気付けない。

- 参照画像は `updateValueByTargetValue('%reference_image%', ...)` のような
  **プレースホルダ方式**で入れる。`updateNodesByInputName`は使わない
- 同じ理由で `seed` / `width` / `height` も全ノードに当たっている。
  今は問題が出ていないが、ノードを増やすときは必ず確認する
- LoRAは `updateNodesByType('LoraLoader', {lora_name, strength_model, strength_clip})` で
  型指定＋`_meta.title`指定にできる。入力名一致は使わない

**ワークフローに該当ノードが無い場合はフォールバックしない。**
LoRA指定があるのにワークフローに`LoraLoader`が無いなら、黙って無指定で生成せず
明示的に弾く（`checkWorkflowNodeVsComfyUI()`と同じ扱い）。
「指定したのに効いていない」が一番分かりにくい壊れ方になる。

---

## 7. 確度について

このドキュメントの記述は3種類ある。**混ぜて読まない。**

| 種別 | 該当箇所 |
|---|---|
| **一次情報・仕様** | IPAdapterのモデルとCLIP Visionの対応、weight_typeの意味、FaceIDのinsightface依存、InstantIDがSDXL専用、各カラーマッチノードの存在、Reference ControlNetのパラメータ、NoobAI-XLの素性 |
| **出典はあるが本アプリで未検証の数値** | LoRAの強度の出発点（0.6/0.9/0.65等）、LoRAと参照画像の一貫性の比較値、領域分けの精度値。**そのまま定数にしない。既定値の初期値としてUIに出し、ユーザーが動かせるようにする** |
| **未検証** | InsightFace系がアニメ絵で検出に失敗するか、75トークン境界をまたいだときの効きの落ち方、Reference ControlNetのSDXL対応状況 |

---

## 参照

- ComfyUI_IPAdapter_plus — https://github.com/cubiq/ComfyUI_IPAdapter_plus
- IPAdapter Style & Composition (SDXL) — https://www.runcomfy.com/comfyui-nodes/ComfyUI_IPAdapter_plus/IPAdapterStyleComposition
- Reference ControlNet (ComfyUI-Advanced-ControlNet) — https://www.runcomfy.com/comfyui-nodes/ComfyUI-Advanced-ControlNet/ACN_ReferenceControlNet
- Illustrious / NoobAI-XL Style Explorer（絵師タグ16,000以上） — https://thetacursed.github.io/Illustrious-NoobAI-Style-Explorer/
- NoobAI XL — https://noobaixl.org/
- ColorMatch (KJNodes) — https://www.runcomfy.com/comfyui-nodes/ComfyUI-KJNodes/ColorMatch
- ImageHistogramMatch+ (essentials) — https://comfyai.run/documentation/ImageHistogramMatch+
- ComfyUI-ppm（Attention Couple for SDXL） — https://github.com/pamparamm/ComfyUI-ppm
- ComfyUI_StoryDiffusion — https://github.com/smthemex/ComfyUI_StoryDiffusion
- StoryDiffusion (NeurIPS 2024) — https://papers.nips.cc/paper_files/paper/2024/file/c7138635035501eb71b0adf6ddc319d6-Paper-Conference.pdf
- PuLID vs InstantID vs FaceID — https://myaiforce.com/pulid-vs-instantid-vs-faceid/
- Illustrious LoRA Training Guide — https://offlinecreator.com/guide/illustrious-lora-training-guide
- LoRA Stacking Guide — https://blog.pixai.art/en/lora-stacking-pixai-guide/
- Anime Character Consistency Guide — https://apatero.com/blog/anime-character-consistency-complete-guide-2025
