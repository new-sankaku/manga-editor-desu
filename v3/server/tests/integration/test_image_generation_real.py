"""画像生成の処理を、本物の ComfyUI（CPU でよい）に、頼む口から通す試験。V3_TEST_COMFYUI_URL が無ければ飛ばす。

モデルは Stable Diffusion 1.5 を分けた3つ（test_comfyui_real.py と同じ名前）。絵は 128px 前後・2手（CPU で1枚30秒ほど）。
確かめること
- 囲んで直す：人の手の範囲の画素と、囲んだ範囲の外の画素が、元の絵と1つも変わらない。囲んだ所は変わる
- 描き足す：広げた大きさで返り、元の絵の所（ぼかしの幅より内側）と人の手の範囲は変わらない
- 絵から作り直す・文から作る：動いて登録される
"""
import base64
import io
import os
import uuid

import numpy as np
import pytest
from conftest import h, new_work, user, wait_for
from PIL import Image
from test_human_ai_interchange import op
from test_queue import admin  # noqa: F401  (fixture)

from v3server.generation_queue.image_process_registry import SPECS, describe
from v3server.server_settings import get_settings

URL = os.environ.get("V3_TEST_COMFYUI_URL")
pytestmark = pytest.mark.skipif(URL is None, reason="V3_TEST_COMFYUI_URL が無い")

SD15 = {"model": {"kind": "separate", "unet_name": "sd15_unet_fp16.safetensors", "weight_dtype": "default",
                  "clip_name": "sd15_te_fp16.safetensors", "clip_type": "stable_diffusion",
                  "vae_name": "sd15_vae_fp16.safetensors"},
        "loras": [], "sampler": {"steps": 2, "cfg": 7, "sampler_name": "euler", "scheduler": "normal"},
        "native_long_side": 128, "controlnet_name": None}


def initial(name):
    props = describe(SPECS[name])["params_schema"]["properties"]
    return {k: v["x-initial"] for k, v in props.items() if "x-initial" in v}


def source_png(w, h_) -> bytes:
    rng = np.random.default_rng(0)
    a = rng.integers(0, 256, (h_, w, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, format="PNG")
    return buf.getvalue()


def arr(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).astype(int)


@pytest.fixture
async def real(api, admin, workers, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))
    r = await api.post("/services", headers=h(admin), json={
        "name": f"comfy-real-{uuid.uuid4().hex[:6]}", "kind": "image", "location": "local", "adapter": "comfyui",
        "endpoint": URL, "send_mode": "serial"})
    sid = r.json()["id"]
    for name in ("text_to_image", "image_to_image", "inpaint", "outpaint"):
        assert (await api.put(f"/services/{sid}/processes/{name}", headers=h(admin), json={
            "comfy_graph_settings": SD15, "comfy_wait_seconds": 600, "comfy_check_choices": True})).status_code == 200
        assert (await api.put(f"/routes/{name}", headers=h(admin), json={
            "service_id": sid, "resend_limit": 0, "regenerate_limit": 0, "ai_task": "drawing",
            "ai_action": "propose"})).status_code == 200
    await workers.reload()
    a = user()
    ids = await new_work(api, a)
    wid, pid = ids["work"], uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1, "frame": {
        "polygon_mm": [[0, 0], [50, 0], [50, 38], [0, 38]], "bleeds": False}})).status_code == 200
    data = source_png(100, 76)  # 8 の倍数でない大きさ（拡大縮小して戻す道を通す）
    r = await api.post(f"/works/{wid}/panels/{pid}/image", headers=h(a),
                       files={"image": ("a.png", data, "image/png")}, data={"origin": "human_drawn"})
    img = r.json()["id"]
    assert (await op(api, wid, a, {"type": "update_panel", "id": pid, "image_placement": {
        "crop_px": [0, 0, 100, 76], "dest_box_mm": [0, 0, 50, 38]}})).status_code == 200
    assert (await op(api, wid, a, {"type": "add_protected_region", "image_id": img,
                                   "polygon_px": [[30, 20], [50, 20], [50, 40], [30, 40]]})).status_code == 200
    return {"a": a, "wid": wid, "pid": pid, "img": img, "src": data}


