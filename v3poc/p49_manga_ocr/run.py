"""P49 manga-ocr（日本語の文字の読み取り）を CPU で動かして、読める範囲と使い方の条件を確かめる（設計 3.1 の取り込み・検出器の候補）。
確かめること:
1. 入るか・動くか。1切り抜きあたりの CPU 時間、モデルの読み込み時間、メモリ。ライセンス（コードと重みの本文を読んだ結果を result.json に残す）。
2. 精度（文字誤り率 CER と完全一致率）。材料は Pillow で自分で描く（正解が分かる）。条件を変える:
   縦書き・横書き、フォント14種（ゴシック・明朝・手書き風・ポップ・極太など）、文字数（短い台詞〜3行）、句読点・「！？」・「…」・長音・小書き文字、
   ルビ付き、吹き出しの中（白地）、絵の上（灰色の網点・斜線の上に縁取り文字）、小さい文字（高さ12〜48px）、
   描き文字の擬音に近いもの（傾き・大きさの不揃い）、切り抜きの余白（ぴったり〜広い）、文字の無い入力。
3. 1ページに複数の吹き出しがある絵をそのまま渡したときの振る舞い（前処理が 224x224 に縮めるので、ページ全体では読めないはず）と、
   吹き出しごとに切り抜いたときの差。
CER の正解側にも manga-ocr と同じ後処理（空白除去・「…」を「...」にして全角化）をかける。後処理の差は誤りに数えない。
使い方: 仮想環境の python で python run.py（モデルは初回に Hugging Face から約440MBを取る）。
フォント: リポジトリの font/ ・システムの IPAGothic ・Noto Serif CJK JP（fonts-noto-cjk の deb から取り出したもの。下の NOTO_SERIF）。
結果: out/result.json（全サンプルと集計）、out/sheet.png（一覧画像）、out/page.png（複数吹き出しのページ）。"""
import json
import math
import pathlib
import platform
import random
import resource
import statistics
import sys
import time
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
REPO = HERE.parents[1]
FONT_DIR = REPO / 'font'
IPA_GOTHIC = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'
NOTO_SERIF = '/tmp/claude-0/-home-user-manga-editor-desu/fa704f96-c74d-4d28-a8d6-2b724e85a763/scratchpad/fonts_dl/x/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc'

# 名前: (パス, 種類)
FONTS = {
    'IPAゴシック': (IPA_GOTHIC, 'ゴシック'),
    'NotoSerifJP': (NOTO_SERIF, '明朝'),
    'KleeOne': (str(FONT_DIR / 'Klee_One/KleeOne-Regular.ttf'), '教科書体風'),
    '851H-kktt': (str(FONT_DIR / '851H-kktt_004.ttf'), '手書き風'),
    'OhisamaFont': (str(FONT_DIR / 'OhisamaFont11/OhisamaFont11.ttf'), '手書き風'),
    'ChalkJP': (str(FONT_DIR / 'ChalkJP_3/Chalk-JP.otf'), '手書き風(チョーク)'),
    '851YOWAKU': (str(FONT_DIR / '851CHIKARA-YOWAKU_002.ttf'), '手書き風(細)'),
    '851MkPOP': (str(FONT_DIR / '851MkPOP_101/851MkPOP_101.ttf'), 'ポップ'),
    'DokiDoki': (str(FONT_DIR / 'DokiDokiFont2/DokiDokiFantasia.otf'), 'ポップ'),
    '851DZUYOKU-B': (str(FONT_DIR / '851CHIKARA-DZUYOKU_kanaB_004.ttf'), '極太'),
    '851DZUYOKU-A': (str(FONT_DIR / '851CHIKARA-DZUYOKU_kanaA_004/851CHIKARA-DZUYOKU_kanaA_004.ttf'), '極太'),
    'RampartOne': (str(FONT_DIR / 'Rampart_One/RampartOne-Regular.ttf'), '極太(縁飾り)'),
    'DotGothic16': (str(FONT_DIR / 'DotGothic16/DotGothic16-Regular.ttf'), 'ドット'),
    'TrainOne': (str(FONT_DIR / 'Train_One/TrainOne-Regular.ttf'), '装飾'),
}

