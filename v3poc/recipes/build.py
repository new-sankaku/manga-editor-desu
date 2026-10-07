"""コマの絵の作り方の一覧（再現に要る情報と、作りたい絵の図と、結果3枚ずつ）を作る。
元の情報は P14・P15 の gen.json と、目で見た判定の labels.json。
使い方: python build.py  → index.html と thumb/ を作り直す"""
import html
import json
import pathlib

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
THUMB = HERE / 'thumb'
THUMB.mkdir(exist_ok=True)
P14 = ROOT / 'p14_margin' / 'out'
P15 = ROOT / 'p15_shots' / 'out'
LABELS = json.loads((HERE / 'labels.json').read_text(encoding='utf-8')) if (HERE / 'labels.json').exists() else {}
MARK = {'ok': ('○', 'good'), 'part': ('△', ''), 'ng': ('×', 'bad')}

# 作りたい絵。kind: scene（人物と背景）/ chara（人物だけ）/ bg（背景だけ）。fig は人物の枠（コマに対する割合）
WANT = {
    'long_yoko': ('scene', (0.66, 0.22, 0.80, 0.94), '横長のコマ。人物は全身が小さく入り、周りの大半は街並み。道や建物の並びで奥行きが出る。人物は1人。',
                  '人物が1人で全身が入る・人物の周りに街が見える・人物が増えたり重なったりしない'),
    'long_tate': ('scene', (0.30, 0.62, 0.70, 0.94), '縦長のコマ。人物は下の方に小さく全身が入り、上は建物や空が高く続く。人物は1人。',
                  '人物が1人で全身が入る・上に建物や空の広がりがある・人物が縦に並んで増えない'),
    'full_std': ('scene', (0.18, 0.38, 0.36, 0.94), '標準の形のコマ。人物は全身で、コマの半分ほどの高さ。横に街の余白がある。',
                 '全身が入る・人物がコマの半分ほどの高さ・横に余白がある'),
    'chara_only': ('chara', (0.28, 0.04, 0.72, 0.96), '人物だけの絵。背景は透明。頭から足先まで切れない。後で背景の絵に重ねる。',
                   '全身が切れずに入る・背景を抜いたあとに人物の一部が欠けない・背景の残りがない'),
    'bg_yoko': ('bg', (0.62, 0.30, 0.82, 0.94), '横長の背景だけの絵。人がいない。後で人物を重ねる場所（道の手前など）がある。',
                '人が1人も描かれない・奥行きがある・人物を置ける地面がある'),
    'bg_tate': ('bg', (0.30, 0.60, 0.70, 0.94), '縦長の背景だけの絵。人がいない。上に建物や空、下に人物を置ける地面。',
                '人が1人も描かれない・縦に建物や空が続く・下に人物を置ける地面がある'),
    'bg_std': ('bg', (0.40, 0.40, 0.60, 0.94), '標準の形の背景だけの絵。人がいない。奥行きがある。',
               '人が1人も描かれない・奥行きがある・人物を置ける地面がある'),
}
SHAPE_TARGET = {'yoko': 'long_yoko', 'tate': 'long_tate', 'std': 'full_std'}
SHAPE_NAME = {'yoko': '横長', 'tate': '縦長', 'std': '標準'}


def esc(s):
    return html.escape(str(s))


def figure_path(x0, y0, x1, y1):
    """人物の簡単な形（頭・胴・脚）。"""
    w, h = x1 - x0, y1 - y0
    cx = x0 + w / 2
    r = h * 0.07
    body = (f'M{cx - w * 0.30:.1f},{y0 + h * 0.18:.1f} L{cx + w * 0.30:.1f},{y0 + h * 0.18:.1f} L{cx + w * 0.22:.1f},{y0 + h * 0.55:.1f} '
            f'L{cx + w * 0.18:.1f},{y1:.1f} L{cx + w * 0.04:.1f},{y1:.1f} L{cx:.1f},{y0 + h * 0.62:.1f} L{cx - w * 0.04:.1f},{y1:.1f} '
            f'L{cx - w * 0.18:.1f},{y1:.1f} L{cx - w * 0.22:.1f},{y0 + h * 0.55:.1f} Z')
    return f'<circle cx="{cx:.1f}" cy="{y0 + r:.1f}" r="{r:.1f}" class="fg"/><path d="{body}" class="fg"/>'


