# V3 人とAIの受け渡し

作成 2026-10-08。V3サーバー（`v3/server/`）で、コマ割り・ネームの中身・文字・絵を、人が作っても、AIが作っても、外から持ち込んでも同じ流れに乗せ、互いに引き継げるようにした内容。サーバーの口と操作までで、画面は作っていない。

利用者の指示（2026-10-08）：「コマ割りなどは人間が行うケースも検討してください。画像は外部から持ち込まれることも検討してください。AIが作る・人間が作る、これが相互にできることが重要です。」
追加の指示（同日）：文字（吹き出し・ナレーション・描き文字）と絵（差し替え・切り抜きと置き場・層・人の手の範囲）を人が直接直せること。人が直した項目はAIが上書きせず、AIの案が当たったら黙って捨てずに判断待ちにすること。人がどれも取り消せ、人の直しにもAIの直しと同じ確かめがかかること。

前提：正本を変えるのは操作の窓口（`operations/operation_submit_and_undo.py`）だけ。出来事・ロック・権限・取り消しはそこで共通（`llm_doc/V3サーバーの土台.md`）。この文書はその上に足したものだけを書く。

---

## 1. 違いを吸収する所（1か所ずつ）

出どころ（人・AI・取り込み）で分ける処理を各所に書かず、次の所に集めた。

| 何を分けるか | 1か所 | 中身 |
|---|---|---|
| 人が直せる項目と、その項目の作業 | `operations/ai_involvement.py` の `HUMAN_EDITABLE_FIELDS` | ページ・コマ・文字・層の項目ごとに、どの作業（コマ割り・ネームの中身・作画・仕上げ）に入るか。人の手の印を付ける項目も、AIの関与で止める項目も、ここから読む |
| 人の手の印・確定印・判断待ち | `operations/human_hand_guard.py` | 項目を変える操作は全部 `change_with_human_hand` を通る（行を抜く・戻すは `remove_or_hold`）。人が変えた項目に印を付け、AIが変えるときは作業のAIの関与を確かめる。AIの変更（直接の操作でも、案の採用でも）が印の項目に当たったら、その項目だけ判断待ちに置き、印の無い項目は当てる。置いた判断待ちは窓口（`operation_submit_and_undo.submit`）が出来事に残して返し、取り消すと下げる |
| AIが出せる操作か | 操作の窓口 `submit` と `OpBase.ai_may_submit` | AIが出せない操作（作品の設定・参加者・関与の選択・人の手の範囲・判断待ちを決める）は窓口で止める |
| AIの関与（4択） | `operations/ai_involvement.py` の `require_ai_may` | 項目の変更（decide）・案や候補（propose）・検査（check）を、作業ごとの関与で許すか決める。依頼の受け付け（`job_start_and_control.enqueue`）もここを呼ぶ |
| AIの案を関与に従って進める | `operations/ai_proposal_flow.py` | AIの案を出し、「AIに任せる」ならそのまま採用、そうでなければ人が選ぶまで案のまま |
| 検査と未定の項目 | `name_checks/name_check_runner.py` の `CHECKS` | 誰が作ったかは見ない。違うのは未定の項目があるかだけ。検査ごとに使う項目を書き、未定なら「データなし」と未定の場所を返す |
| 絵の入口（規制の判定を差し込む場所） | `image_intake.py` の `take_in_image` | 人が置いた絵・持ち込んだ絵・生成した絵は全部ここを通る。判定を記録し、記録の無い絵は登録しない |
| 描き直しの元の絵と人の手の範囲 | `generation_queue/input_image_preparation.py` | 依頼を受けるときに、元の絵が作品の物かを確かめ、人の手の範囲があればマスクを必ず作って渡す |

---

## 2. 場面ごとの入り方

「口」は HTTP の道、「操作」は `/works/{id}/ops` に送る操作の type。AIは窓口 `submit` に Actor(kind="ai", on_behalf_of=頼んだ人) で同じ操作を送る。

### 2.1 コマ割り

| 誰が | 入り方 |
|---|---|
| 人が枠を直接描く（四角以外・斜めを含む） | 操作 `add_panel` / `update_panel` の `frame`（多角形の頂点・mm）。`PanelFrame` の形で確かめる（人もAIも同じ）。描いた項目に人の手の印。段の割りは `update_page` の `layout`。段を決めずに描いてもよい（`rows` 未定。読む順はコマの番号の順）。ただし見開きかどうか（`layout.spread`）は要る |
| 人が描いたネームの絵を取り込む | 絵は口 `POST /works/{id}/images`（`role=page_manuscript`）。コマと文字は外の解析（manga-analyzer）の結果 MangaImport v1 を口 `POST /works/{id}/episodes/{ep}/name-imports` に渡すと、取り込みの案（`made_by=imported`）になる。採用は操作 `apply_name_proposal` |
| AIが割る（コマ割りの計算） | 口 `POST /works/{id}/episodes/{ep}/panel-layout-proposals`。今のネームに `constrained_layout_draft` をかけ、AIの案（`task=panel_layout`）にする |
| 人が一部の枠だけ固定し、残りをAIが割る | 上の口がそのまま行う。`frame` に人の手の印があるコマと確定印のコマの枠を固定（pinned）する。返事の `pinned_panels` に固定したコマ、`broken` に指定どおりにならなかったコマ |
| AIの割りを人が直す | 操作 `update_panel` の `frame`。印が付き、次の計算はその枠も固定する。AIの案が印の枠を変えようとしたら判断待ち |

### 2.2 ネームの中身と文字

| 誰が | 入り方 |
|---|---|
| AIのネーム | 操作 `submit_name_proposal`（`made_by=ai`）→ `apply_name_proposal`。`ai_proposal_flow.submit_ai_proposal` を通すと関与に従って進む。LLMの答えは未定の欄を許さない（`parse_name_draft_answer` が欠けた欄で止める） |
| 人のネーム | 同じ操作で `made_by=human`。未定の項目があってよい |
| 取り込んだネーム | 2.1 の取り込みの口。元の文書は案の `source_document` に丸ごと残る |
| 人が文字を直す | 操作 `add_text_item` / `update_text_item` / `set_removed(target_kind=text_item)`。文字・話者・種類（吹き出し・ナレーションの箱・描き文字、吹き出しの種類）・縦書きか横書きか・書体の大きさ・箱（動かす・大きさ）・しっぽの先・順・同じページの別のコマへ移す |
| 人がコマの中身を直す | 操作 `update_panel` の `content`・`role` |

