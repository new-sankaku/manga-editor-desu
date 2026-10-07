"""P11 コマの読む順を、画像を見たLLMに判定させられるか（一覧 3-17）。
番号のないコマ割りの絵を見せ、右から読む前提で順番を答えさせ、正解と比べる。
割りは、段が揃った素直なもの3種と、段抜きなど迷いやすいもの5種。"""
import concurrent.futures as cf
import json
import pathlib
import re
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
CWD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
S = 3  # 1mm = 3px
W, H = 150, 220
# 各コマ (x, y, w, h)、並びが正解の読む順（右から左、上から下）
LAYOUTS = {
    'grid_2x3': [(76, 0, 74, 70), (0, 0, 74, 70), (76, 75, 74, 70), (0, 75, 74, 70), (76, 150, 74, 70), (0, 150, 74, 70)],
    'rows_1_2_1': [(0, 0, 150, 60), (76, 65, 74, 90), (0, 65, 74, 90), (0, 160, 150, 60)],
    'rows_3_2_2': [(101, 0, 49, 60), (50, 0, 49, 60), (0, 0, 48, 60), (61, 65, 89, 75), (0, 65, 59, 75), (86, 145, 64, 75), (0, 145, 84, 75)],
    'tall_right': [(91, 0, 59, 140), (0, 0, 89, 68), (0, 72, 89, 68), (0, 145, 150, 75)],
    'tall_left': [(61, 0, 89, 68), (61, 72, 89, 68), (0, 0, 59, 140), (0, 145, 150, 75)],
    'tall_mid_row': [(0, 0, 150, 50), (101, 55, 49, 110), (0, 55, 99, 53), (0, 112, 99, 53), (0, 170, 150, 50)],
    'offset_gutters': [(71, 0, 79, 80), (0, 0, 69, 100), (71, 85, 79, 60), (0, 105, 69, 40), (0, 150, 150, 70)],
    'tall_left_bottom': [(0, 0, 150, 70), (61, 75, 89, 70), (61, 150, 89, 70), (0, 75, 59, 145)],
}
PROMPT = """画像ファイル {path} を読んでください。日本の漫画の1ページのコマ割りです。コマには番号が振られていません。
このページは右から左、上から下へ読みます。
各コマを、ページの中の位置で呼んでください。呼び方は、コマの中心の座標（左上を原点、右と下が増える向き、横150・縦220の目盛り）です。
読む順に、コマの中心の座標を並べてください。
出力はJSONだけにしてください。形式：{{"order":[[x,y],[x,y]]}}"""


def draw(name, ps):
    im = Image.new('RGB', (W * S + 40, H * S + 40), 'white')
    d = ImageDraw.Draw(im)
    for x, y, w, h in ps:
        d.rectangle((20 + x * S, 20 + y * S, 20 + (x + w) * S, 20 + (y + h) * S), outline='black', width=4)
    p = OUT / f'{name}.png'
    im.save(p)
    return p


def ask(model, path):
    r = subprocess.run(['claude', '-p', '--model', model, '--output-format', 'json', '--allowedTools', 'Read', '--max-turns', '3'],
                       input=PROMPT.format(path=str(path)), capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=600)
    txt = json.loads(r.stdout).get('result', '')
    m = re.search(r'\{.*\}', txt, re.S)
    return (json.loads(m.group(0))['order'] if m else None), txt


def score(ps, order):
    """答えの座標を、いちばん近いコマに割り当てて順番を出す。"""
    if not order:
        return None, False
    idx = []
    for x, y in order:
        best = min(range(len(ps)), key=lambda i: ((ps[i][0] + ps[i][2] / 2 - x) ** 2 + (ps[i][1] + ps[i][3] / 2 - y) ** 2))
        idx.append(best)
    return idx, idx == list(range(len(ps)))


def one(args):
    name, model, run = args
    ps = LAYOUTS[name]
    try:
        order, raw = ask(model, OUT / f'{name}.png')
        idx, ok = score(ps, order)
    except Exception as e:
        idx, ok, raw = None, False, repr(e)
    return {'layout': name, 'model': model, 'run': run, 'answer_idx': idx, 'ok': ok, 'raw': raw[-600:]}


def main():
    for n, ps in LAYOUTS.items():
        draw(n, ps)
    jobs = [(n, m, r) for n in LAYOUTS for m in ('sonnet', 'opus') for r in range(2)]
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, jobs))
    summ = {m: {n: sum(1 for r in res if r['model'] == m and r['layout'] == n and r['ok']) for n in LAYOUTS} for m in ('sonnet', 'opus')}
    (OUT / 'result.json').write_text(json.dumps({'summary_ok_of_2': summ, 'results': res, 'prompt': PROMPT}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
