"""書き出し（PNG・PDF・PSD）を1件行う。書き出しの依頼（ExportRun）は http_routes/export_routes.py が作り、
Temporal の書き出しの待ち行列（print_export/export_workflow.py）の作業者がここを呼ぶ。

- どの書き出しも、ページの絵は page_render.py の同じ層から作る（PNG・PDF は層を重ねた絵、PSD は層のまま）
- 紙の大きさ（paper_mm）を渡すと、ページ（塗り足し込み）を紙の真ん中に置く。紙がページより小さければ止める
- PSD は層ごとの画素を置き場に残し、出力の layers に書く（PSD を戻すとき、書き出したときの画素と比べる。psd_import_matching.py）
- ペンの線は、層の控えの絵（画面が描いた物）を使う。控えが古ければ止める。PSD でも線は画素の層になる
- 足りない値（書体・文字の大きさ・枠の線など）は補わずに止め、理由を ExportRun.detail に書く
- ページごとの色の種類と解像度（book_layout.plan_pages）で出す。run.dpi があれば全ページをその解像度にする（下見など）。
  色の種類の絵は color_mode_output.py（2階調は1ビット、グレーは8ビット）。PSD は色の種類によらず層のまま RGB
- ファイルの名前は「略号_話2桁_ページ3桁」（決めごと 7章。ページは話の中の位置）。見開きを1枚で出すと「_前-後」
- 見開き（Spread）は render_spread で1枚に描き、spread_output で分ける：split（ノドで2ページ。どちらも塗り足しの幅だけ
  相手の絵を含む）・joined（1枚）・both。PDF は split だけ（ページの大きさが揃うように）、PSD は joined だけ
  （層をノドで切らずに渡すため）。見開きの PSD は戻せない（戻す口が1ページずつのため。未対応）
- ノンブルは作品の preferences.nombre があるときに描く（無ければ描かない。紙に出す作品で無いことは入稿前の確かめが出す）
"""

import io
import pathlib
import tempfile
from typing import Any

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.material_and_setting_tables import ExportRun
from v3server.canonical_tables.page_item_tables import PageItem
from v3server.canonical_tables.text_and_layer_tables import PanelLayer, TextItem
from v3server.canonical_tables.translation_review_import_tables import TextItemTranslation
from v3server.canonical_tables.work_tree_tables import Page, Panel, Spread, Work
from v3server.hand_tools.vector_strokes import refuse_stale_stroke_cache
from v3server.image_file_storage import read_image, store_image
from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.book_layout import (
    BookLayoutError,
    PagePlan,
    nombre_place,
    nombre_settings_of,
    plan_pages,
    print_settings_of,
)
from v3server.print_export.color_mode_output import ColorModeError, page_image
from v3server.print_export.layered_psd_request import build_psd_request, psd_layers_from_nodes, write_layered_psd
from v3server.print_export.page_render import (
    Node,
    PageContent,
    RenderedPage,
    RenderRefused,
    SpreadContent,
    render_page,
    render_spread,
    split_spread,
)
from v3server.print_export.print_pdf_export import canvas_size_mm, paper_size_px, write_print_pdf
from v3server.print_export.text_render import TextRenderError, font_path, render_texts
from v3server.server_settings import get_settings

# 書き出しの画面に出す文（ペンの線は PSD では画素になる）
PSD_STROKE_NOTE = "ペンの線は、PSD では画素の層になります（線のデータはアプリに残ります。PSD から線には戻りません）"


class ExportRefused(ValueError):
    pass


async def translated_texts(session: AsyncSession, work: Work, texts: list[TextItem], language: str) -> list[TextItem]:
    """文字を言語 language の訳文に差し替えた写し（行そのものは変えない）。訳文の無い文字があれば止める。
    元の文字で埋めない（どの言語の版か分からなくなる）。ルビと文字の一部の書式（spans）は元の文字の位置に付くので、訳文では外す。"""
    if language == (work.preferences or {}).get("language"):
        return texts
    rows = {t.text_item_id: t for t in (await session.execute(select(TextItemTranslation).where(
        TextItemTranslation.text_item_id.in_([t.id for t in texts]), TextItemTranslation.language == language,
        TextItemTranslation.removed.is_(False)))).scalars()}
    missing = [t.id for t in texts if t.id not in rows]
    if missing:
        raise ExportRefused(f"{language} の訳文が無い文字がある: {', '.join(missing)}")
    out = []
    for t in texts:
        tr = rows[t.id]
        values = {c.key: getattr(t, c.key) for c in TextItem.__table__.columns}
        values.update(text=tr.text, ruby=[], spans=[])
        if tr.writing_direction is not None:
            values["writing_direction"] = tr.writing_direction
        if tr.font_size_pt is not None:
            values["font_size_pt"] = tr.font_size_pt
        out.append(TextItem(**values))
    return out


