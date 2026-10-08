"""企画（WorkPlan）と設定資料（MaterialEntry）を変える操作（V3細部の決めごと 10.4 の企画・設定資料）。

- 企画：あらすじ・読者・入れないもの・メモ。作品に1行で、無ければ足す
- 設定資料：人物・小物・背景。名前・特徴・服・絵と、人物ごとの生成の設定
- AIが企画から人物を抜き出したとき（処理 extract_characters）は、proposal_state=proposed の案として入る。
  人が採る（adopted）か採らない（rejected）を決める（DecideMaterialProposal）。案のまま描く工程には使わない
AIが人の手の印の付いた項目に当たったときは、断らずに判断待ちに置き、残りを当てる。
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.canonical_tables.service_and_job_tables import Job
from v3server.canonical_tables.table_base import new_id
from v3server.operations.ai_involvement import require_actor_may, require_ai_may_change_fields
from v3server.operations.operation_base import OpBase, Scope, get_in_work, work_obj
from v3server.operations.row_snapshot import RowChanges
from v3server.v3_error_types import HumanHandProtected, Invalid

MaterialKind = Literal["character", "prop", "background", "other"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Clothes(_Strict):
    name: str
    description: str | None = None
    image_ids: list[str] = Field(default_factory=list)


class LoraUse(_Strict):
    name: str
    weight: float


class GenerationSettings(_Strict):
    """人物ごとの生成の設定。絵を作る依頼を組むときに使う（どう使うかは処理の手順が決める）。"""

    # 見た目の指示（生成の指示に入れる文）と、入れない指示
    prompt: str | None = None
    negative_prompt: str | None = None
    loras: list[LoraUse] = Field(default_factory=list)
    # 顔・姿を合わせる参照の絵
    reference_image_ids: list[str] = Field(default_factory=list)
    seed: int | None = None


class MaterialValues(_Strict):
    kind: MaterialKind
    name: str = Field(min_length=1)
    traits: str | None = None
    clothes: list[Clothes] = Field(default_factory=list)
    image_ids: list[str] = Field(default_factory=list)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    notes: str | None = None


async def _check_images(session, work_id: str, values: dict[str, Any]) -> None:
    ids = list(values.get("image_ids", []))
    ids += values.get("generation", {}).get("reference_image_ids", [])
    for c in values.get("clothes", []):
        ids += c.get("image_ids", [])
    for i in ids:
        await get_in_work(session, ImageFile, i, work_id)


def _checked(values: dict[str, Any]) -> dict[str, Any]:
    try:
        return MaterialValues.model_validate(values).model_dump(mode="json")
    except ValueError as e:
        raise Invalid(f"設定資料の値が正しくない: {e}") from e


class SetWorkPlan(OpBase):
    """企画を書く。書いた項目だけ変える。"""

    type: Literal["set_work_plan"] = "set_work_plan"
    synopsis: str | None = None
    audience: str | None = None
    exclusions: list[str] | None = None
    notes: str | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        changes = self.model_dump(exclude={"type"}, exclude_unset=True, mode="json")
        if not changes:
            raise Invalid("変える項目がない")
        if changes.get("exclusions", []) is None:
            raise Invalid("exclusions は空にできない（無くすときは []）")
        rc = RowChanges(ctx)
        plan = (await ctx.session.execute(select(WorkPlan).where(WorkPlan.work_id == ctx.work.id))).scalar_one_or_none()
        if plan is None:
            require_ai_may_change_fields(ctx.actor, ctx.work, "work_plans", set(changes))
            plan = WorkPlan(id=new_id(), work_id=ctx.work.id, exclusions=[],
                            human_hand_fields=sorted(changes) if ctx.actor.kind == "human" else [])
            for k, v in changes.items():
                setattr(plan, k, v)
            # 足した行の取り消しは「中身を空に戻す」（企画は作品に1行で、抜くことはない）
            ctx.session.add(plan)
            rc.before["work_plans"] = {plan.id: {"synopsis": None, "audience": None, "exclusions": [], "notes": None,
                                                 "human_hand_fields": []}}
        else:
            rc.change_or_hold(plan, changes, None)
        return rc.inverse([], "企画を変えた取り消し")


class AddMaterialEntry(OpBase):
    """設定資料を1件足す。人が足すと使う（adopted）、AIが足すと案（proposed）。"""

    type: Literal["add_material_entry"] = "add_material_entry"
    id: str = Field(default_factory=new_id)
    kind: MaterialKind
    name: str
    traits: str | None = None
    clothes: list[dict[str, Any]] = Field(default_factory=list)
    image_ids: list[str] = Field(default_factory=list)
    generation: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    # AIが抜き出したときの依頼
    job_id: str | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        values = _checked(self.model_dump(include=set(MaterialValues.model_fields)))
        await _check_images(ctx.session, ctx.work.id, values)
        if self.job_id is not None:
            await get_in_work(ctx.session, Job, self.job_id, ctx.work.id)
        is_ai = ctx.actor.kind == "ai"
        if is_ai:
            require_actor_may(ctx.actor, ctx.work, "settings_material", "propose")
        rc = RowChanges(ctx)
        rc.created(MaterialEntry(id=self.id, work_id=ctx.work.id, proposal_state="proposed" if is_ai else "adopted",
                                 job_id=self.job_id, removed=False,
                                 human_hand_fields=[] if is_ai else sorted(values), **values))
        return rc.inverse([], "設定資料を足した取り消し")


class UpdateMaterialEntry(OpBase):
    type: Literal["update_material_entry"] = "update_material_entry"
    id: str
    kind: MaterialKind | None = None
    name: str | None = None
    traits: str | None = None
    clothes: list[dict[str, Any]] | None = None
    image_ids: list[str] | None = None
    generation: dict[str, Any] | None = None
    notes: str | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, MaterialEntry, self.id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        entry = await ctx.session.get(MaterialEntry, self.id)
        changes = self.model_dump(exclude={"type", "id"}, exclude_unset=True, mode="json")
        if not changes:
            raise Invalid("変える項目がない")
        merged = {k: getattr(entry, k) for k in MaterialValues.model_fields} | changes
        checked = _checked(merged)
        changes = {k: checked[k] for k in changes}
        await _check_images(ctx.session, ctx.work.id, changes)
        rc = RowChanges(ctx)
        rc.change_or_hold(entry, changes, None)
        return rc.inverse([], "設定資料を変えた取り消し")


class DecideMaterialProposal(OpBase):
    """AIが足した設定資料の案を、人が採る・採らない。人だけ。"""

    type: Literal["decide_material_proposal"] = "decide_material_proposal"
    id: str
    state: Literal["adopted", "rejected", "proposed"]

    async def scope(self, session, work):
        await get_in_work(session, MaterialEntry, self.id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        if ctx.actor.kind != "human":
            raise HumanHandProtected("案を採るのは人だけ")
        entry = await ctx.session.get(MaterialEntry, self.id)
        if entry.proposal_state == self.state:
            raise Invalid("すでにその状態")
        before = entry.proposal_state
        entry.proposal_state = self.state
        return {**self.model_dump(), "state": before}
