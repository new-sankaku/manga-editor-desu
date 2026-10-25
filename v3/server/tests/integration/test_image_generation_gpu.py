"""画像生成の処理を、GPU の本物の ComfyUI に、頼む口から通す試験。V3_TEST_COMFYUI_GPU_URL が無ければ飛ばす。

絵のモデルは SDXL（Illustrious 系の checkpoint）、形の指定は xinsir の union promax、指示で直すは Qwen-Image 2.1
（llm_doc/V3検証の環境.md の「画像生成」に書いたモデル。名前が ComfyUI に無ければ飛ばす）。
test_image_generation_real.py（CPU・SD1.5・128px）と同じことを、実際の大きさの絵で確かめ、
まだ実機で流していなかった指示で直す・形の指定（線画・骨格）も流す。
出来た絵は V3_TEST_GPU_OUT のフォルダに残す（目で見るため。無ければ試験の一時フォルダ）。
"""
import base64
import io
import os
import pathlib
import uuid

import httpx
import numpy as np
import pytest
from conftest import h, new_work, user, wait_for
from PIL import Image, ImageDraw
from test_human_ai_interchange import op
from test_queue import admin  # noqa: F401  (fixture)

from v3server.comfy_graphs.pose_skeleton_image import FigureBox, draw_standing_pose
from v3server.generation_queue.image_process_registry import SPECS, describe
from v3server.server_settings import get_settings

URL = os.environ.get("V3_TEST_COMFYUI_GPU_URL")
pytestmark = pytest.mark.skipif(URL is None, reason="V3_TEST_COMFYUI_GPU_URL が無い")

CHECKPOINT = "illustrious\\waiIllustriousSDXL_v160.safetensors"
CONTROLNET = "xinsir\\union-sdxl-1.0-promax.safetensors"
SDXL = {"model": {"kind": "checkpoint", "checkpoint_name": CHECKPOINT}, "loras": [],
        "sampler": {"steps": 25, "cfg": 6, "sampler_name": "euler_ancestral", "scheduler": "normal"},
        "native_long_side": 1024, "controlnet_name": CONTROLNET}
# p26 の値（comfy_graphs/instruction_edit_graph.py の EditSettings の説明）
QWEN = {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default",
        "clip_name": "qwen3vl_8b_int8_convrot.safetensors", "clip_type": "qwen_image",
        "vae_name": "qwen_image_2.1_vae_bf16.safetensors", "loras": [], "resolution": 1024,
        "cache_device": "auto", "cache_dtype": "default",
        "sampler": {"steps": 25, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"}}
PROMPT = "masterpiece, best quality, 1girl, school uniform, standing, classroom, looking at viewer"
W, H = 768, 1024
PROTECTED = (300, 200, 460, 360)  # x0, y0, x1, y1


def initial(name):
    props = describe(SPECS[name])["params_schema"]["properties"]
    return {k: v["x-initial"] for k, v in props.items() if "x-initial" in v}


def arr(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).astype(int)


def png_b64(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture(scope="module", autouse=True)
def models_present():
    def names(node, key):
        try:
            return httpx.get(f"{URL}/object_info/{node}", timeout=30).json()[node]["input"]["required"][key][0]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            pytest.skip(f"ComfyUI に届かない: {e!r}")
    if CHECKPOINT not in names("CheckpointLoaderSimple", "ckpt_name"):
        pytest.skip("SDXL の checkpoint が ComfyUI に入っていない")
    if CONTROLNET not in names("ControlNetLoader", "control_net_name"):
        pytest.skip("ControlNet の union promax が ComfyUI に入っていない")
    if QWEN["unet_name"] not in names("UNETLoader", "unet_name"):
        pytest.skip("Qwen-Image 2.1 が ComfyUI に入っていない")


@pytest.fixture
def out_dir(tmp_path) -> pathlib.Path:
    d = pathlib.Path(os.environ.get("V3_TEST_GPU_OUT", tmp_path / "out"))
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
async def gpu(api, admin, workers, monkeypatch, tmp_path, out_dir):  # noqa: F811
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))
    r = await api.post("/services", headers=h(admin), json={
        "name": f"comfy-gpu-{uuid.uuid4().hex[:6]}", "kind": "image", "location": "local", "adapter": "comfyui",
        "endpoint": URL, "send_mode": "serial"})
    sid = r.json()["id"]
    for name in ("text_to_image", "image_to_image", "inpaint", "outpaint", "instruction_edit"):
        settings = QWEN if name == "instruction_edit" else SDXL
        assert (await api.put(f"/services/{sid}/processes/{name}", headers=h(admin), json={
            "comfy_graph_settings": settings, "comfy_wait_seconds": 900,
            "comfy_check_choices": True})).status_code == 200
        assert (await api.put(f"/routes/{name}", headers=h(admin), json={
            "service_id": sid, "resend_limit": 0, "regenerate_limit": 0, "ai_task": "drawing",
            "ai_action": "propose"})).status_code == 200
    await workers.reload()
    a = user()
    ids = await new_work(api, a)
    wid, pid = ids["work"], uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1, "frame": {
        "polygon_mm": [[0, 0], [60, 0], [60, 80], [0, 80]], "bleeds": False}})).status_code == 200
    s = {"a": a, "wid": wid, "pid": pid, "out": out_dir}
    # 元の絵は SDXL で作り、人が描いた絵として載せ直す（手動編集の範囲を付けるため）
    t2i = await run(api, s, "source", {"process": "text_to_image", "params": {
        **initial("text_to_image"), "prompt": PROMPT, "width": W, "height": H}})
    data = t2i["bytes"]
    r = await api.post(f"/works/{wid}/panels/{pid}/image", headers=h(a),
                       files={"image": ("a.png", data, "image/png")}, data={"origin": "human_drawn"})
    img = r.json()["id"]
    assert (await op(api, wid, a, {"type": "update_panel", "id": pid, "image_placement": {
        "crop_px": [0, 0, W, H], "dest_box_mm": [0, 0, 60, 80]}})).status_code == 200
    x0, y0, x1, y1 = PROTECTED
    assert (await op(api, wid, a, {"type": "add_protected_region", "image_id": img,
                                   "polygon_px": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]})).status_code == 200
    return {**s, "img": img, "src": data}


