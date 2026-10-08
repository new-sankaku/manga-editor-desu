"""絵のファイルの記録。生成した絵も、人が描いた絵も、外から持ち込んだ絵も同じ表に持つ（出どころの印だけが違う）。
ファイルの中身は置き場（image_file_storage.py）に、中身の sha256 を名前にして置く。"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id


class ImageFile(Base):
    __tablename__ = "image_files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # どのページ・コマのための絵か。設定資料の絵などはどちらも無い
    page_id: Mapped[str | None] = mapped_column(ForeignKey("pages.id"), index=True)
    panel_id: Mapped[str | None] = mapped_column(ForeignKey("panels.id"), index=True)
    # 絵の役目：コマの絵・線画・ベタ・トーン・着彩・背景・人の手・ページの原稿・参照・設定資料
    role: Mapped[str] = mapped_column(String(32))
    # 出どころ：generated（生成）・human_drawn（人が描いた）・imported（外から持ち込んだ）・
    # human_edited（前の版に人が外のソフトなどで手を入れた）
    origin: Mapped[str] = mapped_column(String(16))
    # 元にした版（作り直し・囲んで直す・人が手を入れた絵の、元の絵）。最初の版は無い
    based_on_image_id: Mapped[str | None] = mapped_column(ForeignKey("image_files.id"), index=True)
    # 利用の条件（usage_terms_schema.py の UsageTerms）。持ち込んだ絵は必須。生成した絵は使ったサービスの条件を見る
    usage_terms: Mapped[dict[str, Any] | None] = mapped_column()
    # 生成したときの依頼。人が描いた・持ち込んだ絵は無い
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    # 持ち込んだ絵の元（ファイル名・作者・使ってよい条件など、人が書いたもの）
    source_note: Mapped[str | None] = mapped_column(Text)
    registered_by_kind: Mapped[str] = mapped_column(String(8))
    registered_by_id: Mapped[str] = mapped_column(String(128))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    media_type: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    # 画像に書かれた解像度。書かれていなければ無い
    dpi: Mapped[int | None] = mapped_column(Integer)
    # 生成の設定（モデル・seed など）や、取り込んだときの付帯の情報
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImageIntakeScreening(Base):
    """絵の入口での規制の判定の記録（V3ハーネス設計 12章）。人が置いた絵も、持ち込んだ絵も、生成した絵も、
    置き場に入るときに必ず1行足す（image_intake.py）。判定の手段は後で決めるので、今は「判定していない」を記録する。
    絵を登録する操作（RegisterImage）は、この行の無い絵と、止められた絵を受け付けない。"""

    __tablename__ = "image_intake_screenings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    # 入口：human_upload（人が置いた・持ち込んだ）・generated（生成の出口）
    entry: Mapped[str] = mapped_column(String(16))
    # not_judged（判定の手段が決まっていない）・passed（通した）・blocked（止めた）
    status: Mapped[str] = mapped_column(String(16))
    # 判定した手段の名前。判定していなければ無い
    judge: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