文字は表 `text_items` に1つずつ持つ。ネームの形では balloon・caption が `NamePanel.balloons`、drawn_sfx が `NamePanel.sfx` になる（`operations/name_draft_conversion.py`）。

### 2.3 絵

| 誰が | 入り方 |
|---|---|
| AIが生成 | 依頼（口 `POST /works/{id}/jobs`）→ 作業者が受け取った絵を入口に通し、操作 `register_image`（`origin=generated`）で候補として登録。コマに使うかは `update_panel` の `image_id` |
| 人が描いた絵 | 口 `POST /works/{id}/images`（`origin=human_drawn`） |
| 外から持ち込んだ絵（1コマ分・ページ丸ごと） | 同じ口で `origin=imported`。元（`source_note`）と利用の条件（`usage_terms`）が要る。ページ丸ごとは `role=page_manuscript` |
| AIの絵を人が外のソフトで直して戻す | 口 `POST /works/{id}/panels/{panel}/image`（`origin=human_edited`）。今の絵を元の版（`based_on_image_id`）にして登録し、コマの絵を替える。前の版は消えない。選ぶ方の出来事を取り消すと前の絵に戻る |
| 持ち込んだ絵・人の絵をAIの直し（囲んで直す・作り直し）の元にする | 依頼の `request.input_images` に `{"node","input","image_id","purpose":"source"}`。出どころで分けない。生成した絵の `based_on_image_id` は元の絵になる |
| 人が切り抜きと置き場を決める | 操作 `update_panel` の `image_placement`（`ImagePlacement`：絵のどこを使うか `crop_px`、ページのどこに置くか `dest_box_mm`、回転）。絵の大きさの外は受け付けない |
| 層 | 操作 `add_panel_layer` / `update_panel_layer`（絵・重ねる順・見せるか・不透明度・切り抜きと置き場）/ `set_removed(target_kind=panel_layer)`。1枚の絵だけのコマは `Panel.image_id`、層に分けたコマは `panel_layers` |
| 人の手の範囲（AIが描き直さない所） | 操作 `add_protected_region`（絵の画素の多角形）/ `set_protected_region_removed`。人だけ |

版の出どころ：口 `GET /works/{id}/images/{img}/lineage`（この版から元の版まで、誰が・どこから・どの条件で）、口 `GET /works/{id}/episodes/{ep}/image-provenance`（話の中のコマと層ごと）。

### 2.4 出どころ・利用の条件・規制の判定

- 利用の条件は同じ形 `UsageTerms`（`usage_terms_schema.py`）：商用に使えるか・権利が誰にあるか・学習に使われるか（使ってよいか）・クレジット・規約のURLか確かめた所・確かめた日。分からない項目は `unknown` と書く。
- 持ち込んだ絵は登録のときに必須。サービスの規約は口 `POST /services`・`PATCH /services/{id}` の `usage_terms`（管理者）。生成した絵は依頼からサービスをたどって規約を出す。どちらも無ければ `terms_missing=true`（補って埋めない）。
- 今のアプリのプロジェクトから取り込んだ絵は、取り込む人が出どころを選ぶ：`imported`（持ち込んだ絵。利用の条件が要る）か `human_drawn`（人が描いた絵）。どちらも人の登録で、`source_note` にファイルの名前と sha256 を残す（9章）。
- 規制の判定は入口 `image_intake.take_in_image` の1か所。判定の手段と閾値は後で決める（V3ハーネス設計 12章）ので、今は全部の絵に `not_judged` を記録する（表 `image_intake_screenings`）。手段を決めたら `INTAKE_JUDGES` に足す。止めた絵も置き場には残し、登録を断る。

### 2.5 AIの関与（4択）

操作 `set_ai_involvement`（作品を管理できる人）で、作業ごとに選ぶ。口 `GET /works/{id}/ai-involvement` で今の値と、作品が選んだか（`chosen`）を見る。

| 関与 | propose（案・候補・作る依頼） | decide（正本の値を変える・案を採用） | check（検査の依頼） |
|---|---|---|---|
| ai_auto（AIに任せる） | 可 | 可 | 可 |
| ai_proposes（AIが案を出し人が選ぶ） | 可 | 不可 | 可 |
| human_makes_ai_checks（人が作りAIは検査だけ） | 不可 | 不可 | 可 |
| no_ai（AIを使わない） | 不可 | 不可 | 不可 |

作業：plan（企画）・structure（構成）・settings_material（設定資料）・name（ネームの中身）・panel_layout（コマ割り）・drawing（作画）・finishing（仕上げ）。
依頼の処理には、何の作業のどの手か（`ai_task`・`ai_action`）を送り先（口 `PUT /routes/{process}`）で決める。決めていない処理は頼めない。

### 2.6 ネームの検査

人のネームも、AIのネームも、取り込んだネームも、口 `POST /works/{id}/episodes/{ep}/name-checks` の同じ検査にかかる（採用する前の案も、今のページとコマも）。未定の項目を使う検査は「データなし」で、理由に未定の項目と場所（「1ページ コマ1」など）が出る。枠だけの検査（はみ出し・重なり・隙間・極小・読む順・単調さ）は、枠があれば判定する。

---

## 3. 引き継ぐときの決まり

