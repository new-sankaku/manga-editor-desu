"""P17 参照画像で顔が揃うか（やり直し。一覧 1-29・1-16・1-20・3-8）。
P09 は参照画像を作ったときと同じキャラの説明をプロンプトにも入れたので、参照画像が効いたのかプロンプトが寄せたのかが分からなかった。
ここでは、キャラの特徴をプロンプトにどこまで書くか（性別だけ／髪だけ／全部）と、参照画像（なし・強さ0.5・0.8）を掛け合わせる。
キャラは2人（特徴が多い女性・男性）。参照画像は、全部の特徴を書いて1枚作った上半身の絵（seed 固定、選び直していない）。
参照画像の部品：IP-Adapter plus SDXL（h94、Apache-2.0）＋ 画像の読み取り CLIP ViT-H-14（MIT）。
顔専用の IP-Adapter FaceID は、顔の読み取りに insightface（非商用）を使うので試さない。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
STYLE = 'masterpiece, best quality, manga, monochrome, greyscale, screentone'
REF_ADD = 'upper body, looking at viewer, simple background, white background'
REF_SEED = 101
CHARAS = {
    'a': {'name': '白髪の三つ編みの女性', 'sex': '1girl, solo',
          'hair': 'white hair, long hair, twin braids',
          'full': 'white hair, long hair, twin braids, red eyes, freckles, star hair ornament, black hoodie, choker'},
    'b': {'name': '眼帯の男性', 'sex': '1boy, solo',
          'hair': 'messy hair, brown hair, short hair',
          'full': 'messy hair, brown hair, short hair, scar on cheek, eyepatch, green jacket, white shirt'},
}
LEVELS = {'sex': '性別だけ', 'hair': '性別＋髪', 'full': '性別＋全部の特徴'}
REFS = {'none': ('参照なし', 0.0), 'ipa05': ('参照 強さ0.5', 0.5), 'ipa08': ('参照 強さ0.8', 0.8)}
SCENES = {'run': 'running, full body, street', 'eat': 'eating bread, sitting, cafeteria, upper body',
          'side': 'from side, profile, looking at window, upper body'}
SEEDS = [21, 22, 23]
IPA = {'model': 'ip_adapter_plus_sdxl_vit-h\\ip_adapter.bin', 'clip_vision': 'clip_vision_h.safetensors', 'weight_type': 'linear',
       'combine_embeds': 'concat', 'start_at': 0.0, 'end_at': 1.0, 'embeds_scaling': 'V only'}


def chara_words(c, level):
    ch = CHARAS[c]
    return ch['sex'] if level == 'sex' else f"{ch['sex']}, {ch[level]}"


def prompt(c, level, scene):
    return f'{STYLE}, {chara_words(c, level)}, {SCENES[scene]}'


def graph(pos, seed, ref=None, weight=0.0):
    g = comfy.t2i(pos, seed, prefix='v3poc_p17')
    if ref:
        g['30'] = {'class_type': 'IPAdapterModelLoader', 'inputs': {'ipadapter_file': IPA['model']}}
        g['31'] = {'class_type': 'CLIPVisionLoader', 'inputs': {'clip_name': IPA['clip_vision']}}
        g['32'] = {'class_type': 'LoadImage', 'inputs': {'image': ref}}
        g['33'] = {'class_type': 'IPAdapterAdvanced', 'inputs': {'model': ['1', 0], 'ipadapter': ['30', 0], 'image': ['32', 0], 'clip_vision': ['31', 0],
                                                               'weight': weight, 'weight_type': IPA['weight_type'], 'combine_embeds': IPA['combine_embeds'],
                                                               'start_at': IPA['start_at'], 'end_at': IPA['end_at'], 'embeds_scaling': IPA['embeds_scaling']}}
        g['5']['inputs']['model'] = ['33', 0]
    return g


def main():
    rec, refs = [], {}
    for c in CHARAS:
        pos = f"{STYLE}, {chara_words(c, 'full')}, {REF_ADD}"
        b, t = comfy.run(graph(pos, REF_SEED))
        (OUT / f'ref_{c}.png').write_bytes(b[0])
        refs[c] = {'file': f'ref_{c}.png', 'positive': pos, 'seed': REF_SEED}
        up = comfy.upload(str(OUT / f'ref_{c}.png'), f'v3poc_p17_ref_{c}.png')
        for level in LEVELS:
            for rk, (_, w) in REFS.items():
                for sc in SCENES:
                    for s in SEEDS:
                        name = f'{c}_{level}_{rk}_{sc}_{s}.png'
                        p = prompt(c, level, sc)
                        b, t = comfy.run(graph(p, s, up if w else None, w))
                        (OUT / name).write_bytes(b[0])
                        rec.append({'file': name, 'chara': c, 'level': level, 'ref': rk, 'weight': w, 'scene': sc, 'seed': s,
                                    'sec': round(t, 1), 'positive': p})
                        print(name, round(t, 1), flush=True)
    (OUT / 'gen.json').write_text(json.dumps({'ckpt': comfy.CKPT, 'negative': comfy.NEG, 'steps': 25, 'cfg': 5.0, 'sampler': 'euler_ancestral',
                                              'scheduler': 'normal', 'size': [832, 1216], 'ipadapter': IPA, 'charas': CHARAS, 'levels': LEVELS,
                                              'refs_modes': {k: v[0] for k, v in REFS.items()}, 'scenes': SCENES, 'refs': refs, 'runs': rec},
                                             ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