async def run(api, s, label, body) -> dict:
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
    (s["out"] / f"{label}.png").write_bytes(img["bytes"])
    return img


def protected_same(out, src):
    x0, y0, x1, y1 = PROTECTED
    return (out[y0:y1, x0:x1] == src[y0:y1, x0:x1]).all()


async def test_囲んで直すは人の範囲と囲んだ外の画素を変えない(api, gpu):
    s = gpu
    box = (200, 120, 600, 520)  # 手動編集の範囲を含める
    mask = Image.new("L", (W, H), 0)
    mask.paste(255, box)
    for only_masked in (False, True):
        img = await run(api, s, f"inpaint_only_masked_{only_masked}", {
            "process": "inpaint", "source_image_id": s["img"],
            "params": {**initial("inpaint"), "prompt": PROMPT + ", smile", "only_masked": only_masked},
            "mask": {"png_base64": png_b64(mask)}})
        out, src = arr(img["bytes"]), arr(s["src"])
        assert out.shape == src.shape
        assert protected_same(out, src), "人の手の範囲の画素が変わった"
        reach = initial("inpaint")["grow_px"] + initial("inpaint")["feather_px"] + 2
        outside = np.ones(src.shape[:2], bool)
        outside[box[1] - reach:box[3] + reach, box[0] - reach:box[2] + reach] = False
        assert (out[outside] == src[outside]).all(), "囲んだ範囲の外の画素が変わった"
        inside = np.zeros(src.shape[:2], bool)
        inside[box[1] + 20:box[3] - 20, box[0] + 20:box[2] - 20] = True
        x0, y0, x1, y1 = PROTECTED
        inside[y0:y1, x0:x1] = False
        assert np.abs(out[inside] - src[inside]).mean() > 3, "囲んだ所が描き直されていない"


async def test_描き足すは広げた大きさで返り_元の所と人の範囲を変えない(api, gpu):
    s = gpu
    img = await run(api, s, "outpaint", {"process": "outpaint", "source_image_id": s["img"],
                                         "params": {**initial("outpaint"), "unit": "px", "left": 256, "bottom": 128,
                                                    "prompt": PROMPT}})
    out, src = arr(img["bytes"]), arr(s["src"])
    assert out.shape == (H + 128, W + 256, 3)
    assert img["details"]["geometry"] == {"scale": [1, 1], "offset": [256, 0]}
    x0, y0, x1, y1 = PROTECTED
    assert (out[y0:y1, x0 + 256:x1 + 256] == src[y0:y1, x0:x1]).all(), "人の手の範囲の画素が変わった"
    f = initial("outpaint")["feather_px"] + 1
    assert (out[0:H - f, 256 + f:] == src[0:H - f, f:]).all(), "元の絵の所が変わった"


