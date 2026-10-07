"""報告のページに P19（表情）の節を足す。1回だけ流す（入れ済みなら何もしない）。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / 'index.html'
s = p.read_text(encoding='utf-8')

P19 = '''<section id="p19">
  <h2>表情を言葉で描き分けられるか・強さを比べて判定できるか</h2>
  <p class="rows">一覧 1-6・1-20・3-20 ／ <code>v3poc/p19_expression/</code></p>
  <details class="cond" open><summary>条件（何を渡して何で作ったか）</summary><div class="tw"><table>
    <tr><th>絵のモデル</th><td>WAI-illustrious-SDXL v1.6（ファイル <code>illustrious/waiIllustriousSDXL_v160.safetensors</code>）。euler_ancestral / normal / 25ステップ / CFG 5.0。832×1216</td></tr>
    <tr><th>キャラ</th><td>P17 の2人（a 白髪の三つ編みの女性、b 眼帯の男性）。特徴の言葉は全部入れた</td></tr>
    <tr><th>プロンプト</th><td>画質・絵柄 <code>masterpiece, best quality, manga, monochrome, greyscale, screentone</code> ＋ キャラの言葉 ＋ 表情の言葉 ＋ <code>upper body, looking at viewer, classroom</code></td></tr>
    <tr><th>表情の言葉（弱・中・強）</th><td>無表情 <code>expressionless</code><br>喜 <code>slight smile</code>／<code>smile, happy</code>／<code>laughing, open mouth, very happy</code><br>怒 <code>annoyed, frown</code>／<code>angry</code>／<code>furious, shouting, clenched teeth</code><br>哀 <code>sad, downcast eyes</code>／<code>sad, teary eyes</code>／<code>crying, tears, sobbing</code><br>驚 <code>slightly surprised</code>／<code>surprised, open mouth</code>／<code>shocked, wide-eyed, gasping</code></td></tr>
    <tr><th>参照画像の部品</th><td>強の段と無表情にだけ、P17 の参照画像を IP-Adapter plus 強さ0.5 で足した（1-20）</td></tr>
    <tr><th>seed</th><td><code>31〜33</code>（全108枚）</td></tr>
    <tr><th>LLMの判定（3-20）</th><td>Claude Sonnet（Claude Code の <code>claude -p</code>）に、2枚ずつ「どちらの表情に感情が強く表れているか」と、各画像の感情の種類を答えさせた。組は無表情と弱・弱と中・中と強・弱と強・強と強＋参照。左右を入れ替えて2回聞き、食い違ったら引き分け。画像は名前を伏せた写しを見せ、組の並びも混ぜた</td></tr>
  </table></div></details>
  <div class="tw"><table>
    <tr><th>感情</th><th>弱→中→強が見て順に並ぶ（目、6組）</th><th>LLM が狙いの順と一致（弱と中）</th><th>LLM（中と強）</th><th>LLM（無表情と弱・弱と強）</th></tr>
    <tr><td>喜</td><td class="good">6/6</td><td>5/6</td><td>6/6</td><td>12/12</td></tr>
    <tr><td>怒</td><td>3/6（a は弱と中が同じくらい）</td><td>4/6</td><td>6/6</td><td>12/12</td></tr>
    <tr><td>哀</td><td class="bad">1/6（弱と中がほぼ同じ）</td><td>4/6</td><td>5/6</td><td>10/12</td></tr>
    <tr><td>驚</td><td class="bad">0/6（弱の言葉で既に目を見開く）</td><td>6/6</td><td class="bad">2/6</td><td>12/12</td></tr>
  </table></div>
  <ul>
    <li>1-6：無表情と強い表情は24/24で見分けられる。崩れて見えるほど極端な顔は無かった。ただし段の描き分けは感情で違い、喜は3段が見て分かるが、驚は弱い側が作れない（<code>slightly surprised</code> でもう目を見開いて口を開ける）。哀は弱と中がほぼ同じ。</li>
    <li>3-20：名前を伏せた LLM の「どちらが強いか」は、狙いの順と96組中84組で一致、引き分け9、逆3。左右を入れ替えても同じ答えだったのは88組。外れと引き分けは、目でも差が見分けにくい組（驚の中と強、哀の弱と中）に集まった。感情の種類は、のべ240回の答えのうち233回が狙いどおり（外れは、弱い怒・弱い哀を無表情としたものと、無表情と哀の取り違え）。</li>
    <li class="bad">最初の判定では、ファイル名に感情と段が入ったまま見せていた（96組中92組が一致）。名前から順が読めるので、この数字は使わない（<code>out/judge_sonnet_namesvisible.json</code> に残した）。</li>
    <li>1-20：参照画像の部品を足すと、LLM は24組中18組で「参照なしの方が強い」とした。目でも a は表情が弱まった（笑わない・怒らない）。b は保たれた。どちらも白黒に色が乗った。</li>
    <li class="bad">b の眼帯が、絵によって左右どちらの目にも付いた。同一キャラ判定は、参照なしの b の39枚をすべて同じキャラとした（差は最大0.057、閾値0.178）。その中に眼帯が左右逆の絵が入っていた。左右の違いを見分けられるかは未検証。</li>
    <li>限界：目の判定は Claude が付けた（漫画を描く人ではない）。LLM の判定の正解も「狙いの段」と Claude の目で、人の判定と比べていない。場面は上半身・正面だけ。</li>
  </ul>
  <div class="figs">
    <figure><a href="../p19_expression/out/sheet_face_a.png"><img src="../p19_expression/out/sheet_face_a.png" alt="a の表情の一覧（顔を切り出したもの）" loading="lazy"></a><figcaption>a。行が感情と seed、列が無表情・弱・中・強・強＋参照（顔の検出器で顔を切り出した）</figcaption></figure>
    <figure><a href="../p19_expression/out/sheet_face_b.png"><img src="../p19_expression/out/sheet_face_b.png" alt="b の表情の一覧（顔を切り出したもの）" loading="lazy"></a><figcaption>b。眼帯が左右どちらにも付く</figcaption></figure>
  </div>
</section>
'''


def main():
    global s
    if '<section id="p19">' in s:
        print('入れ済み')
        return
    s = s.replace('<section id="p13">', P19 + '<section id="p13">', 1)
    s = s.replace('<a href="#p13">仕組み</a>', '<a href="#p19">表情</a><a href="#p13">仕組み</a>', 1)
    p.write_text(s, encoding='utf-8')
    print('ok')


if __name__ == '__main__':
    main()
