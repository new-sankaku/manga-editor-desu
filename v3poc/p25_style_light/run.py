"""P25 コマが進んでも画風がずれないか・写実に寄らないか（一覧 1-12・3-10）と、光の向きがコマごとに変わらないか（一覧 1-18）。
画風：P17 の a を8つの場面で seed 2 ずつ（16枚、同じ画風の言葉）。写実の判定器が効くかを見るため、写実の言葉を足した絵も4枚作る（比べる物）。
光：同じ場面で、光の言葉なし／左から／右から × seed 4。
使い方: python run.py"""
import importlib.util
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402
import jobs  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
_spec = importlib.util.spec_from_file_location('p17', HERE.parent / 'p17_identity2' / 'run.py')
P17 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P17)
SCENES = {
    'walk': 'walking, full body, street',
    'desk': 'sitting at desk, upper body, classroom',
    'rain': 'holding umbrella, rain, full body, street',
    'eat': 'eating bread, sitting, cafeteria, upper body',
    'phone': 'holding phone, upper body, bedroom',
    'run': 'running, full body, park',
    'train': 'sitting, train interior, upper body',
    'night': 'standing, night, city lights, cowboy shot',
}
SEEDS = [91, 92]
REAL = 'realistic, photorealistic'
LIGHT = {'none': '', 'left': 'sunlight, light from left, shadow', 'right': 'sunlight, light from right, shadow'}
LIGHT_SCENE = 'standing, upper body, classroom, window'
LIGHT_SEEDS = [95, 96, 97, 98]


def main():
    cw = P17.chara_words('a', 'full')
    js = []
    for sc, w in SCENES.items():
        for s in SEEDS:
            p = f'{P17.STYLE}, {cw}, {w}'
            js.append({'file': f'style_{sc}_{s}.png', 'kind': 'style', 'scene': sc, 'seed': s, 'prompt': p, 'graph': comfy.t2i(p, s, prefix='v3poc_p25')})
    for sc in ('walk', 'desk', 'eat', 'night'):
        p = f'{P17.STYLE}, {REAL}, {cw}, {SCENES[sc]}'
        js.append({'file': f'real_{sc}_91.png', 'kind': 'real', 'scene': sc, 'seed': 91, 'prompt': p, 'graph': comfy.t2i(p, 91, prefix='v3poc_p25')})
    for lk, lw in LIGHT.items():
        for s in LIGHT_SEEDS:
            p = f'{P17.STYLE}, {cw}, {LIGHT_SCENE}' + (f', {lw}' if lw else '')
            js.append({'file': f'light_{lk}_{s}.png', 'kind': 'light', 'light': lk, 'seed': s, 'prompt': p, 'graph': comfy.t2i(p, s, prefix='v3poc_p25')})
    jobs.run_jobs(OUT, js, {'scenes': SCENES, 'real': REAL, 'light': LIGHT, 'light_scene': LIGHT_SCENE})


if __name__ == '__main__':
    main()
