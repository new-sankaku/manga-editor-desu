"""P64 文で書いたポーズを LLM に関節の角度へ直させ、骨格の図と奥行きの図にして ControlNet で作れるか。
1回目：文から角度を決める。2回目：その角度で描いた骨格の図（正面・横・上）を LLM が見て、直すか決める。
LLM は Claude の CLI（sonnet、空のフォルダから。p60 と同じ）。絵は SDXL と xinsir の union promax。言葉だけの手は比べない。
結果は out/ に LLM の答え（llm/）・骨格と奥行きの図（cond/）・絵・一覧（sheet_<ポーズ>.png）・gen.json。"""
import json
import os
import pathlib
import subprocess
import sys
import time

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'common'))
sys.path.insert(0, str(HERE.parent.parent / 'v3' / 'server' / 'src'))
import comfy  # noqa: E402
import rig  # noqa: E402

OUT = HERE / 'out'
for d in ('llm', 'cond'):
    (OUT / d).mkdir(parents=True, exist_ok=True)
EMPTY = pathlib.Path(os.environ.get('TEMP', '/tmp')) / 'v3poc_p64_empty'
BASE = 'best quality, monochrome, greyscale, manga, screentone, 1girl, solo, short black bob hair, school blazer, pleated skirt, classroom'
NEG = f'{comfy.NEG}, nsfw, panties, underwear'
CONTROLNET = 'xinsir\\union-sdxl-1.0-promax.safetensors'
SEEDS = [4001, 4002]
MODES = {'OP': [('openpose', 0.8, 0.8)], 'DP': [('depth', 0.7, 0.8)],
         'MIX': [('openpose', 0.6, 0.8), ('depth', 0.5, 0.6)]}
# (名前, LLM に渡す文, 絵の言葉)
POSES = [
    ('run', '全力で走っている', 'running'),
    ('chair_crossed', '椅子に座って脚を組んでいる', 'sitting, crossed legs'),
    ('seiza', '床に正座している', 'seiza, sitting on floor'),
    ('one_knee', '片膝をついてしゃがんでいる', 'kneeling on one knee'),
    ('stretch', '両手を真上に挙げて伸びをしている', 'arms up, stretching'),
    ('arms_crossed', '腕を組んで立っている', 'crossed arms, standing'),
    ('pointing', '片手で前をまっすぐ指さしている', 'pointing forward, standing'),
    ('head_hold', '頭を両手で抱えてうずくまっている', 'squatting, hands on own head'),
    ('jump', '両脚を曲げて高く跳んでいる', 'jumping, midair'),
    ('lying_back', '床に仰向けに寝ている', 'lying on back, on floor'),
    ('out_of_breath', '前かがみで両手を膝につき、息を切らしている', 'bent over, hands on knees, out of breath'),
    ('wave_back', '体は向こうを向いたまま、振り返って手を振っている', 'looking back, waving'),
    ('hug_knees', '床に座り、両腕で膝を抱えている', 'sitting, hugging own knees'),
    ('one_leg', '片足で立ち、もう片方の膝を高く上げている', 'standing on one leg, knee up'),
    ('dogeza', '床に土下座している', 'dogeza, kneeling, bowing'),
    ('punch', '片手の拳を前へ突き出している', 'punching, fist forward'),
    ('kick', '片脚を横へ高く蹴り上げている', 'high kick'),
    ('lean_back', '後ろへ大きく反って空を見上げている', 'leaning back, looking up'),
]
# (名前, 向き, 上下の角度, 絵の言葉)
CAMS = [('c1', 20, 10, ''), ('c2', 100, 30, 'from side, from above'), ('c3', -35, -25, 'from below')]


