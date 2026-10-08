"""P50 コマ割りの計算を制約ソルバー（kiwisolver）で表せるかを確かめる（設計 3.1 の部品表「コマ割りの計算」）。
確かめること:
  A 段と比・縦横別の余白・基本枠と断ち切り・最小のコマ・見開きを線形制約で書いて解けるか
  B 人が1つのコマの大きさを固定したとき、ほかが追従するか（強い制約・中の制約・弱い制約）
  C 両立しない制約を入れたとき、例外になるか、弱い制約が崩れるか
  D 斜めの区切り（台形のコマ）を線形制約で書ける範囲
  E 1ページを解く時間
使い方: python run.py（kiwisolver・matplotlib が要る）。out/result.json と out/sheet.png を書く。
寸法（mm）: 仕上がり B5 182x257、塗り足し3、基本枠 150x220（一般に流通する値。出典は result.json の source。リポジトリの文書には無い）。
"""
import json
import math
import pathlib
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Polygon, Rectangle
from kiwisolver import Solver, Variable, UnsatisfiableConstraint

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
for f in ('/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf',):
    if pathlib.Path(f).exists():
        font_manager.fontManager.addfont(f)
        plt.rcParams['font.family'] = 'IPAGothic'

TRIM_W, TRIM_H, BLEED = 182.0, 257.0, 3.0
FR_W, FR_H = 150.0, 220.0
FR_L, FR_T = (TRIM_W - FR_W) / 2, (TRIM_H - FR_H) / 2
GX, GY = 3.0, 6.0          # 横の余白（コマの左右）・縦の余白（段の上下）。設計6章は「左右が上下より狭い」
MIN_SIZE = 20.0
STRONG, MEDIUM, WEAK, REQ = 'strong', 'medium', 'weak', 'required'


def st(c, s):
    return c | s


class Page:
    """rows: [{'h':比, 'groups':[{'range':(左,右), 'w':[比...], 'bleedT':bool,...}], 'bleedB':bool}]"""

    def __init__(self, rows, top=FR_T, bottom=FR_H + FR_T, gx=GX, gy=GY, ratio_strength=MEDIUM, pin=None, pin_exclude=True):
        self.s = Solver()
        self.rows = rows
        self.gx, self.gy = gx, gy
        self.t = [Variable(f't{i}') for i in range(len(rows))]
        self.b = [Variable(f'b{i}') for i in range(len(rows))]
        self.pan = []   # (row, group, idx, l, r)
        s = self.s
        top0 = -BLEED if rows[0].get('bleedT') else top
        bot1 = TRIM_H + BLEED if rows[-1].get('bleedB') else bottom
        s.addConstraint(self.t[0] == top0)
        s.addConstraint(self.b[-1] == bot1)
        for i in range(len(rows)):
            s.addConstraint(self.b[i] - self.t[i] >= MIN_SIZE)
            if i + 1 < len(rows):
                s.addConstraint(self.t[i + 1] == self.b[i] + gy)
        # 段の高さの比（段の尺度変数 hs。h_i = hs * 比）
        self.hs = Variable('hs')
        for i, r in enumerate(rows):
            s.addConstraint(st((self.b[i] - self.t[i]) == self.hs * r['h'], ratio_strength))
        for i, r in enumerate(rows):
            for gi, g in enumerate(r['groups']):
                L, R = g['range']
                # 断ち切りは基本枠ではなく塗り足しの縁（仕上がりの外3mm）まで伸ばす
                if g.get('bleedL'):
                    L = (TRIM_W if L >= TRIM_W else 0.0) - BLEED
                if g.get('bleedR'):
                    R = (TRIM_W * 2 if R > TRIM_W else TRIM_W) + BLEED
                n = len(g['w'])
                ls = [Variable(f'l{i}_{gi}_{j}') for j in range(n)]
                rs = [Variable(f'r{i}_{gi}_{j}') for j in range(n)]
                ws = Variable(f'ws{i}_{gi}')
                s.addConstraint(ls[0] == L)
                s.addConstraint(rs[-1] == R)
                for j in range(n):
                    s.addConstraint(rs[j] - ls[j] >= MIN_SIZE)
                    if j + 1 < n:
                        s.addConstraint(ls[j + 1] == rs[j] + gx)
                    if not (pin and (i, gi, j) == pin[0] and pin_exclude):
                        s.addConstraint(st((rs[j] - ls[j]) == ws * g['w'][j], ratio_strength))
                    self.pan.append((i, gi, j, ls[j], rs[j]))
        if pin:
            (i, gi, j), width = pin
            p = next(p for p in self.pan if p[:3] == (i, gi, j))
            s.addConstraint(st((p[4] - p[3]) == width, STRONG))
        # 弱い好み：段の高さ尺度・列の尺度が極端にならない（解を一意にする）
        s.addConstraint(st(self.hs >= 0, WEAK))
        s.updateVariables()

    def rects(self):
        out = []
        for i, gi, j, l, r in self.pan:
            out.append((l.value(), self.t[i].value(), r.value() - l.value(), self.b[i].value() - self.t[i].value()))
        return out