# 台詞（自作）。\n は行の区切り。
LINES = [
    'うそでしょ', '待って！', 'どうして？', 'ありがとう', '行こう', 'あれ…？', 'ぼくがやる！', 'だめだよ',
    'ちょっと待ってよ！！', 'ほんとにいいの？', 'コーヒーを、ください。', 'しょうがないなぁ…', 'ふぅ…やっと着いた', 'うわあああ！？',
    'ゆっくり、ゆーっくりね', 'きゃっ、ごめんなさい', 'ちゃんと食べなさいよ', 'ニュースでやってたよ', 'ウォーターフロント', 'ジュースをこぼしちゃった',
    '魔王を倒すまで帰れない', '隣の席の転校生', '学園祭の準備、間に合うかな', '昨日の夕飯は何だった？', '絶対に許さない！', '世界を救うのは君だ',
    '今日はもう\n帰ろうか', 'お前が来るなんて\n思わなかったよ', '約束は守る。\nだから信じてほしい', 'もう少しだけ\nここにいさせて',
    '夜の学校は\nなんだか怖いね', 'まさか、あの人が\n犯人だったなんて…', 'ねえ、聞いてる？\nちゃんと答えてよ！',
    'あの日の空は\n今でも忘れない\nずっと覚えてる', '明日の朝一番に\n駅前で待ち合わせよう\n遅れないでね', 'さっきの話だけど\nやっぱり断ろうと\n思うんだ',
    '雨が降りそうだから\n傘を持っていきなさい\n風邪をひくわよ', 'この先は\n立ち入り禁止だ\n引き返せ', '君がいない朝は\nこんなに静かなのかと\n初めて知った',
    '窓の外を見て\n私は小さく\n手を振った',
]
# ルビ: (本文, [(開始, 長さ, ルビ)])
RUBY = [
    ('運命の出会い', [(0, 2, 'うんめい'), (3, 2, 'であ')]),
    ('秘密を知った', [(0, 2, 'ひみつ')]),
    ('魔法使いの弟子', [(0, 2, 'まほう'), (2, 1, 'つか'), (5, 2, 'でし')]),
    ('本気で行く', [(0, 2, 'マジ')]),
    ('最強の剣を持つ者', [(0, 2, 'さいきょう'), (3, 1, 'けん'), (5, 1, 'も'), (7, 1, 'もの')]),
    ('絶対に許さない', [(0, 2, 'ぜったい'), (3, 1, 'ゆる')]),
]
SFX = ['ドカーン！', 'ゴゴゴゴ', 'バシッ！', 'ピンポーン', 'ざわざわ', 'ガタガタ', 'シュッ', 'ドキドキ', 'ズバァッ！', 'ばーん', 'キィィーッ', 'ぐらぐら']
SFX_FONTS = ['RampartOne', '851DZUYOKU-B', '851MkPOP']
SIZES = [12, 16, 20, 24, 32, 48]
BASE_SIZE = 28
MARGINS = {'ぴったり': 0.1, '標準': 0.6, '広い': 2.0, '非常に広い': 4.0}

V_ROT = set('ー〜～―-…')          # 縦書きでは90度回す
V_PUNCT = set('、。，．')           # 縦書きでは右上に寄せる
V_SMALL = set('ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ')  # 縦書きでは少し右上


@lru_cache(maxsize=None)
def get_font(path, size):
    return ImageFont.truetype(path, max(4, int(round(size))), index=0)


def glyph_tile(ch, fpath, size, fill, edge, sw, angle=0.0):
    """1文字の透明タイル。中心に描いて角度を付ける。"""
    T = int(size * 3.2)
    im = Image.new('RGBA', (T, T), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((T / 2, T / 2), ch, font=get_font(fpath, size), fill=fill, anchor='mm', stroke_width=sw, stroke_fill=edge)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC)
    return im


def check_glyphs(fpath, text):
    """字形が無い文字を返す（豆腐を読ませないため）。"""
    from fontTools.ttLib import TTFont
    f = TTFont(fpath, fontNumber=0) if fpath.endswith('.ttc') else TTFont(fpath)
    cm = f.getBestCmap()
    return sorted({c for c in text if c != '\n' and ord(c) not in cm})


