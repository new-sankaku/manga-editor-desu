"""画像を並べた一覧画像を作る（目で判定するため）。行ごとに見出し、各こまに番号を付ける。"""
from PIL import Image, ImageDraw, ImageFont


def font(sz):
    for f in ('C:/Windows/Fonts/meiryo.ttc', 'C:/Windows/Fonts/msgothic.ttc'):
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            continue
    raise RuntimeError('日本語フォントが見つかりません')


def opaque(im):
    """透明のある絵は薄い灰色の上に重ねる（抜けた所が分かるように）。"""
    if im.mode != 'RGBA':
        return im.convert('RGB')
    bg = Image.new('RGB', im.size, (200, 205, 210))
    bg.paste(im, mask=im.getchannel('A'))
    return bg


def sheet(rows, out, tw=150, label_w=150):
    """rows: [(見出し, [(画像パス, 小見出し), ...]), ...]"""
    ims = [[(opaque(Image.open(p)), cap) for p, cap in r] for _, r in rows]
    th = max(int(tw * im.height / im.width) for r in ims for im, _ in r)
    cols = max(len(r) for r in ims)
    W, H = label_w + cols * (tw + 4), len(rows) * (th + 22) + 4
    S = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(S)
    f, fs = font(15), font(12)
    for i, ((title, _), r) in enumerate(zip(rows, ims)):
        y = 4 + i * (th + 22)
        d.text((6, y + th // 2 - 8), title, fill='black', font=f)
        for j, (im, cap) in enumerate(r):
            x = label_w + j * (tw + 4)
            t = im.resize((tw, int(tw * im.height / im.width)))
            S.paste(t, (x, y))
            d.text((x + 2, y + th + 2), cap, fill='#333', font=fs)
    S.save(out)
