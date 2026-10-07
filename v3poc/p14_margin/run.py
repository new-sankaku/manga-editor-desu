"""P14 余白のあるコマを作れるか（一覧 1-32・1-33）。
漫画のコマは人物の周りに余白があるのが基本。寄りばかりだとページの圧迫感が強く、世界の奥行きが出ない。
コマの形（横長・縦長・標準）ごとに、余白の出し方を比べる。
 text     : コマの形のまま生成し、引きの言葉（全身・引き・風景）だけで頼む
 shrink   : text に、生成の初めだけ縮小して作る手（Deep Shrink）を足す。極端な形で人物が増えるのを抑える手として知られる
 pose_*   : コマの形のまま生成し、小さく置いた骨格の図で人物の位置と大きさを渡す（商用可の部品だけ）
 outpaint : 普通の縦長で人物を作り、縮めてコマの中に置き、周りを描き足す
 crop     : outpaint の元の絵を、コマの形に切り抜いただけ（比べるため。生成しない）
骨格の部品はどれも Apache-2.0（配布元の表示を 2026-09-30 に確認）。"""
import io
import json
import math
import pathlib
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
AUX = OUT / 'aux'  # 骨格の図・元の絵・置いた絵・マスク（測る対象から外す）
AUX.mkdir(exist_ok=True)
BG = 'masterpiece, best quality, manga, monochrome, greyscale, screentone, city street, buildings, '
PERSON = '1girl, solo, short black bob hair, glasses, school blazer, necktie, standing, full body'
WIDE = ', wide shot, scenery'
SEEDS = [61, 62, 63]
# コマの形：生成の大きさと、人物を置く枠（x0, y0, x1, y1。コマに対する割合）
# 横長：右寄りに立たせ、左（右から読むときの先）を空ける。縦長：下に小さく立たせ、上に街を見せる
SHAPES = {'yoko': ((1536, 576), (0.66, 0.22, 0.80, 0.94)),
          'tate': ((576, 1536), (0.30, 0.62, 0.70, 0.94)),
          'std': ((1152, 896), (0.18, 0.38, 0.36, 0.94))}
POSES = {'pose_xinsir': ('xinsir\\openpose-sdxl-1.0.safetensors', None),
         'pose_union': ('xinsir\\union-sdxl-1.0-promax.safetensors', 'openpose'),
         'pose_windsing': ('windsingai\\illustrious-xl-openpose-s6000.safetensors', None),
         'pose_t2i': ('t2i-adapter-openpose-sdxl-1.0\\diffusion_pytorch_model.safetensors', None)}

# COCO18の関節。立ち姿を 0〜1 の枠に正規化したもの（P8b の骨格と同じ形）
KP = [(0.50, 0.05), (0.50, 0.20), (0.22, 0.21), (0.12, 0.35), (0.08, 0.49), (0.78, 0.21), (0.88, 0.35), (0.92, 0.49),
      (0.33, 0.53), (0.28, 0.76), (0.25, 0.97), (0.68, 0.53), (0.72, 0.76), (0.75, 0.97), (0.44, 0.04), (0.56, 0.04), (0.36, 0.05), (0.64, 0.05)]
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170),
          (0, 255, 255), (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]


def fig_px(shape):
    (w, h), (a, b, c, d) = SHAPES[shape]
    return round(a * w), round(b * h), round(c * w), round(d * h)


def pose_img(shape):
    (w, h), _ = SHAPES[shape]
    x0, y0, x1, y1 = fig_px(shape)
    fh = y1 - y0
    fw = fh * 0.27  # 立ち姿の肩幅と腕の広がり
    cx = (x0 + x1) / 2
    pts = [(cx + (nx - 0.5) * fw, y0 + ny * fh) for nx, ny in KP]
    im = Image.new('RGB', (w, h), 'black')
    d = ImageDraw.Draw(im)
    wd = max(4, fh * 0.018)  # xinsir は太い線で学習している（配布元の説明）
    for i, (a, b) in enumerate(LIMBS):
        (xa, ya), (xb, yb) = pts[a], pts[b]
        ang = math.atan2(yb - ya, xb - xa)
        s, c = math.sin(ang) * wd, math.cos(ang) * wd
        d.polygon([(xa + s, ya - c), (xb + s, yb - c), (xb - s, yb + c), (xa - s, ya + c)], fill=tuple(int(v * .6) for v in COLORS[i]))
    for i, (x, y) in enumerate(pts):
        d.ellipse((x - wd, y - wd, x + wd, y + wd), fill=COLORS[i])
    p = AUX / f'pose_{shape}.png'
    im.save(p)
    return comfy.upload(str(p), f'v3poc_p14_pose_{shape}.png')