def draw_frames(ax, spread=False, pages=1):
    for k in range(pages):
        ox = k * TRIM_W
        ax.add_patch(Rectangle((ox, 0), TRIM_W, TRIM_H, fill=False, ec='#888', lw=0.8))
        ax.add_patch(Rectangle((ox - BLEED, -BLEED), TRIM_W + 2 * BLEED, TRIM_H + 2 * BLEED, fill=False, ec='#d33', lw=0.5, ls='--'))
        ax.add_patch(Rectangle((ox + FR_L, FR_T), FR_W, FR_H, fill=False, ec='#36c', lw=0.6, ls=':'))


def show(ax, rects, title, pages=1, polys=None, hl=None):
    draw_frames(ax, pages=pages)
    for k, (x, y, w, h) in enumerate(rects):
        ax.add_patch(Rectangle((x, y), w, h, fc='#ddd' if k != hl else '#fc8', ec='k', lw=1))
        ax.text(x + w / 2, y + h / 2, f'{w:.0f}x{h:.0f}', ha='center', va='center', fontsize=6)
    for poly in polys or []:
        ax.add_patch(Polygon(poly, closed=True, fc='#ddd', ec='k', lw=1))
    ax.set_xlim(-8, TRIM_W * pages + 8)
    ax.set_ylim(TRIM_H + 8, -8)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=8)
    ax.axis('off')


def row(h, w, **kw):
    return {'h': h, 'groups': [{'range': (FR_L, FR_L + FR_W), 'w': w, **kw.get('g', {})}], **{k: v for k, v in kw.items() if k != 'g'}}


BASE = [row(1, [1, 1]), row(1.4, [2, 1, 1]), row(1, [1, 2])]
result = {'source': {
    'trim_mm': [TRIM_W, TRIM_H], 'bleed_mm': BLEED, 'basic_frame_mm': [FR_W, FR_H],
    'note': 'B5 仕上がり182x257・塗り足し3・基本枠150x220は一般に流通する値（出典は未確認。リポジトリの文書にはB5の仕上がりのみ）。'}}
fig_items = []

# A 基本の3段
p = Page(BASE)
rects = p.rects()
tot_w = {i: None for i in range(3)}
result['A_base'] = {
    'rects_mm': [[round(v, 2) for v in r] for r in rects],
    'row_heights': [round(p.b[i].value() - p.t[i].value(), 2) for i in range(3)],
    'gap_x': [round(rects[k + 1][0] - (rects[k][0] + rects[k][2]), 3) for k in (0, 2, 3, 5)] if False else None,
}
# 余白の確認
gaps_x, gaps_y = [], []
for i in range(3):
    rr = [r for r, q in zip(rects, p.pan) if q[0] == i]
    gaps_x += [round(rr[k + 1][0] - rr[k][0] - rr[k][2], 3) for k in range(len(rr) - 1)]
for i in range(2):
    gaps_y.append(round(p.t[i + 1].value() - p.b[i].value(), 3))
result['A_base'].update({'gaps_x': gaps_x, 'gaps_y': gaps_y,
                         'width_ratio_row1': [round(rects[2][2] / rects[3][2], 3), round(rects[3][2] / rects[4][2], 3)],
                         'height_ratio_row1_row0': round(rects[2][3] / rects[0][3], 3), 'frame_right': round(rects[1][0] + rects[1][2], 3), 'frame_bottom': round(rects[-1][1] + rects[-1][3], 3)})
fig_items.append((rects, 'A 3段(2/3/2コマ)\n比・余白 横3 縦6・基本枠', 1, None, None))

# A 断ち切り（上段の左コマが上と左に、最下段の右コマが右と下に断ち切り）
rows_b = [
    {'h': 1, 'bleedT': True, 'groups': [{'range': (FR_L, FR_L + FR_W), 'w': [1, 1], 'bleedL': True, 'bleedR': True}]},
    row(1.4, [2, 1, 1]),
    {'h': 1, 'bleedB': True, 'groups': [{'range': (FR_L, FR_L + FR_W), 'w': [1, 2], 'bleedR': True}]},
]
p = Page(rows_b)
rects = p.rects()
result['A_bleed'] = {'rects_mm': [[round(v, 2) for v in r] for r in rects],
                     'top_edge': round(rects[0][1], 2), 'left_edge': round(rects[0][0], 2),
                     'right_edge_row0': round(rects[1][0] + rects[1][2], 2), 'bottom_edge': round(rects[-1][1] + rects[-1][3], 2),
                     'right_edge_last': round(rects[-1][0] + rects[-1][2], 2)}
