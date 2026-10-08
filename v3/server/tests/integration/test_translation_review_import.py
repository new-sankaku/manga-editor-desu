"""今のアプリのプロジェクトの取り込み・翻訳・確認の状態と進み具合（V3点検の結果 5章の6）。
PostgreSQL・OpenFGA を実際に使う。取り込みは、今のアプリを Playwright で動かして保存した本物のファイル
（tests/fixtures/current_app_project_4pages.lz4。作り方は tests/fixtures/build_current_app_project.js）を使う。"""

import hashlib
import io
import pathlib
from datetime import UTC, datetime, timedelta

import pytest
from conftest import h, new_work, user, wait_for
from PIL import Image
from sqlalchemy import select
from test_human_ai_interchange import TERMS, ai_op, allow_ai, op, work_json
from test_human_tools_and_finishing import FRAME_STYLE, export_env, ready_page  # noqa: F401  (export_env は fixture)
from test_human_edit_and_handover import image_dir  # noqa: F401  (fixture)

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.translation_review_import_tables import ElementGenerationSetting
from v3server.current_app_import.project_file_reader import data_url_bytes, read_project_file
from v3server.database_engine import get_sessionmaker
from v3server.v3_error_types import Forbidden

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "current_app_project_4pages.lz4"
# 今のアプリの A4（canvas_info.json の pageWidthMm・pageHeightMm）に合わせた寸法
A4_SPEC = {"frame_width_mm": 180, "frame_height_mm": 270, "trim_width_mm": 210, "trim_height_mm": 297,
           "bleed_mm": 3, "gutter_x_mm": 2, "gutter_y_mm": 5}
TEXT_TYPES = ("vertical-textbox", "textbox", "i-text")


def live(rows, **kw):
    return [r for r in rows if not r["removed"] and all(r[k] == v for k, v in kw.items())]


async def import_fixture(api, wid, a, eid, **form):
    data = {"image_origin": "imported", "usage_terms": __import__("json").dumps(TERMS)} | form
    return await api.post(f"/works/{wid}/episodes/{eid}/current-app-imports", headers=h(a),
                          files={"project": (FIXTURE.name, FIXTURE.read_bytes(), "application/octet-stream")},
                          data=data)


