"""P43 同一キャラ判定（CCIP）は、似ているが別の人物を「違う」と言えるか（一覧 3-8）。新しい絵は作らない。
人物の組（どれも作り済みの絵）：
  P17 a・b（見た目の言葉を全部入れ、参照なし）
  P02 眼鏡の女子生徒（96枚すべて同じ言葉）の上半身・寄り
  P16 眼鏡の女子生徒・パーカーの少年・背広の老人（同じ言葉で場所と狙いを変えた。切り抜きは除く）
  P21 f1 短い黒髪の女子生徒・m1 短い黒髪の男子生徒・f2 大人の女性・m2 中年の男性（言葉が大まかで、seed ごとに別人になりうる）
組の中どうし・組の間の全部の対で差を出し、既定の閾値（0.178）で「同じ」と言った割合を数える。
組の間で「同じ」が多い対は一覧画像（out/sheet_pairs.png）にして目で見る。
crop を付けると、人物の検出器でいちばん確かな人物を切り抜いてから比べる（小さく写った人物で背景を比べてしまうのを避けるため）。
結果は out/result.json（切り抜きなし）と out/result_crop.json・out/sheet_pairs_crop.png（切り抜きあり）。
使い方: <検出器の仮想環境の python> run.py [crop]"""
import itertools
import json
import pathlib
import sys

import numpy as np
from imgutils.detect import detect_person
from imgutils.metrics import ccip_batch_differences, ccip_default_threshold, ccip_extract_feature
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
V = HERE.parent


def files():
    g = {}
    g['p17_a'] = sorted((V / 'p17_identity2/out').glob('a_full_none_*.png'))
    g['p17_b'] = sorted((V / 'p17_identity2/out').glob('b_full_none_*.png'))
    g['p02_girl'] = sorted(p for p in (V / 'p02_instruction/out').glob('*.png') if p.name.startswith(('close_up', 'upper_body')))
    for c in ('girl', 'boy', 'old'):
        g[f'p16_{c}'] = sorted(p for p in (V / 'p16_general/out').glob(f'*_{c}_*.png') if not p.stem.endswith('_cut'))
    for c in ('f1', 'm1', 'f2', 'm2'):
        g[f'p21_{c}'] = sorted((V / 'p21_hands/out').glob(f'{c}_*.png'))
    return {k: v for k, v in g.items() if v}


CROP = 'crop' in sys.argv[1:]
SUF = '_crop' if CROP else ''


def load(p):
    im = Image.open(p).convert('RGB')
    if not CROP:
        return im
    ds = detect_person(im)
    if not ds:
        return im
    (x0, y0, x1, y1), _, _ = max(ds, key=lambda d: d[2])
    m = int(0.1 * max(x1 - x0, y1 - y0))
    return im.crop((max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, im.width), min(y1 + m, im.height)))


def main():
    th = ccip_default_threshold()
    g = files()
    names = list(g)
    feats, owner, paths = [], [], []
    for k in names:
        for p in g[k]:
            feats.append(ccip_extract_feature(load(p)))
            owner.append(k)
            paths.append(p)
    d = ccip_batch_differences(feats)
    owner = np.array(owner)
    res = {'threshold': th, 'counts': {k: len(g[k]) for k in names}, 'same_rate': {}}
    for a, b in itertools.combinations_with_replacement(names, 2):
        ia, ib = np.where(owner == a)[0], np.where(owner == b)[0]
        sub = d[np.ix_(ia, ib)]
        if a == b:
            sub = sub[np.triu_indices(len(ia), 1)]
        res['same_rate'][f'{a}|{b}'] = {'same': round(float((sub < th).mean()), 3), 'median_diff': round(float(np.median(sub)), 3)}
    # 組の間で「同じ」と言った対のうち、差が小さい順に24組を一覧に
    pairs = [(d[i, j], i, j) for i in range(len(paths)) for j in range(i + 1, len(paths)) if owner[i] != owner[j] and d[i, j] < th]
    pairs.sort()
    res['cross_same_pairs'] = len(pairs)
    res['cross_same_examples'] = [{'diff': round(float(x), 3), 'a': f'{owner[i]}/{paths[i].name}', 'b': f'{owner[j]}/{paths[j].name}'} for x, i, j in pairs[:24]]
    S = 200
    sh = Image.new('RGB', (4 * (2 * S + 12), 6 * (S + 18)), 'white')
    for n, (x, i, j) in enumerate(pairs[:24]):
        X, Y = (n % 4) * (2 * S + 12), (n // 4) * (S + 18)
        for k, idx in enumerate((i, j)):
            im = load(paths[idx])
            im.thumbnail((S, S))
            sh.paste(im, (X + k * S, Y + 16))
        ImageDraw.Draw(sh).text((X + 2, Y + 2), f'{owner[i]} / {owner[j]}  {x:.3f}', fill='black')
    sh.save(OUT / f'sheet_pairs{SUF}.png')
    (OUT / f'result{SUF}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in res['same_rate'].items():
        print(k, v)
    print('cross same pairs', len(pairs))


if __name__ == '__main__':
    main()
