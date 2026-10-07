"""P6 MagiV2 の結果を測る。
 synth : 合成ページのコマ数と、正解の多角形の外接四角との重なり（IoU 0.5以上で当たり）
 p02   : 人物の数を、目の判定（2人・3人の指示）と比べる
 p10   : 1枚で作ったページのコマ数（目の判定 labels.json と比べる）
 real  : 実際のページ（斜めのコマ）。正解が無いので、検出した枠を重ねた画像を作って目で見る"""
import json
import pathlib
import sys

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
RL = OUT / 'real_local'  # 他人の作品を含むのでリポジトリに入れない（.gitignore）
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


def overlay(rec, dst):
    im = Image.open(rec['file']).convert('RGB')
    d = ImageDraw.Draw(im)
    lw = max(3, im.width // 200)
    for i, b in enumerate(rec['panels']):
        d.rectangle(b, outline=(220, 30, 30), width=lw)
        d.text((b[0] + 8, b[1] + 8), str(i + 1), fill=(220, 30, 30))
    for b in rec['characters']:
        d.rectangle(b, outline=(30, 90, 220), width=max(2, lw // 2))
    for b in rec['texts']:
        d.rectangle(b, outline=(30, 160, 60), width=max(2, lw // 2))
    im.save(dst)


def main():
    det = {pathlib.Path(r['file']).name + '|' + pathlib.Path(r['file']).parent.name: r for r in json.loads((OUT / 'magi.json').read_text(encoding='utf-8'))}
    res = {}
    truth = json.loads((HERE / 'synth' / 'truth.json').read_text(encoding='utf-8'))
    rows = []
    for n, t in truth.items():
        r = det[f'{n}.png|synth']
        S, (ox, oy) = t['scale_px_per_mm'], t['origin_mm']
        gts = [[(min(x for x, _ in p) + ox) * S, (min(y for _, y in p) + oy) * S, (max(x for x, _ in p) + ox) * S, (max(y for _, y in p) + oy) * S] for p in t['polys_mm']]
        hit = sum(1 for g in gts if any(iou(g, b) >= 0.5 for b in r['panels']))
        rows.append({'page': n, 'truth': t['count'], 'detected': len(r['panels']), 'matched_iou50': hit})
        overlay(r, OUT / f'synth_{n}.png')
    res['synth'] = rows
    lab = json.loads((HERE.parent / 'p02_instruction' / 'out' / 'labels.json').read_text(encoding='utf-8'))
    p2 = []
    for k, r in det.items():
        name, folder = k.split('|')
        if folder != 'out' or not ('two_people' in name or 'three_people' in name):
            continue
        want = 2 if 'two' in name else 3
        eye_ok = lab[name[:-4]]['ok']
        p2.append({'file': name, 'want': want, 'magi_chars': len(r['characters']), 'eye_ok': eye_ok})
    res['p02_people'] = {'rows': p2, 'magi_equals_want': sum(1 for x in p2 if x['magi_chars'] == x['want']),
                         'agree_with_eye': sum(1 for x in p2 if (x['magi_chars'] == x['want']) == x['eye_ok']), 'n': len(p2)}
    p10lab = HERE.parent / 'p10_page' / 'out' / 'labels.json'
    p10l = json.loads(p10lab.read_text(encoding='utf-8')) if p10lab.exists() else {}
    res['p10'] = [{'file': k.split('|')[0], 'magi_panels': len(r['panels']), 'eye_panels': p10l.get(k.split('|')[0][:-4])}
                  for k, r in det.items() if k.endswith('|out') and 'panels_' in k]
    reals = [r for k, r in det.items() if k.endswith('|naname') or k.endswith('|視線誘導')]
    for r in reals:
        RL.mkdir(exist_ok=True)
        overlay(r, RL / f'real_{pathlib.Path(r["file"]).parent.name}_{pathlib.Path(r["file"]).stem}.png')
    res['real'] = [{'file': pathlib.Path(r['file']).name, 'panels': len(r['panels']), 'chars': len(r['characters']), 'texts': len(r['texts'])} for r in reals]
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    sheet([('合成', [(OUT / f'synth_{n}.png', n) for n in truth])], OUT / 'sheet_synth.png', tw=200, label_w=60)
    rp = sorted(RL.glob('real_*.png'))
    if rp:
        sheet([('実物1', [(p, p.stem[5:]) for p in rp[:5]]), ('実物2', [(p, p.stem[5:]) for p in rp[5:10]])], RL / 'sheet_real.png', tw=180, label_w=60)
    print(json.dumps({k: v for k, v in res.items() if k != 'p02_people'}, ensure_ascii=False))
    print({k: v for k, v in res['p02_people'].items() if k != 'rows'})


if __name__ == '__main__':
    main()
