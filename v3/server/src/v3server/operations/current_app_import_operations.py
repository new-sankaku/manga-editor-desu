"""今のアプリのプロジェクトを取り込む操作（V3点検の結果 5章の6・点検4 3章）。

口（http_routes/current_app_import_routes.py）がファイルを読み、絵を入口（image_intake.py）に通し、
行の案と報告（current_app_import/import_plan.py の ImportPlan）を作ってから、この操作を窓口に出す。

- 行は前からある操作（ページ・コマ・絵の登録・コマの絵・層・文字を足す操作）の apply をそのまま通す。
  値の確かめ・人の手の印・AIの関与は、1つずつ足したときと同じにかかる。人の操作なので、入れた項目には人の手の印が付く
- 絵の出どころは取り込む人が選ぶ（imported か human_drawn）。imported は利用の条件（usage_terms）が要る（RegisterImage が確かめる）
- 報告（current_app_import_reports）は、元の物を1つずつ、どこへ入れたか・入れられなかった理由と一緒に残す
- 1回で取り消せる（restore_rows で、作ったページ・コマ・層・文字・AIの設定に抜いた印を付ける）。絵と報告は消さない
"""

from typing import Literal

from pydantic import Field
from sqlalchemy import func, select

from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.translation_review_import_tables import (
    CurrentAppImportReport,
    ElementGenerationSetting,
)
from v3server.canonical_tables.work_tree_tables import Episode, Page
from v3server.current_app_import.import_plan import ImportPlan
from v3server.operations.image_file_operations import RegisterImage
from v3server.operations.operation_base import OpBase, Scope, get_in_work, work_obj
from v3server.operations.text_and_layer_operations import AddPanelLayer, AddTextItem
from v3server.operations.work_tree_operations import AddPage, AddPanel, UpdatePanel
from v3server.usage_terms_schema import UsageTerms
from v3server.v3_error_types import Invalid


class ImportCurrentAppProject(OpBase):
    type: Literal["import_current_app_project"] = "import_current_app_project"
    report_id: str = Field(default_factory=new_id)
    episode_id: str
    source_file_name: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_origin: Literal["imported", "human_drawn"]
    usage_terms: UsageTerms | None = None
    plan: ImportPlan

    async def scope(self, session, work):
        await get_in_work(session, Episode, self.episode_id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        if ctx.work.page_spec is None:
            raise Invalid("作品のページの寸法（page_spec）を先に決める。コマと文字の位置を mm に直すのに使う")
        if self.image_origin == "imported" and self.usage_terms is None and self.plan.images:
            raise Invalid("持ち込んだ絵（image_origin=imported）には利用の条件（usage_terms）が要る")
        session = ctx.session
        last = (await session.execute(select(func.max(Page.number)).where(Page.episode_id == self.episode_id))).scalar()
        first = (last or 0) + 1
        snapshot: dict[str, dict[str, dict]] = {}

        def created(table: str, row_id: str) -> None:
            snapshot.setdefault(table, {})[row_id] = {"removed": True}

        session.add(CurrentAppImportReport(
            id=self.report_id, work_id=ctx.work.id, episode_id=self.episode_id, source_file_name=self.source_file_name,
            source_sha256=self.source_sha256, image_origin=self.image_origin, created_by=ctx.actor.id,
            counts=self.plan.counts(), entries=[e.model_dump(mode="json") for e in self.plan.entries]))
        for n, page in enumerate(self.plan.pages):
            await AddPage(id=page.id, episode_id=self.episode_id, number=first + n).apply(ctx)
            created("pages", page.id)
        await session.flush()
        for panel in self.plan.panels:
            await AddPanel(id=panel.id, page_id=panel.page_id, order=panel.order, frame=panel.frame).apply(ctx)
            if panel.frame_style is not None:
                await UpdatePanel(id=panel.id, frame_style=panel.frame_style).apply(ctx)
            created("panels", panel.id)
        await session.flush()
        for img in self.plan.images:
            await RegisterImage(
                id=img.id, role=img.role, origin=self.image_origin, page_id=img.page_id, panel_id=img.panel_id,
                source_note=img.source_note, usage_terms=self.usage_terms, sha256=img.sha256,
                media_type=img.media_type, width=img.width, height=img.height, dpi=img.dpi,
                details={"current_app_image_key": img.key, "current_app_import_report_id": self.report_id},
            ).apply(ctx)
        await session.flush()
        for pi in self.plan.panel_images:
            await UpdatePanel(id=pi.panel_id, image_id=pi.image_id, image_placement=pi.placement).apply(ctx)
        for layer in self.plan.layers:
            await AddPanelLayer(id=layer.id, panel_id=layer.panel_id, role=layer.role, image_id=layer.image_id,
                                stack_order=layer.stack_order, visible=layer.visible, opacity=layer.opacity,
                                placement=layer.placement).apply(ctx)
            created("panel_layers", layer.id)
        for text in self.plan.texts:
            await AddTextItem(id=text.id, panel_id=text.panel_id, **text.values).apply(ctx)
            created("text_items", text.id)
        for s in self.plan.settings:
            session.add(ElementGenerationSetting(
                id=s.id, work_id=ctx.work.id, target_kind=s.target_kind, page_id=s.page_id, panel_id=s.panel_id,
                image_id=s.image_id, prompt=s.prompt, negative_prompt=s.negative_prompt, source_values=s.source_values,
                import_report_id=self.report_id, human_hand_fields=[], removed=False))
            created("element_generation_settings", s.id)
        return {"type": "restore_rows", "label": f"今のアプリのプロジェクト {self.source_file_name} の取り込み",
                "page_ids": sorted(p.id for p in self.plan.pages), "snapshot": snapshot}
