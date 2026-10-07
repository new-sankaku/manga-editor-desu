"""P24 同一キャラ判定（CCIP）で、P17 の参照画像と同じ人物と判定されるかを数え、目で見る一覧を作る。
一覧：人物ごとに out/sheet_<人物>.png（上から デフォルメ／通常／参照そのまま／参照ぼかし。左端に参照画像）。
使い方: <検出器の仮想環境の python> analyze.py"""
import json
import pathlib

from PIL import Image, ImageDraw
from imgutils.metrics import ccip_default_threshold, ccip_difference, ccip_extract_feature

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
P17 = HERE.parent / 'p17_identity2' / 'out'
MODES = ['deform', 'normal', 'refclean', 'refblur']
TH = 260


def main():
    th = ccip_default_threshold()
    refs = {c: ccip_extract_feature(str(P17 / f'ref_{c}.png')) for c in 'ab'}
    rows = []
    for p in sorted(OUT.glob('[ab]_*.png')):
        c, mode, seed = p.stem.split('_')
        f = ccip_extract_feature(str(p))
        d = float(ccip_difference(refs[c], f))
        do = float(ccip_difference(refs['b' if c == 'a' else 'a'], f))
        rows.append({'file': p.name, 'chara': c, 'mode': mode, 'seed': int(seed), 'diff': round(d, 3), 'same': d < th, 'diff_other': round(do, 3)})
    summ = {}
    for c in 'ab':
        for m in MODES:
            g = [r for r in rows if r['chara'] == c and r['mode'] == m]
            summ[f'{c}/{m}'] = {'n': len(g), 'same': sum(r['same'] for r in g), 'diff_mean': round(sum(r['diff'] for r in g) / len(g), 3)}
    (OUT / 'result.json').write_text(json.dumps({'threshold': th, 'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('threshold', round(th, 3), json.dumps(summ))
    for c in 'ab':
        lines = []
        for m in MODES:
            g = [r for r in rows if r['chara'] == c and r['mode'] == m]
            ims = []
            ref = Image.open(OUT / f'ref_{c}_blur.png' if m == 'refblur' else P17 / f'ref_{c}.png').convert('RGB')
            ims.append((ref.resize((round(ref.width * TH / ref.height), TH)), f'ref ({m})' if m.startswith('ref') else 'ref'))
            for r in g:
                im = Image.open(OUT / r['file']).convert('RGB')
                ims.append((im.resize((round(im.width * TH / im.height), TH)), f"{m} {r['seed']} d={r['diff']:.2f}"))
            lines.append(ims)
        w = max(sum(i.width + 4 for i, _ in l) for l in lines)
        sh = Image.new('RGB', (w, len(lines) * (TH + 18)), 'white')
        for y, l in enumerate(lines):
            x = 0
            for im, t in l:
                sh.paste(im, (x, y * (TH + 18) + 16))
                ImageDraw.Draw(sh).text((x + 2, y * (TH + 18) + 2), t, fill='black')
                x += im.width + 4
        sh.save(OUT / f'sheet_{c}.png')


if __name__ == '__main__':
    main()
