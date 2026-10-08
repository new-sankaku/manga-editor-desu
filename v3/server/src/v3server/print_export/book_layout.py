"""本の並び：ページの順・左右・見開きの組・ノンブルの番号と置き場・ページの色の種類と解像度（V3細部の決めごと 1章・3章・7章）。

書き出し（export_runner.py）・入稿前の確かめ（preflight_checks.py）・ページを並べ替える操作（book_structure_operations.py）が
同じここを使う（並びの決まりを1か所に置くため）。

- ページの順：話の中の抜いていないページを (number, id) の順に並べた位置
- 左右：話ごとに、1ページ目を左に置くか（作品の first_page_is_left）から交互に決める
- 見開き：2ページが話の中で隣り合い、読む順で前のページが「めくらずに見える側」にあること
  （右から読む本は前が右・後ろが左。左から読む本は前が左・後ろが右）
- ノンブル：番号は数える範囲（話か巻）の抜いていない全ページを数える（出さないページも数える）
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.work_tree_tables import Episode, Page, Spread, Work
from v3server.name_structure.print_settings import NombreSettings, PrintSettings
from v3server.name_structure.reading_direction import PageSpec

Side = Literal["left", "right"]


class BookLayoutError(ValueError):
    """並びの決まりに合わない（見開きの組が崩れた・決まっていない値がある）。"""


def page_sides(count: int, first_page_is_left: bool) -> list[Side]:
    return ["left" if (i % 2 == 0) == first_page_is_left else "right" for i in range(count)]


def spread_problem(first_index: int, second_index: int, sides: list[Side], reading_direction: str) -> str | None:
    """見開きの2ページの位置が組として正しくなければ、その理由。"""
    if second_index != first_index + 1:
        return f"見開きの2ページが隣り合っていない（{first_index + 1}ページ目と{second_index + 1}ページ目）"
    want = ("right", "left") if reading_direction == "rtl" else ("left", "right")
    got = (sides[first_index], sides[second_index])
    if got != want:
        side = {"left": "左", "right": "右"}
        return (f"見開きの前のページが{side[got[0]]}・後ろのページが{side[got[1]]}になる（{first_index + 1}・{second_index + 1}ページ目）。"
                f"この読む向きでは前が{side[want[0]]}・後ろが{side[want[1]]}")
    return None


def left_page_of_spread(reading_direction: str) -> Literal["first", "second"]:
    """見開きのどちらのページが左になるか（絵は反転しない。決めごと 1.3）。"""
    return "second" if reading_direction == "rtl" else "first"


async def episode_pages(session: AsyncSession, episode_id: str) -> list[Page]:
    q = select(Page).where(Page.episode_id == episode_id, Page.removed.is_(False)).order_by(Page.number, Page.id)
    return list((await session.execute(q)).scalars())


async def episode_spreads(session: AsyncSession, episode_id: str) -> list[Spread]:
    q = select(Spread).where(Spread.episode_id == episode_id, Spread.removed.is_(False))
    return list((await session.execute(q)).scalars())


def check_spreads(pages: list[Page], spreads: list[Spread], work: Work) -> list[tuple[Spread, str]]:
    """話の見開きのうち、組として崩れているものと理由。"""
    index = {p.id: i for i, p in enumerate(pages)}
    out: list[tuple[Spread, str]] = []
    used: dict[str, str] = {}
    sides = page_sides(len(pages), work.first_page_is_left) if work.first_page_is_left is not None else None
    for s in spreads:
        for pid in (s.first_page_id, s.second_page_id):
            if pid in used:
                out.append((s, f"ページ {pid} が2つの見開きに入っている"))
            used[pid] = s.id
        if s.first_page_id not in index or s.second_page_id not in index:
            out.append((s, "見開きのページが抜かれているか、別の話にある"))
            continue
        if sides is None:
            out.append((s, "1ページ目を左に置くか（作品の first_page_is_left）が決まっていないので、見開きの左右を決められない"))
            continue
        problem = spread_problem(index[s.first_page_id], index[s.second_page_id], sides, work.reading_direction)
        if problem:
            out.append((s, problem))
    return out


@dataclass
class NombrePlace:
    """ノンブル1つ。座標は仕上がりの左上を原点にした mm。anchor の点に、文字のブロックの anchor_x・anchor_y の辺を合わせる。"""

    text: str
    font_family: str
    font_size_pt: float
    color: str
    x_mm: float
    y_mm: float
    anchor_x: Literal["left", "center", "right"]
    anchor_y: Literal["top", "bottom"]
    hidden: bool


def nombre_place(settings: NombreSettings, display: str, number: int, side: Side, spec: PageSpec) -> NombrePlace | None:
    if display == "none":
        return None
    if display == "hidden":
        hp = settings.hidden_position
        # ノドは、左のページでは右の端、右のページでは左の端
        x, ax = (spec.trim_width_mm - hp.gutter_mm, "right") if side == "left" else (hp.gutter_mm, "left")
        return NombrePlace(str(number), settings.font_family, settings.hidden_font_size_pt, settings.color, x,
                           spec.trim_height_mm - hp.bottom_mm, ax, "bottom", True)
    pos = settings.position
    if pos.horizontal == "center":
        x, ax = spec.trim_width_mm / 2, "center"
    elif side == "left":
        x, ax = pos.side_mm, "left"
    else:
        x, ax = spec.trim_width_mm - pos.side_mm, "right"
    y, ay = (pos.edge_mm, "top") if pos.vertical == "top" else (spec.trim_height_mm - pos.edge_mm, "bottom")
    return NombrePlace(str(number), settings.font_family, settings.font_size_pt, settings.color, x, y, ax, ay, False)


@dataclass
class PagePlan:
    page: Page
    episode: Episode
    # 話の中の位置（0から）と、話のページ数
    index: int
    episode_page_count: int
    side: Side | None
    color_mode: str | None
    dpi: int | None
    nombre_display: str | None
    nombre_number: int | None
    spread: Spread | None
    # 見開きの中で左か右か
    spread_half: Side | None


async def _scope_offset(session: AsyncSession, episode: Episode, scope: str) -> int:
    """数える範囲（話か巻）で、この話の前にあるページの数。"""
    if scope == "episode":
        return 0
    q = select(Episode).where(Episode.volume_id == episode.volume_id, Episode.removed.is_(False),
                              Episode.number < episode.number)
    total = 0
    for ep in (await session.execute(q)).scalars():
        total += len(await episode_pages(session, ep.id))
    return total


def print_settings_of(work: Work) -> PrintSettings | None:
    raw = (work.preferences or {}).get("print")
    return PrintSettings.model_validate(raw) if raw else None


def nombre_settings_of(work: Work) -> NombreSettings | None:
    raw = (work.preferences or {}).get("nombre")
    return NombreSettings.model_validate(raw) if raw else None


async def plan_pages(session: AsyncSession, work: Work, page_ids: list[str]) -> dict[str, PagePlan]:
    """ページごとの並び・左右・色の種類・解像度・ノンブル・見開き。決まっていない値は None のまま返す（止めるかは呼ぶ側）。"""
    ps = print_settings_of(work)
    ns = nombre_settings_of(work)
    out: dict[str, PagePlan] = {}
    by_episode: dict[str, list[str]] = {}
    for pid in page_ids:
        page = await session.get(Page, pid)
        if page is None or page.work_id != work.id or page.removed:
            raise BookLayoutError(f"ページ {pid} が無いか、抜かれている")
        by_episode.setdefault(page.episode_id, []).append(pid)
    for episode_id, wanted in by_episode.items():
        episode = await session.get(Episode, episode_id)
        pages = await episode_pages(session, episode_id)
        spreads = {pid: s for s in await episode_spreads(session, episode_id)
                   for pid in (s.first_page_id, s.second_page_id)}
        sides = page_sides(len(pages), work.first_page_is_left) if work.first_page_is_left is not None else None
        offset = await _scope_offset(session, episode, ns.numbering_scope) if ns else 0
        left_role = left_page_of_spread(work.reading_direction)
        for i, page in enumerate(pages):
            if page.id not in wanted:
                continue
            color_mode = page.color_mode or (ps.color_mode if ps else None)
            dpi = page.dpi or (ps.dpi_by_color_mode[color_mode] if ps and color_mode else None)
            display = page.nombre_display or (ns.display_by_kind[page.page_kind] if ns and page.page_kind else None)
            spread = spreads.get(page.id)
            half = None
            if spread is not None:
                role = "first" if spread.first_page_id == page.id else "second"
                half = "left" if role == left_role else "right"
            out[page.id] = PagePlan(page, episode, i, len(pages), sides[i] if sides else None, color_mode, dpi, display,
                                    ns.start_number + offset + i if ns else None, spread, half)
    return out
