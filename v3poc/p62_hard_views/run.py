"""P62 AIが出しにくい向き・姿勢を、ControlNet の骨格の指定で再現できるか（後ろ・横・振り返り・寝転ぶ・しゃがむ・向かい合う・うつむき）。
SDXL（Illustrious 系）と xinsir の union promax（openpose）。言葉だけの指定は比べない（利用者の決め。V3検証の環境.md）。
向き・姿勢ごとに、骨格の効きを2段（C8：強さ 0.8・終わり 0.8／C10：強さ 1.0・終わり 1.0）にし、seed を6つ変えて作る。
結果は out/ に絵・骨格の図・一覧（sheet_<向き>.png）・gen.json。"""
import json
import pathlib
import sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'common'))
sys.path.insert(0, str(ROOT.parent / 'v3' / 'server' / 'src'))
import comfy  # noqa: E402
from v3server.comfy_graphs.pose_skeleton_image import COLORS, LIMB_BRIGHTNESS, LIMBS  # noqa: E402

OUT = pathlib.Path(__file__).with_name('out')
(OUT / 'pose').mkdir(parents=True, exist_ok=True)
BASE = 'best quality, monochrome, greyscale, manga, screentone, {who}, short black bob hair, school blazer, pleated skirt, classroom'
CONTROLNET = 'xinsir\\union-sdxl-1.0-promax.safetensors'
SEEDS = list(range(2001, 2007))
MODES = {'C8': (0.8, 0.8), 'C10': (1.0, 1.0)}
P, L = (832, 1216), (1216, 832)  # 縦長・横長


def mirror(kp):
    return [None if p is None else (1 - p[0], p[1]) for p in kp]


# COCO18：0鼻 1首 2右肩 3右肘 4右手首 5左肩 6左肘 7左手首 8右腰 9右膝 10右足首 11左腰 12左膝 13左足首 14右目 15左目 16右耳 17左耳
# 正面では人物の右が絵の左。後ろからでは人物の右が絵の右になり、鼻と目が無い
BACK = [None, (.50, .20), (.78, .21), (.86, .35), (.90, .49), (.22, .21), (.14, .35), (.10, .49),
        (.67, .53), (.70, .76), (.72, .97), (.33, .53), (.30, .76), (.28, .97), None, None, (.60, .07), (.40, .07)]
# 斜め後ろ：肩幅を狭め、向こう側の腕を寄せる
BACK34 = [None, (.50, .20), (.70, .21), (.76, .35), (.78, .49), (.28, .22), (.24, .36), (.24, .50),
          (.62, .53), (.64, .76), (.66, .97), (.38, .53), (.36, .76), (.35, .97), None, None, (.56, .07), (.38, .07)]
# 振り返り：体は後ろ、顔は絵の左へ向けて横顔（鼻・左目・左耳）
LOOK_BACK = [(.36, .10), (.50, .22), (.78, .24), (.86, .40), (.88, .55), (.22, .24), (.14, .40), (.12, .55),
             (.65, .60), (.68, .80), (.70, .98), (.35, .60), (.32, .80), (.30, .98), None, (.41, .08), None, (.52, .08)]
# 真横で歩く（絵の左へ進む。見える側は人物の左）
WALK = [(.40, .06), (.50, .19), (.47, .20), None, None, (.53, .20), (.55, .34), (.58, .47),
        (.49, .52), (.40, .74), (.34, .95), (.51, .52), (.58, .73), (.66, .94), None, (.44, .045), None, (.53, .055)]
# 真横の顔のアップ（頭と肩だけ）
FACE = [(.20, .42), (.50, .78), (.45, .82), None, None, (.60, .84), None, None,
        None, None, None, None, None, None, None, (.30, .34), None, (.58, .38)]
# 横向きに寝転ぶ（横長。頭が絵の左、顔は手前）
LYING = [(.14, .50), (.24, .52), (.25, .60), (.30, .70), (.36, .74), (.24, .44), (.32, .40), (.38, .44),
         (.52, .60), (.68, .62), (.86, .64), (.52, .52), (.68, .56), (.86, .58), (.12, .46), (.13, .53), (.10, .45), (.11, .55)]
# 後ろ向きでしゃがむ（腰が下がり、膝が外へ開く）
CROUCH = [None, (.50, .40), (.74, .42), (.82, .55), (.80, .68), (.26, .42), (.18, .55), (.20, .68),
          (.62, .70), (.80, .80), (.66, .96), (.38, .70), (.20, .80), (.34, .96), None, None, (.58, .28), (.42, .28)]
# うつむき：鼻と目が首の近くまで下がる
HEAD_DOWN = [(.50, .15), (.50, .20), (.22, .21), (.12, .35), (.08, .49), (.78, .21), (.88, .35), (.92, .49),
             (.33, .53), (.28, .76), (.25, .97), (.68, .53), (.72, .76), (.75, .97), (.46, .12), (.54, .12), (.40, .09), (.60, .09)]


def profile_upper(x0, facing_left):
    """横顔の上半身を、横長の絵の x0〜x0+0.5 に置く（向かい合う2人用）。"""
    kp = [(.22, .30), (.50, .55), (.46, .57), (.42, .80), (.36, .98), (.54, .57), (.60, .80), (.62, .98),
          None, None, None, None, None, None, None, (.30, .24), None, (.48, .26)]
    if not facing_left:
        kp = mirror(kp)
    return [None if p is None else (x0 + p[0] * .5, p[1]) for p in kp]


TWO = (profile_upper(.48, True), profile_upper(.02, False))  # 左の人は右を向き、右の人は左を向く

