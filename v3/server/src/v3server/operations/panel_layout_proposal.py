"""コマ割りの計算（panel_layout）を今のネームにかけ、結果をAIの案（task=panel_layout）として出す。

- 人の手の印が frame に付いたコマと、確定印のコマは、その枠を固定して残りを割る（constrained_tier_layout.py）
- 計算はプログラムだが、AIの側として出す（人の手の印を付けず、人の手を上書きしないため。ai_involvement.py）
- 案の先は ai_proposal_flow.py：AIに任せる作品ならそのまま入り、そうでなければ人が選ぶまで案のまま
- コマの最小の大きさは閾値 panel_short_side_min_mm を使う。無ければ計算しない（決め打ちしない）
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.work_tree_tables import Work
from v3server.name_structure.name_draft_schema import PanelFrame
from v3server.openfga_permissions import Authz
from v3server.operations.ai_proposal_flow import submit_ai_proposal
from v3server.operations.name_draft_conversion import (
    episode_rows,
    name_draft_of_episode,
)
from v3server.operations.name_proposal_operations import SubmitNameProposal
from v3server.operations.panel_frame_operations import min_panel_mm
from v3server.panel_layout.constrained_tier_layout import constrained_layout_draft
from v3server.panel_layout.tier_ratio_layout import LayoutInputError
from v3server.request_actor import Actor
from v3server.v3_error_types import Invalid

PROGRAM_ID = "program:panel_layout"


async def propose_panel_layout(session: AsyncSession, authz: Authz, requester: Actor, work_id: str,
                               episode_id: str) -> dict[str, Any]:
    work = await session.get(Work, work_id)
    draft = await name_draft_of_episode(session, work, episode_id)
    _, panels_by_page = await episode_rows(session, episode_id)
    pinned: dict[int, PanelFrame] = {}
    for rows in panels_by_page.values():
        for r in rows:
            if r.frame and ("frame" in r.human_hand_fields or r.human_confirmed):
                pinned[r.order] = PanelFrame.model_validate(r.frame)
    try:
        laid, broken = constrained_layout_draft(draft, pinned, await min_panel_mm(session, work_id))
    except LayoutInputError as e:
        raise Invalid(f"コマ割りを計算できない: {e}") from e
    actor = Actor(kind="ai", id=PROGRAM_ID, on_behalf_of=requester.permission_user)
    op = SubmitNameProposal(episode_id=episode_id, made_by="ai", task="panel_layout", pages=laid.pages,
                            note=f"コマ割りの計算。固定した枠 {sorted(pinned)}")
    out = await submit_ai_proposal(session, authz, actor, work_id, op)
    out["pinned_panels"] = sorted(pinned)
    out["broken"] = [b.__dict__ for b in broken]
    return out
