# 今のアプリとV3の機能の差（細かい単位の棚卸し）

対象: branch v3-server-plan, HEAD 6026d6c。読むだけで、コードと文書は変えていない。
パスの略: `S/` = `v3/server/src/v3server/`、`W/` = `v3/web/`、`R/` = `v3/psd_writer/render_text.js`。

## 前提（全体の結論）

- V3の画面（`W/`）は約1,900行で、「1つのコマの絵を頼む・候補を選ぶ・版を見る」だけの画面。作品・ページ・コマを作る画面、文字・フキダシ・トーン・図形・コマ枠・層・書き出し・設定・設定資料・企画の画面は**ない**。画面から送る操作は `add_panel_layer`・`add_pen_strokes`・`adopt_image`・`set_image_discarded` と、口の `generate`・`stroke-cache`・`erase-pixels`・`cancel` だけ（`W/js/app.js`）。`v3poc/screen/index.html` は試作の見本で、サーバーにつながっていない。
- そのため下の表の「V3の画面」は、ほぼ全部が「なし」。差の中身は主にサーバー側のデータと描画（書き出し）について書く。
- サーバーは描画を書き出し（`S/print_export/page_render.py`）でだけ行う。ペンの線は画面が絵にして上げる（`SetStrokeCache`）前提なので、筆の種類ごとの描き方はサーバーに無い。
- `feature_coverage.py` のテスト（`tests/unit/test_feature_coverage.py:66-87`）は「載せた操作の名前と口が存在するか」しか見ていない。中身が今のアプリと同じか、値が使われているかは見ていない。

## 1. 機能ごとの表

### 1.1 コマ（Template / Page Manager / Shape）

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| コマの型の一覧（縦41・横28、`js/svg/manga-panels-image-*.js`） | 一部 `S/operations/panel_frame_operations.py:350,376`（`save_panel_template`・`apply_panel_template`） | なし | 作品ごとに保存した型を当てるだけ。今のアプリの型69個を入れた組み込みの一覧が無い。最初の1つを作る手段が型からは無い | 必須 |
| ページを足す（縦・横・自由な大きさ customPanelSizeX/Y） | あり `S/operations/work_tree_operations.py:118`、寸法は `set_work_settings.page_spec`（`S/operations/work_setting_operations.py:43`） | なし | 作品1つにつき寸法1つ。ページごとに縦・横を変えられない | 重要 |
| ページの並べ替え（下のバーでドラッグ、`js/ui/bottom-bar.js` reorderImages・swapImages） | なし | なし | `AddPage.number` はあるが、番号を変える操作が無い（`UpdatePage` は `layout` だけ、`work_tree_operations.py:251-257`） | 必須 |
| ページの複製・下のバーのサムネイル・前後のページへ移る | なし | 一部（ページを選ぶだけ） | 複製の操作が無い | 後で |
| ナイフ（向き・斜め・コマの間の幅 knifePanelSpaceSize） | あり `panel_frame_operations.py:169`（through_mm・direction・angle_deg・gap_mm） | なし | 中身は揃っている。画面が無い | 必須 |
| コマの頂点を動かす（Edit モード） | あり `update_panel.frame`（`work_tree_operations.py:201`） | なし | 画面が無い | 必須 |
| コマ枠の線の色・太さ・塗り | あり `FrameStyle`（`S/name_structure/item_styles.py:183`）、描画 `page_render.py:376-380,451-456` | なし | — | 必須 |
| コマ枠の不透明度（panelOpacity） | なし | なし | `FrameStyle` に不透明度が無い | 後で |
| 全部のコマに当てる（panelAllChange） | 一部 `WorkPreferences.frame_style`（`work_setting_operations.py:28`） | なし | 作品の既定として持つだけ。既に枠を持つコマには効かない | 重要 |
| 図形のコマ（四角・縦長・横長・三角・五角・六角・星・ハート） | あり `add_shape_panel`（`panel_frame_operations.py:319`、形は `S/panel_layout/panel_frame_editing.py:184`） | なし | 縦長・横長は box_mm で出せる | 重要 |
| ばらばらに割る（縦・横の数・傾き tiltRandom・変化の割合 cutChangeRate） | 一部 `random_split_panel`（`panel_frame_operations.py:266`） | なし | 傾きと変化の割合の引数が無い | 重要 |
| 複数ページを自動で作る（multiPageGenerate、ページ数・向き） | なし | なし | 1操作で複数ページを割る手段が無い | 後で |
| コマの外の余白（marginFromPanel） | あり `PageSpec` の基本枠（`S/name_structure/reading_direction.py:10-23`） | なし | — | 重要 |

