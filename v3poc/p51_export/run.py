"""P51 書き出し（Pillow・OpenCV・img2pdf）で入稿用の画像とPDFが作れるかを確かめる（設計 3.1「書き出し」、決めごとの書き出しの節）。
確かめること:
  A B5 投稿原稿の寸法（仕上がり182x257・塗り足し3mm・基本枠150x220）で、600dpi・350dpi の白黒2値・グレー・カラーの画像を作る
  B 網点（線数・角度を指定）を作れるライブラリはどれか。Pillow・OpenCV・scikit-image には無い。ImageMagick は固定の閾値表のみ。numpy で自前に書いた網点の濃度の正確さ
  C 2値化で細い線（0.03〜0.5mm）と網点が残るか（閾値・位相・dpi別）
  D img2pdf で入稿用PDFを作り、ページ寸法（mm）・画像のdpi・2値の可逆性（Flate／CCITT G4）・ファイルの大きさを pypdf・pdfinfo・pdfimages で測る
使い方: python run.py（pillow・opencv-python-headless・numpy・img2pdf・pypdf が要る。pdfinfo・pdfimages・convert を使う）。
出力: out/result.json、out/crops.png（一覧）、out/ に画像・PDF（10MBを超えるものは .gitignore）。
寸法（mm）はリポジトリの文書にはB5仕上がり182x257だけ。塗り足し3mm・基本枠150x220は一般に流通する値で、出典は未確認。
"""
import json
import math
import pathlib
import subprocess
import time

import cv2
import img2pdf
import pypdf
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject

# 600dpi カラー（83MB）は pypdf の既定の展開上限（75MB）を超えるので上げる
_cfg = pypdf.overwrite_configuration(zlib_maximum_output_length=400_000_000, image_maximum_buffer_size=400_000_000)
HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
FONT = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'

TRIM = (182.0, 257.0)
BLEED = 3.0
FRAME = (150.0, 220.0)
CANVAS = (TRIM[0] + 2 * BLEED, TRIM[1] + 2 * BLEED)
MASTER_DPI = 1200
DPIS = (600, 350)
result = {'dimensions_mm': {'trim': TRIM, 'bleed': BLEED, 'canvas_with_bleed': CANVAS, 'basic_frame': FRAME,
                            'source': '仕上がりB5 182x257はV3細部の決めごと。塗り足し3・基本枠150x220は一般に流通する値（出典は未確認）'}}


def px(mm, dpi):
    return int(round(mm / 25.4 * dpi))


# ---------- 網点（自前のnumpy） ----------
def make_threshold_cell(n=256):
    """丸い網点（cosの和）の閾値表を、面積が濃度に比例するように並べ直したもの（0..1）。"""
    u, v = np.meshgrid((np.arange(n) + .5) / n, (np.arange(n) + .5) / n)
    f = 1 - (np.cos(2 * np.pi * u) + np.cos(2 * np.pi * v) + 2) / 4
    ranks = np.argsort(np.argsort(f.ravel())).reshape(f.shape)
    return (ranks + .5) / f.size


CELL = make_threshold_cell()


def screen(gray, dpi, lpi, angle_deg):
    """gray: uint8（255=白）。dpi・線数・角度を指定した AM 網点で2値（True=黒）にする。"""
    h, w = gray.shape
    p = dpi / lpi
    a = math.radians(angle_deg)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (x * math.cos(a) + y * math.sin(a)) / p
    v = (-x * math.sin(a) + y * math.cos(a)) / p
    n = CELL.shape[0]
    t = CELL[(np.floor((v % 1) * n)).astype(int) % n, (np.floor((u % 1) * n)).astype(int) % n]
    dark = 1 - gray.astype(np.float32) / 255
    return dark > t


