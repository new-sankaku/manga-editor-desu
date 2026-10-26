"""P63 カメラのアングル（俯瞰・あおり・傾け）と注目する位置（顔・上半身・脚）を変えたとき、ControlNet で再現できるか。
SDXL（Illustrious 系）と xinsir の union promax。言葉だけの指定は比べない（V3検証の環境.md）。
立った人物の3Dの骨格を置き、カメラの向き・高さ・距離・傾きを変えて写し、骨格の図（openpose）と、
同じ骨格に太さを付けた人形の奥行きの図（depth）を作る。渡し方は3つ（OP：骨格だけ／DP：奥行きだけ／MIX：両方）。
結果は out/ に絵・骨格と奥行きの図・一覧（sheet_<名前>.png）・gen.json。優先の高い組から順に作る。"""
import json
import math
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'common'))
sys.path.insert(0, str(ROOT.parent / 'v3' / 'server' / 'src'))
import comfy  # noqa: E402
from v3server.comfy_graphs.pose_skeleton_image import COLORS, LIMB_BRIGHTNESS, LIMBS  # noqa: E402

OUT = pathlib.Path(__file__).with_name('out')
(OUT / 'cond').mkdir(parents=True, exist_ok=True)
W, H = 832, 1216
BASE = 'best quality, monochrome, greyscale, manga, screentone, 1girl, solo, short black bob hair, school blazer, pleated skirt, classroom'
NEG_ADD = 'nsfw, panties, underwear'
CONTROLNET = 'xinsir\\union-sdxl-1.0-promax.safetensors'
SEEDS = [3001, 3002, 3003]
# 名前: [(種類, 強さ, 終わり)]
MODES = {'OP': [('openpose', 0.8, 0.8)], 'DP': [('depth', 0.7, 0.8)],
         'MIX': [('openpose', 0.6, 0.8), ('depth', 0.5, 0.6)]}

# 人物の座標（m）。X＝人物の左、Y＝上、Z＝人物の前。COCO18 の順
KP = np.array([
    (0, 1.50, .10), (0, 1.38, 0), (-.19, 1.36, 0), (-.25, 1.10, -.01), (-.27, .85, .03), (.19, 1.36, 0), (.25, 1.10, -.01),
    (.27, .85, .03), (-.10, .90, 0), (-.11, .48, .02), (-.12, .07, 0), (.10, .90, 0), (.11, .48, .02), (.12, .07, 0),
    (-.035, 1.54, .085), (.035, 1.54, .085), (-.078, 1.52, 0), (.078, 1.52, 0)], dtype=float)
HEAD = np.array([0, 1.52, 0.0])
# 奥行きの人形：(始め, 終わり, 半径)。点は KP の番号か座標
CAPS = [(HEAD, HEAD, .11), (1, HEAD, .05), (2, 5, .06), (1, np.array([0, .95, 0]), .14), (8, 11, .11),
        (2, 3, .045), (3, 4, .038), (5, 6, .045), (6, 7, .038), (8, 9, .075), (9, 10, .055), (11, 12, .075), (12, 13, .055),
        (4, 4, .045), (7, 7, .045), (10, np.array([-.12, .04, .14]), .045), (13, np.array([.12, .04, .14]), .045)]
# 注目する所：(狙う点の高さ, 写す範囲の半分の高さ, 縦の画角)。寄るほど画角を狭め、カメラが近すぎて形が歪むのを避ける
FRAMES = {'full': (.80, .95, 45), 'upper': (1.25, .45, 30), 'face': (1.50, .18, 20), 'lower': (.40, .50, 30)}
PITCH_TAG = {85: 'from above, top-down view', 60: 'from above, high angle', 45: 'from above, high angle', 30: 'from above',
             0: '', -30: 'from below', -45: 'from below, low angle', -60: 'from below, low angle, worm\'s-eye view'}
YAW_TAG = {0: 'facing viewer', 45: 'three-quarter view', 90: 'from side, profile, facing left',
           135: 'from behind, three-quarter view, facing away', 180: 'from behind, facing away, back'}
FRAME_TAG = {'full': 'full body, standing', 'upper': 'upper body', 'face': 'close-up, portrait, face focus',
             'lower': 'lower body, legs, shoes'}


