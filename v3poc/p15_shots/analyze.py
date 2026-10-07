"""P15 の測定。人物の検出器で人数と、いちばん大きい人物の高さ・面積の割合を出す。狙いごとに一覧画像（行＝絵柄、列＝seed）を作る。
使い方: python analyze.py <検出器の仮想環境のpython>"""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402


def main():
    det_json = OUT / 'detect.json'
    if len(sys.argv) > 1:
        subprocess.run([sys.argv[1], str(HERE.parent / 'common' / 'detect.py'), str(OUT), str(det_json)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    det = {r['file']: r for r in json.loads(det_json.read_text(encoding='utf-8'))}
    gen = json.loads((OUT / 'gen.json').read_text(encoding='utf-8'))
    rows = []
    for r in gen['runs']:
        ps = sorted([p for p in det[r['file']]['persons'] if p['score'] >= 0.5], key=lambda p: -p['area_ratio'])
        top = ps[0] if ps else None
        rows.append({'file': r['file'], 'style': r['style'], 'target': r['target'], 'seed': r['seed'], 'sec': r['sec'], 'persons': len(ps),
                     'h_ratio': top and top['h_ratio'], 'area_ratio': top and top['area_ratio'], 'touch': top and top['touch']})
    summ = {}
    for t in gen['targets']:
        for s in gen['styles']:
            g = [x for x in rows if x['target'] == t and x['style'] == s]
            summ[f'{t}/{s}'] = {'persons': [x['persons'] for x in g], 'h_ratio': [x['h_ratio'] for x in g], 'sec': round(sum(x['sec'] for x in g) / len(g), 1)}
    (OUT / 'result.json').write_text(json.dumps({'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in summ.items():
        print(k, v)
    seeds = sorted({r['seed'] for r in gen['runs']})
    tw = {(1536, 576): 300, (576, 1536): 90, (1152, 896): 200, (832, 1216): 140}
    for t, tv in gen['targets'].items():
        rs = []
        for s, sv in gen['styles'].items():
            cells = [(OUT / f'{s}_{t}_{sd}.png', str(sd)) for sd in seeds]
            if tv['cut']:
                cells += [(OUT / f'{s}_{t}_{sd}_cut.png', f'{sd} 抜き') for sd in seeds]
            rs.append((sv['name'], cells))
        sheet(rs, OUT / f'sheet_{t}.png', tw=tw[tuple(tv['size'])], label_w=170)


if __name__ == '__main__':
    main()