async def load_page_content(session: AsyncSession, work: Work, page_id: str,
                            language: str | None = None) -> PageContent:
    page = await session.get(Page, page_id)
    if page is None or page.work_id != work.id or page.removed:
        raise ExportRefused(f"ページ {page_id} が無い")
    if work.page_spec is None:
        raise ExportRefused("作品のページの寸法（page_spec）が決まっていない")

    async def rows(model):
        q = select(model).where(model.page_id == page_id, model.removed.is_(False))
        return list((await session.execute(q)).scalars())

    panels, layers, texts, items = await rows(Panel), await rows(PanelLayer), await rows(TextItem), await rows(PageItem)
    if language is not None:
        texts = await translated_texts(session, work, texts, language)
    image_ids = {p.image_id for p in panels if p.image_id} | {la.image_id for la in layers if la.image_id}
    for it in items:
        target = (it.spec or {}).get("target") or {}
        if target.get("kind") == "mask":
            image_ids.add(target["image_id"])
    images = {}
    for iid in image_ids:
        img = await session.get(ImageFile, iid)
        await refuse_stale_stroke_cache(session, iid)
        images[iid] = img.sha256
    return PageContent(page_id=page.id, spec=PageSpec.model_validate(work.page_spec),
                       text_direction=work.text_direction, preferences=work.preferences or {}, panels=panels,
                       layers=layers, texts=texts, page_items=items, images=images)


def _text_renderer():
    s = get_settings()

    def texts(items):
        if not s.text_render_script:
            raise ExportRefused("V3_TEXT_RENDER_SCRIPT が無い。文字を描けない")
        return render_texts(items, s.node_executable, s.text_render_script)

    return texts, (lambda family: font_path(s.font_dir, family))


def _render(content: PageContent, dpi: int) -> RenderedPage:
    texts, fonts = _text_renderer()
    return render_page(content, dpi, lambda iid: read_image(content.images[iid]), texts, fonts)


async def render_page_preview(session: AsyncSession, work: Work, page_id: str, dpi: int) -> Image.Image:
    """1ページを書き出しと同じ描き方で描いた絵（RGB）。総合の工程（S6）が黒の量・白さを測り、VLM に見せるのに使う。
    文字があって文字の組み方（V3_TEXT_RENDER_SCRIPT）が無ければ ExportRefused。"""
    content = await load_page_content(session, work, page_id)
    return _render(content, dpi).composite.convert("RGB")


def _render_spread(content: SpreadContent, dpi: int) -> RenderedPage:
    texts, fonts = _text_renderer()
    images = {**content.left.images, **content.right.images, **content.images}
    return render_spread(content, dpi, lambda iid: read_image(images[iid]), texts, fonts)


