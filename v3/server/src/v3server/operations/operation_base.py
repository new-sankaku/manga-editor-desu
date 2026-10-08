"""操作の一覧。正本を変える手段はここにある操作だけ。

1つの操作が持つもの
- scope: 誰の権限で（relation・object）、どのロックに当たるか
- apply: 正本を変え、取り消すときに流す操作を返す（取り消せないものは None）

取り消しは、返した操作を同じ窓口に流すだけ。消さずに removed の印を切り替えるので、取り消しの取り消しもできる。
"""


from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.work_tree_tables import Work
from v3server.openfga_permissions import Tuple
from v3server.request_actor import Actor
from v3server.v3_error_types import NotFound


@dataclass
class Scope:
    relation: str
    object: str
    # (target_kind, target_id)。どれか1つでも他の者がロックしていれば止める
    lock_targets: list[tuple[str, str]] = field(default_factory=list)
    # ページ全体を変える操作は、そのページの中のコマ・個別のロックにも当たる
    page_tree: str | None = None


@dataclass
class ApplyContext:
    session: AsyncSession
    work: Work
    actor: Actor
    tuple_writes: list[Tuple] = field(default_factory=list)
    tuple_deletes: list[Tuple] = field(default_factory=list)
    # この操作で置いた判断待ち（AIの変更が人の手の所に当たった分）。積むのは human_hand_guard.py だけ
    held_changes: list[dict[str, Any]] = field(default_factory=list)


async def get_in_work(session: AsyncSession, model, obj_id: str, work_id: str):
    obj = await session.get(model, obj_id)
    if obj is None or obj.work_id != work_id:
        raise NotFound(f"{model.__tablename__}:{obj_id}")
    return obj


def work_obj(work_id: str) -> str:
    return f"work:{work_id}"


def page_obj(page_id: str) -> str:
    return f"page:{page_id}"


class OpBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # AIが出してよい操作か。出してよい操作も、中でAIの関与（ai_involvement.py）と人の手の印を確かめる。
    # 出してよくない操作（作品の設定・参加者・人の手の範囲など）をAIが出すと、窓口が止める
    ai_may_submit: ClassVar[bool] = False

    async def scope(self, session: AsyncSession, work: Work) -> Scope:
        raise NotImplementedError

    async def apply(self, ctx: ApplyContext) -> dict[str, Any] | None:
        raise NotImplementedError


def _changed(obj, changes: dict[str, Any]) -> dict[str, Any]:
    """changes を当て、元の値を返す。"""
    before = {k: getattr(obj, k) for k in changes}
    for k, v in changes.items():
        setattr(obj, k, v)
    return before