async def test_今のアプリのプロジェクトを取り込み_元と突き合わせる(api, image_dir):  # noqa: F811
    a, b = user(), user()
    ids = await new_work(api, a)
    wid = ids["work"]
    assert (await op(api, wid, a, {"type": "set_member", "user": b, "role": "editor", "granted": True})).status_code == 200
    # 寸法が無ければ止める
    r = await import_fixture(api, wid, a, ids["episode"])
    assert r.status_code == 422 and "page_spec" in r.text
    assert (await op(api, wid, a, {"type": "set_work_settings", "page_spec": A4_SPEC})).status_code == 200
    # 作者のほかは取り込めない。持ち込んだ絵は利用の条件が要る
    assert (await import_fixture(api, wid, b, ids["episode"])).status_code == 403
    assert (await import_fixture(api, wid, a, ids["episode"], usage_terms=None)).status_code == 422
    r = await import_fixture(api, wid, a, ids["episode"])
    assert r.status_code == 201, r.text
    rep = r.json()

    # 元のファイル（独立に読む）
    src = read_project_file(FIXTURE.read_bytes())
    objects = [o for p in src.pages for o in p.canvas["objects"]]
    assert rep["counts"]["pages"] == len(src.pages) == 4
    assert rep["counts"]["source_objects"] == len(objects)
    # 元の物は1つずつ、ちょうど1回、報告に出る（黙って落とさない）
    seen = sorted((e["page_index"], e["object_index"]) for e in rep["entries"] if e["object_index"] is not None)
    assert seen == sorted((p.index, i) for p in src.pages for i in range(len(p.canvas["objects"])))
    unmapped = [e for e in rep["entries"] if e["status"] == "unmapped"]
    assert [e["source_kind"] for e in unmapped] == ["pen_stroke"] and unmapped[0]["note"]
    assert rep["source_sha256"] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()

    w = await work_json(api, wid, a)
    pages = sorted(live(w["pages"], episode_id=ids["episode"]), key=lambda p: p["number"])
    # 前からあった2ページの後ろに4ページ
    assert [p["number"] for p in pages] == [1, 2, 3, 4, 5, 6] and [p["id"] for p in pages[2:]] == rep["page_ids"]
    new_pages = set(rep["page_ids"])
    panels = [p for p in live(w["panels"]) if p["page_id"] in new_pages]
    assert len(panels) == sum(1 for o in objects if o.get("isPanel"))
    texts = [t for t in live(w["text_items"]) if t["page_id"] in new_pages]
    src_texts = sorted(o["text"] for o in objects if o.get("type") in TEXT_TYPES)
    assert sorted(t["text"] for t in texts) == src_texts
    by_text = {t["text"]: t for t in texts}
    assert by_text["こんにちは"]["writing_direction"] == "vertical" and by_text["Narration"]["item_kind"] == "caption"
    assert by_text["セリフです"]["item_kind"] == "balloon" and by_text["セリフです"]["balloon_shape"]
    # 人が取り込んだので、入れた項目には人の手の印
    assert all(t["human_hand_fields"] for t in texts)
    # 枠の線は今のアプリのコマの線から
    assert all(p["frame_style"] and p["frame_style"]["line_width_mm"] > 0 for p in panels)
    layers = [la for la in live(w["panel_layers"]) if la["page_id"] in new_pages]
    assert [la["role"] for la in layers] == ["tone"]

    async with get_sessionmaker()() as s:
        imgs = (await s.execute(select(ImageFile).where(ImageFile.work_id == wid))).scalars().all()
        settings = (await s.execute(select(ElementGenerationSetting).where(
            ElementGenerationSetting.work_id == wid))).scalars().all()
    src_imgs = {o["src"]: o for o in objects if o.get("type") == "image"}
    page1 = src.pages[1]
    assert sorted(i.sha256 for i in imgs) == sorted(
        hashlib.sha256(data_url_bytes(page1.stored_values[k])).hexdigest() for k in src_imgs)
    assert all(i.origin == "imported" and i.usage_terms["rights_holder"] == TERMS["rights_holder"]
               and FIXTURE.name in i.source_note for i in imgs)
    panel_img = next(p for p in panels if p["image_id"])
    assert next(i for i in imgs if i.id == panel_img["image_id"]).role == "panel_art"
    # AIの設定：コマ・絵のプロンプトと、プロジェクトの基本のプロンプト（元の値もそのまま残す）
    prompts = {(s_.target_kind, s_.prompt) for s_ in settings}
    assert ("panel", "1girl, school uniform, classroom") in prompts
    assert ("image", "image prompt: sunset") in prompts
    assert ("project_base", src.pages[0].base_prompt["text2img_prompt"]) in prompts
    assert all(s_.source_values for s_ in settings)

    got = await api.get(f"/works/{wid}/current-app-imports/{rep['id']}", headers=h(b))
    assert got.status_code == 200 and got.json()["counts"] == rep["counts"]

    # 1回で取り消せる
    r = await api.post(f"/works/{wid}/events/{rep['event_id']}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    w = await work_json(api, wid, a)
    assert [p["number"] for p in live(w["pages"])] == [1, 2]
    assert not [t for t in live(w["text_items"]) if t["page_id"] in new_pages]
    async with get_sessionmaker()() as s:
        assert all(x.removed for x in (await s.execute(select(ElementGenerationSetting).where(
            ElementGenerationSetting.work_id == wid))).scalars())


async def test_人が描いた絵として取り込むと出どころは人(api, image_dir):  # noqa: F811
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    assert (await op(api, wid, a, {"type": "set_work_settings", "page_spec": A4_SPEC})).status_code == 200
    r = await import_fixture(api, wid, a, ids["episode"], image_origin="human_drawn", usage_terms=None)
    assert r.status_code == 201, r.text
    async with get_sessionmaker()() as s:
        imgs = (await s.execute(select(ImageFile).where(ImageFile.work_id == wid))).scalars().all()
    assert imgs and all(i.origin == "human_drawn" and i.registered_by_kind == "human" for i in imgs)
    # 今のアプリのファイルでないものは止める
    r = await api.post(f"/works/{wid}/episodes/{ids['episode']}/current-app-imports", headers=h(a),
                       files={"project": ("x.lz4", b"not a project", "application/octet-stream")},
                       data={"image_origin": "human_drawn"})
    assert r.status_code == 422 and "読めない" in r.text


# ---------------------------------------------------------------- 翻訳


async def text_page(api, a):
    """寸法と言語（ja）を決め、1ページ目に文字が2つある作品を作る（取り込みで作る）。"""
    ids = await new_work(api, a)
    wid = ids["work"]
    assert (await op(api, wid, a, {"type": "set_work_settings", "page_spec": A4_SPEC})).status_code == 200
    r = await import_fixture(api, wid, a, ids["episode"], image_origin="human_drawn", usage_terms=None)
    assert r.status_code == 201, r.text
    texts = live((await work_json(api, wid, a))["text_items"])
    return ids, {t["text"]: t for t in texts}


async def test_翻訳者は訳文だけを変えられ_言語ごとに人の手と判断待ちが分かれる(api, authz, image_dir):  # noqa: F811
    a, tr = user(), user()
    ids, texts = await text_page(api, a)
    wid = ids["work"]
    t = texts["こんにちは"]
    assert (await op(api, wid, a, {"type": "set_member", "user": tr, "role": "translator",
                                   "granted": True})).status_code == 200
    # 作品の言語が決まっていなければ置けない
    r = await op(api, wid, tr, {"type": "set_text_translation", "text_item_id": t["id"], "language": "en",
                                "text": "Hello"})
    assert r.status_code == 422 and "preferences.language" in r.text
    assert (await op(api, wid, a, {"type": "set_work_settings", "preferences": {"language": "ja"}})).status_code == 200
    # 元の言語には置けない
    r = await op(api, wid, tr, {"type": "set_text_translation", "text_item_id": t["id"], "language": "ja",
                                "text": "x"})
    assert r.status_code == 422
    for lang, text in (("en", "Hello"), ("zh-Hans", "你好")):
        r = await op(api, wid, tr, {"type": "set_text_translation", "text_item_id": t["id"], "language": lang,
                                    "text": text})
        assert r.status_code == 200, r.text
    # 翻訳者は元の文字・位置を変えられない（ページの can_draw が無い）
    r = await op(api, wid, tr, {"type": "update_text_item", "id": t["id"], "text": "変えた"})
    assert r.status_code == 403
    # 編集・見る人は訳文を置けない
    v = user()
    assert (await op(api, wid, a, {"type": "set_member", "user": v, "role": "viewer", "granted": True})).status_code == 200
    r = await op(api, wid, v, {"type": "set_text_translation", "text_item_id": t["id"], "language": "en", "text": "x"})
    assert r.status_code == 403

    got = (await api.get(f"/works/{wid}/translations", params={"language": "en"}, headers=h(tr))).json()
    assert got["source_language"] == "ja"
    (row_en,) = got["translations"]
    assert row_en["text"] == "Hello" and row_en["source_text"] == "こんにちは" and row_en["human_hand_fields"] == ["text"]
    assert len(got["missing_text_item_ids"]) == len(texts) - 1

    # AI（機械の翻訳）が人の置いた en に当たると判断待ち。印の無い言語（AIが置いた fr）は変えられる
    await allow_ai(api, wid, a, "translation")
    ev = await ai_op(authz, wid, a, {"type": "set_text_translation", "text_item_id": t["id"], "language": "en",
                                    "text": "Hi (AI)"})
    assert len(ev.held_changes) == 1 and ev.held_changes[0]["target_table"] == "text_item_translations"
    await ai_op(authz, wid, a, {"type": "set_text_translation", "text_item_id": t["id"], "language": "fr",
                               "text": "Bonjour"})
    ev2 = await ai_op(authz, wid, a, {"type": "set_text_translation", "text_item_id": t["id"], "language": "fr",
                                     "text": "Salut"})
    assert not ev2.held_changes
    got = (await api.get(f"/works/{wid}/translations", params={"language": "en"}, headers=h(tr))).json()
    assert got["translations"][0]["text"] == "Hello"
    fr = (await api.get(f"/works/{wid}/translations", params={"language": "fr"}, headers=h(tr))).json()
    assert fr["translations"][0]["text"] == "Salut" and fr["translations"][0]["human_hand_fields"] == []
    # 翻訳者が判断待ちを採る
    r = await op(api, wid, tr, {"type": "resolve_held_change", "id": ev.held_changes[0]["id"], "decision": "accept"})
    assert r.status_code == 200, r.text
    got = (await api.get(f"/works/{wid}/translations", params={"language": "en"}, headers=h(tr))).json()
    assert got["translations"][0]["text"] == "Hi (AI)"
    # 訳文を変える操作は取り消せる
    r = await op(api, wid, tr, {"type": "set_text_translation", "text_item_id": t["id"], "language": "zh-Hans",
                                "text": "您好"})
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(tr))).status_code == 200
    zh = (await api.get(f"/works/{wid}/translations", params={"language": "zh-Hans"}, headers=h(tr))).json()
    assert zh["translations"][0]["text"] == "你好"