# ---------- 原稿の絵 ----------
def draw_layers(dpi_m):
    """線の層（白地に黒線）と、トーンの層（灰色のベタ）を dpi_m で描く。"""
    W, H = px(CANVAS[0], dpi_m), px(CANVAS[1], dpi_m)
    M = lambda mm: mm / 25.4 * dpi_m
    line = Image.new('L', (W, H), 255)
    tone = Image.new('L', (W, H), 255)
    dl, dt = ImageDraw.Draw(line), ImageDraw.Draw(tone)
    ox, oy = BLEED, BLEED   # 塗り足しの分
    # 仕上がり線（細い）・基本枠
    dl.rectangle([M(ox), M(oy), M(ox + TRIM[0]), M(oy + TRIM[1])], outline=0, width=max(1, round(M(0.1))))
    fx, fy = ox + (TRIM[0] - FRAME[0]) / 2, oy + (TRIM[1] - FRAME[1]) / 2
    dl.rectangle([M(fx), M(fy), M(fx + FRAME[0]), M(fy + FRAME[1])], outline=0, width=max(1, round(M(0.2))))
    # コマ（枠線0.5mm）
    panels = [(fx, fy, fx + 72, fy + 90), (fx + 75, fy, fx + 150, fy + 90), (fx, fy + 93, fx + 150, fy + 220)]
    for x0, y0, x1, y1 in panels:
        dl.rectangle([M(x0), M(y0), M(x1), M(y1)], outline=0, width=round(M(0.5)))
    # トーンの灰色（10〜90%）をコマ1の中に5枚
    pats = []
    for i, d in enumerate((10, 30, 50, 70, 90)):
        x0 = fx + 4 + i * 13
        box = [M(x0), M(fy + 4), M(x0 + 12), M(fy + 30)]
        dt.rectangle(box, fill=round(255 * (1 - d / 100)))
        pats.append((d, x0, fy + 4, x0 + 12, fy + 30))
    # 線の太さ見本（コマ2の中）：横線・縦線・斜め線
    widths = (0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3, 0.5)
    for i, wmm in enumerate(widths):
        y = fy + 8 + i * 6
        dl.line([M(fx + 80), M(y), M(fx + 110), M(y)], fill=0, width=max(1, round(M(wmm))))
        dl.line([M(fx + 115 + i * 4), M(fy + 8), M(fx + 115 + i * 4), M(fy + 40)], fill=0, width=max(1, round(M(wmm))))
    # 文字（小さい）
    f = ImageFont.truetype(FONT, round(M(2.5)))
    dl.text((M(fx + 5), M(fy + 100)), 'あいうえお 漫画原稿 ABC 123', font=f, fill=0)
    f2 = ImageFont.truetype(FONT, round(M(1.6)))
    dl.text((M(fx + 5), M(fy + 108)), 'ひらがなの細い線がつぶれないか', font=f2, fill=0)
    # コマ3の下：連続階調のトーン（10→90%）とハッチング（実際の原稿に近い量の網点・線を入れる）
    gx0, gx1 = fx + 5, fx + 145
    gw = round(M(gx1 - gx0))
    grad = np.tile(np.linspace(0.9, 0.1, gw)[None, :], (round(M(40)), 1))
    tone.paste(Image.fromarray((grad * 255).astype(np.uint8)), (round(M(gx0)), round(M(fy + 168))))
    for k in range(int((gx1 - gx0) / 1.0)):
        xx = gx0 + k * 1.0
        dl.line([M(xx), M(fy + 164), M(xx + 6), M(fy + 164 - 3)], fill=0, width=max(1, round(M(0.1))))
    # コマ3の中：トーン60線用・85線用の灰色30%
    dt.rectangle([M(fx + 5), M(fy + 120), M(fx + 70), M(fy + 160)], fill=round(255 * .7))
    dt.rectangle([M(fx + 80), M(fy + 120), M(fx + 145), M(fy + 160)], fill=round(255 * .7))
    return line, tone, dict(widths=widths, pats=pats, fx=fx, fy=fy)


