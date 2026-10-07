"""P42 全身を描いたとき、顔と手が崩れないか（一覧 1-3）。新しい絵は作らず、作り済みの全身の絵から顔と手を原寸で切り出して目で見る。
使う絵：P02 の全身（8枚）、P16 の標準の形の全身（狙いどおりだった絵）、P24 の通常の全身（12枚）。
一覧：out/sheet_faces.png・out/sheet_hands.png。目の判定は out/labels.json。
使い方: <検出器の仮想環境の python> run.py"""
import json
import pathlib

from PIL import Image, ImageDraw
from imgutils.detect import detect_faces, detect_hands

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
V = HERE.parent
S = 150


def sources():
    fs = sorted((V / 'p02_instruction' / 'out').glob('full_body_*.png'))
    lab = json.loads((V / 'p16_general' / 'out' / 'labels.json').read_text(encoding='utf-8'))
    bad = set(lab['ng']) | set(lab['part'])
    fs += [p for p in sorted((V / 'p16_general' / 'out').glob('full_std_*.png')) if p.name not in bad and not p.name.endswith('_cut.png')]
    fs += sorted((V / 'p24_deform' / 'out').glob('[ab]_normal_*.png'))
    return fs


def crops(p, dets, k):
    im = Image.open(p).convert('RGB')
    out = []
    for i, ((x0, y0, x1, y1), _, s) in enumerate(sorted(dets, key=lambda d: -d[2])[:k]):
        m = int(0.3 * max(x1 - x0, y1 - y0))
        c = im.crop((max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, im.width), min(y1 + m, im.height)))
        c = c.resize((S, round(S * c.height / c.width))) if c.width < c.height else c.resize((round(S * c.width / c.height), S))
        c.thumbnail((S, S))
        out.append((c, f'{p.parent.parent.name[:3]} {p.stem[-12:]}#{i} {x1 - x0}px'))
    return out


def grid(tiles, path, cols=8):
    rows = (len(tiles) + cols - 1) // cols
    sh = Image.new('RGB', (cols * (S + 4), rows * (S + 18)), 'white')
    for i, (c, t) in enumerate(tiles):
        x, y = (i % cols) * (S + 4), (i // cols) * (S + 18)
        sh.paste(c, (x, y + 16))
        ImageDraw.Draw(sh).text((x + 2, y + 2), t[:26], fill='black')
    sh.save(path)


def main():
    faces, hands, meta = [], [], {}
    for p in sources():
        f = [d for d in detect_faces(str(p)) if d[2] >= 0.3]
        h = [d for d in detect_hands(str(p)) if d[2] >= 0.35]
        meta[f'{p.parent.parent.name}/{p.name}'] = {'faces': len(f), 'hands': len(h), 'face_px': [int(d[0][2] - d[0][0]) for d in f],
                                                    'size': list(Image.open(p).size)}
        faces += crops(p, f, 1)
        hands += crops(p, h, 2)
    grid(faces, OUT / 'sheet_faces.png')
    grid(hands, OUT / 'sheet_hands.png')
    (OUT / 'detect.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
    print(len(meta), 'images', len(faces), 'faces', len(hands), 'hands')


if __name__ == '__main__':
    main()
