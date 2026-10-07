"""P47 吹き出しが顔を隠したことを、仕上がった絵だけから見つけられるか（一覧 3-15 の残り）。画像生成は使わない。
P02 の作り済みの絵（寄り・上半身など全身以外）で顔を検出し、その顔に白い楕円の吹き出し（黒い縁、文字の代わりに縦の線）を重ねる。
吹き出しを横にずらして、顔の枠が隠れる割合を 0〜100% の6段にする。重ねた絵でもう一度顔を検出し、元の顔の枠と重なる顔が見つかるかを数える。
吹き出しを置く側（ハーネス）は重ねる前の顔の枠を知っているので、重なりの計算だけで分かる。ここで確かめるのは、
取り込んだページや平らにした絵のように、重ねる前が無いときにも顔の検出だけで隠れを見つけられるか。
結果は out/result.json と out/sheet.png（段ごとの例）。
使い方: <検出器の仮想環境の python> run.py"""
import json
import pathlib

import numpy as np
from imgutils.detect import detect_faces
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
V = HERE.parent
CONF = 0.3
STEPS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    i = max(0, x1 - x0) * max(0, y1 - y0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u else 0


def balloon(im, face, target):
    """顔の枠の target の割合が隠れるよう、楕円を横にずらして置く。実際に隠れた割合を返す。"""
    fx0, fy0, fx1, fy1 = face
    fw, fh = fx1 - fx0, fy1 - fy0
    bw, bh = fw * 1.5, fh * 1.5
    cy = (fy0 + fy1) / 2
    best = None
    for dx in np.linspace(0, fw * 1.6 + bw / 2, 80):
        cx = (fx0 + fx1) / 2 + dx
        m = Image.new('L', im.size, 0)
        ImageDraw.Draw(m).ellipse((cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2), fill=255)
        a = np.asarray(m.crop(tuple(int(v) for v in face))) > 0
        cov = float(a.mean())
        if best is None or abs(cov - target) < abs(best[0] - target):
            best = (cov, cx)
    cov, cx = best
    out = im.copy()
    d = ImageDraw.Draw(out)
    box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    d.ellipse(box, fill='white', outline='black', width=max(2, int(fw / 40)))
    for k in range(4):
        x = cx + bw * (0.2 - 0.13 * k)
        d.line((x, cy - bh * 0.28, x, cy + bh * 0.28), fill='black', width=max(2, int(fw / 30)))
    return out, cov


def main():
    fs = sorted(p for p in (V / 'p02_instruction/out').glob('*.png') if not p.name.startswith('full_body'))
    rows, examples = [], {}
    for p in fs:
        im = Image.open(p).convert('RGB')
        fsd = [d for d in detect_faces(im) if d[2] >= CONF]
        if not fsd:
            rows.append({'file': p.name, 'face': None})
            continue
        face = max(fsd, key=lambda d: (d[0][2] - d[0][0]) * (d[0][3] - d[0][1]))[0]
        r = {'file': p.name, 'face': face, 'steps': []}
        for t in STEPS:
            b, cov = balloon(im, face, t)
            hit = [d for d in detect_faces(b) if d[2] >= CONF and iou(d[0], face) > 0.3]
            r['steps'].append({'target': t, 'covered': round(cov, 2), 'found': bool(hit), 'conf': round(max((d[2] for d in hit), default=0), 3)})
            if t not in examples or len(examples[t]) < 3:
                examples.setdefault(t, []).append((b, face, bool(hit)))
        rows.append(r)
    have = [r for r in rows if r['face']]
    summ = {str(t): {'found': sum(1 for r in have if r['steps'][i]['found']), 'of': len(have),
                     'covered_median': float(np.median([r['steps'][i]['covered'] for r in have]))} for i, t in enumerate(STEPS)}
    S = 180
    sh = Image.new('RGB', (len(STEPS) * (S + 6), 3 * (S + 18)), 'white')
    for i, t in enumerate(STEPS):
        for j, (b, face, hit) in enumerate(examples.get(t, [])):
            fx0, fy0, fx1, fy1 = face
            w = (fx1 - fx0) * 1.6
            c = b.crop((int(fx0 - w * 0.6), int(fy0 - w * 0.6), int(fx1 + w * 1.4), int(fy1 + w * 0.6)))
            c.thumbnail((S, S))
            sh.paste(c, (i * (S + 6), j * (S + 18) + 16))
            ImageDraw.Draw(sh).text((i * (S + 6) + 2, j * (S + 18) + 2), f'{int(t * 100)}% {"found" if hit else "lost"}', fill='black')
    sh.save(OUT / 'sheet.png')
    (OUT / 'result.json').write_text(json.dumps({'conf': CONF, 'images': len(fs), 'face_found_before': len(have), 'summary': summ, 'rows': rows},
                                                ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(fs), len(have))
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
