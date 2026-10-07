"""P21 の絵から手を検出して切り出し、目で見る一覧を作る（一覧 1-3・1-10・1-8）。
人物ごとに1枚の一覧 out/sheet_<人物>.png：絵の縮小と、その下に検出した手の切り抜き（原寸から切って拡大）。
目の判定は out/labels.json に人が付ける：{"<ファイル名>": {"hand": "ok|ng|part", "body": "ok|ng", "face": "ok|ng", "note": ""}}
手の検出数・美しさの採点（P35 の値があれば）と目の判定を突き合わせる。
使い方: <検出器の仮想環境の python> analyze.py [--sheet]"""
import json
import pathlib
import sys

from PIL import Image, ImageDraw
from imgutils.detect import detect_hands

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
CHARAS = ['f1', 'f2', 'm1', 'm2']
TW, TH, HS = 200, 292, 96


def tile(p, hands):
    im = Image.open(p).convert('RGB')
    t = im.resize((TW, TH))
    sx, sy = TW / im.width, TH / im.height
    d = ImageDraw.Draw(t)
    for (x0, y0, x1, y1), _, _ in hands:
        d.rectangle([x0 * sx, y0 * sy, x1 * sx, y1 * sy], outline='red', width=2)
    out = Image.new('RGB', (TW, TH + 16 + HS * 2), 'white')
    out.paste(t, (0, 16))
    ImageDraw.Draw(out).text((2, 2), p.stem, fill='black')
    for k, ((x0, y0, x1, y1), _, _) in enumerate(hands[:4]):
        c = im.crop((max(x0 - 8, 0), max(y0 - 8, 0), min(x1 + 8, im.width), min(y1 + 8, im.height)))
        c.thumbnail((HS, HS))
        out.paste(c, ((k % 2) * (HS + 4), TH + 16 + (k // 2) * HS))
    return out


def main():
    det = {}
    for p in sorted(OUT.glob('*.png')):
        if p.name.startswith('sheet'):
            continue
        det[p.name] = [h for h in detect_hands(str(p)) if h[2] >= 0.35]
    (OUT / 'hands.json').write_text(json.dumps({k: [[list(map(int, b)), round(float(s), 3)] for b, _, s in v] for k, v in det.items()}, indent=1), encoding='utf-8')
    for c in CHARAS:
        tiles = [tile(OUT / f, det[f]) for f in det if f.startswith(c + '_')]
        cols = 6
        rows = (len(tiles) + cols - 1) // cols
        sh = Image.new('RGB', (cols * (TW + 6), rows * (tiles[0].height + 6)), 'white')
        for i, t in enumerate(tiles):
            sh.paste(t, ((i % cols) * (TW + 6), (i // cols) * (t.height + 6)))
        sh.save(OUT / f'sheet_{c}.png')
    lab_p = OUT / 'labels.json'
    if not lab_p.exists():
        return
    lab = json.loads(lab_p.read_text(encoding='utf-8'))
    sc_p = HERE.parent / 'p35_scorers' / 'out' / 'scores_p21_hands.json'
    sc = json.loads(sc_p.read_text(encoding='utf-8')) if sc_p.exists() else {}
    res = {}
    for c in CHARAS:
        fs = [f for f in lab if f.startswith(c + '_')]
        res[c] = {k: {v: sum(1 for f in fs if lab[f][k] == v) for v in ('ok', 'part', 'ng')} for k in ('hand', 'body', 'face')}
    for sex, cs in (('female', ['f1', 'f2']), ('male', ['m1', 'm2'])):
        fs = [f for f in lab if f[:2] in cs]
        res[sex] = {k: sum(1 for f in fs if lab[f][k] == 'ok') for k in ('hand', 'body', 'face')} | {'n': len(fs)}
    if sc:
        import statistics as st
        for v in ('ok', 'part_or_ng'):
            fs = [f for f in lab if (lab[f]['hand'] == 'ok') == (v == 'ok') and f in sc]
            res[f'aesthetic_hand_{v}'] = round(st.mean(sc[f]['dbaesthetic']['percentile'] for f in fs), 3) if fs else None
        res['aesthetic_by_chara'] = {c: round(st.mean(sc[f]['dbaesthetic']['percentile'] for f in lab if f.startswith(c + '_') and f in sc), 3) for c in CHARAS}
        pairs = hit = 0
        for f in lab:
            for g in lab:
                if lab[f]['hand'] == 'ok' and lab[g]['hand'] == 'ng' and f in sc and g in sc:
                    pairs += 1
                    hit += sc[f]['dbaesthetic']['percentile'] > sc[g]['dbaesthetic']['percentile']
        res['aesthetic_ok_above_ng_pairs'] = f'{hit}/{pairs}'
    res['hands_detected_mean'] = round(sum(len(v) for v in det.values()) / len(det), 2)
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