fig_items.append((rects, 'A 断ち切り\n上段は上・左右、下段は右・下', 1, None, None))

# A 見開き（1段目は見開きを横断する1コマ、2段目以降は左右のページ別）
lg, rg = (FR_L, FR_L + FR_W), (TRIM_W + FR_L, TRIM_W + FR_L + FR_W)
rows_s = [
    {'h': 1.2, 'bleedT': True, 'groups': [{'range': (lg[0], rg[1]), 'w': [1]}]},
    {'h': 1, 'groups': [{'range': lg, 'w': [1, 1]}, {'range': rg, 'w': [2, 1]}]},
    {'h': 1, 'bleedB': True, 'groups': [{'range': lg, 'w': [1]}, {'range': rg, 'w': [1, 1, 1]}]},
]
p = Page(rows_s)
rects = p.rects()
result['A_spread'] = {'rects_mm': [[round(v, 2) for v in r] for r in rects], 'span_width': round(rects[0][2], 2),
                      'note': '横断コマは基本枠の左端〜右ページの基本枠の右端。ノドの位置はx=182。ページ別の段は高さを共有'}
fig_items.append((rects, 'A 見開き(ノドをまたぐコマ)', 2, None, None))

# B 人が1コマを固定
b_res = {}
def width_list(p, i):
    return [round(r[2], 2) for r, q in zip(p.rects(), p.pan) if q[0] == i]
base_w = width_list(Page(BASE), 1)
for label, kw in (('除外あり_100', dict(pin=((1, 0, 0), 100.0))), ('除外あり_60', dict(pin=((1, 0, 0), 60.0))),
                  ('除外なし_100', dict(pin=((1, 0, 0), 100.0), pin_exclude=False))):
    p = Page(BASE, **kw)
    b_res[label] = {'row1_widths': width_list(p, 1), 'other_rows': [width_list(p, 0), width_list(p, 2)],
                    'row_heights': [round(p.b[i].value() - p.t[i].value(), 2) for i in range(3)]}
b_res['固定なし_row1_widths'] = base_w
result['B_pin'] = b_res
p = Page(BASE, pin=((1, 0, 0), 100.0))
fig_items.append((p.rects(), 'B 段2の1コマを幅100に固定(強)\nほかは比2:1の残りを分け合う', 1, None, 2))
p = Page(BASE, pin=((1, 0, 0), 100.0), pin_exclude=False)
fig_items.append((p.rects(), 'B 固定したコマも比の制約に残す\n比が崩れる様子', 1, None, 2))

# C 両立しない制約
c_res = {}
s = Solver(); x = Variable('x')
s.addConstraint(x >= 20)
try:
    s.addConstraint(x == 10)
    c_res['required同士'] = '例外なし'
except UnsatisfiableConstraint as e:
    c_res['required同士'] = f'UnsatisfiableConstraint（{type(e).__name__}）'
# 強い固定 vs 必須（基本枠より広い幅）
p = Page(BASE, pin=((1, 0, 0), 400.0))
c_res['強い固定400（基本枠150の段）'] = {'row1_widths': width_list(p, 1), '例外': 'なし。必須（基本枠・余白・最小）が勝ち、強い固定が崩れた'}
# 強い固定 vs 最小のコマ（必須）
p = Page(BASE, pin=((1, 0, 0), 5.0))
c_res['強い固定5（最小20）'] = {'row1_widths': width_list(p, 1), '例外': 'なし。最小が勝った'}
# 固定2つで合計が段の長さを超える（強同士）
try:
    p = Page(BASE, pin=((1, 0, 0), 100.0))
    s = p.s; q = [q for q in p.pan if q[:3] == (1, 0, 1)][0]
    s.addConstraint(((q[4] - q[3]) == 100.0) | 'strong'); s.updateVariables()
    c_res['強い固定を2つ（100+100）'] = {'row1_widths': width_list(p, 1), '例外': 'なし。強同士は両立せず、片方（2つ目）が崩れた'}
except UnsatisfiableConstraint:
    c_res['強い固定を2つ（100+100）'] = '例外'
