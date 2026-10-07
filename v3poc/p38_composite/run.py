"""P38 人物と背景の重ね方を画素の処理で作れるか（一覧 1-23）。生成はしない。
①白フチ：人物の切り抜き（P16 の *_cut.png）の形を数画素ふくらませて白で塗り、人物の下に敷く。
  背景の線が人物の線に重ならず、黒い背景（ベタ）の上でも人物の輪郭が残るかを、白フチなしと並べて目で見る。
②遠近の線の太さ：3D から描いた部屋の線（P18 の aux）を、同じ視点の奥行きの絵で近いところほど太くする。
使い方: python run.py"""
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
P16 = HERE.parent / 'p16_general' / 'out'
P18 = HERE.parent / 'p18_bg_consistency' / 'out' / 'aux'
FUCHI = 9          # 白フチの太さ（画素、元の大きさで）
CHARAS = ['chara_only_girl_none_81', 'chara_only_boy_none_82']
BGS = ['bg_tate_none_street_82', 'bg_tate_none_rural_83']  # P16 の目の判定で狙いどおりだった背景（教室の縦長は3枚とも外れ）
MAX_EXTRA = 4      # 近いところで足す太さ（画素）
TH = 420


def fuchi(cut):
    a = cut.getchannel('A').filter(ImageFilter.MaxFilter(FUCHI * 2 + 1))
    white = Image.new('RGBA', cut.size, (255, 255, 255, 0))
    white.putalpha(a)
    return white


def place(bg, cut, with_fuchi):
    """人物を背景の下寄せに、背景の幅の9割の大きさで置く。"""
    s = bg.width * 0.9 / cut.width
    c = cut.resize((round(cut.width * s), round(cut.height * s)), Image.LANCZOS)
    x, y = (bg.width - c.width) // 2, bg.height - c.height
    out = bg.convert('RGBA').copy()
    if with_fuchi:
        f = fuchi(cut).resize(c.size, Image.LANCZOS)
        out.alpha_composite(f, (x, max(y, 0)))
    out.alpha_composite(c, (x, max(y, 0)))
    return out.convert('RGB')


def lab(im, text):
    w = round(im.width * TH / im.height)
    im = im.resize((w, TH), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 14], fill='white')
    d.text((2, 1), text, fill='black')
    return im


def row(ims, path):
    out = Image.new('RGB', (sum(i.width + 4 for i in ims), TH), 'white')
    x = 0
    for i in ims:
        out.paste(i, (x, 0))
        x += i.width + 4
    out.save(path)


def depth_lines():
    line = np.asarray(Image.open(P18 / 'room_back_line.png').convert('L'))
    depth = np.asarray(Image.open(P18 / 'room_back_depth.png').convert('L')).astype(np.float32)
    near = (depth - depth.min()) / max(depth.max() - depth.min(), 1)  # 明るいほど近い
    ink = line < 128
    out = ink.copy()
    for k in range(1, MAX_EXTRA + 1):
        grown = np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * k + 1))) > 0
        out |= grown & (near >= k / (MAX_EXTRA + 1))
    res = Image.fromarray(np.where(out, 0, 255).astype(np.uint8))
    res.save(OUT / 'room_back_line_depth.png')
    row([lab(Image.open(P18 / 'room_back_line.png'), 'line (uniform)'), lab(Image.open(P18 / 'room_back_depth.png'), 'depth (bright=near)'),
         lab(res, 'near lines thicker')], OUT / 'sheet_depth_lines.png')


def main():
    for c, b in zip(CHARAS, BGS):
        cut = Image.open(P16 / f'{c}_cut.png').convert('RGBA')
        bg = Image.open(P16 / f'{b}.png').convert('RGB')
        black = Image.new('RGB', bg.size, 'black')
        ims = [lab(place(bg, cut, False), 'no fuchi'), lab(place(bg, cut, True), f'white fuchi {FUCHI}px'),
               lab(place(black, cut, False), 'on black, no fuchi'), lab(place(black, cut, True), 'on black, fuchi')]
        row(ims, OUT / f'sheet_{c}.png')
    depth_lines()


if __name__ == '__main__':
    main()
