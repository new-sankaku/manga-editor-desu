"""P31 枠だけでは読む順が決まらない割りで、吹き出しの位置によって LLM の答える読む順が変わるか（一覧 2-4、課題3）。
割り2種（2列2段の格子／2列3段の格子。縦横の隙間がどちらも通っている）× 吹き出しの置き方3種
（つながりなし／右の列の上下のコマをまたぐ吹き出し／上の段の左右のコマをまたぐ吹き出し）。右から読む前提。
番号は描かない。Sonnet に各2回。
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
W, H, M, G = 600, 880, 30, 16
LAYOUTS = {'g2x2': (2, 2), 'g2x3': (2, 3)}
BRIDGE = {'none': 'つながりなし', 'col': '右の列の上下をまたぐ', 'row': '上の段の左右をまたぐ'}
PROMPT = """次の画像は、日本の漫画の1ページのコマ割りです。右から左へ読む本です。コマには番号がありません。
コマの位置を、右上を「右1段目」のように「右か左」と「上から何段目か」で呼ぶことにします。
このページを読む人が、コマをどの順に読むかを答えてください。吹き出しの位置も手がかりにして構いません。

画像：{path}

出力はJSONだけにしてください。形式：{{"order":["右1段目",...],"why":"理由"}}"""


def cells(cols, rows):
    cw = (W - 2 * M - G * (cols - 1)) / cols
    rh = (H - 2 * M - G * (rows - 1)) / rows
    out = {}
    for r in range(rows):
        for c in range(cols):
            x0 = W - M - (c + 1) * cw - c * G  # c=0 が右の列
            y0 = M + r * (rh + G)
            out[('右' if c == 0 else '左') + f'{r + 1}段目'] = (x0, y0, x0 + cw, y0 + rh)
    return out


def balloon(d, cx, cy, rx=46, ry=30):
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill='white', outline='black', width=3)
    for k in (-8, 6):
        d.line((cx - 22, cy + k, cx + 22, cy + k), fill='black', width=3)


def draw(key, bridge):
    cols, rows = LAYOUTS[key]
    cs = cells(cols, rows)
    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    for x0, y0, x1, y1 in cs.values():
        d.rectangle((x0, y0, x1, y1), outline='black', width=4)
    for name, (x0, y0, x1, y1) in cs.items():  # 各コマに1つずつ、右上寄りに吹き出し
        balloon(d, x1 - 60, y0 + 50)
    r1, r2, l1 = cs['右1段目'], cs['右2段目'], cs['左1段目']
    if bridge == 'col':
        balloon(d, (r1[0] + r1[2]) / 2, r1[3] + G / 2, 60, 36)
    elif bridge == 'row':
        balloon(d, r1[0] - G / 2, (r1[1] + r1[3]) / 2, 60, 36)
    p = OUT / f'{key}_{bridge}.png'
    im.save(p)
    return p


def ask(path):
    r = subprocess.run(['claude', '-p', '--model', 'sonnet', '--output-format', 'json', '--allowedTools', 'Read', '--max-turns', '5'],
                       input=PROMPT.format(path=path), capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=600)
    j = json.loads(r.stdout)
    m = re.search(r'\{.*\}', j.get('result', ''), re.S)
    return json.loads(m.group(0)) if m else {'raw': j.get('result', '')}


def main():
    tasks = []
    for key in LAYOUTS:
        for b in BRIDGE:
            p = draw(key, b)
            tasks += [(key, b, run, p) for run in (1, 2)]
    with cf.ThreadPoolExecutor(4) as ex:
        outs = list(ex.map(lambda t: ask(t[3]), tasks))
    rows = []
    for (key, b, run, p), o in zip(tasks, outs):
        order = o.get('order', [])
        second = order[1] if len(order) > 1 else None
        rows.append({'layout': key, 'bridge': b, 'run': run, 'order': order, 'why': o.get('why'),
                     'reading': 'col' if second == '右2段目' else 'row' if second == '左1段目' else 'other'})
    (OUT / 'result.json').write_text(json.dumps({'prompt': PROMPT, 'bridge': BRIDGE, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    for r in rows:
        print(r['layout'], r['bridge'], r['run'], r['reading'], ' '.join(r['order']))


if __name__ == '__main__':
    main()
