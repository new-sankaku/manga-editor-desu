"""入稿前の確かめ（V3細部の決めごと 3章・7章。V3点検の結果 §3）。書き出す前に、ページごとの問題と場所を返す。

確かめること（kind）:
- settings：作品の入稿の設定・ノンブルの設定が無い（紙の作品）
- page_kind・color_mode・dpi：ページの種類・色の種類・解像度が決まっていない
- image_resolution：置いた絵の実際の解像度（絵の画素 ÷ 置いた大きさ）がページの解像度より低い
- color_image：2階調・グレーのページに色のある絵がある（書き出しで白黒にする。知らせるだけ）
- spread：見開きの組が崩れている・見開きの2ページの色の種類か解像度が違う
- safe_area：文字が安全線（PrintSettings.safe_area）の外に出ている（描き文字は知らせるだけ）
- text_overflow：文字が箱に入りきらない
- font：書体のファイルが無い・書体に無い字がある・組版や大きさが決まっていない（書き出しが止まる所）
- held_change：判断待ち（HeldAiChange）が残っている
- ai_candidate・job：まだ選んでいない生成の候補・終わっていない生成の依頼がある
- page_count：話か巻のページ数が、決めた倍数（4・8）になっていない

severity は error（書き出しが止まるか、入稿で戻される）と warning（人が見て決める）。
文字の組み方は書き出しと同じ page_render.text_jobs と render_text.js（measure）を使う（確かめと書き出しで結果が違わないように）。
"""

import io
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.page_item_tables import PageItem
from v3server.canonical_tables.service_and_job_tables import Job
from v3server.canonical_tables.text_and_layer_tables import HeldAiChange, PanelLayer, TextItem
from v3server.canonical_tables.work_tree_tables import Episode, Page, Panel, Work
from v3server.image_file_storage import read_image
from v3server.name_structure.image_placement import ImagePlacement
from v3server.name_structure.item_transform import ItemTransform, transform_matrix
from v3server.name_structure.print_settings import PrintSettings
from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.book_layout import (
    PagePlan,
    check_spreads,
    episode_pages,
    episode_spreads,
    nombre_settings_of,
    plan_pages,
    print_settings_of,
)
from v3server.print_export.page_render import PageContent, RenderRefused, _text_job, text_fill
from v3server.print_export.text_render import RenderedText, TextRenderError

Severity = Literal["error", "warning"]
# 生成の依頼のうち、終わったもの（ほかの状態は、まだ候補が増えうる）
JOB_FINISHED = {"done", "cancelled", "stopped"}


@dataclass
class Issue:
    page_id: str | None
    kind: str
    severity: Severity
    message: str
    # どこか：{"table": 表, "id": 行, ...}。ページ全体・作品全体の問題は None
    location: dict[str, Any] | None = None


def effective_dpi(placement: dict) -> float:
    """置いた絵の実際の解像度（絵の1画素がページで何 mm になるかから）。"""
    m = ImagePlacement.model_validate(placement).image_px_to_page_mm()
    mm_per_px = math.sqrt(abs(np.linalg.det(m[:2, :2])))
    return 25.4 / mm_per_px


def has_color(img: Image.Image) -> bool:
    """見える画素に、R・G・B が揃っていない画素が1つでもあるか（JPEG のにじみも色として数える）。"""
    arr = np.asarray(img.convert("RGBA"))
    seen = arr[..., 3] > 0
    rgb = arr[..., :3][seen].astype(np.int16)
    return bool(rgb.size) and bool(np.any((rgb[:, 0] != rgb[:, 1]) | (rgb[:, 1] != rgb[:, 2])))


