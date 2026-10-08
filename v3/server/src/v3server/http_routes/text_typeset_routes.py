"""文字1つを書き出しと同じ組み方で組み、行の切れ目と字の置き場を返す口（原稿の画面が使える）。

- POST /works/{id}/text-items/{text_id}/typeset  本体 {"dpi": 数}
  組むのは v3/psd_writer/text_layout.js（書き出し・入稿前の確かめと同じ。print_export/text_render.py の layout_texts）。
  文字の大きさ・書体・組版・色が決まっていない文字は、書き出しと同じ理由で止める（補わない）。
  返す座標は画素（dpi で組んだ値。文字のブロックの左上が原点）と、箱の左上を原点にしたミリ。
  縦書きの字の x は列の真ん中・y は字の上端、横書きの字の x は字の左端・y は基準線。hanging はぶら下げた句読点（箱の外に出る）
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from v3server.canonical_tables.text_and_layer_tables import TextItem
from v3server.canonical_tables.work_tree_tables import Work
from v3server.http_routes.http_dependencies import ActorDep, AuthzDep, SessionDep, require
from v3server.operations.operation_base import get_in_work, work_obj
from v3server.print_export.page_render import MM_PER_INCH, RenderRefused, text_job
from v3server.print_export.text_render import TextRenderError, font_path, layout_texts
from v3server.server_settings import get_settings
from v3server.v3_error_types import Invalid

router = APIRouter()


class TypesetBody(BaseModel):
    # 組む解像度（画素の値はこの解像度。ミリの値は解像度によらない）
    dpi: float = Field(gt=0, le=2400)


@router.post("/works/{work_id}/text-items/{text_id}/typeset")
async def typeset_text(work_id: str, text_id: str, body: TypesetBody, session: SessionDep, authz: AuthzDep,
                       actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    t = await get_in_work(session, TextItem, text_id, work_id)
    if t.box_mm is None:
        raise Invalid(f"文字 {text_id} の箱（box_mm）が決まっていない")
    work = await session.get(Work, work_id)
    s = get_settings()
    if not s.text_render_script:
        raise Invalid("V3_TEXT_RENDER_SCRIPT が無い。文字を組めない")
    try:
        job = text_job(t, work.preferences, work.text_direction, body.dpi, lambda f: font_path(s.font_dir, f))
        (out,) = layout_texts([job], s.node_executable, s.text_render_script)
    except (RenderRefused, TextRenderError) as e:
        raise Invalid(str(e)) from e
    mm = MM_PER_INCH / body.dpi
    lay = out["layout"]
    ox, oy = lay["block_origin"]

    def to_mm(x: float, y: float) -> list[float]:
        return [round((ox + x) * mm, 3), round((oy + y) * mm, 3)]

    return {
        "text_id": t.id, "dpi": body.dpi, "vertical": job["vertical"], "overflow": out["overflow"],
        "missing_chars": out["missing_chars"], "block_px": [out["block_w"], out["block_h"]], "layout_px": lay,
        "lines": [{"start": ln["start"], "end": ln["end"]} for ln in lay["lines"]],
        "glyphs_mm": [{"start": g["start"], "end": g["end"], "text": g["text"], "kind": g["kind"], "line": g["line"],
                       "at": to_mm(g["x"], g["y"]), "advance": round(g["advance"] * mm, 3),
                       "size": round(g["size"] * mm, 3), "hanging": g["hanging"]} for g in lay["glyphs"]],
        "ruby_mm": [{"ruby": r["ruby"], "text": r["text"], "at": to_mm(r["x"], r["y"]),
                     "size": round(r["size"] * mm, 3)} for r in lay["ruby"]],
    }
