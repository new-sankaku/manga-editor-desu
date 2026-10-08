"""コマの中の文字（吹き出し・ナレーションの箱・描き文字）と、コマの絵の層と、人の手の範囲（AIが描き直さない所）。
どれも人が直接直せる。人が変えた項目には人の手の印が付き、AIの変更が当たると判断待ちになる（operations/human_hand_guard.py）。"""

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
    # 書体の名前（書体のフォルダ V3_FONT_DIR の中のファイル名から拡張子を除いたもの）。無ければ作品の設定の「種類ごとの書体」
    font_family: Mapped[str | None] = mapped_column(Text)
    # 文字の飾り（name_structure/item_styles.py の TextDecoration）。無ければ飾らない
    decoration: Mapped[dict[str, Any] | None] = mapped_column()
    # ルビ（item_styles.py の Ruby の並び）
    ruby: Mapped[list[Any]] = mapped_column(default=list)
    # 文字の一部の書式（name_structure/print_settings.py の TextSpan の並び：書体・大きさ・太らせる・色）
    spans: Mapped[list[Any]] = mapped_column(default=list)
    # 組版（print_settings.py の Typesetting）。無ければ作品の preferences.typesetting
    typesetting: Mapped[dict[str, Any] | None] = mapped_column()
    # フキダシの形（item_styles.py の BalloonShape）。描き文字・決めていない文字は無い
    balloon_shape: Mapped[dict[str, Any] | None] = mapped_column()
    # 回転（文字の角度）・傾き・反転（name_structure/item_transform.py の ItemTransform）
    transform: Mapped[dict[str, Any]] = mapped_column(default=dict)
    opacity: Mapped[float] = mapped_column(Float, default=1.0)
    # 仕上げ（item_styles.py の Adjustment の並び）
    adjustments: Mapped[list[Any]] = mapped_column(default=list)
    # 人が掛けた「動かさない」。人もAIも変えられない。外せるのは人だけ
    fixed: Mapped[bool] = mapped_column(Boolean, default=False)
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
    # 仕上げ（name_structure/item_styles.py の Adjustment の並び）
    adjustments: Mapped[list[Any]] = mapped_column(default=list)
    # 人が掛けた「動かさない」。人もAIも変えられない。外せるのは人だけ
    fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    # ペンの線（pen_strokes）の版。線を足す・変える・消すたびに1つ増える
    stroke_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # 今の絵（image_id）を、線のどの版から作ったか。stroke_revision と違えば、絵は古い控え
    image_stroke_revision: Mapped[int | None] = mapped_column(Integer)
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
    # 絵の画素の座標の多角形 [[x, y], ...]。消しゴム・PSD の戻しで決めた範囲は多角形でなくマスクの絵で持つ
    polygon_px: Mapped[list[Any] | None] = mapped_column()
    # 範囲のマスクの絵（白が範囲。置き場の sha256。絵と同じ大きさ）。多角形とどちらか一方
    mask_sha256: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(128))
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HeldAiChange(Base):
    """判断待ち（V3細部の決めごと 5章・10.2）。人が決めるまで正本に入れない変更。
    - field_change：AIの変更が人の手の印の付いた項目に当たった。人が「採る」と、その値が人の判断として入る（人の手の印が付く）
    - ai_operation：AIの操作（コマを分ける・合わせるなど、1項目に分けられないもの）が人の手の所に当たった。payload が操作
    - psd_*：人が直した PSD を戻したときに、当てられなかった層（operations/psd_import_operations.py）。choices から選ぶ"""

    __tablename__ = "held_ai_changes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # 行の表の名前と、その id
    target_table: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(32))
    # ページに属さない行（企画・設定資料）は無い
    page_id: Mapped[str | None] = mapped_column(ForeignKey("pages.id"), index=True)
    # 項目の名前。"removed" はAIが抜こうとした
    field: Mapped[str] = mapped_column(String(64))
    # field_change・ai_operation・psd_text_pixels・psd_unmatched_layer・psd_vector_changed・psd_layer_missing
    kind: Mapped[str] = mapped_column(String(32), default="field_change", server_default="field_change")
    # 選べる手（kind が field_change 以外）。選んだ手は chosen
    choices: Mapped[list[Any] | None] = mapped_column()
    chosen: Mapped[str | None] = mapped_column(String(32))
    # 選ぶときに使う値（AIの操作、PSD から取った絵の id と置き場など）
    payload: Mapped[dict[str, Any] | None] = mapped_column()
    # 値は JSON（None も値として持つ）
    proposed_value: Mapped[Any] = mapped_column(JsonType, nullable=True)
    current_value: Mapped[Any] = mapped_column(JsonType, nullable=True)
    # どの案から出たか
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("name_proposals.id"))
    # open（判断待ち）・accepted（採った）・rejected（採らない）・withdrawn（案の採用を取り消した）
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
