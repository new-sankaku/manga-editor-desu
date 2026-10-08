"""絵の版の出どころ（誰が・どこから・どの条件で）。読むだけ（正本は変えない）。

1枚の絵について：出どころ（生成・人が描いた・持ち込んだ・人が手を入れた）、登録した者、元の説明、利用の条件。
生成した絵は、依頼（job）から使ったサービスをたどり、そのサービスの利用規約の要点を条件として出す（V3細部の決めごと 20章）。
条件が記録されていない絵は terms_missing を立てる（書き出しのときに印を出すため）。補って埋めない。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.service_and_job_tables import Job, Service
from v3server.canonical_tables.text_and_layer_tables import PanelLayer
from v3server.operations.name_draft_conversion import episode_rows


async def version_provenance(session: AsyncSession, img: ImageFile) -> dict[str, Any]:
    out: dict[str, Any] = {
        "image_id": img.id, "origin": img.origin, "role": img.role, "based_on_image_id": img.based_on_image_id,
        "registered_by_kind": img.registered_by_kind, "registered_by_id": img.registered_by_id,
        "source_note": img.source_note, "created_at": img.created_at, "service": None, "job_id": img.job_id,
    }
    terms = img.usage_terms
    terms_from = "image" if terms is not None else None
    if img.origin == "generated" and img.job_id is not None:
        job = await session.get(Job, img.job_id)
        service = await session.get(Service, job.service_id)
        out["service"] = {"id": service.id, "name": service.name, "process": job.process}
        terms, terms_from = service.usage_terms, ("service" if service.usage_terms is not None else None)
    out["usage_terms"] = terms
    out["terms_from"] = terms_from
    # 人が自分で描いた絵（人が手を入れた絵も、元の版の条件は元の版の行に出る）は、作品の作り手の物として条件を求めない
    out["terms_missing"] = terms is None and img.origin in ("generated", "imported")
    return out


async def lineage(session: AsyncSession, img: ImageFile) -> list[dict[str, Any]]:
    """この版から元の版へさかのぼった出どころの列（先頭がこの版）。"""
    chain, seen = [], set()
    cur: ImageFile | None = img
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        chain.append(await version_provenance(session, cur))
        cur = await session.get(ImageFile, cur.based_on_image_id) if cur.based_on_image_id else None
    return chain


async def episode_image_provenance(session: AsyncSession, episode_id: str) -> list[dict[str, Any]]:
    """話の中の、コマに使っている絵（コマの絵と層の絵）ごとの出どころと、元の版までの列。"""
    pages, panels_by_page = await episode_rows(session, episode_id)
    panel_ids = [p.id for ps in panels_by_page.values() for p in ps]
    layers: dict[str, list[PanelLayer]] = {pid: [] for pid in panel_ids}
    if panel_ids:
        for layer in (await session.execute(select(PanelLayer).where(
                PanelLayer.panel_id.in_(panel_ids), PanelLayer.removed.is_(False)))).scalars():
            layers[layer.panel_id].append(layer)
    out = []
    for page in pages:
        for panel in sorted(panels_by_page[page.id], key=lambda p: p.order):
            uses = [("panel_image", None, panel.image_id)] + [
                ("layer", lay.id, lay.image_id) for lay in sorted(layers[panel.id], key=lambda x: x.stack_order)]
            for used_as, layer_id, image_id in uses:
                if image_id is None:
                    continue
                chain = await lineage(session, await session.get(ImageFile, image_id))
                out.append({"page": page.number, "panel_id": panel.id, "panel_order": panel.order, "used_as": used_as,
                            "layer_id": layer_id, "versions": chain,
                            "terms_missing": any(v["terms_missing"] for v in chain)})
    return out