### 3.1 AIが人の作った物を引き継ぐ
- 人が変えた項目（項目ごと）には人の手の印が付く。人が足した行は、足したときに入れた項目に印が付く。
- AIは印の項目と、確定印のコマを書かない。AIの変更が当たったとき（直接の操作でも、案の採用でも。採用したのが人でもAIでも）は、断らずにその項目を判断待ち（表 `held_ai_changes`）に置く。1回の変更が印のある項目と無い項目にまたがるときは、印の無い項目は当て、印のある項目だけを判断待ちにする。確定印のコマは全部の項目が判断待ちになる。印・確定印のある行をAIが抜く・戻すときも、抜かずに判断待ち（項目 `removed`）に置く。
- 判断待ちに置いた項目（判断待ちの id・表・行・項目）は、出来事の `held_changes` に残る。操作の窓口の返事（`POST /works/{id}/ops` と取り消しの口は `held_changes`、AIの操作を流す側には返した出来事）と、出来事の一覧（`GET /works/{id}/events`）で見える。
- 判断待ちは口 `GET /works/{id}/held-changes` で見て、操作 `resolve_held_change` で人が決める：accept（採る。その値を人の判断として書く。印が付く）・reject（採らない。今のまま）・reopen（戻す。決めたことを取り消し、判断待ちに戻す。accept で変えた値も戻る）。
- 判断待ちを置いた操作を取り消すと、まだ決めていない判断待ちは withdrawn（下げた）になる。やり直すと開き直す（窓口が取り消しの操作を `undo_with_held_changes` で包む）。決めた後の判断待ちは触らない。案の採用で置いた判断待ちは、案の取り消し（`restore_name_snapshot`）が下げる。
- 今と同じ値は「変えた」ことにしない（印を外さない・判断待ちを作らない）。
- コマ割りの計算は、印の枠を固定して残りを割る。
- 人が描いた絵・持ち込んだ絵をAIが描き直すときは、人の手の範囲を必ずマスクにして渡す。範囲は元の絵と、同じ大きさのまま続く前の版に付いたもの。マスクを入れる所の無い依頼は受けない。描き直した後に元の画素で貼り戻す手順（`comfy_graphs/protected_redraw_graph.py`）は以前からある。
- 印を外せるのは人だけ（`human_hand_fields` を明示して渡す）。

### 3.2 人がAIの作った物を引き継ぐ
- 人はAIの値をいつでも変えられ、変えた所に印が付く。
- 人がAIの案を採用しても、人の手の所は判断待ちになる（人の直しを人が気付かずに上書きしないため）。人の案・取り込んだ案を人が採用したときは、人の判断として上書きし、印を付ける。
- AIの絵は候補として登録されるだけ。コマに使うかは人（関与が ai_auto ならAIも）が選ぶ。
- AIの絵を外で直して戻すと、元の版につながった新しい版になる。

### 3.3 共通
- どの操作も出来事として残り、取り消せる（絵の登録だけは取り消しが無い。絵は消さないため）。
- 値の確かめ（枠の形・文字の種類と範囲・置き場が絵の中か・不透明度の範囲・条件の形）は、人とAIで同じ。
- ロックは、コマはページ・コマ、文字と層はページ・コマ・個別（item）に当たる。

---

## 4. 私の判断

- **AIの関与の既定**：作品が選んでいない作業は「AIが案を出し人が選ぶ」。V3ハーネス設計 5章「人の確認は既定値」に合わせた。既定であることは `chosen=false` で見せる。
- **関与の単位**：作品ごと・作業ごと。設計の「作業ごと」を、工程の作業（7つ）と読んだ。話ごと・ページごとの上書きは作っていない。
- **プログラムの計算もAIの側**：コマ割りの計算は答えが決まるプログラムだが、人の手の印を付けず、人の手を上書きしないため、AIの操作として出す（`program:panel_layout`）。関与が no_ai なら計算も頼めない。
- **AIの案を人が採用したときも判断待ち**：利用者の追加の指示「AIが提案したら判断待ちに」に合わせた。人の案・取り込んだ案を人が採用したときは上書きする（人の判断）。
- **AIの直接の変更も判断待ち**（2026-10-08 に変えた。前は断っていた）：AIが操作で印の項目を直接変えようとしたときも、案の採用と同じく、その項目を判断待ちに置き、印の無い項目は当てる。前からある操作（`update_panel`・`update_text_item`・`update_panel_layer` など）は断り（409）、後から足した操作は判断待ちにしていて、揃っていなかった。断ると、AIの変更のうち印の無い項目まで止まり、AIの依頼が止まった理由を人が出来事から追う必要があった。判断待ちにすると、人は判断待ちの一覧で採る・採らない・戻すを選べる。置いた項目は出来事と操作の返事に残すので、黙って捨てたことにはならない。判断するのは `human_hand_guard.py` の1か所で、操作ごとの分かれ道は消した。AIが人の手の印そのものを変える（`human_hand_fields` を渡す）・確定印を付ける・巻・話・コマの型を抜くのは、今までどおり断る（AIに許していない操作のため）。
- **段の割りは未定でよい**：人がコマ枠の道具で自由に描いた枠には段が無い。段を推し量らず、未定にした。読む順はコマの番号（人が付けた読む順）。見開きかどうかは要る（決めていないページはネームの形にできない）。
- **未定の項目**：ネームの形の項目（大きさ・形・写す範囲・角度・人物・背景・場面・起承転結・ヒキ・中身・吹き出し・擬音・段・吹き出しの話者と種類）を None で持てるようにした。AIの答えには許さない。
- **取り込みの読み方**：MangaImport の 1 ページは見開きでない（Manga2Manga計画で、見開きの絵は左右に分けてから載せる決まり）。コマの形は normal を頂点から「四角」「斜め」に分け、inferred は未定。吹き出しの種類は normal・shout・monologue・narration だけ対応を決め、whisper・inverted・none は未定。除外のセリフとどのコマにも属さないセリフは案に入れず、返事の `dropped` と元の文書に残す。絵の座標が仕上がりか塗り足しまでかは、呼ぶ側が `image_covers` で決める。
- **文字の行**：吹き出しはコマの `content` の中ではなく `text_items` の行に分けた。1つずつ人の手の印・ロック・取り消しを持てるようにするため。未定かどうかは `content.balloons_decided`・`sfx_decided` で持つ。
- **人の手の範囲の座標**：ページの mm でなく、絵の画素で持つ。描き直しのマスクは絵の画素で要るため。前の版の範囲は、同じ大きさのときだけ引き継ぐ（大きさが違えば位置が合う保証が無い）。
- **層と1枚の絵**：今ある `Panel.image_id` は残し、層に分けるコマだけ `panel_layers` を使う。
- **持ち込んだ絵の条件は必須、人が描いた絵は任意**：人が描いた・手を入れた絵は作品の作り手の物として、`terms_missing` を立てない。
- **入口の判定の記録は確定する**：登録が失敗しても、入口を通ったことと判定は残す（呼び出しの記録と同じ扱い）。

---

## 5. 洗い出した不足と対応

