"""P43 の続き：切り抜いた人物の大きさで、眼鏡の女子生徒とパーカーの少年（P16）を「同じ」と言う割合が変わるか。
人物の枠の高さ（元の絵に対する割合）で、2枚のうち小さい方の大きさごとに数える。
使い方: <検出器の仮想環境の python> size.py"""
import json
import pathlib

import numpy as np
from imgutils.detect import detect_person
from imgutils.metrics import ccip_batch_differences, ccip_default_threshold, ccip_extract_feature
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
P16 = HERE.parent / 'p16_general' / 'out'


def crop(p):
    im = Image.open(p).convert('RGB')
    ds = detect_person(im)
    if not ds:
        return im, 0.0
    (x0, y0, x1, y1), _, _ = max(ds, key=lambda d: d[2])
    m = int(0.1 * max(x1 - x0, y1 - y0))
    return im.crop((max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, im.width), min(y1 + m, im.height))), (y1 - y0) / im.height


def main():
    th = ccip_default_threshold()
    items = []
    for c in ('girl', 'boy'):
        for p in sorted(P16.glob(f'*_{c}_*.png')):
            if p.stem.endswith('_cut'):
                continue
            im, h = crop(p)
            items.append((c, p.name, h, ccip_extract_feature(im)))
    d = ccip_batch_differences([x[3] for x in items])
    rows = []
    for i, a in enumerate(items):
        for j, b in enumerate(items):
            if a[0] == 'girl' and b[0] == 'boy':
                rows.append((min(a[2], b[2]), d[i, j] < th))
    res = {}
    for lo, hi in ((0, 0.2), (0.2, 0.4), (0.4, 0.7), (0.7, 1.01)):
        xs = [s for h, s in rows if lo <= h < hi]
        res[f'{lo}-{hi}'] = {'pairs': len(xs), 'same_rate': round(float(np.mean(xs)), 3) if xs else None}
    (HERE / 'out' / 'size.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(res)


if __name__ == '__main__':
    main()
