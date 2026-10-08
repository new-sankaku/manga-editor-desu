"""出来事の列とロック。"""


from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id

# ---------------------------------------------------------------- 出来事の列


class Event(Base):
    """追記のみ。消さない、書き換えない（取り消しも新しい出来事として足す）。"""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("work_id", "seq"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    seq: Mapped[int] = mapped_column(BigInteger)
    # human / ai / system
    actor_kind: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[str] = mapped_column(String(128))
    # AIの作業を頼んだ人。AIはこの人の権限の範囲でしか操作できない
    on_behalf_of: Mapped[str | None] = mapped_column(String(128))
    op_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column()
    # 取り消すときに流す操作。取り消せない出来事（ロックなど）は空
    inverse: Mapped[dict[str, Any] | None] = mapped_column()
    # この操作で置いた判断待ち（AIの変更が人の手の所に当たった分。id・表・行・項目）。無ければ空
    held_changes: Mapped[list[Any] | None] = mapped_column()
    # この操作で変えた行と項目（前の値と後の値）。取り消しが後の変更を上書きしないかを見る（operations/field_change_record.py）。
    # この仕組みより前の出来事は空
    field_changes: Mapped[dict[str, Any] | None] = mapped_column()
    # この出来事が取り消した出来事
    undoes_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UndoConflict(Base):
    """取り消しが、後の出来事の変更を上書きするので止めた記録（operations/field_change_record.py）。
    取り消しは当てず、後の変更をそのまま残す。どちらの値も消さない（取り消す前の値は、取り消そうとした出来事の field_changes にある）。"""

    __tablename__ = "undo_conflicts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # 取り消そうとした出来事
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    actor_kind: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[str] = mapped_column(String(128))
    # [{"table", "id", "field", "undone_after", "current", "events": [後で変えた出来事]}]
    conflicts: Mapped[list[Any]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- ロック


class Lock(Base):
    """ページ・コマ・個別の3段（V3ハーネス設計 4.3）。"""

    __tablename__ = "locks"
    __table_args__ = (UniqueConstraint("target_kind", "target_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # page / panel / item
    target_kind: Mapped[str] = mapped_column(String(8))
    target_id: Mapped[str] = mapped_column(String(64))
    # 対象が入っているページ。ページのロックとコマ・個別のロックがぶつかるかを見るため
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    holder_kind: Mapped[str] = mapped_column(String(8))
    holder_id: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text)
    # AIのロックなら、その作業。人が取り返したらこの作業を取り消す
    job_id: Mapped[str | None] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
