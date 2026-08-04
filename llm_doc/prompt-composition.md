# コマの構図とプロンプト

画像生成AIに漫画のコマを描かせるときの知見。プロンプト生成まわりを触る前に読む。

## 1. 漫画のコマと、画像生成AIが既定で描く絵は違う

学習データ（Danbooru系）はイラスト単体の集まりで、漫画のページではない。
そのため何も指定しないと、モデルは**「1人・膝上〜バストアップ・正面・カメラ目線」**に寄る。
漫画のコマがまず取らない構図で、これがそのまま並ぶとページが漫画に見えない。

実際のポスト数:

| タグ | 件数 |
|------|-----:|
| `1girl` | 8,229,159 |
| `solo` | 6,913,998 |
| `looking_at_viewer` | 4,793,726 |
| `full_body` | 1,247,973 |
| `upper_body` | 1,165,014 |
| `cowboy_shot` | 831,263 |
| `no_humans` | 229,525 |
| `from_above` | 142,540 |
| `from_below` | 116,944 |
| `scenery` | 73,456 |
| `close-up` | 62,529 |
| `wide_shot` | 23,183 |
| `very_wide_shot` | 2,190 |

`looking_at_viewer` が全体の過半数を占める。漫画のコマで読者と目が合うのは
意図した演出のときだけなので、ここは特に差が大きい。

## 2. ただし、常に同じ調整が要るわけではない

必要な調整は作品の性格で変わる。一律に引きを足すのは間違い。

- **人物にフォーカスする漫画（成人向けなど）** — 局所のクローズが多い。
  引きは場所を示す最低限でよい
- **青年向け** — ワイドショットが多い。人物が場所の中でどれくらいの大きさなのかを
  読者に見せる
- **場面の切り替わり、俯瞰で状況を説明したいところ** — 作品の性格に関わらずワイドが増える

このアプリでは、これを**タグの表ではなく作品傾向の説明文としてLLMへ渡し、
どのコマを寄りにしてどのコマを引きにするかはLLMに判断させる**。
（→ `MANGA_TONE_PRESETS` / `js/ai/prompt/panel-composition.js`）

## 3. フレーミングタグは効かない。要素が構図を決める

**ここが一番間違えやすい。**

`full body` や `wide shot` は「そう描け」という指示ではなく、
**出来上がった絵に後から付いたラベル**である。プロンプトに入れても素直には効かない。

構図を決めるのは**フレームの中に何があるかを名指ししたかどうか**。

- **全身を描かせたい** → 足元にあるものを書く。ブーツ・靴・脚・立っている床や地面。
  下端に来る要素が名指しされて初めて、そこまで入る絵になる
- **顔だけを描かせたい** → フレームに入るものだけを書く。靴や脚や地面を書くと、
  それを収めようとして勝手に引く
- **場所を描かせたい** → その場所に実際にあって、フレームを埋める大きさのものを書く。
  人は出さないか、小さく遠くにいると言う
  （プロンプトには具体例を並べない。並べると室内の場面に`sky`が入る → 10章）

`wide shot` などを添えること自体は構わないが、**あくまで補助**。
要素の名指しと矛盾しない範囲でしか効かない。単独では当てにしない。

このアプリでは、この知識を`buildPanelSystemPrompt()`のシステムプロンプトに書いて
LLMに実行させている。**役割ごとにタグを決め打つ表は持たない**（ルールベースにすると、
効かないタグを機械的に入れるだけになるため）。

## 4. 見切れは常にネガティブへ入れる

腕・脚・足先が枠で切れた絵は、**後から直しようがない**。
だから見切れのタグは判断の余地なく常にネガティブへ入れる。

```
out of frame, cropped, cropped legs, cropped torso, cropped arms,
cropped shoulders, head out of frame, feet out of frame,
foot out of frame, knees out of frame
```

**意図して見切れさせたい場合は、プロンプトではなくアプリ側で行う。**
生成後に画像をコマの枠へ接する位置まで動かせば、断ち切りとして成立する。
プロンプトで狙うと、切れる位置も切れ方も制御できない。

`hand out of frame` はDanbooruに存在しない（0件）ので使わない。
存在しないタグを書いても効かないうえ、効いているつもりになる。

## 5. コマの形と生成解像度

コマの形と生成解像度が繋がっていないと、横長のコマに引きの絵を頼んでも
正方形で生成されて嵌める段で上下が切られ、**結局バストアップに見える**。

SDXLの学習解像度（バケット）から最寄りを選ぶ:

```
640x1536 / 768x1344 / 832x1216 / 896x1152 / 1024x1024
1152x896 / 1216x832 / 1344x768 / 1536x640
```

