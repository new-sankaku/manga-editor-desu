"""P10 ページを1枚で生成すると、コマ数・枠・埋まりが守られるか（一覧 1-30）。コマごとに作る案の対照。
コマ数の指定3種 × seed4。数えるのは目で（labels.json）。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
import comfy  # noqa: E402

OUT = pathlib.Path(__file__).with_name('out')
OUT.mkdir(exist_ok=True)
BASE = 'masterpiece, best quality, comic, manga page, monochrome, greyscale, screentone, panel borders, 1girl, short black bob hair, glasses, school blazer, '
REQ = {'3panels': '3 panels, vertical strip', '4panels': '4koma, 4 panels', '6panels': 'multiple panels, 6 panels'}


def main():
    rec = []
    for k, add in REQ.items():
        for s in (51, 52, 53, 54):
            b, t = comfy.run(comfy.t2i(BASE + add, s, 832, 1216, prefix='v3poc_p10'))
            (OUT / f'{k}_{s}.png').write_bytes(b[0])
            rec.append({'file': f'{k}_{s}.png', 'req': k, 'seed': s, 'sec': round(t, 1)})
    (OUT / 'gen.json').write_text(json.dumps(rec, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
