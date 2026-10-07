"""P12 コマ割りを LLM に任せたとき、座標を直接出させるのと、段と比だけ出させてプログラムで座標にするのとで、崩れ方が違うか（一覧 2-1、2-5 の一部）。
右から読む。基本枠は 150x220mm。結果は out/ に JSON と SVG。"""
import concurrent.futures as cf
import json
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
W, H = 150.0, 220.0
GX, GY = 2.0, 5.0  # コマ間の隙間 横・縦（mm）
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
MODEL = 'sonnet'
CWD = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else HERE  # LLMを呼ぶ場所（プロジェクトの指示書を読ませないため外を渡す）

SCRIPTS = {
    's1_talk': [
        ('小', '朝の校舎の外観。場所と時間を示す'),
        ('中', '主人公が窓際の席で本を読んでいる'),
        ('小', '友人が後ろから声をかける'),
        ('小', '主人公が顔を上げる'),
        ('大', '友人が一枚の古い地図を机に広げる。この話の始まり'),
        ('小', '地図の端に書かれた印のアップ'),
    ],
    's2_reveal': [
        ('中', '夜の路地を主人公が走る'),
        ('小', '背後を振り返る'),
        ('小', '足音だけが近づく'),
        ('大', '路地の先に巨大な影が立ちはだかる。見せ場'),
    ],
    's3_action': [
        ('小', '二人が向かい合って構える'),
        ('小', '相手の目つき'),
        ('中', '主人公が踏み込む'),
        ('中', '相手が受け流す'),
        ('小', '主人公の驚いた顔'),
        ('大', '相手の反撃が主人公をとらえる。ページの山場'),
        ('小', '倒れた主人公の手元'),
    ],
}

COMMON = """あなたは日本の漫画のネームを切る人です。次の台本の1ページ分を、コマ割りにしてください。
ページは右から左、上から下に読みます。コマの番号の順に読まれる必要があります。
各コマには大きさの希望（大・中・小）が付いています。

台本：
{script}

"""

PROMPT_A = COMMON + """基本枠は横150mm、縦220mmです。左上が原点で、右と下に向かって数値が増えます。
各コマの位置を基本枠の中の座標で決めてください。コマ同士の隙間は横におよそ2mm、縦におよそ5mmです。

決め方にはいくつかの手があります。
・段を揃えて横に並べる：読む順が分かりやすいが、単調になりやすい
・段をまたぐ縦長のコマを入れる：変化が付くが、読む順が迷いやすくなる
・大きなコマに面積を多く取る：見せ場が立つが、他のコマが窮屈になる

出力はJSONだけにしてください。説明は書かないでください。形式：
{{"panels":[{{"n":コマ番号,"x":数値,"y":数値,"w":数値,"h":数値}}]}}
"""

PROMPT_B = COMMON + """コマ割りを「段」と「比」だけで決めてください。座標はプログラムが計算します。
ページを上から下へ段に分け、各段の高さを比で決めます。各段の中を、右から左へコマに分け、各コマの幅を比で決めます。

決め方にはいくつかの手があります。
・段の数を増やす：コマが小さくなり、情報は多く入るが見せ場が弱くなる
・1段に入れるコマを増やす：テンポは速くなるが、1コマが細くなる
・大きなコマに高い比を与える：見せ場が立つが、他の段が窮屈になる

出力はJSONだけにしてください。説明は書かないでください。形式：
{{"rows":[{{"h":段の高さの比,"cells":[{{"n":コマ番号,"w":幅の比}}]}}]}}
cellsは右から左の順に並べます。
"""


def ask(prompt):
    t0 = time.time()
    r = subprocess.run(['claude', '-p', '--model', MODEL, '--output-format', 'json', '--max-turns', '1'],
                       input=prompt, capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=600)
    j = json.loads(r.stdout)
    txt = j.get('result', '')
    m = re.search(r'\{.*\}', txt, re.S)
    return (json.loads(m.group(0)) if m else None), txt, time.time() - t0, j.get('total_cost_usd')


def rows_to_panels(d):
    """段と比から座標を計算する。"""
    rows = d['rows']
    th = sum(r['h'] for r in rows)
    avail_h = H - GY * (len(rows) - 1)
    y = 0.0
    out = []
    for r in rows:
        h = avail_h * r['h'] / th
        tw = sum(c['w'] for c in r['cells'])
        avail_w = W - GX * (len(r['cells']) - 1)
        x = W
        for c in r['cells']:
            w = avail_w * c['w'] / tw
            x -= w
            out.append({'n': c['n'], 'x': x, 'y': y, 'w': w, 'h': h})
            x -= GX
        y += h + GY
    return out


