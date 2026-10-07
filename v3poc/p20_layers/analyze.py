"""P20 の結果を数える（一覧 1-27）。
手1：トーンの絵を「線（取り出した線）」「ベタ（濃い黒の塊）」「トーン（中間の灰色）」の3層に分け、白地に重ね直して元の絵とどれだけ違うかを測る。
手2：線画の絵が線画になっているか（中間の灰色の割合）と、線画から作ったトーン・カラーの絵が、線画の線の上に暗い線を持っているか（線の保たれ方）を測る。
見るための一覧は out/sheet_split_*.png（手1）と out/sheet_line_*.png（手2）。数は out/result.json。
使い方: python analyze.py"""
import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
SCENES = ['a_desk', 'b_run', 'bg_room']
SEEDS = [41, 42, 43]
BETA = 50        # これより暗い画素の塊はベタ
WHITE = 215      # これより明るい画素は紙の白
LINE_ON = 128    # 取り出した線の画像（黒地に白線）で、これより明るい画素を線とみなす
DARK = 110       # 線画の線の上で、作った絵がこれより暗ければ線が保たれたとみなす
TH = 280         # 一覧の1枚の高さ


def grey(p, size=None):
    im = Image.open(p).convert('L')
    return np.asarray(im.resize(size, Image.LANCZOS) if size and im.size != size else im).astype(np.float32)


def split(tone, line):
    """手1。線・ベタ・トーンの3層（どれも白地に黒、透明のところは255）と、重ね直した絵。"""
    is_line = line >= LINE_ON
    is_beta = (tone < BETA) & ~is_line
    is_tone = (tone >= BETA) & (tone < WHITE) & ~is_line
    l_layer = np.where(is_line, np.minimum(tone, 80), 255)
    b_layer = np.where(is_beta, 0, 255)
    t_layer = np.where(is_tone, tone, 255)
    recomposed = np.minimum(np.minimum(l_layer, b_layer), t_layer)
    return l_layer, b_layer, t_layer, recomposed, {'line': float(is_line.mean()), 'beta': float(is_beta.mean()), 'tone': float(is_tone.mean())}


def thumb(a, label):
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert('RGB') if isinstance(a, np.ndarray) else a.convert('RGB')
    w = round(im.width * TH / im.height)
    im = im.resize((w, TH), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 16], fill='white')
    d.text((3, 2), label, fill='black')
    return im


def row(ims):
    w = sum(i.width for i in ims) + 4 * (len(ims) - 1)
    out = Image.new('RGB', (w, TH), 'white')
    x = 0
    for i in ims:
        out.paste(i, (x, 0))
        x += i.width + 4
    return out


def stack(rows, path):
    w = max(r.width for r in rows)
    out = Image.new('RGB', (w, sum(r.height + 6 for r in rows)), 'white')
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height + 6
    out.save(path)


def main():
    res = {'split': [], 'line': []}
    for sc in SCENES:
        rows1, rows2 = [], []
        for s in SEEDS:
            tone = grey(OUT / f'{sc}_tone_{s}.png')
            size = (tone.shape[1], tone.shape[0])
            for pre in ('m2a', 'ani'):
                line = grey(OUT / f'{sc}_tone_{s}_x{pre}.png', size)
                l_, b_, t_, rc, frac = split(tone, line)
                err = float(np.abs(rc - tone).mean())
                res['split'].append({'file': f'{sc}_tone_{s}.png', 'extractor': pre, 'recompose_mean_abs_error': round(err, 1), **{k: round(v, 3) for k, v in frac.items()}})
                if pre == 'm2a':
                    rows1.append(row([thumb(tone, f'tone {s}'), thumb(255 - line, 'line m2a'), thumb(b_, 'beta'), thumb(t_, 'tone'), thumb(rc, f'recomposed err {err:.1f}')]))
                else:
                    rows1[-1] = row([rows1[-1], thumb(255 - line, 'line ani')])
            ln = grey(OUT / f'{sc}_line_{s}.png')
            mid = float(((ln >= 60) & (ln < 200)).mean())
            on = ln < 100
            r = {'file': f'{sc}_line_{s}.png', 'line_dark_ratio': round(float(on.mean()), 3), 'line_mid_grey_ratio': round(mid, 3)}
            ims = [thumb(ln, f'line {s}')]
            for k in ('line2tone', 'line2color'):
                g = grey(OUT / f'{sc}_{k}_{s}.png')
                kept = float((g[on] < DARK).mean()) if on.any() else 0
                r[f'{k}_line_kept'] = round(kept, 3)
                ims.append(thumb(Image.open(OUT / f'{sc}_{k}_{s}.png'), f'{k} kept {kept:.2f}'))
                if k == 'line2color':
                    col = np.asarray(Image.open(OUT / f'{sc}_{k}_{s}.png').convert('RGB')).copy()
                    col[on] = 0
                    ims.append(thumb(Image.fromarray(col), 'line layer over color'))
            res['line'].append(r)
            rows2.append(row(ims))
        stack(rows1, OUT / f'sheet_split_{sc}.png')
        stack(rows2, OUT / f'sheet_line_{sc}.png')
    for k in ('m2a', 'ani'):
        xs = [r['recompose_mean_abs_error'] for r in res['split'] if r['extractor'] == k]
        res[f'mean_error_{k}'] = round(sum(xs) / len(xs), 1)
    for k in ('line2tone', 'line2color'):
        xs = [r[f'{k}_line_kept'] for r in res['line']]
        res[f'mean_kept_{k}'] = round(sum(xs) / len(xs), 3)
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in res.items() if k.startswith('mean')}, ensure_ascii=False))
    for r in res['line']:
        print(r)


if __name__ == '__main__':
    main()
