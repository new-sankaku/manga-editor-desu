"""P16 の測定。人物の検出器で人数と人物の高さを出し、狙いごとに一覧画像（行＝人物×場所、列＝seed）を作る。
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
        rows.append({k: r[k] for k in ('file', 'target', 'chara', 'place', 'seed')} | {'persons': len(ps), 'h_ratio': ps[0]['h_ratio'] if ps else None})
    (OUT / 'result.json').write_text(json.dumps({'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    seeds = sorted({r['seed'] for r in gen['runs']})
    persons = {x['file']: x['persons'] for x in rows}
    tw = {(1536, 576): 260, (576, 1536): 80, (1152, 896): 180, (832, 1216): 130}
    for t in sorted({r['target'] for r in gen['runs']}):
        rs = []
        combos = sorted({(r['chara'], r['place']) for r in gen['runs'] if r['target'] == t}, key=str)
        size = next(tuple(r['size']) for r in gen['runs'] if r['target'] == t)
        for c, p in combos:
            label = '・'.join(x for x in (gen['charas'][c]['name'] if c else '', gen['places'][p]['name'] if p else '') if x)
            names = [f'{t}_{c or "none"}_{p or "none"}_{s}.png' for s in seeds]
            cells = [(OUT / n, f'{s} 人{persons[n]}') for n, s in zip(names, seeds)]
            if t == 'chara_only':
                cells += [(OUT / f'{t}_{c}_none_{s}_cut.png', f'{s} 抜き') for s in seeds]
            rs.append((label, cells))
        sheet(rs, OUT / f'sheet_{t}.png', tw=tw[size], label_w=250)
    for t in sorted({r['target'] for r in rows}):
        g = [x for x in rows if x['target'] == t]
        print(t, 'n', len(g), 'persons', [x['persons'] for x in g])


if __name__ == '__main__':
    main()