def safe_area_overrun(corners_mm: list[tuple[float, float]], side: str, spec: PageSpec, settings: PrintSettings
                      ) -> list[str]:
    """安全線の外に出た辺（上・下・ノド・小口）。corners_mm は仕上がりの左上を原点にした mm。
    左のページのノドは右の端、右のページのノドは左の端。"""
    sa = settings.safe_area
    xs = [p[0] for p in corners_mm]
    ys = [p[1] for p in corners_mm]
    left_limit, right_limit = (sa.outer_mm, spec.trim_width_mm - sa.gutter_mm) if side == "left" else \
        (sa.gutter_mm, spec.trim_width_mm - sa.outer_mm)
    left_name, right_name = ("小口", "ノド") if side == "left" else ("ノド", "小口")
    out = []
    if min(ys) < sa.top_mm:
        out.append("上")
    if max(ys) > spec.trim_height_mm - sa.bottom_mm:
        out.append("下")
    if min(xs) < left_limit:
        out.append(left_name)
    if max(xs) > right_limit:
        out.append(right_name)
    return out


def page_count_problem(count: int, multiple: int | None) -> str | None:
    if multiple is None or count % multiple == 0:
        return None
    return f"ページ数 {count} が {multiple} の倍数でない（あと {multiple - count % multiple} ページで揃う）"


def _corners_in_trim(t, spec: PageSpec) -> list[tuple[float, float]]:
    """文字の箱（基本枠の座標）の四隅を、置き方を当ててから仕上がりの座標にする。"""
    ox, oy = spec.frame_origin_in_trim()
    b = t.box_mm
    m = transform_matrix(ItemTransform.model_validate(t.transform or {}), b)
    pts = [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]
    return [(float(q[0]) + ox, float(q[1]) + oy) for q in (m @ np.array([x, y, 1.0]) for x, y in pts)]


async def _rows(session: AsyncSession, model, page_id: str) -> list:
    q = select(model).where(model.page_id == page_id, model.removed.is_(False))
    return list((await session.execute(q)).scalars())


def _check_text(session_texts, content: PageContent, plan: PagePlan, spec: PageSpec, ps: PrintSettings,
                measure: Callable[[list[dict]], list[RenderedText]], font_path: Callable[[str], str]) -> list[Issue]:
    pid = plan.page.id
    issues: list[Issue] = []
    jobs: list[tuple[Any, dict]] = []
    dpi = plan.dpi
    for t in sorted(session_texts, key=lambda t: t.order):
        loc = {"table": "text_items", "id": t.id, "box_mm": t.box_mm}
        if t.box_mm is not None and plan.side is not None:
            over = safe_area_overrun(_corners_in_trim(t, spec), plan.side, spec, ps)
            if over:
                issues.append(Issue(pid, "safe_area", "warning" if t.item_kind == "drawn_sfx" else "error",
                                    f"文字「{t.text[:12]}」が安全線の外に出ている（{'・'.join(over)}）", loc))
        try:
            text_fill(t)
        except RenderRefused as e:
            # 解像度が決まっていなくても出す。色を補わないので、この文字は書き出せない
            issues.append(Issue(pid, "text_color", "error", str(e), loc))
            continue
        if dpi is None:
            continue
        try:
            jobs.append((t, _text_job(t, content, dpi, font_path)))
        except (RenderRefused, TextRenderError) as e:
            issues.append(Issue(pid, "font", "error", str(e), loc))
    if jobs:
        for (t, _), rt in zip(jobs, measure([j for _, j in jobs]), strict=False):
            loc = {"table": "text_items", "id": t.id, "box_mm": t.box_mm}
            if rt.missing_chars:
                issues.append(Issue(pid, "font", "error",
                                    f"文字「{t.text[:12]}」の書体に無い字がある: {''.join(rt.missing_chars)}", loc))
            if rt.overflow:
                issues.append(Issue(pid, "text_overflow", "error", f"文字「{t.text[:12]}」が箱に入りきらない", loc))
    return issues


