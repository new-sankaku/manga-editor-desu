"""P11b 画像を見たLLMが、向き・角度と距離を当てられるか（一覧 3-19）。
P2の96枚を、指示ごとに8枚ずつ見せて判定させる。正解は「指示」と、目の判定で指示どおりだった画像だけ。"""
import concurrent.futures as cf
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
P2 = HERE.parent / 'p02_instruction' / 'out'
OUT = HERE / 'out'
CWD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
MODEL = sys.argv[2] if len(sys.argv) > 2 else 'sonnet'
MIXED = len(sys.argv) > 3 and sys.argv[3] == 'mixed'  # 指示を混ぜて8枚ずつ見せる
ANGLE = {'from_behind': '後ろ', 'from_above': '見下ろし', 'from_below': '見上げ', 'from_side': '横'}
DIST = {'close_up': '顔', 'upper_body': '上半身', 'full_body': '全身', 'very_wide': '引き'}
PROMPT = """次の画像ファイルを順に読んでください。どれも漫画の1コマ用の絵です。
{files}

各画像について、2つを判定してください。
・向きと角度：「正面」「横」「後ろ」「見下ろし」「見上げ」から1つ。人物の向きと、カメラの高さのうち、絵の印象を強く決めている方を選んでください
・距離：「顔」「胸から上」「上半身」「全身」「引き」から1つ。「引き」は人物が画面の中で小さく、場所が主になっているもの

出力はJSONだけにしてください。形式：{{"items":[{{"file":"ファイル名","angle":"...","distance":"..."}}]}}"""


def ask(files):
    r = subprocess.run(['claude', '-p', '--model', MODEL, '--output-format', 'json', '--allowedTools', 'Read', '--max-turns', '12'],
                       input=PROMPT.format(files='\n'.join(str(f) for f in files)), capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=900)
    j = json.loads(r.stdout)
    m = re.search(r'\{.*\}', j.get('result', ''), re.S)
    return (json.loads(m.group(0))['items'] if m else []), j.get('total_cost_usd')


def main():
    lab = json.loads((P2 / 'labels.json').read_text(encoding='utf-8'))
    groups = {iid: sorted(P2.glob(f'{iid}_10*.png')) for iid in list(ANGLE) + list(DIST)}
    batches = list(groups.values())
    if MIXED:
        import random
        allf = [f for fs in groups.values() for f in fs]
        random.Random(3).shuffle(allf)
        batches = [allf[i:i + 8] for i in range(0, len(allf), 8)]
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(ask, batches))
    by, cost = {}, 0
    for items, c in res:
        cost += c or 0
        by.update({pathlib.Path(it['file']).name: it for it in items})
    rows = []
    for iid in groups:
        for f in groups[iid]:
            it = by.get(f.name, {})
            want = ANGLE.get(iid) or DIST.get(iid)
            got = it.get('angle') if iid in ANGLE else it.get('distance')
            rows.append({'file': f.name, 'instr': iid, 'eye_ok': lab[f.stem]['ok'], 'want': want, 'got': got, 'hit': got == want})
    use = [r for r in rows if r['eye_ok']]
    summ = {iid: f"{sum(r['hit'] for r in use if r['instr'] == iid)}/{sum(1 for r in use if r['instr'] == iid)}" for iid in groups}
    out = {'model': MODEL, 'mixed': MIXED, 'cost_usd': round(cost, 3), 'summary_hit_of_eye_ok': summ,
           'total': f"{sum(r['hit'] for r in use)}/{len(use)}", 'rows': rows, 'prompt': PROMPT}
    (OUT / f'angle_{MODEL}{"_mixed" if MIXED else ""}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: out[k] for k in ('model', 'cost_usd', 'total', 'summary_hit_of_eye_ok')}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
