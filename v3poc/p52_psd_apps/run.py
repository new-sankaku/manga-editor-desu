"""P52 PSD を別のソフトで開く（一覧 5-14 の残り。P36 の続き）。
確かめること: ag-psd で書いた層つき PSD（紙・隠せるグループ・乗算・不透明度・ベタ・線画・縦書きの文字層）を
  GIMP（apt 2.10、script-fu の batch で層を読み出す）・ImageMagick（convert/identify）・Krita（apt、offscreen の書き出しと .kra の中身）で開いたとき、
  層の数・名前・グループ・不透明度・合成モード・隠す・文字層・合成結果がどう読めるか。
  合成結果は、Photoshop と同じ意味（グループは通過）で numpy が作った期待値と比べる。
  Photoshop と CLIP STUDIO はこの環境に無いので未検証。
P36 の write.js は P20 の画像（リポジトリに出力が無い）を使うので、層の画素はこの run.py が合成の絵で作る。
使い方: npm install（ag-psd 31.0.2・pngjs 7.0.0）→ python run.py（numpy・pillow が要る。gimp・convert・krita を使う）。out/result.json に結果。
"""
import json
import pathlib
import re
import shutil
import subprocess
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
LAY = OUT / 'layers'
LAY.mkdir(parents=True, exist_ok=True)
W, H = 600, 800
FONT = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'


def rgba(arr):
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


def make_layers():
    paper = np.full((H, W, 4), 255, np.uint8)
    color = np.zeros((H, W, 4), np.uint8)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([60, 80, 300, 360], fill=(255, 190, 170, 255))      # 肌色
    d.rectangle([320, 120, 540, 420], fill=(150, 190, 255, 255))   # 青
    color = np.asarray(im).copy()
    tone = np.zeros((H, W, 4), np.uint8)
    yy, xx = np.mgrid[0:H, 0:W]
    dots = ((xx % 8 - 4) ** 2 + (yy % 8 - 4) ** 2) < 6
    mask = (yy > 440) & (yy < 700) & (xx > 40) & (xx < 400)
    tone[..., 3] = (dots & mask) * 255
    beta = np.zeros((H, W, 4), np.uint8)
    beta[720:780, 40:560, 3] = 255
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([40, 60, 560, 700], outline=(0, 0, 0, 255), width=3)
    d.line([40, 440, 560, 440], fill=(0, 0, 0, 255), width=2)
    d.line([300, 60, 300, 440], fill=(0, 0, 0, 255), width=1)
    line = np.asarray(im).copy()
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 40)
    for i, ch in enumerate('きょうは'):
        d.text((W - 110, 80 + i * 46), ch, font=f, fill=(0, 0, 0, 255))
    for i, ch in enumerate('早いね'):
        d.text((W - 160, 100 + i * 46), ch, font=f, fill=(0, 0, 0, 255))
    text = np.asarray(im).copy()
    L = dict(paper=paper, color=color, tone=tone, beta=beta, line=line, text=text)
    for k, v in L.items():
        rgba(v).save(LAY / f'{k}.png')
    return L


def over(base, layer, opacity=1.0, mode='normal'):
    """base は不透明なRGB(float 0..1)、layer は RGBA uint8。"""
    a = layer[..., 3:4].astype(np.float32) / 255 * opacity
    cs = layer[..., :3].astype(np.float32) / 255
    blend = base * cs if mode == 'multiply' else cs
    return base * (1 - a) + blend * a


def expected(L, visible):
    b = L['paper'][..., :3].astype(np.float32) / 255
    if visible:
        b = over(b, L['color'], 1.0, 'multiply')   # グループは通過：下の紙に乗算
    b = over(b, L['tone'], 0.6 if visible else 1.0)
    b = over(b, L['beta']); b = over(b, L['line']); b = over(b, L['text'])
    return (b * 255 + .5).astype(np.uint8)


def diff(a, b):
    a = np.asarray(Image.open(a).convert('RGB')).astype(int) if not isinstance(a, np.ndarray) else a.astype(int)
    b = np.asarray(Image.open(b).convert('RGB')).astype(int) if not isinstance(b, np.ndarray) else b.astype(int)
    if a.shape != b.shape:
        return {'形が違う': [list(a.shape), list(b.shape)]}
    d = np.abs(a - b)
    return {'平均差(0..255)': round(float(d.mean()), 3), '差が16超の画素の割合': round(float((d.max(2) > 16).mean()), 4)}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


