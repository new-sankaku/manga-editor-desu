"""P22 頼んでいないフキダシと文字を、否定の言葉で防げるか・検出器で見つけられるか（一覧 1-22・3-15、課題277・282）。
会話・叫ぶ・掲示のある場所の3種 × 否定の言葉（なし／あり）× seed 8。
見つける側は、文字の検出器（dghs-imgutils の detect_text）と MagiV2 の文字の枠を、目の判定と突き合わせる（analyze.py）。
使い方: python run.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402
import jobs  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
BASE = 'masterpiece, best quality, manga, monochrome, greyscale, screentone'
SCENES = {
    'talk': '2girls, conversation, talking, open mouth, upper body, classroom',
    'shout': '1boy, solo, shouting, angry, upper body, street',
    'board': '1girl, solo, standing, full body, train station, signboard',
}
NEG_ADD = 'speech bubble, text, english text, japanese text, letters, watermark, sign text'
SEEDS = list(range(61, 69))


def main():
    js = []
    for sc, w in SCENES.items():
        for neg in ('base', 'neg'):
            for s in SEEDS:
                p = f'{BASE}, {w}'
                n = comfy.NEG if neg == 'base' else f'{comfy.NEG}, {NEG_ADD}'
                js.append({'file': f'{sc}_{neg}_{s}.png', 'scene': sc, 'neg_mode': neg, 'seed': s, 'prompt': p, 'neg': n,
                           'graph': comfy.t2i(p, s, neg=n, prefix='v3poc_p22')})
    jobs.run_jobs(OUT, js, {'scenes': SCENES, 'neg_add': NEG_ADD})


if __name__ == '__main__':
    main()
