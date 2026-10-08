"""人が直した PSD を戻す操作（V3細部の決めごと 10.3・10.4 の PSD）。人だけが出せる。1回で取り消せる。

http_routes/psd_import_routes.py が PSD を読み、書き出したときの層と結び付け（print_export/psd_import_matching.py）、
変わった層の絵を入口を通して置いてから、この操作を出す。ここでは正本の行を見て、どう当てるかを決める：

- 変わった層
  - コマの1枚の絵（[コマ id-image]）・線を持たない層：新しい版（human_edited、based_on は元の絵）にして層を替える。
    置き場は書き出したときの層の範囲。絵には調整（明るさなど）が焼き込まれているので、合成の仕方（blend）の外の調整は外す
  - 線を持つ人の手の層・コマ枠・コマの地・フキダシ・トーン・図形・紙：線や形の値には戻せないので判断待ち（psd_vector_changed）
  - 文字の層：文字の値は変えず、判断待ち（psd_text_pixels。打ち直す・絵（描き文字）として採る・捨てる）
  - 人が「動かさない」にした行：当てずに判断待ち（psd_unmatched_layer）
  - 言語ごとに書き出した PSD（書き出しの記録の language が作品の言語と違う）の文字の層：判断待ちの先を、その言語の訳文の行
    （text_item_translations）にする。打ち直す（retype）は訳文を変え、元の言語の文字は変えない。
    絵として採る（adopt_as_image）は選べない（コマの絵はどの言語の版にも出るので、1つの言語の直しを絵にできない）。
    層が無くなったときの remove_item は訳文を抜く。書き出した後に訳文が抜かれていたら、discard だけの判断待ちにする
- 新しい層：親のグループがコマなら、そのコマの人の手の層として一番上に置く。それ以外は判断待ち（psd_unmatched_layer）
- 無くなった層：判断待ち（psd_layer_missing）。書き出しで作った層（紙・グループ・コマの絵など）は抜く物が無いので keep だけ

判断待ちの絵は、人が描いた絵（human_drawn・human_hand）として登録しておく（選んだときに置く）。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr
from sqlalchemy import select

from v3server.canonical_tables.material_and_setting_tables import ExportRun
from v3server.canonical_tables.page_item_tables import PageItem
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import HeldAiChange, PanelLayer, TextItem
from v3server.canonical_tables.translation_review_import_tables import TextItemTranslation
from v3server.canonical_tables.work_tree_tables import Page, Panel
from v3server.operations.held_change_operations import CHOICES
from v3server.operations.image_file_operations import RegisterImage
from v3server.operations.operation_base import OpBase, Scope, get_in_work, page_obj
from v3server.operations.pen_stroke_operations import StoredResult
from v3server.operations.row_snapshot import RowChanges
from v3server.v3_error_types import Invalid

ID_RE = r"^[0-9a-f]{32}(-[a-z]+)?$"
# 印の後ろの「-xxx」ごとの、元の行の表
SUFFIX_TABLE = {"paper": "pages", "frame": "pages", "items": "pages", "hand": "pages", "balloons": "pages",
                "typeset": "pages", "sfx": "pages", "fill": "panels", "image": "panels", "balloon": "text_items"}
MODELS = {"pages": Page, "panels": Panel, "panel_layers": PanelLayer, "text_items": TextItem, "page_items": PageItem}


class PsdImportEntry(BaseModel):
    kind: Literal["changed", "new", "missing"]
    marker: str | None = Field(default=None, pattern=ID_RE)
    # 書き出したときの層の表（書き出しの記録の layers の table）
    table: str | None = None
    image: StoredResult | None = None
    box_mm: tuple[float, float, float, float] | None = None
    parent_marker: str | None = Field(default=None, pattern=ID_RE)
    layer_name: str | None = None


def split_marker(marker: str) -> tuple[str, str | None]:
    base, _, suffix = marker.partition("-")
    return base, suffix or None


class ApplyPsdImport(OpBase):
    type: Literal["apply_psd_import"] = "apply_psd_import"
    export_run_id: str
    page_id: str
    entries: list[PsdImportEntry]
    _language: str | None = PrivateAttr(default=None)

    async def scope(self, session, work):
        await get_in_work(session, Page, self.page_id, work.id)
        return Scope("can_draw", page_obj(self.page_id), [("page", self.page_id)], page_tree=self.page_id)

    async def apply(self, ctx):
        if ctx.actor.kind != "human":
            raise Invalid("PSD を戻すのは人だけ")
        run = await get_in_work(ctx.session, ExportRun, self.export_run_id, ctx.work.id)
        if run.format != "psd" or run.status != "done" or self.page_id not in run.page_ids:
            raise Invalid("このページを PSD に書き出し終えた記録ではない")
        rc = RowChanges(ctx)
        # 訳文に差し替えて書き出した PSD なら、その言語（文字の層は訳文へ当てる）
        own = (ctx.work.preferences or {}).get("language")
        self._language = run.language if run.language is not None and run.language != own else None
        for e in self.entries:
            if e.kind in ("changed", "new") and (e.image is None or e.box_mm is None):
                raise Invalid(f"{e.kind} の層には絵（image）と置き場（box_mm）が要る")
            if e.kind == "changed":
                await self._changed(ctx, rc, e)
            elif e.kind == "new":
                await self._new(ctx, rc, e)
            else:
                await self._missing(ctx, rc, e)
        return rc.inverse([self.page_id], "PSD の戻しの取り消し")

    async def _row(self, ctx, table: str, rid: str):
        obj = await ctx.session.get(MODELS[table], rid)
        if obj is None or obj.work_id != ctx.work.id:
            return None
        if table != "pages" and obj.page_id != self.page_id:
            raise Invalid(f"{table}:{rid} はこのページの物ではない")
        if table == "pages" and obj.id != self.page_id:
            raise Invalid(f"ページ {rid} は戻し先のページではない")
        return obj

    async def _register(self, ctx, e: PsdImportEntry, **kw) -> str:
        iid = new_id()
        await RegisterImage(id=iid, page_id=self.page_id, sha256=e.image.sha256, media_type=e.image.media_type,
                            width=e.image.width, height=e.image.height,
                            details={"made_by": "psd_import", "export_run_id": self.export_run_id,
                                     "layer_name": e.layer_name}, **kw).apply(ctx)
        return iid

    async def _hold(self, ctx, rc, kind: str, table: str, target_id: str, e: PsdImportEntry,
                    panel_id: str | None, synthetic: bool, reason: str) -> None:
        choices = list(CHOICES[kind])
        if table == "text_items" and self._language is not None and kind in ("psd_text_pixels", "psd_layer_missing"):
            # 言語の版の文字の層：判断待ちの先を訳文の行にする（元の言語の文字を変えない・抜かない）
            tr = await ctx.session.scalar(select(TextItemTranslation).where(
                TextItemTranslation.text_item_id == target_id, TextItemTranslation.language == self._language,
                TextItemTranslation.removed.is_(False)))
            if tr is None:
                choices = ["discard"] if kind == "psd_text_pixels" else ["keep"]
                reason = f"{reason}（{self._language} の訳文は書き出した後に抜かれた）"
            else:
                table, target_id = "text_item_translations", tr.id
                if kind == "psd_text_pixels":
                    choices = [c for c in choices if c != "adopt_as_image"]
        payload: dict[str, Any] = {"export_run_id": self.export_run_id, "marker": e.marker, "layer_name": e.layer_name,
                                   "panel_id": panel_id, "synthetic": synthetic, "reason": reason,
                                   "language": self._language}
        if e.image is not None:
            payload["image_id"] = await self._register(ctx, e, role="human_hand", origin="human_drawn")
            payload["box_mm"] = list(e.box_mm)
        row = HeldAiChange(id=new_id(), work_id=ctx.work.id, target_table=table, target_id=target_id,
                           page_id=self.page_id, field=kind, proposed_value=None, current_value=None, proposal_id=None,
                           status="open", kind=kind, choices=choices, payload=payload)
        ctx.session.add(row)
        # 取り消すと、置いた判断待ちは下げる
        rc.before.setdefault("held_ai_changes", {})[row.id] = {"status": "withdrawn"}

    async def _replace(self, ctx, rc, e: PsdImportEntry, obj, role: str, image_field: str, placement_field: str):
        old = getattr(obj, image_field)
        iid = await self._register(ctx, e, role=role, origin="human_edited", based_on_image_id=old,
                                   panel_id=obj.id if isinstance(obj, Panel) else obj.panel_id)
        placement = {"crop_px": [0, 0, e.image.width, e.image.height], "dest_box_mm": list(e.box_mm)}
        # 絵に調整が焼き込まれているので、合成の仕方のほかの調整は外す
        keep = [a for a in (obj.adjustments or []) if a["kind"] == "blend"]
        rc.change(obj, {image_field: iid, placement_field: placement, "adjustments": keep})

    async def _changed(self, ctx, rc, e: PsdImportEntry) -> None:
        if e.marker is None:
            raise Invalid("変わった層には印（marker）が要る")
        base, suffix = split_marker(e.marker)
        table = SUFFIX_TABLE.get(suffix) if suffix else e.table
        if table not in MODELS:
            raise Invalid(f"印 {e.marker} の表 {table} は戻せない")
        obj = await self._row(ctx, table, base)
        if obj is None or getattr(obj, "removed", False):
            await self._hold(ctx, rc, "psd_unmatched_layer", "pages", self.page_id, e, None, False,
                             "書き出した後に、元の物が抜かれた")
            return
        panel_id = obj.id if table == "panels" else getattr(obj, "panel_id", None)
        if getattr(obj, "fixed", False):
            await self._hold(ctx, rc, "psd_unmatched_layer", table, obj.id, e, panel_id, False,
                             "人が「動かさない」にしている物の層が変わった")
            return
        if table == "panels" and suffix == "image" and obj.image_id is not None:
            await self._replace(ctx, rc, e, obj, "panel_art", "image_id", "image_placement")
        elif table == "panel_layers" and suffix is None and obj.stroke_revision == 0 and obj.image_id is not None:
            await self._replace(ctx, rc, e, obj, obj.role, "image_id", "placement")
        elif table == "text_items" and suffix is None:
            await self._hold(ctx, rc, "psd_text_pixels", table, obj.id, e, panel_id, False, "文字の層の画素が変わった")
        else:
            await self._hold(ctx, rc, "psd_vector_changed", table, obj.id, e, panel_id, table == "pages",
                             "線や形の値から描いた層の画素が変わった")

    async def _new(self, ctx, rc, e: PsdImportEntry) -> None:
        panel = None
        if e.parent_marker is not None:
            base, suffix = split_marker(e.parent_marker)
            if suffix is None:
                panel = await ctx.session.get(Panel, base)
                if panel is not None and (panel.work_id != ctx.work.id or panel.page_id != self.page_id
                                          or panel.removed):
                    panel = None
        if panel is None or panel.fixed:
            await self._hold(ctx, rc, "psd_unmatched_layer", "pages", self.page_id, e,
                             panel.id if panel is not None else None, False,
                             "どのコマにも入っていない新しい層" if panel is None else "「動かさない」のコマに入った新しい層")
            return
        iid = await self._register(ctx, e, role="human_hand", origin="human_drawn", panel_id=panel.id)
        layers = [la for la in (await ctx.session.execute(
            PanelLayer.__table__.select().where(PanelLayer.panel_id == panel.id, PanelLayer.removed.is_(False)))).all()]
        top = max((la.stack_order for la in layers), default=-1) + 1
        rc.created(PanelLayer(id=new_id(), work_id=ctx.work.id, page_id=self.page_id, panel_id=panel.id,
                              role="human_hand", image_id=iid, stack_order=top, visible=True, opacity=1.0,
                              placement={"crop_px": [0, 0, e.image.width, e.image.height],
                                         "dest_box_mm": list(e.box_mm)},
                              adjustments=[], fixed=False, stroke_revision=0,
                              human_hand_fields=["image_id", "opacity", "placement", "role", "stack_order", "visible"],
                              removed=False))

    async def _missing(self, ctx, rc, e: PsdImportEntry) -> None:
        if e.marker is None:
            raise Invalid("無くなった層には印（marker）が要る")
        base, suffix = split_marker(e.marker)
        table = SUFFIX_TABLE.get(suffix) if suffix else e.table
        if table not in MODELS:
            raise Invalid(f"印 {e.marker} の表 {table} は戻せない")
        obj = await self._row(ctx, table, base)
        if obj is None or getattr(obj, "removed", False):
            return
        panel_id = obj.id if table == "panels" else getattr(obj, "panel_id", None)
        await self._hold(ctx, rc, "psd_layer_missing", table, obj.id, e, panel_id, suffix is not None,
                         "書き出した層が PSD に無い")