async def test_絵から作り直すは人の範囲を変えない(api, gpu):
    s = gpu
    img = await run(api, s, "image_to_image", {"process": "image_to_image", "source_image_id": s["img"],
                                               "params": {**initial("image_to_image"), "prompt": PROMPT + ", night"}})
    out, src = arr(img["bytes"]), arr(s["src"])
    assert out.shape == src.shape and protected_same(out, src)
    assert np.abs(out - src).mean() > 3


async def test_指示で直すはQwen_Imageで動き_人の範囲を変えない(api, gpu):
    s = gpu
    img = await run(api, s, "instruction_edit_whole", {
        "process": "instruction_edit", "source_image_id": s["img"],
        "params": {**initial("instruction_edit"), "instruction": "Change the background to a beach."}})
    out, src = arr(img["bytes"]), arr(s["src"])
    assert out.shape == src.shape and protected_same(out, src)
    assert np.abs(out - src).mean() > 3
    box = (100, 600, 700, 1000)
    mask = Image.new("L", (W, H), 0)
    mask.paste(255, box)
    img = await run(api, s, "instruction_edit_masked", {
        "process": "instruction_edit", "source_image_id": s["img"],
        "params": {**initial("instruction_edit"), "instruction": "Make the skirt red."},
        "mask": {"png_base64": png_b64(mask)}})
    out = arr(img["bytes"])
    assert out.shape == src.shape and protected_same(out, src)
    p = initial("instruction_edit")
    reach = p["grow_px"] + p["feather_px"] + 2
    outside = np.ones(src.shape[:2], bool)
    outside[box[1] - reach:box[3] + reach, box[0] - reach:box[2] + reach] = False
    assert (out[outside] == src[outside]).all(), "囲んだ範囲の外の画素が変わった"
    # 色合わせの有り無しを目で比べるため、合わせない回も残す（色を変える指示を、色合わせが元へ戻すか）
    for label in ("instruction_edit_masked_nocolor", "instruction_edit_whole_nocolor"):
        body = {"process": "instruction_edit", "source_image_id": s["img"], "params": {
            **initial("instruction_edit"), "color_match": "none",
            "instruction": "Make the skirt red." if "masked" in label else "Change the background to a beach."}}
        if "masked" in label:
            body["mask"] = {"png_base64": png_b64(mask)}
        out = arr((await run(api, s, label, body))["bytes"])
        assert out.shape == src.shape and protected_same(out, src)


def line_drawing() -> Image.Image:
    """白地に黒い線の、窓と机の線画（形の指定の線画に渡す）。"""
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.rectangle((80, 120, 360, 460), outline="black", width=6)
    d.line((220, 120, 220, 460), fill="black", width=6)
    d.line((80, 290, 360, 290), fill="black", width=6)
    d.polygon([(60, 760), (708, 760), (640, 860), (130, 860)], outline="black", width=6)
    d.ellipse((470, 180, 690, 400), outline="black", width=6)
    return im


async def test_形の指定_線画と骨格で文から作る(api, gpu):
    s = gpu
    line = line_drawing()
    line.save(s["out"] / "control_lineart_input.png")
    img = await run(api, s, "control_lineart", {
        "process": "text_to_image", "control": {"png_base64": png_b64(line)},
        "params": {**initial("text_to_image"), "prompt": "masterpiece, best quality, classroom, window, desk, no humans",
                   "width": W, "height": H, "control": "lineart"}})
    assert arr(img["bytes"]).shape == (H, W, 3)
    pose = draw_standing_pose(W, H, FigureBox(0.3, 0.1, 0.7, 0.95))
    pose.save(s["out"] / "control_pose_input.png")
    img = await run(api, s, "control_pose", {
        "process": "text_to_image", "control": {"png_base64": png_b64(pose)},
        "params": {**initial("text_to_image"), "prompt": PROMPT, "width": W, "height": H, "control": "pose",
                   "control_invert": False}})
    assert arr(img["bytes"]).shape == (H, W, 3)
