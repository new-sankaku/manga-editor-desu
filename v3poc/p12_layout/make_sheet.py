"""P12 の結果を目で見る一覧画像にする。台本ごとに、座標を直接（A）と段と比（B）を8回ずつ並べる。検査で落ちたものは赤枠。"""
import json
import pathlib

from PIL import Image, ImageDraw

import sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import font  # noqa: E402

OUT = HERE / 'out'
d = json.loads((OUT / 'result.json').read_text(encoding='utf-8'))
S = 0.9
TW, TH = int(150 * S) + 10, int(220 * S) + 26
rows = [(s, m) for s in d['scripts'] for m in 'AB']
im = Image.new('RGB', (190 + 8 * TW, len(rows) * TH + 10), 'white')
dr = ImageDraw.Draw(im)
f, fs = font(14), font(11)
for i, (s, m) in enumerate(rows):
    y0 = 5 + i * TH
    dr.text((6, y0 + 80), f'{s}\n{"A 座標を直接" if m == "A" else "B 段と比"}', fill='black', font=f)
    rs = sorted([r for r in d['results'] if r['script'] == s and r['method'] == m], key=lambda r: r['run'])
    for j, r in enumerate(rs):
        x0 = 190 + j * TW
        bad = not r['check'].get('ok')
        dr.rectangle((x0, y0, x0 + 150 * S, y0 + 220 * S), outline='#c33' if bad else '#bbb', width=3 if bad else 1)
        for p in r['panels']:
            dr.rectangle((x0 + p['x'] * S, y0 + p['y'] * S, x0 + (p['x'] + p['w']) * S, y0 + (p['y'] + p['h']) * S), outline='black', width=2)
            dr.text((x0 + (p['x'] + p['w'] / 2) * S - 4, y0 + (p['y'] + p['h'] / 2) * S - 7), str(p['n']), fill='black', font=f)
        dr.text((x0, y0 + 220 * S + 4), '順番の崩れ' if r['check'].get('order_breaks') else '', fill='#c33', font=fs)
im.save(OUT / 'sheet.png')
print('ok')
