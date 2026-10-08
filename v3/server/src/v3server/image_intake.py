"""絵の入口。人が置いた絵・持ち込んだ絵・生成した絵は、全部ここを通って置き場に入る（V3ハーネス設計 12章の「取り込みの入口」と
「生成の出口」）。規制の判定を差し込む場所はここの1か所だけ。

今は判定の手段と閾値が決まっていない（12章「後で決めるもの」）。INTAKE_JUDGES は空で、どの絵にも
「判定していない（not_judged）」を記録する。通したことにはしない。手段を決めたら INTAKE_JUDGES に足す。
止めた絵も消さない（方針10）。置き場には置き、記録を残し、登録（RegisterImage）を断る。
判定の記録は作品データではないので、操作の窓口を通さず、その場で確定する（呼び出しの記録と同じ扱い）。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.image_file_tables import ImageIntakeScreening
from v3server.image_file_storage import StoredImage, inspect_image, store_image
from v3server.v3_error_types import Invalid

IntakeEntry = Literal["human_upload", "generated"]


@dataclass(frozen=True)
class JudgeVerdict:
    blocked: bool
    detail: str


# (手段の名前, 判定する関数)。関数は (絵の中身, 作品の id, 入口) を受け取る
IntakeJudge = Callable[[bytes, str, IntakeEntry], Awaitable[JudgeVerdict]]
INTAKE_JUDGES: list[tuple[str, IntakeJudge]] = []

NOT_JUDGED_DETAIL = "規制の判定の手段がまだ決まっていない（V3ハーネス設計 12章）。判定していない"


async def take_in_image(session: AsyncSession, work_id: str, data: bytes, entry: IntakeEntry) -> StoredImage:
    """絵を確かめて置き場に置き、判定を記録する。止めたときは記録を確定してから Invalid にする。"""
    inspect_image(data)
    stored = store_image(data)
    rows = []
    if not INTAKE_JUDGES:
        rows.append(ImageIntakeScreening(work_id=work_id, sha256=stored.sha256, entry=entry, status="not_judged",
                                         judge=None, detail=NOT_JUDGED_DETAIL))
    for name, judge in INTAKE_JUDGES:
        verdict = await judge(data, work_id, entry)
        rows.append(ImageIntakeScreening(work_id=work_id, sha256=stored.sha256, entry=entry,
                                         status="blocked" if verdict.blocked else "passed", judge=name,
                                         detail=verdict.detail))
    session.add_all(rows)
    await session.commit()
    blocked = [r for r in rows if r.status == "blocked"]
    if blocked:
        raise Invalid(f"入口の判定で止めた（{blocked[0].judge}）: {blocked[0].detail}")
    return stored
