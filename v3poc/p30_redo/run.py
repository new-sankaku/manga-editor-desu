"""P30 理由を伝えずに作り直させると、同じ物が出やすいか（一覧 6-4、細部5.3）。
LLM にコマの中身から画像生成用の言葉を作らせ、その結果を見せて「作り直して」と頼む。
手：理由なし／理由あり（人物が小さく表情が見えない）。各5回。前の言葉と新しい言葉の重なり（Jaccard）を比べる。
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
PANEL = '放課後の教室。窓際の席で、転校生の少女が一人、夕日を見ながら泣くのをこらえている。白黒の漫画の1コマ。'
FIRST = """次の漫画の1コマを、画像生成AI（Danbooru のタグで学習した SDXL 系のモデル）に渡す英語のタグの列にしてください。

コマの中身：{panel}

出力はJSONだけにしてください。形式：{{"tags":"カンマ区切りのタグ"}}"""
REDO = """次の漫画の1コマを、画像生成AI（Danbooru のタグで学習した SDXL 系のモデル）に渡す英語のタグの列にしてください。

コマの中身：{panel}

前に作ったタグの列はこれです。
{prev}

{ask}

出力はJSONだけにしてください。形式：{{"tags":"カンマ区切りのタグ"}}"""
ASK = {
    'noreason': 'このタグの列で作った絵は採用されませんでした。作り直してください。',
    'reason': 'このタグの列で作った絵は、人物が小さく、表情が見えなかったので採用されませんでした。作り直してください。',
}
RUNS = 5


def ask(prompt):
    r = subprocess.run(['claude', '-p', '--model', 'sonnet', '--output-format', 'json', '--max-turns', '1'],
                       input=prompt, capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=600)
    j = json.loads(r.stdout)
    m = re.search(r'\{.*\}', j.get('result', ''), re.S)
    return json.loads(m.group(0)).get('tags', '') if m else ''


def tags(s):
    return {t.strip().lower() for t in s.split(',') if t.strip()}


def jac(a, b):
    return round(len(a & b) / len(a | b), 3) if a | b else 1.0


def main():
    first = ask(FIRST.format(panel=PANEL))
    tasks = [(k, i) for k in ASK for i in range(RUNS)]
    with cf.ThreadPoolExecutor(5) as ex:
        outs = list(ex.map(lambda t: ask(REDO.format(panel=PANEL, prev=first, ask=ASK[t[0]])), tasks))
    rows = [{'mode': k, 'run': i, 'tags': o, 'jaccard_to_first': jac(tags(first), tags(o)),
             'added': sorted(tags(o) - tags(first)), 'removed': sorted(tags(first) - tags(o))} for (k, i), o in zip(tasks, outs)]
    summ = {}
    for k in ASK:
        xs = [r for r in rows if r['mode'] == k]
        pair = [jac(tags(a['tags']), tags(b['tags'])) for n, a in enumerate(xs) for b in xs[n + 1:]]
        summ[k] = {'jaccard_to_first_mean': round(sum(r['jaccard_to_first'] for r in xs) / len(xs), 3),
                   'jaccard_between_redos_mean': round(sum(pair) / len(pair), 3),
                   'shot_changed': sum(1 for r in xs if any(w in r['added'] for w in ('close-up', 'portrait', 'upper body', 'face focus')))}
    (OUT / 'result.json').write_text(json.dumps({'panel': PANEL, 'first': first, 'ask': ASK, 'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1),
                                     encoding='utf-8')
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