### 1.2 フキダシ

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| フキダシの型48個（`js/svg/speechbubble.js`） | 一部 `BalloonShape.preset` は名前だけ（`item_styles.py:154-177`） | なし | 描くのは `outline_mm` の**多角形1つ**だけ（`page_render.py:486-494`）。型の一覧（SVG）がサーバーに無い。考えのフキダシ（丸が並ぶ形）・二重線・穴のある形は1つの多角形で表せない | 必須 |
| フキダシの線の色・太さ・塗り | あり `BalloonShape.line_width_mm/line_color/fill_color` | なし | — | 必須 |
| フキダシの不透明度（speechBubbleOpacity・sbFillOpacity） | なし | なし | 塗りの不透明度が無い（文字全体の `opacity` だけ） | 後で |
| 線の種類 sb_a〜sb_g（点線・破線・一点鎖線など、`speech-bubble-freehand.js:55-74`） | なし | なし | 線の種類の項目が無い。描画も実線だけ | 重要 |
| 自分で描くフキダシ（点・フリーハンド・点を動かす・消す、なめらかさ・点の間隔・角の丸み） | 一部 `kind="custom"` + `outline_mm` | なし | 外形の多角形は持てる。なめらかさ・角の丸みは画面で多角形に直す前提で、項目は無い | 重要 |
| フキダシの中の文字（なし・横・縦） | あり `text_items` に `balloon_shape` を持つ | なし | — | 必須 |
| しっぽの先（tail） | 一部 `tail_target_mm`（`S/canonical_tables/text_and_layer_tables.py:36`） | なし | 保存するだけで描画に使っていない。しっぽは外形に含める前提 | 後で |

### 1.3 文字（Text / Image Text）

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 横書き・縦書きの文字を足す | あり `add_text_item`（`S/operations/text_and_layer_operations.py:94`） | なし | — | 必須 |
| 縦書きの細部（ー「」（）などの括弧・長音を回す、。、の位置を直す、`js/sidebar/text/vertical-textbox.js:3-6,305-341`） | なし | なし | 書き出しの描画 `R:36-50,75-90` は全部の字を立てたまま同じ間隔で置くだけ。括弧・長音・句読点の向きと位置を直さない。日本語の縦書きの原稿として崩れる | 必須 |
| 書体を選ぶ | あり `font_family`・`fonts_by_kind`（`work_setting_operations.py:26`） | なし | 書体はサーバーの `V3_FONT_DIR` のファイル名だけ（`S/print_export/text_render.py:23-32`） | 必須 |
| 書体を足す（利用者のフォントを上げる、`js/db/user-font-repository.js`・`js/ui/font/user-font-manager.js`、作品に書体を入れる `js/core/font/project-font.js`） | なし | なし | 書体のファイルを上げる口が無い。管理者がサーバーのフォルダに置くしかない | 重要 |
| 文字の大きさ・色 | あり `font_size_pt`・`decoration.fill` | なし | — | 必須 |
| 縁取り（色・太さ）・背景色 | あり `decoration.edge`・`decoration.band`（`item_styles.py:86-120`）、描画 `R:71,122` | なし | — | 必須 |
| 太字（bold-toggle-btn） | なし | なし | 項目が無い | 重要 |
| 左・中・右寄せ（alignText） | なし | なし | 項目が無い。描画は常に箱の真ん中（`page_render.py:500-502`） | 重要 |
| 行の間（lineHeight） | なし | なし | 全部の文字で固定 `LINE_GAP_RATIO = 0.2`（`page_render.py:48`） | 重要 |
| 字の間（charSpacing・letterSpacing） | あり `decoration.spacing_ratio`（`item_styles.py:132`） | なし | — | 重要 |
| 文字の飾りの型14個（plain・standard・inverse・variety・pop・cute・horror・neon・cyber・comic・glitch・japanese・cinema、`js/sidebar/text/text-decor-presets.js`） | 一部 `decoration.edge/glow/shadow/ghosts/band` に展開して持つ（`item_styles.py:122-132`） | なし | 値の展開は画面の仕事。型の一覧（値の表）がサーバーにも画面にも無い | 重要 |
| ルビ | あり `Ruby`（`item_styles.py:135`）、描画 `R:127-139` | なし | 今のアプリより多い | — |
| 画像の文字（Image Text：効果の型22個 void・quantum・destroy・…・metal・water と、broken・cloud・layered・mesh・scratch・shadow・thrill・wild・zebra の9つの効果、影2つ・塗りの不透明度・縦横・寄せ、`js/sidebar/text/text-2-manager.js`・`js/sidebar/text/custom/*`） | なし | なし | 効果の描き方が無い。`feature_coverage.py` の行にも無い（10.4 の表から抜けている） | 重要 |