t0 = time.time()
line_m, tone_m, meta = draw_layers(MASTER_DPI)
result['master_dpi'] = MASTER_DPI
result['master_px'] = list(line_m.size)
result['draw_seconds'] = round(time.time() - t0, 1)
line_a, tone_a = np.asarray(line_m), np.asarray(tone_m)


def down(a, dpi):
    size = (px(CANVAS[0], dpi), px(CANVAS[1], dpi))
    if dpi == MASTER_DPI:
        return a
    return cv2.resize(a, size, interpolation=cv2.INTER_AREA)


LPI, ANG = 60, 45
tint_small = np.full((px(CANVAS[1], 300), px(CANVAS[0], 300), 3), 255, np.uint8)
fx, fy = meta['fx'], meta['fy']
def mmbox(arr, x0, y0, x1, y1, dpi, color):
    arr[px(y0, dpi):px(y1, dpi), px(x0, dpi):px(x1, dpi)] = color
mmbox(tint_small, fx + 5, fy + 120, fx + 70, fy + 160, 300, (255, 200, 190))   # 肌色の着彩
mmbox(tint_small, fx + 80, fy + 120, fx + 145, fy + 160, 300, (190, 215, 255))  # 青

images = {}
for dpi in DPIS:
    ln, tn = down(line_a, dpi), down(tone_a, dpi)
    gray = np.minimum(ln, tn)
    # 2値：線は閾値128、トーンは網点
    bw_line = ln < 128
    bw_tone = screen(tn, dpi, LPI, ANG)
    bw = ~(bw_line | bw_tone)  # True=白
    rgb = np.dstack([gray] * 3).astype(np.float32)
    tint = cv2.resize(tint_small, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_NEAREST).astype(np.float32) / 255
    rgb = (rgb * tint).astype(np.uint8)
    images[dpi] = {'bw': bw, 'gray': gray, 'rgb': rgb, 'line': ln, 'tone': tn}
    Image.fromarray(bw.astype(np.uint8) * 255).convert('1').save(OUT / f'page_{dpi}_bw.png', dpi=(dpi, dpi))
    Image.fromarray(gray, 'L').save(OUT / f'page_{dpi}_gray.png', dpi=(dpi, dpi))
    Image.fromarray(rgb, 'RGB').save(OUT / f'page_{dpi}_rgb.png', dpi=(dpi, dpi))
    Image.fromarray(bw.astype(np.uint8) * 255).convert('1').save(OUT / f'page_{dpi}_bw_g4.tif', compression='group4', dpi=(dpi, dpi))
result['A_images'] = {}
for dpi in DPIS:
    sizes = {k: (OUT / f'page_{dpi}_{k}').stat().st_size for k in ('bw.png', 'gray.png', 'rgb.png', 'bw_g4.tif')}
    pil = Image.open(OUT / f'page_{dpi}_bw.png')
    result['A_images'][dpi] = {'px': list(images[dpi]['bw'].shape[::-1]), 'expected_px_mm_formula': [px(CANVAS[0], dpi), px(CANVAS[1], dpi)],
                               'pil_dpi_in_file': [round(v, 3) for v in pil.info.get('dpi', (0, 0))], 'mode_bw': pil.mode, 'file_bytes': sizes}

# ---------- B 網点のライブラリ ----------
lib = {}
import PIL.Image, PIL.ImageOps, PIL.ImageFilter, PIL.ImageDraw
lib['Pillow'] = {'halftone系の関数': [n for n in dir(PIL.Image) + dir(PIL.ImageOps) + dir(PIL.ImageFilter) + dir(PIL.ImageDraw) if 'halftone' in n.lower()],
                 '2値化': 'Image.convert("1") は既定が Floyd-Steinberg の誤差拡散（dither=NONE で閾値128）。線数・角度の指定は無い'}
