"""P8 ネームのラフ（棒人間とフキダシの丸）を渡したとき、人物の位置とフキダシの場所が保たれるか（一覧 1-25）。
制御の部品2種 × 線の向き（黒地に白線・白地に黒線） × 強さ2段 × seed3。制御なしを対照にする。
人物の位置は検出器で、フキダシの中の空き具合は暗い画素の割合で測る（測定は analyze.py）。"""
import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
W, H = 832, 1216
FIG = (150, 430, 350, 1170)      # 棒人間の外枠
BAL = (500, 60, 800, 420)        # フキダシの丸
POS = 'masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, solo, short black bob hair, glasses, school blazer, red necktie, full body, standing, street'
CNS = {'t2i_sketch': 't2i-adapter-sketch-sdxl-1.0\\diffusion_pytorch_model.safetensors',
       'sai_sketch': 'sd_control_collection\\sai_xl_sketch_256lora.safetensors'}
SEEDS = [11, 12, 13]


def rough():
    im = Image.new('L', (W, H), 255)
    d = ImageDraw.Draw(im)
    cx = 250
    d.ellipse((cx - 60, 440, cx + 60, 560), outline=0, width=6)       # 頭
    d.line((cx, 560, cx, 850), fill=0, width=6)                        # 胴
    d.line((cx, 620, cx - 90, 780), fill=0, width=6)                   # 腕
    d.line((cx, 620, cx + 90, 760), fill=0, width=6)
    d.line((cx, 850, cx - 70, 1160), fill=0, width=6)                  # 脚
    d.line((cx, 850, cx + 70, 1160), fill=0, width=6)
    d.ellipse(BAL, outline=0, width=6)                                 # フキダシ
    d.line((0, 1000, W, 1000), fill=0, width=3)                        # 地面の線
    im.save(OUT / 'rough_bw.png')                  # 白地に黒線
    ImageOps.invert(im).save(OUT / 'rough_wb.png')  # 黒地に白線


def graph(seed, cn=None, img=None, strength=1.0):
    g = comfy.t2i(POS, seed, W, H, prefix='v3poc_p08')
    if cn:
        g['20'] = {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': CNS[cn]}}
        g['21'] = {'class_type': 'LoadImage', 'inputs': {'image': img}}
        g['22'] = {'class_type': 'ControlNetApplyAdvanced', 'inputs': {'positive': ['2', 0], 'negative': ['3', 0], 'control_net': ['20', 0], 'image': ['21', 0],
                                                                     'strength': strength, 'start_percent': 0.0, 'end_percent': 1.0}}
        g['5']['inputs']['positive'] = ['22', 0]
        g['5']['inputs']['negative'] = ['22', 1]
    return g


def main():
    rough()
    up = {k: comfy.upload(str(OUT / f'rough_{k}.png'), f'v3poc_p08_rough_{k}.png') for k in ('bw', 'wb')}
    rec = []
    for s in SEEDS:
        b, t = comfy.run(graph(s))
        (OUT / f'none_{s}.png').write_bytes(b[0])
        rec.append({'file': f'none_{s}.png', 'cn': None, 'sec': round(t, 1)})
    for cn in CNS:
        for pol in ('wb', 'bw'):
            for st in (0.6, 1.0):
                for s in SEEDS:
                    name = f'{cn}_{pol}_{st}_{s}.png'
                    b, t = comfy.run(graph(s, cn, up[pol], st))
                    (OUT / name).write_bytes(b[0])
                    rec.append({'file': name, 'cn': cn, 'polarity': pol, 'strength': st, 'seed': s, 'sec': round(t, 1)})
                    print(name, round(t, 1), flush=True)
    (OUT / 'gen.json').write_text(json.dumps({'FIG': FIG, 'BAL': BAL, 'runs': rec}, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
