"""画像生成の画面の口（http_routes/image_generation_routes.py）を、頼む → 偽の ComfyUI → 候補 → 採る → 取り消す まで通す。
ComfyUI は偽（httpx.MockTransport）。上げられた元の絵（描き足すでは広げた絵）を、色を変えて出来上がりとして返す。
Temporal・PostgreSQL・OpenFGA は実際に使う。本物の ComfyUI の試験は test_image_generation_real.py。"""
import base64
import io
import json
import uuid

import httpx
import numpy as np
import pytest
from conftest import h, new_work, user, wait_for
from PIL import Image, PngImagePlugin
from test_comfyui_pipeline import fake_comfy  # noqa: F401  (fixture)
from test_human_ai_interchange import ai_op, op, work_json
from test_queue import admin  # noqa: F401  (fixture)

from v3server.generation_queue.image_process_registry import SPECS, describe

SD = {"model": {"kind": "separate", "unet_name": "u.safetensors", "weight_dtype": "default", "clip_name": "c.safetensors",
                "clip_type": "stable_diffusion", "vae_name": "v.safetensors"},
      "loras": [], "sampler": {"steps": 4, "cfg": 7, "sampler_name": "euler", "scheduler": "normal"},
      "native_long_side": 512, "controlnet_name": None}
FRAME = {"polygon_mm": [[0, 0], [40, 0], [40, 20], [0, 20]], "bleeds": False}


def initial(name):
    props = describe(SPECS[name])["params_schema"]["properties"]
    return {k: v["x-initial"] for k, v in props.items() if "x-initial" in v}


def png(w=64, h_=32, color=(200, 200, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h_), color).save(buf, format="PNG")
    return buf.getvalue()


class EchoComfy:
    """上げられた source を、赤くして返す。PNG には ComfyUI と同じく指示と手順を書き込む。"""

    def __init__(self):
        self.uploads: dict[str, bytes] = {}
        self.prompts: list[dict] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/upload/image":
            body = req.read()
            name = body.split(b'filename="', 1)[1].split(b'"', 1)[0].decode()
            start = body.index(b"\x89PNG")
            self.uploads[name] = body[start:body.index(b"IEND", start) + 8]
            return httpx.Response(200, json={"name": name, "subfolder": "", "type": "input"})
        if path == "/prompt":
            self.prompts.append(json.loads(req.content)["prompt"])
            return httpx.Response(200, json={"prompt_id": f"p{len(self.prompts)}"})
        if path.startswith("/history/"):
            pid = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={pid: {"status": {"status_str": "success", "messages": []}, "outputs": {
                "9": {"images": [{"filename": pid, "subfolder": "", "type": "output"}]}}}})
        if path == "/view":
            prompt = self.prompts[int(req.url.params["filename"][1:]) - 1]
            if "source" in prompt:
                im = Image.open(io.BytesIO(self.uploads[prompt["source"]["inputs"]["image"]])).convert("RGB")
            else:
                lat = next(n for n in prompt.values() if n["class_type"] == "EmptyLatentImage")["inputs"]
                im = Image.new("RGB", (lat["width"], lat["height"]))
            a = np.asarray(im).copy()
            a[:, :, 0] = 255
            info = PngImagePlugin.PngInfo()
            info.add_text("prompt", json.dumps(prompt))
            buf = io.BytesIO()
            Image.fromarray(a).save(buf, format="PNG", pnginfo=info)
            return httpx.Response(200, content=buf.getvalue())
        return httpx.Response(404)