@pytest.mark.skipif(not pathlib.Path("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf").exists(),
                    reason="試験の書体が無い")
async def test_言語ごとに書き出す_訳文が足りなければ止める(api, workers, export_env):  # noqa: F811
    a = user()
    ids, p, t = await ready_page(api, a)
    wid = ids["work"]
    assert (await op(api, wid, a, {"type": "set_work_settings",
                                   "preferences": {"frame_style": FRAME_STYLE, "language": "ja"}})).status_code == 200

    async def export(**kw):
        r = await api.post(f"/works/{wid}/exports", headers=h(a),
                           json={"format": "png", "page_ids": [ids["page1"]], "dpi": 40} | kw)
        return r

    r = await export(language="en")
    assert r.status_code == 422 and t["id"] in r.text
    assert (await export(language="en", format="psd")).status_code == 422
    r = await op(api, wid, a, {"type": "set_text_translation", "text_item_id": t["id"], "language": "en",
                               "text": "WOW", "writing_direction": "horizontal"})
    assert r.status_code == 200, r.text

    async def finished(rid):
        async def done():
            got = (await api.get(f"/works/{wid}/exports/{rid}", headers=h(a))).json()
            return got if got["status"] in ("done", "failed") else None
        return await wait_for(done, timeout=60)

    runs = {}
    for lang in ("ja", "en"):
        r = await export(language=lang)
        assert r.status_code == 201, r.text
        runs[lang] = await finished(r.json()["id"])
        assert runs[lang]["status"] == "done", runs[lang]["detail"]
        assert runs[lang]["language"] == lang

    def pixels(run):
        return api.get(f"/works/{wid}/exports/{run['id']}/files/{run['outputs'][0]['file']}", headers=h(a))

    ja = Image.open(io.BytesIO((await pixels(runs["ja"])).content))
    en = Image.open(io.BytesIO((await pixels(runs["en"])).content))
    assert ja.size == en.size and ja.tobytes() != en.tobytes()
    # 元の文字の行は変わっていない
    (row,) = [x for x in live((await work_json(api, wid, a))["text_items"]) if x["id"] == t["id"]]
    assert row["text"] == "あ"


