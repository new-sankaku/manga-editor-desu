"""関節の角度から立体の骨格を組み、カメラで写して骨格の図（openpose）と奥行きの図（depth）を描く。
座標は m。X＝人物の左、Y＝上、Z＝人物の前。点の並びは COCO18 に、頭の中心・腰の中心・両足のつま先を足した22個。"""
import math

import numpy as np
from PIL import Image, ImageDraw

from v3server.comfy_graphs.pose_skeleton_image import COLORS, LIMB_BRIGHTNESS, LIMBS

W, H = 832, 1216
# 長さ（m）。身長およそ1.6
NECK_UP, HEAD_UP, SHOULDER, UPPER_ARM, FOREARM, HIP_W, THIGH, SHIN, SPINE = .10, .14, .19, .26, .25, .10, .42, .41, .48
JOINTS = {  # 名前: (意味, 下限, 上限)。LLM に渡す説明の元
    'body_pitch': ('体全体を前へ倒す角度。90で前へうつ伏せ、-90で後ろへ仰向けになる', -90, 90),
    'body_roll': ('体全体を横へ倒す角度。正で人物の左へ倒れる。90で左を下にして横になる', -90, 90),
    'torso_bend': ('腰から上を前へ曲げる角度。負で後ろへ反る', -40, 100),
    'torso_twist': ('腰から上をひねる角度。正で胸が人物の左を向く', -60, 60),
    'torso_side': ('腰から上を横へ曲げる角度。正で人物の左へ傾く', -40, 40),
    'head_pitch': ('首を前へ曲げる角度。正でうつむき、負で上を向く', -60, 70),
    'head_yaw': ('首を回す角度。正で顔が人物の左を向く', -80, 80),
    'head_roll': ('首をかしげる角度。正で人物の左へ傾く', -40, 40),
}
for side, name in (('l', '左'), ('r', '右')):
    JOINTS.update({
        f'{side}_shoulder_front': (f'{name}の腕を前へ上げる角度。0で下に垂らす、90で前へ水平、180で真上、負で後ろへ引く', -60, 180),
        f'{side}_shoulder_out': (f'{name}の腕を横へ開く角度。0で体に沿う、90で横へ水平、負で体の前を横切って反対側へ寄る', -40, 180),
        f'{side}_elbow': (f'{name}の肘を曲げる角度。0でまっすぐ、肘から先は上腕の前の側へ折れる', 0, 150),
        f'{side}_hip_front': (f'{name}の太ももを前へ上げる角度。0でまっすぐ立つ、90で前へ水平、負で後ろへ引く', -40, 150),
        f'{side}_hip_out': (f'{name}の太ももを横へ開く角度。負で反対の脚の前を横切る', -40, 80),
        f'{side}_knee': (f'{name}の膝を曲げる角度。0でまっすぐ、膝から下は太ももの後ろの側へ折れる', 0, 160),
    })
JOINTS['ground'] = ('1なら一番低い所を床に付ける。0なら付けず、腰の高さ hip_height を使う（跳んでいるときなど）', 0, 1)
JOINTS['hip_height'] = ('ground が0のときの腰の中心の高さ（m）。立っているときは0.9', 0, 2)


def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


DOWN = np.array([0, -1.0, 0])


def build(j):
    """角度の辞書から22個の点を作る。無い角度は0（まっすぐ立つ）。"""
    g = lambda k: float(j.get(k, 0) or 0)  # noqa: E731
    lim = {k: max(v[1], min(v[2], g(k))) for k, v in JOINTS.items()}
    pelvis = np.zeros(3)
    pts = [None] * 22
    torso = ry(lim['torso_twist']) @ rz(-lim['torso_side']) @ rx(lim['torso_bend'])
    neck = pelvis + torso @ np.array([0, SPINE, 0])
    pts[1], pts[19] = neck, pelvis
    head_r = torso @ ry(lim['head_yaw']) @ rz(-lim['head_roll']) @ rx(lim['head_pitch'])
    hc = neck + head_r @ np.array([0, NECK_UP, 0])
    pts[18] = hc
    for i, v in ((0, (0, -.02, .10)), (14, (-.035, .02, .085)), (15, (.035, .02, .085)), (16, (-.078, 0, 0)), (17, (.078, 0, 0))):
        pts[i] = hc + head_r @ np.array(v)
    for side, sgn, sh, el, wr, hp, kn, an, toe in (('r', -1, 2, 3, 4, 8, 9, 10, 20), ('l', 1, 5, 6, 7, 11, 12, 13, 21)):
        s0 = neck + torso @ np.array([sgn * SHOULDER, -.02, 0])
        arm = torso @ rx(-lim[f'{side}_shoulder_front']) @ rz(sgn * lim[f'{side}_shoulder_out'])
        e = s0 + arm @ DOWN * UPPER_ARM
        w = e + arm @ rx(-lim[f'{side}_elbow']) @ DOWN * FOREARM
        pts[sh], pts[el], pts[wr] = s0, e, w
        h0 = pelvis + np.array([sgn * HIP_W, 0, 0])
        thigh = rx(-lim[f'{side}_hip_front']) @ rz(sgn * lim[f'{side}_hip_out'])
        k = h0 + thigh @ DOWN * THIGH
        shin = thigh @ rx(lim[f'{side}_knee'])
        a = k + shin @ DOWN * SHIN
        pts[hp], pts[kn], pts[an], pts[toe] = h0, k, a, a + shin @ np.array([0, -.04, .14])
    P = np.array(pts)
    P = P @ (rz(-lim['body_roll']) @ rx(lim['body_pitch'])).T
    if lim['ground'] >= .5 or 'ground' not in j:
        P[:, 1] -= P[:, 1].min() - .04
    else:
        P[:, 1] += lim['hip_height']
    return P


