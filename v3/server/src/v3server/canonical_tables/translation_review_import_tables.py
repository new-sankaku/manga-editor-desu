"""今のアプリからの移行・翻訳・承認と進み具合の表（V3点検の結果 5章の6）。

- TextItemTranslation：文字1つの言語ごとの版。元の言語の文字は TextItem.text に持ち、ほかの言語をここに1行ずつ持つ
  （V3細部の決めごと 2.3「セリフの文字は言語ごとに持つ。フキダシの位置と話者は全言語で共通」）。
  言語ごとに別の行なので、人の手の印と判断待ちも言語ごとに分かれる
- ReviewState・ReviewRecord：ページと作品の承認の状態（下書き・確認待ち・承認・直しが要る）と、その記録（コメント付き）
- ElementGenerationSetting：今のアプリでコマ・絵ごとに持っていたAIの設定（プロンプト・シードなど）。元の値のまま持つ
- CurrentAppImportReport：今のアプリのプロジェクトを取り込んだときの報告。元の物1つずつ、どこへ入れたか・入れられなかった理由
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id

# ---------------------------------------------------------------- 翻訳


class TextItemTranslation(Base):
    __tablename__ = "text_item_translations"
    __table_args__ = (UniqueConstraint("text_item_id", "language"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # 文字はページの間を動かないので、ページはここに持つ（ロック・判断待ちの範囲）
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    text_item_id: Mapped[str] = mapped_column(ForeignKey("text_items.id"), index=True)
    # 言語の名前（BCP 47 の形。en・zh-Hans など）。作品の言語（preferences.language）とは違う言語だけ
    language: Mapped[str] = mapped_column(String(35))
    text: Mapped[str] = mapped_column(Text)
    # 文字の向きは言語ごとに持つ（V3細部の決めごと 2.1）。無ければ元の文字の向き
    writing_direction: Mapped[str | None] = mapped_column(String(16))
    # 訳文が収まらないときに小さくする手（同 2.3）。無ければ元の文字の大きさ
    font_size_pt: Mapped[float | None] = mapped_column(Float)
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- 承認と進み具合


class ReviewState(Base):
    """承認の今の状態。行の無いページ・作品は下書き（draft）。"""

    __tablename__ = "review_states"
    __table_args__ = (UniqueConstraint("target_kind", "target_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # page・work
    target_kind: Mapped[str] = mapped_column(String(8))
    target_id: Mapped[str] = mapped_column(String(32))
    # draft（下書き）・in_review（確認待ち）・approved（承認）・needs_changes（直しが要る）
    status: Mapped[str] = mapped_column(String(16))
    updated_by: Mapped[str] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewRecord(Base):
    """状態を変えた記録。消さない。取り消しも1件の記録として足す（reverts_record_id）。"""

    __tablename__ = "review_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    target_kind: Mapped[str] = mapped_column(String(8))
    target_id: Mapped[str] = mapped_column(String(32), index=True)
    from_status: Mapped[str] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(Text)
    actor_kind: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[str] = mapped_column(String(128))
    # 取り消しの記録なら、取り消した記録
    reverts_record_id: Mapped[str | None] = mapped_column(ForeignKey("review_records.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- 今のアプリからの移行


class ElementGenerationSetting(Base):
    """今のアプリのコマ・絵・プロジェクトが持っていたAIの設定。V3 の生成はまだ読まない（未接続）。"""

    __tablename__ = "element_generation_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # project_base（プロジェクトの基本のプロンプト）・panel（コマ）・image（絵）
    target_kind: Mapped[str] = mapped_column(String(16))
    page_id: Mapped[str | None] = mapped_column(ForeignKey("pages.id"), index=True)
    panel_id: Mapped[str | None] = mapped_column(ForeignKey("panels.id"), index=True)
    image_id: Mapped[str | None] = mapped_column(ForeignKey("image_files.id"))
    prompt: Mapped[str | None] = mapped_column(Text)
    negative_prompt: Mapped[str | None] = mapped_column(Text)
    # 元の項目と値（text2img_*・img2img* など）をそのまま。-1 のような「未設定」の印も読み替えない
    source_values: Mapped[dict[str, Any]] = mapped_column(default=dict)
    import_report_id: Mapped[str | None] = mapped_column(ForeignKey("current_app_import_reports.id"))
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class CurrentAppImportReport(Base):
    __tablename__ = "current_app_import_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"))
    source_file_name: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64))
    # 取り込んだ絵の出どころ（imported・human_drawn）。取り込む人が選ぶ
    image_origin: Mapped[str] = mapped_column(String(16))
    created_by: Mapped[str] = mapped_column(String(128))
    # 種類ごとの数 {"元の物": n, "入れた": n, "形を変えて入れた": n, "入れられなかった": n}
    counts: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 元の物1つずつ（current_app_import/import_plan.py の ReportEntry）
    entries: Mapped[list[Any]] = mapped_column(default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
