"""作画とネーム以外の工程（S0 企画・S1 構成・S2 設定資料・S6 総合）の作業を、本物の Temporal・PostgreSQL・OpenFGA と
偽の LLM で通す。LLM の答えは台本（Script.answers）で工程の問いごとに決める。
"""

from conftest import h, wait_for
from sqlalchemy import select
from test_harness import (  # noqa: F401  (fixture)
    admin,
    comfy,
    harness,
    harness_temporal,
    limits,
    make_work,
    no_leftover_flows,
    script,
    services,
    snap,
    unit_post,
    until_stage,
)
from test_human_ai_interchange import PAGE_SPEC, op

from v3server.canonical_tables.harness_tables import EpisodeOutline
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.database_engine import get_sessionmaker

PLAN = {"synopsis": "海辺の町で少女が古い灯台の秘密を追う", "audience": "中学生から", "exclusions": None, "notes": None}
OUTLINE = {"pages": [{"page": 1, "summary": "灯台を見上げる", "role": "導入"},
                     {"page": 2, "summary": "鍵を見つける", "role": "引き"}],
           "highlights": [2], "foreshadow": [{"page": 1, "setup": "灯台の灯が消えている", "payoff": "後の話"}]}


async def _start(api, w, stage, spec, **lim):
    r = await api.post(f"/works/{w['wid']}/harness/stages", headers=h(w["a"]), json={
        "episode_id": w["episode"], "stage": stage, "limits": limits(**lim), "spec": spec})
    assert r.status_code == 201, r.text
    return r.json()["stage_run_id"]


async def _unit(api, w, kind, *statuses, timeout=60):
    async def check():
        us = [u for u in (await snap(api, w))["units"] if u["kind"] == kind]
        return us[-1] if us and us[-1]["status"] in statuses else None
    return await wait_for(check, timeout)


async def _picked(api, w, uid):
    d = (await snap(api, w, uid))["unit"]
    cands = [c for c in d["candidates"] if c["attempt"] == d["attempt"]]
    return next(c for c in cands if c["picked"]), d


async def test_企画は質問を返し_答えると案を作り_採ると企画に書き_構成は決めごとを足すと進む(api, services, harness, script):
    w = await make_work(api, panels=0, thresholds=False)
    script.answers["plan_interview"] = {"questions": [{"ask": "読者は誰か", "why": "言葉の選び方が変わる"}], "plan": None}
    await _start(api, w, "S0", {"plan": {"request": "灯台の話を作りたい", "required_fields": ["synopsis", "audience"]}})
    u = await _unit(api, w, "plan_interview", "awaiting_review")
    cand, _ = await _picked(api, w, u["unit_id"])
    f = {x["name"]: x for x in cand["check"]["findings"]}
    assert f["作者への質問"]["ok"] is False and cand["content"]["questions"][0]["ask"] == "読者は誰か"
    # 質問だけの候補は採れない
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "approve", "candidate_id": cand["id"]})
    assert r.status_code == 422 and "answer" in r.json()["detail"]
    script.answers["plan_interview"] = {"questions": [], "plan": PLAN}
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "answer", "reason": "中学生から"})
    assert r.status_code == 200, r.text

    async def second_round():
        x = await _unit(api, w, "plan_interview", "awaiting_review")
        return x if x["attempt"] == 2 else None
    u = await wait_for(second_round, 60)
    cand, d = await _picked(api, w, u["unit_id"])
    ctx = next(s for s in d["steps"] if s["step"] == "context" and s["attempt"] == 2)
    assert "中学生から" in ctx["detail"]["question"]
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "approve", "candidate_id": cand["id"]})
    assert r.status_code == 200, r.text
    runs = await until_stage(api, w, "awaiting_review")
    async with get_sessionmaker()() as session:
        plan = (await session.execute(select(WorkPlan).where(WorkPlan.work_id == w["wid"]))).scalar_one()
        assert plan.synopsis == PLAN["synopsis"] and plan.audience == PLAN["audience"]
    r = await api.post(f"/works/{w['wid']}/harness/stages/{runs[-1]['id']}/approve", headers=h(w["a"]))
    assert r.status_code == 200, r.text
    # 構成（S1）の決めごとは始めるときに渡していないので止まる。足して再開すると進む
    u1 = await _unit(api, w, "structure", "blocked")
    assert "structure" in u1["stop_reason"]
    s1 = (await snap(api, w))["stage_runs"][-1]["id"]
    script.answers["structure"] = OUTLINE
    script.answers["structure_views"] = {"views": [{"view": "引きの強さ", "ok": False, "why": "2ページ目が弱い"}]}
    r = await api.put(f"/works/{w['wid']}/harness/stages/{s1}/spec", headers=h(w["a"]),
                      json={"spec": {"structure": {"page_count": 2, "views": ["引きの強さ"]}}})
    assert r.status_code == 200, r.text
    r = await unit_post(api, w, u1["unit_id"], "control", {"action": "resume"})
    assert r.status_code == 200, r.text
    u1 = await _unit(api, w, "structure", "awaiting_review")
    cand, _ = await _picked(api, w, u1["unit_id"])
    f = {x["name"]: x for x in cand["check"]["findings"]}
    assert f["ページの数"]["ok"] is True and f["観点：引きの強さ"]["ok"] is False
    assert cand["check_verdict"] == "flag"
    r = await unit_post(api, w, u1["unit_id"], "review", {"action": "approve", "candidate_id": cand["id"]})
    assert r.status_code == 200, r.text
    await _unit(api, w, "structure", "done")
    async with get_sessionmaker()() as session:
        row = (await session.execute(select(EpisodeOutline).where(EpisodeOutline.episode_id == w["episode"]))
               ).scalar_one()
        assert row.outline["highlights"] == [2]