def render_text(text, fpath, size, vertical, fill=(0, 0, 0, 255), edge=None, sw=0, ruby=None, margin=0.6,
                jitter=None, rng=None, tilt=0.0):
    """文字だけの透明レイヤーを返す。ルビは1行のときだけ。jitter は擬音向けの文字ごとの傾き・大きさの揺れ。"""
    lines = text.split('\n')
    n_l, n_c = len(lines), max(len(l) for l in lines)
    pitch = size * 1.45                       # 行（列）の間隔
    rsz = size * 0.45
    rub_room = size * 0.6 if ruby else 0
    if vertical:
        tw, th = n_l * pitch + rub_room, n_c * size
    else:
        tw, th = n_c * size, n_l * pitch + rub_room
    pad = size * margin + (sw or 0)
    W, H = int(math.ceil(tw + 2 * pad)), int(math.ceil(th + 2 * pad))
    B = int(size * 2.6)                       # タイルが端からはみ出しても貼れるように、大きい透明の枠を付けて最後に切る
    lay = Image.new('RGBA', (W + 2 * B, H + 2 * B), (0, 0, 0, 0))

    def put(ch, cx, cy, fs, ang=0.0, shift=(0, 0)):
        t = glyph_tile(ch, fpath, fs, fill, edge, sw, ang)
        lay.alpha_composite(t, (int(round(cx + shift[0] - t.width / 2)) + B, int(round(cy + shift[1] - t.height / 2)) + B))

    base_pos = []                             # ルビ用: 各文字の中心
    for li, line in enumerate(lines):
        row = []
        for ci, ch in enumerate(line):
            if vertical:
                cx = pad + (n_l - li - 0.5) * pitch       # 右の列から
                cy = pad + (ci + 0.5) * size
            else:
                cx = pad + (ci + 0.5) * size
                cy = pad + rub_room + (li + 0.5) * pitch
            ang, fs, sh = 0.0, size, [0.0, 0.0]
            if vertical:
                if ch in V_ROT:
                    ang = -90.0
                elif ch in V_PUNCT:
                    sh = [0.5 * size, -0.5 * size]
                elif ch in V_SMALL:
                    sh = [0.12 * size, -0.12 * size]
            if jitter:
                ang += rng.gauss(0, jitter['ang'])
                fs = size * rng.uniform(*jitter['scale'])
                sh[0] += rng.uniform(-1, 1) * jitter['pos'] * size
                sh[1] += rng.uniform(-1, 1) * jitter['pos'] * size
            put(ch, cx, cy, fs, ang, tuple(sh))
            row.append((cx, cy))
        base_pos.append(row)
    if ruby:
        row = base_pos[0]
        for (st, ln, rb) in ruby:
            c0, c1 = row[st], row[st + ln - 1]
            mid_x, mid_y = (c0[0] + c1[0]) / 2, (c0[1] + c1[1]) / 2
            for k, ch in enumerate(rb):
                off = (k - (len(rb) - 1) / 2) * rsz
                if vertical:
                    put(ch, mid_x + size * 0.5 + rsz * 0.5, mid_y + off, rsz)
                else:
                    put(ch, mid_x + off, mid_y - size * 0.5 - rsz * 0.5, rsz)
    lay = lay.crop((B, B, B + W, B + H))
    if tilt:
        lay = lay.rotate(tilt, resample=Image.BICUBIC, expand=True)
    return lay


def bg_pattern(kind, W, H, size):
    """背景。white / dots（網点）/ hatch（斜線）。"""
    if kind == 'white':
        return Image.new('RGB', (W, H), 'white')
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    if kind == 'dots':
        p = max(3.0, size / 6)
        u, v = (x + y) / math.sqrt(2), (x - y) / math.sqrt(2)
        val = np.cos(2 * math.pi * u / p) * np.cos(2 * math.pi * v / p)
        a = np.where(val > 0.25, 40, 255)
    elif kind == 'hatch':
        p = max(5.0, size / 3.5)
        lw = max(1.0, p / 4)
        a = np.where(((x + y) % p) < lw, 40, 255)
    else:
        raise ValueError(kind)
    return Image.fromarray(a.astype(np.uint8), 'L').convert('RGB')


def compose(lay, bg_kind, size):
    bg = bg_pattern(bg_kind, lay.width, lay.height, size)
    bg.paste(lay, mask=lay.getchannel('A'))
    return bg


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def summarize(recs):
    if not recs:
        return None
    edits = sum(r['edits'] for r in recs)
    ln = sum(len(r['ref']) for r in recs)
    return {'n': len(recs), 'cer': round(edits / ln, 4), 'cer_mean': round(statistics.mean(r['cer'] for r in recs), 4),
            'exact': sum(r['exact'] for r in recs), 'exact_rate': round(sum(r['exact'] for r in recs) / len(recs), 3),
            'sec_mean': round(statistics.mean(r['sec'] for r in recs), 3)}


