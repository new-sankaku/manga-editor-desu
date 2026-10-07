"""画像フォルダの人物・顔を検出して数値にする（dghs-imgutils、CPUで動く）。
使い方: python detect.py <画像フォルダ> <出力JSON>"""
import json
import os
import pathlib
import sys

os.environ.setdefault('ONNXRUNTIME_PROVIDERS', 'CPUExecutionProvider')
from PIL import Image  # noqa: E402
from imgutils.detect import detect_faces, detect_person, detect_heads  # noqa: E402

EDGE = 3  # 端に接したとみなす画素


def one(p):
    im = Image.open(p)
    w, h = im.size
    per = detect_person(im)
    fac = detect_faces(im)
    hed = detect_heads(im)

    def box(b):
        (x0, y0, x1, y1), _, sc = b
        return {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'score': round(sc, 3),
                'h_ratio': round((y1 - y0) / h, 3), 'area_ratio': round((x1 - x0) * (y1 - y0) / (w * h), 3),
                'touch': ''.join(k for k, v in (('T', y0 <= EDGE), ('B', y1 >= h - EDGE), ('L', x0 <= EDGE), ('R', x1 >= w - EDGE)) if v)}
    return {'file': p.name, 'w': w, 'h': h, 'persons': [box(b) for b in per], 'faces': [box(b) for b in fac], 'heads': [box(b) for b in hed]}


def main(folder, out):
    fs = sorted(pathlib.Path(folder).glob('*.png'))
    res = [one(f) for f in fs]
    pathlib.Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(res), 'images')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
