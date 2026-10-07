"""P16 狙いの言葉は、人物と場所を入れ替えても効くか（一覧 1-37）。
P14・P15 は人物1種（眼鏡の女子生徒）・場所1種（街）だけで試したので、結果が「そのプロンプトでは出た」にとどまる。
ここでは P15 と同じ狙いの言葉のまま、人物3種×場所3種に入れ替え、各 seed 3つで作る。絵柄は白黒・トーンだけ。
人物は性別・年齢・服を、場所は屋外の街・屋内・郊外で分けた。"""
import importlib.util
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
_spec = importlib.util.spec_from_file_location('p15', HERE.parent / 'p15_shots' / 'run.py')
P15 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P15)

SEEDS = [81, 82, 83]
STYLE = 'tone'
CHARAS = {
    'girl': ('眼鏡の女子生徒', P15.CHARA),
    'boy': ('パーカーの少年', '1boy, solo, short hair, hoodie, jeans, sneakers, standing'),
    'old': ('背広の老人', '1boy, solo, old man, grey hair, beard, suit, standing'),
}
PLACES = {
    'street': ('街', P15.PLACE),
    'room': ('屋内（教室）', 'classroom, desks, windows'),
    'rural': ('郊外（田んぼと山）', 'countryside, rice field, mountains, utility pole'),
}
SCENE = ['long_yoko', 'long_tate', 'full_std']
BG = ['bg_yoko', 'bg_tate']
CHARA_ONLY = 'chara_only'


def prompt(target, chara, place):
    _, _, add, _, human, has_place, _ = P15.TARGETS[target]
    parts = [P15.QUALITY, P15.STYLES[STYLE][1], add] + ([CHARAS[chara][1]] if human else []) + ([PLACES[place][1]] if has_place else [])
    return ', '.join(parts)


def graph(target, chara, place, seed):
    (w, h), cut = P15.TARGETS[target][1], P15.TARGETS[target][6]
    g = comfy.t2i(prompt(target, chara, place), seed, w, h, steps=P15.STEPS, cfg=P15.CFG, neg=P15.negative(target),
                  sampler=P15.SAMPLER, scheduler=P15.SCHED, prefix='v3poc_p16')
    if cut:
        g['8'] = {'class_type': 'BiRefNetRMBG', 'inputs': {'image': ['6', 0], 'model': P15.CUT_MODEL, 'mask_blur': 0, 'mask_offset': 0,
                                                          'invert_output': False, 'refine_foreground': False, 'background': 'Alpha', 'background_color': '#222222'}}
        g['9'] = {'class_type': 'SaveImage', 'inputs': {'images': ['8', 0], 'filename_prefix': 'v3poc_p16_cut'}}
    return g


def jobs():
    for t in SCENE:
        for c in CHARAS:
            for p in PLACES:
                yield t, c, p
    for t in BG:
        for p in PLACES:
            yield t, None, p
    for c in CHARAS:
        yield CHARA_ONLY, c, None


def main():
    rec = []
    for t, c, p in jobs():
        for s in SEEDS:
            b, sec = comfy.run(graph(t, c, p, s))
            alpha = [x for x in b if Image.open(io.BytesIO(x)).mode == 'RGBA']
            plain = [x for x in b if x not in alpha]
            name = f'{t}_{c or "none"}_{p or "none"}_{s}.png'
            (OUT / name).write_bytes(plain[0])
            r = {'file': name, 'target': t, 'chara': c, 'place': p, 'seed': s, 'sec': round(sec, 1), 'ckpt': comfy.CKPT,
                 'size': P15.TARGETS[t][1], 'positive': prompt(t, c, p), 'negative': P15.negative(t), 'post': None}
            if alpha:
                cut = name[:-4] + '_cut.png'
                (OUT / cut).write_bytes(alpha[0])
                r['post'] = {'model': P15.CUT_MODEL, 'file': cut}
            rec.append(r)
            print(name, round(sec, 1), flush=True)
    (OUT / 'gen.json').write_text(json.dumps({'style': STYLE, 'charas': {k: {'name': v[0], 'words': v[1]} for k, v in CHARAS.items()},
                                              'places': {k: {'name': v[0], 'words': v[1]} for k, v in PLACES.items()},
                                              'steps': P15.STEPS, 'cfg': P15.CFG, 'sampler': P15.SAMPLER, 'scheduler': P15.SCHED,
                                              'runs': rec}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