| # | 不足（作業前） | 対応 |
|---|---|---|
| 1 | 人が枠だけ描いたネーム・取り込んだネームは、中身の項目が無くネームの形にできず、検査にかけられなかった | 作った（未定の項目、検査ごとの要る項目、段の未定） |
| 2 | 枠の形を書き込むときに確かめていなかった（壊れた枠が入った） | 作った（`PanelFrame` で確かめる） |
| 3 | コマ割りの計算を今のネームにかける口が無かった。人の枠を固定する経路も無かった | 作った（`panel-layout-proposals`） |
| 4 | 人が描いたネームの絵を、コマと文字に取り込む経路が無かった | 作った（MangaImport の取り込み）。解析そのもの（絵からコマを見つける）は外の manga-analyzer の役目で、ここには作っていない |
| 5 | AIの関与の4択を持つ所が無く、工程の進み方が従わなかった | 作った（`ai_involvement`、窓口・依頼・登録で確かめる） |
| 6 | AIの案が人の手の所に当たると、出来事に残すだけで、人が決める場が無かった | 作った（判断待ちと `resolve_held_change`） |
| 7 | 案を採用するとき、同じ値でも書いて人の手の印を外していた。段の傾きと見開きの2ページの項目が、採用で落ちていた | 直した（同じ値は書かない。`PAGE_LAYOUT_KEYS` を NamePage から作る） |
| 8 | 文字を1つずつ直す操作が無かった | 作った（`text_items` と操作） |
| 9 | 持ち込んだ絵をAIの直しの元にできなかった（ComfyUI に絵を上げる処理が無かった） | 作った（`input_images`・`/upload/image`） |
| 10 | 版のつながり（元の版）と、人が手を入れた絵の出どころが無かった | 作った（`based_on_image_id`・`human_edited`・lineage） |
| 11 | 利用の条件を持つ所が無かった（絵・サービス） | 作った（`UsageTerms`） |
| 12 | 規制の判定を差し込む場所が無かった | 作った（入口。判定の手段は未設定） |
| 13 | 絵の切り抜きと置き場、層、人の手の範囲を持つ所が無かった | 作った |
| 14 | 人の手の範囲を描き直しで守る経路が無かった | 作った（依頼のときにマスクを必ず渡す） |
| 15 | 依頼の処理が何の作業か分からず、関与と照らせなかった | 作った（送り先に `ai_task`・`ai_action`。必須） |
| 16 | ページ丸ごとの絵をコマごとに切り分ける | 作っていない。描き直しはページの絵と範囲のマスクで足りるため。必要になったら足す |
| 17 | 絵の中の人の手の範囲を、ページの mm の範囲から作る | 作っていない（範囲は絵の画素で人が決める） |
| 18 | 生成した絵の入口の判定（生成の出口） | 作った（入口が同じ）。書き出しの入口は作っていない |

---

## 6. V3細部の決めごと 10.1・10.4 との対応

10.4 の各行と 10.1 の道具を、サーバーのどのデータと操作で受けるか。画面は作っていない。
「画面だけ」の物のほかに、サーバーで足りない物は無い（2026-10-08）。この表と同じ対応を `v3/server/src/v3server/feature_coverage.py` に持ち、`tests/unit/test_feature_coverage.py` がこの文書の 10.1・10.4 の行を全部読んで、どの行も載っていて、載せた操作と口があるかを確かめる。

どの操作も操作の窓口（`POST /works/{id}/ops`）を通り、権限・ロック・人の手の印・1回で取り消す・AIの関与が同じにかかる。どの操作でも、AIの変更が人の手の印の付いた項目に当たると、断らずにその項目を判断待ちに置く（3.1）。人が「動かさない」を掛けた物は、人もAIも変えられない（409）。

### 6.1 10.1 の道具

| 道具 | サーバーのデータと操作 |
|---|---|
| 選ぶ | 画面だけ。ロックは口 `POST /works/{id}/locks` |
| 囲んで頼む | 依頼の `input_images` に purpose=mask と `region_px`（元の絵の画素の多角形）を渡すと、サーバーが元の絵と同じ大きさのマスクを描く（`generation_queue/input_image_preparation.py`）。人の手の範囲は今までどおり自動で守る |
| 赤入れ | `annotation_items`。`add_annotation`・`update_annotation`（文・範囲・作業・済み）・`set_removed(annotation)`。AIが付けるのは、その作業の検査の関与で許されているときだけ。赤入れから依頼を作る口 `POST /works/{id}/annotations/{id}/job`（依頼に赤入れの文と範囲を添え、`record_annotation_job` で赤入れに残す）。権限は赤入れを付けられる人（can_comment） |
| ペン | 線（`pen_strokes`）が正本。1本ずつの物で、点（x・y・筆圧・時刻）の並び・筆（今のアプリの12種）・太さ・色・不透明度・乱れの種（seed）を持つ。`add_pen_strokes`・`update_pen_strokes`（何本でもまとめて動かす・太さ・色・不透明度・筆を変える）・`remove_pen_strokes`。人だけが出せる。層の絵は線から作った控えで、画面が描いて口 `POST /works/{id}/layers/{id}/stroke-cache`（`set_stroke_cache`）で上げる。層は線の版（`stroke_revision`）と、控えを作った版（`image_stroke_revision`）を持ち、違えば古い控えとして、AIへ渡す依頼と書き出しを止める |
| 消しゴム | 線の消しゴム `erase_pen_strokes`：線ごと（whole）・交わりまで（to_crossings）・触れた所だけ（touched。線が分かれる）。答えは線のデータ。線を持たない絵（AIの絵の層・コマの1枚の絵）は画素の消しゴム `POST /works/{id}/panels/{id}/erase-pixels`（`erase_pixels`）で、新しい版（human_edited）と、消した所の人の手の範囲（マスク）を作る |
| 文字（写植・描き文字） | `text_items` に書体（`font_family`）・飾り（`decoration`：塗り・縁・光彩・影・残像・帯・字間）・ルビ（`ruby`）・置き方（`transform`）・不透明度・仕上げを足した。文字の一部の書式（`spans`：書体・大きさの比・太らせる幅・色）と組版（`typesetting`：行間・自動の改行・縦中横・揃え。無ければ作品の `preferences.typesetting`）も持つ。禁則・縦中横・約物の向き・自動の改行は書き出しの組版（`v3/psd_writer/text_layout.js`。`V3サーバーの土台.md` 3.6）。描き文字はフキダシの形を持たない |
| コマ枠 | 枠を動かす：`update_panel.frame`。分ける `split_panel`・合わせる `merge_panels` は1つの操作で、1回で取り消せる（10.1 の決まり：細すぎる分け方は閾値 `panel_short_side_min_mm` で断る。絵は大きい側に残る。隣り合わない2つは合わせない）。枠の線と塗り：`update_panel.frame_style`（無ければ作品の `preferences.frame_style`） |
| ナイフ | `split_panel`（横・縦・斜め。斜めは角度。間の幅は `gap_mm`、無ければ作品のコマの間） |
| フキダシ | `update_text_item` の `box_mm`・`tail_target_mm`・`text`・`balloon_shape`（型の名前と、箱に合わせた外形・線・塗り・しっぽの根元の幅と曲がり。自分で描いた形も外形で持つ）。書き出しはしっぽを外形と1つの形にして描き、`joined_to_previous` のフキダシもつなげる |
| トーン | `page_items`（`item_kind=tone`）。網点・線・砂目・グラデ・雪・集中線・スピード線、線数・濃さ・角度・本数・中心、貼る所（コマ・囲む・塗る＝マスクの絵）。`add_page_item`・`update_page_item` |
| 図形 | `page_items`（`item_kind=shape`）。四角・楕円・多角形・線・絵記号（名前と外形）、線・塗り・影 |
| 手のひら | 画面だけ |
| 読む順・表示するもの・取り消す・やり直す・拡大縮小 | 読む順：`update_panel.order`・`update_text_item.order`。取り消す・やり直す：口 `POST /works/{id}/events/{event}/undo`（取り消しの取り消しでやり直し）。表示するもの・拡大縮小は画面だけ |