これ以外の比率で描かせると構図が破綻する。5:1のような極端な帯コマは
端のバケットで生成してコマ側で切り出す。
（→ `PANEL_SDXL_BUCKETS` / 「生成サイズをコマの形に合わせる」既定オフ）

## 6. 人数タグはコマごとに決める

キャラ表に`1girl`のような人数タグを入れると、2人のコマでキャラ表を2つ並べたときに
`1girl`が2回入る。`solo`への偏りと噛み合って絵が破綻する。
人数はコマ単位で決めさせる（`LLM_STORY_SHEET_SYSTEM`に明記済み）。

## 7. 重み記法の可搬性

`(tag:1.3)` はComfyUI / SD WebUIでは効くが、fal.ai経由のモデルでは無視されることがある。
プロバイダを跨いで同じ効きを期待しない。

## 8. 配分を決め打たない

「4コマ以上なら人物なしを1枚」のような枚数の割り当ては書かない。
必要な枚数は作品の性格と、そのページで起きることで変わるので決め打てない。
渡すのは原則と判断材料（コマ数・形・面積比・断ち切り・先頭/末尾・作品傾向）だけ。

コード側の検証（`findPanelRhythmProblem`）も同じ。枚数の表は持たず、
**「全コマに人物が居る」という壊れ方だけ**を拾って作り直させる。
LLMは放っておくと全コマを人物のバストアップで埋めるため、そこだけは残している。

## 8.5 キャラと背景の固定 — 現状はタグだけ

**タグの一致だけでは固定できない。** 現状このアプリが持っているのは以下だけで、
「同じキャラに見える」「同じ場所に見える」水準には届いていない。

| 手法 | 効き | 現状 |
|------|------|------|
| キャラ表・ロケ表のタグを一字一句コピー | 弱。髪型と服は揃うが顔は揃わない | **実装済み** |
| seedを揃える（`text2img_seed=-2`でbaseと共有） | 中。ただし構図まで似るので、コマごとに絵を変えたい漫画では逆効果 | 既存の仕組みとして存在するが、キャラ単位ではなくページ全体 |
| キャラLoRA | 強。顔が揃う唯一の実用解 | **未実装**（ComfyUIワークフロー側にノードはある。キャラ表にLoRA名とトリガーワードを持たせる欄が要る。→ `roadmap/027`） |
| 参照画像（IPAdapter / Reference） | 強。LoRAを作らずに寄せられる | **未実装**（→ `roadmap/022`） |
| 前のコマをi2iの種にする | 背景に強い。同じ場所のコマを繋げられる | 未実装（I2I自体はある） |
| 背景画像を1枚生成して使い回す | 最も確実。同じ場所は同じ絵になる | 未実装（アプリ側の機能として） |

**タグ以外に手が無いのが現状の限界。** LLM側でこれ以上できることは無く、
ここから先はアプリの機能追加になる。

キャラだけでなく**絵柄と色のブレ**も原因が別にある。手法の比較・SDXLでの具体的な
使い方・実装順は`llm_doc/consistency.md`にまとめてある。

## 9. 1ページを最初から最後まで通す

表にまとめると何が起きているか分からなくなるので、実際の1ページをそのまま並べる。
**ここに出てくる文字列はすべて実際にコードを走らせて取ったもの**で、書き直していない。

### 題材

- ページ4／全12ページ、5コマ
- 場所: 校舎の屋上／放課後（**前のページは教室なので場面が変わる**）
- 起きること: 屋上。彼女が黙っている。彼が問い詰める。彼女は手首を掴まれる。
- 画風: モノクロ＋トーン

### 段1. コマを採寸する

キャンバス1380x2000。上に横長の断ち切り、その下に2段。
`buildPanelLayoutSummary()`がこれを作ってLLMへ渡す。

```json
{"index":1,"shape":"landscape","widthPercent":100,"heightPercent":26,"areaSharePercent":28,"bleed":true,"first":true,"last":false}
{"index":2,"shape":"square","widthPercent":48,"heightPercent":32,"areaSharePercent":17,"bleed":true,"first":false,"last":false}
{"index":3,"shape":"square","widthPercent":48,"heightPercent":32,"areaSharePercent":17,"bleed":true,"first":false,"last":false}
{"index":4,"shape":"square","widthPercent":48,"heightPercent":37,"areaSharePercent":19,"bleed":true,"first":false,"last":false}
{"index":5,"shape":"square","widthPercent":48,"heightPercent":37,"areaSharePercent":19,"bleed":true,"first":false,"last":true}
```

