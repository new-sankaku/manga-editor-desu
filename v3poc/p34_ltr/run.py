"""P34 左から読む作品で、読む順とめくりの検査が向きに合わせて働くか（一覧 3-5、細部の読む向き）。
P12 の48個のコマ割り（右から読む）を左右反転して「左から読む割り」を作る。
読む順の検査は、向きが左からなら割りを左右反転してから、右から読む検査（P12 と同じ）にかける。
確かめること：①左から読む割りを「左から」で検査すると、元の割りを「右から」で検査した結果と同じになる
②左から読む割りを誤って「右から」で検査すると、読む順の崩れとして出る（向きの取り違えを検査が見逃さない）
③めくり：1ページ目の位置と、めくりの前のページが向きで入れ替わる。
使い方: python run.py"""
import importlib.util
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
_spec = importlib.util.spec_from_file_location('p12', HERE.parent / 'p12_layout' / 'run.py')
P12 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P12)


def mirror(panels):
    return [{**p, 'x': P12.W - p['x'] - p['w']} for p in panels]


def check(panels, script, direction):
    """direction: 'rtl'（右から）か 'ltr'（左から）。"""
    return P12.check(panels if direction == 'rtl' else mirror(panels), script)


def turn_pages(n_pages, direction):
    """めくりの前のページ（見開きの後ろ側）と、1ページ目の置き場。右から読む本は1ページ目が左、左から読む本は1ページ目が右。"""
    first = '左' if direction == 'rtl' else '右'
    side = {p: (first if p % 2 == 1 else ('右' if first == '左' else '左')) for p in range(1, n_pages + 1)}
    return {'first_page_side': first, 'before_turn': [p for p in side if side[p] == first]}


def main():
    res = json.loads((HERE.parent / 'p12_layout' / 'out' / 'result.json').read_text(encoding='utf-8'))
    rows = []
    for r in res['results']:
        if not r.get('panels'):
            continue
        script = P12.SCRIPTS[r['script']]
        orig = check(r['panels'], script, 'rtl')
        ltr = mirror(r['panels'])
        same = check(ltr, script, 'ltr')
        wrong = check(ltr, script, 'rtl')
        rows.append({'id': r['id'], 'rtl_breaks': orig['order_breaks'], 'ltr_as_ltr_breaks': same['order_breaks'], 'ltr_as_rtl_breaks': wrong['order_breaks'],
                     'same_result': {k: v for k, v in orig.items()} == {k: v for k, v in same.items()}, 'panels': len(r['panels'])})
    summ = {'layouts': len(rows), 'same_result': sum(r['same_result'] for r in rows),
            'wrong_direction_caught': sum(1 for r in rows if r['ltr_as_rtl_breaks'] > 0),
            'turn_rtl': turn_pages(8, 'rtl'), 'turn_ltr': turn_pages(8, 'ltr')}
    (OUT / 'result.json').write_text(json.dumps({'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