def want_svg(key, size):
    kind, (a, b, c, d), text, _ = WANT[key]
    W, H = size
    s = 200 / max(W, H)
    w, h = W * s, H * s
    x0, y0, x1, y1 = a * w, b * h, c * w, d * h
    out = [f'<svg viewBox="-2 -2 {w + 4:.0f} {h + 4:.0f}" role="img" aria-label="{esc(text)}" class="want">']
    if kind == 'chara':
        out.append(f'<rect x="0" y="0" width="{w:.1f}" height="{h:.1f}" fill="url(#chk)"/>')
    else:
        hz = h * (0.50 if W > H else 0.42 if W == H else 0.55)
        vx = w * (0.30 if W > H else 0.5)
        out.append(f'<rect x="0" y="0" width="{w:.1f}" height="{h:.1f}" class="sky"/>')
        out.append(f'<rect x="0" y="{hz:.1f}" width="{w:.1f}" height="{h - hz:.1f}" class="ground"/>')
        for px, py in ((0, 0), (w, 0), (0, h), (w, h), (0, hz * 0.4), (w, hz * 0.4)):
            out.append(f'<line x1="{vx:.1f}" y1="{hz:.1f}" x2="{px:.1f}" y2="{py:.1f}" class="persp"/>')
        out.append(f'<text x="{vx:.1f}" y="{hz - 4:.1f}" class="lab" text-anchor="middle">奥</text>')
    if kind == 'bg':
        out.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" class="slot"/>')
        out.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{y1 - 4:.1f}" class="lab" text-anchor="middle">人物を後で置く</text>')
    else:
        out.append(figure_path(x0, y0, x1, y1))
    if kind == 'scene':
        # 余白の見出しを、人物の枠から最も遠い側に置く
        lx = x0 / 2 if x0 > w - x1 else (x1 + w) / 2
        ly = y0 / 2 if y0 > h * 0.3 else h * 0.2
        out.append(f'<text x="{lx:.1f}" y="{ly:.1f}" class="lab strong" text-anchor="middle">余白</text>')
    out.append(f'<rect x="0" y="0" width="{w:.1f}" height="{h:.1f}" class="frame"/></svg>')
    return ''.join(out)


def thumb(src, box=260):
    im = Image.open(src)
    im.thumbnail((box, box))
    if im.mode == 'RGBA':
        dst = THUMB / (src.stem + '.png')
        im.save(dst)
    else:
        dst = THUMB / (src.stem + '.jpg')
        im.convert('RGB').save(dst, quality=82)
    return dst


def shot(src, cap, group, extra=''):
    t = thumb(src)
    lab = LABELS.get(group, {}).get(src.name)
    mark = ''
    if lab:
        m, cls = MARK[lab['v']]
        mark = f'<span class="{cls}">{m}</span> {esc(lab.get("note", ""))}'
    rel = pathlib.Path('..') / src.relative_to(ROOT)
    cls = ' cut' if t.suffix == '.png' else ''
    return (f'<figure class="shot"><a href="{rel.as_posix()}"><img src="thumb/{t.name}" alt="{esc(src.name)}" class="{cls.strip()}" loading="lazy"></a>'
            f'<figcaption>{esc(cap)} {mark}{extra}</figcaption></figure>')


def tally(group, files):
    labs = [LABELS.get(group, {}).get(f) for f in files]
    if not all(labs):
        return '<span class="muted">判定まだ</span>'
    ok = sum(1 for x in labs if x['v'] == 'ok')
    return f'<b>{ok}/{len(files)}</b> がねらいどおり'


def kv(rows):
    return '<table class="kv">' + ''.join(f'<tr><th>{esc(k)}</th><td>{v}</td></tr>' for k, v in rows) + '</table>'


def code(s):
    return f'<code>{esc(s)}</code>'