**この数字が判断材料になる。** コマ1は面積28%で最大かつ`landscape`かつ`first`。
コマ2と3は17%で最小。コマ5は`last`。

### 段2. LLMへ送るユーザーメッセージ

システムプロンプト（原則が書いてある側）は別途送られる。こちらはこのページ固有の情報。

```
どんな漫画か:
特定の傾向に寄せない作品です。読者がまだ知らないもの（どこか → 誰がいるか → その人物が何を感じているか）を基準に距離を決めると、ページが読み進められます。全コマが同じ距離のページは、読者が追う変化がありません。

キャラ表。そのコマのフレームに入る範囲だけ使ってください:
ミナ: short black hair, brown eyes, blazer, pleated skirt, loafers
カイ: messy brown hair, tall, gakuran, school shoes

ロケ表。この場所を写すコマには一字一句そのまま入れてください:
屋上: school rooftop, chain link fence, water tower, city skyline, overcast sky, concrete floor

これは全12ページ中の4ページ目です。
このページの場所と時間: 校舎の屋上 / 放課後
このページから新しい場面が始まります。
このページで起きること:
屋上。彼女が黙っている。彼が問い詰める。彼女は手首を掴まれる。

前のページで起きたこと（教室 / 放課後）:
教室で彼が彼女を探している。

次のページで起きること。ここへ繋げるだけで、描かないでください:
彼女が振り払って階段を駆け下りる。

コマ配置（読み順は右から左）:
[段1のJSON]
```

`このページから新しい場面が始まります。` は、前ページの`place`（教室 / 放課後）と
今ページの`place`（校舎の屋上 / 放課後）の**文字列が違う**ことから自動で入る。

### 段3. LLMが返すもの

```json
{"index":1,"role":"establishing","prompt":"no humans, school rooftop, chain link fence, water tower, city skyline, concrete floor, overcast sky, afternoon light"}
{"index":2,"role":"medium","prompt":"1boy, 1girl, messy brown hair, gakuran, short black hair, brown eyes, blazer, school rooftop, chain link fence, afternoon light, leaning forward, mouth open"}
{"index":3,"role":"closeup","prompt":"1girl, short black hair, brown eyes, frown, looking down, looking away, simple background"}
{"index":4,"role":"full","prompt":"1boy, 1girl, messy brown hair, gakuran, short black hair, blazer, pleated skirt, loafers, socks, concrete floor, school rooftop, chain link fence, afternoon light, standing, facing each other"}
{"index":5,"role":"impact","prompt":"1boy, 1girl, grabbing another's wrist, arm, hand, short black hair, blazer, emphasis lines, dutch angle, simple background"}
```

**この5コマが、どの指示からそう決まったのかを1つずつ見る。**

#### コマ1 — なぜ `establishing` で、なぜ人が居ないか

前ページが教室なので場面が変わる。読者はまだ屋上に居ることを知らない。
「読者が新しく知ることは何か」＝**どこに居るか**。だから距離は引きになる。

面積28%で最大、`landscape`、`bleed:true`。大ゴマは読者が長く留まるので広い絵に耐える。

タグは`no humans`から始まり、屋上を埋めるもの（フェンス・給水塔・スカイライン・コンクリート床）を
名指ししている。**`wide shot`とは書いていない。** それでも引きになるのは、
名指ししたものがフレームに収まりきらない大きさだから。

ロケ表の`school rooftop, chain link fence, water tower, city skyline, overcast sky, concrete floor`が
一字一句そのまま入っている。

#### コマ2 — なぜ `medium` で、なぜ靴が無いか

読者が新しく知るのは**誰が居て何をしているか**。彼が問い詰めている。

面積17%で最小のひとつ。小さいコマは一瞬で過ぎるので1つのことしか運べない。

キャラ表は`short black hair, brown eyes, blazer, pleated skirt, loafers`。
腰から上のコマなので**`blazer`までしか入っていない**。`pleated skirt`も`loafers`も無い。
入れれば、それを収めようとして絵が引く。

場所はまだ入っている（`school rooftop, chain link fence`）。読者は場所を繰り返されないと忘れる。

#### コマ3 — なぜ背景を落としてよいか

読者が新しく知るのは**彼女が何を感じているか**。答えられずにいる。顔が情報。

キャラ表は`short black hair, brown eyes`で止まっている。**服も靴も無い。**
肩から下を名指ししないから顔だけのフレームになる。

`simple background`で背景を落としている。**落としてよいのは、コマ1で既に場所を見せたから。**
1コマ目で落としていたら、読者はこのページがどこの話か分からないまま進むことになる。

#### コマ4 — なぜ全身になるか

読者が新しく知るのは**2人の距離**。離れて向かい合っている。それには足元まで要る。