lib['OpenCV'] = {'halftone系': [n for n in dir(cv2) if 'halftone' in n.lower()], '備考': 'cv2.threshold・adaptiveThreshold のみ。網点（AM スクリーン）は無い'}
try:
    import skimage
    lib['scikit-image'] = {'halftone系': 'なし（skimage に halftone・dither のモジュール名は無い）'}
except ImportError:
    pass
im_out = subprocess.run(['convert', '-version'], capture_output=True, text=True).stdout.splitlines()[0]
# ImageMagick の順序ディザ（角度つき網点 h8x8a=45度）で、灰色の帯を2値にして濃度を測る
grad = np.tile(np.linspace(255, 0, 256, dtype=np.uint8)[None, :], (64, 1))
Image.fromarray(grad).save(OUT / '_grad.png')
im_res = {}
for mp in ('h4x4a', 'h6x6a', 'h8x8a', 'h8x8o', 'c7x7b'):
    subprocess.run(['convert', str(OUT / '_grad.png'), '-ordered-dither', mp, str(OUT / '_gradbw.png')], check=True)
    b = np.asarray(Image.open(OUT / '_gradbw.png').convert('L')) < 128
    # 濃度の目標と実測（列ごと）の最大差
    target = 1 - np.linspace(255, 0, 256) / 255 * 1  # 白→黒の濃度ではなく黒の割合
    target = np.linspace(0, 1, 256)
    meas = b.mean(0)
    k = 16
    sm_m = np.convolve(meas, np.ones(k) / k, 'valid'); sm_t = np.convolve(target, np.ones(k) / k, 'valid')
    im_res[mp] = {'最大濃度差': round(float(np.abs(sm_m - sm_t).max()), 3)}
lib['ImageMagick'] = {'version': im_out, '網点': '-ordered-dither の閾値表（h4x4a/h6x6a/h8x8a=45度・h8x8o=0度・c7x7b 他）。固定の大きさで、線数は dpi と表の大きさで決まり、任意の角度・線数の指定は無い',
                      '濃度の実測': im_res}
lib['numpy自前（この run.py の screen）'] = {'線数・角度': '指定できる（cosの和の丸網点の閾値表を面積が濃度に比例するよう並べ直した）'}
# 自前の網点の濃度の正確さ
acc = {}
for dpi in DPIS:
    for lpi in (60, 85):
        errs = []
        for d in (10, 30, 50, 70, 90):
            g = np.full((px(40, dpi), px(40, dpi)), round(255 * (1 - d / 100)), np.uint8)
            errs.append(round(float(screen(g, dpi, lpi, 45).mean()) - d / 100, 3))
        acc[f'{dpi}dpi_{lpi}線'] = {'セルの一辺px': round(dpi / lpi, 2), '濃度誤差(10/30/50/70/90%)': errs}
result['B_halftone'] = {'libraries': lib, 'own_screen_density_error': acc, 'angle_deg': ANG}

# ---------- C 細い線と網点 ----------
def line_metrics(dpi, thr, phase_mm, kind):
    """幅ごとに、1200dpi の線を dpi に落として2値にし、線の太さ(px)・途切れ数を測る。"""
    out = {}
    L = 20.0   # mm
    for wmm in (0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3, 0.5):
        Wm, Hm = px(30, MASTER_DPI), px(8, MASTER_DPI)
        m = Image.new('L', (Wm, Hm), 255)
        d = ImageDraw.Draw(m)
        wpx = max(1, round(wmm / 25.4 * MASTER_DPI))
        y0 = px(4 + phase_mm, MASTER_DPI)
        if kind == 'h':
            d.line([px(5, MASTER_DPI), y0, px(5 + L, MASTER_DPI), y0], fill=0, width=wpx)
        else:
            d.line([px(5, MASTER_DPI), px(2, MASTER_DPI) + y0 - px(4, MASTER_DPI), px(5 + L / 4, MASTER_DPI), px(2, MASTER_DPI) + y0 - px(4, MASTER_DPI) + px(L / 4, MASTER_DPI)], fill=0, width=wpx)
        a = cv2.resize(np.asarray(m), (px(30, dpi), px(8, dpi)), interpolation=cv2.INTER_AREA)
        b = a < thr
        ink = float(b.sum())
        expected = wmm / 25.4 * dpi * (L / 25.4 * dpi) if kind == 'h' else None
        ncomp = cv2.connectedComponents(b.astype(np.uint8), connectivity=8)[0] - 1
        if kind == 'h':
            col = b[:, px(8, dpi):px(22, dpi)].sum(0)
            out[wmm] = {'線の太さpx(理論)': round(wmm / 25.4 * dpi, 2), '実測の太さpx平均': round(float(col.mean()), 2), '途切れた列の割合': round(float((col == 0).mean()), 3), '断片数': int(ncomp)}
        else:
            out[wmm] = {'断片数': int(ncomp), '黒の画素数': int(ink)}
    return out

