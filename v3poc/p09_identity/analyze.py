"""P9の解析（検出器を入れたPythonで動かす）。参照画像との同一キャラ判定（CCIP）の差を、作り方ごとに比べる。
差が閾値より小さければ「同じキャラ」。別キャラ（other）が閾値より上に分かれるかも見る。"""
import json
import pathlib
import sys

from imgutils.metrics import ccip_default_threshold, ccip_difference, ccip_extract_feature

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
sys.path.insert(0, str(HERE.parent / 'common'))


def main():
    ref = ccip_extract_feature(str(OUT / 'ref.png'))
    th = ccip_default_threshold()
    rows = []
    for p in sorted(OUT.glob('*_*_*.png')):
        sc, mode, seed = p.stem.split('_')
        d = float(ccip_difference(ref, ccip_extract_feature(str(p))))
        rows.append({'file': p.name, 'scene': sc, 'mode': mode, 'seed': int(seed), 'diff': round(d, 3), 'same': d < th})
    summ = {}
    for m in ('text', 'ipa05', 'ipa08', 'other'):
        rs = [r for r in rows if r['mode'] == m]
        summ[m] = {'n': len(rs), 'judged_same': sum(r['same'] for r in rs), 'diff_mean': round(sum(r['diff'] for r in rs) / len(rs), 3),
                   'by_scene': {s: sum(r['same'] for r in rs if r['scene'] == s) for s in sorted({r['scene'] for r in rs})}}
    (OUT / 'result.json').write_text(json.dumps({'threshold': th, 'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('threshold', th)
    for k, v in summ.items():
        print(k, v)


if __name__ == '__main__':
    main()
