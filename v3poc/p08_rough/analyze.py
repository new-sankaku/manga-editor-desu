"""P8の解析。人物の枠がラフの棒人間の位置に来たか（IoU）、フキダシの丸の内側が空いているか（暗い画素の割合・顔が入ったか）。"""
import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / (sys.argv[2] if len(sys.argv) > 2 else 'out')
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402

VENV = sys.argv[1] if len(sys.argv) > 1 else None


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


def main():
    g = json.loads((OUT / 'gen.json').read_text(encoding='utf-8'))
    FIG, BAL = g['FIG'], g['BAL']
    imgdir = OUT / 'imgs'
    imgdir.mkdir(exist_ok=True)
    for r in g['runs']:
        src = OUT / r['file']
        if src.exists():
            src.replace(imgdir / r['file'])
    if not (OUT / 'detect.json').exists():
        subprocess.run([VENV, str(HERE.parent / 'common' / 'detect.py'), str(imgdir), str(OUT / 'detect.json')], check=True)
    det = {d['file']: d for d in json.loads((OUT / 'detect.json').read_text(encoding='utf-8'))}
    m = Image.new('L', (832, 1216), 0)
    ImageDraw.Draw(m).ellipse((BAL[0] + 25, BAL[1] + 25, BAL[2] - 25, BAL[3] - 25), fill=255)
    inner = np.asarray(m) > 0
    rows = []
    for r in g['runs']:
        d = det[r['file']]
        a = np.asarray(Image.open(imgdir / r['file']).convert('L'))
        ps = sorted(d['persons'], key=lambda p: -p['score'])
        best = max((iou((p['x0'], p['y0'], p['x1'], p['y1']), FIG) for p in ps), default=0)
        face_in = any(BAL[0] < (f['x0'] + f['x1']) / 2 < BAL[2] and BAL[1] < (f['y0'] + f['y1']) / 2 < BAL[3] for f in d['faces'])
        rows.append({**r, 'fig_iou': round(best, 2), 'persons': len(ps), 'balloon_dark_ratio': round(float((a[inner] < 100).mean()), 3),
                     'face_in_balloon': face_in})
    summ = {}
    for key in sorted({(r['cn'], r.get('polarity'), r.get('strength')) for r in rows}, key=str):
        rs = [r for r in rows if (r['cn'], r.get('polarity'), r.get('strength')) == key]
        summ['/'.join(str(k) for k in key)] = {'fig_iou_mean': round(sum(r['fig_iou'] for r in rs) / len(rs), 2),
                                              'balloon_dark_mean': round(sum(r['balloon_dark_ratio'] for r in rs) / len(rs), 3),
                                              'face_in_balloon': sum(r['face_in_balloon'] for r in rs), 'n': len(rs),
                                              'sec_mean': round(sum(r['sec'] for r in rs) / len(rs), 1)}
    (OUT / 'result.json').write_text(json.dumps({'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in summ.items():
        print(k, v)
    if OUT.name != 'out':
        modes = sorted({r['cn'] for r in g['runs']})
        sheet([('骨格の図', [(OUT / 'pose.png', '骨格')])] + [(m, [(imgdir / f'{m}_{s}.png', str(s)) for s in (11, 12, 13)]) for m in modes], OUT / 'sheet.png', tw=130, label_w=170)
        return
    # 目で見る一覧：ラフ＋制御なし、各設定のseed3枚
    lines = [('ラフ', [(OUT / 'rough_bw.png', 'ラフ')] + [(imgdir / f'none_{s}.png', f'制御なし {s}') for s in (11, 12, 13)])]
    for cn in ('t2i_sketch', 'sai_sketch'):
        for pol in ('wb', 'bw'):
            for st in (0.6, 1.0):
                lines.append((f'{cn}\n{"黒地白線" if pol == "wb" else "白地黒線"} {st}', [(imgdir / f'{cn}_{pol}_{st}_{s}.png', str(s)) for s in (11, 12, 13)]))
    sheet(lines[:5], OUT / 'sheet_1.png', tw=130, label_w=150)
    sheet([lines[0]] + lines[5:], OUT / 'sheet_2.png', tw=130, label_w=150)


if __name__ == '__main__':
    main()