### 1.4 ペン・消しゴム

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 鉛筆（太さ1-150・不透明度・影の太さ・影のずれ X/Y、`js/sidebar/pen/pen-tools.js`） | 一部 `brush="pencil"`・`width_mm`・`opacity`（`S/hand_tools/vector_strokes.py:21,37-43`） | 一部（黒・0.3/0.6/1.2mm の3段だけ、`W/index.html:59-66`） | 影の3つの値は `brush_options`（中身を確かめない辞書）に入れるしかない | 必須 |
| 二重の縁取りのペン（太さ・縁1/縁2の太さと不透明度） | 一部 `double_outline` + `brush_options` | なし | 縁の値の形が決まっていない | 重要 |
| 丸・クレヨン・インク・マーカー・モザイク（丸の大きさ・モザイクの大きさ）・縦線・横線 | 一部 名前はある（`vector_strokes.py:21-26`） | なし | 描くのは画面の仕事で、V3の画面は鉛筆しか描けない（`W/js/app.js:615-616` は他の筆があると止める） | 重要 |
| 四角のペン（Square）・テクスチャのペン（Texture） | なし | なし | 筆の名前の一覧に無い（`MODE_PEN_SQUARE`・`MODE_PEN_TEXTURE`、`js/ui/util/mode-change.js`） | 重要 |
| 消しゴム（筆として） | あり `erase_pen_strokes`（whole・to_crossings・touched）・`erase_pixels` | 一部（画素の消しゴムだけ） | — | 必須 |

### 1.5 トーン・集中線・スピード線

今のアプリのトーンは、描いた結果を**ラスター画像**として置く（`js/sidebar/tone/*.js` は全部 `toDataURL` → `fabric.Image`）。V3 は値（`ToneSpec`）で持ち、書き出しで描く。

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 網点（点の大きさ・点の間隔・色・グラデの始まりと終わり） | 一部 `kind="dots"`（濃さ・線数・角度・色、`item_styles.py:214-232`）、描画 `page_render.py:230-233` | なし | 網点の濃さのグラデ（場所で濃さが変わる）が無い。濃さは1つ | 必須 |
| ノイズ（砂目）トーン（最小・最大のノイズ、グラデの始まり・終わりの X/Y） | 一部 `kind="sand"`（粒の大きさ・濃さ・種） | なし | 濃さのグラデが無い | 重要 |
| 雪（奥と手前の大きさ・ぼかし・色2つ・角度・密度） | 一部 `kind="snow"` | なし | 粒の大きさ1つ・色1つだけ。奥と手前の2層・ぼかし・角度が無い。描画は `sand` と同じ丸を撒くだけ（`page_render.py:243-248`） | 重要 |
| 集中線（中心 X/Y・最小と最大の半径・線の太さの広がり・本数・色） | 一部 `kind="focus_lines"`（中心・内側の比・本数・濃さ・種・色） | なし | 外側の半径・線の太さの広がりが無い | 重要 |
| スピード線（密度・グラデの始まりと終わり・色） | 一部 `kind="speed_lines"`（本数・角度・濃さ） | なし | 線の端のグラデ（薄くなる）が無い | 重要 |
| グラデのトーン | あり `kind="gradient"` | なし | — | 重要 |
| トーンの型（tonePresetCurrent） | なし | なし | 型の一覧が無い | 後で |
| 貼る範囲（コマ・多角形・塗った所） | あり `ToneTarget*`（`item_styles.py:195-211`） | なし | 今のアプリより多い | — |

### 1.6 効果・仕上げ（Manga Effect / Controls）

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 白黒化5種（明るめ・暗め・網点なし・単純・黒＋淡い色、`js/sidebar/effect/c2bw_tone.js`） | 一部 `Monochrome.threshold`（`item_styles.py:27-31`） | なし | 灰色か2値の2通りだけ。網点に直す白黒化・淡い色を残す白黒化が無い | 重要 |
| 暗い所を強める（EnhanceDark） | なし | なし | — | 後で |
| 明るさ | あり `Brightness` | なし | — | 重要 |
| ぼかし | あり `Blur` | なし | — | 重要 |
| 光る縁（Glow：太さ・色） | なし | なし | 絵に対する光る縁が無い（文字の glow とは別） | 後で |
| GLFX のフィルター（明るさ・コントラスト、色相・彩度、セピア、ぼかし系、ドット、カラーハーフトーン、エッジ、インク、六角のモザイク、渦、ふくらみ、ティルトシフト など約14種、`js/ui/control/glfx-control.js`） | なし | なし | — | 後で |
| 重ね方 25種以上（color-burn・linear-burn・soft-light・hard-light・difference・exclusion・hue・saturation・color・luminosity ほか）と色・グラデの重ねる層（`js/layer/blend/blend.js`） | 一部 6種だけ（`item_styles.py:45`） | なし | 19種が無い。色やグラデを重ねる層が無い | 重要 |
| 範囲（選んだ物・ページ・全ページ）にまとめて当てる・まとめて戻す | 一部 `reset_adjustments`（`S/operations/page_item_operations.py`） | なし | ページ・全ページにまとめて当てる操作が無い（1件ずつ） | 後で |
| 位置・角度・拡大・傾き X/Y・反転・不透明度 | あり `transform`・`opacity`（各表） | なし | — | 必須 |
| 切り抜き（CROP モード） | あり `image_placement.crop_px` | なし | — | 重要 |
| 情報表示（FPS・座標） | 画面だけ | なし | — | 後で |