def by(recs, key):
    keys = sorted({key(r) for r in recs}, key=str)
    return {str(k): summarize([r for r in recs if key(r) == k]) for k in keys}


def main():
    OUT.mkdir(exist_ok=True)
    import torch
    import transformers
    import manga_ocr
    from importlib.metadata import version
    from manga_ocr.ocr import post_process
    t0 = time.perf_counter()
    mocr = manga_ocr.MangaOcr(force_cpu=True)
    load_sec = time.perf_counter() - t0

    recs, imgs = [], []

    def run(cond, img, ref, **meta):
        """1枚読む。時間は __call__ だけ（前処理・生成・復号を含む）。失敗は失敗として記録する。"""
        ref_n = post_process(ref.replace('\n', ''))
        err = None
        secs, same = [], True
        for k in range(3):   # 外部の負荷で時間がぶれるので3回測って最小を使う（初回の値も残す）。出力が毎回同じかも見る
            t = time.perf_counter()
            try:
                h = mocr(img)
            except Exception as ex:  # 読み取りの失敗を記録する（代わりの処理はしない）
                h, err = '', repr(ex)
            secs.append(time.perf_counter() - t)
            if k == 0:
                hyp = h
            elif h != hyp:
                same = False
        sec = min(secs)
        e = lev(ref_n, hyp)
        r = dict(cond=cond, ref=ref_n, hyp=hyp, edits=e, cer=round(e / max(1, len(ref_n)), 4), exact=int(hyp == ref_n),
                 sec=round(sec, 3), sec_first=round(secs[0], 3), same3=same, w=img.width, h=img.height, err=err, **meta)
        recs.append(r)
        imgs.append(img)
        return r

    # --- 1. 基準: 全台詞 x 縦横、IPAゴシック、白地、標準の余白
    for vi, vertical in enumerate((False, True)):
        for i, t in enumerate(LINES):
            lay = render_text(t, IPA_GOTHIC, BASE_SIZE, vertical)
            nl = t.count('\n') + 1
            run('base', compose(lay, 'white', BASE_SIZE), t, dir='縦' if vertical else '横', font='IPAゴシック', size=BASE_SIZE,
                line_id=i, nlines=nl, nchar=len(t.replace('\n', '')),
                feat=[k for k, s in (('!?', '！？!?'), ('…', '…'), ('、。', '、。'), ('長音', 'ー'), ('小書き', 'ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ')) if any(c in t for c in s)])

    # --- 2. フォント: 8台詞 x 縦横 x 14フォント
    font_ids = list(range(0, len(LINES), 5))
    missing = {}
    for fname, (fp, kind) in FONTS.items():
        for vertical in (False, True):
            for i in font_ids:
                t = LINES[i]
                miss = check_glyphs(fp, t)
                if miss:
                    missing.setdefault(fname, []).append((i, miss))
                    continue
                lay = render_text(t, fp, BASE_SIZE, vertical)
                run('font', compose(lay, 'white', BASE_SIZE), t, dir='縦' if vertical else '横', font=fname, fkind=kind, size=BASE_SIZE, line_id=i)

    # --- 3. 背景: 12台詞 x 縦横 x 4（網点・斜線 x 黒字に白縁・白字に黒縁）
    sub12 = [LINES[i] for i in range(0, 36, 3)]
    sub12_ids = list(range(0, 36, 3))
    bgs = [('dots', 'k', '網点・黒字白縁'), ('hatch', 'k', '斜線・黒字白縁'), ('dots', 'w', '網点・白字黒縁'), ('hatch', 'w', '斜線・白字黒縁')]
    for bg, mode, name in bgs:
        for vertical in (False, True):
            for i, t in zip(sub12_ids, sub12):
                sw = max(2, round(BASE_SIZE * 0.12))
                fill, edge = ((0, 0, 0, 255), (255, 255, 255, 255)) if mode == 'k' else ((255, 255, 255, 255), (0, 0, 0, 255))
                lay = render_text(t, IPA_GOTHIC, BASE_SIZE, vertical, fill=fill, edge=edge, sw=sw)
                run('bg', compose(lay, bg, BASE_SIZE), t, dir='縦' if vertical else '横', bgname=name, size=BASE_SIZE, line_id=i)

    # --- 4. 文字の大きさ: 12台詞 x 縦横 x 6サイズ（白地、IPAゴシック）
    for sz in SIZES:
        for vertical in (False, True):
            for i, t in zip(sub12_ids, sub12):
                lay = render_text(t, IPA_GOTHIC, sz, vertical)
                run('size', compose(lay, 'white', sz), t, dir='縦' if vertical else '横', size=sz, line_id=i)

    # --- 5. 擬音に近いもの: 12語 x 3フォント x 縦横。文字ごとに傾き・大きさ・位置を揺らし、全体も傾ける。偶数番は網点の上に白縁
    rng = random.Random(49)
    for fname in SFX_FONTS:
        fp = FONTS[fname][0]
        for vertical in (False, True):
            for k, w in enumerate(SFX):
                tilt = rng.uniform(-25, 25)
                edge_mode = k % 2 == 0
                sw = round(48 * 0.12) if edge_mode else 0
                lay = render_text(w, fp, 48, vertical, fill=(0, 0, 0, 255), edge=(255, 255, 255, 255) if edge_mode else None, sw=sw,
                                  jitter={'ang': 8, 'scale': (0.8, 1.3), 'pos': 0.1}, rng=rng, tilt=tilt)
                run('sfx', compose(lay, 'dots' if edge_mode else 'white', 48), w, dir='縦' if vertical else '横', font=fname, size=48,
                    tilt=round(tilt, 1), on_tone=edge_mode)

    # --- 6. ルビ: 6語 x 縦横 x 2フォント
    for fname in ('IPAゴシック', 'NotoSerifJP'):
        fp = FONTS[fname][0]
        for vertical in (False, True):
            for base, rb in RUBY:
                lay = render_text(base, fp, BASE_SIZE, vertical, ruby=rb)
                r = run('ruby', compose(lay, 'white', BASE_SIZE), base, dir='縦' if vertical else '横', font=fname, size=BASE_SIZE)
                r['ruby_leak'] = any(x[2] in r['hyp'] for x in rb)

    # --- 7. 切り抜きの余白: 8台詞 x 縦横 x 3（標準は基準と同じ）
    for mname, m in MARGINS.items():
        if mname == '標準':
            continue
        for vertical in (False, True):
            for i in font_ids:
                t = LINES[i]
                lay = render_text(t, IPA_GOTHIC, BASE_SIZE, vertical, margin=m)
                run('margin', compose(lay, 'white', BASE_SIZE), t, dir='縦' if vertical else '横', margin=mname, size=BASE_SIZE, line_id=i)

    # --- 8. 文字の無い入力（正解は空）。何かを作り出すか
    rng2 = random.Random(7)
    blanks = []
    for shape, (w, h) in (('正方形', (200, 200)), ('縦長', (150, 400))):
        blanks.append((f'白地{shape}', Image.new('RGB', (w, h), 'white')))
        blanks.append((f'網点{shape}', bg_pattern('dots', w, h, 28)))
        blanks.append((f'斜線{shape}', bg_pattern('hatch', w, h, 28)))
        im = Image.new('RGB', (w, h), 'white')
        d = ImageDraw.Draw(im)
        for _ in range(14):
            d.line([(rng2.randint(0, w), rng2.randint(0, h)), (rng2.randint(0, w), rng2.randint(0, h))], fill=0, width=rng2.randint(1, 4))
        d.ellipse([w * 0.3, h * 0.3, w * 0.7, h * 0.5], outline=0, width=3)
        blanks.append((f'線の絵{shape}', im))
    for name, im in blanks:
        r = run('blank', im, '', dir='-', bgname=name)
        r['cer'] = None if r['hyp'] else 0.0   # 正解が空なので CER は定義しない
        r['exact'] = int(r['hyp'] == '')

    # --- 9. 1ページに複数の吹き出し
    page, boxes = make_page()
    page.save(OUT / 'page.png')
    ref_all = ''.join(post_process(b['text'].replace('\n', '')) for b in boxes)   # 読む順（右上から）に並べた正解
    r = run('page', page, ref_all, dir='-', kind='ページ全体', balloons=len(boxes), size=f'{page.width}x{page.height}')
    ovl = lambda ref, hyp: round(sum(min(ref.count(c), hyp.count(c)) for c in set(ref)) / max(1, len(ref)), 3)   # 文字の重なり（順序を問わない）
    r['char_overlap'] = ovl(r['ref'], r['hyp'])
    # 吹き出しごとの切り抜き（正解の枠に余白を足したもの）
    for b in boxes:
        x0, y0, x1, y1 = b['box']
        m = 12
        crop = page.crop((max(0, x0 - m), max(0, y0 - m), min(page.width, x1 + m), min(page.height, y1 + m)))
        r = run('page', crop, b['text'], dir='縦', kind='吹き出し切り抜き', balloons=1, size=f'{crop.width}x{crop.height}')
        r['char_overlap'] = ovl(r['ref'], r['hyp'])
    # 隣り合う2つ・3つをまとめた切り抜き
    order = sorted(range(len(boxes)), key=lambda k: (-boxes[k]['box'][2]))   # 右の吹き出しから
    for grp_name, idxs in (('隣り合う2つ', [order[0], order[1]]), ('3つ', [order[0], order[1], order[2]])):
        xs = [boxes[k]['box'] for k in idxs]
        x0, y0, x1, y1 = min(b[0] for b in xs), min(b[1] for b in xs), max(b[2] for b in xs), max(b[3] for b in xs)
        crop = page.crop((max(0, x0 - 12), max(0, y0 - 12), min(page.width, x1 + 12), min(page.height, y1 + 12)))
        # 正解は右の吹き出しから読む順
        ref = ''.join(boxes[k]['text'].replace('\n', '') for k in sorted(idxs, key=lambda k: -boxes[k]['box'][2]))
        r = run('page', crop, ref, dir='縦', kind='まとめ切り抜き' + grp_name, balloons=len(idxs), size=f'{crop.width}x{crop.height}')
        r['char_overlap'] = ovl(r['ref'], r['hyp'])

    # --- 集計
    text_recs = [r for r in recs if r['cond'] not in ('blank', 'page')]
    secs = [r['sec'] for r in recs]  # 最小値
    nch = [(len(r['ref']), r['sec']) for r in recs if r['cond'] in ('base',)]
    res = {
        'env': {
            'python': sys.version.split()[0], 'platform': platform.platform(), 'cpu_count': __import__('os').cpu_count(), 'loadavg_end': __import__('os').getloadavg(),
            'torch': version('torch'), 'transformers': version('transformers'), 'manga_ocr': version('manga-ocr'),
            'torch_threads': torch.get_num_threads(), 'device': 'cpu', 'model_load_sec': round(load_sec, 1),
            'peak_rss_mb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
            'preprocess': '画像を灰色にして 224x224 に縮める（縦横比を保たない）。ViTImageProcessor size=224, resample=2, 平均0.5・分散0.5',
            'generate_max_length': 300,
        },
        'license': LICENSE,
        'timing': {
            '方法': '1切り抜きを3回読んだ最小値(sec)。初回値は sec_first', 'nondeterministic': sum(not r['same3'] for r in recs),
            'first_median': round(statistics.median(r['sec_first'] for r in recs), 3),
            'n': len(secs), 'mean': round(statistics.mean(secs), 3), 'median': round(statistics.median(secs), 3),
            'p95': round(sorted(secs)[int(len(secs) * 0.95)], 3), 'max': max(secs),
            'by_ref_len': {k: round(statistics.mean(s for l, s in nch if lo <= l <= hi), 3) for k, (lo, hi) in {'1-5字': (1, 5), '6-10字': (6, 10), '11-15字': (11, 15), '16-25字': (16, 25), '26字以上': (26, 99)}.items() if any(lo <= l <= hi for l, _ in nch)},
        },
        'overall_text': summarize(text_recs),
        'base': {
            'by_dir': by([r for r in recs if r['cond'] == 'base'], lambda r: r['dir']),
            'by_nlines_dir': by([r for r in recs if r['cond'] == 'base'], lambda r: (r['nlines'], r['dir'])),
            'by_feature': {f: summarize([r for r in recs if r['cond'] == 'base' and f in r['feat']]) for f in ('!?', '…', '、。', '長音', '小書き')},
        },
        'font': {'by_font_dir': by([r for r in recs if r['cond'] == 'font'], lambda r: (r['font'], r['dir'])),
                 'by_font': by([r for r in recs if r['cond'] == 'font'], lambda r: r['font']),
                 'by_dir': by([r for r in recs if r['cond'] == 'font'], lambda r: r['dir']),
                 'glyph_missing_skipped': {k: v for k, v in missing.items()}},
        'bg': {'by_bg_dir': by([r for r in recs if r['cond'] == 'bg'], lambda r: (r['bgname'], r['dir'])),
               'by_bg': by([r for r in recs if r['cond'] == 'bg'], lambda r: r['bgname']),
               'white_same_lines_base': summarize([r for r in recs if r['cond'] == 'base' and r['line_id'] in sub12_ids])},
        'size': {'by_size_dir': by([r for r in recs if r['cond'] == 'size'], lambda r: (r['size'], r['dir'])),
                 'by_size': by([r for r in recs if r['cond'] == 'size'], lambda r: r['size'])},
        'sfx': {'by_font': by([r for r in recs if r['cond'] == 'sfx'], lambda r: r['font']),
                'by_dir': by([r for r in recs if r['cond'] == 'sfx'], lambda r: r['dir']),
                'by_on_tone': by([r for r in recs if r['cond'] == 'sfx'], lambda r: r['on_tone'])},
        'ruby': {'by_dir_font': by([r for r in recs if r['cond'] == 'ruby'], lambda r: (r['dir'], r['font'])),
                 'overall': summarize([r for r in recs if r['cond'] == 'ruby']),
                 'leak': sum(r['ruby_leak'] for r in recs if r['cond'] == 'ruby')},
        'margin': {'by_margin_dir': by([r for r in recs if r['cond'] == 'margin'] + [dict(r, margin='標準') for r in recs if r['cond'] == 'base' and r['line_id'] in font_ids],
                                      lambda r: (r['margin'], r['dir']))},
        'blank': [{'name': r['bgname'], 'size': f"{r['w']}x{r['h']}", 'hyp': r['hyp']} for r in recs if r['cond'] == 'blank'],
        'page': [{k: r[k] for k in ('kind', 'balloons', 'size', 'ref', 'hyp', 'cer', 'exact', 'char_overlap', 'sec')} for r in recs if r['cond'] == 'page'],
        'samples': [{k: v for k, v in r.items()} for r in recs],
    }
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    make_sheet(recs, imgs)
    print(json.dumps({k: res[k] for k in ('env', 'timing', 'overall_text')}, ensure_ascii=False, indent=1))


