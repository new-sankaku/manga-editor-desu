"""ネームの案。AIが作った案・人が別に作った案・取り込んだネームを、採用する前に置いておく所。
採用すると、ページとコマの行に書かれる（operations/name_proposal_operations.py）。案そのものは消さずに残す。"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id


class NameProposal(Base):
    __tablename__ = "name_proposals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    # 作り手：ai（AIが作った）・human（人が作った）・imported（外のネームを取り込んだ）
    made_by: Mapped[str] = mapped_column(String(16))
    submitted_by_kind: Mapped[str] = mapped_column(String(8))
    submitted_by_id: Mapped[str] = mapped_column(String(128))
    # AIが作ったときの依頼
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    # ネームの中身（name_structure の NameDraft のうち pages だけ）
    pages: Mapped[list[Any]] = mapped_column(default=list)
    note: Mapped[str | None] = mapped_column(Text)
    # open（未決）・applied（採用した）・discarded（使わない）
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
