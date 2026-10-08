"""読む向きの扱い（試作 p34）。
- 左から読む割りは、左右を反転してから右から読む前提の検査にかける。検査を向きごとに2つ書かない。
- ページの左右・めくりの前のページ・ノドの側・向かい合う2ページ。
読む向きで変わるのは表示位置だけで、絵は反転しない（V3細部の決めごと 1.5）。反転は検査のための写しにだけ使う。"""
from typing import Literal

from v3server.name_structure.name_draft_schema import NameDraft, NamePage
from v3server.name_structure.reading_direction import PageSpec, ReadingDirection
from v3server.panel_layout.panel_geometry import Box, Point, Polygon

PageSide = Literal["左", "右"]


def mirror_x(x: float, spec: PageSpec) -> float:
    """基本枠の左右の反転。基本枠の外（断ち切り）の点も同じ式で移る。"""
    return spec.frame_width_mm - x


def mirror_polygon(poly: Polygon, spec: PageSpec) -> list[Point]:
    """左右を反転する。頂点の回る向きは変わるが、面積・重なりの計算には影響しない。"""
    return [(mirror_x(x, spec), y) for x, y in poly]


def mirror_box(box: Box, spec: PageSpec) -> Box:
    x0, y0, x1, y1 = box
    return mirror_x(x1, spec), y0, mirror_x(x0, spec), y1


def to_right_to_left_polygon(poly: Polygon, direction: ReadingDirection, spec: PageSpec) -> list[Point]:
    """右から読む検査にかけるための写し。右から読む作品はそのまま、左から読む作品は反転する。
    試作 p34：48の割りを反転して「左から」で検査すると48/48で元と同じ結果。誤って「右から」で検査すると48/48で崩れとして出た。"""
    return list(poly) if direction == "right_to_left" else mirror_polygon(poly, spec)


def to_right_to_left_box(box: Box, direction: ReadingDirection, spec: PageSpec) -> Box:
    return box if direction == "right_to_left" else mirror_box(box, spec)


def before_turn_side(direction: ReadingDirection) -> PageSide:
    """めくる直前に読むページの側。右から読む本は右→左と読んでからめくるので左、左から読む本は右。"""
    return "左" if direction == "right_to_left" else "右"


def opposite_side(side: PageSide) -> PageSide:
    return "右" if side == "左" else "左"


def page_sides(draft: NameDraft) -> list[PageSide]:
    """draft.pages の並びの順に、各ページが左右どちらに置かれるか。1ページ目の側は draft が持つ。
    見開きのページ（spread）も1ページとして数える（形に、見開きが2ページ分かの決まりが無い）。"""
    first: PageSide = "左" if draft.first_page_is_left else "右"
    return [first if i % 2 == 0 else opposite_side(first) for i in range(len(draft.pages))]


def before_turn_page_indices(draft: NameDraft) -> list[int]:
    """めくりの前のページ（draft.pages の添字）。最後のページの後にはめくりが無いので入れない。"""
    side = before_turn_side(draft.reading_direction)
    sides = page_sides(draft)
    return [i for i, s in enumerate(sides) if s == side and i < len(sides) - 1]


def facing_page_pairs(draft: NameDraft) -> list[tuple[int, int]]:
    """同時に目に入る2ページ（先に読む方, 後に読む方）の添字。めくりの後のページと、めくりの前のページの組。"""
    side = before_turn_side(draft.reading_direction)
    sides = page_sides(draft)
    return [(i, i + 1) for i in range(len(sides) - 1) if sides[i] != side and sides[i + 1] == side]


def gutter_edge_x(side: PageSide, spec: PageSpec) -> float:
    """ノド（綴じる側）にある基本枠の縦の辺の x。左のページは右の辺、右のページは左の辺。読む向きによらない。"""
    return spec.frame_width_mm if side == "左" else 0.0


def crosses_gutter_edge(xs: list[float], side: PageSide, spec: PageSpec, eps: float) -> bool:
    """点の x のどれかが、基本枠のノドの辺を越えてノドの側へ出ているか。"""
    edge = gutter_edge_x(side, spec)
    return any(x > edge + eps for x in xs) if side == "左" else any(x < edge - eps for x in xs)


def page_reading_sequence(page: NamePage) -> list[int]:
    """ページの中のコマの番号を読む順に並べたもの（rows を上の段から順につないだもの）。"""
    return [n for row in page.rows for n in row]
