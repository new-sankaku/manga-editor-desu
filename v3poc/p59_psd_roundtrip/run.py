"""P59 書き出した PSD を人が開いて直せるか・直したものがサーバーへ戻るか（一覧 5-14・5-12）。

問い:
  「PSD はほぼ完璧に動くか」を、人が開いて直せるか（画像も文字も）で確かめる。
  1. 使いやすさ: 2ページ（4コマ・5コマ）の層つき PSD を本番の書き出し
     （v3/server/src/v3server/print_export/layered_psd_request.py で依頼を組み、v3/psd_writer/write_layered_psd.js で書く）で作る。
     コマごとのグループ（背景・色（乗算、コマにより隠す）・トーン・線画）、コマ枠、人の手、フキダシ、写植（縦書きの文字層）、描き文字。
     GIMP 2.10.36・Krita 5.2.2 を画面なしで動かし、層の名前（日本語）・層とグループの数・開く時間・ファイルの大きさ・
     文字が文字として直せるか（文字の情報が残るか）・縦書きの画素が出るか（画素を付けない文字層も試す）・コマ枠とコマの絵が分かれているか、を測る。
  2. 戻し: 目印（PSD の層の id = lyid、名前の末尾の [目印]、層の時刻 shmd、文書の XMP）を付けた1ページ目を、
     GIMP（script-fu）と Krita（kritarunner の Python）で人の直しを真似て直し（線画の一部を塗る・名前を変える・見せる/隠す・
     コマのグループに層を足す・層を消す・写植の文字を変える）、PSD に保存する。
     psd-tools 1.21.0 と ag-psd 31.0.2 で読み戻し、どの目印が残るか、層ごとの画素の差で何が変わったか、足した層・消えた層、
     直した画素を正しいコマに正しい位置で「人の直した絵の新しい版」として戻せるかを確かめる。
  Photoshop・CLIP STUDIO PAINT はこの環境に無いので未検証。手順の数は人で測っていない（見積り）。
使い方: npm install（ag-psd 31.0.2・pngjs 7.0.0）→ python run.py（numpy・pillow・pydantic・psd-tools 1.21.0 が要る。gimp と kritarunner を使う。Krita は Qt の offscreen で動くので xvfb は要らない）。
結果は out/result.json（"summary" に要点）、一覧の画像は out/sheet_*.png。
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
OUT = HERE / 'out'
LAY = OUT / 'layers'
WORK = OUT / 'work'
for d in (OUT, LAY, WORK):
    d.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO / 'v3' / 'server' / 'src'))
from v3server.print_export.layered_psd_request import PageLayerSet, PsdLayer, TextInfo, build_page_psd_request, write_layered_psd  # noqa: E402
from psd_tools import PSDImage  # noqa: E402
import psd_tools  # noqa: E402

PROD_WRITER = REPO / 'v3' / 'psd_writer' / 'write_layered_psd.js'
W, H = 1240, 1754  # A4 を 150dpi にした大きさ（本番の入稿の解像度より小さい）
FONT = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'
FONT_NAME = 'IPAGothic'
FS = 34
ENV = {**os.environ, 'XDG_RUNTIME_DIR': '/tmp/runtime-root', 'QT_QPA_PLATFORM': 'offscreen', 'PYTHONPATH': str(HERE), 'LANG': 'C.UTF-8'}

# コマの範囲 (x0, y0, x1, y1)。台詞は (文, 縦書きの列の右上の x, y)。描き文字は (文, x, y)
PAGES = {
    1: {'panels': [(80, 80, 1160, 560), (630, 590, 1160, 1100), (80, 590, 600, 1100), (80, 1130, 1160, 1674)],
        'lines': {1: [('ここが\n新しい部屋？', 1080, 120), ('ひろいね', 300, 150)], 2: [('荷物は\nどこに置く？', 1100, 630)],
                  3: [('窓のそばが\nいいな', 540, 630)], 4: [('よし、\nはじめよう！', 1080, 1170)]},
        'sfx': [('ドン', 200, 1250)]},
    2: {'panels': [(630, 80, 1160, 520), (80, 80, 600, 520), (80, 550, 1160, 1040), (630, 1070, 1160, 1674), (80, 1070, 600, 1674)],
        'lines': {1: [('おなか\nすいた', 1100, 120)], 2: [('まだ\n十時だよ', 540, 120)], 3: [('じゃあ\nおやつ！', 1080, 590)],
                  4: [('それ\n私のだよ', 1100, 1110)], 5: [('えへへ', 540, 1110)]},
        'sfx': [('ガサッ', 300, 700)]},
}
# 人の直しの範囲（ページの座標）。gimp_tools.scm の edit と同じ値
PAINT_RECT = (700, 700, 160, 120)
ADD_RECT = (900, 820, 90, 70)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def save(arr, path):
    Image.fromarray(arr.astype(np.uint8), 'RGBA').save(path)
    return path


# ---------------------------------------------------------------- 絵を作る
def vertical_text(text, font):
    """縦書きの文字を描いた RGBA と大きさ。列は右から左。小さい仮名・句読点の位置の調整はしていない。"""
    cols = text.split('\n')
    step = FS + 6
    w = step * len(cols) + 8
    h = step * max(len(c) for c in cols) + 8
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for ci, col in enumerate(cols):
        x = w - 4 - step * (ci + 1) + 3
        for ri, ch in enumerate(col):
            d.text((x, 4 + ri * step), ch, font=font, fill=(0, 0, 0, 255))
    return np.asarray(im).copy()


def panel_art(rect, seed, color_hidden):
    rng = np.random.default_rng(seed)
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    yy, xx = np.mgrid[0:h, 0:w]
    bg = np.zeros((h, w, 4), np.uint8)
    g = (235 - 30 * yy / h).astype(np.uint8)
    bg[..., 0] = g; bg[..., 1] = g; bg[..., 2] = g; bg[..., 3] = 255
    im = Image.fromarray(bg, 'RGBA'); d = ImageDraw.Draw(im)
    for _ in range(6):  # 背景の線（窓や壁）
        a = int(rng.integers(0, w)); d.line([a, 0, a, h], fill=(170, 170, 170, 255), width=2)
    bg = np.asarray(im).copy()
    cx, cy, r = int(w * rng.uniform(.35, .65)), int(h * .38), int(min(w, h) * .14)
    col = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(col)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 205, 180, 255))
    d.rectangle([cx - r, cy + r, cx + r, min(h - 5, cy + 4 * r)], fill=(120, 170, 240, 255))
    color = np.asarray(col).copy()
    tone = np.zeros((h, w, 4), np.uint8)
    dots = ((xx % 6 - 3) ** 2 + (yy % 6 - 3) ** 2) < 4
    tone[..., 3] = (dots & (yy > h * .75)) * 255
    ln = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(ln)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 0, 0, 255), width=4)
    d.line([cx - r, cy + r, cx - r, cy + 4 * r], fill=(0, 0, 0, 255), width=4)
    d.line([cx + r, cy + r, cx + r, cy + 4 * r], fill=(0, 0, 0, 255), width=4)
    d.line([cx - r, cy + 2 * r, cx - 2 * r, cy + 3 * r], fill=(0, 0, 0, 255), width=4)  # 腕と手
    d.ellipse([cx - 2 * r - 12, cy + 3 * r - 12, cx - 2 * r + 12, cy + 3 * r + 12], outline=(0, 0, 0, 255), width=3)
    for _ in range(4):
        a, b = rng.integers(0, w, 2); d.line([a, h - 10, b, int(h * .8)], fill=(0, 0, 0, 255), width=2)
    line = np.asarray(ln).copy()
    return {'背景': bg, '色': color, 'トーン': tone, '線画': line}, color_hidden


def make_page(pno):
    """1ページ分の層の画像を作り、層の一覧（書き出しの依頼の元）と期待する合成を返す。"""
    P = PAGES[pno]
    d = LAY / f'p{pno}'; d.mkdir(exist_ok=True)
    font = ImageFont.truetype(FONT, FS)
    items = []  # 層の項目: dict(item, panel, role, name, png, left, top, arr(ページの大きさ), hidden, blend, text)

    def page_arr(a, left, top):
        full = np.zeros((H, W, 4), np.uint8)
        full[top:top + a.shape[0], left:left + a.shape[1]] = a
        return full

    frame = Image.new('RGBA', (W, H), (0, 0, 0, 0)); fd = ImageDraw.Draw(frame)
    for (x0, y0, x1, y1) in P['panels']:
        fd.rectangle([x0 - 3, y0 - 3, x1 + 2, y1 + 2], outline=(0, 0, 0, 255), width=6)
    frame = np.asarray(frame).copy()
    items.append(dict(item=f'p{pno}frame', panel=None, role='panel_frame', name='コマ枠', png=save(frame, d / 'frame.png'), left=0, top=0, arr=frame))
    for k, rect in enumerate(P['panels'], 1):
        arts, hid = panel_art(rect, pno * 10 + k, color_hidden=(k % 2 == 0))
        for role, a in arts.items():
            items.append(dict(item=f'p{pno}k{k}{ {"背景": "B", "色": "C", "トーン": "T", "線画": "L"}[role]}', panel=k, role=role, name=role,
                              png=save(a, d / f'k{k}_{role}.png'), left=rect[0], top=rect[1], arr=page_arr(a, rect[0], rect[1]),
                              hidden=(role == '色' and hid), blend='multiply' if role == '色' else 'normal'))
    hand = np.zeros((H, W, 4), np.uint8)
    items.append(dict(item=f'p{pno}hand', panel=None, role='human_hand', name='人の手', png=save(hand, d / 'hand.png'), left=0, top=0, arr=hand))
    bal = Image.new('RGBA', (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(bal)
    texts = []
    for k, lines in P['lines'].items():
        for i, (s, xr, yt) in enumerate(lines, 1):
            t = vertical_text(s, font)
            left, top = xr - t.shape[1], yt
            bd.ellipse([left - 30, top - 25, left + t.shape[1] + 30, top + t.shape[0] + 25], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)
            texts.append(dict(item=f'p{pno}k{k}s{i}', panel=k, role='text', name=f'コマ{k} 台詞{i}', png=save(t, d / f'text_k{k}_{i}.png'),
                              left=left, top=top, arr=page_arr(t, left, top),
                              text=dict(text=s.replace('\n', '\r'), orientation='vertical', font_name=FONT_NAME, font_size=FS, color_rgb=(0, 0, 0), x=xr, y=yt)))
    bal = np.asarray(bal).copy()
    items.append(dict(item=f'p{pno}balloon', panel=None, role='balloon', name='フキダシ', png=save(bal, d / 'balloon.png'), left=0, top=0, arr=bal))
    items += texts
    sf = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sf)
    big = ImageFont.truetype(FONT, 110)
    for s, x, y in P['sfx']:
        for i, ch in enumerate(s):
            sd.text((x, y + i * 115), ch, font=big, fill=(255, 255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0, 255))
    sf = np.asarray(sf).copy()
    items.append(dict(item=f'p{pno}sfx', panel=None, role='sfx', name='描き文字', png=save(sf, d / 'sfx.png'), left=0, top=0, arr=sf))
    for it in items:
        it.setdefault('hidden', False); it.setdefault('blend', 'normal'); it.setdefault('text', None)
    # 期待する合成（白い紙の上に下から重ねる。グループは全部 normal・不透明度1なので順に重ねるのと同じ）
    order = [items[0]] + [i for i in items if i['panel'] and i['role'] != 'text'] + [i for i in items if i['role'] == 'human_hand'] + \
            [i for i in items if i['role'] == 'balloon'] + texts + [items[-1]]
    b = np.ones((H, W, 3), np.float32)
    for it in order:
        if it['hidden']:
            continue
        a = it['arr'][..., 3:4].astype(np.float32) / 255
        cs = it['arr'][..., :3].astype(np.float32) / 255
        b = b * (1 - a) + (b * cs if it['blend'] == 'multiply' else cs) * a
    comp = (b * 255 + .5).astype(np.uint8)
    comp_png = d / 'composite.png'
    Image.fromarray(np.dstack([comp, np.full((H, W), 255, np.uint8)]), 'RGBA').save(comp_png)
    Image.fromarray(comp, 'RGB').save(OUT / f'expected_p{pno}.png')
    return items, comp_png, comp


def psd_layer(it, tag_mode, ids):
    """項目を本番の PsdLayer の形（辞書）にする。tag_mode なら名前の末尾に [目印]、id（lyid）と時刻を付ける。"""
    d = dict(name=it['name'] + (f' [{it["item"]}]' if tag_mode else ''), png_path=str(it['png']), hidden=it['hidden'],
             blend_mode=it['blend'], left=it['left'], top=it['top'])
    if it['text']:
        d['text'] = it['text']
    if tag_mode:
        d['id'] = ids[it['item']]
        d['timestamp'] = 1_700_000_000 + ids[it['item']]
    return d


def build_request(pno, items, comp_png, out_psd, tag_mode=False, text_pixels=True):
    """本番の build_page_psd_request で依頼を組む。tag_mode・text_pixels=False のときは、組んだ依頼に目印を足す・文字の画素を外す。"""
    ids = {}
    for n, it in enumerate(items, 101):
        ids[it['item']] = n
    group_ids = {}
    panels = sorted({i['panel'] for i in items if i['panel'] and i['role'] != 'text'})
    by = lambda role: [i for i in items if i['role'] == role]
    groups = []
    for k in panels:
        ch = [PsdLayer(**{kk: v for kk, v in psd_layer(i, False, ids).items()}) for i in items if i['panel'] == k and i['role'] != 'text']
        groups.append(PsdLayer(name=f'コマ{k}', children=ch))
    pls = PageLayerSet(
        panel_frame=PsdLayer(**psd_layer(by('panel_frame')[0], False, ids)),
        ai_art_by_panel=groups,
        hand_drawn=PsdLayer(**psd_layer(by('human_hand')[0], False, ids)),
        balloon=PsdLayer(**psd_layer(by('balloon')[0], False, ids)),
        typeset_texts=[PsdLayer(**{**psd_layer(i, False, ids), 'text': TextInfo(**i['text'])}) for i in by('text')],
        sfx=PsdLayer(**psd_layer(by('sfx')[0], False, ids)),
    )
    req = build_page_psd_request(W, H, comp_png, pls, out_psd)
    if tag_mode or not text_pixels:
        # 本番の依頼の層の並びはそのまま、項目と順に対応づけて目印を足す
        flat_items = [by('panel_frame')[0]] + [i for k in panels for i in items if i['panel'] == k and i['role'] != 'text'] + \
                     by('human_hand') + by('balloon') + by('text') + by('sfx')
        it_iter = iter(flat_items)
        gid = 900

        def walk(layers, parent_name):
            nonlocal gid
            for L in layers:
                if 'children' in L:
                    gid += 1
                    key = 'p%dg%s' % (pno, re.sub(r'\D', '', L['name']) or {'AIの絵': 'art', '写植': 'text'}.get(L['name'], L['name']))
                    if tag_mode:
                        L['name'] = f'{L["name"]} [{key}]'
                        L['id'] = gid
                        L['timestamp'] = 1_700_000_000 + gid
                    group_ids[key] = gid
                    walk(L['children'], L['name'])
                else:
                    it = next(it_iter)
                    if tag_mode:
                        L['name'] = f'{L["name"]} [{it["item"]}]'
                        L['id'] = ids[it['item']]
                        L['timestamp'] = 1_700_000_000 + ids[it['item']]
                    if not text_pixels and 'text' in L:
                        L.pop('png_path')
        walk(req['layers'], None)
        if tag_mode:
            m = json.dumps({'ids': ids, 'groups': group_ids}, ensure_ascii=False).replace('&', '&amp;').replace('<', '&lt;')
            req['xmp'] = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                          '<rdf:Description rdf:about="" xmlns:v3="https://example.invalid/v3/"><v3:layerMap>' + m +
                          '</v3:layerMap></rdf:Description></rdf:RDF></x:xmpmeta>')
    return req, ids, group_ids


def local_write(req):
    r = run(['node', str(HERE / 'write.js'), 'write'], input=json.dumps(req, ensure_ascii=False))
    if r.returncode != 0:
        raise RuntimeError('write.js が失敗: ' + r.stderr[-500:])
    return json.loads(r.stdout)


def agpsd_read(psd, name):
    j = WORK / f'agpsd_{name}.json'
    r = run(['node', str(HERE / 'write.js'), 'read', str(psd), str(j)])
    if r.returncode != 0:
        return {'error': r.stderr[-400:]}
    return json.loads(j.read_text())


# ---------------------------------------------------------------- psd-tools
def pt_read(psd_path):
    """psd-tools で読む。層ごとに道筋・種類・id・見せるか・合成モード・文字・ページの座標の画素。"""
    t0 = time.perf_counter()
    psd = PSDImage.open(psd_path)
    open_sec = time.perf_counter() - t0
    rows = []
    for L in psd.descendants():
        path, p = [], L
        while p is not None and p is not psd:
            path.insert(0, p.name); p = p.parent
        row = dict(path=path, name=L.name, kind=L.kind, layer_id=L.layer_id, visible=L.visible, opacity=L.opacity,
                   blend=str(L.blend_mode).split('.')[-1], bbox=list(L.bbox))
        if L.kind == 'type':
            row['text'] = L.text
            try:
                row['fonts'] = [str(f.get('Name')) for f in L.resource_dict['FontSet']]
            except Exception as e:  # 書体の情報が読めないときはその理由を残す
                row['fonts_error'] = repr(e)[:120]
        if L.kind not in ('group',):
            im = L.topil()
            full = np.zeros((H, W, 4), np.uint8)
            if im is not None:
                a = np.asarray(im.convert('RGBA'))
                x0, y0 = L.left, L.top
                xa, ya = max(0, x0), max(0, y0)
                xb, yb = min(W, x0 + a.shape[1]), min(H, y0 + a.shape[0])
                if xb > xa and yb > ya:
                    full[ya:yb, xa:xb] = a[ya - y0:yb - y0, xa - x0:xb - x0]
            row['_arr'] = full
            row['opaque_px'] = int((full[..., 3] > 0).sum())
        rows.append(row)
    return dict(open_sec=round(open_sec, 3), rows=rows)


def strip(rows):
    return [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows]


def tree_stats(rows):
    groups = [r for r in rows if r['kind'] == 'group']
    layers = [r for r in rows if r['kind'] != 'group']
    names = [r['name'] for r in rows]
    return dict(groups=len(groups), layers=len(layers), kinds={k: sum(1 for r in rows if r['kind'] == k) for k in sorted({r['kind'] for r in rows})},
                type_layers_with_text=sum(1 for r in rows if r.get('text')), duplicate_names=sorted({n for n in names if names.count(n) > 1}),
                names_with_replacement_char=[n for n in names if '�' in n or '?' in n])


# ---------------------------------------------------------------- GIMP・Krita
GIMP_LOAD = f'(load "{HERE}/gimp_tools.scm")'


def gimp(expr, timeout=600):
    t0 = time.perf_counter()
    # 書体を読み込ませる（-f を付けると GIMP の文字の層が作れない）。日本語の引数のため UTF-8 にする
    r = run(['gimp', '-i', '-d', '-b', expr, '-b', '(gimp-quit 0)'], timeout=timeout, env={**os.environ, 'LANG': 'C.UTF-8'})
    return r, time.perf_counter() - t0


_GIMP_BASE = None


def gimp_open_sec(psd):
    """GIMP が開くだけの時間（起動だけの時間を引く）。2回の小さい方。"""
    global _GIMP_BASE
    if _GIMP_BASE is None:
        _GIMP_BASE = min(gimp('(gimp-quit 0)')[1] for _ in range(2))
    base = _GIMP_BASE
    t = min(gimp(f'(let ((i (car (gimp-file-load RUN-NONINTERACTIVE "{psd}" "{psd}")))) (gimp-image-delete i))')[1] for _ in range(2))
    return round(t - base, 2), round(base, 2)


def parse_gimp_dump(txt):
    rows, ops, head = [], [], None
    for line in txt.read_text().splitlines():
        if line.startswith('("image"'):
            head = line
        elif line.startswith('("op"'):
            m = re.match(r'\("op" "([^"]+)" "([^"]+)"\)', line)
            ops.append({'op': m.group(1), 'result': m.group(2)})
        elif line.startswith('("text-content"'):
            rows[-1]['text_content'] = line
        else:
            m = re.match(r'\((\d+) "((?:[^"\\]|\\.)*)" "(\w+)" (\d) ([\d.]+) "?([\w-]+)"? (-?\d+) (-?\d+) (\d+) (\d+) (.*)\)$', line)
            if m:
                rows.append(dict(depth=int(m.group(1)), name=m.group(2), kind=m.group(3), visible=int(m.group(4)), opacity=float(m.group(5)),
                                 mode=m.group(6), offset=[int(m.group(7)), int(m.group(8))], size=[int(m.group(9)), int(m.group(10))], parasites=m.group(11)))
            else:
                rows.append({'unparsed': line[:200]})
    return dict(head=head, rows=rows, ops=ops)


def gimp_dump(psd, tag):
    txt, png, rs = WORK / f'gimp_{tag}.txt', OUT / f'gimp_{tag}.png', WORK / f'gimp_{tag}_resave.psd'
    for p in (txt, png, rs):
        p.unlink(missing_ok=True)
    r, sec = gimp(f'(begin {GIMP_LOAD} (dump "{psd}" "{txt}" "{png}" "{rs}"))')
    e = {'rc': r.returncode, 'sec_total': round(sec, 2), 'stderr_tail': r.stderr[-300:]}
    if txt.exists():
        e.update(parse_gimp_dump(txt))
    return e, png, rs


def krita(fn, *args):
    t0 = time.perf_counter()
    r = run(['kritarunner', '-s', 'krita_tools', '-f', fn, *map(str, args)], env=ENV, timeout=600, cwd=str(HERE))
    return r, time.perf_counter() - t0


def krita_dump(psd, tag):
    js, png, rs = WORK / f'krita_{tag}.json', OUT / f'krita_{tag}.png', WORK / f'krita_{tag}_resave.psd'
    for p in (js, png, rs):
        p.unlink(missing_ok=True)
    r, sec = krita('dump', psd, js, png, rs)
    e = {'rc': r.returncode, 'sec_total': round(sec, 2)}
    e.update(json.loads(js.read_text()) if js.exists() else {'error': 'json が出ていない', 'stderr_tail': r.stderr[-400:]})
    return e, png, rs


def diff_rgb(a_png, b):
    im = Image.open(a_png).convert('RGBA')
    # 本番の PSD には紙の層が無く、コマの間は透明。白い紙の上に置いて比べる
    a = np.asarray(Image.alpha_composite(Image.new('RGBA', im.size, (255, 255, 255, 255)), im).convert('RGB')).astype(int)
    transparent = float((np.asarray(im)[..., 3] < 255).mean())
    b = b.astype(int)
    if a.shape != b.shape:
        return {'形が違う': [list(a.shape), list(b.shape)]}
    d = np.abs(a - b)
    return {'平均差(0..255)': round(float(d.mean()), 3), '差が16超の画素の割合': round(float((d.max(2) > 16).mean()), 5), '透明な画素の割合': round(transparent, 4)}


# ---------------------------------------------------------------- 戻し（対応づけと差）
TAG_RE = re.compile(r'\[(p\d[\w]+)\]')


def match_back(orig_items, ids, group_ids, back_rows, ag_rows):
    """読み戻した層を、元の項目に対応づける。lyid・名前の目印・時刻のそれぞれで、何件当たるかを数える。"""
    id2item = {v: k for k, v in ids.items()}
    id2item.update({v: k for k, v in group_ids.items()})
    ts2item = {1_700_000_000 + v: k for k, v in ids.items()}
    ts2item.update({1_700_000_000 + v: k for k, v in group_ids.items()})
    total = len(ids) + len(group_ids)
    by_lyid, by_tag, by_ts = {}, {}, {}
    for r in back_rows:
        if r['layer_id'] in id2item:
            by_lyid[id2item[r['layer_id']]] = r
        m = TAG_RE.search(r['name'])
        if m:
            by_tag[m.group(1)] = r
    for r in ag_rows:
        if r.get('timestamp') is not None and round(r['timestamp']) in ts2item:
            by_ts[ts2item[round(r['timestamp'])]] = r
    # lyid が付いていても、違う層に同じ値が付き直していないか（目印と食い違う数）
    lyid_conflict = sum(1 for k, r in by_lyid.items() if TAG_RE.search(r['name']) and TAG_RE.search(r['name']).group(1) != k)
    lyids = [r['layer_id'] for r in back_rows]
    return dict(total=total, lyid_hits=len(by_lyid), tag_hits=len(by_tag), timestamp_hits=len(by_ts),
                lyid_values_sample=lyids[:8], lyid_conflict_with_tag=lyid_conflict), by_lyid, by_tag


def change_report(items, by_key, back_rows):
    """対応づけた層ごとに、ページの座標の画素の差を数える。対応しない読み戻しの層は足された層、見つからない項目は消えた層。"""
    out, seen = [], set()
    for it in items:
        r = by_key.get(it['item'])
        if r is None:
            out.append({'item': it['item'], 'name': it['name'], 'status': 'removed_or_unmatched'})
            continue
        seen.add(id(r))
        a, b = it['arr'], r['_arr']
        d = np.any(a != b, axis=2) & ((a[..., 3] > 0) | (b[..., 3] > 0))
        # 透明の画素の色の違いは数えない
        d &= ~((a[..., 3] == 0) & (b[..., 3] == 0))
        n = int(d.sum())
        e = {'item': it['item'], 'back_name': r['name'], 'kind': r['kind'], 'changed_px': n,
             'visible_before': not it['hidden'], 'visible_after': r['visible'], 'blend_before': it['blend'], 'blend_after': r['blend']}
        if n:
            ys, xs = np.nonzero(d)
            e['changed_bbox_page'] = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
        if it['text'] is not None:
            e['text_kept_as_text'] = r['kind'] == 'type'
            e['text_back'] = r.get('text')
        out.append(e)
    added = [{'name': r['name'], 'kind': r['kind'], 'path': r['path'], 'bbox': r['bbox'], 'opaque_px': r.get('opaque_px')}
             for r in back_rows if r['kind'] != 'group' and id(r) not in seen]
    # 目印が消えた層を、見つからない項目と画素が同じかで当てる（名前を変えた層を見分けられるか）
    missing = [it for it in items if by_key.get(it['item']) is None]
    rows_added = [r for r in back_rows if r['kind'] != 'group' and id(r) not in seen]
    for a, r in zip(added, rows_added):
        a['same_pixels_as_missing_item'] = [it['item'] for it in missing if np.array_equal(it['arr'], r['_arr'])]
    return out, added


def reattach(item, back_row, panel_rect):
    """直した線画を、元の層と同じ大きさ・同じ置き場の新しい版として切り出す。元の範囲の外に出た画素も数える。"""
    x0, y0, x1, y1 = panel_rect
    new = back_row['_arr'][y0:y1, x0:x1]
    old = item['arr'][y0:y1, x0:x1]
    outside = back_row['_arr'].copy(); outside[y0:y1, x0:x1] = 0
    d = np.any(new != old, axis=2)
    ys, xs = np.nonzero(d)
    px, py, pw, ph = PAINT_RECT
    exp = [max(px, x0) - x0, max(py, y0) - y0, min(px + pw, x1) - x0, min(py + ph, y1) - y0]
    got = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None
    return {'new_image_size': [x1 - x0, y1 - y0], 'placement_left_top': [x0, y0], 'changed_px_in_panel': int(d.sum()),
            'changed_bbox_in_panel': got, 'expected_bbox_in_panel': exp, 'bbox_matches_edit': got == exp,
            'opaque_px_outside_panel': int((outside[..., 3] > 0).sum()),
            'server_ops': ['register_image(role=line_art, origin=human_edited, based_on_image_id=元の絵, panel_id=コマ)',
                           'update_panel_layer(id=線画の層, image_id=新しい絵, placement=元と同じ)']}


# ---------------------------------------------------------------- 一覧の画像
def thumb(png_or_arr, w=300):
    if isinstance(png_or_arr, np.ndarray):
        im = Image.fromarray(png_or_arr[..., :3])
    else:  # 透明なところ（コマの間）は白い紙として見せる
        im = Image.open(png_or_arr).convert('RGBA')
        im = Image.alpha_composite(Image.new('RGBA', im.size, (255, 255, 255, 255)), im).convert('RGB')
    return im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)


def sheet(tiles, labels, path, cols):
    font = ImageFont.truetype(FONT, 18)
    tw, th = max(t.width for t in tiles), max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    s = Image.new('RGB', (cols * (tw + 10) + 10, rows * (th + 40) + 10), (255, 255, 255))
    d = ImageDraw.Draw(s)
    for i, (t, lb) in enumerate(zip(tiles, labels)):
        x, y = 10 + (i % cols) * (tw + 10), 10 + (i // cols) * (th + 40)
        d.text((x, y), lb, font=font, fill=(0, 0, 0))
        s.paste(t, (x, y + 28))
    s.save(path, optimize=True)
    if path.stat().st_size > 1_000_000:
        s.quantize(64).save(path, optimize=True)
    return path.stat().st_size


# ================================================================ 本体
def main():
    res = {'versions': {'psd_tools': psd_tools.__version__, 'gimp': run(['gimp', '--version']).stdout.strip(),
                        'krita': run(['dpkg-query', '-W', '-f', '${Version}', 'krita']).stdout.strip(), 'node': run(['node', '--version']).stdout.strip()},
           'page_size_px': [W, H], '未検証': ['Photoshop・CLIP STUDIO PAINT で開いたとき（この環境に無い）',
                                              '手順の数は人で測っていない（層の構造から数えた見積り）',
                                              '入稿の解像度（600dpi 程度）での開く時間とファイルの大きさ（ここは 150dpi）']}
    pages = {p: make_page(p) for p in (1, 2)}

    # ---- 1. 本番の書き出しで2ページを書く
    files = {}
    for p, (items, comp_png, _) in pages.items():
        out_psd = OUT / f'page{p}.psd'
        req, _, _ = build_request(p, items, comp_png, out_psd)
        back = write_layered_psd(req, 'node', PROD_WRITER, 120)
        files[f'page{p}'] = out_psd
        res.setdefault('production_write', {})[f'page{p}'] = {'bytes': back['bytes'], 'layers_readback': len(back['layers'])}
    # 目印つき（戻しの試験用）と、文字の画素なし（ag-psd が文字を描くかの試験用）。どちらも1ページ目
    items1, comp1_png, comp1 = pages[1]
    req_tag, ids, group_ids = build_request(1, items1, comp1_png, OUT / 'page1_tagged.psd', tag_mode=True)
    w_tag = local_write(req_tag)
    files['page1_tagged'] = OUT / 'page1_tagged.psd'
    req_np, _, _ = build_request(1, items1, comp1_png, OUT / 'page1_text_no_pixels.psd', text_pixels=False)
    w_np = local_write(req_np)
    files['page1_text_no_pixels'] = OUT / 'page1_text_no_pixels.psd'
    res['text_without_pixels_agpsd'] = [{'name': L['name'], 'bounds': [L['left'], L['top'], L['right'], L['bottom']], 'pixels': L['pixels'], 'text': L['text']}
                                        for L in w_np['layers'] if L['text']][:3]
    res['tagged_write_xmp_kept_by_agpsd'] = bool(w_tag.get('xmp') and 'v3:layerMap' in w_tag['xmp'])

    # ---- 開く・数える
    usab = {}
    for k, f in files.items():
        pno = 2 if k == 'page2' else 1
        comp = pages[pno][2]
        pt = pt_read(f)
        ag = agpsd_read(f, k)
        e = {'bytes': f.stat().st_size, 'psd_tools_open_sec': pt['open_sec'], 'psd_tools': tree_stats(pt['rows']),
             'agpsd_read_ms': ag.get('read_ms'), 'agpsd_text_layers': sum(1 for L in ag.get('layers', []) if L['text'])}
        g, gpng, grs = gimp_dump(f, k)
        e['gimp_open_sec'], e['gimp_startup_sec'] = gimp_open_sec(f)
        grows = [r for r in g.get('rows', []) if 'name' in r]
        e['gimp'] = {'rc': g['rc'], 'groups': sum(1 for r in grows if r['kind'] == 'group'), 'layers': sum(1 for r in grows if r['kind'] != 'group'),
                     'text_layers': sum(1 for r in grows if r['kind'] == 'text'),
                     'renamed_duplicates': [r['name'] for r in grows if re.search(r' #\d+$', r['name'])],
                     'names_sample': [r['name'] for r in grows][:12], 'modes': sorted({r['mode'] for r in grows}),
                     'hidden': [r['name'] for r in grows if not r['visible']],
                     'composite_vs_expected': diff_rgb(gpng, comp) if gpng.exists() else None, 'stderr_tail': g['stderr_tail'][-200:]}
        kd, kpng, krs = krita_dump(f, k)
        krows = kd.get('layers', [])
        e['krita'] = {'open_sec': kd.get('open_sec'), 'groups': sum(1 for r in krows if r['type'] == 'grouplayer'),
                      'layers': sum(1 for r in krows if r['type'] != 'grouplayer'), 'types': sorted({r['type'] for r in krows}),
                      'names_sample': [r['name'] for r in krows][:12], 'blends': sorted({r['blend'] for r in krows}),
                      'hidden': [r['name'] for r in krows if not r['visible']],
                      'composite_vs_expected': diff_rgb(kpng, comp) if kpng.exists() else None, 'error': kd.get('error')}
        # 開いて手を加えずに保存した PSD を読み、文字の層と画素が残るか
        for tool, rs in (('gimp', grs), ('krita', krs)):
            if rs.exists():
                pr = pt_read(rs)
                st = tree_stats(pr['rows'])
                texts = [r for r in pr['rows'] if TAG_RE.sub('', r['name']).strip().split(' ')[-1].startswith('台詞')]
                e[tool]['resave'] = {'bytes': rs.stat().st_size, 'kinds': st['kinds'], 'groups': st['groups'], 'layers': st['layers'],
                                     'text_layer_kinds': sorted({r['kind'] for r in texts}),
                                     'text_layer_opaque_px': [r.get('opaque_px') for r in texts],
                                     'lyid_sample': [r['layer_id'] for r in pr['rows']][:6]}
            else:
                e[tool]['resave'] = {'error': '保存した PSD が無い'}
        # 文字層の画素の数（元）とコマ枠の分離
        pr0 = pt_read(f)
        e['text_layer_opaque_px_original'] = [r.get('opaque_px') for r in pr0['rows'] if '台詞' in r['name']]
        frame = next(r for r in pr0['rows'] if r['name'].startswith('コマ枠'))
        art = sum((r['_arr'][..., 3] > 0) for r in pr0['rows'] if r['kind'] != 'group' and len(r['path']) >= 3)
        fa = frame['_arr'][..., 3] > 0
        e['frame_separable'] = {'frame_is_own_layer': True, 'frame_opaque_px': int(fa.sum()),
                                'frame_px_covered_by_panel_art': int((fa & (art > 0)).sum()),
                                'frame_order': 'コマ枠は一番下（V3細部の決めごと 10.3 の順）'}
        usab[k] = e
        print(k, json.dumps({kk: e[kk] for kk in ('bytes', 'gimp_open_sec')}, ensure_ascii=False), flush=True)
    res['usability_measured'] = usab

    # ---- 2. 戻し：GIMP と Krita で人の直しを真似る
    def nm(item):  # 目印つきの層の名前
        it = next(i for i in items1 if i['item'] == item)
        return f'{it["name"]} [{item}]'
    plan = {'line_name': nm('p1k2L'), 'rename_from': nm('p1k3B'), 'rename_to': '背景（直し）', 'toggle_name': nm('p1k1C'),
            'group_name': 'コマ2 [p1g2]', 'delete_name': nm('p1k4T'), 'text_name': nm('p1k1s1'), 'text_group_name': '写植 [p1gtext]',
            'paint_rect': list(PAINT_RECT), 'add_rect': list(ADD_RECT)}
    (WORK / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False))
    src = files['page1_tagged']
    rt = {'plan': plan}
    gtxt, gpsd, gpng = WORK / 'gimp_edit.txt', OUT / 'page1_gimp_edited.psd', OUT / 'gimp_edited.png'
    for p in (gtxt, gpsd, gpng):
        p.unlink(missing_ok=True)
    q = lambda s: '"' + s.replace('"', '\\"') + '"'
    expr = (f'(begin {GIMP_LOAD} (edit "{src}" "{gtxt}" "{gpsd}" "{gpng}" {q(plan["line_name"])} {q(plan["rename_from"])} {q(plan["rename_to"])} '
            f'{q(plan["toggle_name"])} {q(plan["group_name"])} {q(plan["delete_name"])} {q(plan["text_name"])} {q(plan["text_group_name"])}))')
    r, _ = gimp(expr)
    rt['gimp_edit'] = {'rc': r.returncode, 'ops': parse_gimp_dump(gtxt)['ops'] if gtxt.exists() else None, 'stderr_tail': r.stderr[-400:]}
    kjs, kpsd, kpng = WORK / 'krita_edit.json', OUT / 'page1_krita_edited.psd', OUT / 'krita_edited.png'
    for p in (kjs, kpsd, kpng):
        p.unlink(missing_ok=True)
    r, _ = krita('edit', src, kjs, kpng, kpsd, WORK / 'plan.json')
    kj = json.loads(kjs.read_text()) if kjs.exists() else {'error': r.stderr[-400:]}
    rt['krita_edit'] = {'ops': kj.get('ops'), 'error': kj.get('error'), 'export_psd_ok': kj.get('export_psd_ok')}

    # 読み戻し（基準として、書いたままの PSD も同じ手順で読む）
    re_items = {}
    for tool, f in (('no_edit', src), ('gimp', gpsd), ('krita', kpsd)):
        if not f.exists():
            rt[tool] = {'error': 'PSD が無い'}
            continue
        pr = pt_read(f)
        ag = agpsd_read(f, f'rt_{tool}')
        stats, by_lyid, by_tag = match_back(items1, ids, group_ids, pr['rows'], ag.get('layers', []))
        key = by_lyid if stats['lyid_hits'] >= stats['tag_hits'] else by_tag
        changes, added = change_report(items1, key, pr['rows'])
        e = {'identifiers': stats, 'matched_by': 'lyid' if key is by_lyid else 'name_tag',
             'xmp_kept': bool(ag.get('xmp') and 'v3:layerMap' in ag['xmp']), 'agpsd_read_error': ag.get('error'),
             'changed': [c for c in changes if c.get('changed_px') or c.get('status') or c.get('visible_before') != c.get('visible_after') or c.get('blend_before') != c.get('blend_after')],
             'blend_lost': [c['item'] for c in changes if c.get('blend_before') == 'multiply' and c.get('blend_after') not in (None, 'MULTIPLY')],
             'text_layers': [{'item': c['item'], 'kept_as_text': c.get('text_kept_as_text'), 'text': c.get('text_back')} for c in changes if 'text_kept_as_text' in c],
             'added': added, 'groups': [r['name'] for r in pr['rows'] if r['kind'] == 'group'],
             'unchanged_layers': sum(1 for c in changes if c.get('changed_px') == 0)}
        # ag-psd で読んだ文字層
        e['names_with_nul'] = sum(1 for r in pr['rows'] if '\x00' in r['name'])
        e['agpsd_text_layers'] = [{'name': L['name'], 'text': L['text']} for L in ag.get('layers', []) if L['text']][:3]
        # 足された層がどのグループ（コマ）の中か
        for a in added:
            m = TAG_RE.findall(' '.join(a['path'][:-1]))
            a['parent_panel_key'] = m[-1] if m else None  # いちばん内側のグループの目印
            a['name_has_nul'] = '\x00' in a['name']
        # 塗った線画を新しい版として戻せるか
        line_item = next(i for i in items1 if i['item'] == 'p1k2L')
        if 'p1k2L' in key:
            e['reattach_line_art'] = reattach(line_item, key['p1k2L'], PAGES[1]['panels'][1])
        else:
            e['reattach_line_art'] = {'error': '線画の層を対応づけられない'}
        rt[tool] = e
        re_items[tool] = pr
    res['roundtrip'] = rt

    # ---- 一覧の画像
    sheets = {}
    tiles = [thumb(OUT / 'expected_p1.png'), thumb(OUT / 'gimp_page1.png'), thumb(OUT / 'krita_page1.png'),
             thumb(OUT / 'expected_p2.png'), thumb(OUT / 'gimp_page2.png'), thumb(OUT / 'krita_page2.png')]
    sheets['sheet_open.png'] = sheet(tiles, ['1ページ 期待', '1ページ GIMP', '1ページ Krita', '2ページ 期待', '2ページ GIMP', '2ページ Krita'], OUT / 'sheet_open.png', 3)
    crop = (630, 590, 1160, 1100)
    t2 = [Image.open(OUT / 'expected_p1.png').crop(crop), Image.open(OUT / 'gimp_page1_text_no_pixels.png').crop((900, 560, 1160, 860)) if (OUT / 'gimp_page1_text_no_pixels.png').exists() else Image.new('RGB', (10, 10)),
          Image.open(OUT / 'krita_page1_text_no_pixels.png').crop((900, 560, 1160, 860)) if (OUT / 'krita_page1_text_no_pixels.png').exists() else Image.new('RGB', (10, 10))]
    t2 = [Image.alpha_composite(Image.new('RGBA', t.size, (255, 255, 255, 255)), t.convert('RGBA')).convert('RGB').resize((t.width * 300 // t.width, t.height * 300 // t.width)) for t in t2]
    sheets['sheet_text_no_pixels.png'] = sheet(t2, ['コマ2 期待（文字の画素あり）', '画素なしの文字層 GIMP', '画素なしの文字層 Krita'], OUT / 'sheet_text_no_pixels.png', 3)
    t3, lb3 = [], []
    for tool in ('gimp', 'krita'):
        pngp = OUT / f'{tool}_edited.png'
        if pngp.exists():
            t3.append(thumb(pngp)); lb3.append(f'{tool} で直した合成')
        if tool in re_items:
            pr = re_items[tool]
            keyed = {TAG_RE.search(r['name']).group(1): r for r in pr['rows'] if TAG_RE.search(r['name'])}
            vis = np.full((H, W, 3), 255, np.uint8)
            for it in items1:
                r = keyed.get(it['item'])
                if r is None or '_arr' not in r:
                    continue
                d = np.any(it['arr'] != r['_arr'], axis=2) & ~((it['arr'][..., 3] == 0) & (r['_arr'][..., 3] == 0))
                vis[d] = (220, 30, 30)
            t3.append(thumb(vis)); lb3.append(f'{tool} 層ごとの差（赤）')
    sheets['sheet_roundtrip.png'] = sheet(t3, lb3, OUT / 'sheet_roundtrip.png', 4)
    res['sheets_bytes'] = sheets

    res['summary'] = summarize(res)
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    print(json.dumps(res['summary'], ensure_ascii=False, indent=1))


def summarize(res):
    """測った値から要点を組む。直しの手順は層の構造から数えた見積り（人では測っていない）。"""
    u = res['usability_measured']
    rt = res['roundtrip']
    s = {}
    for k in ('page1', 'page2'):
        e = u[k]
        s[k] = {'bytes': e['bytes'], 'psd_tools': {kk: e['psd_tools'][kk] for kk in ('groups', 'layers', 'kinds', 'duplicate_names')},
                'gimp': {'open_sec': e['gimp_open_sec'], 'groups': e['gimp']['groups'], 'layers': e['gimp']['layers'], 'text_layers': e['gimp']['text_layers'],
                         'renamed_duplicates': len(e['gimp']['renamed_duplicates']), 'composite': e['gimp']['composite_vs_expected']},
                'krita': {'open_sec': e['krita']['open_sec'], 'groups': e['krita']['groups'], 'layers': e['krita']['layers'], 'types': e['krita']['types'],
                          'composite': e['krita']['composite_vs_expected']},
                'resave_text_kinds': {t: e[t]['resave'].get('text_layer_kinds') for t in ('gimp', 'krita')},
                'frame': e['frame_separable']}
    np_ = u['page1_text_no_pixels']
    s['text_without_pixels'] = {'agpsd': res['text_without_pixels_agpsd'][:1],
                                'gimp_resave_text_opaque_px': np_['gimp']['resave'].get('text_layer_opaque_px'),
                                'krita_resave_text_opaque_px': np_['krita']['resave'].get('text_layer_opaque_px'),
                                'original_with_pixels_opaque_px': u['page1']['text_layer_opaque_px_original']}
    s['roundtrip'] = {}
    for tool in ('no_edit', 'gimp', 'krita'):
        e = rt.get(tool, {})
        if 'identifiers' not in e:
            s['roundtrip'][tool] = e
            continue
        s['roundtrip'][tool] = {'identifiers': e['identifiers'], 'xmp_kept': e['xmp_kept'], 'matched_by': e['matched_by'],
                                'changed_items': [(c['item'], c.get('changed_px'), c.get('status'), c.get('visible_before'), c.get('visible_after')) for c in e['changed']],
                                'added': [(a['name'].rstrip('\x00'), a['parent_panel_key'], a['bbox'], a['opaque_px'], a['same_pixels_as_missing_item']) for a in e['added']],
                                'names_with_nul': e['names_with_nul'],
                                'blend_lost': e['blend_lost'], 'text_kept_as_text': sum(1 for t in e['text_layers'] if t['kept_as_text']),
                                'text_layers': len(e['text_layers']), 'reattach_line_art': {k: e['reattach_line_art'].get(k) for k in ('bbox_matches_edit', 'changed_px_in_panel', 'opaque_px_outside_panel', 'error')}}
    # 直しの手順（層の構造と、上で測った読み込み・戻しの結果から数えた見積り。人では測っていない）
    s['corrections_estimate'] = {
        '台詞を1行直す': {
            'PSD': ['写植のグループを開いて該当の層を探す', '文字の層が画素の層になっているので、層の画素を消す',
                    '文字の道具で縦書き・書体・大きさを元に合わせて打ち直す', '吹き出しの中に位置を合わせる', 'PSD で保存してアプリに戻す'],
            'PSD_戻るもの': 'GIMP は画素の層（文字の情報なし）、Krita で足した文字は画素0の層になった。サーバーの文字（text）は変わらない',
            'アプリ': ['台詞を選ぶ', '文字を直して確定（update_text_item の text だけ）'], 'PSDで足りるか': 'いいえ'},
        'フキダシを1つ動かす': {
            'PSD': ['フキダシの層（1ページの全部の吹き出しが1層）で吹き出し1つを範囲選択', '動かす', '写植の層の該当の文字も同じだけ動かす',
                    '重なりを確かめる', '保存して戻す'],
            'PSD_戻るもの': 'フキダシの層と写植の層の画素の差。どの吹き出しを何mm動かしたかは差から推し量るしかない（box_mm に戻す処理は作っていない・未検証）',
            'アプリ': ['吹き出しをドラッグ（update_text_item の box_mm）'], 'PSDで足りるか': 'いいえ'},
        'コマの手を描き直す': {
            'PSD': ['コマのグループを開く', '線画の層を選ぶ（GIMP では同じ名前の2つ目以降が「線画 #3」のように変わる）', '描く・消す', '保存して戻す'],
            'PSD_戻るもの': '線画の層の画素の差。GIMP・Krita とも 19200 画素の差が塗った範囲と一致し、元の層と同じ大きさ・置き場で新しい版にできた',
            'アプリ': ['コマを開く', '人が直接描く道具で描く（register_image origin=human_drawn・add_panel_layer role=human_hand）', 'または範囲を決めて作り直す'],
            'PSDで足りるか': 'はい（PSD のほうが道具がそろう）'},
        'コマの絵を1枚差し替える': {
            'PSD': ['コマのグループの背景・色・トーン・線画の4層を隠すか消す', '新しい絵をレイヤーとして開く', 'グループの中へ入れる', 'コマの範囲に位置と大きさを合わせる', '保存して戻す'],
            'PSD_戻るもの': '目印の無い新しい層。親のグループの目印でコマは分かるが、線画か背景かなどの役は分からない。消した4層は「消えた」として出る',
            'アプリ': ['コマを選ぶ', '候補か画像を選ぶ（update_panel_layer の image_id）'], 'PSDで足りるか': '一部（絵は戻るが、層の役は人が選び直す）'},
    }
    s['verdict'] = ('ほぼ完璧ではない。絵の層（名前・グループ・乗算・隠す・合成）は GIMP と Krita で崩れずに開け、絵の直しは名前の目印で正しいコマ・正しい位置に戻せた。'
                    'しかし文字は両方で画素になり、文字として直せず、直した文字はサーバーの文字に戻らない。PSD の層の id（lyid）・層の時刻は両方で消えた。')
    s['edit_ops'] = {'gimp': rt['gimp_edit']['ops'], 'krita': [(o['op'], o['result']) for o in (rt['krita_edit']['ops'] or [])]}
    return s


if __name__ == '__main__':
    main()