# ---------------------------------------------------------------- 確認の状態と進み具合


async def test_確認の状態は役で分かれ_コメントと記録が残り_進み具合に出る(api, authz):
    a, ed, asst, cl = user(), user(), user(), user()
    ids = await new_work(api, a)
    wid, p1, p2 = ids["work"], ids["page1"], ids["page2"]
    for u, role in ((ed, "editor"), (asst, "assistant"), (cl, "client")):
        assert (await op(api, wid, a, {"type": "set_member", "user": u, "role": role, "granted": True})).status_code == 200
    assert (await op(api, wid, a, {"type": "assign_page", "page_id": p1, "user": asst,
                                   "assigned": True})).status_code == 200

    def st(u, target, status, kind="page", **kw):
        return op(api, wid, u, {"type": "set_review_status", "target_kind": kind, "target_id": target,
                                "status": status, **kw})

    # 下書きから承認へは飛べない
    assert (await st(a, p1, "approved")).status_code == 422
    # 割り当てのない人・依頼主はページを出せない。割り当てられたアシスタントは出せる
    assert (await st(cl, p1, "in_review")).status_code == 403
    r = await st(asst, p1, "in_review", comment="見てください")
    assert r.status_code == 200, r.text
    # アシスタントは承認できない。編集は承認・直しの依頼ができる。直しの依頼にはコメントが要る
    assert (await st(asst, p1, "approved")).status_code == 403
    assert (await st(ed, p1, "needs_changes")).status_code == 422
    assert (await st(ed, p1, "needs_changes", comment="3コマ目の表情")).status_code == 200
    assert (await st(asst, p1, "in_review")).status_code == 200
    r = await st(ed, p1, "approved", comment="OK")
    assert r.status_code == 200
    # 承認の取り消しは承認できる人だけ
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(asst))).status_code == 403
    u2 = await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(ed))
    assert u2.status_code == 200, u2.text
    # 取り消しの取り消し（承認し直し）
    assert (await api.post(f"/works/{wid}/events/{u2.json()['event_id']}/undo", headers=h(ed))).status_code == 200
    # 作品の状態：出すのは作者、決めるのは作者・編集
    assert (await st(ed, wid, "in_review", kind="work")).status_code == 403
    assert (await st(a, wid, "in_review", kind="work")).status_code == 200

    recs = (await api.get(f"/works/{wid}/review-records", params={"target_id": p1}, headers=h(cl))).json()
    assert [(x["from_status"], x["to_status"]) for x in recs] == [
        ("draft", "in_review"), ("in_review", "needs_changes"), ("needs_changes", "in_review"),
        ("in_review", "approved"), ("approved", "in_review"), ("in_review", "approved")]
    assert recs[1]["comment"] == "3コマ目の表情" and recs[4]["reverts_record_id"] == recs[3]["id"]

    # 進み具合：締切を過去にすると、承認していない2ページ目は間に合わない
    deadline = datetime.now(UTC) + timedelta(days=-1)
    assert (await op(api, wid, a, {"type": "update_episode", "id": ids["episode"],
                                   "deadline": deadline.isoformat()})).status_code == 200
    assert (await st(a, p2, "in_review")).status_code == 200
    prog = (await api.get(f"/works/{wid}/progress", headers=h(cl))).json()
    assert prog["work_status"] == "in_review" and prog["approved_pages_in_work"] == 1
    (ep,) = prog["episodes"]
    assert ep["pages_by_status"] == {"draft": 0, "in_review": 1, "approved": 1, "needs_changes": 0}
    assert ep["pending_review_page_ids"] == [p2] and ep["overdue"] is True
    est = ep["estimate"]
    assert est["on_track"] is False and est["late_page_ids"] == [p2] and "未検証" in est["note"]
    assert est["per_page_seconds"] > 0


async def test_承認したページが無ければ見込みを出さない(api):
    a = user()
    ids = await new_work(api, a)
    prog = (await api.get(f"/works/{ids['work']}/progress", headers=h(a))).json()
    est = prog["episodes"][0]["estimate"]
    assert est["projected_finish"] is None and est["reason"]
    assert prog["episodes"][0]["pages_by_status"]["draft"] == 2


async def test_AIは確認の状態を変えられない(api, authz):
    a = user()
    ids = await new_work(api, a)
    with pytest.raises(Forbidden):
        await ai_op(authz, ids["work"], a, {"type": "set_review_status", "target_kind": "page",
                                            "target_id": ids["page1"], "status": "in_review"})
