"""P37 目の判定（out/labels.json：頭か足が画面の端で切れているか）と、人物の検出枠が端に接するか（P02 の detect.json）を突き合わせる。
枠は人物の検出のうちいちばん確かなもの。接するとは P02 の判定（枠の辺が画像の端から数画素以内）。
使い方: python analyze.py"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
P02 = HERE.parent / 'p02_instruction' / 'out'
OUT = HERE / 'out'


def main():
    det = {x['file']: x for x in json.loads((P02 / 'detect.json').read_text(encoding='utf-8'))}
    lab = json.loads((OUT / 'labels.json').read_text(encoding='utf-8'))
    res = {}
    rows = []
    for side, key in (('B', 'cut_bottom'), ('T', 'cut_top')):
        tp = fp = fn = tn = 0
        for f, l in lab.items():
            ps = det[f]['persons']
            touch = side in max(ps, key=lambda p: p['score'])['touch'] if ps else False
            if side == 'B':
                rows.append({'file': f, 'touch': max(ps, key=lambda p: p['score'])['touch'] if ps else '', **l})
            tp += touch and l[key]
            fp += touch and not l[key]
            fn += (not touch) and l[key]
            tn += (not touch) and not l[key]
        res[side] = {'cut_and_touch': tp, 'not_cut_but_touch': fp, 'cut_but_no_touch': fn, 'not_cut_no_touch': tn}
    by = {}
    for r in rows:
        k = r['file'].rsplit('_', 1)[0]
        by.setdefault(k, {'n': 0, 'cut_bottom': 0, 'touch_B': 0, 'touch_T': 0})
        by[k]['n'] += 1
        by[k]['cut_bottom'] += r['cut_bottom']
        by[k]['touch_B'] += 'B' in r['touch']
        by[k]['touch_T'] += 'T' in r['touch']
    out = {'summary': res, 'by_instruction': by, 'rows': rows}
    (OUT / 'result.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'summary': res, 'by_instruction': by}, ensure_ascii=False))


if __name__ == '__main__':
    main()
