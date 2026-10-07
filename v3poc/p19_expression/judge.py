"""P19b 画像を見たLLMが、表情の強さを「どちらが強いか」で判定できるか（一覧 3-20、候補35・36）。
キャラ×感情ごとに、seed ごとの組（無表情と弱・弱と中・中と強・弱と強・強と強＋参照）を見せ、どちらが強いかを答えさせる。
左右を入れ替えてもう1回聞き、2回が食い違ったら引き分けとする。各画像の感情の種類も答えさせる。
ファイル名に感情と段が入っているので、名前を伏せた写し（out/blind/）を見せる。名前と元の対応は out/blind/map.json。
使い方: python judge.py <空フォルダ> [モデル]"""
import concurrent.futures as cf
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
BLIND = OUT / 'blind'
CWD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
MODEL = sys.argv[2] if len(sys.argv) > 2 else 'sonnet'
PROMPT = """次の画像ファイルを順に読んでください。どれも漫画の1コマ用の、同じ人物の絵です。
{files}

1. 各画像について、表情に表れている感情を「喜」「怒」「哀」「驚」「無表情」「その他」から1つ選んでください。
2. 下の各組について、AとBのどちらの表情に感情が強く表れているかを答えてください。感情の種類が違っても、強さだけで比べてください。差が見分けられないときは「同じ」を選べます。「同じ」を選びすぎると強さの順が分からなくなり、無理に選ぶと見分けられない差を作ってしまいます。
{pairs}

出力はJSONだけにしてください。形式：{{"images":[{{"file":"ファイル名","emotion":"..."}}],"pairs":[{{"id":組の番号,"stronger":"A か B か 同じ"}}]}}"""


def pairs_for(runs, c, e):
    """(組の番号, 左, 右, 狙いの強い方)。狙いの強い方は 'L'（左）・'R'（右）・'?'（参照の組。狙いは無い）。"""
    by = {(r['level'], r['ref'], r['seed']): r['file'] for r in runs if r['chara'] == c and r['emotion'] in (e, 'neutral')
          and (r['emotion'] == e or not r['ref'])}
    out = []
    for s in sorted({r['seed'] for r in runs}):
        for a, b in ((0, 1), (1, 2), (2, 3), (1, 3)):
            out.append((len(out) + 1, by[(a, False, s)], by[(b, False, s)], 'R'))
        out.append((len(out) + 1, by[(3, False, s)], by[(3, True, s)], '?'))
    return out


def blind(f):
    """中身の分からない名前の写しを作り、その場所を返す。"""
    BLIND.mkdir(exist_ok=True)
    name = 'img_' + hashlib.sha1(('p19-' + f).encode()).hexdigest()[:10] + '.png'
    if not (BLIND / name).exists():
        shutil.copyfile(OUT / f, BLIND / name)
    return BLIND / name


def ask(pairs, swap):
    files = sorted({f for _, a, b, _ in pairs for f in (a, b)}, key=lambda f: blind(f).name)
    order = sorted(pairs, key=lambda x: blind(x[1]).name + blind(x[2]).name)  # 並びから強さの順が読めないよう、伏せた名前の順に並べる
    lines = [f'組{i}：A＝{blind(b if swap else a)}　B＝{blind(a if swap else b)}' for i, a, b, _ in order]
    r = subprocess.run(['claude', '-p', '--model', MODEL, '--output-format', 'json', '--allowedTools', 'Read', '--max-turns', '30'],
                       input=PROMPT.format(files='\n'.join(str(blind(f)) for f in files), pairs='\n'.join(lines)),
                       capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=1500)
    j = json.loads(r.stdout)
    m = re.search(r'\{.*\}', j.get('result', ''), re.S)
    return (json.loads(m.group(0)) if m else {'images': [], 'pairs': []}), j.get('total_cost_usd')


def main():
    gen = json.loads((OUT / 'gen.json').read_text(encoding='utf-8'))
    runs = gen['runs']
    tasks = [(c, e, swap) for c in gen['charas'] for e in gen['emotions'] for swap in (False, True)]
    res = {}
    with cf.ThreadPoolExecutor(4) as ex:
        futs = {ex.submit(ask, pairs_for(runs, c, e), swap): (c, e, swap) for c, e, swap in tasks}
        for f in cf.as_completed(futs):
            res[futs[f]] = f.result()
            print(futs[f], 'cost', res[futs[f]][1], flush=True)
    back = {blind(r['file']).name: r['file'] for r in runs}
    (BLIND / 'map.json').write_text(json.dumps(back, ensure_ascii=False, indent=1), encoding='utf-8')
    rows, emo = [], []
    for c in gen['charas']:
        for e in gen['emotions']:
            ps = pairs_for(runs, c, e)
            ans = {}
            for swap in (False, True):
                got = {int(x['id']): x['stronger'] for x in res[(c, e, swap)][0].get('pairs', [])}
                ans[swap] = {i: ({'A': 'R', 'B': 'L'}.get(got.get(i), '=') if swap else {'A': 'L', 'B': 'R'}.get(got.get(i), '='))
                             for i, *_ in ps}
                for x in res[(c, e, swap)][0].get('images', []):
                    emo.append({'file': back.get(pathlib.Path(x['file']).name, x['file']), 'emotion': x['emotion'], 'swap': swap})
            for i, a, b, want in ps:
                x, y = ans[False][i], ans[True][i]
                rows.append({'chara': c, 'emotion': e, 'left': a, 'right': b, 'want': want, 'first': x, 'second': y,
                             'final': x if x == y else '=', 'consistent': x == y})
    cost = sum(v[1] or 0 for v in res.values())
    ordered = [r for r in rows if r['want'] != '?']
    summ = {
        'pairs': len(ordered),
        'consistent': sum(r['consistent'] for r in ordered),
        'correct_final': sum(r['final'] == r['want'] for r in ordered),
        'tie_final': sum(r['final'] == '=' for r in ordered),
        'wrong_final': sum(r['final'] not in ('=', r['want']) for r in ordered),
        'ref_pairs': {k: sum(r['final'] == k for r in rows if r['want'] == '?') for k in ('L', 'R', '=')},
        'cost_usd': round(cost, 3), 'model': MODEL,
    }
    (OUT / f'judge_{MODEL}_blind.json').write_text(json.dumps({'summary': summ, 'pairs': rows, 'emotions': emo}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