def _on_paper(img: Image.Image, paper_px: tuple[int, int] | None) -> tuple[Image.Image, tuple[int, int]]:
    if paper_px is None:
        return img, (0, 0)
    if paper_px[0] < img.width or paper_px[1] < img.height:
        raise ExportRefused(f"紙 {paper_px}px がページ {img.size}px より小さい")
    off = ((paper_px[0] - img.width) // 2, (paper_px[1] - img.height) // 2)
    paper = Image.new("RGB", paper_px, (255, 255, 255))
    paper.paste(img, off)
    return paper, off


def _manifest(nodes: list[Node], offset: tuple[int, int], out: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for n in nodes:
        if n.children is not None:
            _manifest(n.children, offset, out)
            continue
        buf = io.BytesIO()
        n.image.save(buf, format="PNG")
        stored = store_image(buf.getvalue())
        out.append({"marker": n.marker, "table": n.table, "left": n.left + offset[0], "top": n.top + offset[1],
                    "width": n.image.width, "height": n.image.height, "sha256": stored.sha256})
    return out


def _file_stem(file_code: str, plan: PagePlan) -> str:
    return f"{file_code}_{plan.episode.number:02d}_{plan.index + 1:03d}"


async def _spread_content(session: AsyncSession, spread: Spread, left: PageContent, right: PageContent
                          ) -> SpreadContent:
    images = {}
    if spread.image_id:
        img = await session.get(ImageFile, spread.image_id)
        await refuse_stale_stroke_cache(session, spread.image_id)
        images[spread.image_id] = img.sha256
    return SpreadContent(spread.id, left, right, spread.image_id, spread.image_placement, spread.adjustments or [],
                         images)


def _check_plan(plan: PagePlan, run: ExportRun, nombre_on: bool) -> None:
    pid = plan.page.id
    if plan.color_mode is None:
        raise ExportRefused(f"ページ {pid} の色の種類が決まっていない（ページの color_mode か、作品の preferences.print）")
    if run.dpi is None and plan.dpi is None:
        raise ExportRefused(f"ページ {pid} の解像度が決まっていない（ページの dpi か、作品の preferences.print）")
    if nombre_on and plan.nombre_display is None:
        raise ExportRefused(f"ページ {pid} のノンブルの出し方が決まっていない（ページの種類 page_kind か nombre_display）")
    if nombre_on and plan.nombre_display != "none" and plan.side is None:
        raise ExportRefused("1ページ目を左に置くか（作品の first_page_is_left）が決まっていないので、ノンブルの左右を決められない")


def export_units(run_page_ids: list[str], plans: dict[str, PagePlan]) -> list[tuple[Spread | None, list[PagePlan]]]:
    """書き出す単位（1ページか、見開きの [左, 右]）を、渡したページの順に並べる。見開きの片方だけなら止める。"""
    units: list[tuple[Spread | None, list[PagePlan]]] = []
    seen: set[str] = set()
    for pid in run_page_ids:
        if pid in seen:
            continue
        plan = plans[pid]
        if plan.spread is None:
            units.append((None, [plan]))
            seen.add(pid)
            continue
        sp = plan.spread
        if sp.first_page_id not in plans or sp.second_page_id not in plans:
            raise ExportRefused(f"見開き {sp.id} の片方のページだけを書き出そうとした（見開きは2ページとも渡す）")
        a, b = plans[sp.first_page_id], plans[sp.second_page_id]
        units.append((sp, [a, b] if a.spread_half == "left" else [b, a]))
        seen.update({a.page.id, b.page.id})
    return units


def check_spread_output(fmt: str, spread_output: str | None, has_spread: bool) -> None:
    if not has_spread:
        return
    if spread_output is None:
        raise ExportRefused("見開きのページがあるのに、見開きの出し方（spread_output：split・joined・both）が決まっていない")
    if fmt == "pdf" and spread_output != "split":
        raise ExportRefused("PDF は見開きを split（ノドで2ページ）でしか出せない（PDF のページの大きさを揃えるため）")
    if fmt == "psd" and spread_output != "joined":
        raise ExportRefused("PSD は見開きを joined（1枚）でしか出せない（層をノドで切らずに渡すため）")


async def run_export(session: AsyncSession, run: ExportRun) -> list[dict[str, Any]]:
    s = get_settings()
    if not s.export_dir:
        raise ExportRefused("V3_EXPORT_DIR が無い。書き出したファイルを置く所が無い")
    work = await session.get(Work, run.work_id)
    if work.page_spec is None:
        raise ExportRefused("作品のページの寸法（page_spec）が決まっていない")
    spec = PageSpec.model_validate(work.page_spec)
    ps = print_settings_of(work)
    if ps is None:
        raise ExportRefused("作品の入稿の設定（preferences.print：略号・色の種類・解像度・安全線）が無い")
    ns = nombre_settings_of(work)
    if run.paper_mm:
        cw, ch = canvas_size_mm(spec)
        if run.paper_mm[0] < cw or run.paper_mm[1] < ch:
            raise ExportRefused(f"紙 {run.paper_mm}mm が塗り足し込みのページ {cw:.1f}x{ch:.1f}mm より小さい")
    try:
        plans = await plan_pages(session, work, list(run.page_ids))
    except BookLayoutError as e:
        raise ExportRefused(str(e)) from e
    for plan in plans.values():
        _check_plan(plan, run, ns is not None)
    units = export_units(list(run.page_ids), plans)
    check_spread_output(run.format, run.spread_output, any(sp is not None for sp, _ in units))
    folder = pathlib.Path(s.export_dir) / run.id
    folder.mkdir(parents=True, exist_ok=True)

    async def content_of(plan: PagePlan) -> PageContent:
        content = await load_page_content(session, work, plan.page.id, run.language)
        if ns is not None:
            content.nombre = nombre_place(ns, plan.nombre_display, plan.nombre_number, plan.side, spec)
        return content

    outputs: list[dict[str, Any]] = []
    pdf_pages: list[Image.Image] = []
    pdf_dpis: list[int] = []

    def emit(img: Image.Image, nodes: list[Node] | None, stem: str, dpi: int, color_mode: str,
             page_id: str | None, extra: dict[str, Any]) -> None:
        paper_px = paper_size_px(tuple(run.paper_mm), dpi) if run.paper_mm else None
        flat, offset = _on_paper(img, paper_px)
        meta = {"page_id": page_id, "dpi": dpi, "color_mode": color_mode, **extra}
        if run.format == "png":
            name = f"{stem}.png"
            flat.save(folder / name, dpi=(dpi, dpi))
            outputs.append({**meta, "file": name, "bytes": (folder / name).stat().st_size})
        elif run.format == "pdf":
            pdf_pages.append(flat)
            pdf_dpis.append(dpi)
        elif run.format == "psd":
            if not s.psd_writer_script:
                raise ExportRefused("V3_PSD_WRITER_SCRIPT が無い。PSD を書けない")
            name = f"{stem}.psd"
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = pathlib.Path(tmp)
                flat.save(tmpdir / "composite.png")
                layers = psd_layers_from_nodes(nodes, tmpdir, offset)
                req = build_psd_request(flat.width, flat.height, tmpdir / "composite.png", layers, folder / name)
                write_layered_psd(req, s.node_executable, pathlib.Path(s.psd_writer_script), 300)
            outputs.append({**meta, "file": name, "bytes": (folder / name).stat().st_size,
                            "layers": _manifest(nodes, offset, []), "offset_px": list(offset),
                            "note": PSD_STROKE_NOTE})
        else:
            raise ExportRefused(f"知らない書き出しの形: {run.format}")

    def as_output(rendered: RenderedPage, color_mode: str, dpi: int) -> Image.Image:
        if run.format == "psd":
            return rendered.composite
        return page_image(rendered.nodes, (rendered.width, rendered.height), color_mode, dpi, ps.bilevel)

    try:
        for sp, unit in units:
            if sp is None:
                plan = unit[0]
                dpi = run.dpi or plan.dpi
                rendered = _render(await content_of(plan), dpi)
                emit(as_output(rendered, plan.color_mode, dpi), rendered.nodes, _file_stem(ps.file_code, plan), dpi,
                     plan.color_mode, plan.page.id, {})
                continue
            left, right = unit
            if left.color_mode != right.color_mode:
                raise ExportRefused(f"見開き {sp.id} の2ページの色の種類が違う（{left.color_mode}・{right.color_mode}）")
            dpi = run.dpi or left.dpi
            if dpi != (run.dpi or right.dpi):
                raise ExportRefused(f"見開き {sp.id} の2ページの解像度が違う（{left.dpi}・{right.dpi}）")
            content = await _spread_content(session, sp, await content_of(left), await content_of(right))
            rendered = _render_spread(content, dpi)
            img = as_output(rendered, left.color_mode, dpi)
            first, second = sorted(unit, key=lambda p: p.index)
            if run.spread_output in ("joined", "both"):
                stem = f"{ps.file_code}_{first.episode.number:02d}_{first.index + 1:03d}-{second.index + 1:03d}"
                emit(img, rendered.nodes, stem, dpi, left.color_mode, None,
                     {"spread_id": sp.id, "page_ids": [first.page.id, second.page.id]})
            if run.spread_output in ("split", "both"):
                halves = dict(zip(("left", "right"), split_spread(img, spec, dpi), strict=False))
                for plan in (first, second):
                    emit(halves[plan.spread_half], None, _file_stem(ps.file_code, plan), dpi, plan.color_mode,
                         plan.page.id, {"spread_id": sp.id})
    except (RenderRefused, ColorModeError, TextRenderError) as e:
        raise ExportRefused(str(e)) from e
    if run.format == "pdf":
        name = f"{ps.file_code}.pdf"
        write_print_pdf(pdf_pages, spec, pdf_dpis, ps.bilevel.pdf_codec if ps.bilevel else None, folder / name,
                        tuple(run.paper_mm) if run.paper_mm else None)
        outputs.append({"page_id": None, "file": name, "bytes": (folder / name).stat().st_size})
    return outputs