@pytest.fixture
async def setup(api, admin, workers, fake_comfy):  # noqa: F811
    comfy = fake_comfy(EchoComfy())
    r = await api.post("/services", headers=h(admin), json={
        "name": f"comfy-{uuid.uuid4().hex[:6]}", "kind": "image", "location": "local", "adapter": "comfyui",
        "endpoint": "http://comfy", "send_mode": "parallel", "max_concurrency": 4})
    sid = r.json()["id"]
    for name in ("text_to_image", "image_to_image", "variation", "inpaint", "outpaint"):
        r = await api.put(f"/services/{sid}/processes/{name}", headers=h(admin), json={
            "comfy_graph_settings": SD, "comfy_wait_seconds": 30})
        assert r.status_code == 200, r.text
        r = await api.put(f"/routes/{name}", headers=h(admin), json={
            "service_id": sid, "resend_limit": 0, "regenerate_limit": 0, "ai_task": "drawing", "ai_action": "propose"})
        assert r.status_code == 200, r.text
    await workers.reload()
    a = user()
    ids = await new_work(api, a)
    wid, pid = ids["work"], uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1,
                                   "frame": FRAME})).status_code == 200
    r = await api.post(f"/works/{wid}/panels/{pid}/image", headers=h(a),
                       files={"image": ("a.png", png(), "image/png")}, data={"origin": "human_drawn"})
    img = r.json()["id"]
    place = {"crop_px": [0, 0, 64, 32], "dest_box_mm": [0, 0, 40, 20]}
    assert (await op(api, wid, a, {"type": "update_panel", "id": pid, "image_placement": place})).status_code == 200
    return {"a": a, "wid": wid, "pid": pid, "img": img, "sid": sid, "comfy": comfy, "page": ids["page1"]}


async def generated(api, s, set_id, n):
    async def done():
        r = (await api.get(f"/works/{s['wid']}/panels/{s['pid']}/candidates", headers=h(s["a"]))).json()
        st = next(x for x in r["sets"] if x["candidate_set_id"] == set_id)
        if any(j["status"] == "stopped" for j in st["jobs"]):
            raise AssertionError(st["jobs"])
        return st if len(st["images"]) == n else None
    return await wait_for(done, timeout=60)


async def test_処理の一覧は入力欄の形と送り先を返す(api, setup):
    s = setup
    r = (await api.get(f"/works/{s['wid']}/image-processes", headers=h(s["a"]))).json()
    by = {p["name"]: p for p in r}
    assert set(by) == set(SPECS)
    inp = by["inpaint"]
    assert inp["canvas_tool"] == "mask" and inp["params_schema"]["properties"]["denoise"]["x-initial"] == 0.75
    assert inp["route_service_id"] == s["sid"]
    svc = next(x for x in inp["services"] if x["service_id"] == s["sid"])
    assert svc["allowed"] and svc["settings"]["model"] == "u.safetensors"
    works = (await api.get("/works", headers=h(s["a"]))).json()
    assert s["wid"] in [w["id"] for w in works]
    assert s["wid"] not in [w["id"] for w in (await api.get("/works", headers=h(user()))).json()]