def views():
    """(名前, 向き, 上下の角度, 注目, 傾き)。優先の順：向き×上下の角度 → 注目×上下×向き → 傾け。"""
    v = [(f'a_y{y}_p{p}', y, p, 'full', 0) for p in (60, -45, 85, 30, -60, -30, 0) for y in (0, 90, 180, 45, 135)]
    v += [(f'f_{f}_y{y}_p{p}', y, p, f, 0) for f in ('face', 'upper', 'lower') for p in (45, -45, 0) for y in (0, 90, 180)]
    v += [(f'd_y{y}_p{p}_r{r}', y, p, 'full', r) for r in (25, 45) for y in (0, 90) for p in (0, 30)]
    return v


def camera(yaw, pitch, frame, roll):
    """人物を yaw 度回し（90で絵の左を向く）、カメラは前から pitch 度上（負で下）から狙う。"""
    a = math.radians(-yaw)
    R = np.array([[math.cos(a), 0, -math.sin(a)], [0, 1, 0], [math.sin(a), 0, math.cos(a)]]).T  # 列が人物の X・Y・Z
    ty, half, fov = FRAMES[frame]
    fov = math.radians(fov)
    d = half / math.tan(fov / 2) * 0.95
    p = math.radians(pitch)
    T = np.array([0, ty, 0])
    C = T + d * np.array([0, math.sin(p), math.cos(p)])
    f = (T - C) / np.linalg.norm(T - C)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    q = math.radians(roll)
    r, u = r * math.cos(q) + u * math.sin(q), -r * math.sin(q) + u * math.cos(q)
    return R, C, r, u, f, fov


def project(P, cam):
    _, C, r, u, f, fov = cam
    D = P - C
    z = D @ f
    foc = 0.5 / math.tan(fov / 2) * H
    return np.stack([W / 2 + foc * (D @ r) / z, H / 2 - foc * (D @ u) / z, z], -1)


def draw_pose(yaw, cam):
    R = cam[0]
    P = KP @ R.T
    pr = project(P, cam)
    head = R @ HEAD
    to_cam = cam[1] - head
    to_cam /= np.linalg.norm(to_cam)
    vis = [pr[i, 2] > .05 for i in range(18)]
    for i in (0, 14, 15, 16, 17):  # 顔の点：頭の中心から見てカメラの反対側なら隠れる
        vec = P[i] - head
        if vec @ to_cam / np.linalg.norm(vec) < -0.15:
            vis[i] = False
    im = Image.new('RGB', (W, H), 'black')
    dr = ImageDraw.Draw(im)
    lw = max(4, int(H * .012))
    for k, (a, b) in enumerate(LIMBS):
        if vis[a] and vis[b]:
            c = tuple(int(v * LIMB_BRIGHTNESS) for v in COLORS[k % len(COLORS)])
            dr.line([tuple(pr[a, :2]), tuple(pr[b, :2])], fill=c, width=lw)
    for i in range(18):
        if vis[i]:
            x, y = pr[i, :2]
            dr.ellipse([x - lw, y - lw, x + lw, y + lw], fill=COLORS[i])
    return im


def draw_depth(cam, scale=2):
    """人形を光線で当てて、近いほど白い奥行きの図を作る（半分の大きさで計算して広げる）。"""
    R, C, r, u, f, fov = cam
    w, h = W // scale, H // scale
    foc = 0.5 / math.tan(fov / 2) * h
    xs, ys = np.meshgrid(np.arange(w) + .5 - w / 2, h / 2 - (np.arange(h) + .5))
    dirs = f[None, None] * foc + r[None, None] * xs[..., None] + u[None, None] * ys[..., None]
    dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)
    pt = lambda x: R @ (KP[x] if isinstance(x, int) else x)  # noqa: E731
    caps = [(pt(a), pt(b), rad) for a, b, rad in CAPS]
    t = np.zeros((h, w))
    hit = np.zeros((h, w), bool)
    for _ in range(60):
        p = C + dirs * t[..., None]
        sd = np.full((h, w), 1e9)
        for a, b, rad in caps:
            ab = b - a
            L = ab @ ab
            pa = p - a
            k = np.clip((pa @ ab) / L, 0, 1) if L > 0 else np.zeros((h, w))
            sd = np.minimum(sd, np.linalg.norm(pa - k[..., None] * ab, axis=-1) - rad)
        hit |= sd < 1e-3
        t = np.where(hit, t, t + np.maximum(sd, 1e-3))
    z = t * (dirs @ f)
    img = np.zeros((h, w))
    if hit.any():
        near, far = z[hit].min(), z[hit].max()
        img[hit] = 1 - 0.75 * (z[hit] - near) / max(far - near, 1e-6)
    return Image.fromarray((img * 255).astype(np.uint8)).convert('RGB').resize((W, H), Image.BILINEAR)


