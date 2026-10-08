"""企画・設定資料と、利用者・作品の設定。

- WorkPlan：企画（あらすじ・読者・入れないもの）。作品に1行
- MaterialEntry：設定資料の1件（人物・小物・背景・その他）。名前・特徴・服・絵と、人物ごとの生成の設定。
  AIが抜き出した人物は proposal_state=proposed の案として入り、人が採る（adopted）か採らない（rejected）
- UserSetting：利用者ごとの設定（言語・自動保存など）。作品のデータではないので操作の窓口を通さない
- ExportRun：書き出しの依頼と結果
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id


class WorkPlan(Base):
    __tablename__ = "work_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    # 作品に1行
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), unique=True)
    synopsis: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str | None] = mapped_column(Text)
    # 入れないもの（描かない題材・表現）
    exclusions: Mapped[list[Any]] = mapped_column(default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)


class MaterialEntry(Base):
    __tablename__ = "material_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # character（人物）・prop（小物）・background（背景）・other（その他）
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(Text)
    traits: Mapped[str | None] = mapped_column(Text)
    # 服（[{"name": 名前, "description": 中身}, ...]）
    clothes: Mapped[list[Any]] = mapped_column(default=list)
    # 設定資料の絵（image_files の id。role=character_sheet か reference）
    image_ids: Mapped[list[Any]] = mapped_column(default=list)
    # 人物ごとの生成の設定（operations/material_and_plan_operations.py の GenerationSettings）
    generation: Mapped[dict[str, Any]] = mapped_column(default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    # adopted（使う）・proposed（AIの案。人が決めるまで使わない）・rejected（採らない）
    proposal_state: Mapped[str] = mapped_column(String(16))
    # 案を作った依頼（AIが抜き出したとき）
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class UserSetting(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # 画面の言語（今のアプリの言語の切り替えと同じ値）
    language: Mapped[str | None] = mapped_column(String(16))
    # 画面の下書きを自動で残すか（正本は操作ごとに入るので、残すのは画面の途中の状態だけ）
    autosave: Mapped[bool | None] = mapped_column(Boolean)
    autosave_interval_seconds: Mapped[int | None] = mapped_column(Integer)
    # そのほかの画面の設定（ショートカットキーの割り当てなど）
    other: Mapped[dict[str, Any]] = mapped_column(default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())


class ExportRun(Base):
    __tablename__ = "export_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    # png・pdf・psd
    format: Mapped[str] = mapped_column(String(8))
    page_ids: Mapped[list[Any]] = mapped_column()
    dpi: Mapped[int] = mapped_column(Integer)
    # 紙の大きさ（mm の [幅, 高さ]）。ページの絵はこの真ん中に置く。無ければ塗り足し込みのページの大きさ
    paper_mm: Mapped[list[Any] | None] = mapped_column()
    # queued・running・done・failed
    status: Mapped[str] = mapped_column(String(16), default="queued")
    detail: Mapped[str | None] = mapped_column(Text)
    # [{"page_id": .., "file": 書き出しのフォルダの中の名前, "bytes": ..}]。PSD は層の記録（layers・offset_px）も持つ
    outputs: Mapped[list[Any]] = mapped_column(default=list)
    workflow_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())