def p15_section(g):
    parts, styles, targets = g['parts'], g['styles'], g['targets']
    runs = {r['file']: r for r in g['runs']}
    r0 = g['runs'][0]
    seeds = sorted({r['seed'] for r in g['runs']})
    out = ['<section id="common"><h2>共通の設定</h2>',
           kv([('モデル', code(r0['ckpt']) + '（WAI-illustrious-SDXL v16。生成した画像の利用に条件は及ばない。詳しくは調査の文書）'),
               ('サンプラー', code(f"{r0['sampler']} / {r0['scheduler']}")), ('ステップ・CFG', code(f"{r0['steps']} / {r0['cfg']}")),
               ('seed', code(', '.join(map(str, seeds))) + '（どの条件も3つ。偶然できたものと安定してできるものを分けるため）'),
               ('画質の言葉', code(parts['quality'])), ('否定の言葉（共通）', code(parts['negative_base'])),
               ('差し替える部品：人物', code(parts['chara']) + '（人物を描く狙いだけに入れる。作品のキャラに差し替える）'),
               ('差し替える部品：場所', code(parts['place']) + '（背景を描く狙いだけに入れる。場面に差し替える）'),
               ('プロンプトの組み方', '画質 ＋ 絵柄 ＋ 狙い ＋ 人物 ＋ 場所 の順に「, 」でつなぐ')]),
           '</section><section id="styles"><h2>絵柄</h2><p>絵柄はモデルを変えず、言葉だけで変えた。</p><table><tr><th>絵柄</th><th>言葉</th><th>見本（標準コマの全身・seed ' + str(seeds[0]) + '）</th></tr>']
    for k, v in styles.items():
        f = f'{k}_full_std_{seeds[0]}.png'
        out.append(f'<tr><td>{esc(v["name"])}<br><span class="muted">{k}</span></td><td>{code(v["words"])}</td>'
                   f'<td>{shot(P15 / f, "", "p15") if (P15 / f).exists() else ""}</td></tr>')
    out.append('</table>' + (f'<p class="note">{esc(LABELS["styles_note"])}</p>' if 'styles_note' in LABELS else '') + '</section>')
    for key, t in targets.items():
        kind, _, text, crit = WANT[key]
        w, h = t['size']
        rows = [('大きさ', code(f'{w} × {h}')), ('狙いに要る言葉', code(t['add'])),
                ('足す否定の言葉', code(t['add_negative']) if t['add_negative'] else 'なし'),
                ('入れる部品', '、'.join(x for x, y in (('人物', t['human']), ('場所', t['place'])) if y) or 'なし'),
                ('制御', 'なし（言葉だけ）')]
        if t['cut']:
            post = next(r['post'] for r in runs.values() if r['target'] == key)
            rows.append(('後処理', f'背景を抜く：{code(post["node"])}、モデル {code(post["model"])}（MIT）、背景は透明'))
        rows.append(('判定の基準', esc(crit)))
        out.append(f'<section id="{key}"><h2>{esc(t["name"])}</h2><div class="recipe"><figure class="wantfig">{want_svg(key, t["size"])}'
                   f'<figcaption>作りたい絵：{esc(text)}</figcaption></figure><div>{kv(rows)}</div></div>')
        if key in LABELS.get('target_notes', {}):
            out.append(f'<p class="note">{esc(LABELS["target_notes"][key])}</p>')
        for sk, sv in styles.items():
            fs = [f'{sk}_{key}_{s}.png' for s in seeds]
            ex = runs[fs[0]]
            shots = []
            for f in fs:
                if not (P15 / f).exists():
                    continue
                r = runs[f]
                shots.append(shot(P15 / f, f'seed {r["seed"]}', 'p15'))
                if r['post']:
                    shots.append(shot(P15 / r['post']['file'], f'seed {r["seed"]} 背景を抜いた', 'p15'))
            out.append(f'<div class="style"><h3>{esc(sv["name"])} <small>{tally("p15", fs)}</small></h3><div class="shots">{"".join(shots)}</div>'
                       f'<details><summary>プロンプトの全文</summary>{kv([("プロンプト", code(ex["positive"])), ("否定", code(ex["negative"]))])}</details></div>')
        out.append('</section>')
    return ''.join(out)


