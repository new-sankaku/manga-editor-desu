"""ネームの案を見る口と、今のネームを形にして返す口。案を出す・採用するのは操作（/works/{id}/ops）で行う。
外のネームの取り込み（MangaImport）と、コマ割りの計算の案も、ここから同じ案の形にして出す。"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from v3server.canonical_tables.name_proposal_tables import NameProposal
from v3server.canonical_tables.work_tree_tables import Episode, Work
from v3server.http_routes.http_dependencies import (
    ActorDep,
    AuthzDep,
    SessionDep,
    require,
    row,
)
from v3server.name_import.manga_import_reader import (
    ImageCovers,
    MangaImportError,
    read_manga_import,
)
from v3server.name_structure.reading_direction import PageSpec
from v3server.operations import operation_submit_and_undo
from v3server.operations.name_draft_conversion import name_draft_of_episode
from v3server.operations.name_proposal_operations import SubmitNameProposal
from v3server.operations.operation_base import get_in_work, work_obj
from v3server.operations.panel_layout_proposal import propose_panel_layout
from v3server.v3_error_types import Invalid

router = APIRouter()

PROPOSAL_FIELDS = ("id", "episode_id", "made_by", "task", "submitted_by_kind", "submitted_by_id", "job_id", "pages", "note",
                   "status", "created_at")


@router.get("/works/{work_id}/episodes/{episode_id}/name-proposals")
async def list_name_proposals(work_id: str, episode_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    await get_in_work(session, Episode, episode_id, work_id)
    q = select(NameProposal).where(NameProposal.episode_id == episode_id).order_by(NameProposal.created_at)
    return [row(p, *PROPOSAL_FIELDS) for p in (await session.execute(q)).scalars()]


@router.get("/works/{work_id}/episodes/{episode_id}/name-draft")
async def get_name_draft(work_id: str, episode_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """今のページとコマを、ネームの形（name_structure の NameDraft）で返す。誰が作ったかに依らず同じ形。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    await get_in_work(session, Episode, episode_id, work_id)
    work = await session.get(Work, work_id)
    return (await name_draft_of_episode(session, work, episode_id)).model_dump()


class NameImportRequest(BaseModel):
    # MangaImport v1 の文書（llm_doc/Manga2Manga計画.md）
    document: dict[str, Any]
    # ページ画像が仕上がりの範囲か、塗り足しまで含む範囲か。座標を mm に直すのに要る
    image_covers: ImageCovers
    # 取り込んだ最初のページの番号と、最初のコマの番号（コマの番号は作品の通し番号）
    first_page_number: int
    first_panel_number: int
    note: str | None = None


@router.post("/works/{work_id}/episodes/{episode_id}/name-imports", status_code=201)
async def import_name(work_id: str, episode_id: str, body: NameImportRequest, session: SessionDep, authz: AuthzDep,
                      actor: ActorDep):
    """外で解析したネーム（MangaImport）を、取り込みの案（made_by=imported）にする。採用は apply_name_proposal。
    分からない項目は未定のまま入り、その項目を使う検査は「データなし」になる。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    work = await session.get(Work, work_id)
    if work.page_spec is None:
        raise Invalid("作品の page_spec がまだ決まっていない")
    try:
        read = read_manga_import(body.document, PageSpec.model_validate(work.page_spec), body.image_covers,
                                 body.first_page_number, body.first_panel_number)
    except (MangaImportError, KeyError, TypeError, ValueError) as e:
        raise Invalid(f"MangaImport を読めない: {e}") from e
    op = SubmitNameProposal(episode_id=episode_id, made_by="imported", pages=read.pages, note=body.note,
                            source_document=body.document)
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id, op)
    return {"proposal_id": op.id, "event_id": event.id, "dropped": read.dropped}


@router.post("/works/{work_id}/episodes/{episode_id}/panel-layout-proposals", status_code=201)
async def layout_proposal(work_id: str, episode_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """今のネームにコマ割りの計算をかけ、案にする。人が描いた枠（人の手の印）は固定する。
    コマ割りのAIの関与が「AIに任せる」なら、そのまま入る。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    await get_in_work(session, Episode, episode_id, work_id)
    return await propose_panel_layout(session, authz, actor, work_id, episode_id)
