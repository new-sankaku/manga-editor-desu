"""P48 MagiV2 の人物の検出は、カラーの絵と人のいない背景で当たるか（一覧 3-6 の残り）。画像生成は使わない。
絵：P15 の4つの描き方（カラー・ペン・レトロ・トーン）× 人物あり4種（全身・人物だけ・横の引き・縦の引き）と背景だけ3種、各3枚。
P16 の人のいない背景18枚、P18 の教室・街の背景。人物ありは1人、背景だけは0人が正解（作るときの指示。背景だけで人が描かれていないかは一覧画像で目で見た）。
MagiV2 は読み込むときに白黒にしてから見る（v3poc/common/magi.py）。カラーの絵も白黒にした形で渡している。
使い方: v3poc で <venv_magiのpython> common/magi.py p48_magi_color/out/magi.json に、p15_shots/out/{color,pen,retro,tone}_*.png（_cut を除く）・
p16_general/out/bg_*_none_*.png・p18_bg_consistency/out/*.png（sheet と aux を除く）を渡す → python analyze.py"""
import json
import pathlib
import re
from collections import defaultdict

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'


def group(f):
    n = pathlib.Path(f).name
    m = re.match(r'(color|pen|retro|tone)_(bg_std|bg_tate|bg_yoko|chara_only|full_std|long_tate|long_yoko)_\d+\.png', n)
    if m:
        return ('p15_' + m.group(1), m.group(2), 0 if m.group(2).startswith('bg_') else 1)
    if n.startswith('bg_'):
        return ('p16', 'bg_none', 0)
    return ('p18', n.split('_')[0] + '_bg', 0)


def main():
    rs = json.loads((OUT / 'magi.json').read_text(encoding='utf-8'))
    tab = defaultdict(lambda: {'n': 0, 'ok': 0, 'counts': []})
    wrong = []
    for r in rs:
        src, kind, want = group(r['file'])
        c = len(r['characters'])
        k = f'{src}|{kind}'
        tab[k]['n'] += 1
        tab[k]['ok'] += c == want
        tab[k]['counts'].append(c)
        if c != want:
            wrong.append((r, want))
    # 描き方ごと・人物あり/なしごと
    by = defaultdict(lambda: [0, 0])
    for k, v in tab.items():
        src, kind = k.split('|')
        key = f'{src}|{"0人" if kind.startswith("bg") or kind.endswith("_bg") else "1人"}'
        by[key][0] += v['ok']
        by[key][1] += v['n']
    # 外れた絵に枠を重ねた一覧（目で見る用）
    S = 220
    cols = 6
    sh = Image.new('RGB', (cols * (S + 6), ((len(wrong) + cols - 1) // cols) * (S + 18) + 2), 'white')
    for i, (r, want) in enumerate(wrong):
        im = Image.open(HERE.parent / r['file']).convert('RGB')
        d = ImageDraw.Draw(im)
        for b in r['characters']:
            d.rectangle(b, outline=(255, 0, 0), width=max(3, im.width // 200))
        im.thumbnail((S, S))
        X, Y = (i % cols) * (S + 6), (i // cols) * (S + 18)
        sh.paste(im, (X, Y + 16))
        ImageDraw.Draw(sh).text((X + 2, Y + 2), f'{pathlib.Path(r["file"]).name[:26]} {len(r["characters"])}/{want}', fill='black')
    sh.save(OUT / 'sheet_wrong.png')
    res = {'by_group': {k: f'{v[0]}/{v[1]}' for k, v in sorted(by.items())},
           'by_kind': {k: {'ok': v['ok'], 'n': v['n'], 'counts': v['counts']} for k, v in sorted(tab.items())},
           'wrong': [{'file': pathlib.Path(r['file']).name, 'want': w, 'got': len(r['characters'])} for r, w in wrong]}
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in res['by_group'].items():
        print(k, v)
    for k, v in res['by_kind'].items():
        print(k, v['ok'], '/', v['n'], v['counts'])


if __name__ == '__main__':
    main()
