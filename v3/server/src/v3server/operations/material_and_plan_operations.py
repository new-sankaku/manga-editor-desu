"""企画（WorkPlan）と設定資料（MaterialEntry）を変える操作（V3細部の決めごと 10.4 の企画・設定資料）。

- 企画：あらすじ・読者・入れないもの・メモ。作品に1行で、無ければ足す
- 設定資料：人物・小物・背景。名前・特徴・服・絵と、人物ごとの生成の設定
- AIが企画から人物を抜き出したとき（処理 extract_characters）は、proposal_state=proposed の案として入る。
  人が採る（adopted）か採らない（rejected）を決める（DecideMaterialProposal）。案のまま描く工程には使わない
AIが人の手の印の付いた項目に当たったときは、断らずに判断待ちに置き、残りを当てる。
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from v3server.canonical_tables.harness_tables import EpisodeOutline
from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.canonical_tables.service_and_job_tables import Job
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.work_tree_tables import Episode
from v3server.llm_questions.structure_question import Outline
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


class CanonicalBackground(_Strict):
    """場所の正本の背景の絵と、その絵の向き（ネームのコマの view と同じ言葉）。向きが同じコマはこの絵から切り出す。"""

    image_id: str
    view: str = Field(min_length=1)


class SceneCamera(_Strict):
    position: tuple[float, float, float]
    yaw_degrees: float
    pitch_degrees: float
    fov_degrees: float = Field(gt=0, lt=180)


class Scene3D(_Strict):
    """場所を箱で組んだ3D（background_scene3d/box_scene_depth_render.py）。boxes は [x0, y0, z0, x1, y1, z1]、
    cameras は向き（ネームのコマの view と同じ言葉）ごとのカメラ。正本の絵と向きが違うコマはここから奥行き・線画を描く。"""

    boxes: list[tuple[float, float, float, float, float, float]] = Field(min_length=1)
    cameras: dict[str, SceneCamera]


class GenerationSettings(_Strict):
    """人物ごとの生成の設定。絵を作る依頼を組むときに使う（どう使うかは処理の手順が決める）。"""

    # 見た目の指示（生成の指示に入れる文）と、入れない指示
    prompt: str | None = None
    negative_prompt: str | None = None
    loras: list[LoraUse] = Field(default_factory=list)
    # 顔・姿を合わせる参照の絵
    reference_image_ids: list[str] = Field(default_factory=list)
    seed: int | None = None
    # 場所（kind=background）だけ：正本の背景の絵と、箱の3D
    canonical: CanonicalBackground | None = None
    scene3d: Scene3D | None = None


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
    if (values.get("generation") or {}).get("canonical"):
        ids.append(values["generation"]["canonical"]["image_id"])
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
            rc.change(plan, changes)
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
        rc.change(entry, changes)
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


class SetEpisodeOutline(OpBase):
    """1話の構成（S1 の正本）を書く。無ければ足す。outline の形は llm_questions/structure_question.py の Outline。
    AIが人の手の印の付いた構成に当たったら判断待ちに置く（人が書いた構成を黙って上書きしない）。"""

    type: Literal["set_episode_outline"] = "set_episode_outline"
    episode_id: str
    outline: dict[str, Any]

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, Episode, self.episode_id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        try:
            value = Outline.model_validate(self.outline).model_dump(mode="json")
        except ValidationError as e:
            raise Invalid(f"構成の形が合わない: {e.errors()[0]['loc']} {e.errors()[0]['msg']}") from e
        rc = RowChanges(ctx)
        row = (await ctx.session.execute(select(EpisodeOutline).where(
            EpisodeOutline.episode_id == self.episode_id))).scalar_one_or_none()
        if row is None:
            require_ai_may_change_fields(ctx.actor, ctx.work, "episode_outlines", {"outline"})
            rc.created(EpisodeOutline(id=new_id(), work_id=ctx.work.id, episode_id=self.episode_id, outline=value,
                                      made_by_kind=ctx.actor.kind, made_by_id=ctx.actor.id, removed=False,
                                      human_hand_fields=["outline"] if ctx.actor.kind == "human" else []))
        else:
            if row.removed:
                rc.set_plain(row, {"removed": False})
            rc.change(row, {"outline": value})
        return rc.inverse([], "構成を書いた取り消し")
