"""書き出し（PNG・PDF・PSD）を1件行う。書き出しの依頼（ExportRun）は http_routes/export_routes.py が作り、
Temporal の書き出しの待ち行列（print_export/export_workflow.py）の作業者がここを呼ぶ。

- どの書き出しも、ページの絵は page_render.py の同じ層から作る（PNG・PDF は層を重ねた絵、PSD は層のまま）
- 紙の大きさ（paper_mm）を渡すと、ページ（塗り足し込み）を紙の真ん中に置く。紙がページより小さければ止める
- PSD は層ごとの画素を置き場に残し、出力の layers に書く（PSD を戻すとき、書き出したときの画素と比べる。psd_import_matching.py）
- ペンの線は、層の控えの絵（画面が描いた物）を使う。控えが古ければ止める。PSD でも線は画素の層になる
- 足りない値（書体・文字の大きさ・枠の線など）は補わずに止め、理由を ExportRun.detail に書く
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
from v3server.canonical_tables.work_tree_tables import Page, Panel, Work
from v3server.hand_tools.vector_strokes import refuse_stale_stroke_cache
from v3server.image_file_storage import read_image, store_image
from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.layered_psd_request import build_psd_request, psd_layers_from_nodes, write_layered_psd
from v3server.print_export.page_render import Node, PageContent, RenderedPage, RenderRefused, render_page
from v3server.print_export.print_pdf_export import canvas_size_mm, paper_size_px, write_print_pdf
from v3server.print_export.text_render import font_path, render_texts
from v3server.server_settings import get_settings

# 書き出しの画面に出す文（ペンの線は PSD では画素になる）
PSD_STROKE_NOTE = "ペンの線は、PSD では画素の層になります（線のデータはアプリに残ります。PSD から線には戻りません）"


class ExportRefused(ValueError):
    pass


async def load_page_content(session: AsyncSession, work: Work, page_id: str) -> PageContent:
    page = await session.get(Page, page_id)
    if page is None or page.work_id != work.id or page.removed:
        raise ExportRefused(f"ページ {page_id} が無い")
    if work.page_spec is None:
        raise ExportRefused("作品のページの寸法（page_spec）が決まっていない")

    async def rows(model):
        q = select(model).where(model.page_id == page_id, model.removed.is_(False))
        return list((await session.execute(q)).scalars())

    panels, layers, texts, items = await rows(Panel), await rows(PanelLayer), await rows(TextItem), await rows(PageItem)
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


def _render(content: PageContent, dpi: int) -> RenderedPage:
    s = get_settings()

    def texts(items):
        if not s.text_render_script:
            raise ExportRefused("V3_TEXT_RENDER_SCRIPT が無い。文字を描けない")
        return render_texts(items, s.node_executable, s.text_render_script)

    return render_page(content, dpi, lambda iid: read_image(content.images[iid]), texts,
                       lambda family: font_path(s.font_dir, family))


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


async def run_export(session: AsyncSession, run: ExportRun) -> list[dict[str, Any]]:
    s = get_settings()
    if not s.export_dir:
        raise ExportRefused("V3_EXPORT_DIR が無い。書き出したファイルを置く所が無い")
    work = await session.get(Work, run.work_id)
    folder = pathlib.Path(s.export_dir) / run.id
    folder.mkdir(parents=True, exist_ok=True)
    paper_px = paper_size_px(tuple(run.paper_mm), run.dpi) if run.paper_mm else None
    spec = PageSpec.model_validate(work.page_spec) if work.page_spec else None
    if spec and run.paper_mm:
        cw, ch = canvas_size_mm(spec)
        if run.paper_mm[0] < cw or run.paper_mm[1] < ch:
            raise ExportRefused(f"紙 {run.paper_mm}mm が塗り足し込みのページ {cw:.1f}x{ch:.1f}mm より小さい")
    outputs: list[dict[str, Any]] = []
    pdf_pages: list[Image.Image] = []
    for page_id in run.page_ids:
        content = await load_page_content(session, work, page_id)
        try:
            rendered = _render(content, run.dpi)
        except RenderRefused as e:
            raise ExportRefused(str(e)) from e
        flat, offset = _on_paper(rendered.composite, paper_px)
        if run.format == "png":
            name = f"{page_id}.png"
            flat.save(folder / name, dpi=(run.dpi, run.dpi))
            outputs.append({"page_id": page_id, "file": name, "bytes": (folder / name).stat().st_size})
        elif run.format == "pdf":
            pdf_pages.append(flat)
        elif run.format == "psd":
            if not s.psd_writer_script:
                raise ExportRefused("V3_PSD_WRITER_SCRIPT が無い。PSD を書けない")
            name = f"{page_id}.psd"
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = pathlib.Path(tmp)
                flat.save(tmpdir / "composite.png")
                layers = psd_layers_from_nodes(rendered.nodes, tmpdir, offset)
                req = build_psd_request(flat.width, flat.height, tmpdir / "composite.png", layers, folder / name)
                write_layered_psd(req, s.node_executable, pathlib.Path(s.psd_writer_script), 300)
            outputs.append({"page_id": page_id, "file": name, "bytes": (folder / name).stat().st_size,
                            "layers": _manifest(rendered.nodes, offset, []), "offset_px": list(offset),
                            "note": PSD_STROKE_NOTE})
        else:
            raise ExportRefused(f"知らない書き出しの形: {run.format}")
    if run.format == "pdf":
        name = "pages.pdf"
        write_print_pdf(pdf_pages, spec, run.dpi, "flate", folder / name,
                        tuple(run.paper_mm) if run.paper_mm else None)
        outputs.append({"page_id": None, "file": name, "bytes": (folder / name).stat().st_size})
    return outputs