def camera(P, yaw, pitch, roll=0, fov=45, fill=0.95):
    """人物を yaw 度回し（90で絵の左を向く）、骨格の真ん中を pitch 度上（負で下）から、全身が入る距離で狙う。"""
    R = ry(-yaw)
    Q = P @ R.T
    T = (Q.min(0) + Q.max(0)) / 2
    half = max(np.linalg.norm(Q - T, axis=1).max(), .3)
    fov = math.radians(fov)
    d = half / math.tan(fov / 2) * fill + .3
    p = math.radians(pitch)
    C = T + d * np.array([0, math.sin(p), math.cos(p)])
    f = (T - C) / np.linalg.norm(T - C)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    q = math.radians(roll)
    r, u = r * math.cos(q) + u * math.sin(q), -r * math.sin(q) + u * math.cos(q)
    return Q, C, r, u, f, fov


def project(Q, cam):
    _, C, r, u, f, fov = cam
    D = Q - C
    z = D @ f
    foc = 0.5 / math.tan(fov / 2) * H
    return np.stack([W / 2 + foc * (D @ r) / z, H / 2 - foc * (D @ u) / z, z], -1)


def draw_pose(cam):
    Q = cam[0]
    pr = project(Q, cam)
    head = Q[18]
    to_cam = cam[1] - head
    to_cam /= np.linalg.norm(to_cam)
    vis = [pr[i, 2] > .05 for i in range(18)]
    for i in (0, 14, 15, 16, 17):  # 顔の点：頭の中心から見てカメラの反対側なら隠れる
        vec = Q[i] - head
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


CAPS = [(18, 18, .11), (1, 18, .05), (2, 5, .06), (1, 19, .14), (8, 11, .11), (2, 3, .045), (3, 4, .038), (5, 6, .045),
        (6, 7, .038), (8, 9, .075), (9, 10, .055), (11, 12, .075), (12, 13, .055), (4, 4, .045), (7, 7, .045),
        (10, 20, .045), (13, 21, .045)]


def draw_depth(cam, scale=2):
    """人形（球と筒）に光線を当て、近いほど白い奥行きの図を作る。"""
    Q, C, r, u, f, fov = cam
    w, h = W // scale, H // scale
    foc = 0.5 / math.tan(fov / 2) * h
    xs, ys = np.meshgrid(np.arange(w) + .5 - w / 2, h / 2 - (np.arange(h) + .5))
    dirs = f[None, None] * foc + r[None, None] * xs[..., None] + u[None, None] * ys[..., None]
    dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)
    t = np.zeros((h, w))
    hit = np.zeros((h, w), bool)
    for _ in range(60):
        p = C + dirs * t[..., None]
        sd = np.full((h, w), 1e9)
        for a, b, rad in CAPS:
            A, ab = Q[a], Q[b] - Q[a]
            L = ab @ ab
            pa = p - A
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


def check_views(P):
    """LLM に見せる確認の図：正面・人物の左の横・上からの3方向に、点の名前の頭文字を添える。"""
    ims = []
    for yaw, pitch, label in ((0, 0, 'front'), (-90, 0, 'left side'), (0, 80, 'top')):
        cam = camera(P, yaw, pitch, fov=30)
        im = draw_pose(cam).resize((416, 608))
        d = ImageDraw.Draw(im)
        d.text((8, 8), label, fill='white')
        ims.append(im)
    s = Image.new('RGB', (416 * 3 + 12, 608), 'gray')
    for k, im in enumerate(ims):
        s.paste(im, (k * 422, 0))
    return s
