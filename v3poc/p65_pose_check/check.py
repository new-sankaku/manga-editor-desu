"""P65 予定した骨格と、出た絵から DWPose（imgutils、Apache-2.0）で取り出した骨格を比べ、構図のずれを自動で見つけられるか。
対象は p63（アングル・注目する位置）と p64（LLM が決めたポーズ）の絵。予定の点は両方の試作と同じ計算で出し直す。
測る物（予定で見えている点だけ）：
- pck：予定の点から、体の大きさ（予定の点の枠の対角）の 0.1 以内に取り出した点がある割合
- swap_pck：取り出した点の左右の名前を入れ替えたときの pck（こちらが大きく上回れば、前後か左右の取り違え）
- face：予定で鼻が見えるか・取り出した鼻が確かか（後ろ姿の予定で顔が出たか、その逆）
- face_det：顔の検出器（imgutils）で顔が見つかったか。鼻の確かさと、前後の見張り役としてどちらが合うかを比べる
- iou：背景を抜いた人物の形（anime-seg、Apache-2.0）と、予定の人形の形（奥行きの図の塗られた所を、服と髪の分だけ太らせた物）の重なり
結果は out/result.json と、印を付けた一覧 out/sheet_<試作>_<組>.png（緑の丸が予定、赤の×が取り出した点、青の線が予定の形の縁）。"""
import importlib.util
import json
import pathlib
import sys

import numpy as np
from imgutils.detect import detect_faces
from imgutils.pose import dwpose_estimate
from imgutils.segment import get_isnetis_mask
from PIL import Image, ImageDraw, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent
V3POC = HERE.parent
sys.path.insert(0, str(V3POC / 'common'))
sys.path.insert(0, str(V3POC.parent / 'v3' / 'server' / 'src'))
sys.path.insert(0, str(V3POC / 'p64_llm_pose'))
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
SWAP = [0, 1, 5, 6, 7, 2, 3, 4, 11, 12, 13, 8, 9, 10, 15, 14, 17, 16]
THR = 0.3
IOU_MIN = 0.4  # 仮の値。目の判定と突き合わせて決め直す
GROW = 0.03  # 予定の形を太らせる幅（絵の高さに対する割合）。服と髪の分


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _visible(Q, pr, head, C):
    to_cam = (C - head) / np.linalg.norm(C - head)
    vis = np.array([pr[i, 2] > .05 for i in range(18)])
    for i in (0, 14, 15, 16, 17):
        vec = Q[i] - head
        if vec @ to_cam / np.linalg.norm(vec) < -0.15:
            vis[i] = False
    return vis


def plans():
    """(試作, 組, 絵のファイル, 予定の点 18x2, 見えるか 18, 絵の大きさ)。"""
    p63 = _load('p63run', V3POC / 'p63_angles' / 'run.py')
    for name, yaw, pitch, frame, roll in p63.views():
        cam = p63.camera(yaw, pitch, frame, roll)
        Q = p63.KP @ cam[0].T
        pr = p63.project(Q, cam)
        vis = _visible(Q, pr, cam[0] @ p63.HEAD, cam[1])
        for m in p63.MODES:
            for s in p63.SEEDS:
                yield 'p63', name, m, p63.OUT / f'{name}_{m}_{s}.png', pr[:, :2], vis, p63.OUT / 'cond' / f'{name}_depth.png'
    p64 = _load('p64run', V3POC / 'p64_llm_pose' / 'run.py')
    rig = p64.rig
    for name, _, _ in p64.POSES:
        f = p64.OUT / 'llm' / f'{name}.json'
        if not f.exists():
            continue
        P = rig.build(json.loads(f.read_text(encoding='utf-8'))['second'])
        for c, yaw, pitch, _ in p64.CAMS:
            cam = rig.camera(P, yaw, pitch)
            rig.W, rig.H = p64.size_for(cam)
            pr = rig.project(cam[0], cam)
            vis = _visible(cam[0], pr, cam[0][18], cam[1])
            for m in p64.MODES:
                for s in p64.SEEDS:
                    yield 'p64', f'{name}_{c}', m, p64.OUT / f'{name}_{c}_{m}_{s}.png', pr[:18, :2].copy(), vis, p64.OUT / 'cond' / f'{name}_{c}_depth.png'
            rig.W, rig.H = 832, 1216


def pck(plan, vis, det, thr):
    ok = vis & (det[:, 2] >= THR)
    if not vis.any():
        return 0.0
    d = np.linalg.norm(plan[:, :2] - det[:, :2], axis=1)
    return float(((d <= thr) & ok).sum() / vis.sum())