L = make_layers()
for vis in (False, True):
    e = expected(L, vis)
    Image.fromarray(np.dstack([e, np.full(e.shape[:2], 255, np.uint8)]), 'RGBA').save(LAY / ('expected_visible.png' if vis else 'expected_hidden.png'))
    Image.fromarray(e, 'RGB').save(OUT / ('expected_visible_rgb.png' if vis else 'expected_hidden_rgb.png'))
node = run(['node', str(HERE / 'write.js')])
result = {'node_write': node.stdout.strip().splitlines(), 'node_err': node.stderr.strip()[:300]}
files = {'layers': OUT / 'layers.psd', 'layers_visible': OUT / 'layers_visible.psd'}
files['p36_既存'] = HERE.parent / 'p36_psd' / 'out' / 'layers.psd'
result['psd_bytes'] = {k: v.stat().st_size for k, v in files.items() if v.exists()}

# ---------- GIMP ----------
SCM = r'''
(define (kind-of l)
  (cond ((= (car (gimp-item-is-group l)) 1) "group")
        ((= (car (gimp-item-is-text-layer l)) 1) "text")
        (else "layer")))
(define (mode-name m)
  (cond ((= m LAYER-MODE-NORMAL) "NORMAL") ((= m LAYER-MODE-MULTIPLY) "MULTIPLY") ((= m LAYER-MODE-PASS-THROUGH) "PASS-THROUGH")
        ((= m LAYER-MODE-NORMAL-LEGACY) "NORMAL-LEGACY") ((= m LAYER-MODE-MULTIPLY-LEGACY) "MULTIPLY-LEGACY") (else m)))
(define (dump-item l depth port)
  (let* ((name (car (gimp-item-get-name l)))
         (kind (kind-of l)))
    (write (list depth name kind (car (gimp-item-get-visible l)) (car (gimp-layer-get-opacity l)) (mode-name (car (gimp-layer-get-mode l)))
                 (car (gimp-drawable-width l)) (car (gimp-drawable-height l))) port)
    (newline port)
    (if (equal? kind "text")
        (begin (write (list "text-content" (car (gimp-text-get-text l)) "font" (car (gimp-text-get-font l))) port) (newline port)))
    (if (equal? kind "group")
        (let* ((ch (gimp-item-get-children l)) (n (car ch)) (v (cadr ch)) (i 0))
          (while (< i n) (dump-item (vector-ref v i) (+ depth 1) port) (set! i (+ i 1)))))))
(define (go in out-txt out-png)
  (let* ((image (car (gimp-file-load RUN-NONINTERACTIVE in in)))
         (port (open-output-file out-txt))
         (ls (gimp-image-get-layers image)) (n (car ls)) (v (cadr ls)) (i 0))
    (write (list "image" (car (gimp-image-width image)) (car (gimp-image-height image)) "top-level" n) port) (newline port)
    (while (< i n) (dump-item (vector-ref v i) 0 port) (set! i (+ i 1)))
    (close-output-port port)
    (let* ((flat (car (gimp-image-merge-visible-layers image CLIP-TO-IMAGE))))
      (file-png-save RUN-NONINTERACTIVE image flat out-png out-png 0 9 0 0 0 0 0))
    (gimp-image-delete image)))
'''
(OUT / 'gimp_dump.scm').write_text(SCM)
gimp = {}
for k, f in files.items():
    if not f.exists():
        continue
    txt, png = OUT / f'gimp_{k}.txt', OUT / f'gimp_{k}.png'
    for p in (txt, png):
        p.unlink(missing_ok=True)
    # 文字列の中の " は使わない。パスは絶対パス
    expr = f'(begin (load "{OUT}/gimp_dump.scm") (go "{f}" "{txt}" "{png}"))'
    r = run(['gimp', '-i', '-d', '-f', '-b', expr, '-b', '(gimp-quit 0)'], timeout=300)
    entry = {'rc': r.returncode, 'stderr_tail': (r.stderr or '')[-300:]}
    if txt.exists():
        entry['dump'] = txt.read_text().strip().splitlines()
    if png.exists():
        if k != 'p36_既存':
            entry['composite_vs_期待値'] = diff(png, OUT / ('expected_visible_rgb.png' if 'visible' in k else 'expected_hidden_rgb.png'))
    gimp[k] = entry
