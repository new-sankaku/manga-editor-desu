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
What kind of manga this is:
Nothing pulls this page in one direction. Let the distance follow what the reader still
has to learn: where they are, then who is there, then what that person feels.
A page where every panel sits at the same distance reads flat.

Character sheet. Use the parts of it that are inside the panel frame:
ミナ: short black hair, brown eyes, blazer, pleated skirt, loafers
カイ: messy brown hair, tall, gakuran, school shoes

Location sheet. Copy these word for word into every panel that shows this place:
屋上: school rooftop, chain link fence, water tower, city skyline, overcast sky, concrete floor

This is page 4 of 12.
Where and when this page happens: 校舎の屋上 / 放課後
This page opens a new scene.
What happens on this page:
屋上。彼女が黙っている。彼が問い詰める。彼女は手首を掴まれる。

What happened on the previous page (教室 / 放課後):
教室で彼が彼女を探している。

What happens on the next page. Lead into it, do not draw it:
彼女が振り払って階段を駆け下りる。

Panel layout in reading order (right to left):
[段1のJSON]
```

`This page opens a new scene.` は、前ページの`place`（教室 / 放課後）と
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

加えて、プロンプト全体に効く歯止めを2つ入れている:

- 「この指示に出てくるタグはすべて**種類の例であって、選ぶべきタグではない**。
  タグがコマに入るのは、そのコマがそれを必要とするからであって、他の理由はない」
- 「答える前にコマを見渡せ。**キャラでも場所でもないタグが大半のコマに出ているなら、
  それはページを読んだ結果ではなく指示から写したもの。外せ**」

後者は自己点検なので確実ではないが、LLMが自分で気付ける形にはなっている。

---

## 送っているプロンプトの対訳

正はコード（`buildPanelSystemPrompt()` / llm-storyboard-service.js）。
ここは読むためのもの。

**役割** — ラベルではなく「フレームに何が入るか」で定義する
- establishing: その場所。埋めているものがフレームに入る。人はいないか、小さく見える距離
- scenery: 空気・天気・時間の経過。人なし。空、通り、窓、静物
- insert: ひとつのディテール。物、手、足、目
- full: その人物の靴と、立っている地面がフレームに入る
- medium: 腰から上。足元と地面はフレームの外
- closeup: 顔。肩から下は入らない
- impact: ページで一番強い瞬間。傾いた/煽った視点。背景は落としてよい

**出力**
- JSONのみ / 受け取ったindexすべてに1件 / 小文字のDanbooru風タグをカンマ区切り
- 読者がそのコマで見る必要があるものを書いて止める。少なすぎるとモデルが勝手に埋め、
  多すぎると1つ1つが薄まってフレーミングを決めるタグまで効かなくなる
- **この指示に出てくるタグはすべて種類の例であって、選ぶべきタグではない。**
  タグがコマに入るのは、そのコマがそれを必要とするからであって他の理由はない
- **答える前にコマを見渡す。キャラでも場所でもないタグが大半のコマに出ているなら、
  ページを読んだ結果ではなく指示から写したもの。外す**

**フレーミングの作り方**（今回の中心）
- `wide shot` `full body` `upper body` `close-up` は出来上がった絵に付いたラベルであって指示ではない。
  `full body` と書いても全身にはならない
- 構図は名指ししたものに従う。欲しいフレームの端にあるものを名指しすれば、フレームはそれを収めるために広がる
- 全身にしたいなら、靴・脚・立っている床か地面を名指しする
- 顔だけにしたいなら、肩から下を一切名指ししない。靴も脚も地面も書かない。書けば勝手に引く
- 場所を見せたいなら、その場所に実際にあってフレームを埋める大きさのものを名指しし、人は出さないか遠くに置く
- フレーミングタグは補助として足してよいが、名指しした内容と矛盾しないこと。単独では働かない

**コマの仕事**（役割を決める前に）
- そのコマの仕事とは、直前のコマが読者に教えていないことのうち、そのコマが教えるもの。
  どこに居るか、誰が居るか、誰が何を感じたか、誰が何をしたか。
  先にそれを決める。距離はそこから決まり、役割はその距離の名前でしかない

**ページの緩急**
- 全コマが同じ距離の人物だと平板になる。距離は変わらなければならない
- 人のいないコマはページの隙間ではない。3つの仕事のどれかを担う。
  時間の経過を見せる / 読者に現在地を伝える / 直前のコマの余韻を保つ。
  ページがそのどれかを必要とするところに入れる。必要としないなら入れない。
  必要だったのに入れなければ、読者は次のコマで筋を見失う
- コマの大きさは読者がそこに留まる時間。大きいコマは見られるので、引きか
  ページが組み上がる一番の瞬間に耐える。小さいコマは一瞬で過ぎるので1つのことしか運べない。
  顔かディテールかリアクション。**小さいコマに引きを置くと読者には何も見えない**
- `bleed` は紙の外へ抜けるので、読者はその辺に境界を感じない。開けた絵かページの頂点向き
- `last` は読者がページをめくる理由。着地させるか、問いを残す

**背景**
- 読者は場所を見せるコマから現在地を組み立て、繰り返されなければまた忘れる。
  場所を見せるコマは場所と光（時間帯）を名指しし、同じ場所のコマは一字一句そのまま繰り返す。
  言い換えると別の場所として読まれる
- 背景を落とすのは、読者を1点に引き寄せるときか、時間を止めるとき。それは寄り・インサート・見せ場のコマ。
  **代わりに何を入れるかは、なぜ落としたかで決まる。** 孤立させたいなら空白、速さを運ぶなら流れる線、
  打つなら放射する線。毎回同じものを使うとページが機械的に見えてくる
  （タグ名を並べると全コマに入るので、種類だけ言っている → 10章）
- **そのページで場所を見せる前に落としてはいけない。** 読者にはまだそのコマの置き場所が無く、
  ページが浮いて読まれる

**ページの前後** — 渡された場所・時間と矛盾しない / 場面が変わったページは、
何かが起きる前にまず読者へ現在地を見せる / 前ページの締めの絵を繰り返さない /
次ページへ繋ぐが描かない / このページに居る根拠のない人物を出さない

**人数** — 人物が写るコマは、そのコマに実際に居る人数のDanbooru人数タグで始める。
そのコマで数える。前のコマから引き継がない。本当に1人だけのときにしか `solo` を書かない

**一貫性** — キャラ表からは**そのコマのフレームに入る範囲だけ**を取る。
顔と髪は毎回、服は身体が入るとき、靴は足が入るときだけ。
（並び順には依存させない。順番を仕様にすると、手で編集したときに黙って崩れる）
フレーム外のものを名指しすると視点がそこまで引き戻される /
ロケ表は一字一句そのまま / 与えられていない作品名・キャラ名を作らない /
`comic` `panel` `border` `speech bubble` `text` `4koma` は出さない（枠と吹き出しはアプリが描く）/
見切れについては書かない（アプリが扱う）

**作品傾向**（ユーザープロンプト先頭）— `MANGA_TONE_PRESETS`。
「どんな漫画か」の選択が説明文になって入る

### ページ配分の指示（`LLM_STORY_PAGEPLAN_SYSTEM`。ストーリー→コマの1段目）

- 読者は説明より先に、読み続ける理由を必要とする。何かが起きている状態か、
  何かが伏せられている状態で開く。読者がまだ求めていない背景説明は後でよい
- **重みはページ数。** 3ページ割いた場面は重要に読まれ、同じ場面が半ページなら
  通りすがりに読まれる。話が本当に何についてなのかにページを使い、
  ただ事実として必要なだけのところは速く通る
- どこかで話は転じる。読者が予期したことが起きなくなる地点。
  それがどのページかを決める。終わりに寄せすぎると、読者が感じる余地が残らない
- 最後のページは読者が手に持って帰るもの。1ページ目が立てた問いに答えるか、
  予期しない形で答える
- ページは読者が一度に受け取る単位で、ページの切れ目は「間」。
  1つの場面は1ページに収める。間そのものが効くところでだけ割る

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
