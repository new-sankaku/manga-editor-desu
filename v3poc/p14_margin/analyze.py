"""P14 の測定。人物の検出器で、人数・人物の高さと面積の割合・置いた枠との重なりを出す。
使い方: python analyze.py <検出器の仮想環境のpython>"""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402

MODES = ['text', 'shrink', 'pose_xinsir', 'pose_union', 'pose_windsing', 'pose_t2i', 'crop', 'outpaint']


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


def main():
    det_json = OUT / 'detect.json'
    if len(sys.argv) > 1:
        subprocess.run([sys.argv[1], str(HERE.parent / 'common' / 'detect.py'), str(OUT), str(det_json)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    det = {r['file']: r for r in json.loads(det_json.read_text(encoding='utf-8'))}
    gen = json.loads((OUT / 'gen.json').read_text(encoding='utf-8'))
    rows = []
    for r in gen['runs']:
        d = det[r['file']]
        fig = gen['shapes'][r['shape']]['fig']
        ps = sorted([p for p in d['persons'] if p['score'] >= 0.5], key=lambda p: -p['area_ratio'])
        top = ps[0] if ps else None
        rows.append({**r, 'persons': len(ps), 'h_ratio': top and top['h_ratio'], 'area_ratio': top and top['area_ratio'],
                     'fig_iou': top and round(iou((top['x0'], top['y0'], top['x1'], top['y1']), fig), 2), 'touch': top and top['touch']})
    summ = {}
    for shape in gen['shapes']:
        for m in MODES:
            g = [x for x in rows if x['shape'] == shape and x['mode'] == m]
            ok = [x for x in g if x['persons']]
            summ[f'{shape}/{m}'] = {
                'one_person': sum(1 for x in g if x['persons'] == 1), 'n': len(g),
                'h_ratio': round(sum(x['h_ratio'] for x in ok) / len(ok), 2) if ok else None,
                'area_ratio': round(sum(x['area_ratio'] for x in ok) / len(ok), 2) if ok else None,
                'fig_iou': round(sum(x['fig_iou'] for x in ok) / len(ok), 2) if ok else None,
                'sec': round(sum(x['sec'] for x in g) / len(g), 1) if g else None}
    (OUT / 'result.json').write_text(json.dumps({'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in summ.items():
        print(k, v)
    tw = {'yoko': 300, 'tate': 90, 'std': 200}
    for shape in gen['shapes']:
        rs = [('骨格', [(OUT / 'aux' / f'pose_{shape}.png', '')])]
        rs += [(m, [(OUT / f'{shape}_{m}_{s}.png', str(s)) for s in (61, 62, 63)]) for m in MODES]
        sheet(rs, OUT / f'sheet_{shape}.png', tw=tw[shape], label_w=120)


if __name__ == '__main__':
    main()
