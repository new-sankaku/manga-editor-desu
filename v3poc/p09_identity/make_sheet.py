"""P9 の目で見る一覧。場面ごとに、文字だけ・参照0.5・参照0.8・別キャラを並べる。"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'common'))
from sheet import sheet  # noqa: E402

OUT = HERE / 'out'
MODES = [('text', '文字だけ'), ('ipa05', '参照0.5'), ('ipa08', '参照0.8'), ('other', '別キャラ')]
rows = [('参照', [(OUT / 'ref.png', '参照')])]
for sc in ('run', 'eat', 'side', 'laugh'):
    for m, lb in MODES:
        rows.append((f'{sc} {lb}', [(OUT / f'{sc}_{m}_{s}.png', str(s)) for s in (21, 22, 23)]))
sheet(rows[:9], OUT / 'sheet_1.png', tw=110, label_w=130)
sheet([rows[0]] + rows[9:], OUT / 'sheet_2.png', tw=110, label_w=130)