### 1.7 絵記号（Shape パネル）

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| Google のアイコンを探して置く（塗り・線・角丸・2色の4つの形） | 一部 `ShapeSpec.kind="symbol"`（`item_styles.py:267-289`） | なし | 外形は `points_mm` の**多角形1つ**。アイコンの曲線と穴（ほとんどのアイコンにある）を表せない。アイコンの一覧・探す口もサーバーに無い | 重要 |
| 線の色・塗りの色・線の太さ・塗りの不透明度 | あり `ShapeStroke`・`ShapeFill` | なし | — | 重要 |
| 影（色・ぼかし・ずれ X/Y） | あり `ShapeShadow` | なし | — | 後で |

### 1.8 層・画像

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 画像を読み込んでコマに置く・ドロップ | あり `POST /works/{id}/images`・`/panels/{id}/image`（`S/http_routes/image_file_routes.py:65,82`） | なし | — | 必須 |
| コマの外に画像を置く（ページ全体の背景など） | なし | なし | 層は必ずコマに属し、`human_hand` 以外はコマで切られる（`page_render.py:395-397`）。ページの層は `tone`・`shape` だけ（`page_item_operations.py:27`） | 重要 |
| 層の一覧・見せる・順番・動かさない（moveLock） | あり `update_panel_layer`・`set_fixed` | なし | — | 必須 |
| 層の名前を変える（beginLayerNameEdit） | なし | なし | 層に名前の項目が無い | 後で |
| 物を消す・全部消す | あり `set_removed`（ごみ箱） | なし | — | 必須 |
| 取り消す・やり直す | あり `POST .../events/{id}/undo` | あり | — | 必須 |
| コピー・貼り付け（物の複製） | なし | なし | 複製の操作が無い | 重要 |
| 矢印キーで動かす | あり（`transform`） | なし | — | 後で |
| 物の右クリックのメニュー（`js/ui/canvas-object-menu.js`） | 画面だけ | なし | — | 後で |