タグに`loafers, socks, concrete floor, standing`が入っている。
**`full body`とは書いていない。** 足元と地面を名指ししたからフレームが下まで伸びる。

キャラ表を最後（`loafers`）まで取っているのはこのコマだけ。

#### コマ5 — なぜ見せ場になるか

`last:true`。読者がページをめくる理由を担う。次のページは「振り払って駆け下りる」なので、
掴まれた瞬間で切ればフックになる。

`grabbing another's wrist, arm, hand`で腕と手に寄り、`emphasis lines, dutch angle`で
時間を止めている。背景は落とす。

`emphasis lines`が出ているのはこのコマだけ。**指示に効果線のタグ名を書いていないから、
全コマに入らずに済んでいる**（→ 10章）。

### 段4. コマに書き込まれる最終プロンプト

`promptApplyToPanel()`が、LLMのタグに**画風タグ**と**見切れのネガティブ**を足す。
どちらも判断の余地がないので、LLMには書かせず書き込み側で固定して入れる。

**コマ1（引き）**
```
positive: no humans, school rooftop, chain link fence, water tower, city skyline,
          concrete floor, overcast sky, afternoon light,
          greyscale, monochrome, manga, screentone, halftone, high contrast
negative: out of frame, cropped, cropped legs, cropped torso, cropped arms,
          cropped shoulders, head out of frame, feet out of frame,
          foot out of frame, knees out of frame
```

**コマ3（顔だけ）**
```
positive: 1girl, short black hair, brown eyes, frown, looking down, looking away,
          simple background,
          greyscale, monochrome, manga, screentone, halftone, high contrast
negative: （コマ1と同じ）
```

**コマ4（全身）**
```
positive: 1boy, 1girl, messy brown hair, gakuran, short black hair, blazer, pleated skirt,
          loafers, socks, concrete floor, school rooftop, chain link fence, afternoon light,
          standing, facing each other,
          greyscale, monochrome, manga, screentone, halftone, high contrast
negative: （コマ1と同じ）
```

後半の`greyscale, monochrome, manga, screentone, halftone, high contrast`が画風タグ
（`storyArtStyle`で「モノクロ＋トーン」を選んだ場合）。
ネガティブは全コマ同じで、これが見切れ対策。

「生成サイズをコマの形に合わせる」をONにしていれば、ここで
コマ1に`1536x640`、コマ4に`1024x1024`が入る。

### この通しで確認できること

- **`wide shot`も`full body`も1つも出ていない。** それでも引きと全身になる
- **同じ`school rooftop, chain link fence`が3コマに一字一句同じで入っている**
- **`loafers`はコマ4にしか無い。** 顔だけのコマ・腰から上のコマには入らない
- **`simple background`はコマ3と5だけ。** 場所を見せたコマ1の後にしか出ない
- **`emphasis lines`はコマ5だけ**
- ネガティブは全コマ共通で見切れのみ

## 10. 例を書くと全コマに入れてくる

プロンプトに具体的なタグを例として並べると、**LLMはそれを使うべきタグの一覧と受け取り、
全コマに入れてくる。** 判断軸を渡すつもりが、新しい決め打ちを作ることになる。

実際に危なかったもの:

| 元の書き方 | 起きること | 直し方 |
|---|---|---|
| `{"index":1,"role":"establishing",...}`（出力形式の例） | **1コマ目がestablishingに引っ張られる** | `"role":"<role name>"` のplaceholderにする |
| 背景を落としたら `simple background` `speed lines` `emphasis lines` `motion blur` `sunburst` を使う | 寄りのコマ全部に効果線が入る | タグ名を出さず「何のために落としたかで選ぶ」と種類だけ言う |
| 場所を見せるには `buildings, sky, road, furniture, a window` | 室内の場面に `sky` `road` が入る | 「その場所に実際にあって、フレームを埋める大きさのもの」 |
| scenery: `Sky, street, window, still objects` | 同上 | 「その場所にあるもの。動きを止めて」 |
| 人数は `1girl` `1boy, 1girl` `2girls` | 全コマ `1girl` | 「そのコマに実際に居る人数を数える。前のコマから引き継がない」 |

### タグ名をプロンプトに書いてよい基準

**LLMはDanbooruの語彙を知っている。** 「〜を名指しする」と書けば適切なタグを選ぶ。
だからタグ名を書く必要があるのは、**そのタグでなければならない理由があるときだけ**。

