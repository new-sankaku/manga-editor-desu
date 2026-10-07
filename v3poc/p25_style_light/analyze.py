"""P25 目で見る一覧と、写実の判定（P35 の anime_real）・画風の近さ（P41 の CSD）をまとめる（一覧 1-12・3-10・1-18）。
一覧：out/sheet_style.png（8場面×seed 2と、写実の言葉を足した4場面）、out/sheet_light.png（光の指定なし／左から／右から × seed 4）。
光の向きの目の判定は out/labels.json：{"<ファイル名>": {"light_from": "left|right|none|unclear", "note": ""}}（左右は絵を見る人から見て）
使い方: python analyze.py"""
import json
import pathlib
import statistics as st

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
SC = HERE.parent / 'p35_scorers' / 'out' / 'scores_p25_style_light.json'
TH = 260


def sheet(rows, path):
    w = max(sum(i.width + 4 for i, _ in r) for r in rows)
    sh = Image.new('RGB', (w, len(rows) * (TH + 18)), 'white')
    for y, r in enumerate(rows):
        x = 0
        for im, t in r:
            sh.paste(im, (x, y * (TH + 18) + 16))
            ImageDraw.Draw(sh).text((x + 2, y * (TH + 18) + 2), t, fill='black')
            x += im.width + 4
    sh.save(path)


def th(p):
    im = Image.open(p).convert('RGB')
    return im.resize((round(im.width * TH / im.height), TH))


def main():
    sc = json.loads(SC.read_text(encoding='utf-8'))
    real = lambda f: sc[f]['real'].get('real', 0)
    scenes = ['desk', 'eat', 'night', 'walk', 'phone', 'rain', 'run', 'train']
    rows = [[(th(OUT / f'style_{s}_{sd}.png'), f'{s} {sd} real={real(f"style_{s}_{sd}.png"):.2f}') for s in scenes] for sd in (91, 92)]
    rows.append([(th(OUT / f'real_{s}_91.png'), f'+realistic {s} real={real(f"real_{s}_91.png"):.2f}') for s in scenes[:4]])
    sheet(rows, OUT / 'sheet_style.png')
    sheet([[(th(OUT / f'light_{l}_{s}.png'), f'{l} {s}') for s in (95, 96, 97, 98)] for l in ('none', 'left', 'right')], OUT / 'sheet_light.png')
    res = {'real_score_style_mean': round(st.mean(real(f) for f in sc if f.startswith('style_')), 3),
           'real_score_style_max': round(max(real(f) for f in sc if f.startswith('style_')), 3),
           'real_score_realistic_words': {f: round(real(f), 3) for f in sc if f.startswith('real_')}}
    csd = HERE.parent / 'p41_csd' / 'out' / 'result.json'
    if csd.exists():
        res['csd'] = json.loads(csd.read_text(encoding='utf-8')).get('p25')
    lab_p = OUT / 'labels.json'
    if lab_p.exists():
        lab = json.loads(lab_p.read_text(encoding='utf-8'))
        res['light'] = {l: {v: sum(1 for f in lab if f.startswith(f'light_{l}_') and lab[f]['light_from'] == v) for v in ('left', 'right', 'none', 'unclear')}
                        for l in ('none', 'left', 'right')}
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
