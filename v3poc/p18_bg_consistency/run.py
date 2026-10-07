"""P18 背景の不揃いを解消できるか（一覧 1-38、方針20、候補98・99・101）。
同じ場所（教室・街）を3つの向き（front・side・back）から描いたコマで、間取りと物の位置が揃うかを比べる。
 text      : 言葉だけ（比べるため。向きごとに場所がばらばらになるはず）
 depth     : 箱で組んだ3Dの場所から描いた奥行きの図を、多用途の制御（xinsir union、Apache-2.0）の奥行きとして渡す
 line      : 同じく3Dの場所の線画を、多用途の制御の線画として渡す
 depth_ref : depth に、同じ seed の front の絵を参照画像（IP-Adapter plus、Apache-2.0）として足し、描き込みの質感を寄せる（side・back だけ）
3Dの場所は scene3d.py（外の3Dソフトは使わない）。絵柄は白黒・トーン、背景だけ（人物なし）。各 seed 3つ。"""
import json
import pathlib
import sys

from PIL import ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402
import scene3d  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
AUX = OUT / 'aux'
AUX.mkdir(parents=True, exist_ok=True)
W, H = 1152, 896
SEEDS = [91, 92, 93]
STYLE = 'masterpiece, best quality, manga, monochrome, greyscale, screentone'
PLACE_WORDS = {'room': 'classroom, desks, chalkboard, windows, indoors', 'street': 'city street, buildings, road, utility pole'}
NEG_ADD = '1girl, 1boy, people'
UNION = 'xinsir\\union-sdxl-1.0-promax.safetensors'
CN = {'depth': ('depth', 0.8, 0.8), 'line': ('canny/lineart/anime_lineart/mlsd', 0.8, 0.8)}  # 種類・強さ・効かせる終わり
IPA = {'model': 'ip_adapter_plus_sdxl_vit-h\\ip_adapter.bin', 'clip_vision': 'clip_vision_h.safetensors', 'weight': 0.5}


def prompt(place):
    return f'{STYLE}, scenery, no humans, {PLACE_WORDS[place]}'


def graph(place, seed, mode, ctl=None, ref=None):
    g = comfy.t2i(prompt(place), seed, W, H, neg=f'{comfy.NEG}, {NEG_ADD}', prefix='v3poc_p18')
    if mode in ('depth', 'line', 'depth_ref'):
        typ, st, end = CN['line' if mode == 'line' else 'depth']
        g['20'] = {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': UNION}}
        g['23'] = {'class_type': 'SetUnionControlNetType', 'inputs': {'control_net': ['20', 0], 'type': typ}}
        g['21'] = {'class_type': 'LoadImage', 'inputs': {'image': ctl}}
        g['22'] = {'class_type': 'ControlNetApplyAdvanced', 'inputs': {'positive': ['2', 0], 'negative': ['3', 0], 'control_net': ['23', 0], 'image': ['21', 0],
                                                                     'strength': st, 'start_percent': 0.0, 'end_percent': end}}
        g['5']['inputs']['positive'] = ['22', 0]
        g['5']['inputs']['negative'] = ['22', 1]
    if mode == 'depth_ref':
        g['30'] = {'class_type': 'IPAdapterModelLoader', 'inputs': {'ipadapter_file': IPA['model']}}
        g['31'] = {'class_type': 'CLIPVisionLoader', 'inputs': {'clip_name': IPA['clip_vision']}}
        g['32'] = {'class_type': 'LoadImage', 'inputs': {'image': ref}}
        g['33'] = {'class_type': 'IPAdapterAdvanced', 'inputs': {'model': ['1', 0], 'ipadapter': ['30', 0], 'image': ['32', 0], 'clip_vision': ['31', 0],
                                                               'weight': IPA['weight'], 'weight_type': 'linear', 'combine_embeds': 'concat',
                                                               'start_at': 0.0, 'end_at': 1.0, 'embeds_scaling': 'V only'}}
        g['5']['inputs']['model'] = ['33', 0]
    return g


def main():
    rec = []
    for place in scene3d.PLACES:
        ctl = {}
        for view in scene3d.PLACES[place]['cams']:
            depth, line = scene3d.render(place, view, W, H)
            depth.save(AUX / f'{place}_{view}_depth.png')
            line.save(AUX / f'{place}_{view}_line.png')
            ImageOps.invert(line).save(AUX / f'{place}_{view}_line_inv.png')  # 制御には黒地に白線で渡す
            ctl[view] = {'depth': comfy.upload(str(AUX / f'{place}_{view}_depth.png'), f'v3poc_p18_{place}_{view}_depth.png'),
                         'line': comfy.upload(str(AUX / f'{place}_{view}_line_inv.png'), f'v3poc_p18_{place}_{view}_line.png')}
        for s in SEEDS:
            for view in scene3d.PLACES[place]['cams']:
                for mode in ('text', 'depth', 'line', 'depth_ref'):
                    if mode == 'depth_ref' and view == 'front':
                        continue
                    ref = None
                    if mode == 'depth_ref':
                        ref = comfy.upload(str(OUT / f'{place}_front_depth_{s}.png'), f'v3poc_p18_ref_{place}_{s}.png')
                    c = ctl[view]['line' if mode == 'line' else 'depth'] if mode != 'text' else None
                    b, t = comfy.run(graph(place, s, mode, c, ref))
                    name = f'{place}_{view}_{mode}_{s}.png'
                    (OUT / name).write_bytes(b[0])
                    rec.append({'file': name, 'place': place, 'view': view, 'mode': mode, 'seed': s, 'sec': round(t, 1)})
                    print(name, round(t, 1), flush=True)
    (OUT / 'gen.json').write_text(json.dumps({'ckpt': comfy.CKPT, 'size': [W, H], 'steps': 25, 'cfg': 5.0, 'sampler': 'euler_ancestral', 'scheduler': 'normal',
                                              'positive': {p: prompt(p) for p in PLACE_WORDS}, 'negative': f'{comfy.NEG}, {NEG_ADD}',
                                              'controlnet': {'model': UNION, 'modes': {k: {'type': v[0], 'strength': v[1], 'end_percent': v[2]} for k, v in CN.items()}},
                                              'ipadapter': IPA, 'cams': {p: v['cams'] for p, v in scene3d.PLACES.items()}, 'runs': rec},
                                             ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
