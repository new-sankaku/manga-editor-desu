"""P2 指示どおりに描かれるか（一覧 1-1 1-2 1-4 1-5 1-7）。
同じキャラに12種の指示を付け、seedを8つ変えて作る。結果はout/に画像とresult.jsonで残す。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

OUT = pathlib.Path(__file__).with_name('out')
OUT.mkdir(exist_ok=True)
CHARA = 'masterpiece, best quality, manga, monochrome, greyscale, screentone, 1girl, short black bob hair, glasses, school blazer, red necktie, pleated skirt, classroom'
SOLO = 'solo, '
# 指示ID, 一覧の行, 足す語, 人数の語を差し替えるか
INSTR = [
    ('from_behind', '1-1', 'from behind, facing away', False),
    ('from_above', '1-1', 'from above, high angle', False),
    ('from_below', '1-1', 'from below, low angle', False),
    ('from_side', '1-1', 'from side, profile', False),
    ('full_body', '1-2', 'full body, standing, shoes', False),
    ('close_up', '1-2', 'close-up, face focus, portrait', False),
    ('very_wide', '1-2', 'very wide shot, small figure in distance, scenery', False),
    ('upper_body', '1-2', 'upper body', False),
    ('two_people', '1-4', '2girls, standing side by side, talking', True),
    ('three_people', '1-4', '3girls, group, standing', True),
    ('looking_at_viewer', '1-7', 'looking at viewer, upper body', False),
    ('hand_action', '1-5', 'upper body, holding pencil, writing in notebook, hands visible', False),
]
SEEDS = list(range(1001, 1009))


def main():
    rec = []
    for iid, row, add, multi in INSTR:
        base = CHARA.replace('1girl, ', '') if multi else CHARA
        pos = f'{base}, {add}' if multi else f'{base}, {SOLO}{add}'
        for s in SEEDS:
            fn = OUT / f'{iid}_{s}.png'
            if fn.exists():
                continue
            imgs, t = comfy.run(comfy.t2i(pos, s, prefix='v3poc_p02'))
            fn.write_bytes(imgs[0])
            rec.append({'id': iid, 'row': row, 'seed': s, 'prompt': pos, 'sec': round(t, 2)})
            print(iid, s, round(t, 1), flush=True)
    old = json.loads((OUT / 'gen.json').read_text(encoding='utf-8')) if (OUT / 'gen.json').exists() else []
    (OUT / 'gen.json').write_text(json.dumps(old + rec, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
