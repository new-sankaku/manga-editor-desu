"""作画（S4）の作業の中身を、本物の Temporal・PostgreSQL・OpenFGA と偽の ComfyUI・LLM・検出器で通す。

流れの筋道（直す回数・答え・知らせ）は tests/unit/test_unit_workflow_timeskip.py で時間を飛ばして確かめる。
ここは段の中身：形の指定・背景の3D・直させる・2枚ずつの比べ・コマをまたぐ一致・足りない入力の記録。
"""

import io
import uuid

import pytest
from conftest import h, wait_for
from harness_fakes import Script  # noqa: F401
from PIL import Image
from sqlalchemy import select
from test_harness import (  # noqa: F401  (fixture)
    BACKGROUND,
    DRAWING,
    FRAME,
    admin,
    comfy,
    harness,
    jobs_of,
    make_work,
    no_leftover_flows,
    script,
    services,
    snap,
    start,
    unit_post,
    until_stage,
    until_unit,
)
from test_human_ai_interchange import op

from v3server.canonical_tables.harness_tables import HarnessUnit
from v3server.database_engine import get_sessionmaker

pytestmark = pytest.mark.full

PEOPLE_BOX = [{"name": "アオイ", "face": "中", "facing": "正面", "box_mm": [0, 0, 30, 40]}]


def _png(w: int = 64, h_: int = 64, color=(200, 200, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h_), color).save(buf, format="PNG")
    return buf.getvalue()


async def _threshold(api, w, key, value):
    r = await op(api, w["wid"], w["a"], {"type": "set_threshold", "key": f"harness.drawing.{key}",
                                         "value": {"value": value}, "source": "試験", "status": "verified"})
    assert r.status_code == 200, r.text


async def _panel(api, w, content, order=2):
    pid = uuid.uuid4().hex
    r = await op(api, w["wid"], w["a"], {"type": "add_panel", "id": pid, "page_id": w["page"], "order": order,
                                         "frame": FRAME, "content": content})
    assert r.status_code == 200, r.text
    return pid


