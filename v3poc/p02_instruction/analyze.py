"""P2の解析。1) 目で判定する一覧画像 2) 検出器の数値 3) 目の判定（labels.json）との突き合わせ。
labels.json は一覧画像を見て人が付ける：{"<指示ID>_<seed>": {"ok": true/false, "note": "..."}}"""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402
from run import INSTR, SEEDS  # noqa: E402

OUT = HERE / 'out'
VENV = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None  # 検出器を入れたPython


def sheets():
    for k in range(3):
        rows = [(iid, [(OUT / f'{iid}_{s}.png', str(s)) for s in SEEDS]) for iid, *_ in INSTR[k * 4:(k + 1) * 4]]
        sheet(rows, OUT / f'sheet_{k + 1}.png', tw=140, label_w=150)


def detect():
    if not (OUT / 'detect.json').exists():
        subprocess.run([str(VENV), str(HERE.parent / 'common' / 'detect.py'), str(OUT), str(OUT / 'detect.json')], check=True)
    return {d['file'][:-4]: d for d in json.loads((OUT / 'detect.json').read_text(encoding='utf-8'))}


def auto(d, iid):
    """検出器の数値だけで指示を満たしたかを決める（決められる指示だけ）。"""
    ps = [p for p in d['persons'] if p['score'] > 0.4]
    fs = d['faces']
    face_h = max((f['h_ratio'] for f in fs), default=0)
    per_h = max((p['h_ratio'] for p in ps), default=0)
    if iid == 'two_people':
        return len(ps) == 2
    if iid == 'three_people':
        return len(ps) == 3
    if iid == 'close_up':
        return face_h >= 0.3
    if iid == 'upper_body':
        return 0.12 <= face_h < 0.3 and any('B' in p['touch'] for p in ps)
    if iid == 'full_body':
        return bool(ps) and not any(('B' in p['touch']) or ('T' in p['touch']) for p in ps) and face_h < 0.12
    if iid == 'very_wide':
        return bool(ps) and per_h < 0.5
    if iid == 'from_behind':
        return not fs  # 顔が見えなければ後ろ向きとみなす
    return None


def main():
    sheets()
    det = detect()
    labels = json.loads((OUT / 'labels.json').read_text(encoding='utf-8')) if (OUT / 'labels.json').exists() else {}
    summ = {}
    labels.pop('_meta', None)
    for iid, row, *_ in INSTR:
        keys = [f'{iid}_{s}' for s in SEEDS]
        eye = [labels[k]['ok'] for k in keys if k in labels]
        au = [auto(det[k], iid) for k in keys]
        agree = [a == labels[k]['ok'] for a, k in zip(au, keys) if a is not None and k in labels]
        summ[iid] = {'row': row, 'eye_ok': sum(eye), 'n': len(eye), 'eye_rate': round(sum(eye) / len(eye), 2) if eye else None,
                     'any_ok': any(eye) if eye else None,
                     'auto_ok': sum(1 for a in au if a) if au[0] is not None else None,
                     'auto_eye_agree': f'{sum(agree)}/{len(agree)}' if agree else None,
                     'persons': [len([p for p in det[k]['persons'] if p['score'] > 0.4]) for k in keys],
                     'face_h': [max((f['h_ratio'] for f in det[k]['faces']), default=0) for k in keys]}
    (OUT / 'result.json').write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in summ.items():
        print(k, v['eye_ok'], '/', v['n'], 'auto', v['auto_ok'], 'agree', v['auto_eye_agree'], v['persons'], v['face_h'])


if __name__ == '__main__':
    main()