C = {}
for dpi in DPIS:
    for thr in (128, 200):
        for phase in (0.0, 0.5 * 25.4 / dpi):
            key = f'{dpi}dpi_閾値{thr}_位相{round(phase / (25.4 / dpi), 1)}px'
            C[key] = {'横': line_metrics(dpi, thr, phase, 'h'), '斜め': line_metrics(dpi, thr, phase, 'd')}
result['C_thin_lines'] = C
# 直接2値で描く（アンチエイリアス無し）場合は、幅は最低1pxになる
direct = {}
for dpi in DPIS:
    direct[f'{dpi}dpi'] = {str(w): max(1, round(w / 25.4 * dpi)) for w in (0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3, 0.5)}
result['C_direct_binary_line_px'] = direct
# 網点を600で作って350に縮めて2値化 vs 350で直接網点
res_h = {}
for lpi in (60, 85):
    g600 = np.full((px(40, 600), px(40, 600)), round(255 * .7), np.uint8)
    b600 = screen(g600, 600, lpi, 45)
    sm = cv2.resize((~b600).astype(np.uint8) * 255, (px(40, 350), px(40, 350)), interpolation=cv2.INTER_AREA)
    re = sm < 128
    g350 = np.full((px(40, 350), px(40, 350)), round(255 * .7), np.uint8)
    b350 = screen(g350, 350, lpi, 45)
    # モアレ：セル4つ分の窓で平均した黒の割合のばらつき（標準偏差。網点が一様なら小さい）
    def lowfreq_std(b, dpi_):
        k = int(round(4 * dpi_ / lpi))
        return float(cv2.blur(b.astype(np.float32), (k, k))[k:-k, k:-k].std())
    res_h[f'{lpi}線_30%濃度'] = {'600で作り350に縮め閾値128の黒の割合': round(float(re.mean()), 3), '350で直接作った黒の割合': round(float(b350.mean()), 3),
                               '600で作った黒の割合': round(float(b600.mean()), 3), '低周波のむら(標準偏差) 600で作った': round(lowfreq_std(b600, 600), 4), '同 350で直接': round(lowfreq_std(b350, 350), 4), '同 600から350に縮めた': round(lowfreq_std(re, 350), 4)}
result['C_halftone_resample'] = res_h
# 原稿全体で網点領域・線が残った割合（600dpi の2値）
g_line = images[600]['line'] < 128
result['C_page_600_black_ratio'] = {'line層(閾値128)': round(float(g_line.mean()), 4), '網点(70%灰)': round(float(images[600]['bw'].mean()), 4)}

# 画像の一覧（切り出し）
def crop(a, x0, y0, x1, y1, dpi):
    return a[px(y0, dpi):px(y1, dpi), px(x0, dpi):px(x1, dpi)]
