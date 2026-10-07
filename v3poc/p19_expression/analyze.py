"""P19 の測定。一覧画像（キャラごと。行＝感情×seed、列＝無表情・弱・中・強・強＋参照）を作り、
同一キャラ判定（CCIP）で参照画像との差を出す（参照画像の部品で表情が消えて参照に寄るかの目安、一覧 1-20）。
使い方: <検出器の仮想環境のpython> analyze.py"""
import json
import pathlib
import sys

from PIL import Image
from imgutils.detect import detect_faces
from imgutils.metrics import ccip_difference, ccip_extract_feature

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
FACE = OUT / 'face'
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402

COLS = [('neutral', 0, False, '無表情'), (None, 1, False, '弱'), (None, 2, False, '中'), (None, 3, False, '強'), (None, 3, True, '強＋参照')]


def main():
    gen = json.loads((OUT / 'gen.json').read_text(encoding='utf-8'))
    runs = gen['runs']
    refs = {c: ccip_extract_feature(str((HERE / p).resolve())) for c, p in gen['refs'].items()}
    rows = []
    for r in runs:
        rows.append({**{k: r[k] for k in ('file', 'chara', 'emotion', 'level', 'ref', 'seed')},
                     'ccip_diff': round(float(ccip_difference(refs[r['chara']], ccip_extract_feature(str(OUT / r['file'])))), 3)})
    summ = {}
    for c in gen['charas']:
        for ref in (False, True):
            g = [x['ccip_diff'] for x in rows if x['chara'] == c and x['ref'] == ref and x['level'] in (0, 3)]
            summ[f'{c}/{"ref" if ref else "none"}/無表情と強'] = round(sum(g) / len(g), 3)
    (OUT / 'result.json').write_text(json.dumps({'summary': summ, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in summ.items():
        print(k, v)
    seeds = sorted({r['seed'] for r in runs})
    for c, ch in gen['charas'].items():
        rs = [('参照画像', [((HERE / gen['refs'][c]).resolve(), '')])]
        for e, info in gen['emotions'].items():
            for s in seeds:
                cells = []
                for ce, lv, ref, lab in COLS:
                    f = f"{c}_{ce or e}_{lv}{'_ipa' if ref else ''}_{s}.png"
                    cells.append((OUT / f, lab))
                rs.append((f"{info['name']} seed {s}", cells))
        sheet(rs, OUT / f'sheet_{c}.png', tw=150, label_w=120)
        # 顔の検出器で見つけた顔を、周りを少し広げて切り出して大きく並べる（表情を見比べるため）。見つからない絵は全体を出し、そう書く
        FACE.mkdir(exist_ok=True)
        fr = []
        for lab, cells in rs[1:]:
            fc = []
            for f, cl in cells:
                im = Image.open(f)
                faces = detect_faces(im)
                if not faces:
                    fc.append((f, cl + '（顔が見つからず全体）'))
                    continue
                (x0, y0, x1, y1), _, _ = max(faces, key=lambda d: d[2])
                side = max(x1 - x0, y1 - y0) * 1.6
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                im.crop((int(cx - side / 2), int(cy - side / 2), int(cx + side / 2), int(cy + side / 2))).save(FACE / f.name)
                fc.append((FACE / f.name, cl))
            fr.append((lab, fc))
        sheet(fr, OUT / f'sheet_face_{c}.png', tw=190, label_w=120)


if __name__ == '__main__':
    main()