LICENSE = {
    '確認日': '2026-10-08',
    'コード': {'リポジトリ': 'kha-white/manga-ocr', 'ファイル': 'LICENSE', 'URL': 'https://raw.githubusercontent.com/kha-white/manga-ocr/master/LICENSE',
              '本文': 'Apache License Version 2.0, January 2004（全文。Apache-2.0 の標準の本文）'},
    '重み': {'リポジトリ': 'kha-white/manga-ocr-base（Hugging Face）', 'URL': 'https://huggingface.co/kha-white/manga-ocr-base/raw/main/README.md',
            'モデルカードの宣言': 'license: apache-2.0 / datasets: manga109s',
            'ファイル一覧': '.gitattributes README.md config.json preprocessor_config.json pytorch_model.bin special_tokens_map.json tokenizer_config.json vocab.txt（LICENSE ファイルは無い。宣言はモデルカードだけ）'},
    '学習データ': {'名前': 'Manga109-s（モデルカードの datasets 欄）', 'URL': 'http://www.manga109.org/en/download_s.html',
               '本文の要旨': 'Manga109 は学術・非営利が条件。109巻のうち87巻は商用利用が新たに承認され、その部分を Manga109-s と呼ぶ'},
    '未検証': '重みがManga109-sの条件を引き継ぐかどうか。モデルカードはApache-2.0とだけ書く。学習に使った別のデータ（CC-100、合成画像のフォント）の条件はREADMEに名前が出るだけで読んでいない',
    '依存': 'pip の METADATA で確認したのは manga-ocr の License: Apache License のみ。torch・transformers・fugashi・unidic-lite・jaconv の各ライセンスは読んでいない（未検証）',
}


