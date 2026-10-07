"""P32 評価役の答えが、聞き方でぶれないか（一覧 3-24・3-25・3-27）。
P19 の表情の絵（名前を伏せた写し）で「どちらの感情が強いか」を聞く。キャラ a・参照なし・4感情・seed 3・組（弱と中・中と強・弱と強）の36組。
聞き方5種：
  base    P19 と同じ文。1回に1感情の9組
  word    問いの言い回しを変える（「どちらの人物の気持ちがより激しく表に出ているか」）
  forced  「同じ」を選べなくする
  long    判定の手引きを長く付ける（目・口・眉・涙のそれぞれの見方）
  many    1回に4感情の36組を全部並べる
左右を入れ替えて2回聞き、食い違ったら引き分け。狙いの順との一致、base との答えの違いを数える。
使い方: python run.py <空フォルダ>"""
import concurrent.futures as cf
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
P19 = HERE.parent / 'p19_expression' / 'out'
CWD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
BACK = json.loads((P19 / 'blind' / 'map.json').read_text(encoding='utf-8'))
FWD = {v: k for k, v in BACK.items()}
EMOS = ['joy', 'anger', 'sad', 'surprise']
SEEDS = [31, 32, 33]
Q = {
    'base': 'AとBのどちらの表情に感情が強く表れているかを答えてください。感情の種類が違っても、強さだけで比べてください。',
    'word': 'AとBのどちらの人物の気持ちが、より激しく表に出ているかを答えてください。気持ちの種類が違っても、激しさだけで比べてください。',
}
TIE = '差が見分けられないときは「同じ」を選べます。「同じ」を選びすぎると強さの順が分からなくなり、無理に選ぶと見分けられない差を作ってしまいます。'
FORCED = '必ずAかBのどちらかを選んでください。'
GUIDE = """判定の手引き：
・目：見開き・細め・涙・視線の強さ
・口：開き方・歯が見えるか・口角の上がり下がり
・眉：寄り方・上がり方
・顔全体：赤み・汗・影の付け方などの描き足し
これらが大きく動いているほど、感情が強く表れていると見ます。どれか1つだけが大きい場合も、ほかと合わせて総合で比べてください。"""
PROMPT = """次の画像ファイルを順に読んでください。どれも漫画の1コマ用の、同じ人物の絵です。
{files}

下の各組について、{q}{tie}
{guide}
{pairs}

出力はJSONだけにしてください。形式：{{"pairs":[{{"id":組の番号,"stronger":"{opts}"}}]}}"""


def blind(f):
    return str(P19 / 'blind' / FWD[f])


def pairs(emos):
    out = []
    for e in emos:
        for s in SEEDS:
            for a, b in ((1, 2), (2, 3), (1, 3)):
                out.append((len(out) + 1, f'a_{e}_{a}_{s}.png', f'a_{e}_{b}_{s}.png', e))
    return out


def ask(variant, ps, swap):
    q = Q['word' if variant == 'word' else 'base']
    tie = FORCED if variant == 'forced' else TIE
    opts = 'A か B' if variant == 'forced' else 'A か B か 同じ'
    guide = GUIDE if variant == 'long' else ''
    files = sorted({f for _, a, b, _ in ps for f in (a, b)}, key=blind)
    order = sorted(ps, key=lambda x: FWD[x[1]] + FWD[x[2]])
    lines = [f'組{i}：A＝{blind(b if swap else a)}　B＝{blind(a if swap else b)}' for i, a, b, _ in order]
    prompt = PROMPT.format(files='\n'.join(blind(f) for f in files), q=q, tie=tie, guide=guide, pairs='\n'.join(lines), opts=opts)
    r = subprocess.run(['claude', '-p', '--model', 'sonnet', '--output-format', 'json', '--allowedTools', 'Read', '--max-turns', '40'],
                       input=prompt, capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=1800)
    j = json.loads(r.stdout)
    m = re.search(r'\{.*\}', j.get('result', ''), re.S)
    got = {int(x['id']): x['stronger'] for x in (json.loads(m.group(0)).get('pairs', []) if m else [])}
    conv = {'A': 'R', 'B': 'L'} if swap else {'A': 'L', 'B': 'R'}
    return {i: conv.get(got.get(i), '=') for i, *_ in ps}, j.get('total_cost_usd')


def main():
    tasks = []
    for v in ('base', 'word', 'forced', 'long'):
        for e in EMOS:
            for sw in (False, True):
                tasks.append((v, (e,), sw))
    for sw in (False, True):
        tasks.append(('many', tuple(EMOS), sw))
    res = {}
    with cf.ThreadPoolExecutor(4) as ex:
        fut = {ex.submit(ask, v, pairs(list(es)), sw): (v, es, sw) for v, es, sw in tasks}
        for f in cf.as_completed(fut):
            res[fut[f]] = f.result()
            print(fut[f][0], fut[f][1][0], fut[f][2], flush=True)
    final = {}
    cost = {}
    for v in ('base', 'word', 'forced', 'long', 'many'):
        groups = [(e,) for e in EMOS] if v != 'many' else [tuple(EMOS)]
        cost[v] = 0
        for es in groups:
            ps = pairs(list(es))
            x, c1 = res[(v, es, False)]
            y, c2 = res[(v, es, True)]
            cost[v] += (c1 or 0) + (c2 or 0)
            for i, a, b, e in ps:
                final[(v, a, b)] = {'first': x[i], 'second': y[i], 'final': x[i] if x[i] == y[i] else '='}
    keys = [(a, b) for _, a, b, _ in pairs(EMOS)]
    summ = {}
    for v in ('base', 'word', 'forced', 'long', 'many'):
        fs = [final[(v, a, b)] for a, b in keys]
        summ[v] = {'pairs': len(fs), 'correct': sum(f['final'] == 'R' for f in fs), 'tie': sum(f['final'] == '=' for f in fs),
                   'wrong': sum(f['final'] == 'L' for f in fs), 'consistent': sum(f['first'] == f['second'] for f in fs),
                   'differs_from_base': sum(final[(v, a, b)]['final'] != final[('base', a, b)]['final'] for a, b in keys),
                   'cost_usd': round(cost[v], 3)}
    rows = [{'variant': v, 'left': a, 'right': b, **final[(v, a, b)]} for v in summ for a, b in keys]
    (OUT / 'result.json').write_text(json.dumps({'questions': Q, 'tie': TIE, 'forced': FORCED, 'guide': GUIDE, 'prompt': PROMPT,
                                                'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
