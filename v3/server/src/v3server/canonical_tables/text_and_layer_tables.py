"""コマの中の文字（吹き出し・ナレーションの箱・描き文字）と、コマの絵の層と、人の手の範囲（AIが描き直さない所）。
どれも人が直接直せる。人が変えた項目には人の手の印が付き、AIは変えられない（operations/human_hand_guard.py）。"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, JsonType, new_id


class TextItem(Base):
    """文字1つ。ネームの形（name_structure）では、balloon と caption が NamePanel.balloons、drawn_sfx が NamePanel.sfx になる。"""

    __tablename__ = "text_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    panel_id: Mapped[str] = mapped_column(ForeignKey("panels.id"), index=True)
    # balloon（吹き出し）・caption（ナレーションの箱）・drawn_sfx（描き文字の擬音）
    item_kind: Mapped[str] = mapped_column(String(16))
    # コマの中の読む順（同じ item_kind の中で）
    order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    speaker: Mapped[str | None] = mapped_column(Text)
    # 台詞・叫び・心の声・ナレーション（name_structure の BalloonKind）。未定なら無い
    balloon_kind: Mapped[str | None] = mapped_column(String(16))
    # vertical（縦書き）・horizontal（横書き）。未定なら無い
    writing_direction: Mapped[str | None] = mapped_column(String(16))
    font_size_pt: Mapped[float | None] = mapped_column(Float)
    # 文字の箱（基本枠の座標・mm の [x0, y0, x1, y1]）。置く前は無い
    box_mm: Mapped[list[Any] | None] = mapped_column()
    # しっぽの先（基本枠の座標・mm の [x, y]）。しっぽが無い・決めていなければ無い
    tail_target_mm: Mapped[list[Any] | None] = mapped_column()
    joined_to_previous: Mapped[bool | None] = mapped_column(Boolean)
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class PanelLayer(Base):
    """コマの絵の層1枚（線画・ベタ・トーン・着彩・背景・文字など。V3細部の決めごと 10.3）。
    1枚の絵だけのコマは Panel.image_id を使い、層に分けたコマはここに並べる。"""

    __tablename__ = "panel_layers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    panel_id: Mapped[str] = mapped_column(ForeignKey("panels.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    image_id: Mapped[str | None] = mapped_column(ForeignKey("image_files.id"))
    # 重ねる順。小さいほど下
    stack_order: Mapped[int] = mapped_column(Integer)
    visible: Mapped[bool] = mapped_column(Boolean)
    # 0〜1
    opacity: Mapped[float] = mapped_column(Float)
    # 切り抜きと置き場（name_structure/image_placement.py の ImagePlacement）。決めていなければ無い
    placement: Mapped[dict[str, Any] | None] = mapped_column()
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class ProtectedRegion(Base):
    """人の手の範囲（V3細部の決めごと 10.2）。この絵（と、同じ大きさのまま続く後の版）をAIが描き直すときは、
    この範囲を描き直す範囲から外す（generation_queue/input_image_preparation.py がマスクにして必ず渡す）。
    人だけが足せる・外せる。"""

    __tablename__ = "protected_regions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    image_id: Mapped[str] = mapped_column(ForeignKey("image_files.id"), index=True)
    page_id: Mapped[str | None] = mapped_column(ForeignKey("pages.id"), index=True)
    # 絵の画素の座標の多角形 [[x, y], ...]
    polygon_px: Mapped[list[Any]] = mapped_column()
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(128))
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HeldAiChange(Base):
    """AIの案が人の手の印の付いた項目を変えようとしたときに、黙って捨てずに置いておく判断待ち（V3細部の決めごと 10.2）。
    人が「採る」と、その値が人の判断として入る（人の手の印が付く）。「採らない」と、そのまま残る。"""

    __tablename__ = "held_ai_changes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # 行：pages・panels・text_items・panel_layers と、その id
    target_table: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(32))
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    # 項目の名前。"removed" はAIが抜こうとした
    field: Mapped[str] = mapped_column(String(32))
    # 値は JSON（None も値として持つ）
    proposed_value: Mapped[Any] = mapped_column(JsonType, nullable=True)
    current_value: Mapped[Any] = mapped_column(JsonType, nullable=True)
    # どの案から出たか
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("name_proposals.id"))
    # open（判断待ち）・accepted（採った）・rejected（採らない）・withdrawn（案の採用を取り消した）
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