def graph(pos, neg, seed, conds):
    g = comfy.t2i(pos, seed, w=W, h=H, neg=neg, prefix='v3poc_p63')
    g['20'] = {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': CONTROLNET}}
    last = ['2', 0], ['3', 0]
    for k, (kind, name, strength, end) in enumerate(conds):
        n = 30 + k * 3
        g[str(n)] = {'class_type': 'SetUnionControlNetType', 'inputs': {'control_net': ['20', 0], 'type': kind}}
        g[str(n + 1)] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
        g[str(n + 2)] = {'class_type': 'ControlNetApplyAdvanced', 'inputs': {
            'positive': last[0], 'negative': last[1], 'control_net': [str(n), 0], 'image': [str(n + 1), 0],
            'strength': strength, 'start_percent': 0.0, 'end_percent': end}}
        last = [str(n + 2), 0], [str(n + 2), 1]
    g['5']['inputs']['positive'], g['5']['inputs']['negative'] = last
    return g


def sheet(name):
    def row(ims, hgt=300):
        ims = [i.resize((int(i.width * hgt / i.height), hgt)) for i in ims]
        r = Image.new('RGB', (sum(i.width for i in ims) + 6 * len(ims), hgt), 'white')
        x = 0
        for i in ims:
            r.paste(i, (x, 0))
            x += i.width + 6
        return r
    rows = [row([Image.open(OUT / 'cond' / f'{name}_pose.png'), Image.open(OUT / 'cond' / f'{name}_depth.png')])]
    rows += [row([Image.open(OUT / f'{name}_{m}_{s}.png') for s in SEEDS]) for m in MODES]
    s = Image.new('RGB', (max(r.width for r in rows), 306 * len(rows)), 'white')
    for k, r in enumerate(rows):
        s.paste(r, (0, k * 306))
    s.save(OUT / f'sheet_{name}.png')


def main():
    rec = []
    for name, yaw, pitch, frame, roll in views():
        tags = ', '.join(t for t in (YAW_TAG[yaw], PITCH_TAG[pitch], FRAME_TAG[frame], 'dutch angle' if roll else '') if t)
        pos, neg = f'{BASE}, {tags}', f'{comfy.NEG}, {NEG_ADD}'
        cam = camera(yaw, pitch, frame, roll)
        names = {}
        for kind, im in (('pose', draw_pose(yaw, cam)), ('depth', draw_depth(cam))):
            path = OUT / 'cond' / f'{name}_{kind}.png'
            im.save(path)
            names['openpose' if kind == 'pose' else 'depth'] = comfy.upload(str(path), f'v3poc_p63_{name}_{kind}.png')
        for m, conds in MODES.items():
            for s in SEEDS:
                fn = OUT / f'{name}_{m}_{s}.png'
                if not fn.exists():
                    imgs, t = comfy.run(graph(pos, neg, s, [(k, names[k], st, e) for k, st, e in conds]))
                    fn.write_bytes(imgs[0])
                    print(name, m, s, round(t, 1), flush=True)
        sheet(name)
        rec.append({'view': name, 'yaw': yaw, 'pitch': pitch, 'frame': frame, 'roll': roll, 'prompt': pos, 'negative': neg})
        (OUT / 'gen.json').write_text(json.dumps({
            'ckpt': comfy.CKPT, 'controlnet': CONTROLNET, 'steps': 25, 'cfg': 5.0, 'sampler': 'euler_ancestral',
            'scheduler': 'normal', 'size': [W, H], 'frames': FRAMES, 'seeds': SEEDS,
            'modes': {m: [{'type': k, 'strength': st, 'end': e} for k, st, e in c] for m, c in MODES.items()},
            'views': rec}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1:] == ['cond']:  # 図だけ作って目で確かめる
        for name, yaw, pitch, frame, roll in views():
            cam = camera(yaw, pitch, frame, roll)
            draw_pose(yaw, cam).save(OUT / 'cond' / f'{name}_pose.png')
            draw_depth(cam).save(OUT / 'cond' / f'{name}_depth.png')
            print(name, flush=True)
    else:
        main()
