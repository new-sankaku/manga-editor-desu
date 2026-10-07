"""P22 文字の検出器（dghs-imgutils の detect_text）の枠を描いた一覧を作り、目の判定（out/labels.json）と突き合わせる。
labels.json：{"<ファイル名>": {"balloon": 頼んでいないフキダシの数, "text": 文字らしき物があるか(true/false), "note": ""}}
使い方: <検出器の仮想環境の python> analyze.py"""
import json
import pathlib

from PIL import Image, ImageDraw
from imgutils.detect import detect_text

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
TW, TH = 180, 263
TEXT_CONF = 0.1   # 一覧に描く枠と、判定に使う確かさの下限。検出器の標準（0.05）で全部をためてから切る
THS = [0.05, 0.1, 0.15, 0.2]


def main():
    det_p = OUT / 'text_all.json'
    det = json.loads(det_p.read_text(encoding='utf-8')) if det_p.exists() else {}
    files = sorted(p for p in OUT.glob('*.png') if not p.name.startswith('sheet'))
    for p in files:
        if p.name not in det:
            det[p.name] = [[list(map(int, b)), round(float(s), 3)] for b, _, s in detect_text(str(p))]
    det_p.write_text(json.dumps(det, indent=1), encoding='utf-8')
    for grp in sorted({p.name.rsplit('_', 1)[0] for p in files}):
        fs = [p for p in files if p.name.rsplit('_', 1)[0] == grp]
        sh = Image.new('RGB', (len(fs) * (TW + 4), TH + 16), 'white')
        for i, p in enumerate(fs):
            im = Image.open(p).convert('RGB')
            d = ImageDraw.Draw(im)
            for (x0, y0, x1, y1), sc in det[p.name]:
                if sc < TEXT_CONF:
                    continue
                d.rectangle([x0, y0, x1, y1], outline='red', width=5)
            sh.paste(im.resize((TW, TH)), (i * (TW + 4), 16))
            ImageDraw.Draw(sh).text((i * (TW + 4) + 2, 2), f'{p.stem} n={sum(1 for _, sc in det[p.name] if sc >= TEXT_CONF)}', fill='black')
        sh.save(OUT / f'sheet_{grp}.png')
    lab_p = OUT / 'labels.json'
    if not lab_p.exists():
        return
    lab = json.loads(lab_p.read_text(encoding='utf-8'))
    res = {}
    for grp in sorted({f.rsplit('_', 1)[0] for f in lab}):
        fs = [f for f in lab if f.rsplit('_', 1)[0] == grp]
        res[grp] = {'n': len(fs), 'with_balloon': sum(1 for f in fs if lab[f]['balloon'] > 0), 'with_text': sum(1 for f in fs if lab[f]['text']),
                    'detected': sum(1 for f in fs if any(sc >= TEXT_CONF for _, sc in det[f]))}
    res['detector_vs_eye'] = {}
    for t in THS:
        hit = {f: any(sc >= t for _, sc in det[f]) for f in lab}
        res['detector_vs_eye'][str(t)] = {'text_and_detected': sum(1 for f in lab if lab[f]['text'] and hit[f]),
                                          'no_text_but_detected': sum(1 for f in lab if not lab[f]['text'] and hit[f]),
                                          'text_but_missed': sum(1 for f in lab if lab[f]['text'] and not hit[f]),
                                          'no_text_not_detected': sum(1 for f in lab if not lab[f]['text'] and not hit[f])}
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
