"""P12 の保存済みの結果に、機械の検査を2つ足して数え直す（LLMは呼ばない）。
 tiny_panel  : 短い辺が15mm未満のコマがある
 empty_space : どのコマにも隙間にも入らない場所が100mm²以上ある（1mmの升目で数える）"""
import json
import pathlib

import numpy as np

OUT = pathlib.Path(__file__).with_name('out')
d = json.loads((OUT / 'result.json').read_text(encoding='utf-8'))
for r in d['results']:
    ps, c = r['panels'], r['check']
    if not ps:
        continue
    c['tiny_panel'] = sum(1 for p in ps if min(p['w'], p['h']) < 15)
    g = np.zeros((220, 150), bool)
    for p in ps:
        x0, y0 = max(0, int(p['x'] - 3)), max(0, int(p['y'] - 6))
        g[y0:int(p['y'] + p['h'] + 6), x0:int(p['x'] + p['w'] + 3)] = True
    c['empty_mm2'] = int((~g).sum())
    c['empty_space'] = c['empty_mm2'] >= 100
    c['ok2'] = c['ok'] and not c['tiny_panel'] and not c['empty_space']
summ = {}
for m in 'AB':
    rs = [r['check'] for r in d['results'] if r['method'] == m]
    summ[m] = {'n': len(rs), 'ok_before': sum(1 for c in rs if c.get('ok')), 'ok_after': sum(1 for c in rs if c.get('ok2')),
               'tiny_panel': sum(1 for c in rs if c.get('tiny_panel')), 'empty_space': sum(1 for c in rs if c.get('empty_space'))}
d['summary_recheck'] = summ
(OUT / 'result.json').write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(summ, ensure_ascii=False))
