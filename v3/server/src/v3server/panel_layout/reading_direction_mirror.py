"""読む向きの扱い（試作 p34）。
- 左から読む割りは、左右を反転してから右から読む前提の検査にかける。検査を向きごとに2つ書かない。
- ページの左右・めくりの前のページ・ノドの側・向かい合う2ページ。
読む向きで変わるのは表示位置だけで、絵は反転しない（V3細部の決めごと 1.5）。反転は検査のための写しにだけ使う。"""
from typing import Literal

from v3server.name_structure.name_draft_schema import NameDraft, NamePage
from v3server.name_structure.reading_direction import PageSpec, ReadingDirection
from v3server.panel_layout.panel_geometry import Box, Point, Polygon

PageSide = Literal["左", "右"]


def frame_span_width(page: NamePage, spec: PageSpec) -> float:
    """ページの座標で、コマを置く範囲の左端（x=0）から右端までの幅。2ページ分の見開きは右のページの基本枠の右端まで。"""
    if occupies_two_pages(page):
        ox, _ = spec.frame_origin_in_trim()
        return 2 * spec.frame_width_mm + 2 * ox
    return spec.frame_width_mm


def mirror_x(x: float, width: float) -> float:
    """コマを置く範囲（幅 width）の左右の反転。範囲の外（断ち切り）の点も同じ式で移る。"""
    return width - x


def mirror_polygon(poly: Polygon, width: float) -> list[Point]:
    """左右を反転する。頂点の回る向きは変わるが、面積・重なりの計算には影響しない。"""
    return [(mirror_x(x, width), y) for x, y in poly]


def mirror_box(box: Box, width: float) -> Box:
    x0, y0, x1, y1 = box
    return mirror_x(x1, width), y0, mirror_x(x0, width), y1


def to_right_to_left_polygon(poly: Polygon, direction: ReadingDirection, width: float) -> list[Point]:
    """右から読む検査にかけるための写し。右から読む作品はそのまま、左から読む作品は反転する。width は frame_span_width。
    試作 p34：48の割りを反転して「左から」で検査すると48/48で元と同じ結果。誤って「右から」で検査すると48/48で崩れとして出た。"""
    return list(poly) if direction == "right_to_left" else mirror_polygon(poly, width)


def to_right_to_left_box(box: Box, direction: ReadingDirection, width: float) -> Box:
    return box if direction == "right_to_left" else mirror_box(box, width)


def before_turn_side(direction: ReadingDirection) -> PageSide:
    """めくる直前に読むページの側。右から読む本は右→左と読んでからめくるので左、左から読む本は右。"""
    return "左" if direction == "right_to_left" else "右"


def opposite_side(side: PageSide) -> PageSide:
    return "右" if side == "左" else "左"


def occupies_two_pages(page: NamePage) -> bool:
    """見開きのページが左右の2ページ分を占めると決まっているか。決めていなければ1ページとして数える。"""
    return page.spread and page.spread_occupies_two_pages is True


def _page_slots(draft: NameDraft) -> list[tuple[PageSide, PageSide]]:
    """各ページの（最初の側, 最後の側）。2ページ分を占める見開きは、左右の2つの側を続けて使う。"""
    first: PageSide = "左" if draft.first_page_is_left else "右"
    out = []
    slot = 0
    for pg in draft.pages:
        n = 2 if occupies_two_pages(pg) else 1
        sides = [first if (slot + k) % 2 == 0 else opposite_side(first) for k in range(n)]
        out.append((sides[0], sides[-1]))
        slot += n
    return out


def page_sides(draft: NameDraft) -> list[PageSide]:
    """draft.pages の並びの順に、各ページが左右どちらに置かれるか（2ページ分の見開きは最初の側）。1ページ目の側は draft が持つ。
    spread_occupies_two_pages が無い見開きは1ページとして数える。"""
    return [a for a, _ in _page_slots(draft)]


def before_turn_page_indices(draft: NameDraft) -> list[int]:
    """めくりの前のページ（draft.pages の添字）。2ページ分の見開きは最後の側で見る。最後のページの後にはめくりが無いので入れない。"""
    side = before_turn_side(draft.reading_direction)
    slots = _page_slots(draft)
    return [i for i, (_, last) in enumerate(slots) if last == side and i < len(slots) - 1]


def facing_page_pairs(draft: NameDraft) -> list[tuple[int, int]]:
    """同時に目に入る2ページ（先に読む方, 後に読む方）の添字。めくりの後のページと、めくりの前のページの組。
    2ページ分を占める見開きは、それだけで1組なので入れない。"""
    side = before_turn_side(draft.reading_direction)
    slots = _page_slots(draft)
    two = [occupies_two_pages(pg) for pg in draft.pages]
    return [(i, i + 1) for i in range(len(slots) - 1)
            if not two[i] and not two[i + 1] and slots[i][0] != side and slots[i + 1][0] == side]


def spread_gutter_x(spec: PageSpec) -> float:
    """2ページ分を占める見開きのノドの x（左のページの基本枠の左上が原点）。"""
    ox, _ = spec.frame_origin_in_trim()
    return spec.frame_width_mm + ox


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