### 1.9 AI（つなぎ先・役・手順）

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 手元の ComfyUI | あり adapter `comfyui`（`S/service_senders/comfyui_sender.py`） | 一部（つなぎ先を選ぶだけ） | つなぎ先を登録する画面が無い（`POST /services` は管理者の口） | 必須 |
| RunPod の ComfyUI（認証付き HTTPS） | 一部 同じ adapter に `endpoint` を入れる | なし | 認証の値（ヘッダー）を送る項目が無い。URL に入れる形しか取れない（未検証） | 重要 |
| 手元の SD WebUI（T2I・I2I・背景を消す・ADetailer・プロンプト／シードを画像から取る） | なし | なし | adapter が無い（`S/service_senders/sender_by_adapter_name.py`：litellm・comfyui・detector の3つ） | 重要 |
| fal.ai（T2I・I2I・拡大・背景を消す、モデルの一覧を読み直す、同時に送る数） | なし | なし | adapter が無い | 重要 |
| Google の画像（Nano Banana 4モデル、1K/2K/4K、同時に送る数） | なし | なし | 画像を返す API の adapter が無い。litellm の送り手は文章だけ（`S/service_senders/litellm_sender.py:16-25`） | 必須 |
| Grok・Ollama（文章と画像を読む LLM） | 一部 LiteLLM を通す（`litellm_sender.py`） | なし | LiteLLM の設定はサーバーの外。モデルの一覧を読み直す口が無い | 重要 |
| 役の割り当て（T2I・I2I・Inpaint・拡大・背景を消す・角度・Text2Prompt・Image2Prompt を、つなぎ先ごとに、`js/ai/role/ai-roles.js`） | あり `PUT /routes/{process}`（`S/http_routes/service_routes.py:143`） | なし | — | 必須 |
| つなぎの確かめ（ハートビート） | 一部 `services.state` を手で入れる（`service_routes.py:46-53`） | なし | 自動で確かめる仕組みが無い | 後で |
| 文から作る（T2I） | あり `text_to_image`（`S/generation_queue/image_process_registry.py:306`） | あり | — | 必須 |
| 絵から作り直す（I2I） | あり `image_to_image`・`variation` | あり | — | 必須 |
| 囲んで直す（Inpaint：筆・消しゴム・全部塗る・消す・大きさ・指示・入れないもの・変える強さ） | あり `inpaint` | あり（投げ縄・多角形・四角も） | 今のアプリより多い | 必須 |
| 角度を変える（3Dのカメラの部品で方位・高さ・距離を決め、指示文を作る、`js/ai/angle/*`） | 一部 処理の名前 `change_angle` だけ（`S/generation_queue/known_processes.py:22`） | なし | 組み込みの手順が無い。管理者が ComfyUI の手順（JSON）を丸ごと登録し、ノード番号で値を差し替える形（`comfyui_sender.py:281-285`）。カメラの値から指示文を作る所が無い | 重要 |
| 背景を消す（Rembg） | 一部 処理の名前 `remove_background` だけ | なし | 同上。組み込みの手順が無い | 重要 |
| 拡大（Upscaler） | 一部 `S/comfy_graphs/upscale_graph.py` はあるが**どこからも呼ばれない**（テストだけ） | なし | 依頼として出す処理が無い | 重要 |
| Hires fix（拡大の方法・手数・変える強さ・倍率） | なし | なし | — | 後で |
| ADetailer（モデル・指示・入れないもの） | なし | なし | — | 後で |
| モデル・CLIP・VAE・SD/Flux・Simple/Diffusion/NF4 の切り替え | 一部 `comfy_graph_settings` の checkpoint か separate（UNET・CLIP・VAE、`S/comfy_graphs/model_loader_nodes.py:30-43`） | なし | NF4 が無い。モデルの一覧を ComfyUI から読む口が無い | 重要 |
| 手数・サンプラー・CFG・幅・高さ・シード | あり（処理の引数と `SamplerSettings`） | あり | — | 必須 |
| 手順（ワークフロー）の編集（`js/ai/comfyui/v2/comfyui-workflow-editor*.js`、型ごとの既定 T2I・I2I・inpaint・rembg・upscale・angle、object_info で選べる値を読む） | 一部 `comfy_workflow` を丸ごと保存（`service_routes.py:57-65`）、選べる値を確かめる `comfy_check_choices` | なし | 編集の画面が無い。既定の手順の一覧が無い | 重要 |
| コマのプロンプトをコマに持つ（コマごとの指示・入れないもの・シード） | 一部 依頼（job）の引数に残る | 一部（毎回入れる） | コマに指示を保存する項目が無い。前の指示は版の履歴から読むしかない | 重要 |
| ページの全部のコマを一度に作る（AllRun）・コマごとの枚数（onePanelGenerateNumber） | 一部 1コマずつ `generate`（枚数あり） | 一部（1コマ・1〜6枚） | ページ・全ページをまとめて頼む口が無い | 重要 |
| タグを推定する（DeepDanbooru・CLIP） | なし | なし | `read_prompt`（`known_processes.py:23`）は LLM に読ませる形だけ。DeepDanbooru・CLIP の送り手が無い | 重要 |
| 画像から指示を読む（LLM） | あり `POST .../images/{id}/read-prompt`（`S/http_routes/ai_job_routes.py:41`） | なし | — | 重要 |
| 画像の生成情報からプロンプト・シードを取る（PutPrompt・PutSeed） | なし | なし | — | 後で |
| 一時に置く（Temp） | なし | なし | — | 後で |
| 生成の順番待ち・止める | あり `jobs`・`cancel`・`resume`・`retry`（`S/http_routes/job_routes.py`） | 一部（止めるだけ） | — | 必須 |

### 1.10 プロンプト・物語（Prompt Manager / Auto Generate）

