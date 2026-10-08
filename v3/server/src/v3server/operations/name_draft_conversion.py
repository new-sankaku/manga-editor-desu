"""ページとコマの行と、ネームの形（name_structure）の間の変換。

ネームは、人がコマ枠の道具で引いても、AIが段と比で決めても、取り込んでも、同じ行（Page・Panel）に入る。
検査（name_checks）とコマ割りの計算（panel_layout）は、ここで作った NameDraft だけを見る。誰が作ったかは見ない。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.work_tree_tables import Page, Panel, Work
from v3server.name_structure.name_draft_schema import NameDraft, NamePage, NamePanel
from v3server.name_structure.reading_direction import PageSpec
from v3server.v3_error_types import Invalid

# 作品の読む向き（rtl・ltr）と、ネームの形の読む向き
READING_DIRECTION = {"rtl": "right_to_left", "ltr": "left_to_right"}
# ページの行の layout に入れる項目（NamePage のうちコマ以外）
PAGE_LAYOUT_KEYS = ("spread", "rows", "row_height_ratios", "cell_width_ratios")


def page_layout_from_name_page(page: NamePage) -> dict[str, Any]:
    return page.model_dump(include=set(PAGE_LAYOUT_KEYS))


def panel_fields_from_name_panel(panel: NamePanel) -> dict[str, Any]:
    """コマの行に書く値。番号は読む順（order）に、枠は frame に、残りは content に入れる。"""
    content = panel.model_dump(exclude={"n", "frame"})
    return {"order": panel.n, "frame": panel.frame.model_dump() if panel.frame else {}, "content": content}


def name_panel_from_row(row: Panel) -> NamePanel:
    data = {**row.content, "n": row.order}
    if row.frame:
        data["frame"] = row.frame
    return NamePanel.model_validate(data)


def name_page_from_rows(page: Page, panels: list[Panel]) -> NamePage:
    if not page.layout:
        raise Invalid(f"page:{page.id} は段の割りがまだ無い")
    return NamePage.model_validate({**page.layout, "page": page.number,
                                    "panels": [name_panel_from_row(p) for p in sorted(panels, key=lambda p: p.order)]})


async def episode_rows(session: AsyncSession, episode_id: str) -> tuple[list[Page], dict[str, list[Panel]]]:
    """抜いていないページとコマ。ページは番号順。"""
    pages = (await session.execute(
        select(Page).where(Page.episode_id == episode_id, Page.removed.is_(False)).order_by(Page.number))).scalars().all()
    panels: dict[str, list[Panel]] = {p.id: [] for p in pages}
    if pages:
        rows = (await session.execute(
            select(Panel).where(Panel.page_id.in_(list(panels)), Panel.removed.is_(False)))).scalars().all()
        for r in rows:
            panels[r.page_id].append(r)
    return list(pages), panels


def _name_draft(work: Work, pages: list[NamePage]) -> NameDraft:
    """寸法と1ページ目の位置が作品に無ければ止める（既定の値で補わない）。"""
    if work.page_spec is None or work.first_page_is_left is None:
        raise Invalid("作品の page_spec と first_page_is_left がまだ決まっていない")
    return NameDraft(reading_direction=READING_DIRECTION[work.reading_direction],
                     page_spec=PageSpec.model_validate(work.page_spec),
                     first_page_is_left=work.first_page_is_left, pages=pages)


async def name_draft_of_episode(session: AsyncSession, work: Work, episode_id: str) -> NameDraft:
    """今のページとコマの行から、1話のネームを組む。"""
    pages, panels = await episode_rows(session, episode_id)
    return _name_draft(work, [name_page_from_rows(p, panels[p.id]) for p in pages])


def name_draft_of_proposal(work: Work, proposal_pages: list[Any]) -> NameDraft:
    """ネームの案を、今のページとコマと同じ形にする（採用する前に検査するため）。"""
    return _name_draft(work, [NamePage.model_validate(p) for p in proposal_pages])
