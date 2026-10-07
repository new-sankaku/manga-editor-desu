"""P19 表情を言葉で描き分けられるか（一覧 1-6・1-20）。
喜・怒・哀・驚の4種を、弱・中・強の3段の言葉で作り、狙いの強さの順に並ぶか、極端すぎ・弱すぎにならないかを見る。
比べるために無表情も作る。参照画像の部品を足すと表情が消えて似通うか（1-20）を、強の段と無表情で確かめる。
キャラは P17 の2人（全部の特徴の言葉）。絵柄は白黒トーン。各 seed 3つ。"""
import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
_spec = importlib.util.spec_from_file_location('p17', HERE.parent / 'p17_identity2' / 'run.py')
P17 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P17)

SEEDS = [31, 32, 33]
SCENE = 'upper body, looking at viewer, classroom'
NEUTRAL = 'expressionless'
EMOTIONS = {  # 種類 → 弱・中・強の言葉
    'joy': ('喜', ['slight smile', 'smile, happy', 'laughing, open mouth, very happy']),
    'anger': ('怒', ['annoyed, frown', 'angry', 'furious, shouting, clenched teeth']),
    'sad': ('哀', ['sad, downcast eyes', 'sad, teary eyes', 'crying, tears, sobbing']),
    'surprise': ('驚', ['slightly surprised', 'surprised, open mouth', 'shocked, wide-eyed, gasping']),
}
IPA_WEIGHT = 0.5


def prompt(c, words):
    return f'{P17.STYLE}, {P17.chara_words(c, "full")}, {words}, {SCENE}'


def jobs():
    """(名前, キャラ, 種類, 段, 言葉, 参照)。段 0 は無表情。"""
    for c in P17.CHARAS:
        yield (f'{c}_neutral_0', c, 'neutral', 0, NEUTRAL, False)
        yield (f'{c}_neutral_0_ipa', c, 'neutral', 0, NEUTRAL, True)
        for e, (_, ws) in EMOTIONS.items():
            for i, w in enumerate(ws, 1):
                yield (f'{c}_{e}_{i}', c, e, i, w, False)
            yield (f'{c}_{e}_3_ipa', c, e, 3, ws[2], True)


def main():
    refs = {c: comfy.upload(str(HERE.parent / 'p17_identity2' / 'out' / f'ref_{c}.png'), f'v3poc_p19_ref_{c}.png') for c in P17.CHARAS}
    rec = []
    for name, c, e, lv, w, ipa in jobs():
        for s in SEEDS:
            f = f'{name}_{s}.png'
            pos = prompt(c, w)
            if not (OUT / f).exists():
                b, t = comfy.run(P17.graph(pos, s, refs[c] if ipa else None, IPA_WEIGHT if ipa else 0.0))
                (OUT / f).write_bytes(b[0])
                print(f, round(t, 1), flush=True)
            rec.append({'file': f, 'chara': c, 'emotion': e, 'level': lv, 'words': w, 'ref': ipa, 'seed': s, 'positive': pos})
    (OUT / 'gen.json').write_text(json.dumps({
        'ckpt': comfy.CKPT, 'size': [832, 1216], 'steps': 25, 'cfg': 5.0, 'sampler': 'euler_ancestral', 'scheduler': 'normal',
        'negative': comfy.NEG, 'scene': SCENE, 'neutral': NEUTRAL, 'emotions': {k: {'name': v[0], 'levels': v[1]} for k, v in EMOTIONS.items()},
        'charas': P17.CHARAS, 'ipadapter': {**P17.IPA, 'weight': IPA_WEIGHT},
        'refs': {c: f'../p17_identity2/out/ref_{c}.png' for c in P17.CHARAS}, 'runs': rec}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
