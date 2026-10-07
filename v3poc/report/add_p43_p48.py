"""報告のページに P43〜P48（画像生成を使わずに進めた検証）の節を足す。1回だけ流す（入れ済みなら何もしない）。
P21 の動作の判定（1-5）は P21 の節に1行足す。P22・P11 の「未検証」の書き置きを、新しい節への案内に替える。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / 'index.html'
s = p.read_text(encoding='utf-8')


def fig(path, cap):
    return f'<figure><a href="../{path}"><img src="../{path}" alt="{cap}" loading="lazy"></a><figcaption>{cap}</figcaption></figure>'


def sec(id_, h2, rows, folder, cond, body, figs=()):
    c = f'<details class="cond"><summary>条件（何を渡して何で作ったか）</summary><div class="tw"><table>{cond}</table></div></details>' if cond else ''
    f = f'<div class="figs">{"".join(fig(a, b) for a, b in figs)}</div>' if figs else ''
    return f'''<section id="{id_}">
  <h2>{h2}</h2>
  <p class="rows">一覧 {rows} ／ <code>v3poc/{folder}/</code></p>
  {c}
  {body}
  {f}
</section>
'''


NEW = [
 sec('p43', '同一キャラ判定は、似た別人を「違う」と言えるか', '3-8', 'p43_ccip',
     '<tr><th>絵</th><td>作り済みの絵だけ。P17 の a・b、P02 の眼鏡の女子生徒（寄り・上半身）、P16 の女子生徒・少年・老人、P21 の f1（短い黒髪の女子生徒）・m1（短い黒髪の男子生徒）・f2・m2</td></tr>'
     '<tr><th>判定</th><td>CCIP（imgutils）、既定の閾値0.178。全部の対で差を出し「同じ」と言った割合を数えた。切り抜きありは、人物の検出器でいちばん確かな人物を1割の余白付きで切り抜いてから比べた</td></tr>',
     '''<div class="tw"><table><tr><th>対</th><th>本当は</th><th>「同じ」の割合 切り抜きなし</th><th>切り抜きあり</th></tr>
  <tr><td>P17 a と他の全部</td><td>別人</td><td class="good">0</td><td class="good">0</td></tr>
  <tr><td>P02 の眼鏡の女子生徒と P21 f1（眼鏡なし）</td><td>別人</td><td class="bad">0.944</td><td class="bad">0.951</td></tr>
  <tr><td>P16 の少年と P21 m1（別の黒髪の男子）</td><td>別人</td><td>—</td><td class="bad">0.935</td></tr>
  <tr><td>P16 の少女と少年</td><td>別人</td><td class="bad">0.727</td><td class="bad">0.526</td></tr>
  <tr><td>P16 の少年と老人</td><td>別人</td><td>0.384</td><td class="good">0.016</td></tr>
  <tr><td>P02 と P16 の眼鏡の女子生徒（同じ言葉）</td><td>同じ</td><td>0.475</td><td class="good">0.904</td></tr>
  <tr><td>P16 の同じ人物どうし</td><td>同じ</td><td>約0.79</td><td>約0.93</td></tr></table></div>
  <div class="tw"><table><tr><th>小さい方の人物の高さ（絵の高さに対して）</th><th>対の数</th><th>少女と少年を「同じ」とした割合（切り抜きあり）</th></tr>
  <tr><td>2割未満</td><td>200</td><td class="bad">0.725</td></tr><tr><td>2〜4割</td><td>301</td><td>0.635</td></tr><tr><td>4〜7割</td><td>371</td><td>0.361</td></tr><tr><td>7割以上</td><td>28</td><td>0.107</td></tr></table></div>
  <ul><li class="bad">切り抜かないと、小さく写った人物は背景で比べる（少年と老人の差0.013）。切り抜くと同じ人物は揃うが、眼鏡の有無・性別の違う黒髪の人物は「同じ」とした。</li>
  <li>m1 と m2 の seed 53 は目で見ても似ていて、別人かは決めきれない。</li>
  <li>「違う」と言ったら落とす使い方はできる。「同じ」だけで通すと別人が通る。</li></ul>''',
     [('p43_ccip/out/sheet_pairs_crop.png', '切り抜きありで「同じ」とした別の組の対（差が小さい順）')]),
 sec('p44', '人物の枠の大きさで、寄り・全身・引きを分けられるか', '3-11', 'p44_distance',
     '<tr><th>合わせる絵</th><td>P02 の目で合格の29枚（顔・上半身・全身・引き）で、人物の高さ・人物の面積・顔の高さの閾値を合わせた</td></tr>'
     '<tr><th>試す絵</th><td>P16 の71枚（全身27・引き44）、P15 の34枚（全身11・引き23）。どれも目で合格の絵</td></tr>',
     '''<div class="tw"><table><tr><th>測る物</th><th>合わせた絵</th><th>P16 全身</th><th>P16 引き</th><th>P15 全身</th><th>P15 引き</th></tr>
  <tr><td>人物の面積</td><td>28/29</td><td class="bad">0/27</td><td>44/44</td><td class="bad">0/11</td><td>23/23</td></tr>
  <tr><td>顔の高さ</td><td>27/29</td><td class="bad">0/27</td><td>44/44</td><td class="bad">0/11</td><td>23/23</td></tr>
  <tr><td>人物の高さ</td><td>20/29</td><td class="bad">0/27</td><td>44/44</td><td class="bad">0/11</td><td>23/23</td></tr></table></div>
  <ul><li class="bad">余白のある全身は全部「引き」になった。P16 の中で閾値を選び直しても、人物の高さで71枚中58、面積で55、顔で54まで。全身と引きの大きさの分布が重なる。</li>
  <li>画像を見た LLM の距離の判定（3-19）は59枚中56枚で、枠の大きさより合う。</li></ul>'''),
 sec('p45', '斜めのコマを含む割りの読む順を、画像を見た LLM が当てられるか', '3-17', 'p45_diag_order',
     '<tr><th>割り</th><td>台形・三角のコマを含む8種を線で描いた（番号なし）。正解は右から左・上から下で私が付けた順</td></tr>'
     '<tr><th>聞き方</th><td>P11 と同じ（コマの中心の座標を読む順に並べる）に「枠の辺が斜めのコマもあります」を足した。Sonnet・Opus で各2回、計32回</td></tr>',
     '''<p class="good">Sonnet 16/16、Opus 16/16。8種すべてで2回とも当てた。</p>
  <ul><li>四角いコマの P11（Sonnet 16/16、Opus 14/16）と合わせ、読む順の判定を画像から LLM に任せても外れは少ない。ただし、どれも右から左・上から下で迷いの少ない割り。人でも迷う割りは P11 の2つだけ。</li></ul>''',
     [('p45_diag_order/out/sheet.png', '試した8種の割り')]),
 sec('p46', '話をまたいだ伏線の回収漏れと食い違いを、LLM が見つけられるか', '5-22', 'p46_foreshadow',
     '<tr><th>台本</th><td>4話・22行（<code>script.json</code>）。回収されない伏線2つ、回収が前の描写と食い違う物2つ（取り壊された灯台に上る、一枚しかない地図をもう一人が持つ）、きちんと回収される伏線3つ、日常の行。一部だけ回収される伏線（転校生の言いよどみ）を境目として1つ</td></tr>'
     '<tr><th>聞き方</th><td>A 問題のある行だけ挙げる／B 伏線に見える行を全部並べ、回収済み・未回収・食い違いを付ける。Sonnet・Opus で各2回</td></tr>',
     '''<div class="tw"><table><tr><th>モデル・聞き方</th><th>見つけた（4つ中）</th><th>境目の伏線</th><th>回収済みの行を挙げた</th></tr>
  <tr><td>Sonnet A</td><td class="good">4・4</td><td>0・0</td><td>0・0</td></tr>
  <tr><td>Sonnet B</td><td class="good">4・4</td><td>0・0（回収済みとした）</td><td>0・1</td></tr>
  <tr><td>Opus A</td><td class="good">4・4</td><td>0・0</td><td>0・1</td></tr>
  <tr><td>Opus B</td><td class="good">4・4</td><td>0・0（回収済みとした）</td><td>0・1</td></tr></table></div>
  <ul><li>回収されない伏線と、前と食い違う回収は、8回とも全部見つけた。</li>
  <li class="bad">一部だけ回収された伏線は8回とも挙げなかった。</li>
  <li>回収済みの行を挙げた3回は、どれも手紙の「二人の子」のもう一人が書かれていない点を突いた。台本の書き方の穴で、誤りとは言い切れない。</li>
  <li>台本は私が作った短い物。長い連載で同じように見つかるかは未検証。</li></ul>'''),
 sec('p47', '吹き出しが顔を隠したことを、仕上がった絵だけから見つけられるか', '3-15', 'p47_balloon_face',
     '<tr><th>絵</th><td>P02 の全身以外の91枚。顔が見つかった81枚に、白い楕円の吹き出し（文字の代わりに縦の線）を横にずらして重ね、顔の枠が隠れる割合を0〜100%の6段にした</td></tr>'
     '<tr><th>判定</th><td>重ねた絵で顔の検出器（imgutils、確かさ0.3以上）を回し、元の顔の枠と重なる顔が見つかるか</td></tr>',
     '''<div class="tw"><table><tr><th>顔の枠が隠れた割合</th><th>0%</th><th>20%</th><th>40%</th><th>60%</th><th>80%</th><th>100%</th></tr>
  <tr><td>顔が見つかった（81枚中）</td><td>81</td><td>79</td><td class="bad">76</td><td>27</td><td>0</td><td>0</td></tr></table></div>
  <ul><li>吹き出しを置く側は重ねる前の顔の位置を知っているので、隠れは重なりの計算で分かる。</li>
  <li class="bad">重ねた後の絵だけからは、顔の4割を隠しても顔が見つかるので、隠れたと言えない。取り込んだページ・平らにした絵では使えない。</li>
  <li>元の絵で顔が見つからなかったのが91枚中10枚。この絵は重なりの計算もできない。</li></ul>''',
     [('p47_balloon_face/out/sheet.png', '隠れた割合ごとの例（found は顔が見つかった、lost は見つからない）')]),
 sec('p48', 'MagiV2 は、カラーの絵と人のいない背景で人数を当てられるか', '3-6', 'p48_magi_color',
     '<tr><th>絵</th><td>P15 の4つの描き方（カラー・ペン・レトロ・トーン）× 人物あり4種・背景だけ3種 × 3枚。P16 の人のいない背景18枚。P18 の教室・街の背景66枚。計168枚</td></tr>'
     '<tr><th>判定</th><td>MagiV2（<code>v3poc/common/magi.py</code>）。読み込むときに白黒にしてから見る</td></tr>',
     '''<div class="tw"><table><tr><th>絵</th><th>人物あり（1人）</th><th>人のいない背景（0人）</th></tr>
  <tr><td>カラー</td><td class="good">12/12</td><td class="good">9/9</td></tr>
  <tr><td>ペン</td><td>11/12</td><td>9/9</td></tr><tr><td>レトロ</td><td>10/12</td><td>9/9</td></tr><tr><td>トーン</td><td>12/12</td><td>7/9</td></tr>
  <tr><td>P16 の背景</td><td>—</td><td>15/18</td></tr><tr><td>P18 の背景</td><td>—</td><td class="good">66/66</td></tr></table></div>
  <ul><li>カラーの絵で落ちることはなかった。</li>
  <li class="bad">外れは、看板や赤い電話ボックスを人物とした物（人物ありの3枚、背景1枚）と、草むらの大きな範囲を人物とした物（P16 の3枚）。</li>
  <li class="bad">トーンの縦長の背景の1枚は、絵そのものが4つのコマに分かれたページになっていた（生成の失敗）。MagiV2 はそのコマを人物とした。</li></ul>''',
     [('p48_magi_color/out/sheet_wrong.png', '人数を外した8枚（赤い枠が人物とした所）')]),
]

if 'id="p43"' not in s:
    s = s.replace('<section id="src">', ''.join(NEW) + '<section id="src">', 1)
    s = s.replace('<a href="#src">出典</a>', '<a href="#p43">別人の判定</a><a href="#p44">距離</a><a href="#p45">斜めのコマ</a><a href="#p46">伏線</a>'
                  '<a href="#p47">顔を隠す</a><a href="#p48">カラーと0人</a><a href="#src">出典</a>', 1)
    s = s.replace('<li>吹き出しが顔を隠しているかは未検証。</li>', '<li>吹き出しが顔を隠しているかは <a href="#p47">P47</a>。</li>', 1)
    s = s.replace('斜めのコマは未検証。</li>', '斜めのコマは <a href="#p45">P45</a>。</li>', 1)
    s = s.replace('<li>頼んでいない文字が72枚中10枚。</li></ul>', '<li>頼んでいない文字が72枚中10枚。</li>'
                  '<li>動作（1-5）：72枚中71枚が指示どおり（外れは腰に手が太ももに手になった1枚）。手を振るが後ろ姿になったのが12枚中2枚、片手だけが1枚。m2 は seed ごとに別人（年配・金髪の年配・若い）。</li></ul>', 1)
    p.write_text(s, encoding='utf-8')
    print('added')
else:
    print('already')
