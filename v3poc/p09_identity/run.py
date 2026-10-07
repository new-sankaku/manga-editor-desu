"""P9 参照画像1枚で同じキャラに揃うか（一覧 1-29、1-16、1-20、3-8）。
参照＝P2の上半身の1枚。別の場面4種 × seed3 を、文字だけ／参照画像の部品（強さ0.5・0.8）で作る。
別キャラも文字だけで作り、同一キャラ判定（CCIP）で「同じ」と「違う」が分かれるかを見る（測定は analyze.py）。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
REF = HERE.parent / 'p02_instruction' / 'out' / 'upper_body_1001.png'
BASE = 'masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, solo, '
CHARA = 'short black bob hair, glasses, school blazer, red necktie, pleated skirt, '
OTHER = 'long blonde twintails, sailor school uniform, ribbon, '
SCENES = {'run': 'running, full body, street', 'eat': 'eating bread, sitting, cafeteria, upper body',
          'side': 'from side, profile, looking at window, upper body', 'laugh': 'laughing, close-up, park'}
SEEDS = [21, 22, 23]


def graph(pos, seed, ref=None, weight=0.0):
    g = comfy.t2i(pos, seed, prefix='v3poc_p09')
    if ref:
        g['30'] = {'class_type': 'IPAdapterModelLoader', 'inputs': {'ipadapter_file': 'ip_adapter_plus_sdxl_vit-h\\ip_adapter.bin'}}
        g['31'] = {'class_type': 'CLIPVisionLoader', 'inputs': {'clip_name': 'clip_vision_h.safetensors'}}
        g['32'] = {'class_type': 'LoadImage', 'inputs': {'image': ref}}
        g['33'] = {'class_type': 'IPAdapterAdvanced', 'inputs': {'model': ['1', 0], 'ipadapter': ['30', 0], 'image': ['32', 0], 'clip_vision': ['31', 0],
                                                               'weight': weight, 'weight_type': 'linear', 'combine_embeds': 'concat',
                                                               'start_at': 0.0, 'end_at': 1.0, 'embeds_scaling': 'V only'}}
        g['5']['inputs']['model'] = ['33', 0]
    return g


def main():
    ref = comfy.upload(str(REF), 'v3poc_p09_ref.png')
    (OUT / 'ref.png').write_bytes(REF.read_bytes())
    rec = []
    for sc, add in SCENES.items():
        for s in SEEDS:
            for mode, r, w, ch in (('text', None, 0, CHARA), ('ipa05', ref, 0.5, CHARA), ('ipa08', ref, 0.8, CHARA), ('other', None, 0, OTHER)):
                name = f'{sc}_{mode}_{s}.png'
                if (OUT / name).exists():
                    continue
                b, t = comfy.run(graph(BASE + ch + add, s, r, w))
                (OUT / name).write_bytes(b[0])
                rec.append({'file': name, 'scene': sc, 'mode': mode, 'seed': s, 'sec': round(t, 1)})
                print(name, round(t, 1), flush=True)
    (OUT / 'gen.json').write_text(json.dumps(rec, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
