"""P35 既製の判定器（dghs-imgutils）が、この画風の漫画の絵で使えるか。
・規制（一覧 5-20）：年齢区分の判定（anime_rating）と NSFW の判定（nsfw_pred）を P02 の96枚にかける。見上げの8枚（スカートを強調する構図に寄った）で上がるか
・採点器の偏り（一覧 3-23）：美しさの採点（anime_dbaesthetic、get_aesthetic_score）を P15 の絵柄4種と、P16 の狙いどおり／外れの絵にかける
・写実（一覧 1-12）：写実の判定（anime_real）を、P25 の写実の言葉あり・なしにかける（P25 ができてから）
・崩れ（一覧 1-10）：P21 の手の崩れの目の判定と、美しさの採点が合うか（P21 の目の判定ができてから）
判定器の値は out/scores_<試作>.json にためる（一度測った絵は測り直さない）。
使い方: <検出器の仮想環境の python> run.py <試作のフォルダ名> ..."""
import json
import os
import pathlib
import sys

os.environ.setdefault('ONNXRUNTIME_PROVIDERS', 'CPUExecutionProvider')
from imgutils.metrics import anime_dbaesthetic, get_aesthetic_score  # noqa: E402
from imgutils.validate import anime_rating_score, anime_real_score, nsfw_pred_score  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)


def score(p):
    lvl, pct, prob = anime_dbaesthetic(str(p), fmt=('label', 'percentile', 'confidence'))
    return {'rating': {k: round(v, 3) for k, v in anime_rating_score(str(p)).items()},
            'nsfw': {k: round(v, 3) for k, v in nsfw_pred_score(str(p)).items()},
            'real': {k: round(v, 3) for k, v in anime_real_score(str(p)).items()},
            'dbaesthetic': {'label': lvl, 'percentile': round(float(pct), 3)},
            'aesthetic': round(float(get_aesthetic_score(str(p))), 3)}


def main(names):
    for name in names:
        src = HERE.parent / name / 'out'
        dst = OUT / f'scores_{name}.json'
        have = json.loads(dst.read_text(encoding='utf-8')) if dst.exists() else {}
        for p in sorted(src.glob('*.png')):
            if p.name.startswith('sheet') or p.name in have:
                continue
            have[p.name] = score(p)
        dst.write_text(json.dumps(have, ensure_ascii=False, indent=1), encoding='utf-8')
        print(name, len(have), flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
