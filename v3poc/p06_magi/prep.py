"""P6 MagiV2 の材料を用意する（一覧 3-6、2-17、1-30、3-16）。
 synth/ : 正解の分かっている合成ページ。四角だけ・斜めの枠・重ねたコマ・断ち切り。コマの中に生成した絵を貼る
 正解は synth/truth.json（コマ数と、読む順に並べた多角形）"""
import json
import pathlib
import random

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
SY = HERE / 'synth'
SY.mkdir(exist_ok=True)
SRC = sorted((HERE.parent / 'p02_instruction' / 'out').glob('*_100*.png'))
S = 5  # 1mm = 5px（B5の基本枠の周りに余白を付けた 182x257mm → 910x1285px）
OX, OY = 16, 18  # 基本枠の左上（mm）

PAGES = {
    'rect': [[(75, 0), (150, 0), (150, 70), (75, 70)], [(0, 0), (73, 0), (73, 70), (0, 70)],
             [(0, 75), (150, 75), (150, 145), (0, 145)], [(77, 150), (150, 150), (150, 220), (77, 220)], [(0, 150), (75, 150), (75, 220), (0, 220)]],
    'diag_row': [[(0, 0), (150, 0), (150, 60), (0, 80)], [(80, 66), (150, 58), (150, 150), (70, 150)], [(0, 86), (76, 67), (66, 150), (0, 150)],
                 [(0, 155), (150, 155), (150, 220), (0, 220)]],
    'diag_many': [[(60, 0), (150, 0), (150, 55), (70, 75)], [(0, 0), (56, 0), (66, 76), (0, 90)], [(0, 95), (150, 60), (150, 120), (0, 150)],
                  [(90, 125), (150, 125), (150, 220), (70, 220)], [(0, 155), (85, 125), (65, 220), (0, 220)]],
    'overlap_bleed': [[(-16, -18), (166, -18), (166, 110), (-16, 110)], [(20, 80), (130, 80), (130, 150), (20, 150)],
                      [(77, 155), (150, 155), (150, 220), (77, 220)], [(0, 155), (75, 155), (75, 220), (0, 220)]],
}


def page(name, polys, rnd):
    im = Image.new('RGB', (182 * S, 257 * S), 'white')
    for poly in polys:
        pts = [((x + OX) * S, (y + OY) * S) for x, y in poly]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        box = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
        art = Image.open(rnd.choice(SRC)).convert('RGB')
        bw, bh = box[2] - box[0], box[3] - box[1]
        sc = max(bw / art.width, bh / art.height)
        art = art.resize((int(art.width * sc) + 1, int(art.height * sc) + 1))
        m = Image.new('L', im.size, 0)
        ImageDraw.Draw(m).polygon(pts, fill=255)
        layer = Image.new('RGB', im.size, 'white')
        layer.paste(art, (box[0], box[1]))
        im.paste(layer, (0, 0), m)
        ImageDraw.Draw(im).polygon(pts, outline='black', width=6)
    im.save(SY / f'{name}.png')


def main():
    rnd = random.Random(5)
    truth = {}
    for n, ps in PAGES.items():
        page(n, ps, rnd)
        truth[n] = {'count': len(ps), 'polys_mm': ps, 'scale_px_per_mm': S, 'origin_mm': [OX, OY]}
    (SY / 'truth.json').write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(truth), 'pages')


if __name__ == '__main__':
    main()
