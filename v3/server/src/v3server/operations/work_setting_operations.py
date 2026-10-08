"""作品の設定・参加者・送ってよい先・閾値・指摘への反応を変える操作。"""


from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from v3server.canonical_tables.service_and_job_tables import Service, WorkDestination
from v3server.canonical_tables.threshold_and_finding_tables import (
    FindingReaction,
    Threshold,
)
from v3server.name_structure.item_styles import FrameStyle
from v3server.name_structure.print_settings import NombreSettings, PrintSettings, Typesetting
from v3server.name_structure.reading_direction import PageSpec
from v3server.openfga_permissions import WORK_ROLES, Tuple
from v3server.operations.ai_involvement import Mode, Task
from v3server.operations.operation_base import OpBase, Scope, _changed, work_obj
from v3server.v3_error_types import Invalid, NotFound


class WorkPreferences(BaseModel):
    """作品ごとの設定（V3細部の決めごと 10.4 の言語・自動保存・設定）。利用者ごとの設定は user_settings（操作の窓口の外）。"""

    model_config = ConfigDict(extra="forbid")

    # 作品の文字の言語（セリフ・書き出しの書体を選ぶ元。画面の言語は利用者ごと）
    language: str | None = None
    # 文字の種類ごとの書体（書き出しで、文字に書体が無いときに使う。ここにも無ければ書き出しは止まる）
    fonts_by_kind: dict[Literal["balloon", "caption", "drawn_sfx"], str] = Field(default_factory=dict)
    # コマ枠の線と塗りの標準（コマに frame_style が無いときの見た目。書き出しで、ここにも無ければ止まる）
    frame_style: FrameStyle | None = None
    # 作品の画面の下書きを残す間隔（秒）。無ければ利用者の設定に従う
    autosave_interval_seconds: int | None = Field(default=None, gt=0)
    # 入稿の設定（色の種類と解像度の既定・2階調の作り方・安全線・ページ数の決まり・ファイル名の略号）。書き出しに要る
    print: PrintSettings | None = None
    # ノンブル（位置・書体・始まりの番号・ページの種類ごとの出し方）。無ければノンブルを描かない（入稿前の確かめが紙の作品に印を出す）
    nombre: NombreSettings | None = None
    # 写植の組版の標準（文字に typesetting が無いときに使う。ここにも無ければ書き出しは止まる）
    typesetting: Typesetting | None = None


class SetWorkSettings(OpBase):
    type: Literal["set_work_settings"] = "set_work_settings"
    title: str | None = None
    reading_direction: Literal["rtl", "ltr"] | None = None
    text_direction: Literal["vertical", "horizontal"] | None = None
    medium: Literal["paper", "web_page", "vertical_scroll"] | None = None
    trim_size: str | None = None
    default_page_count: int | None = None
    # ページの寸法（name_structure の PageSpec）と、1ページ目を左に置くか
    page_spec: PageSpec | None = None
    first_page_is_left: bool | None = None
    preferences: WorkPreferences | None = None

    async def scope(self, session, work):
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        changes = self.model_dump(exclude={"type"}, exclude_unset=True)
        if not changes:
            raise Invalid("変える項目がない")
        before = _changed(ctx.work, changes)
        return {"type": self.type, **before}


class SetAiInvolvement(OpBase):
    """作業ごとのAIの関与を選ぶ（operations/ai_involvement.py）。mode を None にすると設計の既定に戻す。"""

    type: Literal["set_ai_involvement"] = "set_ai_involvement"
    task: Task
    mode: Mode | None

    async def scope(self, session, work):
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        current = dict(ctx.work.ai_involvement or {})
        before = current.get(self.task)
        if before == self.mode:
            raise Invalid("すでにその状態")
        if self.mode is None:
            current.pop(self.task)
        else:
            current[self.task] = self.mode
        ctx.work.ai_involvement = current
        return {"type": self.type, "task": self.task, "mode": before}


class SetMember(OpBase):
    """作品に人を招く・外す。役ごとに1件。"""

    type: Literal["set_member"] = "set_member"
    user: str
    role: str
    granted: bool

    async def scope(self, session, work):
        if self.role not in WORK_ROLES:
            raise Invalid(f"役が無い: {self.role}")
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        t = Tuple(f"user:{self.user}", self.role, work_obj(ctx.work.id))
        (ctx.tuple_writes if self.granted else ctx.tuple_deletes).append(t)
        return {**self.model_dump(), "granted": not self.granted}


class AllowDestination(OpBase):
    """作品の送ってよい先に API のつなぎ先を足す・外す。"""

    type: Literal["allow_destination"] = "allow_destination"
    service_id: str
    allowed: bool

    async def scope(self, session, work):
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        service = await ctx.session.get(Service, self.service_id)
        if service is None:
            raise NotFound(f"services:{self.service_id}")
        if service.location != "api":
            raise Invalid("手元のつなぎ先は常に送ってよい。足す・外すのはAPIだけ")
        row = await ctx.session.get(WorkDestination, (ctx.work.id, self.service_id))
        if self.allowed and row is None:
            ctx.session.add(WorkDestination(work_id=ctx.work.id, service_id=self.service_id))
        elif not self.allowed and row is not None:
            await ctx.session.delete(row)
        return {**self.model_dump(), "allowed": not self.allowed}


class SetThreshold(OpBase):
    """閾値を置く・変える・外す（value が None で外す）。"""

    type: Literal["set_threshold"] = "set_threshold"
    key: str
    value: dict[str, Any] | None
    source: str | None = None
    status: Literal["unverified", "verified", "rejected"] | None = None
    note: str | None = None

    async def scope(self, session, work):
        if self.value is not None and (self.source is None or self.status is None):
            raise Invalid("閾値には出典と検証の状態が要る")
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        row = (
            await ctx.session.execute(
                select(Threshold).where(Threshold.work_id == ctx.work.id, Threshold.key == self.key)
            )
        ).scalar_one_or_none()
        if row is None:
            inverse = {"type": self.type, "key": self.key, "value": None}
        else:
            inverse = {
                "type": self.type,
                "key": self.key,
                "value": row.value,
                "source": row.source,
                "status": row.status,
                "note": row.note,
            }
        if self.value is None:
            if row is not None:
                await ctx.session.delete(row)
        elif row is None:
            ctx.session.add(
                Threshold(
                    work_id=ctx.work.id,
                    key=self.key,
                    value=self.value,
                    source=self.source,
                    status=self.status,
                    note=self.note,
                )
            )
        else:
            row.value, row.source, row.status, row.note = self.value, self.source, self.status, self.note
        return inverse


class RecordFindingReaction(OpBase):
    """検査の指摘に人がどう反応したか。記録なので取り消さない（違えば反応を足し直す）。"""

    type: Literal["record_finding_reaction"] = "record_finding_reaction"
    finding_key: str
    target_kind: Literal["page", "panel", "item"]
    target_id: str
    reaction: Literal["fixed", "ignored", "disagreed"]
    note: str | None = None

    async def scope(self, session, work):
        return Scope("can_view", work_obj(work.id))

    async def apply(self, ctx):
        ctx.session.add(
            FindingReaction(
                work_id=ctx.work.id,
                finding_key=self.finding_key,
                target_kind=self.target_kind,
                target_id=self.target_id,
                reaction=self.reaction,
                actor_id=ctx.actor.id,
                note=self.note,
            )
        )
        return None


# ---------------------------------------------------------------- 巻・話・ページ
