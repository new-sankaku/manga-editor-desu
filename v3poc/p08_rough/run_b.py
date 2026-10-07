"""P8b 棒人間のラフが効かなかったので、人物の位置を渡す別の手を試す（一覧 1-25、2-18）。
 pose_thibaud / pose_t2i : 骨格の図（OpenPoseの描き方）をラフの棒人間の位置に置いて渡す
 area                    : 画面の左下の範囲にだけ人物の指示を効かせる（範囲つきの条件）
 area+pose               : 両方
フキダシの場所は制御に入れない。測り方は analyze.py と同じ（人物の枠とラフの位置の重なり）。"""
import json
import math
import pathlib
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out_b'
OUT.mkdir(exist_ok=True)
W, H = 832, 1216
FIG = (150, 430, 350, 1170)
BAL = (500, 60, 800, 420)
BG = 'masterpiece, best quality, manga, monochrome, greyscale, screentone, street, '
PERSON = '1girl, solo, short black bob hair, glasses, school blazer, red necktie, full body, standing'
POSES = {'pose_thibaud': 'sd_control_collection\\thibaud_xl_openpose.safetensors',
         'pose_t2i': 't2i-adapter-openpose-sdxl-1.0\\diffusion_pytorch_model.safetensors'}
SEEDS = [11, 12, 13]

# COCO18の関節（x, y）。立っている人をラフの棒人間の位置に置く
KP = [(250, 480), (250, 580), (195, 585), (175, 690), (165, 790), (305, 585), (325, 690), (335, 790),
      (215, 820), (205, 990), (200, 1150), (285, 820), (295, 990), (300, 1150), (238, 468), (262, 468), (222, 478), (278, 478)]
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170),
          (0, 255, 255), (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]


def pose_img():
    im = Image.new('RGB', (W, H), 'black')
    d = ImageDraw.Draw(im, 'RGBA')
    for i, (a, b) in enumerate(LIMBS):
        (x1, y1), (x2, y2) = KP[a], KP[b]
        L = math.hypot(x2 - x1, y2 - y1)
        ang = math.atan2(y2 - y1, x2 - x1)
        wdt = 8
        pts = [(x1 + math.sin(ang) * wdt, y1 - math.cos(ang) * wdt), (x2 + math.sin(ang) * wdt, y2 - math.cos(ang) * wdt),
               (x2 - math.sin(ang) * wdt, y2 + math.cos(ang) * wdt), (x1 - math.sin(ang) * wdt, y1 + math.cos(ang) * wdt)]
        c = COLORS[i]
        d.polygon(pts, fill=(int(c[0] * .6), int(c[1] * .6), int(c[2] * .6), 255))
        _ = L
    for i, (x, y) in enumerate(KP):
        d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=COLORS[i])
    im.save(OUT / 'pose.png')


def graph(seed, pose=None, img=None, area=False):
    g = comfy.t2i(BG + PERSON, seed, W, H, prefix='v3poc_p08b')
    pos = ['2', 0]
    if area:
        g['2']['inputs']['text'] = BG + 'empty street, no humans'
        g['40'] = {'class_type': 'CLIPTextEncode', 'inputs': {'text': BG + PERSON, 'clip': ['1', 1]}}
        x0, y0, x1, y1 = FIG
        g['41'] = {'class_type': 'ConditioningSetArea', 'inputs': {'conditioning': ['40', 0], 'width': (x1 - x0 + 80) // 8 * 8, 'height': (y1 - y0 + 40) // 8 * 8,
                                                                 'x': (x0 - 40) // 8 * 8, 'y': (y0 - 20) // 8 * 8, 'strength': 1.0}}
        g['42'] = {'class_type': 'ConditioningCombine', 'inputs': {'conditioning_1': ['2', 0], 'conditioning_2': ['41', 0]}}
        pos = ['42', 0]
    if pose:
        g['20'] = {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': POSES[pose]}}
        g['21'] = {'class_type': 'LoadImage', 'inputs': {'image': img}}
        g['22'] = {'class_type': 'ControlNetApplyAdvanced', 'inputs': {'positive': pos, 'negative': ['3', 0], 'control_net': ['20', 0], 'image': ['21', 0],
                                                                     'strength': 1.0, 'start_percent': 0.0, 'end_percent': 1.0}}
        pos = ['22', 0]
        g['5']['inputs']['negative'] = ['22', 1]
    g['5']['inputs']['positive'] = pos
    return g


def main():
    pose_img()
    img = comfy.upload(str(OUT / 'pose.png'), 'v3poc_p08b_pose.png')
    rec = []
    for mode, pose, area in (('pose_thibaud', 'pose_thibaud', False), ('pose_t2i', 'pose_t2i', False), ('area', None, True), ('area_pose_thibaud', 'pose_thibaud', True)):
        for s in SEEDS:
            b, t = comfy.run(graph(s, pose, img, area))
            name = f'{mode}_{s}.png'
            (OUT / name).write_bytes(b[0])
            rec.append({'file': name, 'cn': mode, 'seed': s, 'sec': round(t, 1)})
            print(name, round(t, 1), flush=True)
    (OUT / 'gen.json').write_text(json.dumps({'FIG': FIG, 'BAL': BAL, 'runs': rec}, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
