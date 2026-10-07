"""P23 目で見る一覧（組ごとに、1つの文／範囲ごとの文 × seed 6）と、カラーの組の髪の色を画素で測る（一覧 3-9）。
髪の色：人物の頭を検出（dghs-imgutils の detect_heads）し、頭の枠の中で色の濃い画素の色相を数える。赤（色相0〜20・340〜360）と青（色相190〜250）の画素の割合を、
左の頭と右の頭それぞれで出す。狙いは左が赤、右が青。
目の判定は out/labels.json：{"<ファイル名>": {"people": 人数, "mixed": 特徴が混ざったか, "swap": 左右が入れ替わったか, "page": コマ割りのページになったか, "note": ""}}
使い方: <検出器の仮想環境の python> analyze.py"""
import colorsys
import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw
from imgutils.detect import detect_heads

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
PAIRS = ['ab', 'sim', 'color']
SEEDS = list(range(71, 77))
TW = 300


def hair(im, box):
    a = np.asarray(im.crop(box).convert('RGB')).reshape(-1, 3) / 255.0
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in a[::4]])
    sat = hsv[(hsv[:, 1] > 0.35) & (hsv[:, 2] > 0.2)]
    if not len(sat):
        return {'red': 0.0, 'blue': 0.0}
    h = sat[:, 0] * 360
    return {'red': round(float(((h < 20) | (h > 340)).mean()), 3), 'blue': round(float(((h > 190) & (h < 250)).mean()), 3)}


def main():
    colors = {}
    for k in PAIRS:
        rows = []
        for mode in ('one', 'area'):
            ims = []
            for s in SEEDS:
                p = OUT / f'{k}_{mode}_{s}.png'
                im = Image.open(p).convert('RGB')
                if k == 'color':
                    heads = sorted(detect_heads(str(p)), key=lambda x: x[0][0])
                    colors[p.name] = [{'x': int(b[0]), **hair(im, b)} for b, _, _ in heads]
                t = im.resize((TW, round(im.height * TW / im.width)))
                ImageDraw.Draw(t).rectangle([0, 0, 90, 12], fill='white')
                ImageDraw.Draw(t).text((2, 1), f'{mode} {s}', fill='black')
                ims.append(t)
            rows.append(ims)
        sh = Image.new('RGB', (6 * (TW + 4), 2 * (rows[0][0].height + 4)), 'white')
        for r, ims in enumerate(rows):
            for i, t in enumerate(ims):
                sh.paste(t, (i * (TW + 4), r * (t.height + 4)))
        sh.save(OUT / f'sheet_{k}.png')
    (OUT / 'hair_color.json').write_text(json.dumps(colors, indent=1), encoding='utf-8')
    # 画素での判定：頭が2つ以上あり、左端の頭が赤優勢・右端の頭が青優勢なら「狙いどおり」
    judge = {}
    for f, hs in colors.items():
        if len(hs) < 2:
            judge[f] = 'heads<2'
            continue
        l, r = hs[0], hs[-1]
        judge[f] = 'ok' if l['red'] > l['blue'] and r['blue'] > r['red'] else ('swap' if l['blue'] > l['red'] and r['red'] > r['blue'] else 'mixed')
    res = {'pixel_judge': judge}
    lab_p = OUT / 'labels.json'
    if lab_p.exists():
        lab = json.loads(lab_p.read_text(encoding='utf-8'))
        for k in PAIRS:
            for mode in ('one', 'area'):
                fs = [f'{k}_{mode}_{s}.png' for s in SEEDS]
                res[f'{k}_{mode}'] = {'two_people': sum(1 for f in fs if lab[f]['people'] == 2), 'mixed': sum(1 for f in fs if lab[f]['mixed']),
                                      'swap': sum(1 for f in fs if lab[f]['swap']),
                                      'page': sum(1 for f in fs if lab[f].get('page')),
                                      'ok': sum(1 for f in fs if lab[f]['people'] == 2 and not lab[f]['mixed'] and not lab[f]['swap'] and not lab[f].get('page'))}
        cf = [f for f in judge]
        # 画素で見ているのは髪の色の左右だけ。目の判定の「左右が逆」「3人目がいる」とだけ突き合わせる
        res['pixel_vs_eye_hair_side'] = {'agree': sum(1 for f in cf if (judge[f] == 'ok') == (not lab[f]['swap'] and lab[f]['people'] == 2)), 'n': len(cf)}
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