def make_page():
    """複数の吹き出しがあるページ。コムの枠・網点・線画風のノイズ・縦書きの吹き出し5つ。"""
    W, H = 900, 1300
    pg = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(pg)
    d.rectangle([30, 30, W - 30, 620], outline=0, width=4)
    d.rectangle([30, 660, 470, H - 30], outline=0, width=4)
    d.rectangle([500, 660, W - 30, H - 30], outline=0, width=4)
    dots = bg_pattern('dots', 440, 620, 28)
    pg.paste(dots.crop((0, 0, 436, 604)), (34, 664))
    rng = random.Random(3)
    for _ in range(25):                                # 線画風のノイズ
        x, y = rng.randint(60, W - 60), rng.randint(60, 600)
        d.line([(x, y), (x + rng.randint(-120, 120), y + rng.randint(-80, 80))], fill=0, width=rng.randint(1, 3))
    d.ellipse([320, 250, 580, 560], outline=0, width=3)
    texts = [('学園祭の準備、\n間に合うかな', (700, 60)), ('大丈夫、\n私が手伝うよ', (410, 70)), ('ありがとう', (110, 80)),
             ('絶対に許さない！', (330, 700)), ('世界を救うのは君だ', (650, 740))]
    sz = 26
    boxes = []
    for t, (x, y) in texts:
        lay = render_text(t, IPA_GOTHIC, sz, True, margin=0.9)
        tw, th = lay.size
        # 吹き出し（白い楕円）を敷く
        bal = Image.new('RGBA', (tw + 30, th + 30), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bal)
        bd.ellipse([0, 0, bal.width - 1, bal.height - 1], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)
        bal.alpha_composite(lay, (15, 15))
        pg.paste(bal, (x - bal.width // 2, y), mask=bal.getchannel('A'))
        boxes.append({'text': t, 'box': (x - bal.width // 2, y, x + bal.width // 2, y + bal.height)})
    # 読む順（右上→左下）に並べ替え: 上の段が先、同じ段では右が先
    boxes.sort(key=lambda b: (0 if b['box'][1] < 650 else 1, -b['box'][2]))
    return pg, boxes


def make_sheet(recs, imgs):
    """一覧画像: 条件ごとの行。各セルは画像・正解(正)・読み取り(読)。誤りは赤。"""
    cap = ImageFont.truetype(IPA_GOTHIC, 12)
    lab = ImageFont.truetype(IPA_GOTHIC, 14)
    CW, IH, CH = 200, 170, 78
    rows = []
    for cond, title in (('base', '基準'), ('font', 'フォント'), ('bg', '絵の上'), ('size', '小さい文字'), ('sfx', '擬音'), ('ruby', 'ルビ'),
                        ('margin', '余白'), ('blank', '文字なし'), ('page', 'ページ')):
        for d in ('横', '縦', '-'):
            idx = [i for i, r in enumerate(recs) if r['cond'] == cond and r['dir'] == d]
            if not idx:
                continue
            sub = [recs[i] for i in idx]
            s = summarize([r for r in sub if r['cer'] is not None]) if cond != 'blank' else None
            head = f"{title}{'' if d == '-' else '・' + d + '書き'}"
            if s:
                head += f"  CER {s['cer']*100:.1f}%  完全一致 {s['exact']}/{s['n']}"
            if cond == 'font':
                pick = idx[::max(1, len(idx) // 5)][:5]
            elif cond == 'page':
                pick = idx
            else:
                pick = idx[::max(1, len(idx) // 5)][:5]
            worst = sorted([i for i in idx if recs[i]['cer'] is not None and i not in pick], key=lambda i: -recs[i]['cer'])[:2]
            if cond == 'page':
                worst = []
            rows.append((head, pick + worst))
    ncol = max(len(p) for _, p in rows)
    W = ncol * CW + 10
    H = sum(IH + CH + 28 for _ in rows) + 10
    S = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(S)
    y = 6
    for head, picks in rows:
        dr.rectangle([0, y, W, y + 22], fill=(230, 235, 245))
        dr.text((6, y + 3), head, font=lab, fill=0)
        y += 26
        for c, i in enumerate(picks):
            r, im = recs[i], imgs[i]
            x = 5 + c * CW
            t = im.copy()
            t.thumbnail((CW - 8, IH - 4))
            S.paste(t, (x + 2, y + 2))
            dr.rectangle([x, y, x + CW - 4, y + IH + CH - 2], outline=(200, 200, 200))
            ok = r['exact']
            for k, (tag, txt, col) in enumerate((('正', r['ref'], (0, 0, 0)), ('読', r['hyp'] or '(空)', (0, 120, 0) if ok else (200, 0, 0)))):
                cur = f'{tag}:{txt}'
                per = 15
                for j in range(0, min(len(cur), per * 3), per):
                    dr.text((x + 3, y + IH + 2 + k * 38 + (j // per) * 12), cur[j:j + per], font=cap, fill=col)
        y += IH + CH
    S.save(OUT / 'sheet.png')


if __name__ == '__main__':
    main()
