"""報告のページの各試作に「条件（何を渡して何で作ったか）」の欄を入れる。1回だけ流す（入れ済みなら何もしない）。"""
import html
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / 'index.html'
s = p.read_text(encoding='utf-8')


def c(x):
    return f'<code>{html.escape(x)}</code>'


def img(path, cap):
    return f'<figure class="sm"><a href="{path}"><img src="{path}" alt="{html.escape(cap)}" loading="lazy"></a><figcaption>{html.escape(cap)}</figcaption></figure>'


M = 'WAI-illustrious-SDXL v1.6（SDXL系・アニメ。ファイル ' + c('illustrious/waiIllustriousSDXL_v160.safetensors') + '）'
NEG = 'lowres, bad anatomy, bad hands, extra digits, fewer digits, worst quality, low quality, jpeg artifacts, signature, watermark, username, blurry'
COMMON = (f'<tr><th>絵のモデル</th><td>{M}</td></tr>'
          f'<tr><th>生成の設定</th><td>{c("832×1216 / euler_ancestral / normal / 25ステップ / CFG 5.0")}（ほかに書いていなければこれ）</td></tr>'
          f'<tr><th>否定の言葉</th><td>{c(NEG)}</td></tr>')
ONE = '<tr><th>中身</th><td class="bad">人物1種（眼鏡の女子生徒）だけで試した。結果は「このプロンプトではこうなった」まで</td></tr>'


def block(rows, common=True, one=True):
    return (f'<details class="cond" open><summary>条件（何を渡して何で作ったか）</summary><div class="tw"><table>'
            f'{COMMON if common else ""}{rows}{ONE if one else ""}</table></div></details>')


P02 = 'masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, short black bob hair, glasses, school blazer, red necktie, pleated skirt, classroom'
INSTR = [('後ろ姿', 'from behind, facing away'), ('見下ろし', 'from above, high angle'), ('見上げ', 'from below, low angle'), ('横顔', 'from side, profile'),
         ('全身', 'full body, standing, shoes'), ('寄り（顔）', 'close-up, face focus, portrait'), ('引き', 'very wide shot, small figure in distance, scenery'),
         ('上半身', 'upper body'), ('2人', '2girls, standing side by side, talking'), ('3人', '3girls, group, standing'),
         ('カメラ目線', 'looking at viewer, upper body'), ('書く手', 'upper body, holding pencil, writing in notebook, hands visible')]
