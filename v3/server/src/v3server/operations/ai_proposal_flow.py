"""AIの案を出し、作業のAIの関与に従って先へ進める（V3ハーネス設計 4.2・5章）。AIのネームの案はここを通す。

- ai_auto（AIに任せる）：案を出し、そのままAIが採用する。人の手の所は書かずに判断待ちに置く（name_proposal_operations.py）
- ai_proposes（AIが案を出し人が選ぶ）：案を出して止まる。人が採用する（apply_name_proposal）か、使わない
- human_makes_ai_checks・no_ai：案を出せない（SubmitNameProposal が断る）
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.work_tree_tables import Work
from v3server.openfga_permissions import Authz
from v3server.operations import operation_submit_and_undo
from v3server.operations.ai_involvement import ai_may
from v3server.operations.name_proposal_operations import (
    ApplyNameProposal,
    SubmitNameProposal,
)
from v3server.request_actor import Actor


async def submit_ai_proposal(session: AsyncSession, authz: Authz, ai_actor: Actor, work_id: str,
                             op: SubmitNameProposal) -> dict[str, Any]:
    if ai_actor.kind != "ai" or op.made_by != "ai":
        raise ValueError("AIの案だけを流す")
    await operation_submit_and_undo.submit(session, authz, ai_actor, work_id, op)
    work = await session.get(Work, work_id)
    out: dict[str, Any] = {"proposal_id": op.id, "applied": False, "held_change_ids": []}
    if not ai_may(work, op.task, "decide"):
        return out
    event = await operation_submit_and_undo.submit(session, authz, ai_actor, work_id, ApplyNameProposal(id=op.id))
    out["applied"] = True
    out["apply_event_id"] = event.id
    out["held_change_ids"] = (event.inverse or {}).get("held_change_ids", [])
    return out
