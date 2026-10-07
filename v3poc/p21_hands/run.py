"""P21 手と体の崩れがどのくらいの割合で出るか・男性キャラで質が落ちないか（一覧 1-3・1-10・1-8）。
手の見える動作6種 × 女性・男性（それぞれ2人）× seed 3。原寸で手を切り出して目で見る（analyze.py）。
使い方: python run.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402
import jobs  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
BASE = 'masterpiece, best quality, manga, monochrome, greyscale, screentone'
CHARAS = {
    'f1': ('女性・短い黒髪の女子生徒', '1girl, solo, short hair, black hair, school uniform'),
    'f2': ('女性・長い髪の大人の女性', '1girl, solo, mature female, long hair, blouse'),
    'm1': ('男性・短い黒髪の男子生徒', '1boy, solo, short hair, black hair, school uniform'),
    'm2': ('男性・背広の中年の男性', '1boy, solo, middle-aged man, short hair, suit'),
}
ACTIONS = {
    'cup': 'holding cup, drinking',
    'wave': 'waving, raised hand',
    'point': 'pointing at viewer',
    'write': 'writing, holding pen, notebook',
    'hips': 'hands on hips',
    'phone': 'holding phone, looking at phone',
}
SCENE = 'cowboy shot, indoors'
SEEDS = [51, 52, 53]


def main():
    js = []
    for c, (_, cw) in CHARAS.items():
        for a, aw in ACTIONS.items():
            for s in SEEDS:
                p = f'{BASE}, {cw}, {aw}, {SCENE}'
                js.append({'file': f'{c}_{a}_{s}.png', 'chara': c, 'action': a, 'seed': s, 'prompt': p, 'graph': comfy.t2i(p, s, prefix='v3poc_p21')})
    jobs.run_jobs(OUT, js, {'charas': {k: {'name': v[0], 'words': v[1]} for k, v in CHARAS.items()}, 'actions': ACTIONS, 'scene': SCENE,
                            'neg': comfy.NEG})


if __name__ == '__main__':
    main()
