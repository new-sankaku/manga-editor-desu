"""ページとコマと文字の行と、ネームの形（name_structure）の間の変換。

ネームは、人がコマ枠の道具で引いても、AIが段と比で決めても、取り込んでも、同じ行（Page・Panel・TextItem）に入る。
検査（name_checks）とコマ割りの計算（panel_layout）は、ここで作った NameDraft だけを見る。誰が作ったかは見ない。

文字は TextItem の行で持つ（人が1つずつ直せるように）。ネームの形では
balloon・caption → NamePanel.balloons、drawn_sfx → NamePanel.sfx になる。
文字が未定か（None）は、コマの content の "balloons_decided"・"sfx_decided" で持つ。文字の行が1つでもあれば決まっている。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.text_and_layer_tables import TextItem
from v3server.canonical_tables.work_tree_tables import Page, Panel, Work
from v3server.name_structure.name_draft_schema import (
    Balloon,
    NameDraft,
    NamePage,
    NamePanel,
)
from v3server.name_structure.reading_direction import PageSpec
from v3server.v3_error_types import Invalid

# 作品の読む向き（rtl・ltr）と、ネームの形の読む向き
READING_DIRECTION = {"rtl": "right_to_left", "ltr": "left_to_right"}
# ページの行の layout に入れる項目（NamePage のうちページ番号とコマ以外の全部）
PAGE_LAYOUT_KEYS = tuple(k for k in NamePage.model_fields if k not in ("page", "panels"))
# コマの content に入れない項目（枠は frame、番号は order、文字は TextItem）
_NOT_IN_CONTENT = {"n", "frame", "balloons", "sfx"}
BALLOON_ITEM_KINDS = ("balloon", "caption")


def page_layout_from_name_page(page: NamePage) -> dict[str, Any]:
    return page.model_dump(include=set(PAGE_LAYOUT_KEYS), mode="json")


def panel_fields_from_name_panel(panel: NamePanel) -> dict[str, Any]:
    """コマの行に書く値。番号は読む順（order）に、枠は frame に、文字以外の残りは content に入れる。"""
    content = panel.model_dump(exclude=_NOT_IN_CONTENT, mode="json")
    content["balloons_decided"] = panel.balloons is not None
    content["sfx_decided"] = panel.sfx is not None
    return {"order": panel.n, "frame": panel.frame.model_dump(mode="json") if panel.frame else {}, "content": content}


def text_values_from_name_panel(panel: NamePanel) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    """コマの文字の行に書く値（吹き出しとナレーション, 描き文字）。未定なら None。"""
    balloons = None
    if panel.balloons is not None:
        balloons = [{"item_kind": "caption" if b.kind == "ナレーション" else "balloon", "order": i, "text": b.text,
                     "speaker": b.speaker, "balloon_kind": b.kind,
                     "box_mm": list(b.box_mm) if b.box_mm is not None else None,
                     "joined_to_previous": b.joined_to_previous} for i, b in enumerate(panel.balloons)]
    sfx = None
    if panel.sfx is not None:
        sfx = [{"item_kind": "drawn_sfx", "order": i, "text": t} for i, t in enumerate(panel.sfx)]
    return balloons, sfx


def _balloon_of(item: TextItem) -> Balloon:
    return Balloon(speaker=item.speaker, kind=item.balloon_kind, text=item.text,
                   box_mm=tuple(item.box_mm) if item.box_mm is not None else None,
                   joined_to_previous=item.joined_to_previous)


def name_panel_from_row(row: Panel, items: list[TextItem]) -> NamePanel:
    content = {k: v for k, v in row.content.items() if k not in ("balloons_decided", "sfx_decided")}
    data: dict[str, Any] = {**content, "n": row.order}
    if row.frame:
        data["frame"] = row.frame
    balloon_items = sorted((i for i in items if i.item_kind in BALLOON_ITEM_KINDS), key=lambda i: i.order)
    sfx_items = sorted((i for i in items if i.item_kind == "drawn_sfx"), key=lambda i: i.order)
    data["balloons"] = [_balloon_of(i) for i in balloon_items] \
        if balloon_items or row.content.get("balloons_decided") else None
    data["sfx"] = [i.text for i in sfx_items] if sfx_items or row.content.get("sfx_decided") else None
    return NamePanel.model_validate(data)


def name_page_from_rows(page: Page, panels: list[Panel], items_by_panel: dict[str, list[TextItem]]) -> NamePage:
    if "spread" not in page.layout:
        raise Invalid(f"page:{page.id} は見開きかどうか（layout.spread）がまだ決まっていない")
    return NamePage.model_validate({**page.layout, "page": page.number, "panels": [
        name_panel_from_row(p, items_by_panel.get(p.id, [])) for p in sorted(panels, key=lambda p: p.order)]})


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


async def text_items_of_panels(session: AsyncSession, panel_ids: list[str],
                               include_removed: bool = False) -> dict[str, list[TextItem]]:
    out: dict[str, list[TextItem]] = {pid: [] for pid in panel_ids}
    if not panel_ids:
        return out
    q = select(TextItem).where(TextItem.panel_id.in_(panel_ids))
    if not include_removed:
        q = q.where(TextItem.removed.is_(False))
    for item in (await session.execute(q)).scalars():
        out[item.panel_id].append(item)
    return out


def _name_draft(work: Work, pages: list[NamePage]) -> NameDraft:
    """寸法と1ページ目の位置が作品に無ければ止める（既定の値で補わない）。"""
    if work.page_spec is None or work.first_page_is_left is None:
        raise Invalid("作品の page_spec と first_page_is_left がまだ決まっていない")
    return NameDraft(reading_direction=READING_DIRECTION[work.reading_direction],
                     page_spec=PageSpec.model_validate(work.page_spec),
                     first_page_is_left=work.first_page_is_left, pages=pages)


async def name_draft_of_episode(session: AsyncSession, work: Work, episode_id: str) -> NameDraft:
    """今のページとコマと文字の行から、1話のネームを組む。"""
    pages, panels = await episode_rows(session, episode_id)
    items = await text_items_of_panels(session, [p.id for ps in panels.values() for p in ps])
    return _name_draft(work, [name_page_from_rows(p, panels[p.id], items) for p in pages])


def name_draft_of_proposal(work: Work, proposal_pages: list[Any]) -> NameDraft:
    """ネームの案を、今のページとコマと同じ形にする（採用する前に検査するため）。"""
    return _name_draft(work, [NamePage.model_validate(p) for p in proposal_pages])
