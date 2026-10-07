"""P46 話をまたいだ伏線の回収漏れと、回収が前の描写と食い違うことを、LLM が見つけられるか（一覧 5-22 の残り）。
4話分の台本（script.json）に、回収されない伏線2つ・回収が前の描写と食い違うもの2つ・きちんと回収されるもの3つと、
伏線ではない日常の行を入れた。答えは script.json の answers（LLM には見せない）。L4 は回収済みと見なす判断もあり得る境目として別に数える。
手：A 問題のある行だけを挙げさせる／B 伏線に見える行を全部並べ、それぞれ回収済み・未回収・食い違いのどれかを付けさせる。
Sonnet と Opus で各2回。
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
# 正解の行。食い違いは、前振りの行と回収の行のどちらを挙げても当たりにする
TRUTH = {'dropped_L9': {'L9'}, 'dropped_L10': {'L10'}, 'contradict_lighthouse': {'L8', 'L19'}, 'contradict_map': {'L2', 'L20'}}
BORDER = {'L4'}
RESOLVED = {'L1', 'L6', 'L16', 'L13', 'L17', 'L18', 'L21'}
HEAD = """次は連載漫画の4話分の台本と、その設定です。

設定：
{settings}

台本（行の番号・話数・中身）：
{lines}

"""
PROMPT_A = HEAD + """この台本で、前の話で置いた伏線や手がかりが後の話で回収されていない所と、回収のしかたが前の描写と食い違っている所を探してください。
伏線か日常の描写か迷う行は、挙げても挙げなくても構いません。挙げすぎると作者が直す手間が増え、挙げないと読者が引っかかる所が残ります。

出力はJSONだけにしてください。形式：{{"issues":[{{"line":"行の番号","kind":"未回収 か 食い違い","why":"理由"}}]}}"""
PROMPT_B = HEAD + """この台本で、後の話で回収されることを読者が期待しそうな行（伏線や手がかり）を並べ、それぞれがどうなったかを付けてください。
状態は「回収済み」「未回収」「食い違い」（回収はされたが前の描写と合わない）のどれかです。
伏線か日常の描写か迷う行は、並べても並べなくても構いません。並べすぎると作者が読む手間が増え、並べないと見落としが残ります。

出力はJSONだけにしてください。形式：{{"setups":[{{"line":"伏線の行の番号","payoff":"回収の行の番号（無ければ空）","state":"回収済み か 未回収 か 食い違い","why":"理由"}}]}}"""


def ask(model, mode):
    lines = '\n'.join(f'{x["id"]}（第{x["ep"]}話）{x["text"]}' for x in S['lines'])
    prompt = (PROMPT_A if mode == 'A' else PROMPT_B).format(settings=S['settings'], lines=lines)
    r = subprocess.run(['claude', '-p', '--model', model, '--output-format', 'json', '--max-turns', '1'],
                       input=prompt, capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=900)
    j = json.loads(r.stdout)
    m = re.search(r'\{.*\}', j.get('result', ''), re.S)
    d = json.loads(m.group(0)) if m else {}
    if mode == 'A':
        flagged = [(x['line'], x.get('payoff', ''), x.get('kind', '')) for x in d.get('issues', [])]
    else:
        flagged = [(x['line'], x.get('payoff', ''), x.get('state', '')) for x in d.get('setups', []) if x.get('state') in ('未回収', '食い違い')]
    return d, flagged, j.get('total_cost_usd')


def score(flagged):
    lines = set()
    for line, payoff, _ in flagged:
        lines.add(line)
        lines |= set(re.findall(r'L\d+', str(payoff)))
    found = [k for k, v in TRUTH.items() if v & lines]
    truth_lines = set().union(*TRUTH.values()) | BORDER
    false = sorted(l for l, _, _ in flagged if l not in truth_lines)
    return {'found': found, 'missed': [k for k in TRUTH if k not in found], 'border_L4': bool(BORDER & lines),
            'false': false, 'false_on_resolved': sorted(l for l in false if l in RESOLVED)}


def main():
    jobs = [(m, mode, r) for m in ('sonnet', 'opus') for mode in ('A', 'B') for r in (1, 2)]
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda a: ask(a[0], a[1]), jobs))
    rows = []
    for (m, mode, r), (d, flagged, cost) in zip(jobs, res):
        rows.append({'model': m, 'mode': mode, 'run': r, **score(flagged), 'cost_usd': cost, 'answer': d})
    summ = [{k: r[k] for k in ('model', 'mode', 'run')} | {'found': len(r['found']), 'of': len(TRUTH), 'border_L4': r['border_L4'],
                                                          'false': len(r['false']), 'false_lines': r['false']} for r in rows]
    (OUT / 'result.json').write_text(json.dumps({'summary': summ, 'rows': rows, 'prompt_A': PROMPT_A, 'prompt_B': PROMPT_B,
                                                 'cost_usd': round(sum(r['cost_usd'] or 0 for r in rows), 3)}, ensure_ascii=False, indent=1), encoding='utf-8')
    for s in summ:
        print(s)


if __name__ == '__main__':
    main()