def g_text(shape, seed):
    (w, h), _ = SHAPES[shape]
    return comfy.t2i(BG + PERSON + WIDE, seed, w, h, prefix='v3poc_p14')


def g_shrink(shape, seed):
    g = g_text(shape, seed)
    g['10'] = {'class_type': 'PatchModelAddDownscale', 'inputs': {'model': ['1', 0], 'block_number': 3, 'downscale_factor': 1.5, 'start_percent': 0.0,
                                                                'end_percent': 0.35, 'downscale_after_skip': True,
                                                                'downscale_method': 'bicubic', 'upscale_method': 'bicubic'}}
    g['5']['inputs']['model'] = ['10', 0]
    return g


def g_pose(shape, seed, mode, img):
    g = g_text(shape, seed)
    name, typ = POSES[mode]
    g['20'] = {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': name}}
    cn = ['20', 0]
    if typ:
        g['23'] = {'class_type': 'SetUnionControlNetType', 'inputs': {'control_net': cn, 'type': typ}}
        cn = ['23', 0]
    g['21'] = {'class_type': 'LoadImage', 'inputs': {'image': img}}
    g['22'] = {'class_type': 'ControlNetApplyAdvanced', 'inputs': {'positive': ['2', 0], 'negative': ['3', 0], 'control_net': cn, 'image': ['21', 0],
                                                                 'strength': 1.0, 'start_percent': 0.0, 'end_percent': 1.0}}
    g['5']['inputs']['positive'] = ['22', 0]
    g['5']['inputs']['negative'] = ['22', 1]
    return g


def place(shape, base):
    """元の絵を縮めてコマの中の人物の枠に合わせて置く。返り値は置いた絵と、描き足す所（白）のマスク。"""
    (w, h), _ = SHAPES[shape]
    x0, y0, x1, y1 = fig_px(shape)
    # 元の絵の人物は縦の約8割。人物の枠の高さに合うよう、元の絵の高さを枠の1.25倍にする
    bh = min(h, round((y1 - y0) * 1.25))
    bw = round(base.width * bh / base.height)
    if bw > w:
        bw, bh = w, round(base.height * w / base.width)
    bx = min(max(0, round((x0 + x1) / 2 - bw / 2)), w - bw)
    by = h - bh
    canvas = Image.new('RGB', (w, h), (128, 128, 128))
    canvas.paste(base.resize((bw, bh), Image.LANCZOS), (bx, by))
    mask = Image.new('L', (w, h), 255)
    mask.paste(0, (bx, by, bx + bw, by + bh))
    return canvas, mask


def g_outpaint(shape, seed, canvas_name, mask_name):
    g = g_text(shape, seed)
    g['30'] = {'class_type': 'LoadImage', 'inputs': {'image': canvas_name}}
    g['31'] = {'class_type': 'LoadImageMask', 'inputs': {'image': mask_name, 'channel': 'red'}}
    g['32'] = {'class_type': 'VAEEncodeForInpaint', 'inputs': {'pixels': ['30', 0], 'vae': ['1', 2], 'mask': ['31', 0], 'grow_mask_by': 24}}
    g['5']['inputs']['latent_image'] = ['32', 0]
    g['33'] = {'class_type': 'InvertMask', 'inputs': {'mask': ['31', 0]}}
    g['34'] = {'class_type': 'ImageCompositeMasked', 'inputs': {'destination': ['6', 0], 'source': ['30', 0], 'x': 0, 'y': 0, 'resize_source': False, 'mask': ['33', 0]}}
    g['7']['inputs']['images'] = ['34', 0]
    return g


def crop(shape, base):
    """元の絵をコマの形に切り抜く（人物を真ん中に、幅か高さをいっぱいに）。"""
    (w, h), _ = SHAPES[shape]
    r = w / h
    if base.width / base.height > r:
        cw, ch = round(base.height * r), base.height
    else:
        cw, ch = base.width, round(base.width / r)
    x = (base.width - cw) // 2
    y = max(0, min(base.height - ch, round(base.height * 0.1)))  # 頭が入るよう上寄り
    return base.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS)