def p14_section(g, res):
    out = []
    seeds = sorted({r['seed'] for r in g['runs']})
    meas = res['summary'] if res else {}
    rowm = {r['file']: r for r in res['rows']} if res else {}
    for shape, sv in g['shapes'].items():
        w, h = sv['size']
        key = SHAPE_TARGET[shape]
        out.append(f'<section id="fit_{shape}"><h2>コマの形に合わせる：{SHAPE_NAME[shape]}（{w} × {h}）</h2>'
                   f'<div class="recipe"><figure class="wantfig">{want_svg(key, (w, h))}<figcaption>作りたい絵：{esc(WANT[key][2])}'
                   f'人物は図の枠の位置と大きさに置きたい。</figcaption></figure><div>'
                   + kv([('プロンプト（全部の手で同じ）', code(g['prompt'])), ('否定', code(g['negative'])),
                         ('モデル・サンプラー', code(f"{g['ckpt']} / {g['sampler']} / {g['scheduler']} / {g['steps']}ステップ / CFG {g['cfg']}")),
                         ('人物の枠（画素）', code(sv['fig'])), ('骨格の図', shot(P14 / 'aux' / f'pose_{shape}.png', '', 'p14'))]) + '</div></div>')
        if shape in LABELS.get('shape_notes', {}):
            out.append(f'<p class="note">{esc(LABELS["shape_notes"][shape])}</p>')
        for m, mv in g['modes'].items():
            fs = [f'{shape}_{m}_{s}.png' for s in seeds]
            shots = []
            for f in fs:
                if (P14 / f).exists():
                    r = rowm.get(f)
                    ex = f'<br><span class="muted">人数 {r["persons"]}・高さ {r["h_ratio"]}・枠との重なり {r["fig_iou"]}</span>' if r else ''
                    shots.append(shot(P14 / f, f'seed {f.rsplit("_", 1)[1][:-4]}', 'p14', ex))
            ctl = mv['control']
            ctl_rows = [(k, code(v)) for k, v in ctl.items()] if ctl else [('制御', 'なし')]
            s = meas.get(f'{shape}/{m}')
            ms = f'人物が1人：{s["one_person"]}/{s["n"]}・平均の高さ {s["h_ratio"]}・枠との重なり {s["fig_iou"]}・{s["sec"]}秒' if s else ''
            out.append(f'<div class="style"><h3>{esc(mv["name"])} <span class="muted">{m}</span> <small>{tally("p14", fs)}</small></h3>'
                       f'<p class="muted">{esc(ms)}</p><div class="shots">{"".join(shots)}</div>'
                       f'<details><summary>制御の設定</summary>{kv(ctl_rows)}</details></div>')
        out.append('</section>')
    return ''.join(out)