| 書いてよい | 理由 | 例 |
|---|---|---|
| モデルが自然に選ぶタグが間違っている | 言わないと直らない | `angry` ではなく `frown`。感情の段階表 |
| 指定しないと既定値が入ってしまう | 明示が必要 | `closed mouth`（`open mouth`が343万件で勝手に入る） |
| 存在しないタグを避けさせる | 知らないと書いてしまう | `biting lip`(0件) → `frown` |
| 出力の決まりとして必要 | 判定や形式に使う | `no humans` / `solo` / 禁止する `comic` `text` など |
| 効かないと警告するために名指しする | 名前を出さないと警告にならない | `full body` `wide shot` |

| 書いてはいけない | 起きること |
|---|---|
| 「こういうものを書け」の例示 | 全コマに同じタグが入る |
| 場所・物・背景の具体例 | 場面と噛み合わないタグが入る（室内に `sky`） |

**判定の仕方**: そのタグが大半のコマに出たとき、
**それが意図通りなら書いてよい**（会話コマの `looking at another` など）。
**壊れているなら書いてはいけない**（室内の `sky`、全寄りコマの `emphasis lines`）。

加えて、プロンプト全体に効く歯止めを2つ入れている:

- 「この指示に出てくるタグはすべて**種類の例であって、選ぶべきタグではない**。
  タグがコマに入るのは、そのコマがそれを必要とするからであって、他の理由はない」
- 「答える前にコマを見渡せ。**キャラでも場所でもないタグが大半のコマに出ているなら、
  それはページを読んだ結果ではなく指示から写したもの。外せ**」

後者は自己点検なので確実ではないが、LLMが自分で気付ける形にはなっている。

---

## 11. プロンプトの書き方の決まり

LLMへ送るプロンプト本体は**すべて日本語**。英語のまま残すのはDanbooruタグそのものと、
JSONのキー・役割名だけ。翻訳調の文が混ざると、どこが指示でどこが例か読めなくなる。

**判断の余地があるものを断定で書かない。** 「見せ場の直前に静かな場面を置く」と書けば、
LLMは毎回そう書いてくる。ページも話も全部同じ構成になる。書き方は次の形にする。

```
■ 見出し

そのとき何が起きるかの説明。

よく使われる手:
・選択肢A … どういうときに効くか
・選択肢B … どういうときに効くか
外したときに何が起きるか。
```

断定してよいのは、判断の余地が無い3つだけ。プロンプト末尾の`【必ず守ること】`と
`【出力】`に集めてある。

| 断定してよいもの | 例 |
|---|---|
| 出力形式 | JSONの形、受け取ったindexすべてに1件、タグは小文字カンマ区切り |
| モデルの挙動 | フレーミングタグが効かない、感情ラベルが極端に振れる、既定が「1人・胸から膝・正面・カメラ目線」 |
| アプリの制約 | 枠と吹き出しはエディタが描く、見切れはネガティブで塞ぐ、人数タグはコマごと |

プロンプト本体はコードが正。読むときは実際の文字列を出す。

| 何を読むか | どこ |
|---|---|
| コマのプロンプト（ネーム／ストーリー共通） | `buildPanelSystemPrompt()` — llm-storyboard-service.js |
| ストーリーのページ数合わせ | `LLM_STORY_FIT_SYSTEM` — llm-story-service.js |
| キャラ表・ロケ表 | `LLM_STORY_SHEET_SYSTEM` — llm-story-service.js |
| ページ配分 | `LLM_STORY_PAGEPLAN_SYSTEM` — llm-story-service.js |
| 文章→タグ / 画像→タグ | `LLM_TEXT2PROMPT_SYSTEM` / `LLM_IMAGE2PROMPT_SYSTEM` — llm-prompt-service.js |
| セリフの推敲・翻訳 | `LLM_DIALOGUE_BASE_RULES` — llm-dialogue-service.js |
| 作品傾向（ユーザーメッセージ先頭） | `MANGA_TONE_PRESETS` — panel-composition.js |

---

## 実装の対応表

| 知見 | 入っている場所 |
|------|----------------|
| 作品傾向 → LLMの判断材料 | `MANGA_TONE_PRESETS`（panel-composition.js）→ ユーザープロンプト |
| フレーミングは要素で決まる | `buildPanelSystemPrompt()`（llm-storyboard-service.js） |
| 見切れのネガティブ | `MANGA_FRAME_NEGATIVE_DEFAULT` → `panelApplyFrameNegative()` |
| コマの形 → 解像度 | `PANEL_SDXL_BUCKETS` → `panelCompositionApplySize()` |
| 人数タグ | `LLM_STORY_SHEET_SYSTEM`（llm-story-service.js） |

書き込みは`promptApplyToPanel()`（prompt-apply.js）1か所に集約。
ネーム窓とストーリー→コマの両方がここを通る。