def save(name, b, rec, **kw):
    (OUT / name).write_bytes(b) if isinstance(b, bytes) else b.save(OUT / name)
    rec.append({'file': name, **kw})
    print(name, kw.get('sec'), flush=True)


def main():
    rec = []
    for shape in SHAPES:
        img = pose_img(shape)
        for s in SEEDS:
            b, t = comfy.run(g_text(shape, s))
            save(f'{shape}_text_{s}.png', b[0], rec, shape=shape, mode='text', seed=s, sec=round(t, 1))
            b, t = comfy.run(g_shrink(shape, s))
            save(f'{shape}_shrink_{s}.png', b[0], rec, shape=shape, mode='shrink', seed=s, sec=round(t, 1))
            for mode in POSES:
                b, t = comfy.run(g_pose(shape, s, mode, img))
                save(f'{shape}_{mode}_{s}.png', b[0], rec, shape=shape, mode=mode, seed=s, sec=round(t, 1))
            b, t = comfy.run(comfy.t2i(BG + PERSON, s, 832, 1216, prefix='v3poc_p14'))
            base = Image.open(io.BytesIO(b[0])).convert('RGB')
            base.save(AUX / f'base_{shape}_{s}.png')
            save(f'{shape}_crop_{s}.png', crop(shape, base), rec, shape=shape, mode='crop', seed=s, sec=0)
            canvas, mask = place(shape, base)
            canvas.save(AUX / f'canvas_{shape}_{s}.png')
            mask.save(AUX / f'mask_{shape}_{s}.png')
            cn = comfy.upload(str(AUX / f'canvas_{shape}_{s}.png'), f'v3poc_p14_canvas_{shape}_{s}.png')
            mn = comfy.upload(str(AUX / f'mask_{shape}_{s}.png'), f'v3poc_p14_mask_{shape}_{s}.png')
            b2, t2 = comfy.run(g_outpaint(shape, s, cn, mn))
            save(f'{shape}_outpaint_{s}.png', b2[0], rec, shape=shape, mode='outpaint', seed=s, sec=round(t + t2, 1))
    shrink = g_shrink('std', 0)['10']['inputs']
    modes = {'text': {'name': 'コマの形のまま・言葉だけ', 'control': None},
             'shrink': {'name': 'コマの形のまま・初めだけ縮小（Deep Shrink）',
                        'control': {'node': 'PatchModelAddDownscale', **{k: v for k, v in shrink.items() if k != 'model'}}},
             'crop': {'name': '縦長で作って切り抜く（比べるため）', 'control': {'base_size': [832, 1216], 'base_positive': BG + PERSON, 'crop': '人物を真ん中に、幅か高さをいっぱいに'}},
             'outpaint': {'name': '縦長で作り、縮めて置き、周りを描き足す',
                          'control': {'base_size': [832, 1216], 'base_positive': BG + PERSON, 'place': '元の絵の高さを人物の枠の1.25倍にし、下端に揃えて置く',
                                      'node': 'VAEEncodeForInpaint', 'grow_mask_by': 24, 'denoise': 1.0, 'mask': 'out/aux/mask_<形>_<seed>.png（白が描き足す所）'}}}
    for m, (name, typ) in POSES.items():
        modes[m] = {'name': '骨格の図で位置と大きさを渡す', 'control': {'node': 'ControlNetApplyAdvanced', 'model': name, 'union_type': typ, 'strength': 1.0,
                                                                  'start_percent': 0.0, 'end_percent': 1.0, 'image': 'out/aux/pose_<形>.png'}}
    (OUT / 'gen.json').write_text(json.dumps({'shapes': {k: {'size': v[0], 'fig': fig_px(k)} for k, v in SHAPES.items()}, 'runs': rec, 'modes': modes,
                                              'ckpt': comfy.CKPT, 'steps': 25, 'cfg': 5.0, 'sampler': 'euler_ancestral', 'scheduler': 'normal',
                                              'negative': comfy.NEG, 'prompt': BG + PERSON + WIDE}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