`feature_coverage.py` にも §10.4 の表にも、この節の機能の行が**無い**。

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 物語から各コマのプロンプトを作る（範囲：選んだ物・ページ・全ページ、人物・場所、絵柄、作風 一般・青年・少年・少女・成人、作風の指示、枠の入れないもの、コマの形から大きさ、右から左、`js/ai/prompt/llm/llm-story-*.js`） | なし | なし | V3 のネームの LLM（`S/llm_questions/name_draft_question.py`）はネームを作る物で、コマの絵の指示を作らない | 重要 |
| 物語を広げる（storyExpand）・人物を抜き出す（storySheetButton） | 一部 人物を抜き出す `POST .../plan/extract-characters`（`ai_job_routes.py:59`） | なし | 広げる処理が無い | 後で |
| LLM の絵コンテ（`js/ai/prompt/llm/llm-storyboard-*.js`） | 一部 ネーム案・コマ割り案（`S/http_routes/name_proposal_routes.py:86`） | なし | — | 重要 |
| 文からプロンプトを作る（Text2Prompt、`llm-prompt-service.js`） | なし | なし | — | 後で |
| シナリオの型からプロンプトを入れる（ScenarioPromptSelecter・prompt-map） | なし | なし | — | 後で |
| プロンプトの補助（画像付きのタグの一覧、`js/ui/imagePromptHelper/*`） | なし | なし | — | 後で |
| プロンプトを探して置き換える（openPromptChangeFloatingWindow） | なし | なし | `replace_text` の対象は文字・設定資料・企画・赤入れだけ（`S/operations/text_search_and_replace.py:21,73`）。プロンプトはコマに保存されないので対象にできない | 後で |
| プロンプトの入力のタグ表示（Tagify） | 画面だけ | なし | — | 後で |

### 1.11 参照の絵（Reference Sheets）

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 人物・背景・小物・その他のタブ、探す、表示の切り替え | あり `material_entries`（`S/canonical_tables/material_and_setting_tables.py:33-54`） | なし | — | 重要 |
| 参照の絵を生成の依頼に付ける（スロット、Google の画像に複数の絵を渡す、「指示に説明を入れる」） | 一部 `input_images` の `purpose="reference"`（`S/generation_queue/input_image_preparation.py:4`） | なし | 設定資料の `generation.reference_image_ids` は**生成のどこからも読まれない**（下の2章）。参照の絵を受ける組み込みの手順も無い | 必須 |
| 参照の絵を作る（名前・比率・対象・指示） | なし | なし | — | 重要 |
| 選んだ層から足す・ドロップで足す | 一部 `add_material_entry.image_ids` | なし | — | 重要 |
| まとめて書き出す・読み込む（exportBase・importBase） | なし | なし | — | 後で |
| キャンバスに参照の印を出す | 画面だけ | なし | — | 後で |

### 1.12 保存・読み込み

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| プロジェクトの保存（zip の中にページごとの `.lz4`＋`.json`、`js/core/compression/project-compression.js`） | 一部 操作のたびにサーバーに残る | なし | 作品を1つのファイルに書き出す口が無い（§18 で決めたのに未実装。`S/http_routes/export_routes.py:62` の形式は png・pdf・psd だけ） | 必須 |
| プロジェクトの読み込み（zip・lz4、複数） | なし | なし | 作品のファイルを読み込む口が無い | 必須 |
| 自動保存（IndexedDB・間隔・最後に保存した時刻・復元のダイアログ、`js/core/auto-save.js`） | 一部 操作のたびに保存されるので要らない | — | `autosave`・`autosave_interval_seconds` は保存するだけで使われていない（下の2章） | 後で |
| 保存していない変更の警告（`js/core/unsaved-guard.js`） | 不要（サーバーに保存） | — | — | — |
| 毎日の控え | なし | なし | §18 で決めたのに無い（`backup` の実装が無い） | 重要 |
| ごみ箱 | あり `set_removed` | なし | ごみ箱を空にする操作は無い | 後で |

### 1.13 書き出し

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 画像の書き出し（ページを切り抜いて PNG、DPI・ページの mm・出力の画素） | あり `POST .../exports` png・dpi・paper_mm（`export_routes.py:55-60`） | なし | — | 必須 |
| PDF・PSD | あり（今のアプリより多い） | なし | — | — |
| クリップボードにコピー（clipCopy） | 画面だけ | なし | — | 重要 |
| SVG の書き出し（svgDownload） | なし | なし | — | 後で |
| 層ごと・切り抜いた層の書き出し（putImageDownloadButton・putCropImageDownloadButton） | 一部 `GET .../images/{id}/file` | なし | — | 後で |
| 書き出しの描き方の差 | — | — | V3 は値から描き直す。今のアプリの画面で見えていた見た目（トーンの画像・画像の文字・GLFX・重ね方）は V3 の書き出しで出ない | 必須 |

### 1.14 設定・表示・その他

