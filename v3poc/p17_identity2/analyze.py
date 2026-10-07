"""P17 の測定（検出器を入れたPythonで動かす）。
各絵を、そのキャラの参照画像と同一キャラ判定（CCIP）で比べる。差が閾値より小さければ「同じキャラ」。
もう1人のキャラの参照画像とも比べ、別人を「同じ」と言わないかも見る。キャラごとに一覧画像（行＝書き方×参照、列＝場面×seed）を作る。
使い方: <venv_detのpython> analyze.py"""
import json
import pathlib
import sys

from imgutils.metrics import ccip_default_threshold, ccip_difference, ccip_extract_feature

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402


def main():
    gen = json.loads((OUT / 'gen.json').read_text(encoding='utf-8'))
    th = ccip_default_threshold()
    refs = {c: ccip_extract_feature(str(OUT / r['file'])) for c, r in gen['refs'].items()}
    rows = []
    for r in gen['runs']:
        f = ccip_extract_feature(str(OUT / r['file']))
        d = float(ccip_difference(refs[r['chara']], f))
        other = [c for c in refs if c != r['chara']][0]
        do = float(ccip_difference(refs[other], f))
        rows.append({**{k: r[k] for k in ('file', 'chara', 'level', 'ref', 'scene', 'seed')}, 'diff': round(d, 3), 'same': d < th,
                     'diff_other': round(do, 3), 'same_other': do < th})
    summ = {}
    for c in gen['charas']:
        for lv in gen['levels']:
            for rk in gen['refs_modes']:
                g = [x for x in rows if x['chara'] == c and x['level'] == lv and x['ref'] == rk]
                summ[f'{c}/{lv}/{rk}'] = {'n': len(g), 'same': sum(x['same'] for x in g), 'diff_mean': round(sum(x['diff'] for x in g) / len(g), 3),
                                          'same_as_other': sum(x['same_other'] for x in g)}
    (OUT / 'result.json').write_text(json.dumps({'threshold': th, 'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('threshold', round(th, 3))
    for k, v in summ.items():
        print(k, v)
    scenes, seeds = list(gen['scenes']), sorted({r['seed'] for r in gen['runs']})
    for c, cv in gen['charas'].items():
        rs = [('参照画像', [(OUT / gen['refs'][c]['file'], '')])]
        for lv, lname in gen['levels'].items():
            for rk, rname in gen['refs_modes'].items():
                rs.append((f'{lname}／{rname}', [(OUT / f'{c}_{lv}_{rk}_{sc}_{s}.png', f'{sc} {s}') for sc in scenes for s in seeds]))
        sheet(rs, OUT / f'sheet_{c}.png', tw=110, label_w=230)


if __name__ == '__main__':
    main()
