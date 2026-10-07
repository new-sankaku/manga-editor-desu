"""P15 絵柄ごとに、狙ったコマの絵（引き・背景だけ・人物だけ）を作れるか（一覧 1-32・1-33・1-35・1-36）。
プロンプトは部品に分けて組む：画質 ＋ 絵柄 ＋ 狙い ＋ 人物 ＋ 場所。狙いの部品は、その狙いに要る言葉だけにする。
どの条件も seed を3つ変えて作る（偶然できたものと、安定してできるものを分けるため）。
再現に要る情報（モデル・大きさ・手順・seed・プロンプトの全文・制御・後処理）は1枚ごとに gen.json に残す。"""
import io
import json
import pathlib
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
SEEDS = [71, 72, 73]
STEPS, CFG, SAMPLER, SCHED = 25, 5.0, 'euler_ancestral', 'normal'

QUALITY = 'masterpiece, best quality'
STYLES = {
    'tone': ('白黒・トーン', 'manga, monochrome, greyscale, screentone'),
    'pen': ('白黒・ペン線の描き込み', 'monochrome, greyscale, lineart, crosshatching, hatching (texture)'),
    'retro': ('白黒・90年代風', 'monochrome, greyscale, retro artstyle, 1990s (style)'),
    'color': ('カラー・Web向け', 'anime coloring, flat color'),
}
CHARA = '1girl, solo, short black hair, bob cut, glasses, school uniform, blazer, standing'
PLACE = 'city street, buildings'
# 狙い：(名前, 大きさ, 足す言葉, 足す否定の言葉, 人物を入れるか, 場所を入れるか, 背景を抜くか)
TARGETS = {
    'long_yoko': ('横長コマの引き', (1536, 576), 'wide shot, scenery', '', True, True, False),
    'long_tate': ('縦長コマの引き', (576, 1536), 'wide shot, scenery', '', True, True, False),
    'full_std': ('標準コマの全身と余白', (1152, 896), 'full body, wide shot', '', True, True, False),
    'chara_only': ('人物だけ（背景なし）', (832, 1216), 'full body, simple background, white background', 'scenery, building, detailed background', True, False, True),
    'bg_yoko': ('背景だけ・横長', (1536, 576), 'scenery, no humans', '1girl, 1boy, people', False, True, False),
    'bg_tate': ('背景だけ・縦長', (576, 1536), 'scenery, no humans', '1girl, 1boy, people', False, True, False),
    'bg_std': ('背景だけ・標準', (1152, 896), 'scenery, no humans', '1girl, 1boy, people', False, True, False),
}
CUT_MODEL = 'BiRefNet_toonout'  # アニメ絵向けの背景抜き（MIT）


def prompt(style, target):
    _, _, add, _, human, place, _ = TARGETS[target]
    parts = [QUALITY, STYLES[style][1], add] + ([CHARA] if human else []) + ([PLACE] if place else [])
    return ', '.join(parts)


def negative(target):
    return ', '.join(x for x in (comfy.NEG, TARGETS[target][3]) if x)


def graph(style, target, seed):
    (w, h), cut = TARGETS[target][1], TARGETS[target][6]
    g = comfy.t2i(prompt(style, target), seed, w, h, steps=STEPS, cfg=CFG, neg=negative(target), sampler=SAMPLER, scheduler=SCHED, prefix='v3poc_p15')
    if cut:
        g['8'] = {'class_type': 'BiRefNetRMBG', 'inputs': {'image': ['6', 0], 'model': CUT_MODEL, 'mask_blur': 0, 'mask_offset': 0,
                                                          'invert_output': False, 'refine_foreground': False, 'background': 'Alpha', 'background_color': '#222222'}}
        g['9'] = {'class_type': 'SaveImage', 'inputs': {'images': ['8', 0], 'filename_prefix': 'v3poc_p15_cut'}}
    return g


def main():
    rec = []
    for style in STYLES:
        for target in TARGETS:
            for s in SEEDS:
                b, t = comfy.run(graph(style, target, s))
                # 出力の順は決まっていないので、透明を持つ方を背景を抜いた絵とする
                alpha = [x for x in b if Image.open(io.BytesIO(x)).mode == 'RGBA']
                plain = [x for x in b if x not in alpha]
                name = f'{style}_{target}_{s}.png'
                (OUT / name).write_bytes(plain[0])
                r = {'file': name, 'style': style, 'target': target, 'seed': s, 'sec': round(t, 1),
                     'ckpt': comfy.CKPT, 'size': TARGETS[target][1], 'steps': STEPS, 'cfg': CFG, 'sampler': SAMPLER, 'scheduler': SCHED,
                     'positive': prompt(style, target), 'negative': negative(target), 'control': None, 'post': None}
                if TARGETS[target][6]:
                    cut = f'{style}_{target}_{s}_cut.png'
                    (OUT / cut).write_bytes(alpha[0])
                    r['post'] = {'node': 'BiRefNetRMBG（ComfyUI-RMBG）', 'model': CUT_MODEL, 'background': 'Alpha', 'file': cut}
                rec.append(r)
                print(name, round(t, 1), flush=True)
    (OUT / 'gen.json').write_text(json.dumps({'styles': {k: {'name': v[0], 'words': v[1]} for k, v in STYLES.items()},
                                              'targets': {k: {'name': v[0], 'size': v[1], 'add': v[2], 'add_negative': v[3], 'human': v[4],
                                                              'place': v[5], 'cut': v[6]} for k, v in TARGETS.items()},
                                              'parts': {'quality': QUALITY, 'chara': CHARA, 'place': PLACE, 'negative_base': comfy.NEG},
                                              'runs': rec}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
