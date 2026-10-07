"""P4 大きさと時間（一覧 6-1）、書き出しの大きさへの拡大で線が保たれるか（一覧 1-26、1-13）。
1) 3つの大きさ × seed3 で生成時間と破綻（目で見る）を記録
2) 832x1216の1枚を、拡大部品3種と単純な拡大で B5 600dpi（4300x6070）へ。時間と、線の部分の切り抜きを残す"""
import io
import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
POS = 'masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, solo, short black bob hair, glasses, school blazer, red necktie, full body, standing, street, detailed background'
SIZES = [(640, 960), (832, 1216), (1024, 1536)]
TARGET = (4300, 6070)
UPS = ['4x-UltraSharp.pth', 'RealESRGAN_x4plus_anime_6B.pth', 'RealESRGAN_x4plus.pth']


def up_graph(img, model):
    g = {'10': {'class_type': 'LoadImage', 'inputs': {'image': img}}}
    src = ['10', 0]
    if model:
        g['11'] = {'class_type': 'UpscaleModelLoader', 'inputs': {'model_name': model}}
        g['12'] = {'class_type': 'ImageUpscaleWithModel', 'inputs': {'upscale_model': ['11', 0], 'image': src}}
        src = ['12', 0]
    g['13'] = {'class_type': 'ImageScale', 'inputs': {'image': src, 'upscale_method': 'lanczos', 'width': TARGET[0], 'height': TARGET[1], 'crop': 'disabled'}}
    g['14'] = {'class_type': 'SaveImage', 'inputs': {'images': ['13', 0], 'filename_prefix': 'v3poc_p04up'}}
    return g


def sharp(a):
    g = a.astype(np.float32)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return round(float(lap.var()), 1)


def main():
    rec = {'gen': [], 'upscale': []}
    comfy.run(comfy.t2i(POS, 1, 832, 1216, prefix='v3poc_p04'))  # 読み込みを済ませる
    for w, h in SIZES:
        for s in (41, 42, 43):
            b, t = comfy.run(comfy.t2i(POS, s, w, h, prefix='v3poc_p04'))
            (OUT / f'gen_{w}x{h}_{s}.png').write_bytes(b[0])
            rec['gen'].append({'size': f'{w}x{h}', 'mpx': round(w * h / 1e6, 2), 'seed': s, 'sec': round(t, 2)})
            print(rec['gen'][-1], flush=True)
    src = OUT / 'gen_832x1216_41.png'
    img = comfy.upload(str(src), 'v3poc_p04_src.png')
    crop = (1500, 1200, 2300, 2000)  # 拡大後の同じ場所（顔と服の線のあたり）
    for m in [None] + UPS:
        b, t = comfy.run(up_graph(img, m))
        im = Image.open(io.BytesIO(b[0])).convert('L')
        name = (m or 'lanczos').split('.')[0]
        c = im.crop(crop)
        c.save(OUT / f'up_{name}_crop.png')
        rec['upscale'].append({'model': name, 'sec': round(t, 1), 'size': im.size, 'crop_sharpness': sharp(np.asarray(c))})
        print(rec['upscale'][-1], flush=True)
    (OUT / 'result.json').write_text(json.dumps(rec, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
