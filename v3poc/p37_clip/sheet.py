"""P37 見切れを「人物の枠がコマの端に接するか」で判定できるか（一覧 1-9・3-12）。
P02 の全身が入るはずの指示（全身・横から・後ろから・二人・かなり引き）の40枚に、人物の検出枠（P02 の detect.json）を描いた一覧を作る。
目の判定（頭か足が画面の外に切れているか）は out/labels.json に人が付け、analyze.py で枠の接し方と突き合わせる。
使い方: python sheet.py"""
import json
import pathlib

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
P02 = HERE.parent / 'p02_instruction' / 'out'
OUT = HERE / 'out'
KINDS = ['full_body', 'from_side', 'from_behind', 'two_people', 'very_wide']
TH = 300


def main():
    det = {x['file']: x for x in json.loads((P02 / 'detect.json').read_text(encoding='utf-8'))}
    for k in KINDS:
        files = sorted(f for f in det if f.startswith(k + '_'))
        ims = []
        for f in files:
            im = Image.open(P02 / f).convert('RGB')
            d = ImageDraw.Draw(im)
            for p in det[f]['persons']:
                d.rectangle([p['x0'], p['y0'], p['x1'], p['y1']], outline='red', width=4)
            w = round(im.width * TH / im.height)
            im = im.resize((w, TH))
            ImageDraw.Draw(im).rectangle([0, 0, w, 14], fill='white')
            ImageDraw.Draw(im).text((2, 1), f.replace('.png', ''), fill='black')
            ims.append(im)
        out = Image.new('RGB', (sum(i.width + 4 for i in ims), TH), 'white')
        x = 0
        for i in ims:
            out.paste(i, (x, 0))
            x += i.width + 4
        out.save(OUT / f'sheet_{k}.png')


if __name__ == '__main__':
    main()