def _llm(question, image=None):
    EMPTY.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ('CLAUDE_CODE_SESSION_ID', 'CLAUDE_CODE_REMOTE_SESSION_ID', 'CLAUDECODE')}
    cmd = ['claude', '-p', '--model', 'sonnet', '--output-format', 'json', '--no-session-persistence', '--max-turns', '4']
    if image:
        cmd += ['--allowedTools', 'Read']
    t0 = time.time()
    r = subprocess.run(cmd, input=question.encode('utf-8'), capture_output=True, cwd=str(EMPTY), env=env, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace')[:300])
    res = json.loads(r.stdout)
    text = res.get('result', '')
    s, e = text.find('{'), text.rfind('}')
    return json.loads(text[s:e + 1]), {'cost': res.get('total_cost_usd'), 'seconds': round(time.time() - t0, 1), 'raw': text}


def _joint_lines():
    return '\n'.join(f'・{k}：{m}（{lo}〜{hi}）' for k, (m, lo, hi) in rig.JOINTS.items())


FORMAT = '出力はJSONだけにしてください。形式：{"angles":{"関節の名前":数}}。書かなかった関節は0（まっすぐ立った形）になります。'  # i18n:prompt


def first_question(text):  # i18n:prompt
    return f"""漫画のコマの人物のポーズを、立体の人形の関節の角度で表してください。この角度から骨格の図と奥行きの図を描き、画像生成のモデルに形として渡します。

ポーズ：{text}

人形は身長およそ1.6mで、角度が全部0のとき、まっすぐ立って腕を体の横に垂らし、正面を向きます。左右は人物から見た左右です。
カメラの向きは別に決めるので、ここではポーズだけを決めてください。

関節（意味・取れる範囲。範囲の外は範囲の端に切られます）：
{_joint_lines()}

文に書かれていない所の決め方には、次のような手があります。どれを選ぶかは任せます。
・その動きで漫画によく描かれる形に寄せる：読み手に伝わりやすいが、どのコマも同じ形になりやすい
・書かれた所だけを動かし、ほかは0に近く残す：文から外れにくいが、硬く不自然な形になりやすい
・左右を変えて非対称にする：自然に見えやすいが、文の狙いとずれた所が目立つことがある

{FORMAT}"""


def second_question(text, angles, path):  # i18n:prompt
    return f"""漫画のコマの人物のポーズを、立体の人形の関節の角度で表しています。この角度で描いた骨格の図を確かめ、必要なら直してください。

ポーズ：{text}

今の角度：{json.dumps(angles, ensure_ascii=False)}

骨格の図のファイル：{path}
左から、正面から・人物の左の横から・上から見た図です。点と線の色は OpenPose の描き方で、顔の点は見えない側を描いていません。

関節（意味・取れる範囲）：
{_joint_lines()}

図とポーズの文が合わない所の扱いには、次のような手があります。どれを選ぶかは任せます。
・合わない関節だけを直す：合っている所が保たれるが、直した所とほかの所の釣り合いが崩れることがある
・全体を決め直す：釣り合いは取りやすいが、合っていた所まで変わることがある
・そのまま返す：図が文に合っているなら手間がかからないが、見落としがあるとそのまま絵に出る

{FORMAT}"""


def graph(pos, seed, w, h, conds):
    g = comfy.t2i(pos, seed, w=w, h=h, neg=NEG, prefix='v3poc_p64')
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


def angles_for(name, text):
    """LLM の2回の答えを out/llm/<名前>.json に残し、2回目の角度を返す（残っていれば聞き直さない）。"""
    path = OUT / 'llm' / f'{name}.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    a1, m1 = _llm(first_question(text))
    img1 = OUT / 'llm' / f'{name}_check1.png'
    rig.check_views(rig.build(a1['angles'])).save(img1)
    a2, m2 = _llm(second_question(text, a1['angles'], str(img1)), image=True)
    rig.check_views(rig.build(a2['angles'])).save(OUT / 'llm' / f'{name}_check2.png')
    rec = {'text': text, 'first': a1['angles'], 'second': a2['angles'], 'calls': [m1, m2]}
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
    return rec


def size_for(cam):
    """写した骨格が横に広いなら横長の絵にする。"""
    pr = rig.project(cam[0], cam)[:18, :2]
    span = pr.max(0) - pr.min(0)
    return (1216, 832) if span[0] > span[1] * 1.2 else (832, 1216)


def sheet(name):
    def row(ims, hgt=280):
        ims = [i.resize((int(i.width * hgt / i.height), hgt)) for i in ims]
        r = Image.new('RGB', (sum(i.width for i in ims) + 6 * len(ims), hgt), 'white')
        x = 0
        for i in ims:
            r.paste(i, (x, 0))
            x += i.width + 6
        return r
    rows = [row([Image.open(OUT / 'llm' / f'{name}_check2.png')], 220)]
    for c, *_ in CAMS:
        conds = [Image.open(OUT / 'cond' / f'{name}_{c}_{k}.png') for k in ('pose', 'depth')]
        rows.append(row(conds + [Image.open(OUT / f'{name}_{c}_{m}_{s}.png') for m in MODES for s in SEEDS]))
    s = Image.new('RGB', (max(r.width for r in rows), sum(r.height + 6 for r in rows)), 'white')
    y = 0
    for r in rows:
        s.paste(r, (0, y))
        y += r.height + 6
    s.save(OUT / f'sheet_{name}.png')


def main():
    rec = []
    for name, text, words in POSES:
        a = angles_for(name, text)
        P = rig.build(a['second'])
        for c, yaw, pitch, cam_words in CAMS:
            cam = rig.camera(P, yaw, pitch)
            rig.W, rig.H = size_for(cam)
            names = {}
            for kind, im in (('pose', rig.draw_pose(cam)), ('depth', rig.draw_depth(cam))):
                path = OUT / 'cond' / f'{name}_{c}_{kind}.png'
                im.save(path)
                names['openpose' if kind == 'pose' else 'depth'] = comfy.upload(str(path), f'v3poc_p64_{name}_{c}_{kind}.png')
            pos = ', '.join(t for t in (BASE, words, cam_words) if t)
            for m, conds in MODES.items():
                for s in SEEDS:
                    fn = OUT / f'{name}_{c}_{m}_{s}.png'
                    if not fn.exists():
                        imgs, t = comfy.run(graph(pos, s, rig.W, rig.H, [(k, names[k], st, e) for k, st, e in conds]))
                        fn.write_bytes(imgs[0])
                        print(name, c, m, s, round(t, 1), flush=True)
            rec.append({'pose': name, 'cam': c, 'yaw': yaw, 'pitch': pitch, 'size': [rig.W, rig.H], 'prompt': pos})
        rig.W, rig.H = 832, 1216
        sheet(name)
        (OUT / 'gen.json').write_text(json.dumps({
            'ckpt': comfy.CKPT, 'controlnet': CONTROLNET, 'steps': 25, 'cfg': 5.0, 'sampler': 'euler_ancestral',
            'negative': NEG, 'seeds': SEEDS, 'llm': 'claude CLI sonnet',
            'modes': {m: [{'type': k, 'strength': st, 'end': e} for k, st, e in cs] for m, cs in MODES.items()},
            'runs': rec}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1:] == ['llm']:  # LLM の答えと確認の図だけ作る
        for name, text, _ in POSES:
            angles_for(name, text)
            print(name, flush=True)
    else:
        main()
