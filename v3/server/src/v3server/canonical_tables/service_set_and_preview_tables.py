"""生成サービスの組と比べ、ページの下見の絵の控え。どれも作品の正本ではないので、操作の窓口を通さない。

- ServiceSet：管理者が作った組（処理ごとの送り先の並び）。画面が計算する組（安い・良い・手元・API）とは別に、名前を付けて残す。
  当てるのは POST /service-sets/{id}/apply（送り先が決まっている処理の、つなぎ先だけを替える）
- ServiceComparison：同じ指示を、いくつものつなぎ先へ1件ずつ送った記録。結果は依頼（jobs）が持つ
- PagePreview：確認の画面に出すページの下見の絵（小さく描いた1枚）。content_key はページの中身から作る鍵で、
  中身が変わると鍵が変わるので、古い絵は使われない（http_routes/page_assignment_and_preview_routes.py）
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id


class ServiceSet(Base):
    __tablename__ = "service_sets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(Text, unique=True)
    # {処理の名前: つなぎ先の id}
    routes: Mapped[dict[str, Any]] = mapped_column()
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())


class ServiceComparison(Base):
    __tablename__ = "service_comparisons"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    process: Mapped[str] = mapped_column(String(64))
    page_id: Mapped[str | None] = mapped_column(ForeignKey("pages.id"))
    request: Mapped[dict[str, Any]] = mapped_column()
    # [{"service_id": .., "job_id": ..}]（送った順）
    jobs: Mapped[list[Any]] = mapped_column()
    requested_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PagePreview(Base):
    __tablename__ = "page_previews"

    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), primary_key=True)
    # 長い辺の画素数
    size: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    content_key: Mapped[str] = mapped_column(String(64))
    # 絵の置き場の sha256（image_file_storage）
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())