async def test_囲んで直すの候補を採り_取り消し_却下する(api, setup):
    s = setup
    a, wid, pid = s["a"], s["wid"], s["pid"]
    # 人の手の範囲（左上）
    assert (await op(api, wid, a, {"type": "add_protected_region", "image_id": s["img"],
                                   "polygon_px": [[0, 0], [16, 0], [16, 16], [0, 16]]})).status_code == 200
    mask = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    mask.paste((255, 255, 255, 255), (8, 8, 40, 24))
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    r = await api.post(f"/works/{wid}/panels/{pid}/generate", headers=h(a), json={
        "process": "inpaint", "params": {**initial("inpaint"), "prompt": "空"}, "count": 2, "seed_mode": "fixed",
        "seed": 10, "source_image_id": s["img"], "mask": {"png_base64": base64.b64encode(buf.getvalue()).decode()}})
    assert r.status_code == 201, r.text
    set_id = r.json()["candidate_set_id"]
    st = await generated(api, s, set_id, 2)
    assert sorted(i["seed"] for i in st["images"]) == [10, 11]
    cand = st["images"][0]
    d = cand["details"]
    assert d["process"] == "inpaint" and d["candidate_set_id"] == set_id and d["service_id"] == s["sid"]
    assert d["params"]["prompt"] == "空" and d["geometry"] == {"scale": [1, 1], "offset": [0, 0]}
    assert cand["based_on_image_id"] == s["img"] and cand["service_name"] and cand["settings"]["model"]
    assert cand["protected_mask_url"]
    pm = Image.open(io.BytesIO((await api.get(cand["protected_mask_url"], headers=h(a))).content)).convert("L")
    assert pm.getpixel((4, 4)) == 255 and pm.getpixel((30, 4)) == 0
    # 送った描き直す範囲から、人の範囲が引かれている
    prompt = s["comfy"].prompts[-1]
    redraw = Image.open(io.BytesIO(s["comfy"].uploads[prompt["redraw_mask"]["inputs"]["image"]])).convert("L")
    assert redraw.getpixel((10, 10)) == 0 and redraw.getpixel((30, 16)) == 255
    assert set(redraw.getdata()) <= {0, 255}  # 描くときは白黒。重ねるときのマスクはぼかしたまま別に送る
    blend = Image.open(io.BytesIO(s["comfy"].uploads[prompt["blend_mask"]["inputs"]["image"]])).convert("L")
    assert blend.getpixel((10, 10)) == 0 and blend.getpixel((30, 16)) == 255
    # ComfyUI が書いた指示は、置いた絵に残らない
    file = Image.open(io.BytesIO((await api.get(f"/works/{wid}/images/{cand['id']}/file", headers=h(a))).content))
    assert "prompt" not in getattr(file, "text", {})
    thumb = Image.open(io.BytesIO((await api.get(f"/works/{wid}/images/{cand['id']}/thumbnail", headers=h(a),
                                                 params={"size": 32})).content))
    assert max(thumb.size) == 32

    # 採る → 取り消す
    r = await op(api, wid, a, {"type": "adopt_image", "panel_id": pid, "image_id": cand["id"]})
    assert r.status_code == 200, r.text
    panel = next(p for p in (await work_json(api, wid, a))["panels"] if p["id"] == pid)
    assert panel["image_id"] == cand["id"] and panel["image_placement"]["crop_px"] == [0, 0, 64, 32]
    vers = (await api.get(f"/works/{wid}/panels/{pid}/versions", headers=h(a))).json()
    assert [v["id"] for v in vers["versions"]] == [s["img"], cand["id"]] and vers["versions"][1]["current"]
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))).status_code == 200
    panel = next(p for p in (await work_json(api, wid, a))["panels"] if p["id"] == pid)
    assert panel["image_id"] == s["img"]
    # 前の版に戻すのも同じ操作
    other = st["images"][1]["id"]
    assert (await op(api, wid, a, {"type": "adopt_image", "panel_id": pid, "image_id": other})).status_code == 200
    assert (await op(api, wid, a, {"type": "adopt_image", "panel_id": pid, "image_id": s["img"]})).status_code == 200
    # 却下（使っている絵は却下できない）
    assert (await op(api, wid, a, {"type": "set_image_discarded", "image_id": s["img"], "discarded": True})).status_code == 422
    r = await op(api, wid, a, {"type": "set_image_discarded", "image_id": cand["id"], "discarded": True})
    assert r.status_code == 200, r.text
    st = next(x for x in (await api.get(f"/works/{wid}/panels/{pid}/candidates", headers=h(a))).json()["sets"]
              if x["candidate_set_id"] == set_id)
    assert next(i for i in st["images"] if i["id"] == cand["id"])["discarded"] is True
    assert (await op(api, wid, a, {"type": "adopt_image", "panel_id": pid, "image_id": cand["id"]})).status_code == 422
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))).status_code == 200


