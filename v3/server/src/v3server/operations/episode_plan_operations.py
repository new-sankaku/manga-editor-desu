"""話ごとの構成（あらすじ・メモ・出る人物と設定資料・話の生成の中身）と伏線の操作、前の話から引き継ぐ操作。

- 構成は作業 structure（ai_involvement.py）。人が書いた項目には人の手の印が付き、AIが当たると判断待ちに置く
- 前の話から引き継ぐ（V3細部の決めごと 15章）：出る人物・設定資料と、話の生成の中身だけを写す。あらすじ・メモ（構成）と
  ネームは写さない。設定資料そのもの（material_entries）とつなぎ先の使い分け（process_routes）は作品・サーバーに1つなので、
  話をまたいでそのまま使われる（写す物が無い）
- 話の生成の中身（generation_defaults）は置き場だけで、生成の依頼はまだ読まない（未接続）
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from v3server.canonical_tables.episode_plan_tables import EpisodePlan, Foreshadowing
from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.work_tree_tables import Episode, Volume
from v3server.operations.ai_involvement import require_actor_may, require_ai_may_change_fields
from v3server.operations.material_and_plan_operations import LoraUse
from v3server.operations.operation_base import OpBase, Scope, get_in_work, work_obj
from v3server.operations.row_snapshot import RowChanges
from v3server.v3_error_types import Invalid

PLAN_FIELDS = ("synopsis", "notes", "cast_entry_ids", "generation_defaults")
# 前の話から写す項目
CARRIED_FIELDS = ("cast_entry_ids", "generation_defaults")
FORESHADOWING_STATES = ("open", "paid_off", "dropped")


class EpisodeGeneration(BaseModel):
    """話の生成の中身。作品の設定と人物ごとの設定の間に入る（V3細部の決めごと 12章）。"""

    model_config = ConfigDict(extra="forbid")
    prompt: str | None = None
    negative_prompt: str | None = None
    loras: list[LoraUse] = Field(default_factory=list)
    reference_image_ids: list[str] = Field(default_factory=list)


async def _checked_plan_values(session, work_id: str, values: dict[str, Any]) -> dict[str, Any]:
    if "cast_entry_ids" in values:
        ids = values["cast_entry_ids"]
        if ids is None or len(set(ids)) != len(ids):
            raise Invalid("cast_entry_ids は重ならない id の並び（無くすときは []）")
        for i in ids:
            entry = await get_in_work(session, MaterialEntry, i, work_id)
            if entry.removed or entry.proposal_state != "adopted":
                raise Invalid(f"設定資料 {i} は抜かれているか、採っていない案")
    if "generation_defaults" in values:
        try:
            g = EpisodeGeneration.model_validate(values["generation_defaults"] or {})
        except ValueError as e:
            raise Invalid(f"話の生成の中身が正しくない: {e}") from e
        for i in g.reference_image_ids:
            await get_in_work(session, ImageFile, i, work_id)
        values["generation_defaults"] = g.model_dump(mode="json")
    return values


async def _plan_of(ctx, rc: RowChanges, episode_id: str, fields: set[str]) -> EpisodePlan:
    """話の構成の行。無ければ空の行を足す（取り消すと空に戻る。行は話に1つで、抜くことはない）。"""
    plan = (await ctx.session.execute(select(EpisodePlan).where(EpisodePlan.episode_id == episode_id))).scalar()
    if plan is not None:
        return plan
    require_ai_may_change_fields(ctx.actor, ctx.work, "episode_plans", fields)
    plan = EpisodePlan(id=new_id(), work_id=ctx.work.id, episode_id=episode_id, synopsis=None, notes=None,
                       cast_entry_ids=[], generation_defaults={}, carried_from_episode_id=None, human_hand_fields=[])
    ctx.session.add(plan)
    rc.before["episode_plans"] = {plan.id: {"synopsis": None, "notes": None, "cast_entry_ids": [],
                                            "generation_defaults": {}, "carried_from_episode_id": None,
                                            "human_hand_fields": []}}
    return plan


class SetEpisodePlan(OpBase):
    """話の構成を書く。書いた項目だけ変える。"""

    type: Literal["set_episode_plan"] = "set_episode_plan"
    episode_id: str
    synopsis: str | None = None
    notes: str | None = None
    cast_entry_ids: list[str] | None = None
    generation_defaults: dict[str, Any] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, Episode, self.episode_id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        changes = self.model_dump(include=set(PLAN_FIELDS), exclude_unset=True, mode="json")
        if not changes:
            raise Invalid("変える項目がない")
        changes = await _checked_plan_values(ctx.session, ctx.work.id, changes)
        rc = RowChanges(ctx)
        plan = await _plan_of(ctx, rc, self.episode_id, set(changes))
        rc.change(plan, changes)
        return rc.inverse([], "話の構成を変えた取り消し")


async def previous_episode(session, episode: Episode) -> Episode | None:
    """読む順（巻の番号・話の番号）で、抜いていない前の話。"""
    rows = (await session.execute(
        select(Episode, Volume.number).join(Volume, Volume.id == Episode.volume_id)
        .where(Episode.work_id == episode.work_id, Episode.removed.is_(False), Volume.removed.is_(False))
        .order_by(Volume.number, Episode.number))).all()
    order = [e for e, _ in rows]
    if episode not in order:
        return None
    i = order.index(episode)
    return order[i - 1] if i > 0 else None


class CarryOverEpisodePlan(OpBase):
    """前の話（from_episode_id。無ければ読む順で1つ前の話）から、出る人物・設定資料と話の生成の中身を写す。
    写した物は人が確かめて直す前提なので、写すのは人だけ（AIが出すと、前の話の人物を黙って当てることになる）。"""

    type: Literal["carry_over_episode_plan"] = "carry_over_episode_plan"
    episode_id: str
    from_episode_id: str | None = None

    async def scope(self, session, work):
        await get_in_work(session, Episode, self.episode_id, work.id)
        if self.from_episode_id is not None:
            await get_in_work(session, Episode, self.from_episode_id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        if ctx.actor.kind != "human":
            raise Invalid("前の話から引き継ぐのは人だけ")
        episode = await ctx.session.get(Episode, self.episode_id)
        source = (await ctx.session.get(Episode, self.from_episode_id) if self.from_episode_id
                  else await previous_episode(ctx.session, episode))
        if source is None:
            raise Invalid("引き継ぐ前の話が無い（最初の話か、前の話が抜かれている）")
        if source.id == episode.id:
            raise Invalid("同じ話からは引き継げない")
        src = (await ctx.session.execute(select(EpisodePlan).where(EpisodePlan.episode_id == source.id))).scalar()
        if src is None:
            raise Invalid("前の話に構成（出る人物・話の生成の中身）が無い")
        values = await _checked_plan_values(ctx.session, ctx.work.id, {
            # 前の話の後で抜いた・採らなかった設定資料は写さない
            "cast_entry_ids": [i for i in src.cast_entry_ids
                               if (e := await ctx.session.get(MaterialEntry, i)) is not None and not e.removed
                               and e.proposal_state == "adopted"],
            "generation_defaults": dict(src.generation_defaults)})
        rc = RowChanges(ctx)
        plan = await _plan_of(ctx, rc, episode.id, set(CARRIED_FIELDS))
        rc.change(plan, values)
        rc.set_plain(plan, {"carried_from_episode_id": source.id})
        return rc.inverse([], "前の話から引き継いだ取り消し")


class AddForeshadowing(OpBase):
    type: Literal["add_foreshadowing"] = "add_foreshadowing"
    id: str = Field(default_factory=new_id)
    planted_episode_id: str
    text: str = Field(min_length=1)
    payoff_episode_id: str | None = None
    notes: str | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        for eid in (self.planted_episode_id, self.payoff_episode_id):
            if eid is not None:
                await get_in_work(session, Episode, eid, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        require_actor_may(ctx.actor, ctx.work, "structure", "decide")
        values = self.model_dump(include={"planted_episode_id", "text", "payoff_episode_id", "notes"})
        rc = RowChanges(ctx)
        rc.created(Foreshadowing(id=self.id, work_id=ctx.work.id, state="paid_off" if self.payoff_episode_id else "open",
                                 removed=False, **values,
                                 human_hand_fields=sorted(k for k, v in values.items() if v is not None)
                                 if ctx.actor.kind == "human" else []))
        return rc.inverse([], "伏線を足した取り消し")


class UpdateForeshadowing(OpBase):
    type: Literal["update_foreshadowing"] = "update_foreshadowing"
    id: str
    text: str | None = Field(default=None, min_length=1)
    planted_episode_id: str | None = None
    payoff_episode_id: str | None = None
    state: Literal["open", "paid_off", "dropped"] | None = None
    notes: str | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, Foreshadowing, self.id, work.id)
        for eid in (self.planted_episode_id, self.payoff_episode_id):
            if eid is not None:
                await get_in_work(session, Episode, eid, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        row = await ctx.session.get(Foreshadowing, self.id)
        changes = self.model_dump(exclude={"type", "id"}, exclude_unset=True)
        if not changes:
            raise Invalid("変える項目がない")
        for k in ("text", "planted_episode_id", "state"):
            if k in changes and changes[k] is None:
                raise Invalid(f"{k} は空にできない")
        if row.removed:
            raise Invalid("抜いた伏線は set_removed で戻してから変える")
        rc = RowChanges(ctx)
        rc.change(row, changes)
        return rc.inverse([], "伏線を変えた取り消し")