tiles = []
for dpi in DPIS:
    bw = (images[dpi]['bw'].astype(np.uint8) * 255)
    tiles.append((f'{dpi}dpi 線の太さ見本 80..110mm', crop(bw, fx + 78, fy + 6, fx + 112, fy + 54, dpi)))
    tiles.append((f'{dpi}dpi 網点30% 60線45度', crop(bw, fx + 5, fy + 120, fx + 25, fy + 135, dpi)))
    tiles.append((f'{dpi}dpi 文字', crop(bw, fx + 5, fy + 99, fx + 60, fy + 112, dpi)))
Hs = 360
canvas = []
font = ImageFont.truetype(FONT, 14)
for title, t in tiles:
    s = Hs / t.shape[0]
    im = Image.fromarray(t).convert('L').resize((max(1, int(t.shape[1] * s)), Hs), Image.NEAREST)
    box = Image.new('L', (im.width, Hs + 20), 255)
    box.paste(im, (0, 20)); ImageDraw.Draw(box).text((2, 2), title, font=font, fill=0)
    canvas.append(box)
W_total = sum(c.width + 8 for c in canvas)
sheet = Image.new('L', (W_total, Hs + 20), 200)
x = 0
for c in canvas:
    sheet.paste(c, (x, 0)); x += c.width + 8
sheet.save(OUT / 'crops.png')

# ---------- D PDF ----------
mm2pt = lambda mm: mm / 25.4 * 72
D = {}
def pdf_report(path, expect_px):
    r = PdfReader(str(path))
    pg = r.pages[0]
    mb = [float(v) for v in pg.mediabox]
    w_mm, h_mm = (mb[2] - mb[0]) / 72 * 25.4, (mb[3] - mb[1]) / 72 * 25.4
    xo = pg['/Resources']['/XObject']
    im = xo[list(xo.keys())[0]].get_object()
    iw, ih = int(im['/Width']), int(im['/Height'])
    return {'ページ寸法mm': [round(w_mm, 3), round(h_mm, 3)], '画像px': [iw, ih], '画像の実効dpi': [round(iw / (w_mm / 25.4), 2), round(ih / (h_mm / 25.4), 2)],
            'フィルタ': str(im.get('/Filter')), 'ビット数': int(im.get('/BitsPerComponent', 0)), '色空間': str(im.get('/ColorSpace')),
            'ファイルバイト': path.stat().st_size, 'pdfinfoのPage size': next((l for l in subprocess.run(['pdfinfo', str(path)], capture_output=True, text=True).stdout.splitlines() if l.startswith('Page size')), '')}

for dpi in DPIS:
    for kind, src in (('bw_png', f'page_{dpi}_bw.png'), ('bw_g4', f'page_{dpi}_bw_g4.tif'), ('gray', f'page_{dpi}_gray.png'), ('rgb', f'page_{dpi}_rgb.png')):
        # (a) 画像のdpi情報どおりの大きさ  (b) 寸法をmmで明示
        pa = OUT / f'pdf_{dpi}_{kind}_dpi.pdf'
        pa.write_bytes(img2pdf.convert(str(OUT / src)))
        pb = OUT / f'pdf_{dpi}_{kind}_mm.pdf'
        lf = img2pdf.get_layout_fun((img2pdf.mm_to_pt(CANVAS[0]), img2pdf.mm_to_pt(CANVAS[1])))
        pb.write_bytes(img2pdf.convert(str(OUT / src), layout_fun=lf))
        D[f'{dpi}dpi_{kind}'] = {'dpi情報どおり': pdf_report(pa, None), 'mm明示': pdf_report(pb, None)}