CSS = """
:root{--bg:#eceef0;--surface:#fff;--surface-2:#f5f6f7;--line:#d9dce0;--ink:#1d2126;--ink-2:#4a525c;--ink-3:#79828d;--acc:#2f5f8f;--warn:#a4452c;--ok:#2e6b45;
--font:"Yu Gothic UI","Meiryo",system-ui,sans-serif;--chk:#dde0e4}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.7 var(--font)}
header{position:sticky;top:0;z-index:5;background:var(--surface);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline}
header h1{font-size:16px;margin:0}
nav{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:13px}
nav a{color:var(--acc);text-decoration:none}
main{padding:14px 16px 40px;display:grid;gap:14px;max-width:1400px;margin:0 auto}
section{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:14px 16px;scroll-margin-top:70px;min-width:0}
h2{font-size:16px;margin:0 0 10px;text-wrap:balance}
h3{font-size:14px;margin:0 0 6px}
h3 small{font-weight:400;margin-left:8px}
.muted{color:var(--ink-3);font-size:12px}
.good{color:var(--ok);font-weight:700}
.bad{color:var(--warn);font-weight:700}
.note{background:var(--surface-2);border-left:3px solid var(--ink-3);padding:6px 10px;font-size:13px;color:var(--ink-2)}
table{border-collapse:collapse;font-size:13px;max-width:100%}
th,td{border:1px solid var(--line);padding:3px 8px;text-align:left;vertical-align:top}
th{background:var(--surface-2);font-weight:600;color:var(--ink-2);white-space:nowrap}
code{font-family:Consolas,"BIZ UDGothic",monospace;font-size:12px;background:var(--surface-2);padding:1px 4px;border-radius:3px;word-break:break-word}
.recipe{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start}
.recipe>div{flex:1 1 420px;min-width:0;overflow-x:auto}
.wantfig{margin:0;flex:0 1 240px}
.wantfig figcaption{font-size:12px;color:var(--ink-2)}
svg.want{width:100%;max-width:240px;max-height:240px;height:auto;display:block;color:var(--ink)}
svg.want .frame{fill:none;stroke:currentColor;stroke-width:2}
svg.want .sky{fill:var(--surface)}
svg.want .ground{fill:var(--surface-2)}
svg.want .persp{stroke:var(--ink-3);stroke-width:.6}
svg.want .fg{fill:var(--acc)}
svg.want .slot{fill:none;stroke:var(--acc);stroke-width:1.2;stroke-dasharray:4 3}
svg.want .lab{font-size:10px;fill:var(--ink-3)}
svg.want .strong{font-size:12px;fill:var(--ink-2);font-weight:700}
.style{border-top:1px solid var(--line);margin-top:10px;padding-top:8px}
.shots{display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start}
.shot{margin:0;max-width:260px}
.shot img{display:block;max-width:100%;height:auto;border:1px solid var(--line);border-radius:4px}
.shot img.cut{background:repeating-conic-gradient(var(--chk) 0 25%,var(--surface) 0 50%) 0 0/16px 16px}
.shot figcaption{font-size:12px;color:var(--ink-2)}
details{margin-top:6px;font-size:13px}
summary{cursor:pointer;color:var(--acc)}
"""


def main():
    g15 = json.loads((P15 / 'gen.json').read_text(encoding='utf-8'))
    g14 = json.loads((P14 / 'gen.json').read_text(encoding='utf-8'))
    res = json.loads((P14 / 'result.json').read_text(encoding='utf-8')) if (P14 / 'result.json').exists() else None
    nav = [('common', '共通'), ('styles', '絵柄')] + [(k, v['name']) for k, v in g15['targets'].items()] + \
          [(f'fit_{s}', f'形に合わせる（{SHAPE_NAME[s]}）') for s in g14['shapes']]
    intro = LABELS.get('intro', '')
    page = (f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>コマの絵の作り方</title><style>{CSS}</style></head><body>'
            f'<header><h1>コマの絵の作り方</h1><nav>{"".join(f"<a href=#{k}>{esc(v)}</a>" for k, v in nav)}'
            f'<a href="../report/index.html">検証の結果へ</a></nav></header><main>'
            f'<section><h2>この一覧について</h2><p>狙いのコマごとに、作りたい絵の図・要る言葉・大きさ・制御・後処理と、seed を変えた3枚の結果を並べた。'
            f'サムネイルを押すと元の大きさの絵が開く。○はねらいどおり、△は一部、×は外れ（目で見た判定）。</p>'
            f'{f"<p class=note>{esc(intro)}</p>" if intro else ""}</section>'
            f'{p15_section(g15)}{p14_section(g14, res)}</main></body></html>')
    page = page.replace('<main>', '<main><svg width="0" height="0" style="position:absolute"><defs><pattern id="chk" width="10" height="10" '
                        'patternUnits="userSpaceOnUse"><rect width="10" height="10" fill="#fff"/><rect width="5" height="5" fill="#dde0e4"/>'
                        '<rect x="5" y="5" width="5" height="5" fill="#dde0e4"/></pattern></defs></svg>', 1)
    (HERE / 'index.html').write_text(page, encoding='utf-8')
    print('ok', len(page))


if __name__ == '__main__':
    main()
