"""P24 デフォルメで別人にならないか・参照画像が不鮮明なとき別人にならないか（一覧 1-21、課題146）。
手1：P17 の2人を、特徴の言葉は全部入れたまま、デフォルメの言葉（chibi）で描く。seed 6。
手2：参照画像の部品（IP-Adapter plus 強さ0.5）に、P17 の参照画像をそのまま／ぼかして縮めたものを渡す。seed 3。
判定は同一キャラ判定（CCIP）で P17 の参照画像と比べ、目でも見る（analyze.py）。
使い方: python run.py"""
import importlib.util
import pathlib
import sys

from PIL import Image, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402
import jobs  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
_spec = importlib.util.spec_from_file_location('p17', HERE.parent / 'p17_identity2' / 'run.py')
P17 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P17)
DEFORM = 'chibi, super deformed, full body, standing, classroom'
NORMAL = 'full body, standing, classroom'
REF_SCENE = 'eating bread, sitting, cafeteria, upper body'
SEEDS = [81, 82, 83, 84, 85, 86]
REF_SEEDS = [81, 82, 83]
BLUR = {'scale': 0.25, 'radius': 3}


def blurred(c):
    """参照画像を 1/4 に縮めてぼかし、元の大きさに戻す（不鮮明な参照画像の代わり）。"""
    src = HERE.parent / 'p17_identity2' / 'out' / f'ref_{c}.png'
    dst = OUT / f'ref_{c}_blur.png'
    if not dst.exists():
        im = Image.open(src).convert('RGB')
        w, h = im.size
        small = im.resize((int(w * BLUR['scale']), int(h * BLUR['scale'])), Image.BILINEAR).filter(ImageFilter.GaussianBlur(BLUR['radius']))
        small.resize((w, h), Image.BILINEAR).save(dst)
    return dst


def main():
    OUT.mkdir(exist_ok=True)
    js = []
    for c in P17.CHARAS:
        cw = P17.chara_words(c, 'full')
        for mode, words in (('deform', DEFORM), ('normal', NORMAL)):
            for s in SEEDS:
                p = f'{P17.STYLE}, {cw}, {words}'
                js.append({'file': f'{c}_{mode}_{s}.png', 'chara': c, 'mode': mode, 'seed': s, 'prompt': p,
                           'graph': comfy.t2i(p, s, prefix='v3poc_p24')})
        clean = jobs.upload_once(HERE.parent / 'p17_identity2' / 'out' / f'ref_{c}.png', f'v3poc_p24_ref_{c}.png')
        blur = jobs.upload_once(blurred(c), f'v3poc_p24_ref_{c}_blur.png')
        for mode, ref in (('refclean', clean), ('refblur', blur)):
            for s in REF_SEEDS:
                p = f'{P17.STYLE}, {cw}, {REF_SCENE}'
                js.append({'file': f'{c}_{mode}_{s}.png', 'chara': c, 'mode': mode, 'seed': s, 'prompt': p, 'ref': ref,
                           'graph': P17.graph(p, s, ref, 0.5)})
    jobs.run_jobs(OUT, js, {'deform': DEFORM, 'normal': NORMAL, 'ref_scene': REF_SCENE, 'blur': BLUR, 'ipa_weight': 0.5})


if __name__ == '__main__':
    main()
