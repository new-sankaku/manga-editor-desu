"""構成と確認の画面が読む口：ページの割り当ての一覧と、ページの下見の絵。

- GET /works/{id}/page-assignments：ページごとに、割り当てた人（assign_page）。割り当ては OpenFGA の組
  （page:{id} の assigned）にだけあるので、ページごとに読む。抜いたページも返す（removed で分かる）
- GET /works/{id}/pages/{page_id}/preview?size=：ページ1枚を小さく描いた PNG（長い辺が size 画素）。
  書き出しと同じ描き方（print_export/page_render.py）で、塗り足し込みのページを描く。描いた絵は page_previews に控え、
  ページの中身から作る鍵（page_content_key）が同じ間は描き直さない。中身（コマ・層・文字・トーン・絵・作品の寸法と設定）が
  変わると鍵が変わるので、古い絵は返らない。描けないとき（寸法が無い・線の控えが古いなど）は理由を返して止める
"""

import asyncio
import hashlib
import io
import json

from fastapi import APIRouter, Query
from fastapi.responses import Response
from PIL import Image
from sqlalchemy import select

from v3server.canonical_tables.service_set_and_preview_tables import PagePreview
from v3server.canonical_tables.work_tree_tables import Page, Work
from v3server.http_routes.http_dependencies import ActorDep, AuthzDep, SessionDep, require
from v3server.image_file_storage import read_image, store_image
from v3server.operations.operation_base import get_in_work, page_obj, work_obj
from v3server.print_export.export_runner import ExportRefused, load_page_content, render_page_image
from v3server.print_export.page_render import PageContent, RenderRefused
from v3server.print_export.print_pdf_export import canvas_size_mm
from v3server.print_export.text_render import TextRenderError
from v3server.v3_error_types import Invalid, NotFound

router = APIRouter()

# OpenFGA へ同時に読みに行く数
_READ_CONCURRENCY = 8


@router.get("/works/{work_id}/page-assignments")
async def list_page_assignments(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    pages = (await session.execute(select(Page).where(Page.work_id == work_id))).scalars().all()
    gate = asyncio.Semaphore(_READ_CONCURRENCY)

    async def users_of(pid: str) -> list[str]:
        async with gate:
            return sorted(t.user.removeprefix("user:") for t in await authz.read(page_obj(pid))
                          if t.relation == "assigned" and t.user.startswith("user:"))

    users = await asyncio.gather(*(users_of(p.id) for p in pages))
    return [{"page_id": p.id, "episode_id": p.episode_id, "number": p.number, "removed": p.removed, "users": u}
            for p, u in zip(pages, users, strict=True)]


def page_content_key(content: PageContent, size: int) -> str:
    """下見の絵の鍵。描くのに使う値を全部入れる（行の列・絵の sha256・寸法・作品の設定・文字の向き・大きさ）。"""

    def cols(obj):
        return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}

    body = {"spec": content.spec.model_dump(mode="json"), "text_direction": content.text_direction,
            "preferences": content.preferences, "images": content.images, "size": size,
            **{name: sorted((cols(x) for x in rows), key=lambda r: r["id"])
               for name, rows in (("panels", content.panels), ("layers", content.layers), ("texts", content.texts),
                                  ("page_items", content.page_items))}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


@router.get("/works/{work_id}/pages/{page_id}/preview")
async def get_page_preview(work_id: str, page_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                           size: int = Query(ge=64, le=2048)):
    await require(authz, actor, "can_view", work_obj(work_id))
    page = await get_in_work(session, Page, page_id, work_id)
    if page.removed:
        raise NotFound(f"ページ {page_id} は抜かれている")
    work = await session.get(Work, work_id)
    try:
        content = await load_page_content(session, work, page_id)
    except ExportRefused as e:
        raise Invalid(f"ページを描けない: {e}") from e
    key = page_content_key(content, size)
    cached = await session.get(PagePreview, (page_id, size))
    if cached is not None and cached.content_key == key:
        return Response(read_image(cached.sha256), media_type="image/png", headers={"X-V3-Preview-Cache": "hit"})
    # 長い辺が size 画素になる解像度で描く（塗り足し込み）
    dpi = size / (max(canvas_size_mm(content.spec)) / 25.4)
    try:
        img = await asyncio.to_thread(render_page_image, content, dpi)
    except (ExportRefused, RenderRefused, TextRenderError) as e:
        raise Invalid(f"ページを描けない: {e}") from e
    scale = size / max(img.size)
    if scale < 1:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    data = buf.getvalue()
    sha = store_image(data).sha256
    if cached is None:
        session.add(PagePreview(page_id=page_id, size=size, work_id=work_id, content_key=key, sha256=sha))
    else:
        cached.content_key, cached.sha256 = key, sha
    await session.commit()
    return Response(data, media_type="image/png", headers={"X-V3-Preview-Cache": "miss"})