### 6.2 10.4 の各行

| 今のアプリ | サーバーのデータと操作 |
|---|---|
| コマの型・図形のコマ・コマの間・枠の線と塗り・ばらばらに割る | コマの型：`panel_templates`（`save_panel_template`・`apply_panel_template`）。図形のコマ：`add_shape_panel`。コマの間：`page_spec.gutter_*`。枠の線と塗り：`frame_style`。ばらばらに割る：`random_split_panel`（種を残すので同じ割りを作り直せる） |
| ナイフ | 6.1 のナイフ |
| フキダシの型・自分で描くフキダシ | 6.1 のフキダシ（`balloon_shape`） |
| 文字・文字の飾り・書体を足す | 6.1 の文字。書体はサーバーの書体の置き場（`V3_FONT_DIR`）のファイルの名前で選ぶ。文字の種類ごとの標準の書体は作品の `preferences.fonts_by_kind` |
| ペンの種類・消しゴム | 6.1 のペン・消しゴム |
| トーン・集中線・スピード線 | 6.1 のトーン |
| 絵記号 | 6.1 の図形 |
| 位置・角度・拡大・傾き・反転・不透明度 | 絵・文字・トーン・図形で同じ形（`name_structure/item_transform.py` の ItemTransform：回転・傾き・左右と上下の反転）。絵は `image_placement`・層の `placement`、文字は `transform`、トーン・図形は `transform`。不透明度はどれも `opacity` |
| 白黒化・明るさ・ぼかし・重ね方・まとめて戻す | 仕上げ（`adjustments`：白黒化・明るさ・ぼかし・重ね方）を、コマ・層・文字・トーン・図形が同じ形で持つ。元の絵は変えない。まとめて戻す：`reset_adjustments`（1つの物か、ページの全部。1回で取り消せる） |
| 層の一覧（見せる・動かさない・順番） | `visible`・`stack_order`。動かさない：`set_fixed`（コマ・文字・層・トーン・図形。人だけが掛け外しできる） |
| 絵を作る・絵から作り直す・囲んで直す・角度を変える・拡大・背景を抜く・絵から指示を読む | 依頼（`POST /works/{id}/jobs`）。角度を変える（change_angle）・背景を抜く（remove_background）・絵から指示を読む（read_prompt）は、何の作業の処理か（ai_task・ai_action）をサーバーが決めていて、送り先を決めるときと頼むときに確かめる（`generation_queue/known_processes.py`）。絵から指示を読む口 `POST /works/{id}/images/{id}/read-prompt`（答えは依頼の `result.read`） |
| 手順・モデル・シード・参照 | 手順・モデル：`service_processes`。シード：依頼の `overrides`、記録は `call_logs.seed`。参照：`input_images` の purpose=reference。人物ごとの生成の設定：設定資料の `generation`（指示文・否定の指示文・LoRA・参照の絵・シード） |
| 設定資料（人物・小物・背景・その他） | `material_entries`（名前・特徴・服・絵・生成の設定・メモ）。`add_material_entry`・`update_material_entry`・`set_removed(material_entry)`。AIが足すと案（proposed）で、人が `decide_material_proposal` で採る |
| あらすじ・読者・人物を抜き出す・入れないもの | `work_plans`（`set_work_plan`）。人物を抜き出す：口 `POST /works/{id}/plan/extract-characters`（extract_characters。答えの人物はAIの案として設定資料に入る） |
| ページを足す・画像から足す・取り込む | ページを足す：`add_page`。並べ替える：`reorder_pages`。見開き：`add_spread`・`update_spread`（見開きにまたがる絵）・`set_removed(spread)`。ページの種類・色の種類・解像度・ノンブルの出し方：`update_page`（どれも人だけ）。画像から足す・取り込む：絵の口と `name-imports`。絵からコマを見つける解析は外（manga-analyzer）。今のアプリのプロジェクト（.lz4）：口 `POST /works/{id}/episodes/{id}/current-app-imports`（`import_current_app_project`。9章） |
| 画像の書き出し・コピー・解像度・紙の大きさ | 口 `POST /works/{id}/exports`（形：png・pdf・psd、ページ、解像度（無ければページごと）、見開きの出し方、紙の大きさ）。色の種類（2階調・グレー・カラー）と解像度はページごと、ノンブルは作品の `preferences.nombre`。入稿前の確かめ：口 `POST /works/{id}/preflight`（`V3サーバーの土台.md` 3.6）。書き出しは書き出しの待ち行列（Temporal の v3-export）で行い、`GET /works/{id}/exports/{id}` で状態、`.../files/{name}` でファイル。紙の大きさを渡すと、ページを紙の真ん中に置く。コピーは画面だけ。直した PSD を戻す口 `POST /works/{id}/exports/{id}/pages/{page}/psd`（`apply_psd_import`） |
| マス目・基本枠・印の表示 | 基本枠：`page_spec`。表示は画面だけ |
| 言語・自動保存・設定 | 利用者ごと：口 `GET/PUT /me/settings`（その人だけの物なので操作の窓口の外）。作品ごと：`set_work_settings.preferences`（言語・文字の種類ごとの書体・コマ枠の標準・自動保存の間隔） |
| 探す・置き換え | 探す：口 `GET /works/{id}/search`（文字・話す人・設定資料・企画・赤入れ）。置き換え：`replace_text`（当たった全部を1回で変え、1回で取り消せる。ルビの付いた文字で字数が変わる所は止める） |
| 統計の一覧 | 入れない（8章） |

