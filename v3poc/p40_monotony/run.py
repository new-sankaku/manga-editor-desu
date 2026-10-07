"""P40 単調さを数で見分けられるか（一覧 3-29、課題261）。
検査を通った LLM のコマ割り（P12 の48個）と、実際の漫画のページ（P06 で MagiV2 が見つけたコマの枠、10ページ）で、
単調さの目安を同じ式で数え、分かれるかを見る。目安：
  area_cv      コマの面積のばらつき（標準偏差÷平均）。小さいほど同じ大きさのコマが並ぶ
  max_min      いちばん大きいコマ÷いちばん小さいコマ
  shapes       縦横比を3つ（横長・ほぼ四角・縦長）に分けたときの種類の数
  full_width   ページの幅いっぱいのコマの割合
  aligned      コマの上端が、ほかのコマの上端とそろっている割合（段が揃う＝格子に近い）
実際のページの枠は検出器の出力で、斜めのコマは外接する四角になる。実際のページは他人の作品なので、数だけを残す。
使い方: python run.py"""
import json
import pathlib
import statistics as st

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
P12 = HERE.parent / 'p12_layout' / 'out' / 'result.json'
P06 = HERE.parent / 'p06_magi' / 'out' / 'magi.json'


def metrics(panels, W, H):
    """panels: [(x, y, w, h)]"""
    areas = [w * h for _, _, w, h in panels]
    shape = lambda w, h: 0 if w / h > 1.3 else (2 if w / h < 0.77 else 1)
    tol = 0.02 * H
    tops = [y for _, y, _, _ in panels]
    return {'n': len(panels), 'area_cv': round(st.pstdev(areas) / st.mean(areas), 3), 'max_min': round(max(areas) / max(min(areas), 1), 2),
            'shapes': len({shape(w, h) for _, _, w, h in panels}),
            'full_width': round(sum(1 for _, _, w, _ in panels if w >= 0.9 * W) / len(panels), 3),
            'aligned': round(sum(1 for i, t in enumerate(tops) if any(abs(t - u) <= tol for j, u in enumerate(tops) if j != i)) / len(panels), 3)}


def summ(rows):
    keys = ['n', 'area_cv', 'max_min', 'shapes', 'full_width', 'aligned']
    return {k: {'median': round(st.median(r[k] for r in rows), 3), 'min': min(r[k] for r in rows), 'max': max(r[k] for r in rows)} for k in keys}


def main():
    p12 = json.loads(P12.read_text(encoding='utf-8'))
    llm = []
    for r in p12['results']:
        if r.get('panels') and r.get('check', {}).get('ok'):
            ps = [(p['x'], p['y'], p['w'], p['h']) for p in r['panels']]
            llm.append({'id': r['id'], **metrics(ps, 150, 220)})
    real = []
    for r in json.loads(P06.read_text(encoding='utf-8')):
        if 'naname' in r['file'] or '視線誘導' in r['file']:
            ps = [(x0, y0, x1 - x0, y1 - y0) for x0, y0, x1, y1 in r['panels']]
            if len(ps) >= 2:
                real.append({'id': pathlib.Path(r['file']).parent.name[:2] + '_' + pathlib.Path(r['file']).stem, **metrics(ps, r['w'], r['h'])})
    # 実物のいちばん単調な値を下限にしたとき、LLM の割りの何個がそれより単調か
    lo_cv = min(r['area_cv'] for r in real)
    lo_shapes = min(r['shapes'] for r in real)
    res = {'llm_passed': len(llm), 'real_pages': len(real), 'llm': summ(llm), 'real': summ(real),
           'llm_below_real_min_area_cv': sum(1 for r in llm if r['area_cv'] < lo_cv),
           'llm_below_real_min_shapes': sum(1 for r in llm if r['shapes'] < lo_shapes),
           'real_min_area_cv': lo_cv, 'real_min_shapes': lo_shapes, 'rows_llm': llm, 'rows_real': real}
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in res.items() if not k.startswith('rows')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
