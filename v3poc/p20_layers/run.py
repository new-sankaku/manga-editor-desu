"""P20 線画・ベタ・トーン・着彩を別々に作れるか（一覧 1-27）。
手1（後から分ける）：トーンまで入った絵を作り、線画を取り出す部品（Manga2Anime・AnimeLineArt）で線だけを抜く。ベタとトーンは濃さで分ける（analyze.py）。
手2（先に線画）：線画だけの絵を作り、その線画を多用途の制御（xinsir union、Apache-2.0）で渡して、トーンの絵とカラーの絵を作る。
  線画が1枚の層として手元に残るので、トーンと着彩はその上に重ねる層になるかを見る。
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
LINE = 'lineart, monochrome, greyscale, sketch, white background'
LINE_NEG = 'screentone, shading, grey, halftone, color'
COLOR = 'anime coloring, flat color'
SCENES = {
    'a_desk': '1girl, solo, white hair, long hair, twin braids, red eyes, freckles, star hair ornament, black hoodie, choker, sitting at desk, upper body, classroom',
    'b_run': '1boy, solo, messy hair, brown hair, short hair, scar on cheek, eyepatch, green jacket, white shirt, running, full body, street',
    'bg_room': 'scenery, no humans, classroom, desk, window, blackboard',
}
SEEDS = [41, 42, 43]
UNION = 'xinsir\\union-sdxl-1.0-promax.safetensors'
CN_TYPE = 'canny/lineart/anime_lineart/mlsd'
CN_STRENGTH = 0.9
PRE = {'m2a': 'Manga2Anime_LineArt_Preprocessor', 'ani': 'AnimeLineArtPreprocessor'}


def with_line(g, line_img):
    g['20'] = {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': UNION}}
    g['23'] = {'class_type': 'SetUnionControlNetType', 'inputs': {'control_net': ['20', 0], 'type': CN_TYPE}}
    g['21'] = {'class_type': 'LoadImage', 'inputs': {'image': line_img}}
    g['24'] = {'class_type': 'ImageInvert', 'inputs': {'image': ['21', 0]}}  # 制御は黒地に白い線を受け取る
    g['22'] = {'class_type': 'ControlNetApplyAdvanced', 'inputs': {'positive': ['2', 0], 'negative': ['3', 0], 'control_net': ['23', 0], 'image': ['24', 0],
                                                                 'strength': CN_STRENGTH, 'start_percent': 0.0, 'end_percent': 1.0}}
    g['5']['inputs']['positive'] = ['22', 0]
    g['5']['inputs']['negative'] = ['22', 1]
    return g


def extract(src_name, pre):
    return {'1': {'class_type': 'LoadImage', 'inputs': {'image': src_name}},
            '2': {'class_type': PRE[pre], 'inputs': {'image': ['1', 0], 'resolution': 1216}},
            '3': {'class_type': 'SaveImage', 'inputs': {'images': ['2', 0], 'filename_prefix': 'v3poc_p20'}}}


def main():
    meta = {'scenes': SCENES, 'tone': TONE, 'line': LINE, 'line_neg': LINE_NEG, 'color': COLOR, 'union': UNION, 'cn_type': CN_TYPE,
            'cn_strength': CN_STRENGTH, 'pre': PRE}
    first = []
    for s, words in SCENES.items():
        for seed in SEEDS:
            first.append({'file': f'{s}_tone_{seed}.png', 'scene': s, 'mode': 'tone', 'seed': seed,
                          'prompt': f'{Q}, {TONE}, {words}', 'graph': comfy.t2i(f'{Q}, {TONE}, {words}', seed, prefix='v3poc_p20')})
            first.append({'file': f'{s}_line_{seed}.png', 'scene': s, 'mode': 'line', 'seed': seed, 'prompt': f'{Q}, {LINE}, {words}',
                          'graph': comfy.t2i(f'{Q}, {LINE}, {words}', seed, neg=f'{comfy.NEG}, {LINE_NEG}', prefix='v3poc_p20')})
    runs = jobs.run_jobs(OUT, first, meta)
    second = []
    for s, words in SCENES.items():
        for seed in SEEDS:
            tone = jobs.upload_once(OUT / f'{s}_tone_{seed}.png', f'v3poc_p20_{s}_tone_{seed}.png')
            line = jobs.upload_once(OUT / f'{s}_line_{seed}.png', f'v3poc_p20_{s}_line_{seed}.png')
            for pre in PRE:
                second.append({'file': f'{s}_tone_{seed}_x{pre}.png', 'scene': s, 'mode': f'extract_{pre}', 'seed': seed, 'graph': extract(tone, pre)})
            for mode, style in (('line2tone', TONE), ('line2color', COLOR)):
                p = f'{Q}, {style}, {words}'
                second.append({'file': f'{s}_{mode}_{seed}.png', 'scene': s, 'mode': mode, 'seed': seed, 'prompt': p,
                               'graph': with_line(comfy.t2i(p, seed, prefix='v3poc_p20'), line)})
    jobs.run_jobs(OUT, first + second, meta)


if __name__ == '__main__':
    main()