---

## 7. 確かめたこと

`cd v3/server && uv run pytest -q tests/unit` → 234 件通過（2026-10-08、AIの直接の変更を判断待ちに揃えた後。ほかの作業で足された試験を含む）。
`uv run pytest -q tests/integration --ignore=tests/integration/test_comfyui_real.py --ignore=tests/integration/test_detector_real.py` → 56 件通過・3 件飛ばし（試験の書体が無い）。続けて7回流し、ほかの作業の試験ファイルが途中で同じ試験用データベースを作り直したと見られる1回（未検証）を除いて、すべて通った。
移行 `0006_human_tools_and_finishing.py`：`alembic downgrade base` → `upgrade head` → `downgrade 0005` → `upgrade head` が通り、`alembic check` が「No new upgrade operations detected」。
`v3/psd_writer` の `npm test` → 2 件通過。
前からある `tests/integration/test_queue.py::test_人の依頼をAIの依頼より先に送る` が時々落ちていた件は、依頼を受ける口が流れを始めただけで返し、送信が待ち行列に入る順が頼んだ順と入れ替わっていたのが原因だった。口を送信が待ち行列に入ってから返す形に直した（経緯と数字は `V3サーバーの土台.md` 7章・8章）。

### 7.1 6章の道具と機能（2026-10-08 に足した物）

`tests/unit/test_feature_coverage.py`
- every_10_1_tool_is_mapped / every_10_4_row_is_mapped（V3細部の決めごと 10.1・10.4 の行を文書から読み、`feature_coverage.py` に全部あり、載せた操作と口が本当にある。文書から消えた行が一覧に残っていない）

`tests/unit/test_hand_tools_and_export_units.py`
- 線の消しゴムの3つの消し方（線ごと・交わりまで・触れた所だけ）
- 線の値の決まり / 画素の消しゴムがマスクを作る
- ページを描く層の順（紙・コマ・トーンと図形・枠・手描き・フキダシ・写植・描き文字）と層の名前の [id] / 足りない値で止める
- 文字を絵にする（IPA の書体）と書体の探し方 / 紙の上の PDF
- 層の名前から [id] を読む（NUL と「 #1」を除く）
- PSD の書き出し→読み戻しの突き合わせ（変わった・新しい・無くなった）
- 決まった処理の作業が動かない / 絵から指示を読む・人物を抜き出す問いと答えの読み方

`tests/unit/test_print_export.py`：PSD は Node（`v3/psd_writer`）で書き、層を読み戻して確かめるように直した。

`tests/integration/test_human_tools_and_finishing.py`
- コマを分ける_合わせるは1つの操作で_1回で取り消せる
- トーンと図形_動かさない_まとめて戻す_AIが人の所に当たると判断待ち
- 文字の書体_飾り_ルビ_角度_フキダシの形
- ペンの線は1本ずつの物で_選んで変え_線の消しゴムで分かれ_控えの古さが分かる
- 画素の消しゴムは新しい版と人の手の範囲を作る
- 赤入れ_企画_設定資料_探す_置き換え_利用者の設定
- 書き出し_PNG_PDF_PSDと_直したPSDの戻し（書き出しは Temporal の待ち行列を本物で通す。戻しは1回で取り消せる）

### 7.2 前の作業（移行 0005）

`alembic upgrade head` → `downgrade 0004` → `upgrade head` が通る（移行 `0005_human_ai_interchange.py`）。

`tests/unit/test_human_ai_handover_units.py`
- 検査の一覧に書いたidと_検査が返すidが合う
- 一覧の要る項目は_未定にできる項目の名前だけ
- 枠だけのネームでも検査が回り_枠の検査は判定し_中身の検査はデータなし（斜めの枠を含む）
- 全部決まったネームは今までどおり全部の検査が回る
- 段の割りが未定なら読む順はコマの番号の順で_割りの計算はしない
- AIの答えは未定の欄を許さない
- 取り込みの座標を基本枠のmmに直す（仕上がり・塗り足しまで）
- 取り込みは分かる所だけ読み_分からない所は未定にする
- 取り込みの形が崩れていれば止める
- AIの関与の4択で_AIの手が許されるもの
- 項目を変えるAIは_その項目の作業の関与で止まり_人は止まらない
- 同じ値は変更に数えない
- AIの変更は人の手の所に当たる分を分けて返す
- 文字の値の形 / 絵の置き場と利用の条件の形 / 人の手の範囲のマスクは範囲だけ白

`tests/unit/test_comfyui_sender.py`（追加 2 件）
- prepared_inputs_are_uploaded_and_put_into_the_workflow（偽の ComfyUI。/prompt の前に /upload/image し、返った名前が手順に入る）
- upload_failures（5xx は transport、4xx は refused、名前の無い返事は broken_response、無いノードは refused）

`tests/integration/test_human_edit_and_handover.py`
- 人が文字を足し_直し_抜き_取り消せる_検査も同じにかかる
- AIの案が人の直した所に当たると判断待ちになり_人が採る_採らない_戻すを選べる
- AIの関与の4択に従って_案_採用_作業が止まる
- 人が描いた斜めの枠を固定して残りをコマ割りの計算が割り_人の枠は上書きしない
- 最小の大きさの閾値が無ければ割りを計算しない
- 人が描いたネームを取り込み_分からない所は未定のまま同じ検査にかかる
- コマの絵を差し替えても前の版が残り_誰がどこからどの条件で作ったかをたどれる
- 絵の切り抜きと置き場と層を人が直し_AIは人の所を変えられない
- 入口を通らない絵と_入口で止めた絵は登録しない（止める判定は試験の中だけで差し込んだ）
- 人の手の範囲は人だけが決められる
- 人が手を入れた絵を元にAIが描き直すとき_人の手の範囲を必ずマスクで渡し_版がつながる（偽の ComfyUI、Temporal・PostgreSQL・OpenFGA は本物）