# 必須の比（ratio=required）と固定（required）
try:
    p = Page(BASE, ratio_strength=REQ)
    s = p.s; q = [q for q in p.pan if q[:3] == (1, 0, 0)][0]
    s.addConstraint(((q[4] - q[3]) == 100.0) | 'required')
    c_res['必須の比＋必須の固定'] = '例外なし'
except UnsatisfiableConstraint:
    c_res['必須の比＋必須の固定'] = 'UnsatisfiableConstraint'
# 行の高さ比が必須で、最小20と衝突
try:
    Page([row(1, [1]), row(0.01, [1])], ratio_strength=REQ)
    c_res['必須の比 1:0.01（最小20と衝突）'] = '例外なし'
except UnsatisfiableConstraint:
    c_res['必須の比 1:0.01（最小20と衝突）'] = 'UnsatisfiableConstraint'
p = Page([row(1, [1]), row(0.01, [1])])
c_res['中の比 1:0.01（最小20と衝突）'] = {'row_heights': [round(p.b[i].value() - p.t[i].value(), 2) for i in range(2)], '例外': 'なし。比の中の制約が崩れ、最小が勝った'}
result['C_conflict'] = c_res
fig_items.append((Page(BASE, pin=((1, 0, 0), 400.0)).rects(), 'C 幅400に強く固定\n必須(基本枠)が勝ち固定が崩れる', 1, None, 2))

# D 斜め
def slanted(ks, mrow, gap=3.0):
    """2段。上段は3コマで区切りが斜め(傾き ks=tanθ、水平の差=k*段の高さ)、段の境も斜め(傾き mrow=縦の差/横)。
    すべて線形制約。角度は定数（変数にすると sqrt(1+k^2) の補正が非線形になる）。"""
    s = Solver()
    L, R, T, B = FR_L, FR_L + FR_W, FR_T, FR_T + FR_H
    ht = Variable('ht')            # 上段の高さ（左端での段の境）
    yl = Variable('yl')            # 段の境の左端のy
    s.addConstraint(yl == T + ht)
    # 段の境: y(x) = yl + mrow*(x-L)
    ybound = lambda x: yl + mrow * (x - L)
    gapy = gap * math.sqrt(1 + mrow ** 2)
    n = len(ks) + 1
    u = [Variable(f'u{j}') for j in range(n + 1)]   # 上辺の各境のx
    # 上段の高さは境の位置により変わるが、斜めの区切りの下端x = 上端x + k*(区切りの高さ)。区切りの高さは境のy(x)-T なので x の1次式
    d = [Variable(f'd{j}') for j in range(n + 1)]   # 下辺（段の境上）の各境のx
    s.addConstraint(u[0] == L); s.addConstraint(u[n] == R)
    s.addConstraint(d[0] == L); s.addConstraint(d[n] == R)
    # 区切りjは (u[j]上辺,T)-(d[j],ybound(d[j])) を結ぶ。水平の差 d-u = k*(ybound(d)-T)  → d - u = k*(yl + m*(d-L) - T): 線形
    # 簡略: 区切りjを2本の平行線（左の線 pl_j・右の線 pr_j）として持つ。
    pl_u = [Variable() for _ in ks]; pr_u = [Variable() for _ in ks]
    pl_d = [Variable() for _ in ks]; pr_d = [Variable() for _ in ks]
    for j, k in enumerate(ks):
        for (xu, xd) in ((pl_u[j], pl_d[j]), (pr_u[j], pr_d[j])):
            s.addConstraint(xd - xu == k * (ybound(xd) - T))     # 斜めの角度（線形）
        # 垂直な余白gapは、平行な2線の水平距離 gap*sqrt(1+k^2)（上辺は水平なので上辺での差で与える）
        s.addConstraint(pr_u[j] - pl_u[j] == gap * math.sqrt(1 + k * k))
    # 並び
    s.addConstraint(pl_u[0] - L >= MIN_SIZE)
    for j in range(len(ks) - 1):
        s.addConstraint(pl_u[j + 1] - pr_u[j] >= MIN_SIZE)
        s.addConstraint(pl_d[j + 1] - pr_d[j] >= MIN_SIZE)
    s.addConstraint(R - pr_u[-1] >= MIN_SIZE)
    # 弱い好み：上辺で等分
    n_seg = len(ks) + 1
    tot = (R - L) - sum(gap * math.sqrt(1 + k * k) for k in ks)
    s.addConstraint(((pl_u[0] - L) == tot / n_seg) | 'weak')
    for j in range(len(ks) - 1):
        s.addConstraint(((pl_u[j + 1] - pr_u[j]) == tot / n_seg) | 'weak')
    # 下段（3コマの段）。段の境の下にgapys
    yl2 = Variable('yl2')
    s.addConstraint(yl2 == yl + gapy)
    s.updateVariables()
    top = []
    xs_u = [L] + [v for j in range(len(ks)) for v in (pl_u[j].value(), pr_u[j].value())] + [R]
    xs_d = [L] + [v for j in range(len(ks)) for v in (pl_d[j].value(), pr_d[j].value())] + [R]
    yb = lambda x: yl.value() + mrow * (x - L)
    yb2 = lambda x: yl2.value() + mrow * (x - L)
    polys = []
    for j in range(n_seg):
        a, b = xs_u[2 * j], xs_u[2 * j + 1]
        c, dd = xs_d[2 * j], xs_d[2 * j + 1]
        polys.append([(a, T), (b, T), (dd, yb(dd)), (c, yb(c))])
    # 下段は1コマ：段の境の下から下端まで
    polys.append([(L, yb2(L)), (R, yb2(R)), (R, B), (L, B)])
    # 垂直な余白の実測
    meas = []
    for j, k in enumerate(ks):
        # 左の線上の1点と右の線の距離
        p0 = (pl_u[j].value(), T); p1 = (pl_d[j].value(), ybound(pl_d[j]).value())
        q0 = (pr_u[j].value(), T)
        vx, vy = p1[0] - p0[0], p1[1] - p0[1]
        n_ = math.hypot(vx, vy)
        dist = abs((q0[0] - p0[0]) * vy - (q0[1] - p0[1]) * vx) / n_
        meas.append(round(dist, 3))
    # 段の境と下段の間の垂直距離
    vd = (yl2.value() - yl.value()) / math.sqrt(1 + mrow ** 2)
    return polys, meas, round(vd, 3), [round(math.degrees(math.atan(k)), 1) for k in ks]

