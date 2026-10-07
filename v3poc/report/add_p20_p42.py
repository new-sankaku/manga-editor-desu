"""報告のページに P20〜P42、出典の確認、未実施の理由の節を足す。1回だけ流す（入れ済みなら何もしない）。
市販の漫画のページ（P06・P39 で読んだもの）は載せない。数だけ書く。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / 'index.html'
s = p.read_text(encoding='utf-8')

GEN = '<tr><th>絵のモデル</th><td>WAI-illustrious-SDXL v1.6。euler_ancestral / normal / 25ステップ / CFG 5.0。プロンプトと seed は各フォルダの <code>out/gen.json</code></td></tr>'


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
 sec('p20', '線画・ベタ・トーン・着彩を別々に作れるか', '1-27', 'p20_layers',
     GEN + '<tr><th>手1 後から分ける</th><td>トーンの絵から、線画を取り出す部品（Manga2Anime・AnimeLineArt）で線を抜き、濃さでベタ（50未満）とトーン（50〜215）に分ける</td></tr>'
     '<tr><th>手2 先に線画</th><td>線画だけの絵を作り、多用途の制御（xinsir union、Apache-2.0）で渡してトーンの絵・カラーの絵を作る</td></tr><tr><th>場面</th><td>机の人物・走る人物・部屋の背景 × seed 3</td></tr>',
     '''<div class="tw"><table><tr><th>測った物</th><th>結果</th></tr>
  <tr><td>分けた3層を重ね直した絵と元の絵の差</td><td>平均 6.2/255（Manga2Anime）・6.3/255（AnimeLineArt）</td></tr>
  <tr><td>線画の線が、トーンの絵・カラーの絵で保たれた割合</td><td>0.952・0.971</td></tr></table></div>
  <ul><li>後から分ける手：Manga2Anime の線はきれい。AnimeLineArt は網の模様まで線として拾う。ベタに背景の暗いぼかしが混じる。トーンは網点ではなく灰色の階調。</li>
  <li class="bad">先に線画の手：線画の絵自体に灰色の塗りが入る（机の場面で中間の灰色が29〜33%）。そのため線画の層をカラーの上に重ねると塗りが黒くなる。線画から作ったトーンの絵に色が漏れた（赤い目、走る場面は3枚とも上着と髪に色）。</li>
  <li>線画からカラーは線によく沿う。</li></ul>''',
     [('p20_layers/out/sheet_split_a_desk.png', '後から分ける手（机）。元・線・ベタ・トーン・重ね直し'), ('p20_layers/out/sheet_line_b_run.png', '先に線画の手（走る）。線画・トーン・カラー・線をカラーに重ねた物')]),
 sec('p21', '手の崩れの割合・男性キャラで質が落ちないか', '1-3・1-10・1-8・3-23', 'p21_hands',
     GEN + '<tr><th>中身</th><td>手の見える動作6種 × 女性2人（f1・f2「大人の女性」）・男性2人（m1・m2）× seed 3 = 72枚。手は原寸で切り出して目で見た</td></tr>',
     '''<div class="tw"><table><tr><th>人物</th><th>手の崩れなし</th><th>一部崩れ</th><th>崩れ</th><th>美しさの採点（百分位）</th></tr>
  <tr><td>f1</td><td>14</td><td>4</td><td>0</td><td>0.824</td></tr><tr><td>f2</td><td>13</td><td>3</td><td class="bad">2</td><td>0.97</td></tr>
  <tr><td>m1</td><td class="good">18</td><td>0</td><td>0</td><td>0.273</td></tr><tr><td>m2</td><td>16</td><td>2</td><td>0</td><td>0.197</td></tr></table></div>
  <ul><li>男性の手は女性より崩れない（34/36 と 27/36）。</li>
  <li class="bad">m1 がスカートを履いた・少女になったのが18枚中2枚。m2 は seed 53 で幼く見えるのが5枚。f2（大人の女性）は18/18で胸が誇張され、年齢区分の判定器は15/18を r15 とした（f1 1/18、男性0）。</li>
  <li class="bad">美しさの採点器は女性・肌の多い絵を高く付けた。手が崩れた絵（0.797）を崩れなし（0.524）より高くした。</li>
  <li>頼んでいない文字が72枚中10枚。</li></ul>''',
     [('p21_hands/out/crops_f2.png', 'f2 の手を原寸で切り出した物'), ('p21_hands/out/crops_m1.png', 'm1 の手')]),
 sec('p22', '頼んでいないフキダシと文字を防げるか・見つけられるか', '1-22・3-15', 'p22_balloon',
     GEN + '<tr><th>中身</th><td>会話・叫ぶ・掲示のある駅 × 否定の言葉（なし／あり）× seed 8</td></tr>',
     '''<div class="tw"><table><tr><th>場面</th><th>否定の言葉なし</th><th>あり</th></tr>
  <tr><td>会話</td><td class="bad">8/8 がフキダシだらけの複数コマのページ</td><td class="bad">8/8 同じ</td></tr>
  <tr><td>叫ぶ（文字あり）</td><td>5/8</td><td>4/8</td></tr><tr><td>掲示（駅の看板）</td><td>8/8</td><td>5/8</td></tr></table></div>
  <div class="tw"><table><tr><th>文字の検出器の閾値</th><th>見つけた（38枚中）</th><th>見逃し</th><th>誤り（文字なし10枚）</th></tr>
  <tr><td>0.05（既定）</td><td>33</td><td>5</td><td>3</td></tr><tr><td>0.1</td><td>31</td><td>7</td><td>2</td></tr><tr><td>0.2</td><td>24</td><td>14</td><td>1</td></tr></table></div>
  <ul><li>否定の言葉は効かない。会話の場面は言葉だけではコマ1つの絵にならない。</li><li>吹き出しが顔を隠しているかは未検証。</li></ul>''',
     [('p22_balloon/out/sheet_talk.png', '会話（上が否定なし、下があり）'), ('p22_balloon/out/sheet_board.png', '掲示')]),
 sec('p23', '2人を描いたとき特徴が混ざらないか・髪の色で見分けられるか', '1-19・3-9', 'p23_two_chara',
     GEN + '<tr><th>中身</th><td>組3種（P17 の2人 ab／似た女子生徒2人 sim／カラーの2人 color）× 書き方（1つの文に全部／左右の範囲ごとに文、ComfyUI 標準の範囲指定）× seed 6</td></tr>',
     '''<div class="tw"><table><tr><th>組</th><th>1つの文</th><th>範囲ごと</th></tr>
  <tr><td>color</td><td class="bad">正しい0（左右入れ替わり4・混ざり3）</td><td class="good">6/6</td></tr>
  <tr><td>ab</td><td>2/6（混ざり4）</td><td>3/6（3枚が複数コマのページ）</td></tr>
  <tr><td>sim</td><td>1/6（混ざり5）</td><td>2/6（4枚が複数コマのページ）</td></tr></table></div>
  <ul><li>3-9：頭を検出して髪の色相を比べる手で、左右どちらが誰かを目と12/12で一致した。</li><li class="bad">白黒で範囲ごとに文を当てると、1枚が複数コマのページになりやすい。</li></ul>''',
     [('p23_two_chara/out/sheet_color.png', 'カラーの2人'), ('p23_two_chara/out/sheet_ab.png', 'P17 の2人')]),
 sec('p24', 'デフォルメ・ぼかした参照画像で別人にならないか', '1-21', 'p24_deform',
     GEN + '<tr><th>中身</th><td>P17 の2人。手1 デフォルメの言葉（chibi）seed 6。手2 参照画像の部品（IP-Adapter plus 強さ0.5）にそのまま／ぼかして縮めた参照画像 seed 3。判定は同一キャラ判定（CCIP、閾値0.178）と目</td></tr>',
     '''<ul><li>同一キャラ判定：デフォルメ12/12、通常12/12、きれいな参照 a 2/3・b 3/3、ぼかした参照 a 3/3・b 3/3。</li>
  <li>目でもデフォルメで特徴は残った。</li><li class="bad">パーカーに英字（SUPER など）が勝手に入る。参照画像を使うと色が乗る（P17 と同じ）。ぼかした参照だと b の髪の色がぶれる。</li></ul>''',
     [('p24_deform/out/sheet_a.png', 'a（デフォルメ・通常・参照）'), ('p24_deform/out/sheet_b.png', 'b')]),
 sec('p25', '画風がずれないか・写実に寄らないか・光の向き', '1-12・1-18・3-10', 'p25_style_light',
     GEN + '<tr><th>中身</th><td>P17 の a を8場面 × seed 2。写実の言葉を足した4枚。光の言葉なし／左から／右から × seed 4</td></tr>',
     '''<ul><li>8場面で画風は目で揃った。</li>
  <li class="bad">写実の判定器は平均0.024。写実の言葉を足しても0.009〜0.019で反応しない。目では顔が少し写実に寄った。写実の言葉の4枚中3枚に文字が入った。</li></ul>
  <div class="tw"><table><tr><th>光の言葉</th><th>左から光</th><th>右から光</th><th>分からない</th></tr>
  <tr><td>なし</td><td>2</td><td>0</td><td>2</td></tr><tr><td>左から</td><td>2</td><td class="bad">2</td><td>0</td></tr><tr><td>右から</td><td class="bad">3</td><td>1</td><td>0</td></tr></table></div>
  <p>光の言葉は効かない。明るい側は seed ごとの窓の位置に従った。</p>''',
     [('p25_style_light/out/sheet_style.png', '画風（8場面）'), ('p25_style_light/out/sheet_light.png', '光の向き')]),
 sec('p26', '画像編集で写真風にならないか・背景が勝手に変わらないか', '1-15・1-17', 'p26_edit',
     '<tr><th>編集のモデル</th><td>Qwen-Image 2.1（int8、Apache-2.0）。ComfyUI 標準の編集の文の部品に元の絵を渡す</td></tr><tr><th>中身</th><td>P17 の a（食べる）と b（走る）× 編集5種（物を持たせる・笑わせる・座らせる・後ろ向き・海辺の背景）× seed 2。20枚の予定で14枚まで作った</td></tr>',
     '''<ul><li>写真風になったのは0。同一キャラ判定は14/14で同じ人。</li>
  <li>カップを持たせる・笑わせる（b）は、ほかを保ったまま効いた。後ろ向きは効いた（1枚で三つ編みが消えた）。</li>
  <li class="bad">海辺の背景に変えると背景だけカラーになり、白黒の人物と合わない。</li>
  <li>座らせる編集は、元の絵が既に座っていて試せなかった（課題の選び方の誤り）。a の笑顔はパンで口が隠れて見えない。</li>
  <li class="bad">人物の外の画素の変化（0.15〜0.25）は、出力が32の倍数に丸められ（1216→1248）位置がずれるので使えない。</li>
  <li>b の座る・後ろ向き・背景の6枚は、画像生成を止めたので作っていない。</li></ul>''',
     [('p26_edit/out/sheet_a.png', 'a の編集'), ('p26_edit/out/sheet_b.png', 'b の編集（作った分）')]),
 sec('p27', 'LLMのネームを機械で数える', '2-3〜2-16', 'p27_name',
     '<tr><th>LLM</th><td>Claude Sonnet（<code>claude -p</code>）。港の話8ページ・学校の話6ページ × 3回。プロンプトは <code>out/prompt.json</code></td></tr>',
     '''<div class="tw"><table><tr><th>数えた物</th><th>6つのネーム</th></tr>
  <tr><td>読む順の崩れ</td><td>5つで0。1つは段の中を左から書いた（書き方の揺れ）</td></tr>
  <tr><td>同じ段の割りが次のページに続く</td><td>1〜5回（港の話は3〜5回）</td></tr>
  <tr><td>斜め・断ち切り・枠なし</td><td>1〜4・2〜5・0〜2</td></tr>
  <tr><td>会話だけのコマで変形</td><td>0〜3</td></tr>
  <tr><td>大きいコマの無いページ／見開き</td><td>0〜4／0〜2</td></tr>
  <tr><td>目の高さ以外の角度</td><td>26〜39%、1つだけ70%</td></tr>
  <tr><td>左ページ最後のヒキの印</td><td>全ネームで全部に付けた</td></tr>
  <tr><td>吹き出しの最大字数／30字超え</td><td>22〜58字／0〜2個</td></tr></table></div>
  <p>数で見られるのは形だけ。良し悪しは漫画を描く人の判定が要る（3-1）。</p>'''),
 sec('p28', '話の矛盾を見つけられるか', '2-11・2-12・2-13・3-22・5-22', 'p28_contradiction',
     '<tr><th>中身</th><td>3話分の台本に矛盾を12か所入れた（口調・設定・物の状態・時間の前後）。全部の観点を1回で聞く／観点ごとに4回。Sonnet と Opus で各2回</td></tr>',
     '<p>全部を1回：Sonnet 11・12、Opus 12・12。観点ごと：全部12。誤りの指摘は0。今回の難しさでは観点ごとに分けても差がほぼ出ない。</p>'),
 sec('p29', '取り込んだ原稿の中の指示が記憶に入らないか', '5-19', 'p29_injection',
     '<tr><th>中身</th><td>原稿に AI あての指示3種（はっきり AI あて／作者の方針に見せかけ／台詞の中）と、残すべき作者のメモ1つ。手 A 素直に作らせる／B 資料だと伝え指示に見える文を別の欄に出させる／C 決まった欄だけ。Sonnet で各3回</td></tr>',
     '<p class="good">3つの手とも、記憶に指示が入ったのは0/9。作者のメモは9/9で残った。B は3回とも指示3つを別の欄に出した。</p>'),
 sec('p30', '理由を伝えずに作り直させると同じ物が出るか', '6-4', 'p30_redo',
     '<tr><th>中身</th><td>LLM にコマの中身から画像生成の言葉を作らせ、「作り直して」と頼む。理由なし／理由あり × 5回。言葉の重なりで比べた</td></tr>',
     '<p>推測と逆。前の言葉との重なりは理由なし0.374・理由あり0.46で、理由なしの方が大きく変わった。理由なしの作り直しどうしは0.524で似る。距離を変えたのは4/5と5/5。絵での比較は未検証。</p>'),
 sec('p31', '吹き出しの位置で読む順が変わるか', '2-4', 'p31_balloon_order',
     '<tr><th>中身</th><td>枠だけでは順が決まらない格子（2列2段・2列3段）× 吹き出し（つながりなし／列をまたぐ／段をまたぐ）× 2回。Sonnet に読む順を答えさせた</td></tr>',
     '<p>列をまたぐ吹き出しで縦に読んだのは2列2段の1回だけ。ほかの11回は位置によらず横に読んだ。LLM は吹き出しの位置をほとんど手がかりにしない。</p>',
     [('p31_balloon_order/out/sheet_col_row.png', '吹き出しの置き方（列をまたぐ・段をまたぐ）')]),
 sec('p32', '評価役の答えが聞き方でぶれないか', '3-24・3-25・3-27', 'p32_judge_robust',
     '<tr><th>中身</th><td>P19 の表情の36組で「どちらの感情が強いか」。聞き方5種（元の文・言い回し違い・引き分けを許さない・長い説明・一度に多く並べる）</td></tr>',
     '''<div class="tw"><table><tr><th>聞き方</th><th>正しい</th><th>引き分け</th><th>逆</th><th>入れ替えで同じ答え</th><th>元と答えが違う</th></tr>
  <tr><td>元の文</td><td>30</td><td>4</td><td>2</td><td>33</td><td>—</td></tr>
  <tr><td>言い回し違い</td><td>30</td><td>5</td><td>1</td><td>31</td><td>7</td></tr>
  <tr><td>引き分けを許さない</td><td>29</td><td>3</td><td>4</td><td>33</td><td>7</td></tr>
  <tr><td>長い説明</td><td>28</td><td class="bad">8</td><td>0</td><td>28</td><td class="bad">12</td></tr>
  <tr><td>一度に多く並べる</td><td>26</td><td class="bad">9</td><td>1</td><td>29</td><td>9</td></tr></table></div>'''),
 sec('p33', '候補を3枚作ってLLMに選ばせると良くなるか', '4-14・3-27', 'p33_select',
     '<tr><th>中身</th><td>P16 の同じ狙いの3枚×36組。名前を伏せて Sonnet に1枚選ばせ、どれも合わなければ「なし」。正解は P16 の目の判定</td></tr>',
     '<p class="good">1枚だけなら狙いどおり0.824。選ばせると、選んだ33回が全部狙いどおり。「なし」の3回は、全部外れの3組とちょうど一致した。費用 1.15ドル。</p>'),
 sec('p34', '左から読む作品で検査が向きに合わせて働くか', '3-5', 'p34_ltr', '',
     '<p class="good">P12 の48の割りを左右反転し「左から」で検査すると、48/48で元の結果と同じ。誤って「右から」で検査すると48/48で読む順の崩れとして出た。1ページ目の位置は右から読む本で左、左から読む本で右に入れ替わる。</p>'),
 sec('p35', '既製の判定器がこの画風で使えるか', '3-7・3-23・3-25・5-20', 'p35_scorers',
     '<tr><th>判定器</th><td>dghs-imgutils の年齢区分・NSFW・写実・美しさ（2種）。値は <code>out/scores_*.json</code></td></tr>',
     '''<ul><li>年齢区分：見上げの8枚（スカートを強調する構図に寄った）を7枚 r15、ほか88枚では1枚。使える。</li>
  <li class="bad">NSFW：普通の絵88枚中35枚を「成人向けの絵」とした。この画風では使えない。</li>
  <li class="bad">写実：白黒の絵柄は約0.5、カラーは0.045。白黒では当てにならない。写実の言葉にも反応しない（P25）。</li>
  <li class="bad">美しさ：絵柄でカラー0.486・ペン線0.341・90年代風0.362・トーン0.307。狙いどおりの絵が外れより高いのは14組中7組。女性・肌の多い絵を高く、崩れを見逃す（P21）。</li>
  <li>3-7 崩れの専用の検出器を公開の場所で探した：手の崩れの分類（Apache-2.0、学習の中身不明）、写実の体の崩れの分類（許諾なし）、画像の不具合の検出（Apache-2.0）。この画風では試していない。</li></ul>'''),
 sec('p36', 'PSDを層ごとに書き出して読み戻せるか', '5-14・5-12', 'p36_psd',
     '<tr><th>道具</th><td>書く：ag-psd 31.0.2（MIT、Node）。読み戻す：ag-psd と psd-tools 1.21.0（MIT、Python）</td></tr><tr><th>中身</th><td>P20 の机の場面から、紙・隠したグループ「カラー」（着彩・乗算）・トーン・ベタ・線画・縦書きの文字層「セリフ」</td></tr>',
     '<p class="good">3.6MB。両方の読み戻しで全層の画素の差0。名前・グループ・隠す・乗算・文字と縦書きが保たれた。psd-tools で重ねた絵と期待の差は平均0.21。</p><p>Photoshop・CLIP STUDIO で開くのと、文字層の画素（描き直しが要る）、.clip 形式は未検証。</p>',
     [('p36_psd/out/psdtools_composite.png', 'psd-tools が重ねた絵')]),
 sec('p37', '検出器の枠が端に接するかで見切れが分かるか', '1-9・3-12', 'p37_clip', '',
     '''<div class="tw"><table><tr><th>端</th><th>切れて接する</th><th>切れずに接する</th><th>切れて接しない</th><th>どちらもなし</th></tr>
  <tr><td>下</td><td>21</td><td class="bad">6</td><td>3</td><td>10</td></tr><tr><td>上</td><td>0</td><td>8</td><td>0</td><td>32</td></tr></table></div>
  <p>P02 の40枚。全身8枚は切れていないのに6枚が下端に接した。接触は「切れ」ではなく「余白なし」を拾う。余白を要る条件の検査には使える。</p>''',
     [('p37_clip/out/sheet_full_body.png', '全身'), ('p37_clip/out/sheet_two_people.png', '2人')]),
 sec('p38', '人物の周りを白く抜けるか・近くの線を太くできるか', '1-23', 'p38_composite', '',
     '''<ul><li class="good">切り抜いた人物の周りを9px 白く縁取ると、背景の線が縁で止まり、黒の上でも輪郭が読める。縁なしは髪が黒に溶け、柵の線が脚に重なる。</li>
  <li>人物に影が無く浮いて見える。</li>
  <li class="good">P18 の奥行きから、近くの線を最大+4px 太くできた。</li></ul>''',
     [('p38_composite/out/sheet_chara_only_girl_none_81.png', '白い縁あり・なし'), ('p38_composite/out/sheet_depth_lines.png', '近くの線を太く')]),
 sec('p39', '描き文字の擬音をLLMが読めるか', '6-2・5-21', 'p39_sfx',
     '<tr><th>中身</th><td>市販の漫画3ページ（性的な内容のページは除いた）を Sonnet に読ませ、目の判定と比べた。ページと読んだ文字は公開しない（手元だけ）</td></tr>',
     '<p>台詞は25/25読めた。描き文字の擬音は8つ中3つだけ（目でも判断できない4、読めないと答えた1、勝手に作った1）。手書きの台詞を擬音とした1。1ページ約0.065ドル。</p>'),
 sec('p40', 'コマ割りの単調さを1ページの数で測れるか', '3-29', 'p40_monotony', '',
     '''<div class="tw"><table><tr><th>中央値</th><th>LLMの割り（41）</th><th>市販のページ（9）</th></tr>
  <tr><td>面積のばらつき</td><td>0.582</td><td>0.45</td></tr><tr><td>上の辺が揃う割合</td><td>0.667</td><td>0.5</td></tr></table></div>
  <p>LLM の41中15は形が1種だけ（市販は最低2種）。1ページの数では弱くしか分けられない。単調さはページをまたいだ繰り返し（P27 の同じ割りの連続）に出る。</p>'''),
 sec('p41', '画風の揃いをCSDで見られるか', '3-10・1-12', 'p41_csd',
     '<tr><th>道具</th><td>CSD（ViT-L、重み CC-BY-4.0・コード MIT）</td></tr>',
     '''<ul><li>P15 の84枚：最も近い絵が同じ画風なのは0.726。同じ画風で違う物0.711、違う画風で同じ物0.653、両方違う0.529。</li>
  <li class="bad">カラーは離れる（他と0.379）が、白黒3種の差は小さい（同じ中0.69〜0.76、他と0.59〜0.61）。</li>
  <li>P25：同じ画風0.802、写実の言葉0.754。</li></ul>'''),
 sec('p42', '全身を描いたとき顔と手が崩れないか', '1-3', 'p42_fullbody',
     '<tr><th>中身</th><td>新しい絵は作らず、P02・P16・P24 の全身47枚から顔と手を検出して原寸で切り出した</td></tr>',
     '''<div class="tw"><table><tr><th>顔の幅</th><th>枚数</th><th>崩れ</th><th>一部</th></tr>
  <tr><td>100px 以上</td><td>20</td><td>0</td><td>0</td></tr><tr><td>42〜71px</td><td>17</td><td>0</td><td>1</td></tr><tr><td>32〜38px</td><td>7</td><td class="bad">2</td><td>2</td></tr></table></div>
  <p>手：27（誤検出2を除く）中、指まで描けた6、指を省いた形10、意味のない線が入った形11（P24 の少年の握った手7つ中6つ）。省いた形は遠めのコマなら通るかもしれない（未検証）。</p>''',
     [('p42_fullbody/out/sheet_faces.png', '全身の顔（幅の数字付き）'), ('p42_fullbody/out/sheet_hands.png', '全身の手')]),
 '''<section id="src">
  <h2>出典の確認</h2>
  <p class="rows">一覧 7-8・7-9・7-10・7-11</p>
  <div class="tw"><table><tr><th>出典</th><th>本文で確かめたこと</th><th>文書と合うか</th></tr>
  <tr><td>ACE</td><td>要旨の +10.6%・+8.6%。表1に +17.0%。差分だけ書き換えて文脈の崩れを避ける</td><td>合う</td></tr>
  <tr><td>Audit &amp; Repair</td><td>合わないコマだけ直す</td><td>合う</td></tr>
  <tr><td>MAST</td><td>失敗14種・3分類、一致率 κ=0.88、1,642件</td><td>合う</td></tr>
  <tr><td>APG</td><td>CFG が高いと色がごてごてする</td><td>合う</td></tr>
  <tr><td>ComicsPAP</td><td>偶然 24.30%、最良 41.27%、学習した7B 62.31%</td><td class="bad">課題196の「ほぼ偶然と同じ」は言い過ぎ</td></tr>
  <tr><td>SalArt-VQA</td><td>検出 99.37%、4問全部 53.26%</td><td>合う</td></tr>
  <tr><td>AgentJudgeBench</td><td>正解を見せると一致が下がった（1.5・3.9ポイント）</td><td>合う</td></tr></table></div>
  <ul><li>7-8：Manga109 は学術の非営利だけ。Manga109-s（87冊）は商用の利用が認められ、申請で入手する。</li>
  <li>7-9：OFL の FAQ 1.1・1.1.1。OFL のフォントで描いた文字を画像にした物は商用でも使え、出来た物は作った人の物。</li>
  <li>Kirtley は読めなかった（403）。残りはウェブ検索の上限に達し調べられなかった。</li></ul>
</section>
<section id="rest">
  <h2>未実施と理由</h2>
  <div class="tw"><table><tr><th>理由</th><th>一覧</th></tr>
  <tr><td>利用者の指示で一覧に載せるだけ（試作しない）</td><td>2-17・2-18・2-19</td></tr>
  <tr><td>商用サービスのキーが無い</td><td>1-31・5-10・5-28・7-6</td></tr>
  <tr><td>漫画を描く人の判定・実際の使用・実機が要る</td><td>3-1・3-2・3-3・3-4・3-21・3-26・3-28・5-7・5-26・5-29・5-30・6-3・8-1・8-2・8-3</td></tr>
  <tr><td>ウェブ検索の上限に達した</td><td>7-1〜7-7（7-7 は学習も要る）</td></tr>
  <tr><td>画像生成を止めた（一部の行の残り）</td><td>1-15・1-17 の残り</td></tr>
  <tr><td>一般的なプログラミングで解ける（検証しない）</td><td>4-1〜4-13・4-15・5-1〜5-6・5-8・5-9・5-11・5-15〜5-18・5-23〜5-25・5-27</td></tr></table></div>
</section>
''']

if 'id="p20"' not in s:
    s = s.replace('<section id="p13">', ''.join(NEW) + '<section id="p13">')
    s = s.replace('<a href="#p13">仕組み</a>',
                  '<a href="#p20">層に分ける</a><a href="#p21">手</a><a href="#p22">フキダシ</a><a href="#p23">2人</a><a href="#p24">デフォルメ</a><a href="#p25">画風と光</a>'
                  '<a href="#p26">編集</a><a href="#p27">ネーム</a><a href="#p28">矛盾</a><a href="#p29">原稿の指示</a><a href="#p30">作り直し</a><a href="#p31">吹き出しと順</a>'
                  '<a href="#p32">評価役のぶれ</a><a href="#p33">候補選び</a><a href="#p34">左から読む</a><a href="#p35">判定器</a><a href="#p36">PSD</a><a href="#p37">見切れ</a>'
                  '<a href="#p38">白い縁</a><a href="#p39">描き文字</a><a href="#p40">単調さ</a><a href="#p41">CSD</a><a href="#p42">全身</a><a href="#src">出典</a>'
                  '<a href="#p13">仕組み</a><a href="#rest">未実施</a>')
    p.write_text(s, encoding='utf-8')
    print('added')
else:
    print('already')
