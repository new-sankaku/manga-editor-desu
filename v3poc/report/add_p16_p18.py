"""報告のページに P16（中身を変えても効くか）・P17（顔を揃えるやり直し）・P18（背景の不揃い）の節を足す。1回だけ流す（入れ済みなら何もしない）。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / 'index.html'
s = p.read_text(encoding='utf-8')

MODEL = 'WAI-illustrious-SDXL v1.6（SDXL系・アニメ。ファイル <code>illustrious/waiIllustriousSDXL_v160.safetensors</code>）。euler_ancestral / normal / 25ステップ / CFG 5.0'

P16 = f'''<section id="p16">
  <h2>人物と場所を入れ替えても、狙いの言葉が効くか</h2>
  <p class="rows">一覧 1-37 ／ <code>v3poc/p16_general/</code></p>
  <details class="cond" open><summary>条件（何を渡して何で作ったか）</summary><div class="tw"><table>
    <tr><th>絵のモデル</th><td>{MODEL}。制御なし（言葉だけ）</td></tr>
    <tr><th>プロンプトの組み方</th><td>P15 と同じ「画質＋絵柄＋狙い＋人物＋場所」。絵柄は白黒トーン（<code>manga, monochrome, greyscale, screentone</code>）だけ。狙いの言葉と大きさは P15 のまま</td></tr>
    <tr><th>人物（3種）</th><td>眼鏡の女子生徒 <code>1girl, solo, short black hair, bob cut, glasses, school uniform, blazer, standing</code>／パーカーの少年 <code>1boy, solo, short hair, hoodie, jeans, sneakers, standing</code>／背広の老人 <code>1boy, solo, old man, grey hair, beard, suit, standing</code></td></tr>
    <tr><th>場所（3種）</th><td>街 <code>city street, buildings</code>／教室 <code>classroom, desks, windows</code>／郊外 <code>countryside, rice field, mountains, utility pole</code></td></tr>
    <tr><th>seed</th><td><code>81〜83</code>（組み合わせごとに3枚、全108枚）</td></tr>
    <tr><th>判定</th><td>目で「狙いどおりか」（Claude が一覧画像を見て付けた。<code>out/labels.json</code>）。人数は検出器でも数えた</td></tr>
  </table></div></details>
  <div class="tw"><table>
    <tr><th>狙い（大きさ）</th><th>街</th><th>教室</th><th>郊外</th><th>P15（街だけ・トーン）</th></tr>
    <tr><td>横長コマの引き（1536×576）</td><td>8/9</td><td>9/9</td><td>9/9</td><td>3/3</td></tr>
    <tr><td>縦長コマの引き（576×1536）</td><td>8/9</td><td class="bad">1/9</td><td>9/9</td><td>3/3</td></tr>
    <tr><td>標準コマの全身（1152×896）</td><td>9/9</td><td>9/9</td><td>9/9</td><td>3/3</td></tr>
    <tr><td>背景だけ・横長</td><td class="bad">1/3</td><td>3/3</td><td>3/3</td><td>1/3</td></tr>
    <tr><td>背景だけ・縦長</td><td class="bad">1/3</td><td class="bad">0/3</td><td>2/3</td><td>1/3</td></tr>
    <tr><td>人物だけ（832×1216、場所なし）</td><td colspan="3">8/9（人物3種）</td><td>3/3</td></tr>
  </table></div>
  <ul>
    <li class="bad">縦長のコマで場所を教室にすると、1枚の中にコマが縦に2〜4段並んだ絵になった（引き 9枚中7枚、背景だけ 3枚中3枚）。P15 の街だけでは1回も起きなかった。場所を変えるだけで、同じ狙いの言葉が効かなくなる。</li>
    <li>標準の全身と横長の引きは、人物と場所を変えてもほぼ狙いどおり（横長の失敗1枚は人物が2人）。</li>
    <li class="bad">背景だけの街は、ここでも真上から見下ろす絵が多い（P15 と同じ）。教室と郊外は地面の高さで描かれた。</li>
    <li>絵の構図は seed で決まる傾向が強い。同じ seed なら、人物を変えても似た構図になった（街の seed 82 は3人とも傾いた見下ろし、全身の seed 82 は3人とも真ん中に立つ一点透視）。うまくいった seed を別の中身に使い回すと、同じ構図が並んで単調になる。</li>
    <li class="bad">人物だけの背広の老人（seed 81）に読めない文字が入り、背景を抜いても文字が残った。</li>
    <li>検出器は、横長の引きで人物の高さがコマの約3分の1より小さいと人物を見落とした（「人0」と出た8枚は、どれも人物が1人いる）。小さい人物の数を検出器だけで確かめることはできない。</li>
  </ul>
  <div class="figs">
    <figure class="sm"><a href="../p16_general/out/sheet_long_tate.png"><img src="../p16_general/out/sheet_long_tate.png" alt="縦長コマの引き。教室の行でコマが縦に並ぶ" loading="lazy"></a><figcaption>縦長コマの引き。行が人物・場所、列が seed。教室の行でコマが縦に並ぶ</figcaption></figure>
    <figure><a href="../p16_general/out/sheet_long_yoko.png"><img src="../p16_general/out/sheet_long_yoko.png" alt="横長コマの引き" loading="lazy"></a><figcaption>横長コマの引き。「人0」は検出器の見落とし</figcaption></figure>
    <figure><a href="../p16_general/out/sheet_full_std.png"><img src="../p16_general/out/sheet_full_std.png" alt="標準コマの全身" loading="lazy"></a><figcaption>標準コマの全身。列ごと（seed ごと）に構図が似る</figcaption></figure>
    <figure><a href="../p16_general/out/sheet_bg_yoko.png"><img src="../p16_general/out/sheet_bg_yoko.png" alt="背景だけ・横長" loading="lazy"></a><figcaption>背景だけ・横長</figcaption></figure>
    <figure class="sm"><a href="../p16_general/out/sheet_bg_tate.png"><img src="../p16_general/out/sheet_bg_tate.png" alt="背景だけ・縦長" loading="lazy"></a><figcaption>背景だけ・縦長</figcaption></figure>
    <figure><a href="../p16_general/out/sheet_chara_only.png"><img src="../p16_general/out/sheet_chara_only.png" alt="人物だけと背景を抜いた絵" loading="lazy"></a><figcaption>人物だけ（左3列）と背景を抜いた絵（右3列）</figcaption></figure>
  </div>
</section>
'''

P17 = f'''<section id="p17">
  <h2>顔を揃えるのに、プロンプトをどこまで寄せる必要があるか（P09 のやり直し）</h2>
  <p class="rows">一覧 1-29・1-20・3-8 ／ <code>v3poc/p17_identity2/</code></p>
  <details class="cond" open><summary>条件（何を渡して何で作ったか）</summary><div class="tw"><table>
    <tr><th>絵のモデル</th><td>{MODEL}。832×1216</td></tr>
    <tr><th>キャラ（2人）</th><td>a 白髪の三つ編みの女性、b 眼帯の男性。どちらもモデルがふだん描かない見た目にした（P09 の黒髪の女子生徒は、言葉が無くても出やすかった）</td></tr>
    <tr><th>参照画像</th><td>キャラごとに1枚。全部の特徴の言葉 ＋ <code>upper body, looking at viewer, simple background, white background</code>、seed 101 で作った（下の図の1行目）。<br>a：<code>1girl, solo, white hair, long hair, twin braids, red eyes, freckles, star hair ornament, black hoodie, choker</code><br>b：<code>1boy, solo, messy hair, brown hair, short hair, scar on cheek, eyepatch, green jacket, white shirt</code></td></tr>
    <tr><th>プロンプトの寄せ方（3段）</th><td>性別だけ（<code>1girl, solo</code> など）／性別＋髪（a <code>white hair, long hair, twin braids</code>、b <code>messy hair, brown hair, short hair</code>）／性別＋全部の特徴（参照画像と同じ言葉）。前に画質と絵柄 <code>masterpiece, best quality, manga, monochrome, greyscale, screentone</code>、後ろに場面</td></tr>
    <tr><th>場面（3種）</th><td>走る <code>running, full body, street</code>／食べる <code>eating bread, sitting, cafeteria, upper body</code>／横顔 <code>from side, profile, looking at window, upper body</code></td></tr>
    <tr><th>参照画像の部品</th><td>なし／IP-Adapter plus SDXL（<code>ip_adapter_plus_sdxl_vit-h</code>、Apache-2.0）＋ <code>clip_vision_h</code>（MIT）、強さ 0.5・0.8。顔専用の FaceID は insightface が非商用なので外した</td></tr>
    <tr><th>seed</th><td><code>21〜23</code>（条件ごとに 場面3 × seed3 ＝ 9枚、全162枚）</td></tr>
    <tr><th>判定</th><td>目で「目立つ特徴が見えるか」（Claude が一覧画像を見て付けた）と、同一キャラ判定 CCIP（dghs-imgutils、閾値0.178）で参照画像と比べた</td></tr>
  </table></div></details>
  <div class="tw"><table>
    <tr><th>寄せ方</th><th>参照</th><th>a 目で見て同じ</th><th>a CCIP 同じ</th><th>b 目で見て同じ</th><th>b CCIP 同じ</th></tr>
    <tr><td rowspan="3">性別だけ</td><td>なし</td><td class="bad">0/9</td><td>0/9</td><td class="bad">0/9</td><td class="bad">7/9</td></tr>
    <tr><td>0.5</td><td>0/9</td><td>0/9</td><td>0/9</td><td>6/9</td></tr>
    <tr><td>0.8</td><td>0/9</td><td>0/9</td><td>0/9</td><td>5/9</td></tr>
    <tr><td rowspan="3">性別＋髪</td><td>なし</td><td class="bad">0/9</td><td class="bad">6/9</td><td class="bad">0/9</td><td class="bad">9/9</td></tr>
    <tr><td>0.5</td><td>0/9</td><td>2/9</td><td>0/9</td><td>9/9</td></tr>
    <tr><td>0.8</td><td>0/9</td><td>0/9</td><td>0/9</td><td>9/9</td></tr>
    <tr><td rowspan="3">性別＋全部の特徴</td><td>なし</td><td class="good">9/9</td><td>9/9</td><td class="good">8/9</td><td>9/9</td></tr>
    <tr><td>0.5</td><td>—</td><td>8/9</td><td>—</td><td>9/9</td></tr>
    <tr><td>0.8</td><td>—</td><td>7/9</td><td>—</td><td>7/9</td></tr>
  </table></div>
  <p>「—」は、特徴は出ているが色が乗って絵が崩れたので、揃ったかを数えなかった所。</p>
  <ul>
    <li><b>寄せる所：見た目の特徴を全部、毎回言葉で書く必要があった。</b>性別だけでは別人（黒髪のよくある顔）になり、髪まで書いても目の色・髪飾り・眼帯・服が出ない。全部書くと a 9/9、b 8/9（外した1枚は横顔で眼帯の側が見えない）。</li>
    <li class="bad">参照画像の部品（IP-Adapter plus）は言葉の代わりにならなかった。性別だけに足すと白い髪は寄るが、三つ編み・髪飾り・眼帯は出ない。強さ0.5でも白黒の指定なのに青・緑・紫の色が乗り、線がにじむ。全部の特徴を書いた上に足しても良くならない。</li>
    <li class="bad">特徴の言葉に色が入ると（<code>red eyes</code>・<code>green jacket</code>）、白黒の指定でもその色が残った。P07 の赤いネクタイと同じことが、別の人物でも起きた。</li>
    <li class="bad">同一キャラ判定 CCIP は、髪が似ていれば別人でも「同じ」と出た（b は性別だけの黒髪の別人でも 7/9）。別キャラの参照画像と「同じ」と出たことは162枚で0回。「違う」は信じてよいが、「同じ」だけでは同じキャラと決められない。</li>
    <li>限界：モデル1つ・キャラ2人・特徴の言葉で言い表せる見た目だけ。言葉で言い表せない顔立ち（目の形・輪郭）は未検証。追加学習（1-29 の比較）は未実施。</li>
  </ul>
  <div class="figs">
    <figure><a href="../p17_identity2/out/sheet_a.png"><img src="../p17_identity2/out/sheet_a.png" alt="白髪の三つ編みの女性の結果" loading="lazy"></a><figcaption>a 白髪の三つ編みの女性。1行目が参照画像、行が寄せ方／参照、列が場面と seed</figcaption></figure>
    <figure><a href="../p17_identity2/out/sheet_b.png"><img src="../p17_identity2/out/sheet_b.png" alt="眼帯の男性の結果" loading="lazy"></a><figcaption>b 眼帯の男性</figcaption></figure>
  </div>
</section>
'''

P18 = f'''<section id="p18">
  <h2>背景の不揃いを、3Dの場所で解消できるか</h2>
  <p class="rows">一覧 1-38 ／ <code>v3poc/p18_bg_consistency/</code> ／ 方針20、候補96〜103</p>
  <details class="cond" open><summary>条件（何を渡して何で作ったか）</summary><div class="tw"><table>
    <tr><th>絵のモデル</th><td>{MODEL}。1152×896</td></tr>
    <tr><th>プロンプト</th><td>教室 <code>masterpiece, best quality, manga, monochrome, greyscale, screentone, scenery, no humans, classroom, desks, chalkboard, windows, indoors</code><br>街 <code>…, scenery, no humans, city street, buildings, road, utility pole</code>。否定に <code>1girl, 1boy, people</code> を足した</td></tr>
    <tr><th>3Dの場所</th><td>箱だけで組んだ教室（幅8m・奥行き10m、左の壁に窓、前に黒板、後ろにロッカー、机3×3）と街（真ん中の道、両側に高さの違う建物、右に電柱）。<code>scene3d.py</code>（numpy だけ、外の3Dソフトなし）で3つの向き（front・side・back）から奥行きの図と線画を書き出した（下の図の1行目）</td></tr>
    <tr><th>手</th><td>言葉だけ／奥行き（xinsir 多用途版の depth、Apache-2.0、強さ0.8、効かせる終わり0.8）／線画（同じ部品の lineart、白黒を反転して渡す）／奥行き＋参照（front の絵を IP-Adapter plus 強さ0.5 で足す。side・back だけ）</td></tr>
    <tr><th>seed</th><td><code>91〜93</code>（手・向きごとに3枚、全66枚）</td></tr>
    <tr><th>測り方</th><td>線の重なり＝3Dの線のうち、生成した絵の輪郭が3画素以内にある割合。同じ絵を別の向きの3Dの線とも比べ、その差を見る（候補101）</td></tr>
  </table></div></details>
  <div class="tw"><table>
    <tr><th>手</th><th>間取りが揃う（目）</th><th>線の重なり 教室（別の向き）</th><th>線の重なり 街（別の向き）</th></tr>
    <tr><td>言葉だけ</td><td class="bad">—（向きを言い分けられない）</td><td>0.49（0.49）</td><td>0.47（0.47）</td></tr>
    <tr><td>奥行き</td><td class="good">18/18</td><td>0.98（0.46）</td><td>0.79（0.56）</td></tr>
    <tr><td>線画</td><td class="good">18/18</td><td>0.97（0.46）</td><td>0.84（0.55）</td></tr>
    <tr><td>奥行き＋参照</td><td>12/12</td><td>0.94（0.39）</td><td>0.77（0.60）</td></tr>
  </table></div>
  <ul>
    <li>3Dの場所から書き出した奥行きか線画を渡すと、壁・床・天井の境目、机の数と位置、道の向き、建物の並びが、向きを変えても3Dどおりに揃った（両方の手で18/18）。</li>
    <li class="bad">言葉だけでは向きを言い分けられず、同じ seed なら3つの向きで同じ絵になった。seed を変えると、窓の数・黒板の大きさ・照明の並びが違う別の教室になる（コマごとに別の部屋になる）。</li>
    <li class="bad">壁に何を描くかは揃わない。後ろの壁（3Dではロッカー）には9枚とも黒板が描かれ、窓の壁にも黒板が描かれ、窓が左右逆の壁に出ることも多い。原因は、3Dの箱が面に何があるかを持たないことだと考えるが、未検証（→候補102・103）。</li>
    <li class="bad">机は脚のない箱のまま描かれた。3Dの箱の形をそのまま写すので、3Dを粗く作るとそのまま絵に出る。</li>
    <li class="bad">front の絵を参照画像にしても質感は揃わず、白黒の指定なのに水色・緑が乗った（候補99は効かなかった）。</li>
    <li>線の重なりは、自分の向きの線と別の向きの線で 0.79〜0.98 と 0.39〜0.60 に分かれ、間取りが3Dどおりかの検査に使えるかもしれない（候補101、この試作だけ）。窓の所に黒板が描かれた絵でも重なりは高いままで、窓か黒板かの違いは数値に出なかった。</li>
  </ul>
  <div class="figs">
    <figure><a href="../p18_bg_consistency/out/sheet_room_91.png"><img src="../p18_bg_consistency/out/sheet_room_91.png" alt="教室を3つの向きから" loading="lazy"></a><figcaption>教室 seed 91。1行目が3Dの線画、行が手、列が向き</figcaption></figure>
    <figure><a href="../p18_bg_consistency/out/sheet_room_92.png"><img src="../p18_bg_consistency/out/sheet_room_92.png" alt="教室 seed 92" loading="lazy"></a><figcaption>教室 seed 92</figcaption></figure>
    <figure><a href="../p18_bg_consistency/out/sheet_room_93.png"><img src="../p18_bg_consistency/out/sheet_room_93.png" alt="教室 seed 93" loading="lazy"></a><figcaption>教室 seed 93</figcaption></figure>
    <figure><a href="../p18_bg_consistency/out/sheet_room_text.png"><img src="../p18_bg_consistency/out/sheet_room_text.png" alt="言葉だけの教室を seed ごとに" loading="lazy"></a><figcaption>言葉だけの教室。seed ごとに別の部屋になる</figcaption></figure>
    <figure><a href="../p18_bg_consistency/out/sheet_street_91.png"><img src="../p18_bg_consistency/out/sheet_street_91.png" alt="街を3つの向きから" loading="lazy"></a><figcaption>街 seed 91</figcaption></figure>
    <figure><a href="../p18_bg_consistency/out/sheet_street_text.png"><img src="../p18_bg_consistency/out/sheet_street_text.png" alt="言葉だけの街を seed ごとに" loading="lazy"></a><figcaption>言葉だけの街</figcaption></figure>
  </div>
</section>
'''

P09_NOTE = '  <p class="note">この節の結果は易しい条件だった（参照画像と同じ言葉で作り、モデルがふだん描く見た目だった）。キャラを変え、プロンプトの寄せ方を3段にしたやり直しは <a href="#p17">P17</a>。</p>\n'


def main():
    global s
    if '<section id="p16">' in s:
        print('入れ済み')
        return
    s = s.replace('<section id="p13">', P16 + P17 + P18 + '<section id="p13">', 1)
    s = s.replace('<a href="#p13">仕組み</a>', '<a href="#p16">中身を変える</a><a href="#p17">顔を揃える（やり直し）</a><a href="#p18">背景を揃える</a><a href="#p13">仕組み</a>', 1)
    s = s.replace('<p class="rows">一覧 1-20・1-29・3-8 ／ <code>v3poc/p09_identity/</code></p>\n',
                  '<p class="rows">一覧 1-20・1-29・3-8 ／ <code>v3poc/p09_identity/</code></p>\n' + P09_NOTE, 1)
    s = s.replace('人物と場所を入れ替えた結果は P16（生成中）', '人物と場所を入れ替えた結果は <a href="#p16">P16</a>', 1)
    p.write_text(s, encoding='utf-8')
    print('ok')


if __name__ == '__main__':
    main()
