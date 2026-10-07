"""P33 候補を複数作って LLM に選ばせると、1枚だけ作るより狙いどおりの絵が増えるか（一覧 4-14、方針13・14）。
P16 の絵を使う。同じ狙い・人物・場所で seed 違いの3枚を1組にし、Sonnet に「狙いにいちばん合う1枚」を選ばせる（どれも合わなければ「なし」）。
正解は P16 の目の判定（out/labels.json）。選んだ絵が狙いどおりだった割合を、1枚だけ作ったときの割合（狙いどおりの枚数÷全枚数）と比べる。
画像は名前を伏せた写しで見せる。
使い方: python run.py <空フォルダ>"""
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
BLIND.mkdir(parents=True, exist_ok=True)
P16 = HERE.parent / 'p16_general' / 'out'
CWD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
TARGET = {'long_yoko': '横長のコマに入れる引きの絵（人物の周りに場所が広く見える）', 'long_tate': '縦長のコマに入れる引きの絵（人物の周りに場所が広く見える）',
          'full_std': '標準の形のコマに入れる全身の絵（周りに余白がある）', 'chara_only': '人物だけの絵（背景なし）',
          'bg_yoko': '人物のいない背景だけの絵（横長。人物を後から立たせる地面がある）', 'bg_tate': '人物のいない背景だけの絵（縦長。人物を後から立たせる地面がある）'}
CHARA = {'girl': '眼鏡の女子生徒', 'boy': 'パーカーの少年', 'old': '背広の老人', 'none': '人物なし'}
PLACE = {'street': '街', 'room': '教室', 'rural': '郊外（田んぼと山）', 'none': 'なし（背景なし）'}
PROMPT = """次の3枚は、どれも漫画の1コマ用に、同じ狙いで作った絵です。
狙い：{target}。人物：{chara}。場所：{place}。1枚の絵が1つのコマです（絵の中にさらにコマが並んでいるものは狙いに合いません）。

{files}

狙いにいちばん合う1枚を選んでください。どれも狙いに合わなければ「なし」と答えてください。
「なし」を選ぶと作り直しになり時間がかかります。合わない絵を選ぶと、そのまま次の工程に進みます。

出力はJSONだけにしてください。形式：{{"pick":"ファイル名 か なし","why":"理由"}}"""


def blind(f):
    name = 'img_' + hashlib.sha1(('p33-' + f).encode()).hexdigest()[:10] + '.png'
    if not (BLIND / name).exists():
        shutil.copyfile(P16 / f, BLIND / name)
    return BLIND / name


def ask(g, files):
    fs = sorted(files, key=lambda f: blind(f).name)
    prompt = PROMPT.format(target=TARGET[g[0]], chara=CHARA.get(g[1], '人物なし'), place=PLACE.get(g[2], 'なし（背景なし）'), files='\n'.join(str(blind(f)) for f in fs))
    r = subprocess.run(['claude', '-p', '--model', 'sonnet', '--output-format', 'json', '--allowedTools', 'Read', '--max-turns', '10'],
                       input=prompt, capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=900)
    j = json.loads(r.stdout)
    m = re.search(r'\{.*\}', j.get('result', ''), re.S)
    d = json.loads(m.group(0)) if m else {}
    pick = pathlib.Path(str(d.get('pick', ''))).name
    back = {blind(f).name: f for f in files}
    return back.get(pick, 'なし' if 'なし' in str(d.get('pick', '')) else None), d.get('why'), j.get('total_cost_usd')


def main():
    gen = json.loads((P16 / 'gen.json').read_text(encoding='utf-8'))
    lab = json.loads((P16 / 'labels.json').read_text(encoding='utf-8'))
    bad = set(lab['ng']) | set(lab['part'])
    groups = {}
    for r in gen['runs']:
        if r['target'] in TARGET:
            groups.setdefault((r['target'], r['chara'], r['place']), []).append(r['file'])
    groups = {k: v for k, v in groups.items() if len(v) == 3}
    with cf.ThreadPoolExecutor(4) as ex:
        res = dict(zip(groups, ex.map(lambda k: ask(k, groups[k]), groups)))
    rows = []
    for k, files in groups.items():
        pick, why, cost = res[k]
        okn = sum(f not in bad for f in files)
        rows.append({'target': k[0], 'chara': k[1], 'place': k[2], 'files': files, 'ok_count': okn, 'pick': pick, 'why': why, 'cost_usd': cost,
                     'pick_ok': (pick not in bad) if pick not in (None, 'なし') else None})
    n_img = sum(len(r['files']) for r in rows)
    summ = {'groups': len(rows), 'single_ok_rate': round(sum(r['ok_count'] for r in rows) / n_img, 3),
            'picked': sum(1 for r in rows if r['pick_ok'] is not None), 'picked_ok': sum(1 for r in rows if r['pick_ok']),
            'none': sum(1 for r in rows if r['pick'] == 'なし'), 'none_when_all_bad': sum(1 for r in rows if r['pick'] == 'なし' and r['ok_count'] == 0),
            'all_bad_groups': sum(1 for r in rows if r['ok_count'] == 0), 'none_when_some_ok': sum(1 for r in rows if r['pick'] == 'なし' and r['ok_count'] > 0),
            'best_possible': sum(1 for r in rows if r['ok_count'] > 0), 'cost_usd': round(sum(r['cost_usd'] or 0 for r in rows), 3)}
    (OUT / 'result.json').write_text(json.dumps({'prompt': PROMPT, 'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
