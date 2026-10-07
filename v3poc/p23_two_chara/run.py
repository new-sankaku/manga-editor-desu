"""P23 2人を1枚に描いたとき、それぞれの特徴が混ざらないか（一覧 1-19、課題140）・髪の色を画素で比べて見分けられるか（一覧 3-9）。
組3種（P17の2人／似た女子生徒2人／カラーの2人）× 書き方（1つの文に全部／左右の範囲ごとに文を当てる）× seed 6。
範囲ごとの文は ComfyUI 標準の ConditioningSetArea（左半分・右半分）。
使い方: python run.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402
import jobs  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
Q = 'masterpiece, best quality'
TONE = 'manga, monochrome, greyscale, screentone'
COLOR = 'anime coloring, flat color'
W, H = 1216, 832
PAIRS = {
    'ab': ('P17の2人（白髪の三つ編みの女性・眼帯の男性）', TONE, '1girl, 1boy, 2people, standing side by side, upper body, classroom',
           'girl, white hair, long hair, twin braids, red eyes, freckles, star hair ornament, black hoodie, choker',
           'boy, messy hair, brown hair, short hair, scar on cheek, eyepatch, green jacket, white shirt'),
    'sim': ('似た女子生徒2人（眼鏡とポニーテール／眼鏡なしの長い髪とリボン）', TONE, '2girls, standing side by side, upper body, classroom, school uniform',
            'girl, black hair, ponytail, glasses', 'girl, black hair, long hair, hair ribbon'),
    'color': ('カラーの2人（赤い短髪／青い長髪）', COLOR, '2girls, standing side by side, upper body, classroom',
              'girl, red hair, short hair, blue eyes, white shirt', 'girl, blue hair, long hair, yellow eyes, black jacket'),
}
SEEDS = list(range(71, 77))


def regional(base, left, right, seed):
    g = comfy.t2i(base, seed, W, H, prefix='v3poc_p23')
    g['40'] = {'class_type': 'CLIPTextEncode', 'inputs': {'text': left, 'clip': ['1', 1]}}
    g['41'] = {'class_type': 'CLIPTextEncode', 'inputs': {'text': right, 'clip': ['1', 1]}}
    g['42'] = {'class_type': 'ConditioningSetArea', 'inputs': {'conditioning': ['40', 0], 'width': W // 2, 'height': H, 'x': 0, 'y': 0, 'strength': 1.0}}
    g['43'] = {'class_type': 'ConditioningSetArea', 'inputs': {'conditioning': ['41', 0], 'width': W // 2, 'height': H, 'x': W // 2, 'y': 0, 'strength': 1.0}}
    g['44'] = {'class_type': 'ConditioningCombine', 'inputs': {'conditioning_1': ['42', 0], 'conditioning_2': ['43', 0]}}
    g['45'] = {'class_type': 'ConditioningCombine', 'inputs': {'conditioning_1': ['2', 0], 'conditioning_2': ['44', 0]}}
    g['5']['inputs']['positive'] = ['45', 0]
    return g


def main():
    js = []
    for k, (_, style, scene, left, right) in PAIRS.items():
        for mode in ('one', 'area'):
            for s in SEEDS:
                if mode == 'one':
                    p = f'{Q}, {style}, {scene}, {left}, {right}'
                    g = comfy.t2i(p, s, W, H, prefix='v3poc_p23')
                    row = {'prompt': p}
                else:
                    base = f'{Q}, {style}, {scene}'
                    g = regional(base, f'{Q}, {style}, {left}', f'{Q}, {style}, {right}', s)
                    row = {'prompt': base, 'left': f'{Q}, {style}, {left}', 'right': f'{Q}, {style}, {right}'}
                js.append({'file': f'{k}_{mode}_{s}.png', 'pair': k, 'mode': mode, 'seed': s, **row, 'graph': g})
    jobs.run_jobs(OUT, js, {'pairs': {k: {'name': v[0], 'style': v[1], 'scene': v[2], 'left': v[3], 'right': v[4]} for k, v in PAIRS.items()},
                            'size': [W, H]})


if __name__ == '__main__':
    main()
