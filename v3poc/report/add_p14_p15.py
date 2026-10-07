"""報告のページに P14（余白とコマの形）と P15（絵柄と狙い）の節を足す。1回だけ流す（入れ済みなら何もしない）。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / 'index.html'
s = p.read_text(encoding='utf-8')

P14 = '''<section id="p14">
  <h2>余白のあるコマを、横長・縦長の形に合わせて作れるか</h2>
  <p class="rows">一覧 1-32・1-33・1-34 ／ <code>v3poc/p14_margin/</code> ／ 手ごとの設定の全部は <a href="../recipes/index.html#fit_yoko">作り方の一覧</a></p>
  <details class="cond" open><summary>条件（何を渡して何で作ったか）</summary><div class="tw"><table>
    <tr><th>絵のモデル</th><td>WAI-illustrious-SDXL v1.6（SDXL系・アニメ）。euler_ancestral / normal / 25ステップ / CFG 5.0</td></tr>
    <tr><th>プロンプト（全部の手で同じ）</th><td><code>masterpiece, best quality, manga, monochrome, greyscale, screentone, city street, buildings, 1girl, solo, short black bob hair, glasses, school blazer, necktie, standing, full body, wide shot, scenery</code></td></tr>
    <tr><th>コマの形と人物の枠</th><td>横長 1536×576（人物は右寄り）／縦長 576×1536（人物は下の真ん中）／標準 1152×896（人物は左寄り）</td></tr>
    <tr><th>手</th><td>言葉だけ／初めだけ縮小（Deep Shrink）／骨格の図4種（xinsir・xinsir 多用途版・windsingai・TencentARC。どれも Apache-2.0）／縦長で作って切り抜く／縦長で作り縮めて置き周りを描き足す</td></tr>
    <tr><th>seed</th><td><code>61〜63</code>（手ごとに3枚）</td></tr>
    <tr><th>中身</th><td class="bad">人物1種（眼鏡の女子生徒）・場所1種（街）だけ。結果は「このプロンプトではこうなった」まで</td></tr>
  </table></div></details>
  <div class="tw"><table>
    <tr><th>手（人物を枠の位置と大きさに置けたか）</th><th>横長</th><th>縦長</th><th>標準</th><th>外れ方</th></tr>
    <tr><td>言葉だけ</td><td>0/3</td><td>3/3</td><td>0/3</td><td>余白は出るが、人物はほぼ真ん中に立つ。縦長は枠が真ん中なので合っただけ</td></tr>
    <tr><td>初めだけ縮小</td><td>0/3</td><td>3/3</td><td>0/3</td><td>言葉だけと同じ。極端な形でも人物は増えなかった（言葉だけでも増えなかった）</td></tr>
    <tr><td>骨格 xinsir</td><td class="bad">0/3</td><td>3/3</td><td>2/3</td><td>位置は合うが、横長では3枚とも人物の周りに白い縁取り</td></tr>
    <tr><td>骨格 xinsir 多用途版</td><td class="bad">1/3</td><td>3/3</td><td>2/3</td><td>同じく白い縁取り</td></tr>
    <tr><td>骨格 windsingai（Illustrious 向け）</td><td class="good">3/3</td><td class="good">3/3</td><td class="good">3/3</td><td>—</td></tr>
    <tr><td>骨格 TencentARC</td><td>2/3</td><td>3/3</td><td>1/3</td><td>骨格を無視して真ん中に立つことがある</td></tr>
    <tr><td>切り抜く（比べるため）</td><td class="bad">0/3</td><td class="bad">0/3</td><td class="bad">0/3</td><td>寄りになり余白がない</td></tr>
    <tr><td>描き足す</td><td class="good">3/3</td><td>2/3</td><td>1/3</td><td>描き足した所が黒や灰色の平らな面になることがある</td></tr>
  </table></div>
  <p>商用に使える骨格の制御で、人物を狙いの位置と大きさに置けた。いちばん安定したのは windsingai（9/9）。3枚ずつなので目安。</p>
  <div class="figs">
    <figure><a href="../p14_margin/out/sheet_yoko.png"><img src="../p14_margin/out/sheet_yoko.png" alt="横長のコマの手ごとの結果" loading="lazy"></a><figcaption>横長。行が手、列が seed</figcaption></figure>
    <figure><a href="../p14_margin/out/sheet_std.png"><img src="../p14_margin/out/sheet_std.png" alt="標準の形のコマの手ごとの結果" loading="lazy"></a><figcaption>標準の形</figcaption></figure>
    <figure class="sm"><a href="../p14_margin/out/sheet_tate.png"><img src="../p14_margin/out/sheet_tate.png" alt="縦長のコマの手ごとの結果" loading="lazy"></a><figcaption>縦長</figcaption></figure>
  </div>
</section>

<section id="p15">
  <h2>絵柄を変えて、狙いのコマ（引き・人物だけ・背景だけ）を作れるか</h2>
  <p class="rows">一覧 1-32・1-35・1-36 ／ <code>v3poc/p15_shots/</code> ／ 狙いごとの作りたい絵・プロンプトの全文・大きさ・結果の全部は <a href="../recipes/index.html">作り方の一覧</a></p>
  <details class="cond" open><summary>条件（何を渡して何で作ったか）</summary><div class="tw"><table>
    <tr><th>絵のモデル</th><td>WAI-illustrious-SDXL v1.6。euler_ancestral / normal / 25ステップ / CFG 5.0。制御なし（言葉だけ）</td></tr>
    <tr><th>プロンプトの組み方</th><td>画質 ＋ 絵柄 ＋ 狙い ＋ 人物 ＋ 場所。狙いの部品は、その狙いに要る言葉だけ</td></tr>
    <tr><th>絵柄の言葉</th><td>トーン <code>manga, monochrome, greyscale, screentone</code>／ペン線 <code>monochrome, greyscale, lineart, crosshatching, hatching (texture)</code>／90年代風 <code>monochrome, greyscale, retro artstyle, 1990s (style)</code>／カラー <code>anime coloring, flat color</code></td></tr>
    <tr><th>背景を抜く</th><td>ComfyUI-RMBG の BiRefNetRMBG、モデル BiRefNet_toonout（MIT）</td></tr>
    <tr><th>seed</th><td><code>71〜73</code>（条件ごとに3枚）</td></tr>
    <tr><th>中身</th><td class="bad">人物1種（眼鏡の女子生徒）・場所1種（街）だけ。人物と場所を入れ替えた結果は P16（生成中）</td></tr>
  </table></div></details>
  <div class="tw"><table>
    <tr><th>狙い（大きさ）</th><th>狙いの言葉</th><th>トーン</th><th>ペン線</th><th>90年代風</th><th>カラー</th></tr>
    <tr><td>横長コマの引き（1536×576）</td><td><code>wide shot, scenery</code></td><td>3/3</td><td>3/3</td><td>2/3</td><td>3/3</td></tr>
    <tr><td>縦長コマの引き（576×1536）</td><td><code>wide shot, scenery</code></td><td>3/3</td><td>3/3</td><td>3/3</td><td>3/3</td></tr>
    <tr><td>標準コマの全身（1152×896）</td><td><code>full body, wide shot</code></td><td>3/3</td><td>3/3</td><td>2/3</td><td>3/3</td></tr>
    <tr><td>人物だけ（832×1216、背景を抜く）</td><td><code>full body, simple background, white background</code></td><td>3/3</td><td>3/3</td><td>3/3</td><td>3/3</td></tr>
    <tr><td>背景だけ・横長</td><td><code>scenery, no humans</code></td><td class="bad">1/3</td><td>3/3</td><td>2/3</td><td>2/3</td></tr>
    <tr><td>背景だけ・縦長</td><td><code>scenery, no humans</code></td><td class="bad">1/3</td><td>3/3</td><td>2/3</td><td class="bad">1/3</td></tr>
    <tr><td>背景だけ・標準</td><td><code>scenery, no humans</code></td><td class="bad">0/3</td><td>3/3</td><td class="bad">1/3</td><td class="bad">1/3</td></tr>
  </table></div>
  <ul>
    <li>引きと人物だけは、ほぼ狙いどおり。ただし言葉だけでは人物はほとんど真ん中に立つ（単調になる）。</li>
    <li class="bad">背景だけは、真上から見下ろす街になり、人物を立たせる地面がない絵がよく出た。ペン線だけは9枚とも地面の高さだったが、理由は分からない。</li>
    <li class="bad">白黒の絵柄3種は見分けがつかないほど似た。試した言葉（3種）では、白黒の絵柄は変わらなかった。ほかの言葉で変わるかは未検証。カラーだけははっきり変わる。</li>
  </ul>
  <div class="figs">
    <figure><a href="../p15_shots/out/sheet_long_yoko.png"><img src="../p15_shots/out/sheet_long_yoko.png" alt="横長コマの引きの絵柄ごとの結果" loading="lazy"></a><figcaption>横長コマの引き。行が絵柄、列が seed</figcaption></figure>
    <figure><a href="../p15_shots/out/sheet_bg_std.png"><img src="../p15_shots/out/sheet_bg_std.png" alt="背景だけの標準の形の結果" loading="lazy"></a><figcaption>背景だけ・標準（見下ろしが多い）</figcaption></figure>
    <figure><a href="../p15_shots/out/sheet_chara_only.png"><img src="../p15_shots/out/sheet_chara_only.png" alt="人物だけの絵と背景を抜いた絵" loading="lazy"></a><figcaption>人物だけ。右3列が背景を抜いた絵</figcaption></figure>
  </div>
</section>

'''


def main():
    global s
    if '<section id="p14">' in s:
        print('入れ済み')
        return
    s = s.replace('<section id="p13">', P14 + '<section id="p13">', 1)
    s = s.replace('<a href="#p13">仕組み</a>', '<a href="#p14">余白とコマの形</a><a href="#p15">絵柄と狙い</a><a href="#p13">仕組み</a>', 1)
    s = s.replace('<a href="../checklist/checklist.html">検証の一覧</a>', '<a href="../recipes/index.html">作り方の一覧</a>\n    <a href="../checklist/checklist.html">検証の一覧</a>', 1)
    p.write_text(s, encoding='utf-8')
    print('ok')


if __name__ == '__main__':
    main()
