"""P18 の測定。3Dの場所から描いた線画の線が、生成した絵のどれだけに現れたか（線の重なり、候補101）を数え、一覧画像を作る。
線の重なり＝3Dの線の画素のうち、生成した絵の輪郭（明るさの差が大きい所）が近く（R画素以内）にある割合。
間取りが3Dどおりなら高く、ばらばらなら低い。描き込みの多さでも上がるので、同じ絵を「別の向きの3Dの線」とも比べ（other）、その差を見る。
言葉だけ（text）は向きを言い分けられないので、同じ seed なら3つの向きで同じ絵になる。言葉だけの一覧は seed を並べ、コマごとに seed が変わったときの間取りの違いを見る。
使い方: python analyze.py"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
AUX = OUT / 'aux'
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402

R = 3
PCT = 92
MODES = ['text', 'depth', 'line', 'depth_ref']


def edges(path):
    g = Image.open(path).convert('L').filter(ImageFilter.GaussianBlur(1.5)).filter(ImageFilter.FIND_EDGES)
    a = np.asarray(g, dtype=np.float32)
    return a > np.percentile(a, PCT)


def near(mask, r):
    im = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * r + 1))
    return np.asarray(im) > 0


def main():
    gen = json.loads((OUT / 'gen.json').read_text(encoding='utf-8'))
    rows = []
    for r in gen['runs']:
        e = near(edges(OUT / r['file']), R)
        rec = {}
        for v in gen['cams'][r['place']]:
            line = np.asarray(Image.open(AUX / f"{r['place']}_{v}_line.png").convert('L')) < 128
            rec[v] = float((e & line).sum() / line.sum())
        other = [x for v, x in rec.items() if v != r['view']]
        rows.append({**r, 'line_recall': round(rec[r['view']], 3), 'line_recall_other': round(sum(other) / len(other), 3)})
    summ = {}
    for place in gen['cams']:
        for m in MODES:
            g = [x for x in rows if x['place'] == place and x['mode'] == m]
            summ[f'{place}/{m}'] = {'n': len(g), 'line_recall_mean': round(sum(x['line_recall'] for x in g) / len(g), 3),
                                    'line_recall_other_mean': round(sum(x['line_recall_other'] for x in g) / len(g), 3)}
    (OUT / 'result.json').write_text(json.dumps({'radius': R, 'edge_percentile': PCT, 'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in summ.items():
        print(k, v)
    seeds = sorted({r['seed'] for r in gen['runs']})
    views = list(next(iter(gen['cams'].values())))
    blank = AUX / 'blank.png'
    Image.new('RGB', tuple(gen['size']), 'white').save(blank)
    for place in gen['cams']:
        for s in seeds:
            rs = [('3Dの線画', [(AUX / f'{place}_{v}_line.png', v) for v in views])]
            for m in MODES[1:]:
                rs.append((m, [(OUT / f'{place}_{v}_{m}_{s}.png', v) if (OUT / f'{place}_{v}_{m}_{s}.png').exists() else (blank, '参照元なので無し')
                               for v in views]))
            sheet(rs, OUT / f'sheet_{place}_{s}.png', tw=300, label_w=110)
        sheet([('言葉だけ', [(OUT / f'{place}_front_text_{s}.png', f'seed {s}') for s in seeds])], OUT / f'sheet_{place}_text.png', tw=300, label_w=110)


if __name__ == '__main__':
    main()
