"""作品の階層（作品 ＞ 巻 ＞ 話 ＞ ページ ＞ コマ）。出来事の列から作った現在の姿。変えるのは操作の窓口だけ。"""


from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id

# ---------------------------------------------------------------- 作品の階層（作品 ＞ 巻 ＞ 話 ＞ ページ ＞ コマ）


class Work(Base):
    __tablename__ = "works"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(Text)
    # 読む向き（V3細部の決めごと 1章）: rtl=右から / ltr=左から
    reading_direction: Mapped[str] = mapped_column(String(8))
    # 文字の向き（同 2章）: vertical / horizontal
    text_direction: Mapped[str] = mapped_column(String(16))
    # 媒体（同 3章）: paper / web_page / vertical_scroll
    medium: Mapped[str] = mapped_column(String(32))
    trim_size: Mapped[str | None] = mapped_column(String(32))
    default_page_count: Mapped[int | None] = mapped_column(Integer)
    # 出来事の列の最後の番号。書き込みは作品ごとに1本（V3ハーネス設計 9.3）にするため、この行を FOR UPDATE で取る
    head_seq: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Volume(Base):
    __tablename__ = "volumes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    volume_id: Mapped[str] = mapped_column(ForeignKey("volumes.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    # 抜いたページは消さずに残す（V3細部の決めごと 15章）
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class Panel(Base):
    __tablename__ = "panels"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    # 読む順
    order: Mapped[int] = mapped_column(Integer)
    # 枠（形・大きさ・断ち切り）
    frame: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 役割（決めゴマ・めくり・ヒキ・つなぎ・場所を見せる）
    role: Mapped[str | None] = mapped_column(String(32))
    # 中身（場所・登場人物・セリフ・擬音など）。形は工程を作るときに決める
    content: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 人の確定印（V3ハーネス設計 9.2）
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