async def test_描き足すは置き場を広げて見えていた所を同じ位置に残す(api, setup):
    s = setup
    a, wid, pid = s["a"], s["wid"], s["pid"]
    r = await api.post(f"/works/{wid}/panels/{pid}/generate", headers=h(a), json={
        "process": "outpaint", "params": {**initial("outpaint"), "unit": "mm", "left": 5, "bottom": 2.5},
        "count": 1, "seed_mode": "random", "source_image_id": s["img"]})
    assert r.status_code == 201, r.text
    st = await generated(api, s, r.json()["candidate_set_id"], 1)
    assert st["requested_params"]["unit"] == "mm" and st["params"]["unit"] == "px"
    cand = st["images"][0]
    assert (cand["width"], cand["height"]) == (72, 36)  # 1.6 px / mm で左8、下4
    assert cand["details"]["geometry"] == {"scale": [1, 1], "offset": [8, 0]}
    r = await op(api, wid, a, {"type": "adopt_image", "panel_id": pid, "image_id": cand["id"]})
    assert r.status_code == 200, r.text
    pl = next(p for p in (await work_json(api, wid, a))["panels"] if p["id"] == pid)["image_placement"]
    assert pl["crop_px"] == [0, 0, 72, 36]
    assert pl["dest_box_mm"] == pytest.approx([-5, 0, 40, 22.5])
    # 元の絵に戻すと、置き場も戻る
    assert (await op(api, wid, a, {"type": "adopt_image", "panel_id": pid, "image_id": s["img"]})).status_code == 200
    pl = next(p for p in (await work_json(api, wid, a))["panels"] if p["id"] == pid)["image_placement"]
    assert pl["crop_px"] == [0, 0, 64, 32] and pl["dest_box_mm"] == pytest.approx([0, 0, 40, 20])


async def test_文から作るは元の絵なしで_コマの枠を覆うように置く(api, setup):
    s = setup
    a, wid, pid = s["a"], s["wid"], s["pid"]
    r = await api.post(f"/works/{wid}/panels/{pid}/generate", headers=h(a), json={
        "process": "text_to_image", "params": {**initial("text_to_image"), "width": 64, "height": 64},
        "count": 1, "seed_mode": "random"})
    assert r.status_code == 201, r.text
    cand = (await generated(api, s, r.json()["candidate_set_id"], 1))["images"][0]
    assert cand["details"]["geometry"] is None and cand["based_on_image_id"] is None
    assert (await op(api, wid, a, {"type": "adopt_image", "panel_id": pid, "image_id": cand["id"]})).status_code == 200
    pl = next(p for p in (await work_json(api, wid, a))["panels"] if p["id"] == pid)["image_placement"]
    assert pl["crop_px"] == [0, 0, 64, 64] and pl["dest_box_mm"] == pytest.approx([0, -10, 40, 30])


async def test_頼むときの誤りは送る前に断る(api, setup):
    s = setup
    a, wid, pid = s["a"], s["wid"], s["pid"]
    base = {"count": 1, "seed_mode": "random", "source_image_id": s["img"]}
    bad = [
        {"process": "inpaint", "params": initial("inpaint")},  # 範囲が無い
        {"process": "image_to_image", "params": {**initial("image_to_image"), "strength": 2}},
        {"process": "nothing", "params": {}},
        {"process": "image_to_image", "params": initial("image_to_image"), "seed_mode": "fixed"},
        {"process": "text_to_image", "params": initial("text_to_image")},  # 元の絵を受けない
        {"process": "image_to_image", "params": initial("image_to_image"), "service_id": uuid.uuid4().hex},
    ]
    for b in bad:
        r = await api.post(f"/works/{wid}/panels/{pid}/generate", headers=h(a), json={**base, **b})
        assert r.status_code in (404, 422), (b, r.text)
    assert (await api.post(f"/works/{wid}/panels/{pid}/generate", headers=h(user()), json={
        **base, "process": "image_to_image", "params": initial("image_to_image")})).status_code == 403


async def test_AIは候補を採れない(api, authz, setup):
    s = setup
    with pytest.raises(Exception, match="adopt_image|AI"):
        await ai_op(authz, s["wid"], s["a"], {"type": "adopt_image", "panel_id": s["pid"], "image_id": s["img"]})