| 今のアプリの機能 | V3のサーバー | V3の画面 | 差の中身 | 重さ |
|---|---|---|---|---|
| 言語 8つ（英・日・韓・中・仏・露・西・独、i18next） | 一部 `user_settings.language`（`material_and_setting_tables.py:62`） | なし | V3 の画面は日本語の固定。言語の値は保存するだけ | 重要 |
| 設定の保存・初期化・自動で保存（localStorage） | 一部 `GET/PUT /me/settings`（`S/http_routes/settings_and_search_routes.py:33,43`） | なし | `other` は中身を決めていない辞書 | 後で |
| パネルの表示の切り替え（層・AI・プロンプト）・下のバー | 画面だけ | なし | — | 後で |
| 背景色・マス目（表示・大きさ・吸い付く）・参照の印 | 画面だけ | なし | — | 重要 |
| 拡大・縮小・合わせる | 画面だけ | あり | — | 必須 |
| ショートカット（元に戻す・やり直す・コピー・貼り付け・層を消す・選択を外す・画像の書き出し・層の上下・矢印で動かす（Shift で速く）・新しいページ・前後のページ・プロジェクトの保存と読み込み・設定の保存・プロンプトの表示・下のバー・コントロール・マス目・層パネルの切り替え・拡大縮小・ショートカットの一覧、`js/shortcut.js`） | — | 一部（V・M・O・P・E・Ctrl+Z・Ctrl+Shift+Z だけ） | 20個以上が無い | 重要 |
| チュートリアル・ヘルプ・リンク・共有・寄付・PWA のインストール | 画面だけ | なし | — | 後で |
| モード管理（選ぶ・フリーハンド・点・ナイフ・切り抜き・コマの編集・トーン5種・ペン12種、`js/ui/util/mode-manager.js`） | 画面だけ | 一部（5つの道具） | — | 必須 |
| 統計の一覧（ダッシュボード） | 入れない | — | 決めごとどおり対象外。ただし API の費用の集計は `cost_per_call`・`monthly_budget`（`service_routes.py:41,59`）で一部ある | 対象外 |

## 2. `feature_coverage.py` が受けていると書いているが、本当には受けていないもの

| `feature_coverage.py` の行 | 書いてある操作・口 | 実際 |
|---|---|---|
| `コマの型・…`（`feature_coverage.py:43-45`） | `save_panel_template`・`apply_panel_template` | 組み込みの型（今のアプリの69個）が無い。保存した物を当てるだけ。`random_split_panel` は傾き・変化の割合が無い |
| `フキダシの型・自分で描くフキダシ`（:47） | `add_text_item`・`update_text_item` | 型は名前（`BalloonShape.preset`）を保存するだけで、描画は `outline_mm` の多角形1つ。型の一覧・線の種類（点線など）・塗りの不透明度・しっぽの描画が無い。`tail_target_mm` は保存だけ |
| `文字・文字の飾り・書体を足す`（:48） | `add_text_item`・`update_text_item`・`set_work_settings` | 「書体を足す」は `set_work_settings.fonts_by_kind` で既にある書体の名前を選ぶだけ。書体のファイルを上げる口が無い。縦書きの括弧・長音・句読点の向きを直さない（`R:45`）。太字・寄せ・行の間が無い。飾りの型の名前 `decoration.preset` は保存だけで描画に使わない（`item_styles.py:124`） |
| `ペンの種類・消しゴム`（:49） | `add_pen_strokes` ほか | 筆の名前を保存するだけ。各筆の値は `brush_options`（中身を確かめない辞書、`vector_strokes.py:43`）。描くのは画面の仕事で、V3 の画面は鉛筆しか描けない。Square・Texture の筆は名前の一覧にも無い |
| `トーン・集中線・スピード線`（:50） | `add_page_item`・`update_page_item` | 網点・砂目・スピード線の濃さのグラデ、雪の2層・ぼかし・角度、集中線の外側の半径・太さの広がり、トーンの型が無い |
| `絵記号`（:51） | `add_page_item`・`update_page_item` | アイコンを多角形1つで持つので、曲線と穴を表せない。アイコンを探す口が無い |
| `白黒化・明るさ・ぼかし・重ね方・まとめて戻す`（:54-55） | `update_*`・`reset_adjustments` | 白黒化は灰色か2値だけ（5種のうち網点・淡い色が無い）。重ね方は6種（今のアプリは25種以上）。Glow・GLFX・EnhanceDark は行の名前にも入っていない |
| `絵を作る・…・角度を変える・拡大・背景を抜く・絵から指示を読む`（:57-58） | `POST /works/{id}/jobs`・`read-prompt` | 角度を変える・背景を消すは処理の名前（`known_processes.py:22-23`）だけで、組み込みの手順が無い。管理者が ComfyUI の手順の JSON を登録しないと動かない。拡大は `upscale_graph.py` がどこからも呼ばれず、依頼の処理が無い。カメラの部品から指示文を作る所が無い |
| `手順・モデル・シード・参照`（:59-60） | `add_material_entry`・`update_material_entry`・`PUT .../processes/{process}`・`POST .../jobs` | 設定資料の `generation`（prompt・negative_prompt・loras・reference_image_ids・seed、`S/operations/material_and_plan_operations.py:42-51`）は**保存するだけで生成のどこからも読まれない**。`S/comfy_graphs/character_prompt_words.py` もどこからも呼ばれない。手順の編集の画面・既定の手順の一覧が無い |
| `ページを足す・画像から足す・取り込む`（:65-67） | `add_page`・`POST images`・`name-imports` | 「取り込む」は MangaImport（ネームの取り込み）と PSD の読み戻しで、今のアプリのプロジェクトは取り込めない。ページの並べ替え・複製が無い |
| `画像の書き出し・コピー・解像度・紙の大きさ`（:68-71） | `exports` の口 | 「コピー」（クリップボード）は画面の仕事で、画面が無い。作品を丸ごと書き出す形式（§18）が無い |
| `言語・自動保存・設定`（:73） | `set_work_settings`・`/me/settings` | `user_settings.language`・`autosave`・`autosave_interval_seconds` と `WorkPreferences.language`・`autosave_interval_seconds`（`work_setting_operations.py:24,30`）は保存するだけで、読む所が無い |
| `ナイフ`・`コマ枠` ほか 10.1 の道具 | 各操作 | 操作はあるが、画面はペン・消しゴム・囲んで頼むの3つ（＋見る）だけ。文字・コマ枠・ナイフ・フキダシ・トーン・図形・読む順・表示するものの画面が無い |