async def test_構成のページの数が決めた数と違う案は落とす(api, services, harness, script):
    w = await make_work(api, panels=0, thresholds=False)
    assert (await op(api, w["wid"], w["a"], {"type": "set_work_plan", **{k: v for k, v in PLAN.items() if v}})
            ).status_code == 200
    script.answers["structure"] = OUTLINE
    await _start(api, w, "S1", {"structure": {"page_count": 3, "views": []}}, unit={"max_attempts": 1})
    u = await _unit(api, w, "structure", "stopped")
    d = (await snap(api, w, u["unit_id"]))["unit"]
    assert all(c["check_verdict"] == "drop" for c in d["candidates"])
    assert "check:ページの数" in d["fix_fallbacks"][0]["reason"] and "上限回数" in u["stop_reason"]


async def test_設定資料は人物を足し_同じ名前は飛ばして知らせる(api, services, harness, script):
    w = await make_work(api, panels=0, thresholds=False)
    assert (await op(api, w["wid"], w["a"], {"type": "set_work_plan", **{k: v for k, v in PLAN.items() if v}})
            ).status_code == 200
    script.answers["settings_sheet"] = {
        "characters": [{"name": "アオイ", "traits": "短い青い髪", "role": "主人公", "prompt": "1girl, short blue hair"},
                       {"name": "灯台守", "traits": "白い髭", "role": "導き手", "prompt": "1old man, white beard"}],
        "locations": [{"name": "灯台", "traits": "白い塔", "prompt": "lighthouse"}]}
    script.answers["distinguish"] = {"confusable": []}
    await _start(api, w, "S2", {"settings": {"model_description": "SD1.5 系", "character_min": 1, "character_max": 4,
                                             "document": None}})
    u = await _unit(api, w, "settings_sheet", "awaiting_review")
    cand, _ = await _picked(api, w, u["unit_id"])
    f = {x["name"]: x for x in cand["check"]["findings"]}
    assert f["人物の数"]["ok"] is True and f["設定資料に同じ名前"]["ok"] is False
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "approve", "candidate_id": cand["id"]})
    assert r.status_code == 200, r.text
    u = await _unit(api, w, "settings_sheet", "done")
    result = (await snap(api, w, u["unit_id"]))["unit"]["result"]
    assert result["skipped_existing"] == ["アオイ"] and len(result["added"]) == 2
    async with get_sessionmaker()() as session:
        rows = (await session.execute(select(MaterialEntry).where(MaterialEntry.work_id == w["wid"]))).scalars().all()
    names = sorted((m.kind, m.name, m.proposal_state) for m in rows)
    assert names == [("background", "灯台", "adopted"), ("character", "アオイ", "adopted"),
                     ("character", "灯台守", "adopted")]


async def test_総合は閾値が無ければ止まり_置くとページの白と要約を出して落とさない(api, services, harness, script):
    w = await make_work(api, panels=0, thresholds=False)
    assert (await op(api, w["wid"], w["a"], {"type": "set_work_settings", "page_spec": PAGE_SPEC,
                                             "first_page_is_left": True})).status_code == 200
    script.answers["page_summary"] = {"pages": [{"image": 1, "summary": "白いページ"}, {"image": 2, "summary": "白いページ"}]}
    await _start(api, w, "S6", {})
    u = await _unit(api, w, "overall_review", "blocked")
    assert "harness.overall.page_white_max" in u["stop_reason"]
    for key, v in (("spread_black_max", 0.5), ("page_white_max", 0.9)):
        r = await op(api, w["wid"], w["a"], {"type": "set_threshold", "key": f"harness.overall.{key}",
                                             "value": {"value": v}, "source": "試験", "status": "unverified"})
        assert r.status_code == 200, r.text
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "resume"})
    assert r.status_code == 200, r.text
    u = await _unit(api, w, "overall_review", "awaiting_review")
    cand, _ = await _picked(api, w, u["unit_id"])
    f = {x["name"]: x for x in cand["check"]["findings"]}
    white = f["ページの白（1ページ）"]
    assert white["ok"] is False and "unverified" in white["detail"]
    assert f["構成との食い違い"]["ok"] is None
    assert cand["check_verdict"] == "flag" and cand["content"]["summaries"][0] == {"page": 1, "summary": "白いページ"}