result['GIMP'] = {'version': run(['gimp', '--version']).stdout.strip(), **gimp}

# ---------- ImageMagick ----------
UTF8 = {**__import__('os').environ, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
im = {'version': run(['convert', '-version']).stdout.splitlines()[0]}
for k, f in files.items():
    if not f.exists():
        continue
    ident = run(['identify', '-format', '%[scene]|%[label]|%wx%h|%[compose]|%[page]|%[colorspace]\\n', str(f)], env=UTF8)
    layers = [l for l in ident.stdout.strip().splitlines()]
    ops = re.findall(r'psd:layer\.opacity: *(\d+)', run(['identify', '-verbose', str(f)], env=UTF8).stdout)
    out_png = OUT / f'im_{k}_flatten.png'
    run(['convert', str(f), '-background', 'white', '-layers', 'flatten', str(out_png)])
    verbose = run(['identify', '-verbose', str(f)], env=UTF8).stdout
    props = sorted(set(re.findall(r'^\s+(psd:[^:]+|label|photoshop:[^:]+):', verbose, re.M)))
    im[k] = {'psd:layer.opacityの値(層ごと)': ops, 'identifyの層の行数': len(layers), 'identifyの行': layers, 'プロパティ名': props,
             'flatten_vs_期待値': diff(out_png, OUT / ('expected_visible_rgb.png' if 'visible' in k else 'expected_hidden_rgb.png')) if out_png.exists() and k != 'p36_既存' else None,
             'stderr': run(['identify', str(f)]).stderr[:200]}
    # 層ごとの書き出しの有無（[0] は合成画像）
    out0 = OUT / f'im_{k}_0.png'
    run(['convert', f'{f}[0]', str(out0)])
    im[k]['[0]_vs_期待値'] = diff(out0, OUT / ('expected_visible_rgb.png' if 'visible' in k else 'expected_hidden_rgb.png')) if out0.exists() and k != 'p36_既存' else None
result['ImageMagick'] = im

# ---------- Krita ----------
# Krita は offscreen では xcb を探して起動しないので、xvfb-run（仮想画面）で動かす
kr = {'version': run(['dpkg-query', '-W', '-f', '${Version}', 'krita']).stdout.strip(), '起動': 'xvfb-run -a krita --export'}
env = {**__import__('os').environ, 'XDG_RUNTIME_DIR': '/tmp/runtime-root'}
for k, f in files.items():
    if not f.exists():
        continue
    kra, png = OUT / f'krita_{k}.kra', OUT / f'krita_{k}.png'
    for p in (kra, png):
        p.unlink(missing_ok=True)
    r1 = run(['xvfb-run', '-a', 'krita', '--export', '--export-filename', str(png), str(f)], env=env, timeout=300)
    r2 = run(['xvfb-run', '-a', 'krita', '--export', '--export-filename', str(kra), str(f)], env=env, timeout=300)
    entry = {'png_rc': r1.returncode, 'kra_rc': r2.returncode, 'stderr_tail': (r1.stderr + r2.stderr)[-300:]}
    if png.exists():
        if k != 'p36_既存':
            entry['composite_vs_期待値'] = diff(png, OUT / ('expected_visible_rgb.png' if 'visible' in k else 'expected_hidden_rgb.png'))
    if kra.exists():
        with zipfile.ZipFile(kra) as z:
            xml = z.read('maindoc.xml').decode()
            entry['kra内のファイル'] = [n for n in z.namelist() if 'layer' in n.lower() or n.endswith('.xml')][:20]
        entry['layers'] = []
        for m in re.finditer(r'<layer\b[^>]*>', xml):
            t = m.group(0)
            g = lambda a: (re.search(a + r'="([^"]*)"', t) or [None, None])[1]
            entry['layers'].append({'name': g('name'), 'nodetype': g('nodetype'), 'opacity': g('opacity'), 'compositeop': g('compositeop'), 'visible': g('visible')})
        entry['layers_group_nesting_in_xml'] = bool(re.search(r'<layer[^>]*nodetype="grouplayer"[^>]*>\s*<layers>', xml))
    kr[k] = entry
result['Krita'] = kr
result['未検証'] = ['Photoshop', 'CLIP STUDIO PAINT（この環境に無い）']
(OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=1)[:6000])