async def _upload(api, w, role, panel_id=None):
    data = {"role": role, "origin": "human_drawn"}
    if panel_id:
        data["panel_id"] = panel_id
    r = await api.post(f"/works/{w['wid']}/images", headers=h(w["a"]), data=data,
                       files={"image": ("x.png", _png(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _detail(api, w, uid):
    return (await snap(api, w, uid))["unit"]


def _findings(cand):
    return {f["name"]: f for f in cand["check"]["findings"]}


async def test_場所の3Dから背景を描き_人物を描き足し_人物の位置と吹き出しを検査する(api, services, harness, script):
    w = await make_work(api, panels=0)
    await _threshold(api, w, "person_iou_min", 0.3)
    await _threshold(api, w, "face_covered_max", 0.5)
    scene = {"boxes": [[-5, -1, 8, 5, 3, 9]], "cameras": {"正面": {"position": [0, 1, 0], "yaw_degrees": 0,
                                                                   "pitch_degrees": 0, "fov_degrees": 60}}}
    r = await op(api, w["wid"], w["a"], {"type": "add_material_entry", "kind": "background", "name": "教室",
                                         "generation": {"prompt": "classroom", "scene3d": scene}})
    assert r.status_code == 200, r.text
    pid = await _panel(api, w, {"content": "教室で振り返る", "shot": "胸から上", "angle": "目の高さ",
                                "location": "教室", "view": "正面", "people": PEOPLE_BOX}, order=1)
    r = await op(api, w["wid"], w["a"], {"type": "add_text_item", "panel_id": pid, "item_kind": "balloon", "order": 1,
                                         "text": "おはよう", "box_mm": [40, 0, 60, 10]})
    assert r.status_code == 200, r.text
    await start(api, w, drawing={**DRAWING, "background": BACKGROUND})
    u = await until_unit(api, w, "awaiting_review")
    d = await _detail(api, w, u["unit_id"])
    cand = next(c for c in d["candidates"] if c["picked"])
    roles = [j["role"] for j in cand["made_with"]["jobs"]]
    assert roles == ["background", "composite"], roles
    assert any("箱の3D" in x for x in cand["made_with"]["used"])
    jobs = await jobs_of(u["unit_id"])
    bg = [j for j in jobs if j.request.get("register", {}).get("role") == "background"]
    assert bg and all(j.process == "text_to_image" and j.request["image_process"]["params"]["control"] == "depth"
                      and j.request["input_images"][0]["png_base64"] for j in bg)
    assert any(j.process == "inpaint" for j in jobs)
    f = _findings(cand)
    assert f["人物の位置（IoU）"]["ok"] is True and "下限 0.3" in f["人物の位置（IoU）"]["detail"]
    assert f["顔と吹き出しの重なり"]["ok"] is not None and "上限" in f["顔と吹き出しの重なり"]["detail"]


async def test_足りない入力は候補に書き残す(api, services, harness, script):
    w = await make_work(api)
    await start(api, w)
    u = await until_unit(api, w, "awaiting_review")
    cand = (await _detail(api, w, u["unit_id"]))["candidates"][0]
    missing = "\n".join(cand["made_with"]["missing"])
    assert "アオイ の範囲" in missing and "場所（location）が無い" in missing


async def test_絵の中の文字で落ちた候補は囲んで直し_直した候補を検査し直して通す(api, services, harness, script):
    script.texts, script.texts_calls = 1, 2  # 2枚の初めの検査だけ文字が出る（直した後は消えた）
    w = await make_work(api)
    await start(api, w)
    u = await until_unit(api, w, "awaiting_review")
    d = await _detail(api, w, u["unit_id"])
    fixed = [c for c in d["candidates"] if c["fixed_from"]]
    assert len(fixed) == 2 and all(c["fix_round"] == 1 and c["check_verdict"] != "drop" for c in fixed)
    assert all(c["made_with"]["fix"]["kinds"] == ["text"] for c in fixed)
    assert [s["step"] for s in d["steps"]] == ["cut_out", "context", "generate", "check", "fix", "check", "evaluate"]
    jobs = await jobs_of(u["unit_id"])
    inpaint = [j for j in jobs if j.process == "inpaint"]
    assert len(inpaint) == 2
    for j in inpaint:
        assert "no text" in j.request["image_process"]["params"]["prompt"]
        assert j.request["input_images"][1]["purpose"] == "mask" and j.request["input_images"][1]["region_px"]
    assert not d["fix_fallbacks"]


async def test_直しても落ちたままなら記録してから作り直し_上限回数で止まる(api, services, harness, script):
    script.texts = 1
    w = await make_work(api)
    await start(api, w, unit={"max_attempts": 1})
    u = await until_unit(api, w, "stopped")
    d = await _detail(api, w, u["unit_id"])
    assert len(d["fix_fallbacks"]) == 1
    assert "直す上限（1回）" in d["fix_fallbacks"][0]["reason"]
    assert "上限回数" in u["stop_reason"]


async def test_比べで左右を入れ替えると答えが変わる組は引き分けで_1位が決まらず止まる(api, services, harness, script):
    script.pair = "a"
    w = await make_work(api)
    await start(api, w, unit={"max_attempts": 1})
    u = await until_unit(api, w, "stopped")
    d = await _detail(api, w, u["unit_id"])
    ev = next(s for s in d["steps"] if s["step"] == "evaluate")["detail"]
    assert ev["picked"] is None and ev["failure"] == "evaluate:同点"
    assert all(r["verdict"] == "tie" and r["first"] != r["second"] for r in ev["rounds"])
    assert not any(c["picked"] for c in d["candidates"])


async def test_人が描いた下絵があれば線画の形の指定で描く(api, services, harness, script):
    w = await make_work(api)
    rough = await _upload(api, w, "line_art", w["pids"][0])
    await start(api, w)
    u = await until_unit(api, w, "awaiting_review")
    gen = [j for j in await jobs_of(u["unit_id"]) if j.process == "text_to_image"]
    assert len(gen) == 2
    for j in gen:
        assert j.request["image_process"]["params"]["control"] == "lineart"
        assert j.request["input_images"] == [{"node": "control", "input": "image", "purpose": "control",
                                              "image_id": rough}]
    cand = (await _detail(api, w, u["unit_id"]))["candidates"][0]
    assert any("下絵" in x for x in cand["made_with"]["used"])


async def test_設定資料の絵と違う人物になったコマを工程の検査で挙げ_そのコマだけ作り直せる(api, services, harness, script):
    w = await make_work(api, panels=0)
    await _threshold(api, w, "ccip_threshold", 0.178)
    ref = await _upload(api, w, "character_sheet")
    r = await op(api, w["wid"], w["a"], {"type": "add_material_entry", "kind": "character", "name": "ミドリ",
                                         "traits": "長い緑の髪", "image_ids": [ref],
                                         "generation": {"prompt": "1girl, long green hair"}})
    assert r.status_code == 200, r.text
    content = {"content": "立つ", "shot": "全身", "angle": "目の高さ",
               "people": [{"name": "ミドリ", "face": "小", "facing": "正面"}]}
    await _panel(api, w, content, order=1)
    run_id = await start(api, w)
    u = await until_unit(api, w, "awaiting_review")
    cand = next(c for c in (await _detail(api, w, u["unit_id"]))["candidates"] if c["picked"])
    assert _findings(cand)["同じ人物（CCIP）"]["ok"] is True
    script.same = False  # 採った後に工程の検査で比べると「違う」
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "approve", "candidate_id": cand["id"]})
    assert r.status_code == 200, r.text
    runs = await until_stage(api, w, "awaiting_review")
    check = runs[-1]["stage_check"]
    assert check["drifted_units"] == [u["unit_id"]]
    assert check["drift_compared"][0]["same"] is False
    script.same = True
    r = await api.post(f"/works/{w['wid']}/harness/stages/{run_id}/rerun", headers=h(w["a"]),
                       json={"unit_ids": check["drifted_units"]})
    assert r.status_code == 200, r.text

    async def rerun_unit():
        async with get_sessionmaker()() as session:
            return (await session.execute(select(HarnessUnit).where(HarnessUnit.rerun_of == u["unit_id"]))
                    ).scalar_one_or_none()
    again = await wait_for(rerun_unit, 30)
    assert again.kind == "panel_drawing" and again.requested_by == w["a"]
