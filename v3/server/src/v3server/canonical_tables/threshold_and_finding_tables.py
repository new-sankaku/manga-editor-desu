"""閾値、指摘への人の反応、サーバーの内部の値。"""


from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id

# ---------------------------------------------------------------- 閾値と、指摘への人の反応


class Threshold(Base):
    """閾値は値・出典・検証の状態を持つデータ（V3ハーネス設計 7章）。作品ごとに持つ。"""

    __tablename__ = "thresholds"
    __table_args__ = (UniqueConstraint("work_id", "key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[dict[str, Any]] = mapped_column()
    source: Mapped[str] = mapped_column(Text)
    # unverified / verified / rejected
    status: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)


class FindingReaction(Base):
    """検査の指摘に人がどう反応したか。閾値の検証の材料（V3ハーネス設計 7章）。"""

    __tablename__ = "finding_reactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    finding_key: Mapped[str] = mapped_column(String(128))
    target_kind: Mapped[str] = mapped_column(String(8))
    target_id: Mapped[str] = mapped_column(String(64))
    # fixed=直した / ignored=見送った / disagreed=指摘が違う
    reaction: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- サーバーの内部の値


class SystemValue(Base):
    """OpenFGA のストアIDなど、サーバーが自分で作って覚えておく値。"""

    __tablename__ = "system_values"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