# 名前, 大きさ, 人, 言葉, 否定の言葉, 骨格（人ごと）
VIEWS = [
    ('back_full', P, '1girl, solo', 'from behind, facing away, back, back of head, standing, full body',
     'looking at viewer, facing viewer, looking back, face', (BACK,)),
    ('back_34', P, '1girl, solo', 'from behind, facing away, three-quarter view, looking ahead, standing, full body',
     'looking at viewer, facing viewer, looking back', (BACK34,)),
    ('look_back', P, '1girl, solo', 'from behind, back, looking back, looking over shoulder, profile, full body, standing',
     'facing viewer, looking at viewer', (LOOK_BACK,)),
    ('profile_walk', P, '1girl, solo', 'from side, profile, walking, facing left, full body, side view',
     'looking at viewer, facing viewer, three-quarter view', (WALK,)),
    ('profile_face', P, '1girl, solo', 'from side, profile, side view, facing left, close-up, portrait',
     'looking at viewer, facing viewer, three-quarter view', (FACE,)),
    ('lying_side', L, '1girl, solo', 'lying, on side, on floor, full body, from side',
     'standing, sitting', (LYING,)),
    ('crouch_back', P, '1girl, solo', 'from behind, facing away, back, squatting, full body, back of head',
     'looking at viewer, facing viewer, looking back, face', (CROUCH,)),
    ('two_profile', L, '2girls', 'face-to-face, from side, profile, looking at another, upper body, side view',
     'looking at viewer, facing viewer', TWO),
    ('head_down', P, '1girl, solo', 'head down, looking down, face hidden, hair over eyes, full body, standing',
     'looking at viewer, eyes visible', (HEAD_DOWN,)),
]


def draw_pose(size, people):
    w, h = size
    im = Image.new('RGB', size, 'black')
    d = ImageDraw.Draw(im)
    lw = max(4, int(h * .012))
    for kp in people:
        pts = [None if p is None else (p[0] * w, p[1] * h) for p in kp]
        for i, (a, b) in enumerate(LIMBS):
            if pts[a] is not None and pts[b] is not None:
                c = tuple(int(v * LIMB_BRIGHTNESS) for v in COLORS[i % len(COLORS)])
                d.line([pts[a], pts[b]], fill=c, width=lw)
        for i, p in enumerate(pts):
            if p is not None:
                d.ellipse([p[0] - lw, p[1] - lw, p[0] + lw, p[1] + lw], fill=COLORS[i])
    return im


def graph(pos, neg, seed, size, pose_name, strength, end):
    g = comfy.t2i(pos, seed, w=size[0], h=size[1], neg=neg, prefix='v3poc_p62')
    g['20'] = {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': CONTROLNET}}
    g['23'] = {'class_type': 'SetUnionControlNetType', 'inputs': {'control_net': ['20', 0], 'type': 'openpose'}}
    g['21'] = {'class_type': 'LoadImage', 'inputs': {'image': pose_name}}
    g['22'] = {'class_type': 'ControlNetApplyAdvanced', 'inputs': {
        'positive': ['2', 0], 'negative': ['3', 0], 'control_net': ['23', 0], 'image': ['21', 0],
        'strength': strength, 'start_percent': 0.0, 'end_percent': end}}
    g['5']['inputs']['positive'] = ['22', 0]
    g['5']['inputs']['negative'] = ['22', 1]
    return g


def sheet(name, size):
    """1行目に骨格の図、続けて段ごとに seed を並べる。"""
    def row(ims):
        ims = [i.resize((int(i.width * 260 / i.height), 260)) for i in ims]
        r = Image.new('RGB', (sum(i.width for i in ims) + 6 * len(ims), 260), 'white')
        x = 0
        for i in ims:
            r.paste(i, (x, 0))
            x += i.width + 6
        return r
    rows = [row([Image.open(OUT / f'{name}_{m}_{s}.png') for s in SEEDS]) for m in MODES]
    pose = row([Image.open(OUT / 'pose' / f'{name}.png')])
    s = Image.new('RGB', (max(r.width for r in rows) + pose.width, 266 * len(rows)), 'white')
    s.paste(pose, (0, 0))
    for k, r in enumerate(rows):
        s.paste(r, (pose.width, k * 266))
    s.save(OUT / f'sheet_{name}.png')


def main():
    rec = []
    for name, size, who, words, neg_words, people in VIEWS:
        pos, neg = f'{BASE.format(who=who)}, {words}', f'{comfy.NEG}, {neg_words}'
        pose_path = OUT / 'pose' / f'{name}.png'
        draw_pose(size, people).save(pose_path)
        pose_name = comfy.upload(str(pose_path), f'v3poc_p62_{name}.png')
        for m, (strength, end) in MODES.items():
            for s in SEEDS:
                fn = OUT / f'{name}_{m}_{s}.png'
                if not fn.exists():
                    imgs, t = comfy.run(graph(pos, neg, s, size, pose_name, strength, end))
                    fn.write_bytes(imgs[0])
                    print(name, m, s, round(t, 1), flush=True)
                rec.append({'view': name, 'mode': m, 'seed': s, 'strength': strength, 'end': end})
        sheet(name, size)
        (OUT / 'gen.json').write_text(json.dumps({
            'ckpt': comfy.CKPT, 'controlnet': CONTROLNET, 'union_type': 'openpose', 'steps': 25, 'cfg': 5.0,
            'sampler': 'euler_ancestral', 'scheduler': 'normal', 'size': {v[0]: v[1] for v in VIEWS},
            'prompts': {v[0]: {'prompt': f'{BASE.format(who=v[2])}, {v[3]}', 'negative': f'{comfy.NEG}, {v[4]}'} for v in VIEWS},
            'runs': rec}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
