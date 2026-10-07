"""P45 斜めのコマを含む割りで、画像を見た LLM が読む順を当てられるか（一覧 3-17 の残り）。画像生成は使わない。
P11 は四角いコマだけだった。ここでは枠の辺が斜めのコマ（台形・三角）を8種描き、P11 と同じ聞き方で Sonnet と Opus に各2回聞く。
正解は、右から左・上から下の読み方で私が付けた順（コマの並びが正解の順）。台形どうしの段の区切りが斜めでも、段の順は変わらない割りにした。
コマは線で分けた多角形を、重心へ少し縮めて隙間を作る。
使い方: python run.py <空フォルダ>"""
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
S = 3
W, H = 150, 220
GAP = 2.5  # 隙間の半分（目盛り）
# 各コマは多角形の頂点。並びが正解の読む順
LAYOUTS = {
    'slant_rows': [[(75, 0), (150, 0), (150, 55), (75, 62.5)], [(0, 0), (75, 0), (75, 62.5), (0, 70)],
                   [(90, 61), (150, 55), (150, 135), (60, 144)], [(0, 70), (90, 61), (60, 144), (0, 150)],
                   [(75, 142.5), (150, 135), (150, 220), (75, 220)], [(0, 150), (75, 142.5), (75, 220), (0, 220)]],
    'diag_band': [[(0, 0), (150, 0), (150, 40), (0, 70)], [(110, 48), (150, 40), (150, 140), (40, 162)],
                  [(0, 70), (110, 48), (40, 162), (0, 170)], [(0, 170), (150, 140), (150, 220), (0, 220)]],
    'zigzag': [[(100, 0), (150, 0), (150, 90), (50, 90)], [(0, 0), (100, 0), (50, 90), (0, 90)],
               [(0, 90), (150, 90), (150, 140), (0, 140)],
               [(40, 140), (150, 140), (150, 220), (110, 220)], [(0, 140), (40, 140), (110, 220), (0, 220)]],
    'triangle_split': [[(76, 0), (150, 0), (150, 70), (76, 70)], [(0, 0), (74, 0), (74, 70), (0, 70)],
                       [(0, 75), (150, 75), (150, 165)], [(0, 75), (150, 165), (0, 165)],
                       [(0, 170), (150, 170), (150, 220), (0, 220)]],
    'slant_three': [[(105, 0), (150, 0), (150, 90), (95, 90)], [(55, 0), (105, 0), (95, 90), (45, 90)], [(0, 0), (55, 0), (45, 90), (0, 90)],
                    [(70, 90), (150, 90), (150, 220), (80, 220)], [(0, 90), (70, 90), (80, 220), (0, 220)]],
    'tall_slant_right': [[(95, 0), (150, 0), (150, 150), (80, 150)], [(0, 0), (95, 0), (88, 70), (0, 80)],
                         [(0, 80), (88, 70), (80, 150), (0, 150)], [(0, 150), (150, 150), (150, 220), (0, 220)]],
    'tall_slant_left': [[(55, 0), (150, 0), (150, 65), (62.5, 75)], [(62.5, 75), (150, 65), (150, 150), (70, 150)],
                        [(0, 0), (55, 0), (70, 150), (0, 150)], [(0, 150), (150, 150), (150, 220), (0, 220)]],
    'dynamic': [[(85, 0), (150, 0), (150, 50), (70, 60)], [(0, 0), (85, 0), (70, 60), (0, 70)],
                [(0, 70), (150, 50), (150, 140), (0, 160)],
                [(110, 147), (150, 140), (150, 220), (100, 220)], [(55, 153), (110, 147), (100, 220), (45, 220)], [(0, 160), (55, 153), (45, 220), (0, 220)]],
}
PROMPT = """画像ファイル {path} を読んでください。日本の漫画の1ページのコマ割りです。コマには番号が振られていません。枠の辺が斜めのコマもあります。
このページは右から左、上から下へ読みます。
各コマを、ページの中の位置で呼んでください。呼び方は、コマの中心の座標（左上を原点、右と下が増える向き、横150・縦220の目盛り）です。
読む順に、コマの中心の座標を並べてください。
出力はJSONだけにしてください。形式：{{"order":[[x,y],[x,y]]}}"""


def centroid(pts):
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def shrink(pts):
    cx, cy = centroid(pts)
    out = []
    for x, y in pts:
        dx, dy = x - cx, y - cy
        d = (dx * dx + dy * dy) ** 0.5 or 1
        out.append((x - dx / d * GAP * 1.4, y - dy / d * GAP * 1.4))
    return out


def draw(name, ps):
    im = Image.new('RGB', (W * S + 40, H * S + 40), 'white')
    d = ImageDraw.Draw(im)
    for pts in ps:
        q = [(20 + x * S, 20 + y * S) for x, y in shrink(pts)]
        d.line(q + [q[0]], fill='black', width=4)
    p = OUT / f'{name}.png'
    im.save(p)
    return p


def ask(model, path):
    r = subprocess.run(['claude', '-p', '--model', model, '--output-format', 'json', '--allowedTools', 'Read', '--max-turns', '3'],
                       input=PROMPT.format(path=str(path)), capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=600)
    j = json.loads(r.stdout)
    txt = j.get('result', '')
    m = re.search(r'\{.*\}', txt, re.S)
    return (json.loads(m.group(0))['order'] if m else None), txt, j.get('total_cost_usd')


def score(ps, order):
    """答えの座標を、中心がいちばん近いコマに割り当てて順番を出す。"""
    if not order:
        return None, False
    cs = [centroid(p) for p in ps]
    idx = [min(range(len(ps)), key=lambda i: (cs[i][0] - x) ** 2 + (cs[i][1] - y) ** 2) for x, y in order]
    return idx, idx == list(range(len(ps)))


def one(args):
    name, model, run = args
    try:
        order, raw, cost = ask(model, OUT / f'{name}.png')
        idx, ok = score(LAYOUTS[name], order)
    except Exception as e:
        idx, ok, raw, cost = None, False, repr(e), None
    return {'layout': name, 'model': model, 'run': run, 'answer_idx': idx, 'ok': ok, 'cost_usd': cost, 'raw': raw[-600:]}


def main():
    for n, ps in LAYOUTS.items():
        draw(n, ps)
    sh = Image.new('RGB', (4 * 250, 2 * 360), 'white')
    for i, n in enumerate(LAYOUTS):
        im = Image.open(OUT / f'{n}.png')
        im.thumbnail((240, 340))
        sh.paste(im, ((i % 4) * 250, (i // 4) * 360 + 16))
        ImageDraw.Draw(sh).text(((i % 4) * 250 + 4, (i // 4) * 360 + 2), n, fill='black')
    sh.save(OUT / 'sheet.png')
    jobs = [(n, m, r) for n in LAYOUTS for m in ('sonnet', 'opus') for r in range(2)]
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, jobs))
    summ = {m: {n: sum(1 for r in res if r['model'] == m and r['layout'] == n and r['ok']) for n in LAYOUTS} for m in ('sonnet', 'opus')}
    tot = {m: sum(v.values()) for m, v in summ.items()}
    cost = round(sum(r['cost_usd'] or 0 for r in res), 3)
    (OUT / 'result.json').write_text(json.dumps({'summary_ok_of_2': summ, 'total_ok_of_16': tot, 'cost_usd': cost, 'results': res, 'prompt': PROMPT},
                                                ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summ, ensure_ascii=False), tot, cost)


if __name__ == '__main__':
    main()