def measure(plan, vis, people):
    pts = plan[vis]
    size = float(np.linalg.norm(pts.max(0) - pts.min(0)))
    best = None
    for p in people:
        det = np.asarray(p.body)[:18]
        r = {'pck': pck(plan, vis, det, .1 * size), 'swap_pck': pck(plan, vis, det[SWAP], .1 * size), 'det': det}
        if best is None or max(r['pck'], r['swap_pck']) > max(best['pck'], best['swap_pck']):
            best = r
    if best is None:
        return {'people': 0, 'pck': 0.0, 'swap_pck': 0.0, 'plan_face': bool(vis[0]), 'det_face': False, 'det': None}
    best.update(people=len(people), plan_face=bool(vis[0]), det_face=bool(best['det'][0, 2] >= THR))
    return best


def plan_shape(depth_path):
    """予定の人形の形（1/4 の大きさ）と、服と髪の分だけ太らせた形。"""
    d = Image.open(depth_path).convert('L')
    small = d.resize((d.width // 4, d.height // 4)).point(lambda v: 255 if v > 0 else 0)
    k = int(d.height / 4 * GROW) // 2 * 2 + 1
    return small, small.filter(ImageFilter.MaxFilter(k))


def shape_iou(im, depth_path):
    small, grown = plan_shape(depth_path)
    mask = Image.fromarray((get_isnetis_mask(im) * 255).astype(np.uint8)).resize(small.size)
    m, g = np.asarray(mask) > 127, np.asarray(grown) > 127
    union = (m | g).sum()
    return float((m & g).sum() / union) if union else 0.0, small


def verdict(r):
    """外れの印。理由を並べる（無ければ合格）。"""
    why = []
    if r['people'] == 0:
        why.append('人が見つからない')
    if r['pck'] < .5:
        why.append('点がずれる')
    if r['swap_pck'] > r['pck'] + .2:
        why.append('左右か前後が逆')
    if r['iou'] < IOU_MIN:
        why.append('形が合わない')
    if r['plan_face'] != r['face_det']:
        why.append('顔が出た' if r['face_det'] else '顔が無い')
    return why


def main():
    rows, groups = [], {}
    for src, group, mode, path, plan, vis, depth in plans():
        if not path.exists():
            continue
        im = Image.open(path).convert('RGB')
        r = measure(plan, vis, dwpose_estimate(im))
        r['iou'], small = shape_iou(im, depth)
        r['face_det'] = bool(detect_faces(im, conf_threshold=THR))
        why = verdict(r)
        rows.append({'src': src, 'group': group, 'mode': mode, 'file': str(path.relative_to(V3POC)).replace('\\', '/'),
                     'pck': round(r['pck'], 2), 'swap_pck': round(r['swap_pck'], 2), 'people': r['people'],
                     'iou': round(r['iou'], 2), 'plan_face': r['plan_face'], 'det_face': r['det_face'], 'face_det': r['face_det'], 'flags': why})
        th = im.copy()
        d = ImageDraw.Draw(th)
        for (x, y), v in zip(plan, vis):
            if v:
                d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(0, 200, 0), width=4)
        if r['det'] is not None:
            for x, y, sc in r['det']:
                if sc >= THR:
                    d.line([x - 9, y - 9, x + 9, y + 9], fill=(230, 0, 0), width=4)
                    d.line([x - 9, y + 9, x + 9, y - 9], fill=(230, 0, 0), width=4)
        edge = small.filter(ImageFilter.FIND_EDGES).resize(im.size).point(lambda v: 255 if v > 0 else 0)
        th.paste((40, 90, 255), mask=edge.filter(ImageFilter.MaxFilter(5)))
        if why:
            d.rectangle([0, 0, th.width - 1, th.height - 1], outline=(230, 0, 0), width=14)
        groups.setdefault((src, group), []).append(th.resize((int(th.width * 300 / th.height), 300)))
        print(group, mode, path.stem[-4:], rows[-1]['pck'], rows[-1]['swap_pck'], rows[-1]['iou'], why, flush=True)
    for (src, group), ims in groups.items():
        s = Image.new('RGB', (sum(i.width + 6 for i in ims), 300), 'white')
        x = 0
        for i in ims:
            s.paste(i, (x, 0))
            x += i.width + 6
        s.save(OUT / f'sheet_{src}_{group}.png')
    (OUT / 'result.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    print('外れの印', sum(1 for r in rows if r['flags']), '/', len(rows))


if __name__ == '__main__':
    main()
