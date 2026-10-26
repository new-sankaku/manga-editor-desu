"""P62 の続き：骨格の図では横向きの向き（左右）を決められなかった（歩く全身・向かい合う2人が全部右を向いた）。
右向きに出た絵を左右反転して輪郭（Canny）を取り、線の形の指定（union promax の canny）で渡すと、向きを再現できるか。
- profile_walk：歩く全身（profile_walk_C8_2001）を反転 → 左向き
- two_profile：2人（two_profile_C8_2001）の左半分（右を向く人）を反転して右半分に置く → 向かい合う
効きを2段（L6：強さ 0.6・終わり 0.6／L8：0.8・0.8）にして、seed を6つ変える。"""
import json
import pathlib
import time

from PIL import Image, ImageOps

import run
from run import OUT, SEEDS, VIEWS, comfy

MODES = {'L6': (0.6, 0.6), 'L8': (0.8, 0.8)}


def control_images():
    walk = ImageOps.mirror(Image.open(OUT / 'profile_walk_C8_2001.png').convert('RGB'))
    two = Image.open(OUT / 'two_profile_C8_2001.png').convert('RGB')
    w, h = two.size
    left = two.crop((0, 0, w // 2, h))
    pair = Image.new('RGB', (w, h))
    pair.paste(left, (0, 0))
    pair.paste(ImageOps.mirror(left), (w // 2, 0))
    return {'profile_walk': walk, 'two_profile': pair}


def graph(pos, neg, seed, size, src_name, strength, end):
    g = comfy.t2i(pos, seed, w=size[0], h=size[1], neg=neg, prefix='v3poc_p62d')
    g['20'] = {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': run.CONTROLNET}}
    g['23'] = {'class_type': 'SetUnionControlNetType', 'inputs': {'control_net': ['20', 0], 'type': 'canny/lineart/anime_lineart/mlsd'}}
    g['21'] = {'class_type': 'LoadImage', 'inputs': {'image': src_name}}
    g['24'] = {'class_type': 'Canny', 'inputs': {'image': ['21', 0], 'low_threshold': 0.4, 'high_threshold': 0.8}}
    g['22'] = {'class_type': 'ControlNetApplyAdvanced', 'inputs': {
        'positive': ['2', 0], 'negative': ['3', 0], 'control_net': ['23', 0], 'image': ['24', 0],
        'strength': strength, 'start_percent': 0.0, 'end_percent': end}}
    g['5']['inputs']['positive'] = ['22', 0]
    g['5']['inputs']['negative'] = ['22', 1]
    g['25'] = {'class_type': 'SaveImage', 'inputs': {'images': ['24', 0], 'filename_prefix': 'v3poc_p62d_canny'}}
    return g


def main():
    rec = []
    views = {v[0]: v for v in VIEWS}
    for name, src in control_images().items():
        _, size, who, words, neg_words, _ = views[name]
        src_path = OUT / 'direction' / f'{name}_src.png'
        src_path.parent.mkdir(exist_ok=True)
        src.save(src_path)
        src_name = comfy.upload(str(src_path), f'v3poc_p62d_{name}.png')
        pos, neg = f'{run.BASE.format(who=who)}, {words}', f'{comfy.NEG}, {neg_words}'
        for m, (strength, end) in MODES.items():
            for s in SEEDS:
                fn = OUT / 'direction' / f'{name}_{m}_{s}.png'
                if not fn.exists():
                    t0 = time.time()
                    h = comfy.wait(comfy.queue(graph(pos, neg, s, size, src_name, strength, end)))
                    fn.write_bytes(comfy.images({'outputs': {'7': h['outputs']['7']}})[0])
                    canny = OUT / 'direction' / f'{name}_canny.png'
                    if not canny.exists():
                        canny.write_bytes(comfy.images({'outputs': {'25': h['outputs']['25']}})[0])
                    t = time.time() - t0
                    print(name, m, s, round(t, 1), flush=True)
                rec.append({'view': name, 'mode': m, 'seed': s, 'strength': strength, 'end': end})
        rows = []
        for m in MODES:
            ims = [Image.open(OUT / 'direction' / f'{name}_{m}_{s}.png') for s in SEEDS]
            rows.append([i.resize((int(i.width * 260 / i.height), 260)) for i in ims])
        head = src.resize((int(src.width * 260 / src.height), 260))
        W = head.width + 6 + sum(i.width + 6 for i in rows[0])
        sheet = Image.new('RGB', (W, 266 * len(rows)), 'white')
        sheet.paste(head, (0, 0))
        for k, r in enumerate(rows):
            x = head.width + 6
            for i in r:
                sheet.paste(i, (x, k * 266))
                x += i.width + 6
        sheet.save(OUT / f'sheet_direction_{name}.png')
    (OUT / 'direction' / 'gen.json').write_text(json.dumps({'union_type': 'canny/lineart/anime_lineart/mlsd',
                                                             'canny': [0.4, 0.8], 'runs': rec}, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
