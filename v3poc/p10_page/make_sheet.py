"""P10 の目で見る一覧。コマ数の指定ごとに seed4 枚。"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402

OUT = HERE / 'out'
sheet([(k, [(OUT / f'{k}_{s}.png', str(s)) for s in (51, 52, 53, 54)]) for k in ('3panels', '4panels', '6panels')], OUT / 'sheet.png', tw=200, label_w=100)