async def _check_images(session: AsyncSession, plan: PagePlan, placed: list[tuple[str, str, str, dict | None]]
                        ) -> list[Issue]:
    """placed：(表, 行の id, 絵の id, 置き場)。"""
    pid = plan.page.id
    issues: list[Issue] = []
    for table, row_id, image_id, placement in placed:
        loc = {"table": table, "id": row_id, "image_id": image_id}
        if placement is None:
            issues.append(Issue(pid, "image_resolution", "error", f"絵 {image_id} の置き場が決まっていない", loc))
            continue
        eff = effective_dpi(placement)
        if plan.dpi is not None and eff < plan.dpi:
            issues.append(Issue(pid, "image_resolution", "error",
                                f"絵 {image_id} の実際の解像度 {eff:.0f}dpi が、ページの解像度 {plan.dpi}dpi より低い",
                                {**loc, "effective_dpi": round(eff, 1)}))
        if plan.color_mode in ("bilevel", "grayscale"):
            f = await session.get(ImageFile, image_id)
            if has_color(Image.open(io.BytesIO(read_image(f.sha256)))):
                mode = {"bilevel": "2階調", "grayscale": "グレー"}[plan.color_mode]
                issues.append(Issue(pid, "color_image", "warning",
                                    f"{mode}のページに色のある絵 {image_id} がある（書き出しで{mode}にする）", loc))
    return issues


async def _check_ai(session: AsyncSession, pid: str, in_use: set[str]) -> list[Issue]:
    issues: list[Issue] = []
    held = (await session.execute(select(HeldAiChange).where(HeldAiChange.page_id == pid,
                                                             HeldAiChange.status == "open"))).scalars().all()
    for h in held:
        issues.append(Issue(pid, "held_change", "error", f"判断待ち（{h.kind}・{h.target_table}.{h.field}）が残っている",
                            {"table": "held_ai_changes", "id": h.id, "target_table": h.target_table,
                             "target_id": h.target_id}))
    jobs = (await session.execute(select(Job).where(Job.page_id == pid, Job.status.not_in(JOB_FINISHED)))
            ).scalars().all()
    for j in jobs:
        issues.append(Issue(pid, "job", "error", f"生成の依頼 {j.id}（{j.process}）が終わっていない（{j.status}）",
                            {"table": "jobs", "id": j.id}))
    cands = (await session.execute(select(ImageFile).where(ImageFile.page_id == pid, ImageFile.origin == "generated",
                                                           ImageFile.discarded.is_(False)))).scalars().all()
    # 採っていない候補の版だけ（採った版の元の版は、前の版として残るので数えない）
    ancestors = {c.based_on_image_id for c in cands if c.based_on_image_id}
    for c in cands:
        if c.id in in_use or c.id in ancestors:
            continue
        issues.append(Issue(pid, "ai_candidate", "warning", f"まだ選んでいない生成の候補 {c.id} がある（採るか却下する）",
                            {"table": "image_files", "id": c.id, "panel_id": c.panel_id}))
    return issues


