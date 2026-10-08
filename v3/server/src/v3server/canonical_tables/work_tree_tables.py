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

from v3server.canonical_tables.table_base import Base, JsonType, new_id

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
    # ページの寸法（name_structure の PageSpec の形）。コマ割りの計算と検査が使う。決めるまでは無い
    page_spec: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    # 1ページ目を左のページに置くか（V3ハーネス設計 6章）。決めるまでは無い
    first_page_is_left: Mapped[bool | None] = mapped_column(Boolean)
    default_page_count: Mapped[int | None] = mapped_column(Integer)
    # 作業ごとのAIの関与（operations/ai_involvement.py）。{作業: 関与}。選んでいない作業は設計の既定
    ai_involvement: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 作品の設定（言語・種類ごとの書体・書き出しの既定。operations/work_preference_operations.py の WorkPreferences）
    preferences: Mapped[dict[str, Any]] = mapped_column(default=dict)
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
    # 段の割り（見開きか・段ごとのコマの番号・段の高さの比・コマの幅の比）。人が引いても、AIが決めても同じ形
    layout: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 人の手の印が付いた項目の名前（V3細部の決めごと 10.2）。AIはこの項目を変えられない
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    # 抜いたページは消さずに残す（V3細部の決めごと 15章）
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    # ページの種類（name_structure/print_settings.py の PageKind：cover・color_page・body・blank）。未定なら無い
    page_kind: Mapped[str | None] = mapped_column(String(16))
    # 色の種類（bilevel・grayscale・color）。無ければ作品の preferences.print.color_mode
    color_mode: Mapped[str | None] = mapped_column(String(16))
    # 解像度。無ければ作品の preferences.print.dpi_by_color_mode の、このページの色の種類の値
    dpi: Mapped[int | None] = mapped_column(Integer)
    # ノンブルの出し方（visible・hidden・none）。無ければ作品の preferences.nombre.display_by_kind
    nombre_display: Mapped[str | None] = mapped_column(String(16))


class Spread(Base):
    """見開き：並んだ2ページの組と、見開きにまたがる1枚の絵（V3細部の決めごと 1.3）。
    絵の座標は見開きの基本枠の座標（左のページの基本枠の左上が原点。右のページは仕上がりの幅だけ右）。
    どちらのページが左になるかは、書き出しのときに読む向きで決める（print_export/book_layout.py）。"""

    __tablename__ = "spreads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    # 読む順で前のページと後ろのページ
    first_page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    second_page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    # 見開きにまたがる絵（image_files の行）と、その切り抜きと置き場（ImagePlacement。見開きの座標）
    image_id: Mapped[str | None] = mapped_column(ForeignKey("image_files.id"))
    image_placement: Mapped[dict[str, Any] | None] = mapped_column()
    adjustments: Mapped[list[Any]] = mapped_column(default=list)
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
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
    # コマに使う絵（image_files の行）。生成した絵・人が描いた絵・取り込んだ絵のどれでもよい
    image_id: Mapped[str | None] = mapped_column(ForeignKey("image_files.id"))
    # コマの絵の切り抜きと置き場（name_structure/image_placement.py の ImagePlacement）。決めていなければ無い
    image_placement: Mapped[dict[str, Any] | None] = mapped_column()
    # 枠の線と塗り（name_structure/item_styles.py の FrameStyle）。無ければ作品の既定（書き出しで決めていなければ止める）
    frame_style: Mapped[dict[str, Any] | None] = mapped_column()
    # コマの絵の仕上げ（item_styles.py の Adjustment の並び）
    adjustments: Mapped[list[Any]] = mapped_column(default=list)
    # 人が掛けた「動かさない」。人もAIも変えられない。外せるのは人だけ
    fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    # 人の手の印が付いた項目の名前（V3細部の決めごと 10.2）。AIはこの項目を変えられない
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    # 人の確定印（V3ハーネス設計 9.2）。付いたコマはAIが何も変えられない
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
