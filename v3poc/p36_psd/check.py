"""P36 別の読み手（psd-tools、MIT）で layers.psd を読む。層の名前・入れ子・表示・合成の方法・画素・文字の中身と、
psd-tools が層を重ねて作った絵が、手1で重ね直した絵（expected_mono.png）と合うか。
使い方: <検出器の仮想環境の python> check.py"""
import json
import pathlib

import numpy as np
from PIL import Image
from psd_tools import PSDImage

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
SRC = {'紙': 'paper.png', '着彩': 'color.png', 'トーン': 'tone.png', 'ベタ': 'beta.png', '線画': 'line.png'}


def main():
    psd = PSDImage.open(OUT / 'layers.psd')
    rows = []
    for layer in psd.descendants():
        r = {'name': layer.name, 'kind': layer.kind, 'visible': layer.visible, 'blend': str(layer.blend_mode)}
        if layer.name in SRC:
            a = np.asarray(Image.open(OUT / 'layers' / SRC[layer.name]).convert('RGBA'))
            b = np.asarray(layer.topil().convert('RGBA'))
            r['pixel_diff'] = int((a != b).sum()) if a.shape == b.shape else -1
        if layer.kind == 'type':
            r['text'] = layer.text
        rows.append(r)
    comp = psd.composite(force=True, ignore_preview=True, layer_filter=lambda x: x.is_visible() and x.kind != 'type')
    exp = np.asarray(Image.open(OUT / 'layers' / 'expected_mono.png').convert('L')).astype(np.int16)
    got = np.asarray(comp.convert('L')).astype(np.int16)
    comp.save(OUT / 'psdtools_composite.png')
    res = {'layers': rows, 'composite_mean_abs_diff': round(float(np.abs(exp - got).mean()), 2), 'composite_max_diff': int(np.abs(exp - got).max())}
    (OUT / 'psdtools_readback.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
