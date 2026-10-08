"""書き出しの途中で作業者が止まったときの試験（compose の PostgreSQL・OpenFGA・Temporal を使う）。

前は書き出しの送り直しが1回きりで、生存の知らせも無かった。作業者を止めると ExportRun が running のまま残り、
書き出しが終わらなかった（2026-10-08 保存と再起動の確かめで見つけた。V3サーバーの土台「保存と再起動の確かめ」）。
ここでは作業者を止めて起こし、別の回でやり直して1回だけ終えること、やり直しを使い切ったら failed にすることを確かめる。
本物のプロセスを落とす確かめ（SIGTERM）は v3/web/test/persistence_e2e.mjs の場面 c。
"""

import asyncio

from conftest import h, user, wait_for
from temporalio import activity
from temporalio.worker import Worker
from test_human_ai_interchange import op
from test_human_edit_and_handover import image_dir  # noqa: F401  (fixture)
from test_human_tools_and_finishing import export_env  # noqa: F401  (fixture)
from test_print_manuscript_flow import book, needs_font

from v3server.print_export import export_runner, export_workflow
from v3server.print_export.export_workflow import EXPORT_ACTIVITIES, EXPORT_QUEUE, ExportRunWorkflow


async def restart_export_worker(workers) -> None:
    """書き出しの待ち行列の作業者だけを止めて、新しく起こす（止めると、動いている書き出しは取り消される）。"""
    await workers.export.shutdown()
    await workers._export_task
    workers.export = Worker(workers.client, task_queue=EXPORT_QUEUE, workflows=[ExportRunWorkflow],
                            activities=EXPORT_ACTIVITIES)
    workers._export_task = asyncio.create_task(workers.export.run())


async def _ready_book(api, a):
    wid, _, pids = await book(api, a)
    r = await op(api, wid, a, {"type": "update_page", "id": pids[0], "page_kind": "body"})
    assert r.status_code == 200, r.text
    return wid, pids[0]


async def _start(api, wid, a, page):
    r = await api.post(f"/works/{wid}/exports", headers=h(a), json={"format": "png", "page_ids": [page]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _until_end(api, wid, a, rid, timeout=60):
    async def end():
        got = (await api.get(f"/works/{wid}/exports/{rid}", headers=h(a))).json()
        return got if got["status"] in ("done", "failed") else None
    return await wait_for(end, timeout)


@needs_font
async def test_書き出しの途中で作業者が止まっても_やり直して1回だけ終える(api, authz, workers, export_env, monkeypatch):  # noqa: F811
    a = user()
    wid, page = await _ready_book(api, a)
    real = export_runner.run_export
    attempts: list[int] = []

    async def first_hangs(session, run):
        attempts.append(activity.info().attempt)
        if len(attempts) == 1:
            await asyncio.Event().wait()   # 1回目は終わらない（作業者が止まるまで）
        return await real(session, run)

    monkeypatch.setattr(export_runner, "run_export", first_hangs)
    rid = await _start(api, wid, a, page)
    await wait_for(lambda: asyncio.sleep(0, result=attempts == [1]), 30)
    await restart_export_worker(workers)
    run = await _until_end(api, wid, a, rid)
    assert run["status"] == "done", run["detail"]
    assert attempts == [1, 2]
    assert [o["page_id"] for o in run["outputs"]] == [page]


@needs_font
async def test_やり直しを使い切ったら書き出しをfailedにして理由を残す(api, authz, workers, export_env, monkeypatch):  # noqa: F811
    a = user()
    wid, page = await _ready_book(api, a)
    attempts: list[int] = []

    async def always_hangs(session, run):
        attempts.append(activity.info().attempt)
        await asyncio.Event().wait()

    monkeypatch.setattr(export_runner, "run_export", always_hangs)
    rid = await _start(api, wid, a, page)
    for n in range(1, export_workflow.MAX_ATTEMPTS + 1):
        await wait_for(lambda n=n: asyncio.sleep(0, result=len(attempts) == n), 30)
        await restart_export_worker(workers)
    run = await _until_end(api, wid, a, rid)
    assert run["status"] == "failed" and "やり直しても終わらなかった" in run["detail"], run
    assert len(attempts) == export_workflow.MAX_ATTEMPTS
