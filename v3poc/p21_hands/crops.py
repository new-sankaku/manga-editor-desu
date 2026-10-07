"""P21 手の切り抜きだけを大きく並べた一覧 out/crops_<人物>.png（目の判定用）。analyze.py の後に動かす（out/hands.json を使う）。
使い方: python crops.py"""
import json
import pathlib

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
S = 170
COLS = 7


def main():
    hands = json.loads((OUT / 'hands.json').read_text(encoding='utf-8'))
    for c in ['f1', 'f2', 'm1', 'm2']:
        tiles = []
        for f, hs in hands.items():
            if not f.startswith(c + '_'):
                continue
            im = Image.open(OUT / f).convert('RGB')
            for k, ((x0, y0, x1, y1), s) in enumerate(hs[:3]):
                m = int(0.25 * max(x1 - x0, y1 - y0))
                cr = im.crop((max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, im.width), min(y1 + m, im.height)))
                cr.thumbnail((S, S))
                t = Image.new('RGB', (S, S + 14), 'white')
                t.paste(cr, (0, 14))
                ImageDraw.Draw(t).text((2, 1), f'{f[3:-4]}#{k}', fill='black')
                tiles.append(t)
        rows = (len(tiles) + COLS - 1) // COLS
        sh = Image.new('RGB', (COLS * (S + 4), rows * (S + 18)), 'white')
        for i, t in enumerate(tiles):
            sh.paste(t, ((i % COLS) * (S + 4), (i // COLS) * (S + 18)))
        sh.save(OUT / f'crops_{c}.png')


if __name__ == '__main__':
    main()
