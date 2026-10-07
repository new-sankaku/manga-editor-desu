"""P28 話の矛盾（口調・設定・物の状態・時間の前後）を LLM が見つけられるか。観点ごとに分けると良くなるか（一覧 3-22・5-22、候補31）。
3話分の台本（script.json）に、わざと矛盾を12か所入れた。答えは script.json の answers（LLM には見せない）。
手：全部の観点を1回で聞く／観点ごとに4回に分けて聞く。Sonnet と Opus で各2回。
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
CWD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
S = json.loads((HERE / 'script.json').read_text(encoding='utf-8'))
VIEWS = {
    '口調': '登場人物の話し方が、設定の話し方と合っているか',
    '設定': '人物の年齢・家族・利き手・持ち物・通学の仕方などが、設定と合っているか',
    '物の状態': '壊れた物・預けた物・けがなど、物や体の状態が前の行と合っているか',
    '時間': '時間の流れと、前の話で起きたこと・話したことが、後の行と合っているか',
}
PROMPT = """次は漫画の台本と、その設定です。台本の中で、設定や前の行と食い違っている行を探してください。

見る観点：
{views}

食い違いかどうか迷う行は、挙げても挙げなくても構いません。挙げすぎると直す人の手間が増え、挙げないと矛盾が残ります。

設定：
{settings}

台本（行の番号・話数・中身）：
{lines}

出力はJSONだけにしてください。形式：{{"issues":[{{"line":"行の番号","why":"何と食い違っているか"}}]}}"""


def ask(model, views):
    vs = '\n'.join(f'・{k}：{VIEWS[k]}' for k in views)
    lines = '\n'.join(f'{x["id"]}（第{x["ep"]}話）{x["text"]}' for x in S['lines'])
    r = subprocess.run(['claude', '-p', '--model', model, '--output-format', 'json', '--max-turns', '1'],
                       input=PROMPT.format(views=vs, settings=S['settings'], lines=lines), capture_output=True, text=True, encoding='utf-8',
                       cwd=str(CWD), timeout=900)
    j = json.loads(r.stdout)
    m = re.search(r'\{.*\}', j.get('result', ''), re.S)
    return (json.loads(m.group(0)).get('issues', []) if m else None), j.get('total_cost_usd')


def score(found):
    truth = {a['line'] for a in S['answers']}
    got = {x['line'] for x in found}
    return {'found': sorted(got & truth), 'missed': sorted(truth - got), 'false': sorted(got - truth)}


def main():
    tasks = []
    for model in ('sonnet', 'opus'):
        for run in (1, 2):
            tasks.append((model, 'all', run, list(VIEWS)))
            for v in VIEWS:
                tasks.append((model, 'per_' + v, run, [v]))
    res = {}
    with cf.ThreadPoolExecutor(4) as ex:
        fut = {ex.submit(ask, m, vs): (m, mode, run) for m, mode, run, vs in tasks}
        for f in cf.as_completed(fut):
            res[fut[f]] = f.result()
            print(fut[f], flush=True)
    rows = []
    for model in ('sonnet', 'opus'):
        for run in (1, 2):
            allf, c1 = res[(model, 'all', run)]
            per = []
            cost = c1 or 0
            for v in VIEWS:
                x, c = res[(model, 'per_' + v, run)]
                per += x or []
                cost += c or 0
            rows.append({'model': model, 'run': run, 'all': {'issues': allf, **score(allf or [])},
                         'per': {'issues': per, **score(per)}, 'cost_usd': round(cost, 3)})
    summ = [{'model': r['model'], 'run': r['run'], 'all_found': len(r['all']['found']), 'all_false': len(r['all']['false']),
             'per_found': len(r['per']['found']), 'per_false': len(r['per']['false'])} for r in rows]
    (OUT / 'result.json').write_text(json.dumps({'truth': len(S['answers']), 'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