そもそも行が無い（`feature_coverage.py` と §10.4 の表のどちらにも入っていない）もの:
- 画像の文字（Image Text の効果の型22個と効果9つ）
- プロンプトの管理（物語から各コマのプロンプト、広げる、Text2Prompt、シナリオの型、プロンプトの補助、プロンプトの探す・置き換え、ページ・全ページの一括生成、複数ページの自動作成）
- タグの推定（DeepDanbooru・CLIP）、ADetailer、Hires fix、PutPrompt・PutSeed
- つなぎ先の種類（SD WebUI・fal.ai・Google の画像・RunPod の認証）
- GLFX・Glow・EnhanceDark・重ね方の層
- プロジェクトの保存・読み込み（ファイル）、ページの並べ替え・複製、物のコピー・貼り付け、層の名前、コマの外の画像
- ショートカットの一覧

## 3. 今のアプリで作ったプロジェクトを V3 に移す道

**無い。**

- V3 のサーバーにも画面にも、今のアプリのプロジェクト（zip の中のページごとの `.lz4`＋`.json`。中身は fabric.js のキャンバスの JSON）を読む所が無い。`v3/` の下に `lz4`・`zip`・fabric の JSON を読むコードは無い（`fabric` という語はペンの説明の注釈にだけ出る）。
- V3 にある取り込みは次の2つで、どちらも今のアプリのプロジェクトには使えない。
  - MangaImport（`POST .../name-imports`、`S/name_import/manga_import_reader.py`）：既存の漫画のコマとセリフを解析した結果を受ける形
  - PSD の読み戻し（`S/operations/psd_import_operations.py`）：V3 が書き出した PSD の層を合わせ直す形
- 画像を1枚ずつ上げる（`POST /works/{id}/images`）ことはできるが、コマ・文字・フキダシ・ペンの線は移らない。
- 移す道を作るときに、表しきれず落ちる物（上の差から）:
  - トーン・集中線・スピード線：今のアプリでは画像なので、`ToneSpec` には戻せない。画像として移すと、コマの外にある物を置く場所が無い（層はコマに属する）
  - フキダシ：SVG の複数の path・穴・点線を、`outline_mm` の多角形1つには移せない
  - 文字：太字・寄せ・行の間・画像の文字の効果は移せない。縦書きは書き出しの見た目が変わる
  - ペン：fabric の Path（画素の座標）を mm の点の列に直す必要がある。四角・テクスチャの筆は名前が無い
  - 絵記号：アイコンの SVG の path を多角形1つには移せない
  - 効果：GLFX・Glow・25種の重ね方・白黒化の網点は移せない（画像として焼き込むしかない）
  - AI の設定（コマごとのプロンプト・シード・モデル）：コマに持つ項目が無いので移せない
  - 参照の絵（IndexedDB の `reference-repository`）・利用者の書体（IndexedDB の `user-font-repository`）：受ける口が無い
- ページの寸法も、今のアプリはページごとに縦・横を持てるが、V3 は作品に1つ。