# 可逆性：PDFから画像を取り出し、元の2値と比べる
chk = {}
for dpi in DPIS:
    for kind in ('bw_png', 'bw_g4', 'gray', 'rgb'):
        r = PdfReader(str(OUT / f'pdf_{dpi}_{kind}_mm.pdf'))
        imgs = r.pages[0].images
        ex = np.asarray(imgs[0].image)
        src = images[dpi][kind.split('_')[0]]
        if kind.startswith('bw'):
            ex = ex.astype(bool) if ex.dtype == bool else (ex > 127)
        chk[f'{dpi}dpi_{kind}'] = {'抽出画像のモード': imgs[0].image.mode, '元画像と完全一致': bool(ex.shape == src.shape and np.array_equal(ex, src)),
                                 '違う画素数': int((ex != src).sum()) if ex.shape == src.shape else '形が違う'}
D['roundtrip_pypdf'] = chk
# poppler（pdfimages -png）で取り出して比べる（pypdf の結果と別の読み手）
import tempfile
chk2 = {}
for dpi in DPIS:
    for kind in ('bw_png', 'bw_g4', 'gray', 'rgb'):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(['pdfimages', '-png', str(OUT / f'pdf_{dpi}_{kind}_mm.pdf'), td + '/x'], check=True)
            ex = np.asarray(Image.open(td + '/x-000.png'))
        src = images[dpi][kind.split('_')[0]]
        if kind.startswith('bw'):
            ex = ex > 0 if ex.ndim == 2 else ex[..., 0] > 127
        chk2[f'{dpi}dpi_{kind}'] = {'元画像と完全一致': bool(ex.shape == src.shape and np.array_equal(ex, src))}
D['roundtrip_poppler'] = chk2
# pdfimages -list（poppler）
pil = subprocess.run(['pdfimages', '-list', str(OUT / 'pdf_600_bw_g4_mm.pdf')], capture_output=True, text=True).stdout
D['pdfimages_600_g4'] = pil.strip().splitlines()[-1]
pil = subprocess.run(['pdfimages', '-list', str(OUT / 'pdf_600_bw_png_mm.pdf')], capture_output=True, text=True).stdout
D['pdfimages_600_bw_png'] = pil.strip().splitlines()[-1]
# TrimBox・BleedBox を足す
r = PdfReader(str(OUT / 'pdf_600_bw_g4_mm.pdf'))
w = PdfWriter(); w.append_pages_from_reader(r)
pg = w.pages[0]
W_pt, H_pt = float(pg.mediabox.width), float(pg.mediabox.height)
b = mm2pt(BLEED)
pg.bleedbox = RectangleObject([0, 0, W_pt, H_pt])
pg.trimbox = RectangleObject([b, b, W_pt - b, H_pt - b])
with open(OUT / 'pdf_600_bw_g4_boxes.pdf', 'wb') as f:
    w.write(f)
r2 = PdfReader(str(OUT / 'pdf_600_bw_g4_boxes.pdf')).pages[0]
D['TrimBox追加'] = {'trim_mm': [round(float(r2.trimbox.width) / 72 * 25.4, 3), round(float(r2.trimbox.height) / 72 * 25.4, 3)],
                   'media_mm': [round(float(r2.mediabox.width) / 72 * 25.4, 3), round(float(r2.mediabox.height) / 72 * 25.4, 3)]}
# 20ページの原稿のファイルの大きさ（同じページを20回）
pages = [str(OUT / 'page_600_bw_g4.tif')] * 20
(OUT / 'pdf_600_bw_g4_20p.pdf').write_bytes(img2pdf.convert(pages))
pages = [str(OUT / 'page_600_bw.png')] * 20
(OUT / 'pdf_600_bw_png_20p.pdf').write_bytes(img2pdf.convert(pages))
D['20ページ_bytes'] = {'600dpi G4': (OUT / 'pdf_600_bw_g4_20p.pdf').stat().st_size, '600dpi PNG(Flate)': (OUT / 'pdf_600_bw_png_20p.pdf').stat().st_size,
                       '注': '同じページの繰り返し。実際の原稿の絵は網点で大きくなる'}
result['D_pdf'] = D
(OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
for f in ('_grad.png', '_gradbw.png'):
    (OUT / f).unlink(missing_ok=True)
print('done')
