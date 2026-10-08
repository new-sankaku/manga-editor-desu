"""原稿の上に人やAIが置く物（V3細部の決めごと 10.1・10.4）。

- PageItem：トーン・集中線・スピード線（item_kind=tone）と、図形・絵記号（item_kind=shape）
- AnnotationItem：赤入れ（ページかコマの範囲に付ける指摘。人もAIも付ける。開いている・済んだ、の状態を持つ）
- PenStroke：ペンの線（人の手の層ごと。点・筆圧・時刻・筆・太さ・色・種・描いた機器）。線が正本で、層の絵は線から作った控え
- PanelTemplate：コマの型（作品ごとに人が保存した枠の並び）

どれも人が直せる。人が変えた項目には人の手の印が付き、AIの変更が当たると判断待ちになる（operations/human_hand_guard.py）。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, event, func
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id


class PageItem(Base):
    __tablename__ = "page_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    # どのコマの物か。ページに直接置いた物（コマをまたぐ図形など）は無い
    panel_id: Mapped[str | None] = mapped_column(ForeignKey("panels.id"), index=True)
    # tone（トーン・集中線・スピード線）・shape（図形・絵記号）
    item_kind: Mapped[str] = mapped_column(String(16))
    # 中身（name_structure/item_styles.py の ToneSpec か ShapeSpec）
    spec: Mapped[dict[str, Any]] = mapped_column()
    # 置き場（基本枠の座標・mm の [x0, y0, x1, y1]）。トーンで貼る所がコマ・多角形のときは、その外接の箱
    box_mm: Mapped[list[Any]] = mapped_column()
    # 回転・傾き・反転（name_structure/item_transform.py の ItemTransform）
    transform: Mapped[dict[str, Any]] = mapped_column(default=dict)
    stack_order: Mapped[int] = mapped_column(Integer)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    opacity: Mapped[float] = mapped_column(Float, default=1.0)
    # 仕上げ（item_styles.py の Adjustment の並び）
    adjustments: Mapped[list[Any]] = mapped_column(default=list)
    # 人が掛けた「動かさない」。人もAIも変えられない。外せるのは人だけ
    fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class AnnotationItem(Base):
    """赤入れ。V3ハーネス設計 9.4。ここから AIへの指示（依頼）を作れる（http_routes/annotation_routes.py）。"""

    __tablename__ = "annotation_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    panel_id: Mapped[str | None] = mapped_column(ForeignKey("panels.id"), index=True)
    # 範囲（基本枠の座標・mm の多角形）。無ければコマ全体（コマも無ければページ全体）
    region_mm: Mapped[list[Any] | None] = mapped_column()
    body: Mapped[str] = mapped_column(Text)
    # 何の作業についての指摘か（operations/ai_involvement.py の TASKS）。AIが付けるときは、その作業の検査（check）の関与で決める
    about_task: Mapped[str] = mapped_column(String(32))
    author_kind: Mapped[str] = mapped_column(String(8))
    author_id: Mapped[str] = mapped_column(String(128))
    # open（開いている）・resolved（済んだ）
    status: Mapped[str] = mapped_column(String(16), default="open")
    # この赤入れから作った依頼
    job_ids: Mapped[list[Any]] = mapped_column(default=list)
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PenStroke(Base):
    """ペンの線1本（V3細部の決めごと 10.1 のペン・消しゴム）。線そのものが正本で、絵は線から作った控え（層の image_id）。

    今のアプリ（fabric.js の筆。js/sidebar/pen/pen-tools.js）と同じく、1本ずつ選んで動かす・消す・太さや色や筆を変えられる。
    点は基本枠の mm で持つ（控えの絵をどの解像度でも作り直せる）。乱れのある筆（クレヨン・スプレーなど）は seed で同じ絵に戻す。
    """

    __tablename__ = "pen_strokes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    panel_id: Mapped[str] = mapped_column(ForeignKey("panels.id"), index=True)
    # 描いた層（人の手の層）
    layer_id: Mapped[str] = mapped_column(ForeignKey("panel_layers.id"), index=True)
    # 筆（hand_tools/vector_strokes.py の Brush）
    brush: Mapped[str] = mapped_column(String(24))
    # [[x_mm, y_mm, 筆圧 0〜1（機器が返さなければ null）, 描き始めからの ms], ...]（描いた順）
    points: Mapped[list[Any]] = mapped_column()
    width_mm: Mapped[float] = mapped_column(Float)
    color: Mapped[str | None] = mapped_column(String(7))
    opacity: Mapped[float] = mapped_column(Float, default=1.0)
    # 乱れのある筆を同じ絵に描き直すための種
    seed: Mapped[int | None] = mapped_column(Integer)
    # 筆ごとの値（モザイクの大きさ・模様の間隔など。今のアプリの筆の設定）
    brush_options: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 描いた機器（pen・mouse・touch。PointerEvent.pointerType）。記録の無い線は null
    pointer_type: Mapped[str | None] = mapped_column(String(8))
    # 外接の箱（点に太さの半分を足した mm）。点と太さから下の _keep_box が決める（手で入れない）。
    # 消しゴムが通り道の近くの線だけを読むための索引（GiST。migrations 0010）に使う
    box_x0_mm: Mapped[float] = mapped_column(Float)
    box_y0_mm: Mapped[float] = mapped_column(Float)
    box_x1_mm: Mapped[float] = mapped_column(Float)
    box_y1_mm: Mapped[float] = mapped_column(Float)
    # 層の中で重ねる順（小さいほど下）
    stack_order: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(128))
    fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


@event.listens_for(PenStroke, "before_insert")
@event.listens_for(PenStroke, "before_update")
def _keep_box(_mapper, _connection, stroke: PenStroke) -> None:
    """点か太さが変わるたびに外接の箱を決め直す。足す・変える・線の消しゴム・取り消し（row_snapshot.py）のどれを通っても、
    ここ1か所で合わせる。"""
    from v3server.hand_tools.vector_strokes import stroke_box

    stroke.box_x0_mm, stroke.box_y0_mm, stroke.box_x1_mm, stroke.box_y1_mm = stroke_box(stroke.points, stroke.width_mm)


def _pen_stroke_box():
    return func.box(func.point(PenStroke.box_x0_mm, PenStroke.box_y0_mm), func.point(PenStroke.box_x1_mm, PenStroke.box_y1_mm))


# 索引は移行 0010 で作った。alembic check がモデルと突き合わせるので、ここにも同じものを書く
Index("ix_pen_strokes_box", _pen_stroke_box(), postgresql_using="gist")
Index("ix_pen_strokes_layer_order", PenStroke.layer_id, PenStroke.stack_order)


def pen_stroke_box_overlaps(x0: float, y0: float, x1: float, y1: float):
    """外接の箱が (x0, y0)-(x1, y1) に重なる線の条件。索引（migrations 0010）と同じ式で書く。"""
    return _pen_stroke_box().op("&&")(func.box(func.point(x0, y0), func.point(x1, y1)))


class PanelTemplate(Base):
    """コマの型。枠の多角形を基本枠に対する比（0〜1）で持つので、判型が違っても使える。"""

    __tablename__ = "panel_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    # [{"polygon": [[x比, y比], ...], "bleeds": bool, "frame_style": {...}|null}, ...]（読む順）
    frames: Mapped[list[Any]] = mapped_column()
    created_by: Mapped[str] = mapped_column(String(128))
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
