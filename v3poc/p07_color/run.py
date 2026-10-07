"""P7 カラーで色がごてごてするか。cfgで彩度がどう動くか。数値で「多すぎる」を測れるか（一覧 1-11、3-14、6-5）。
cfg 3/5/7/9/12 × seed4。HSVの彩度の平均と、彩度0.8超えの画素の割合を出す。"""
import io
import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

OUT = pathlib.Path(__file__).with_name('out')
OUT.mkdir(exist_ok=True)
POS = 'masterpiece, best quality, anime coloring, 1girl, solo, short black bob hair, glasses, school blazer, red necktie, upper body, classroom, afternoon'


def sat(b):
    hsv = np.asarray(Image.open(io.BytesIO(b)).convert('HSV')).astype(np.float32) / 255
    s, v = hsv[..., 1], hsv[..., 2]
    return {'sat_mean': round(float(s.mean()), 3), 'sat_gt08': round(float((s > 0.8).mean()), 3), 'val_mean': round(float(v.mean()), 3)}


def main():
    rec = []
    for cfg in (3, 5, 7, 9, 12):
        for s in (31, 32, 33, 34):
            b, t = comfy.run(comfy.t2i(POS, s, cfg=cfg, prefix='v3poc_p07'))
            name = f'cfg{cfg}_{s}.png'
            (OUT / name).write_bytes(b[0])
            rec.append({'file': name, 'cfg': cfg, 'seed': s, **sat(b[0])})
            print(rec[-1], flush=True)
    summ = {}
    for cfg in (3, 5, 7, 9, 12):
        rs = [r for r in rec if r['cfg'] == cfg]
        summ[cfg] = {k: round(sum(r[k] for r in rs) / len(rs), 3) for k in ('sat_mean', 'sat_gt08', 'val_mean')}
    (OUT / 'result.json').write_text(json.dumps({'summary': summ, 'runs': rec}, indent=1), encoding='utf-8')
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