polys, meas, vd, angs = slanted([0.35, -0.2], 0.04)
result['D_diagonal'] = {
    '表せた': '区切りの角度を定数にすれば、斜めの区切り・斜めの段の境・台形は線形制約（kiwisolver）で表せる。',
    '垂直な余白の実測mm（指定3）': meas, '段の境と下段の垂直距離mm（指定3）': vd, '区切りの角度度': angs,
    '表せない': ['角度を変数にした制約（余白の補正 sqrt(1+k^2) が非線形）', 'コマの面積の指定（幅×高さ）', '幅と高さの積の比'],
    '表せる': ['幅=定数×高さ（縦横比の固定）', '角度が定数の斜め区切り', '傾きが定数の段の境'],
}
fig_items.append(([], 'D 斜めの区切り(台形)・斜めの段の境\n垂直な余白は定数3mm', 1, polys, None))

# E 時間
def time_it(fn, n=300):
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return round((time.perf_counter() - t0) / n * 1000, 3)
result['E_time_ms_per_solve'] = {
    '基本3段7コマ（構築+解く）': time_it(lambda: Page(BASE)),
    '断ち切り付き7コマ': time_it(lambda: Page(rows_b)),
    '見開き（コマ数10）': time_it(lambda: Page(rows_s)),
    '固定1つ追加': time_it(lambda: Page(BASE, pin=((1, 0, 0), 100.0))),
    '8段x4コマ=32コマ': time_it(lambda: Page([row(1, [1, 1, 1, 1]) for _ in range(8)]), 100),
}
# 追従の速さ：既存の解に編集変数で値を入れ直す（ドラッグ中の更新）
s = Solver(); xs = Variable('xs')
ep = Page(BASE)
q = [q for q in ep.pan if q[:3] == (1, 0, 0)][0]
ep.s.addEditVariable(q[4], STRONG)
def drag():
    for v in (95, 96, 97, 98):
        ep.s.suggestValue(q[4], v); ep.s.updateVariables()
result['E_time_ms_per_solve']['ドラッグ中の再計算（編集変数・1回）'] = round(time_it(drag, 500) / 4, 4)

# 一覧画像
n = len(fig_items)
cols = 4
rows_n = math.ceil(n / cols)
fig, axes = plt.subplots(rows_n, cols, figsize=(cols * 4.2, rows_n * 5.2))
axes = axes.flatten()
for ax in axes:
    ax.axis('off')
for ax, (rects, title, pages, polys, hl) in zip(axes, fig_items):
    if pages == 2:
        ax.set_position(ax.get_position())
    show(ax, rects, title, pages, polys, hl)
fig.tight_layout()
fig.savefig(OUT / 'sheet.png', dpi=80)
(OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=1))