---

## 8. まだ作っていないもの・未検証

- 未検証：本物の ComfyUI の `/upload/image` に上げて、`LoadImage` が読めること（偽の ComfyUI でだけ確かめた。形は ComfyUI の口の決まりに合わせた）。
- 未検証：人の手の範囲のマスクを `protected_redraw_graph` の「引く」に渡したときに、人の範囲が守られること（引く手は試作でも未検証。V3細部の決めごと 10.2）。
- 未検証：MangaImport の座標の読み方が、manga-analyzer の実際の出力と合うこと（形は Manga2Manga計画の文書どおり。実物の出力では試していない）。
- 未検証：人の手の範囲を、大きさが同じ前の版から引き継ぐとき、絵の中の物の位置が合っていること（拡大・切り抜きをした版では合わない）。
- 未検証：判断待ちを、人が実際の作業で決めきれる量か（AIの案が人の手の所に広く当たると判断待ちが多くなる）。
- 作っていない：規制の判定の手段（12章「後で決める」）。書き出しの入口の判定。
- 作っていない：LLMにネームを作らせる依頼の結果を `ai_proposal_flow` に流す処理（作業者が LLM の答えを案にする所）。今は流す先だけある。
- 作っていない：ページ丸ごとの絵をコマごとに切り分ける。
- 作っていない：AIの関与を話・ページごとに変える。
- 画面は作っていない（6章の道具はサーバーのデータと操作だけ。ペンの控えの絵を描くのも画面の役目なので、画面が無い今は試験の中で作った絵を上げている）。
- 揃えた（2026-10-08）：前は、新しく足した操作（トーン・図形・ペン・赤入れ・設定資料・まとめて戻すなど）は判断待ちに置き、前からある操作（`update_panel`・`update_text_item`・`update_panel_layer` など）は断っていた。今はどの操作も判断待ちに置く（4章）。
- 決めていない：AIの層の操作で、役割が「人の手」の層は、今も印と別に断る（`update_panel_layer` の「人の手の層はAIが変えられない」）。この層は全部の項目に印が付くので、判断待ちに揃えてもよいかは決めていない。
- 未検証：ag-psd が書く線の形（vectorMask・vectorStroke）は ag-psd で読み戻せることだけ確かめた。Photoshop・Krita・CLIP STUDIO で線として表示されるかは未検証。今の書き出しは線を画素の層にする（画面にその旨を出す）。
- 未検証：直した PSD を戻すとき、画素が全部同じかで「変わっていない」を決めている。保存のときに画素を少し変える道具では、変えていない層も「変わった」になるおそれがある。
- 未検証：文字を絵にするときの行の間（`LINE_GAP_RATIO = 0.2`）。縦書きの約物の向きと縦中横はしていない。
- 未検証：絵から指示を読む（read_prompt）を VLM に頼む方が、今のアプリのタグの推定より合うか。
- 未検証：角度を変える・背景を抜くの、つなぎ先の本物の手順（グラフ）。サーバーは処理の名前と作業を決めて送るだけ。
- 決めたこと：PSD で差し替えた絵は、重ね方のほかの仕上げを外し、枠の外にあった絵は失う（PSD の層には枠の中だけが入るため）。
- 決めたこと（2026-10-08）：判断待ちの選べる手は行ごとに持つ（`held_ai_changes.choices`）。前は種類ごとに決まっていた（`CHOICES[kind]`）。判断の操作は行の `choices` で確かめる。言語ごとの PSD の文字の層は「絵として採る」を持たず、その後に訳文が抜かれていれば「捨てる」か「残す」だけになる
- 決めたこと（2026-10-08）：見開きを1枚にした PSD の戻しは、1回の操作で2ページを扱う（ロックは2ページ、取り消しも1回）。見開きの絵・紙のように、どのページの物でもない層の画素が変わったら判断待ちにする（理由「どのページの物でもない層（見開きの絵・見開きの紙）の画素が変わった」）
- 決めたこと：PSD の戻しを取り消すと、そのとき作った判断待ちは「取り下げ」になる。判断待ちを決めた後に戻しを取り消すと、決めた結果も戻るので、新しい順に取り消す。
- 決めたこと：利用者ごとの設定は操作の窓口の外（出来事の一覧と取り消しに入らない）。

---

## 9. 今のアプリのプロジェクトの取り込み（2026-10-08）

今のアプリ（ブラウザだけで動く版）の「プロジェクトを保存」で出した `.lz4` を、話の後ろにページとして足す。人の操作で、作品の作者（`can_manage`）だけが出せる。AIは出せない。

- 口：`POST /works/{id}/episodes/{eid}/current-app-imports`（multipart：`project` にファイル、`image_origin` に `imported` か `human_drawn`、`imported` なら `usage_terms` に `UsageTerms` の JSON）。報告は `GET /works/{id}/current-app-imports/{report_id}`
- 読む所：`current_app_import/project_file_reader.py`（入れ物の形は `js/core/compression/lz4.js` と同じ。LZ4 は Python の `lz4` ライブラリでほどく）。古い zip の形は読まない（止める）
- 形の計算：`current_app_import/fabric_geometry.py`（fabric.js 5.3.0 の位置・回転・拡大・傾き・反転・原点、多角形と道（M・L・Q・C・Z）の点）
- 行の案と報告：`current_app_import/import_plan.py`。正本へ入れるのは操作 `import_current_app_project`（`operations/current_app_import_operations.py`）で、中はページ・コマ・絵の登録・コマの絵・層・文字を足す前からの操作の apply をそのまま通す。値の確かめ・人の手の印・AIの関与は1つずつ足したときと同じにかかる。1回で取り消せる（作ったページ・コマ・層・文字・AIの設定に抜いた印を付ける。絵と報告は残す）
- 寸法：今のアプリのページ（`canvas_info.json` の mm）を仕上がりの大きさとみなし、作品の `page_spec` の仕上がりと比べる。違うページはページだけ作り、中の物は全部「入れられない」にする。座標は 画素 × mm/画素 − 基本枠の原点

