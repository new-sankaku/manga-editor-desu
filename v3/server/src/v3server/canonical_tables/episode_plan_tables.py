"""話ごとの構成（工程の「構成」）と、前の話から引き継ぐもの。

- EpisodePlan：話ごとに1行。あらすじ・メモ（構成。引き継がない）と、出る人物・使う設定資料（cast_entry_ids）・
  話の生成の中身（generation_defaults。V3細部の決めごと 12章の「作品の設定」と「人物ごとの設定」の間に入る話の既定）。
  前の話から引き継いだときは、引き継いだ元の話（carried_from_episode_id）を残す（決めごと 15章）
- Foreshadowing：伏線。張った話と、回収する話（まだなら無い）。状態は open（張ったまま）・paid_off（回収した）・
  dropped（回収しないと決めた）
"""

from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id


class EpisodePlan(Base):
    __tablename__ = "episode_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # 話に1行
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), unique=True)
    synopsis: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    # この話に出る人物・使う設定資料（material_entries の id。並びは人が決めた順）
    cast_entry_ids: Mapped[list[Any]] = mapped_column(default=list)
    # 話の生成の中身（operations/episode_plan_operations.py の EpisodeGeneration）
    generation_defaults: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 前の話から引き継いだときの元の話
    carried_from_episode_id: Mapped[str | None] = mapped_column(ForeignKey("episodes.id"))
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)


class Foreshadowing(Base):
    __tablename__ = "foreshadowings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    planted_episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    payoff_episode_id: Mapped[str | None] = mapped_column(ForeignKey("episodes.id"))
    text: Mapped[str] = mapped_column(Text)
    # open・paid_off・dropped
    state: Mapped[str] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
