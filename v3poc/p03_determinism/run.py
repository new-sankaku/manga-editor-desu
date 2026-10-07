"""P3 同じ条件で同じ絵が出るか（一覧 1-28、ComfyUI・このPC）。
同じ依頼を3回（間に別の依頼を挟む）送り、画素の差を数える。"""
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
POS = 'masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, solo, short black bob hair, glasses, school blazer, red necktie, upper body, classroom'


def arr(b):
    return np.asarray(Image.open(io.BytesIO(b)).convert('RGB')).astype(np.int16)


def main():
    res = {}
    for sampler in ('euler_ancestral', 'dpmpp_2m'):
        runs = []
        for i in range(3):
            if i == 2:
                comfy.run(comfy.t2i(POS + ', from side', 7, sampler=sampler, prefix='v3poc_p03'))  # 間に別の依頼
            b, t = comfy.run(comfy.t2i(POS, 4242, sampler=sampler, prefix='v3poc_p03'))
            (OUT / f'{sampler}_{i}.png').write_bytes(b[0])
            runs.append(arr(b[0]))
        diffs = []
        for i in (1, 2):
            d = np.abs(runs[0] - runs[i])
            diffs.append({'max': int(d.max()), 'changed_px_ratio': float((d.max(axis=2) > 0).mean()), 'mean': float(d.mean())})
        res[sampler] = diffs
    (OUT / 'result.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