async def run(api, s, body) -> dict:
    r = await api.post(f"/works/{s['wid']}/panels/{s['pid']}/generate", headers=h(s["a"]),
                       json={"count": 1, "seed_mode": "fixed", "seed": 3, **body})
    assert r.status_code == 201, r.text
    set_id = r.json()["candidate_set_id"]

    async def done():
        res = (await api.get(f"/works/{s['wid']}/panels/{s['pid']}/candidates", headers=h(s["a"]))).json()
        st = next(x for x in res["sets"] if x["candidate_set_id"] == set_id)
        if st["jobs"][0]["status"] == "stopped":
            raise AssertionError(st["jobs"][0])
        return st["images"][0] if st["images"] else None
    img = await wait_for(done, timeout=900, interval=2)
    img["bytes"] = (await api.get(f"/works/{s['wid']}/images/{img['id']}/file", headers=h(s["a"]))).content
    return img


async def test_囲んで直すは人の範囲と囲んだ外の画素を変えない(api, real):
    s = real
    mask = Image.new("L", (100, 76), 0)
    mask.paste(255, (20, 10, 70, 60))  # 人の範囲（30..50, 20..40）を囲みに含める
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    for only_masked in (False, True):
        img = await run(api, s, {"process": "inpaint", "source_image_id": s["img"],
                                 "params": {**initial("inpaint"), "prompt": "a cat", "only_masked": only_masked,
                                            "padding_px": 8},
                                 "mask": {"png_base64": base64.b64encode(buf.getvalue()).decode()}})
        out, src = arr(img["bytes"]), arr(s["src"])
        assert out.shape == src.shape
        assert (out[20:40, 30:50] == src[20:40, 30:50]).all(), "人の手の範囲の画素が変わった"
        grow, feather = initial("inpaint")["grow_px"], initial("inpaint")["feather_px"]
        reach = grow + feather + 2
        outside = np.ones(src.shape[:2], bool)
        outside[max(0, 10 - reach):60 + reach, max(0, 20 - reach):70 + reach] = False
        assert (out[outside] == src[outside]).all(), "囲んだ範囲の外の画素が変わった"
        inside = np.zeros(src.shape[:2], bool)
        inside[12:58, 22:68] = True
        inside[20:40, 30:50] = False
        assert np.abs(out[inside] - src[inside]).mean() > 5, "囲んだ所が描き直されていない"


async def test_描き足すは広げた大きさで返り_元の所と人の範囲を変えない(api, real):
    s = real
    img = await run(api, s, {"process": "outpaint", "source_image_id": s["img"],
                             "params": {**initial("outpaint"), "unit": "px", "left": 28, "bottom": 20,
                                        "prompt": "sky", "feather_px": 8}})
    out, src = arr(img["bytes"]), arr(s["src"])
    assert out.shape == (96, 128, 3)
    assert img["details"]["geometry"] == {"scale": [1, 1], "offset": [28, 0]}
    assert (out[20:40, 58:78] == src[20:40, 30:50]).all(), "人の手の範囲の画素が変わった"
    # 広げた辺（左・下）からぼかしの幅より内側の元の絵は変わらない
    assert (out[0:76 - 9, 28 + 9:128] == src[0:76 - 9, 9:100]).all()
    assert np.abs(out[:, :20].astype(int) - 128).mean() > 0  # 広げた所が描かれている
    r = await op(api, s["wid"], s["a"], {"type": "adopt_image", "panel_id": s["pid"], "image_id": img["id"]})
    assert r.status_code == 200, r.text


async def test_絵から作り直す_文から作る(api, real):
    s = real
    img = await run(api, s, {"process": "image_to_image", "source_image_id": s["img"],
                             "params": {**initial("image_to_image"), "prompt": "a dog", "strength": 0.5}})
    out, src = arr(img["bytes"]), arr(s["src"])
    assert out.shape == src.shape and (out[20:40, 30:50] == src[20:40, 30:50]).all()
    img = await run(api, s, {"process": "text_to_image",
                             "params": {**initial("text_to_image"), "prompt": "a dog", "width": 128, "height": 96}})
    assert arr(img["bytes"]).shape == (96, 128, 3)
