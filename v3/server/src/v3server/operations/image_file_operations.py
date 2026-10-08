"""絵を登録する操作と、人の手の範囲（AIが描き直さない所）を決める操作。

生成した絵・人が描いた絵・外から持ち込んだ絵・前の版に人が手を入れた絵を、同じ操作で登録する。
ファイルの中身は先に入口（image_intake.py）で置き場へ置き、規制の判定を記録してから、ここで行を書く。
入口を通っていない絵と、入口で止めた絵は登録しない。
コマに使う絵を選ぶのは UpdatePanel の image_id（人が選ぶと人の手の印が付き、AIは変えられない）。
絵は消さないので、前の版は based_on_image_id でたどれる（版として残る）。"""

from typing import Any, Literal

from pydantic import Field
from sqlalchemy import select

from v3server.canonical_tables.image_file_tables import ImageFile, ImageIntakeScreening
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import ProtectedRegion
from v3server.canonical_tables.work_tree_tables import Page, Panel
from v3server.operations.ai_involvement import image_role_task, require_actor_may
from v3server.operations.operation_base import (
    OpBase,
    Scope,
    get_in_work,
    page_obj,
    work_obj,
)
from v3server.usage_terms_schema import UsageTerms
from v3server.v3_error_types import HumanHandProtected, Invalid

ImageRole = Literal["panel_art", "line_art", "solid_black", "tone", "color", "background", "human_hand", "page_manuscript",
                    "reference", "character_sheet", "effect", "text"]
ImageOrigin = Literal["generated", "human_drawn", "imported", "human_edited"]


async def intake_status(session, work_id: str, sha256: str) -> str | None:
    """入口での判定の状態。1度でも止めていれば blocked。入口を通っていなければ None。"""
    rows = (await session.execute(select(ImageIntakeScreening.status).where(
        ImageIntakeScreening.work_id == work_id, ImageIntakeScreening.sha256 == sha256))).scalars().all()
    if not rows:
        return None
    return "blocked" if "blocked" in rows else rows[-1]


async def register_image_scope(session, work_id: str, page_id: str | None,
                               panel_id: str | None) -> tuple[Scope, str | None]:
    """絵を登録できる権限の範囲と、絵が属するページ。アップロードの口は、ファイルを書く前にこれで確かめる。"""
    if panel_id is not None:
        panel = await get_in_work(session, Panel, panel_id, work_id)
        if page_id is not None and page_id != panel.page_id:
            raise Invalid("コマとページが合わない")
        page_id = panel.page_id
    if page_id is not None:
        await get_in_work(session, Page, page_id, work_id)
        return Scope("can_draw", page_obj(page_id)), page_id
    # ページに属さない絵（設定資料・参照）は作品を管理できる人だけ
    return Scope("can_manage", work_obj(work_id)), None


class RegisterImage(OpBase):
    type: Literal["register_image"] = "register_image"
    id: str = Field(default_factory=new_id)
    role: ImageRole
    origin: ImageOrigin
    page_id: str | None = None
    panel_id: str | None = None
    job_id: str | None = None
    based_on_image_id: str | None = None
    source_note: str | None = None
    usage_terms: UsageTerms | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    dpi: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    ai_may_submit = True

    async def scope(self, session, work):
        scope, self.page_id = await register_image_scope(session, work.id, self.page_id, self.panel_id)
        return scope

    async def apply(self, ctx):
        # 出どころを偽れない：AIが登録するのは生成した絵だけ。人は描いた絵・持ち込んだ絵・手を入れた絵
        if (ctx.actor.kind == "ai") != (self.origin == "generated"):
            raise Invalid(f"{ctx.actor.kind} は origin={self.origin} の絵を登録できない")
        if self.origin == "generated" and self.job_id is None:
            raise Invalid("生成した絵には依頼（job_id）が要る")
        if self.origin == "imported" and (not self.source_note or self.usage_terms is None):
            raise Invalid("持ち込んだ絵には元（source_note）と利用の条件（usage_terms）を書く")
        if self.origin == "human_edited" and self.based_on_image_id is None:
            raise Invalid("手を入れた絵には元の版（based_on_image_id）が要る")
        if self.based_on_image_id is not None:
            await get_in_work(ctx.session, ImageFile, self.based_on_image_id, ctx.work.id)
        # 生成した絵は候補（案）。コマに使うかは別に選ぶ
        require_actor_may(ctx.actor, ctx.work, image_role_task(self.role), "propose")
        status = await intake_status(ctx.session, ctx.work.id, self.sha256)
        if status is None:
            raise Invalid("入口（image_intake.py）を通っていない絵は登録できない")
        if status == "blocked":
            raise Invalid("入口の判定で止めた絵は登録できない")
        ctx.session.add(ImageFile(
            id=self.id, work_id=ctx.work.id, page_id=self.page_id, panel_id=self.panel_id, role=self.role,
            origin=self.origin, job_id=self.job_id, based_on_image_id=self.based_on_image_id,
            source_note=self.source_note,
            usage_terms=self.usage_terms.model_dump(mode="json") if self.usage_terms else None,
            registered_by_kind=ctx.actor.kind, registered_by_id=ctx.actor.id, sha256=self.sha256,
            media_type=self.media_type, width=self.width, height=self.height, dpi=self.dpi, details=self.details))
        # 絵は消さない（V3検証の一覧 4-15）。取り消しは無い
        return None


class AddProtectedRegion(OpBase):
    """人の手の範囲を決める。この絵と、同じ大きさのまま続く後の版を描き直すとき、AIはこの範囲を描き直さない。"""

    type: Literal["add_protected_region"] = "add_protected_region"
    id: str = Field(default_factory=new_id)
    image_id: str
    polygon_px: list[tuple[float, float]] = Field(min_length=3)
    note: str | None = None

    async def scope(self, session, work):
        img = await get_in_work(session, ImageFile, self.image_id, work.id)
        if img.page_id is None:
            return Scope("can_manage", work_obj(work.id))
        return Scope("can_draw", page_obj(img.page_id), [("page", img.page_id)])

    async def apply(self, ctx):
        img = await ctx.session.get(ImageFile, self.image_id)
        if any(not (0 <= x <= img.width and 0 <= y <= img.height) for x, y in self.polygon_px):
            raise Invalid(f"範囲が絵（{img.width}x{img.height}）の外に出ている")
        ctx.session.add(ProtectedRegion(id=self.id, work_id=ctx.work.id, image_id=img.id, page_id=img.page_id,
                                        polygon_px=[list(p) for p in self.polygon_px], note=self.note,
                                        created_by=ctx.actor.id, removed=False))
        return {"type": "set_protected_region_removed", "id": self.id, "removed": True}


class SetProtectedRegionRemoved(OpBase):
    """人の手の範囲を外す・戻す。人だけ（AIはこの操作を出せない）。"""

    type: Literal["set_protected_region_removed"] = "set_protected_region_removed"
    id: str
    removed: bool

    async def scope(self, session, work):
        region = await get_in_work(session, ProtectedRegion, self.id, work.id)
        if region.page_id is None:
            return Scope("can_manage", work_obj(work.id))
        return Scope("can_draw", page_obj(region.page_id), [("page", region.page_id)])

    async def apply(self, ctx):
        if ctx.actor.kind != "human":
            raise HumanHandProtected("人の手の範囲を変えられるのは人だけ")
        region = await ctx.session.get(ProtectedRegion, self.id)
        if region.removed == self.removed:
            raise Invalid("すでにその状態")
        region.removed = self.removed
        return {**self.model_dump(), "removed": not self.removed}
