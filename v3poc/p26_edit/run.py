"""P26 画像編集で写真風にならないか・ポーズを大きく変える編集で構造が保てるか・編集で背景が勝手に変わらないか（一覧 1-15・1-17）。
編集のモデル：Qwen-Image 2.1（int8、ComfyUI 標準の TextEncodeQwenImage21 に元の絵を渡す。Qwen Research License で非商用。当時は Apache-2.0 と誤って書いていた）。
元の絵：P17 の a（食べる・上半身）と b（走る・全身）。編集5種 × seed 2。
判定：写実の判定器・白黒の判定器・同一キャラ判定（CCIP）・人物の枠の外の画素の変化（analyze.py）と目。
使い方: python run.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import jobs  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
SRC = {'a': 'a_full_none_eat_21.png', 'b': 'b_full_none_run_21.png'}
EDITS = {
    'smile': 'Make the character smile. Keep everything else unchanged.',
    'cup': "Put a coffee cup in the character's hand. Keep everything else unchanged.",
    'sit': 'Make the character sit on a chair. Keep the same character, clothes and drawing style.',
    'back': 'Show the same character from behind. Keep the same clothes and drawing style.',
    'bg': 'Change the background to a beach. Keep the character unchanged.',
}
SEEDS = [1, 2]
MODEL = {'unet': 'qwen_image_2.1_int8_convrot.safetensors', 'clip': 'qwen3vl_8b_int8_convrot.safetensors',
         'vae': 'qwen_image_2.1_vae_bf16.safetensors', 'steps': 25, 'cfg': 1.0, 'sampler': 'euler', 'scheduler': 'simple', 'resolution': 1024}


def graph(src, prompt, seed):
    m = MODEL
    return {'1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': m['unet'], 'weight_dtype': 'default'}},
            '2': {'class_type': 'QwenImage21Cache', 'inputs': {'model': ['1', 0], 'device': 'auto', 'dtype': 'default'}},
            '3': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': m['clip'], 'type': 'qwen_image', 'device': 'default'}},
            '4': {'class_type': 'VAELoader', 'inputs': {'vae_name': m['vae']}},
            '5': {'class_type': 'LoadImage', 'inputs': {'image': src}},
            '6': {'class_type': 'TextEncodeQwenImage21', 'inputs': {'clip': ['3', 0], 'prompt': prompt, 'negative_prompt': '', 'resolution': m['resolution'],
                                                                    'vae': ['4', 0], 'images.image_1': ['5', 0]}},
            '7': {'class_type': 'KSampler', 'inputs': {'model': ['2', 0], 'positive': ['6', 0], 'negative': ['6', 1], 'latent_image': ['6', 2], 'seed': seed,
                                                       'steps': m['steps'], 'cfg': m['cfg'], 'sampler_name': m['sampler'], 'scheduler': m['scheduler'], 'denoise': 1.0}},
            '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['7', 0], 'vae': ['4', 0]}},
            '9': {'class_type': 'SaveImage', 'inputs': {'images': ['8', 0], 'filename_prefix': 'v3poc_p26'}}}


def main():
    js = []
    for c, f in SRC.items():
        name = jobs.upload_once(HERE.parent / 'p17_identity2' / 'out' / f, f'v3poc_p26_src_{c}.png')
        for e, p in EDITS.items():
            for s in SEEDS:
                js.append({'file': f'{c}_{e}_{s}.png', 'chara': c, 'edit': e, 'seed': s, 'prompt': p, 'src': f, 'graph': graph(name, p, s)})
    jobs.run_jobs(OUT, js, {'src': SRC, 'edits': EDITS, 'model': MODEL})


if __name__ == '__main__':
    main()