COND = {
    'p02': block(f'<tr><th>プロンプト</th><td>{c(P02)} ＋（1人のときは {c("solo, ")}）＋ 下の指示の言葉</td></tr>'
                 + ''.join(f'<tr><th>{a}</th><td>{c(b)}</td></tr>' for a, b in INSTR)
                 + f'<tr><th>seed</th><td>{c("1001〜1008")}（指示ごとに8枚）</td></tr>'),
    'p03': block(f'<tr><th>プロンプト</th><td>{c("masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, solo, short black bob hair, glasses, school blazer, red necktie, upper body, classroom")}</td></tr>'
                 f'<tr><th>seed</th><td>{c("4242")}（3回とも同じ）。3回目の前に別の依頼（{c(", from side")} を足して seed 7）を挟んだ</td></tr>'
                 f'<tr><th>描き方</th><td>{c("euler_ancestral")}、{c("dpmpp_2m")}</td></tr>'),
    'p04': block(f'<tr><th>プロンプト</th><td>{c("masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, solo, short black bob hair, glasses, school blazer, red necktie, full body, standing, street, detailed background")}</td></tr>'
                 f'<tr><th>生成の大きさ</th><td>{c("640×960 / 832×1216 / 1024×1536")}</td></tr>'
                 f'<tr><th>拡大先</th><td>{c("4300×6070")}（B5・600dpi）</td></tr>'
                 f'<tr><th>拡大のモデル</th><td>{c("4x-UltraSharp.pth")}（非商用）、{c("RealESRGAN_x4plus_anime_6B.pth")}、{c("RealESRGAN_x4plus.pth")}、比べるための単純な拡大（lanczos）</td></tr>'
                 '<tr><th>網点のトーン</th><td class="bad">絵1枚の網点だけで見た</td></tr>'),
    'p05': block('<tr><th>元の絵</th><td>「指示どおりか」の試作の上半身の1枚（seed 1001）。左上の枠 ' + c('(60,60)-(420,330)') + ' を人が直した範囲とした</td></tr>'
                 f'<tr><th>描き直させる範囲</th><td>正しい範囲 {c("(0,760)-(832,1216)")}／誤って人の範囲に掛けた範囲 {c("(0,250)-(832,1216)")}</td></tr>'
                 f'<tr><th>プロンプト</th><td>{c("masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, holding a book, school blazer")}</td></tr>'
                 f'<tr><th>描き直しの強さ</th><td>{c("denoise 0.85")}、seed {c("77")}</td></tr>'
                 '<tr><th>貼り戻し</th><td>生成のあと、人の範囲の画素を元の絵からそのまま戻す（画素の処理なので、絵の中身に依らない）</td></tr>', one=False),
    'p07': block(f'<tr><th>プロンプト</th><td>{c("masterpiece, best quality, anime coloring, 1girl, solo, short black bob hair, glasses, school blazer, red necktie, upper body, classroom, afternoon")}</td></tr>'
                 f'<tr><th>CFG</th><td>{c("3 / 5 / 7 / 9 / 12")}</td></tr><tr><th>seed</th><td>{c("31〜34")}（CFGごとに4枚）</td></tr>'),
    'p08': block(f'<tr><th>プロンプト</th><td>{c("masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, solo, short black bob hair, glasses, school blazer, red necktie, full body, standing, street")}</td></tr>'
                 f'<tr><th>ラフ</th><td>下の絵。人物の枠 {c("(150,430)-(350,1170)")}、フキダシの丸 {c("(500,60)-(800,420)")}</td></tr>'
                 f'<tr><th>線画の制御</th><td>{c("t2i-adapter-sketch-sdxl-1.0")}、{c("sai_xl_sketch_256lora")}。強さ {c("0.6 / 1.0")}、線の向き 白地に黒・黒地に白</td></tr>'
                 f'<tr><th>骨格の制御</th><td>{c("thibaud_xl_openpose")}（非営利だけ）、{c("t2i-adapter-openpose-sdxl-1.0")}。強さ {c("1.0")}</td></tr>'
                 f'<tr><th>範囲の指定</th><td>ComfyUIの標準の {c("ConditioningSetArea")} で、人物の言葉を人物の枠にだけ効かせる。強さ {c("1.0")}</td></tr>'
                 f'<tr><th>seed</th><td>{c("11〜13")}</td></tr>'
                 f'<tr><th>渡した絵</th><td><div class="figs">{img("../p08_rough/out/rough_bw.png", "ラフ（白地に黒）")}{img("../p08_rough/out/rough_wb.png", "ラフ（黒地に白）")}</div></td></tr>'),
    'p09': block(f'<tr><th>参照画像</th><td><div class="figs">{img("../p09_identity/out/ref.png", "参照画像（「指示どおりか」の上半身 seed 1001）")}</div></td></tr>'
                 f'<tr><th>参照画像の部品</th><td>IP-Adapter plus SDXL（{c("ip_adapter_plus_sdxl_vit-h")}、Apache-2.0）＋画像の読み取り CLIP ViT-H-14（MIT）。強さ {c("0.5 / 0.8")}、{c("linear / concat / V only")}</td></tr>'
                 f'<tr><th>プロンプト</th><td>{c("masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, solo, ")} ＋ キャラの説明 {c("short black bob hair, glasses, school blazer, red necktie, pleated skirt, ")} ＋ 場面</td></tr>'
                 f'<tr><th>場面</th><td>{c("running, full body, street")}／{c("eating bread, sitting, cafeteria, upper body")}／{c("from side, profile, looking at window, upper body")}／{c("laughing, close-up, park")}。seed {c("21〜23")}</td></tr>'
                 f'<tr><th>別キャラ（対照）</th><td>キャラの説明を {c("long blonde twintails, sailor school uniform, ribbon, ")} に替え、参照なし</td></tr>'
                 '<tr><th>判定</th><td>同一キャラ判定 CCIP（deepghs、OpenRAIL）で参照画像との差を測る。差が閾値 0.178 未満なら同じキャラ</td></tr>'
                 '<tr><th>欠陥</th><td class="bad">参照画像を作ったときと同じキャラの説明を、プロンプトにも全部入れた。参照画像が効いたのか、プロンプトが寄せたのかが分からない。プロンプトをどこまで寄せる必要があるかも調べていない。やり直しは P17</td></tr>'),
    'p10': block(f'<tr><th>プロンプト</th><td>{c("masterpiece, best quality, comic, manga page, monochrome, greyscale, screentone, panel borders, 1girl, short black bob hair, glasses, school blazer, ")} ＋ コマ数の言葉</td></tr>'
                 f'<tr><th>コマ数の言葉</th><td>3コマ {c("3 panels, vertical strip")}／4コマ漫画 {c("4koma, 4 panels")}／6コマ {c("multiple panels, 6 panels")}</td></tr>'
                 f'<tr><th>seed</th><td>{c("51〜54")}</td></tr>'),
    'p12': block(f'<tr><th>LLM</th><td>Claude Sonnet（Claude Code の CLI {c("claude -p --model sonnet")}）</td></tr>'
                 f'<tr><th>渡したもの</th><td>台本3本（見せ場の位置が違う）と、出させ方2種（座標を直接／段と比）の指示。指示の全文は {c("v3poc/p12_layout/out/result.json")} の prompt_A・prompt_B</td></tr>'
                 '<tr><th>回数</th><td>台本ごと・出させ方ごとに8回</td></tr>', common=False, one=False),
    'p11': block('<tr><th>LLM</th><td>Claude Sonnet と Opus（Claude Code の CLI で画像を読ませる）</td></tr>'
                 '<tr><th>読む順</th><td>番号のない四角いコマ割りの図8種（下の図はその一部）を見せて、読む順を答えさせた。各2回</td></tr>'
                 '<tr><th>向き・角度・距離</th><td>「指示どおりか」の試作の絵59枚を見せ、5択ずつで答えさせた。正解は Claude（Opus）の目の判定</td></tr>', common=False, one=False),
    'p06': block(f'<tr><th>検出のモデル</th><td>MagiV2（{c("ragavsachdeva/magiv2")}。<span class="bad">非営利だけ</span>。文字の読み取りは切った）</td></tr>'
                 '<tr><th>渡したページ</th><td>プログラムで描いた合成ページ4枚（四角・斜めの区切り・斜めが多い・重ね）、生成したページ12枚、実際の漫画のページ9枚（他人の作品なので載せない）</td></tr>',
                 common=False, one=False),
}


def main():
    global s
    if 'class="cond"' in s:
        print('入れ済み')
        return
    for k, v in COND.items():
        m = re.search(rf'<section id="{k}">\s*<h2>.*?</h2>\s*<p class="rows">.*?</p>', s, re.S)
        assert m, k
        s = s[:m.end()] + '\n  ' + v + s[m.end():]
    s = s.replace('.note{', '.cond{margin:6px 0 10px;font-size:13px}\n.cond summary{cursor:pointer;color:var(--acc);font-weight:600}\n'
                  '.cond th{white-space:nowrap}\n.cond td code{word-break:break-word}\n.note{', 1)
    p.write_text(s, encoding='utf-8')
    print('ok', len(COND))


if __name__ == '__main__':
    main()
