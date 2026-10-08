"""絵を登録する操作。生成した絵・人が描いた絵・外から持ち込んだ絵を、同じ操作で登録する。
ファイルの中身は先に置き場（image_file_storage.py）へ置き、ここでは行だけを書く。
コマに使う絵を選ぶのは UpdatePanel の image_id（人が選ぶと人の手の印が付き、AIは変えられない）。"""

from typing import Any, Literal

from pydantic import Field

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.work_tree_tables import Page, Panel
from v3server.operations.operation_base import (
    OpBase,
    Scope,
    get_in_work,
    page_obj,
    work_obj,
)
from v3server.v3_error_types import Invalid

ImageRole = Literal["panel_art", "line_art", "solid_black", "tone", "color", "background", "human_hand", "page_manuscript",
                    "reference", "character_sheet"]


class RegisterImage(OpBase):
    type: Literal["register_image"] = "register_image"
    id: str = Field(default_factory=new_id)
    role: ImageRole
    origin: Literal["generated", "human_drawn", "imported"]
    page_id: str | None = None
    panel_id: str | None = None
    job_id: str | None = None
    source_note: str | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    dpi: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    async def scope(self, session, work):
        if self.panel_id is not None:
            panel = await get_in_work(session, Panel, self.panel_id, work.id)
            if self.page_id is not None and self.page_id != panel.page_id:
                raise Invalid("コマとページが合わない")
            self.page_id = panel.page_id
        if self.page_id is not None:
            await get_in_work(session, Page, self.page_id, work.id)
            return Scope("can_draw", page_obj(self.page_id))
        # ページに属さない絵（設定資料・参照）は作品を管理できる人だけ
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        # 出どころを偽れない：AIが登録するのは生成した絵だけ。人は描いた絵と持ち込んだ絵
        if (ctx.actor.kind == "ai") != (self.origin == "generated"):
            raise Invalid(f"{ctx.actor.kind} は origin={self.origin} の絵を登録できない")
        if self.origin == "generated" and self.job_id is None:
            raise Invalid("生成した絵には依頼（job_id）が要る")
        if self.origin == "imported" and not self.source_note:
            raise Invalid("持ち込んだ絵には元（source_note）を書く")
        ctx.session.add(ImageFile(
            id=self.id, work_id=ctx.work.id, page_id=self.page_id, panel_id=self.panel_id, role=self.role,
            origin=self.origin, job_id=self.job_id, source_note=self.source_note,
            registered_by_kind=ctx.actor.kind, registered_by_id=ctx.actor.id, sha256=self.sha256,
            media_type=self.media_type, width=self.width, height=self.height, dpi=self.dpi, details=self.details))
        # 絵は消さない（V3検証の一覧 4-15）。取り消しは無い
        return None