def check(panels, script):
    """機械で数える検査。"""
    n = len(script)
    tol = 0.6
    res = {}
    nums = sorted(p['n'] for p in panels)
    res['count_ok'] = nums == list(range(1, n + 1))
    res['out_of_frame'] = sum(1 for p in panels if p['x'] < -tol or p['y'] < -tol or p['x'] + p['w'] > W + tol or p['y'] + p['h'] > H + tol)
    ov = 0
    thin_gap = 0
    for i, a in enumerate(panels):
        for b in panels[i + 1:]:
            ix = min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])
            iy = min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y'])
            if ix > tol and iy > tol:
                ov += 1
            elif (ix > tol and -tol < iy < 1.0) or (iy > tol and -tol < ix < 1.0):
                thin_gap += 1  # 接しているが隙間が1mm未満
    res['overlaps'] = ov
    res['gap_under_1mm'] = thin_gap
    area = sum(p['w'] * p['h'] for p in panels)
    res['fill'] = round(area / (W * H), 3)
    # 読む順：次のコマが「前のコマより上」または「縦に重なる帯で前より右」なら崩れ
    bym = {p['n']: p for p in panels}
    bad = 0
    for k in range(1, n):
        a, b = bym.get(k), bym.get(k + 1)
        if not a or not b:
            continue
        vov = min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y'])
        if b['y'] + b['h'] <= a['y'] + tol:
            bad += 1
        elif vov > tol and b['x'] >= a['x'] + a['w'] - tol and b['y'] >= a['y'] - tol:
            bad += 1
    res['order_breaks'] = bad
    # 大の指定：大のコマがいちばん広いか
    big = [i + 1 for i, (s, _) in enumerate(script) if s == '大']
    if big and all(k in bym for k in big):
        maxa = max(p['w'] * p['h'] for p in panels)
        res['big_is_largest'] = all(abs(bym[k]['w'] * bym[k]['h'] - maxa) < 1 for k in big)
    res['ok'] = res['count_ok'] and res['out_of_frame'] == 0 and res['overlaps'] == 0 and res['order_breaks'] == 0 and res['gap_under_1mm'] == 0
    return res


def svg(panels, title):
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-8 -14 166 242" width="166" height="242" font-family="sans-serif">',
         f'<text x="0" y="-5" font-size="7">{title}</text>',
         f'<rect x="0" y="0" width="{W}" height="{H}" fill="none" stroke="#bbb" stroke-dasharray="2 2"/>']
    for p in panels:
        s.append(f'<rect x="{p["x"]:.1f}" y="{p["y"]:.1f}" width="{p["w"]:.1f}" height="{p["h"]:.1f}" fill="#fff" fill-opacity=".7" stroke="#222" stroke-width="1"/>')
        s.append(f'<text x="{p["x"] + p["w"] / 2:.1f}" y="{p["y"] + p["h"] / 2 + 4:.1f}" font-size="11" text-anchor="middle">{p["n"]}</text>')
    s.append('</svg>')
    return '\n'.join(s)


def one(sid, method, run):
    script = SCRIPTS[sid]
    st = '\n'.join(f'{i + 1}.（{s}）{t}' for i, (s, t) in enumerate(script))
    prompt = (PROMPT_A if method == 'A' else PROMPT_B).format(script=st)
    try:
        d, raw, sec, cost = ask(prompt)
        panels = (d['panels'] if method == 'A' else rows_to_panels(d)) if d else []
        chk = check(panels, script) if panels else {'ok': False, 'parse_error': True}
    except Exception as e:  # 形式の崩れも結果として残す
        d, raw, sec, cost, panels, chk = None, repr(e), 0, None, [], {'ok': False, 'error': repr(e)}
    name = f'{sid}_{method}_{run}'
    (OUT / f'{name}.svg').write_text(svg(panels, name), encoding='utf-8')
    return {'id': name, 'script': sid, 'method': method, 'run': run, 'sec': round(sec, 1), 'cost_usd': cost,
            'raw': raw, 'panels': panels, 'check': chk}


def main():
    jobs = [(s, m, r) for s in SCRIPTS for m in 'AB' for r in range(RUNS)]
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda a: one(*a), jobs))
    summ = {}
    for m in 'AB':
        rs = [r['check'] for r in res if r['method'] == m]
        summ[m] = {'n': len(rs), 'ok': sum(1 for c in rs if c.get('ok')),
                   'overlaps': sum(1 for c in rs if c.get('overlaps')), 'out_of_frame': sum(1 for c in rs if c.get('out_of_frame')),
                   'order_breaks': sum(1 for c in rs if c.get('order_breaks')), 'gap_under_1mm': sum(1 for c in rs if c.get('gap_under_1mm')),
                   'big_is_largest': sum(1 for c in rs if c.get('big_is_largest')),
                   'fill_mean': round(sum(c.get('fill', 0) for c in rs) / len(rs), 3)}
    (OUT / 'result.json').write_text(json.dumps({'model': MODEL, 'runs': RUNS, 'summary': summ, 'prompt_A': PROMPT_A, 'prompt_B': PROMPT_B,
                                                 'scripts': SCRIPTS, 'results': res}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