移し方（元の物 → 正本）

| 元の物 | 入れる所 | 報告の状態 |
|---|---|---|
| ページ | `pages`（話の最後の番号の後ろ） | 移した |
| コマ（`isPanel` の多角形・四角） | `panels.frame`（mm の多角形、基本枠からはみ出せば塗り足し）。読む順は位置から決める（今のアプリは読む順を持たない）。枠の線は `frame_style` | 変えて移した（理由を書く） |
| コマの中の絵（最初の、不透明で見えている物） | 絵の登録（`image_files`）と `panels.image_id`・`image_placement`（切り抜き・置く箱・回転・傾き・反転） | 変えて移した |
| トーン・効果線の絵、2枚目からの絵 | `panel_layers`（トーンは role=tone、ほかは art） | 変えて移した |
| 縦書き・横書きの文字 | `text_items` の caption（コマの中にあるとき） | 変えて移した |
| フキダシ（形・四角・文字の組） | `text_items` の balloon。外形は `balloon_shape` の custom に mm の点で入れる。四角は「要らない」 | 変えて移した |
| コマ・絵ごとのAIの設定（`text2img_*`・`img2img*`・`temp*`） | `element_generation_settings`（指示文と否定の指示文、元の値はそのまま `source_values`） | 移した |
| プロジェクトの基本のプロンプト | 同じ表の `project_base`（全ページで同じなら1行、違えばページごと） | 移した |
| ペンの線・コマの外の絵や文字・知らない種類 | 入れない | 入れられない（理由を書く） |
| 取り消しの記録・書体・参照の絵・一覧の小さな絵 | 入れない | 要らない（理由を書く） |

- 報告（`current_app_import_reports`）には、元のページ番号・物の番号・種類・名前・状態・入れた表と行・理由を、元の物1つにつき1行残す。黙って落とさない（試験で、元の物が全部ちょうど1回出ることを確かめる）
- 絵は入口（`image_intake.take_in_image`、入口の種類は `human_upload`）を通す。読めない絵・入口で止めた絵は入れず、報告に理由を残す
- 本物の見本：今のアプリを Playwright（Chromium、`/opt/pw-browsers`）で動かし、コマ割りのテンプレート・コマの指示文・コマの絵・トーン・縦書きと横書きの文字・フキダシ・ペンの線・2ページ目を作って保存した4ページのファイル（`v3/server/tests/fixtures/current_app_project_4pages.lz4`、作り方は同じ場所の `build_current_app_project.js`）
- 突き合わせの結果（`tests/integration/test_translation_review_import.py`）：報告の行は19（元の物12個と、ページ・取り消しの記録などページ単位の行）で、移した4・変えて移した10・入れられない1（ペンの線）・要らない4。コマ3つ・文字4つ（文字は元と全部同じ）・コマの絵1枚・トーンの層1つ・AIの設定6行。絵の sha256 は元の data URL の中身と同じ
- 未検証：フキダシの外形（最も大きい輪を使う）としっぽの位置。縦書きの字間・行間は移していない（報告に書く）
- ペンの線を移す（2026-10-08）：customType の無い path と、path だけの group を、コマの人の手の層（役 `human_hand`、絵は無し）の線（`pen_strokes`）にする。筆は pencil とみなし（報告に書く）、色は css の色、太さは strokeWidth × 拡大 × mm/画素、点の時刻は 0（今のアプリは時刻を持たない）、コマは線の範囲の真ん中が入るコマ。模様の線（stroke が pattern）は移さない（入れられない）。消しゴムの跡・塗りがあれば報告に書く。線の控えの絵は無いので、画面で開いて線から描くまで、書き出しと入稿前の確かめ（`stroke_cache`）が止める（黙って線を抜かない）
- 作っていない：コマの外の物（V3 はコマに属さない絵の層を持たない）。フキダシの格子。取り込みの画面

## 10. 翻訳（2026-10-08）

- 元の言語は作品の `preferences.language`。決まっていないと訳文は置けない（どれが元か分からないため）
- 訳文は文字1つ×言語1つで1行（`text_item_translations`：文字・書く向き・文字の大きさ）。言語は BCP 47 の形（`en`・`zh-Hans` など。中身が正しい言語かまでは見ない）
- 操作：`set_text_translation`（無ければ足す、あれば変える）・`set_text_translation_removed`。読む口：`GET /works/{id}/translations?language=`（訳文と、訳文の無い文字）
- 権限：作品の `can_translate`（作者・翻訳者）。翻訳者はページの `can_draw` を持たないので、元の文字・位置・フキダシ・コマは変えられない（試験で確かめた）。ロックは文字1つ（`item`）にだけ当たり、ページを描いている人のロックでは止めない
- 人の手の印と判断待ち：言語ごとに別の行なので、印も判断待ちも言語ごとに分かれる。AIの関与の作業に「翻訳（translation）」を足した。AI（機械の翻訳）の変更が人の置いた訳文に当たると判断待ちになり、印の無い言語は変えられる（試験で確かめた）。判断待ちは訳文を置ける人が決める
- 言語ごとの入稿前の確かめ（2026-10-08）：`POST /works/{id}/preflight` に `language`。訳文に差し替えて確かめ、訳文の無い文字を `translation` として場所付きで挙げる
- 言語ごとの PSD（2026-10-08）：`language` を付けた PSD も書き出せる。戻すと、文字の層は訳文の行（`text_item_translations`）への判断待ちになり、元の文字は変えない（試験で、訳文を打ち直しても元の文字が同じことを確かめた）
- 抜いた訳文（2026-10-08）：`GET /works/{id}/translations` が抜いた訳文も返す。抜いた訳文のある文字へ `set_text_translation` で足すと、その行を戻して書き直す（取り消すと抜き直す）
- 言語ごとの書き出し：`POST /works/{id}/exports` に `language`。訳文に差し替えた写しで描く（行は変えない）。訳文の無い文字があれば、その文字を挙げて止める（元の文字で埋めない）。ルビは元の文字の位置に付くので訳文では外す。PSD は言語ごとに書き出さない（直した PSD を戻す突き合わせが元の言語の文字で動くため。未対応）
- 未検証：訳文の長さでフキダシからはみ出すか（箱は元のまま。はみ出しの検査は無い）
