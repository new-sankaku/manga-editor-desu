"""GET /works/{id} の行の並びの試験（compose の PostgreSQL・OpenFGA を使う。速い組）。

前は表の行を ORDER BY 無しで返していた。PostgreSQL は、行を直したときに同じ場所へ書けない（表の頁が埋まっている・
索引の列が変わる）と、新しい版を表の後ろへ置き、返す順が変わる。取り込みの試験（test_translation_review_import.py）が
3回に1回、取り消しの後のページの順 [2, 1] で落ちた（2026-10-08）。
ここでは、頁が埋まったときと同じ動き（行の新しい版が後ろへ移る）を、索引の列を一度変えて戻すことで毎回起こす。
"""

import uuid

from conftest import h, user
from sqlalchemy import text
from test_human_ai_interchange import op, work_json
from test_print_manuscript_flow import book

from v3server.database_engine import get_sessionmaker


async def move_row_to_end(table: str, row_id: str, column: str, other: str) -> None:
    """索引のある列を別の値にして戻す（HOT 更新にならず、行の新しい版が表の後ろへ移る）。"""
    async with get_sessionmaker()() as s:
        old = (await s.execute(text(f"SELECT {column} FROM {table} WHERE id = :i"), {"i": row_id})).scalar_one()
        for v in (other, old):
            await s.execute(text(f"UPDATE {table} SET {column} = :v WHERE id = :i"), {"v": v, "i": row_id})
            await s.commit()


async def test_行の版が表の後ろへ移っても_ページとコマは決まった順で返る(api, authz):
    a = user()
    wid, ids, pids = await book(api, a, pages=4)
    other_ep = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_episode", "id": other_ep, "volume_id": ids["volume"],
                                   "number": 2})).status_code == 200
    panels = []
    for n in (1, 2, 3):
        pid = uuid.uuid4().hex
        r = await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": pids[1], "order": n,
                                   "frame": {"polygon_mm": [[0, 0], [10, 0], [10, 10], [0, 10]], "bleeds": False}})
        assert r.status_code == 200, r.text
        panels.append(pid)
    await move_row_to_end("pages", pids[0], "episode_id", other_ep)
    await move_row_to_end("panels", panels[0], "page_id", pids[2])
    # 取り消しを挟んでも同じ
    r = await op(api, wid, a, {"type": "update_page", "id": pids[0], "dpi": 300})
    assert r.status_code == 200, r.text
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))).status_code == 200
    w = await work_json(api, wid, a)
    assert [p["id"] for p in w["pages"] if p["episode_id"] == ids["episode"]] == pids
    assert [p["id"] for p in w["panels"] if p["page_id"] == pids[1]] == panels
