"""P36 の下準備：P20 の手1で分けた層（線・ベタ・トーン）と、手2のカラーを、透明付きの PNG にする。
使い方: python prep.py"""
import importlib.util
import pathlib

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
P20 = HERE.parent / 'p20_layers'
_spec = importlib.util.spec_from_file_location('p20a', P20 / 'analyze.py')
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
OUT = HERE / 'out' / 'layers'
OUT.mkdir(parents=True, exist_ok=True)


def rgba(gray_layer):
    """白地に黒の層（透明のところは255）を、黒か灰色＋透明の層にする。"""
    a = (255 - gray_layer).astype(np.uint8)
    rgb = np.zeros(gray_layer.shape + (3,), np.uint8)
    return Image.fromarray(np.dstack([rgb, a]), 'RGBA')


def main():
    tone = A.grey(P20 / 'out' / 'a_desk_tone_41.png')
    size = (tone.shape[1], tone.shape[0])
    line = A.grey(P20 / 'out' / 'a_desk_tone_41_xm2a.png', size)
    l_, b_, t_, rc, _ = A.split(tone, line)
    rgba(l_).save(OUT / 'line.png')
    rgba(b_).save(OUT / 'beta.png')
    rgba(t_).save(OUT / 'tone.png')
    Image.new('RGBA', size, (255, 255, 255, 255)).save(OUT / 'paper.png')
    Image.open(P20 / 'out' / 'a_desk_line2color_41.png').convert('RGBA').save(OUT / 'color.png')
    Image.fromarray(np.clip(rc, 0, 255).astype(np.uint8)).save(OUT / 'expected_mono.png')
    print('ok', size)


if __name__ == '__main__':
    main()
