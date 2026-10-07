"""P26 画像編集（Qwen-Image 2.1）で、写真風にならないか・白黒が保たれるか・同じ人物のままか・頼んでいない所が変わらないか（一覧 1-15・1-17）。
数えるもの：写実の判定（P35 の anime_real）、色の量（彩度の平均）、同一キャラ判定（CCIP、元の絵と比べる）、
人物の枠（元の絵で検出）の外側で画素がどれだけ変わったか（背景を変える編集以外）。一覧は out/sheet_<人物>.png（左端が元の絵）。
画像生成を途中で止めたので、b の座る・後ろ姿・背景の編集は作っていない（14枚）。
使い方: <検出器の仮想環境の python> analyze.py"""
import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw
from imgutils.detect import detect_person
from imgutils.metrics import ccip_default_threshold, ccip_difference, ccip_extract_feature
from imgutils.validate import anime_real_score

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
P17 = HERE.parent / 'p17_identity2' / 'out'
SRC = {'a': 'a_full_none_eat_21.png', 'b': 'b_full_none_run_21.png'}
TH = 300


def sat(im):
    hsv = np.asarray(im.convert('HSV')).astype(np.float32)
    return round(float(hsv[..., 1].mean() / 255), 3)


def main():
    th = ccip_default_threshold()
    rows = []
    for c, s in SRC.items():
        src = Image.open(P17 / s).convert('RGB')
        feat = ccip_extract_feature(str(P17 / s))
        (x0, y0, x1, y1), _, _ = max(detect_person(str(P17 / s)), key=lambda x: x[2])
        tiles = [(src, 'source')]
        for p in sorted(OUT.glob(f'{c}_*.png')):
            im = Image.open(p).convert('RGB')
            d = float(ccip_difference(feat, ccip_extract_feature(str(p))))
            a = np.asarray(src.resize(im.size)).astype(np.int16)
            b = np.asarray(im).astype(np.int16)
            sx, sy = im.width / src.width, im.height / src.height
            mask = np.ones(b.shape[:2], bool)
            mask[int(y0 * sy):int(y1 * sy), int(x0 * sx):int(x1 * sx)] = False
            outside = float((np.abs(a - b).max(axis=2)[mask] > 40).mean())
            r = {'file': p.name, 'edit': p.stem.split('_')[1], 'real': round(float(anime_real_score(str(p)).get('real', 0)), 3),
                 'saturation': sat(im), 'source_saturation': sat(src), 'ccip_diff': round(d, 3), 'same_person': d < th,
                 'changed_outside_person': round(outside, 3), 'size': list(im.size)}
            rows.append(r)
            tiles.append((im, f"{p.stem} real={r['real']:.2f} out={outside:.2f}"))
        ims = [(im.resize((round(im.width * TH / im.height), TH)), t) for im, t in tiles]
        sh = Image.new('RGB', (sum(i.width + 4 for i, _ in ims), TH + 16), 'white')
        x = 0
        for im, t in ims:
            sh.paste(im, (x, 16))
            ImageDraw.Draw(sh).text((x + 2, 2), t, fill='black')
            x += im.width + 4
        sh.save(OUT / f'sheet_{c}.png')
    res = {'threshold': th, 'rows': rows, 'n': len(rows), 'same_person': sum(r['same_person'] for r in rows),
           'max_real': max(r['real'] for r in rows), 'max_saturation': max(r['saturation'] for r in rows)}
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    for r in rows:
        print(r)


if __name__ == '__main__':
    main()
