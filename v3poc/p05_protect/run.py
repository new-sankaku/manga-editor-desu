"""P5 人が直した範囲を、AIの描き直しから守れるか（一覧 1-24、3-13）。
元の絵に「人の線」を描き足し、別の範囲だけAIに描き直させる。人の範囲がどれだけ変わったかを画素で数える。
 a: 描き直す範囲だけ変える指定（潜在空間のマスク）のみ
 b: aの後で、範囲の外を元の画素で貼り戻す
 c: 描き直す範囲が誤って人の範囲に掛かった場合（検査で見つけられるか）"""
import io
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
BASE = HERE.parent / 'p02_instruction' / 'out' / 'upper_body_1001.png'
HUMAN = (60, 60, 420, 330)      # 人が直した範囲（左上）
AI_OK = (0, 760, 832, 1216)     # AIに描き直させる範囲（下）
AI_BAD = (0, 250, 832, 1216)    # 誤って人の範囲に掛かった描き直し
POS = 'masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, holding a book, school blazer'


def prep():
    im = Image.open(BASE).convert('RGB')
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = HUMAN
    d.rectangle(HUMAN, fill='white')
    for k in range(9):  # 人の描いた線の代わり：細い線と太い線、斜線
        d.line((x0 + 10, y0 + 20 + k * 28, x1 - 10, y0 + 10 + k * 30), fill='black', width=1 + k % 3)
    d.ellipse((x0 + 120, y0 + 60, x0 + 240, y0 + 180), outline='black', width=3)
    im.save(OUT / 'input.png')
    for name, box in (('mask_ok', AI_OK), ('mask_bad', AI_BAD)):
        m = Image.new('RGB', im.size, 'black')
        ImageDraw.Draw(m).rectangle(box, fill='white')
        m.save(OUT / f'{name}.png')
    return im


def graph(img_name, mask_name, composite):
    g = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': comfy.CKPT}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': POS, 'clip': ['1', 1]}},
        '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': comfy.NEG, 'clip': ['1', 1]}},
        '10': {'class_type': 'LoadImage', 'inputs': {'image': img_name}},
        '11': {'class_type': 'LoadImage', 'inputs': {'image': mask_name}},
        '12': {'class_type': 'ImageToMask', 'inputs': {'image': ['11', 0], 'channel': 'red'}},
        '13': {'class_type': 'VAEEncode', 'inputs': {'pixels': ['10', 0], 'vae': ['1', 2]}},
        '14': {'class_type': 'SetLatentNoiseMask', 'inputs': {'samples': ['13', 0], 'mask': ['12', 0]}},
        '5': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0], 'latent_image': ['14', 0],
                                                    'seed': 77, 'steps': 25, 'cfg': 5.0, 'sampler_name': 'euler_ancestral', 'scheduler': 'normal', 'denoise': 0.85}},
        '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
    }
    src = ['6', 0]
    if composite:
        g['15'] = {'class_type': 'ImageCompositeMasked', 'inputs': {'destination': ['10', 0], 'source': ['6', 0], 'x': 0, 'y': 0, 'resize_source': False, 'mask': ['12', 0]}}
        src = ['15', 0]
    g['7'] = {'class_type': 'SaveImage', 'inputs': {'images': src, 'filename_prefix': 'v3poc_p05'}}
    return g


def measure(inp, out):
    a = np.asarray(inp).astype(np.int16)
    b = np.asarray(out.convert('RGB')).astype(np.int16)
    x0, y0, x1, y1 = HUMAN
    ra, rb = a[y0:y1, x0:x1], b[y0:y1, x0:x1]
    d = np.abs(ra - rb).max(axis=2)
    ink = ra.mean(axis=2) < 100  # 人の線の画素
    lost = ink & (rb.mean(axis=2) > 150)
    return {'max_diff': int(d.max()), 'changed_px_ratio_gt8': round(float((d > 8).mean()), 5),
            'changed_px_ratio_gt0': round(float((d > 0).mean()), 5),
            'ink_px': int(ink.sum()), 'ink_lost_ratio': round(float(lost.sum() / max(1, ink.sum())), 5)}


def main():
    inp = prep()
    img = comfy.upload(str(OUT / 'input.png'), 'v3poc_p05_input.png')
    res = {}
    for name, mask, comp in (('a_mask_only', 'mask_ok', False), ('b_mask_composite', 'mask_ok', True), ('c_bad_mask_composite', 'mask_bad', True)):
        m = comfy.upload(str(OUT / f'{mask}.png'), f'v3poc_p05_{mask}.png')
        b, t = comfy.run(graph(img, m, comp))
        (OUT / f'{name}.png').write_bytes(b[0])
        res[name] = measure(inp, Image.open(io.BytesIO(b[0])))
        res[name]['sec'] = round(t, 1)
    (OUT / 'result.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