async def run_preflight(session: AsyncSession, work: Work, page_ids: list[str] | None,
                        measure: Callable[[list[dict]], list[RenderedText]], font_path: Callable[[str], str]
                        ) -> list[Issue]:
    issues: list[Issue] = []
    if work.page_spec is None:
        return [Issue(None, "settings", "error", "作品のページの寸法（page_spec）が決まっていない")]
    spec = PageSpec.model_validate(work.page_spec)
    ps = print_settings_of(work)
    if ps is None:
        return [Issue(None, "settings", "error", "作品の入稿の設定（preferences.print）が無い")]
    if work.medium == "paper" and nombre_settings_of(work) is None:
        issues.append(Issue(None, "settings", "error", "紙の作品なのに、ノンブルの設定（preferences.nombre）が無い"))
    if work.first_page_is_left is None:
        issues.append(Issue(None, "settings", "error", "1ページ目を左に置くか（作品の first_page_is_left）が決まっていない"
                                                        "（見開き・ノンブル・安全線のノドが決まらない）"))
    if page_ids is None:
        q = (select(Page.id).join(Episode, Episode.id == Page.episode_id)
             .where(Page.work_id == work.id, Page.removed.is_(False), Episode.removed.is_(False))
             .order_by(Episode.number, Page.number, Page.id))
        page_ids = list((await session.execute(q)).scalars())
    plans = await plan_pages(session, work, page_ids)

    # 見開きと、ページ数の倍数（話ごと）
    episodes = {p.episode.id: p.episode for p in plans.values()}
    counts: dict[str, int] = {}
    for ep in episodes.values():
        pages = await episode_pages(session, ep.id)
        for sp, msg in check_spreads(pages, await episode_spreads(session, ep.id), work):
            for pid in (sp.first_page_id, sp.second_page_id):
                issues.append(Issue(pid, "spread", "error", msg, {"table": "spreads", "id": sp.id}))
        key = ep.id if ps.page_count_scope == "episode" else ep.volume_id
        if ps.page_count_scope == "volume" and key in counts:
            continue
        if ps.page_count_scope == "volume":
            vol_eps = (await session.execute(select(Episode).where(Episode.volume_id == ep.volume_id,
                                                                   Episode.removed.is_(False)))).scalars().all()
            counts[key] = sum([len(await episode_pages(session, e.id)) for e in vol_eps])
        else:
            counts[key] = len(pages)
        problem = page_count_problem(counts[key], ps.page_count_multiple)
        if problem:
            where = {"table": "episodes", "id": ep.id} if ps.page_count_scope == "episode" else \
                {"table": "volumes", "id": ep.volume_id}
            issues.append(Issue(None, "page_count", "error", problem, where))

    for pid in page_ids:
        plan = plans[pid]
        page = plan.page
        if page.page_kind is None:
            issues.append(Issue(pid, "page_kind", "error", "ページの種類（表紙・カラー・本文・白ページ）が決まっていない"))
        if plan.color_mode is None:
            issues.append(Issue(pid, "color_mode", "error", "色の種類が決まっていない"))
        if plan.dpi is None:
            issues.append(Issue(pid, "dpi", "error", "解像度が決まっていない"))
        sp = plan.spread
        if sp is not None:
            other_id = sp.second_page_id if sp.first_page_id == pid else sp.first_page_id
            other = plans.get(other_id)
            if other is not None and (other.color_mode != plan.color_mode or other.dpi != plan.dpi):
                issues.append(Issue(pid, "spread", "error",
                                    f"見開きの相手のページと色の種類か解像度が違う（{plan.color_mode} {plan.dpi}dpi・"
                                    f"{other.color_mode} {other.dpi}dpi）", {"table": "spreads", "id": sp.id}))
        panels, layers = await _rows(session, Panel, pid), await _rows(session, PanelLayer, pid)
        texts, items = await _rows(session, TextItem, pid), await _rows(session, PageItem, pid)
        placed = [("panels", p.id, p.image_id, p.image_placement) for p in panels if p.image_id]
        placed += [("panel_layers", la.id, la.image_id, la.placement) for la in layers if la.image_id]
        if sp is not None and sp.image_id and sp.first_page_id == pid:
            placed.append(("spreads", sp.id, sp.image_id, sp.image_placement))
        issues += await _check_images(session, plan, placed)
        content = PageContent(page_id=pid, spec=spec, text_direction=work.text_direction,
                              preferences=work.preferences or {}, panels=panels, layers=layers, texts=texts,
                              page_items=items, images={})
        issues += _check_text(texts, content, plan, spec, ps, measure, font_path)
        issues += await _check_ai(session, pid, {x[2] for x in placed})
    return issues


def issues_json(issues: list[Issue]) -> dict[str, Any]:
    return {"ok": not any(i.severity == "error" for i in issues),
            "errors": sum(1 for i in issues if i.severity == "error"),
            "warnings": sum(1 for i in issues if i.severity == "warning"),
            "issues": [asdict(i) for i in issues]}
