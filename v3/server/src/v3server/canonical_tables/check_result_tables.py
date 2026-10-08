"""検査の結果の記録。作品データではないので操作の窓口を通さず、回すたびに1行足す（呼び出しの記録と同じ扱い）。"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id


class NameCheckRun(Base):
    __tablename__ = "name_check_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    # 何を検査したか。案なら proposal_id、今のページとコマなら無い
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("name_proposals.id"))
    run_by_kind: Mapped[str] = mapped_column(String(8))
    run_by_id: Mapped[str] = mapped_column(String(128))
    # 使った閾値（鍵 → 値・出典・検証の状態）。後で閾値を変えても、この結果がどの値で出たかが分かる
    thresholds_used: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # name_checks の CheckReport
    report: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
