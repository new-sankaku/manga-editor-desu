"""P44 距離（顔・上半身・全身・引き）を、検出器の枠の大きさで決められるか（一覧 3-11）。新しい絵は作らない。
P02 では私が置いた閾値が合わなかった（全身 2/8）。今回は閾値を P02 の狙いどおりの絵から決め直し、別の絵（P16 の全身・引き、P15 の全身・引き）で当たるかを見る。
使う大きさ：人物の枠の高さ・面積（絵に対する割合）と顔の枠の高さ。横長・縦長の絵が混ざるので、高さと面積の両方で試す。
正解は狙いの距離で、目の判定で狙いどおりだった絵だけを使う（P16 は labels.json、P15 は作り方の一覧の labels.json）。
使い方: python run.py"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
V = HERE.parent
ORDER = ['顔', '上半身', '全身', '引き']
P02 = {'close_up': '顔', 'upper_body': '上半身', 'full_body': '全身', 'very_wide': '引き'}
TARGET = {'full_std': '全身', 'long_yoko': '引き', 'long_tate': '引き'}


def feats(r):
    p = max(r['persons'], key=lambda x: x['score']) if r['persons'] else None
    f = max(r['faces'], key=lambda x: x['score']) if r['faces'] else None
    return {'person_h': p['h_ratio'] if p else 0.0, 'person_area': p['area_ratio'] if p else 0.0, 'face_h': f['h_ratio'] if f else 0.0}


def load_p02():
    det = {r['file']: r for r in json.loads((V / 'p02_instruction/out/detect.json').read_text(encoding='utf-8'))}
    lab = json.loads((V / 'p02_instruction/out/labels.json').read_text(encoding='utf-8'))
    out = []
    for f, r in det.items():
        k = f.rsplit('_', 1)[0]
        if k in P02 and lab.get(f[:-4], {}).get('ok'):
            out.append((P02[k], feats(r), f))
    return out


def load_other(name, bad):
    det = json.loads((V / name / 'out/detect.json').read_text(encoding='utf-8'))
    det = det if isinstance(det, list) else [dict(v, file=k) for k, v in det.items()]
    out = []
    for r in det:
        t = next((v for k, v in TARGET.items() if r['file'].startswith(k) or f'_{k}_' in r['file']), None)
        if t and r['file'] not in bad and not r['file'].endswith('_cut.png'):
            out.append((t, feats(r), r['file']))
    return out


def fit(train, key):
    """隣り合う距離の境を、間違いが最も少なくなる値に置く（下の距離ほど値が大きい）。"""
    ths = []
    for a, b in zip(ORDER, ORDER[1:]):
        xs = sorted({x[1][key] for x in train if x[0] in (a, b)})
        best = min(xs, key=lambda t: sum((x[1][key] >= t) != (x[0] == a) for x in train if x[0] in (a, b)))
        ths.append(best)
    return ths


def classify(v, ths):
    for name, t in zip(ORDER, ths):
        if v >= t:
            return name
    return ORDER[-1]


def score(data, key, ths, classes):
    got = [(x[0], classify(x[1][key], ths)) for x in data if x[0] in classes]
    return {'n': len(got), 'correct': sum(a == b for a, b in got), 'by_class': {c: f'{sum(1 for a, b in got if a == c and b == c)}/{sum(1 for a, _ in got if a == c)}' for c in classes}}


def main():
    train = load_p02()
    lab16 = json.loads((V / 'p16_general/out/labels.json').read_text(encoding='utf-8'))
    p16 = load_other('p16_general', set(lab16['ng']) | set(lab16['part']))
    lab15 = json.loads((V / 'recipes' / 'labels.json').read_text(encoding='utf-8'))['p15']
    bad15 = {k for k, v in lab15.items() if v['v'] != 'ok'}
    p15 = load_other('p15_shots', bad15)
    res = {'train_n': len(train), 'p16_n': len(p16), 'p15_n': len(p15), 'keys': {}}
    for key in ('person_h', 'person_area', 'face_h'):
        ths = fit(train, key)
        res['keys'][key] = {'thresholds': [round(t, 3) for t in ths], 'train': score(train, key, ths, ORDER),
                            'p16': score(p16, key, ths, ['全身', '引き']), 'p15': score(p15, key, ths, ['全身', '引き'])}
    # 余白のある全身と引きを、P16 の中だけで最も良く分ける閾値（学習と試しが同じ絵なので上限の目安）
    res['p16_best_inside'] = {}
    for key in ('person_h', 'person_area', 'face_h'):
        xs = sorted({x[1][key] for x in p16})
        best = max(xs, key=lambda t: sum((x[1][key] >= t) == (x[0] == '全身') for x in p16))
        res['p16_best_inside'][key] = {'threshold': round(best, 3), 'correct': sum((x[1][key] >= best) == (x[0] == '全身') for x in p16), 'n': len(p16)}
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
