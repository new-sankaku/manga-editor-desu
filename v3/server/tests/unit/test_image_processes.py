"""画像生成の処理（generation_queue/image_process_registry.py）の単体の試験。
マスクの下ごしらえ・手順の組み方・置き場の引き継ぎ・送り手の分かれ道・PNG の文字の欄を外す。"""
import io
import json
from functools import partial

import httpx
import numpy as np
import pytest
from PIL import Image, PngImagePlugin

from v3server.canonical_tables.service_and_job_tables import Service, ServiceProcess
from v3server.generation_queue import image_process_inputs as mk
from v3server.generation_queue.image_process_preparation import finish_image_process
from v3server.generation_queue.image_process_registry import (
    SPECS,
    build_prompt,
    describe,
    parse_params,
    resolve_outpaint,
)
from v3server.generation_queue.known_processes import KNOWN_PROCESSES
from v3server.image_intake import strip_png_text
from v3server.operations.image_placement_carry import Geometry, Version, carry, cover, placement_for, relation
from v3server.service_senders import comfyui_sender
from v3server.service_senders.comfyui_sender import call_comfyui
from v3server.service_senders.sender_result_types import AdapterError
from v3server.v3_error_types import Invalid

SD = {"model": {"kind": "separate", "unet_name": "u.safetensors", "weight_dtype": "default", "clip_name": "c.safetensors",
                "clip_type": "stable_diffusion", "vae_name": "v.safetensors"},
      "loras": [], "sampler": {"steps": 4, "cfg": 7, "sampler_name": "euler", "scheduler": "normal"},
      "native_long_side": 512, "controlnet_name": None}
# p26（v3poc/p26_edit/run.py）で流した値
EDIT = {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default",
        "clip_name": "qwen3vl_8b_int8_convrot.safetensors", "clip_type": "qwen_image",
        "vae_name": "qwen_image_2.1_vae_bf16.safetensors",
        "loras": [{"name": "l.safetensors", "strength_model": 1.0, "strength_clip": 0.0}],
        "resolution": 1024, "cache_device": "auto", "cache_dtype": "default",
        "sampler": {"steps": 25, "cfg": 1, "sampler_name": "euler", "scheduler": "simple"}}


def initial(name):
    """画面と同じく、x-initial から引数を作る。"""
    props = describe(SPECS[name])["params_schema"]["properties"]
    return {k: v["x-initial"] for k, v in props.items() if "x-initial" in v}


def classes(prompt):
    return [n["class_type"] for n in prompt.values()]


# ---------------------------------------------------------------- 一覧と引数の形


def test_every_process_is_known_with_its_task():
    for name, spec in SPECS.items():
        assert KNOWN_PROCESSES[name] == (spec.ai_task, spec.ai_action)


@pytest.mark.parametrize("name", list(SPECS))
def test_initial_values_from_schema_are_valid_params(name):
    schema = describe(SPECS[name])["params_schema"]
    for key, prop in schema["properties"].items():
        assert prop["title"], key
        assert "x-group" in prop
    p = initial(name)
    if name == "instruction_edit":
        p["instruction"] = "笑顔にする"
    parse_params(SPECS[name], p)


def test_params_have_no_hidden_defaults():
    with pytest.raises(Invalid):
        parse_params(SPECS["inpaint"], {"prompt": "a", "negative_prompt": ""})
    with pytest.raises(Invalid):
        parse_params(SPECS["inpaint"], {**initial("inpaint"), "unknown": 1})


# ---------------------------------------------------------------- マスクの下ごしらえ


def test_grow_is_square_window_and_zero_is_noop():
    m = np.zeros((20, 20), np.float32)
    m[10, 10] = 1
    g = mk.grow(m, 3)
    assert g.sum() == 49 and g[7, 7] == 1 and g[6, 10] == 0
    assert (mk.grow(m, 0) == m).all()
    edge = np.zeros((5, 5), np.float32)
    edge[0, 0] = 1
    assert mk.grow(edge, 2)[:3, :3].all() and mk.grow(edge, 2).sum() == 9


def test_redraw_mask_subtracts_protected_after_grow_and_feather():
    m = np.zeros((64, 64), np.float32)
    m[20:40, 20:40] = 1
    prot = np.zeros_like(m)
    prot[:, 38:] = 1  # 囲んだ所の右端に人の範囲
    r = mk.redraw_mask(m, prot, 6, 8)
    assert r[:, 38:].max() == 0  # 広げても、ぼかしても、人の範囲には掛からない
    assert r[30, 30] == 1 and r[30, 14] == 1  # 囲んだ所と広げた所はちょうど 1
    assert 0 < r[30, 12] < 1 and r[30, 2] == 0  # ぼかしは広げた所の外側へ


def test_crop_box_adds_padding_and_clamps():
    m = np.zeros((100, 80), np.float32)
    m[10:20, 70:75] = 1
    assert mk.crop_box(m, 8) == (62, 2, 18, 26)
    with pytest.raises(Invalid):
        mk.crop_box(np.zeros((4, 4), np.float32), 2)


def test_pad_and_extend_mask():
    src = Image.new("RGB", (4, 2), (10, 20, 30))
    src.putpixel((0, 0), (200, 0, 0))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    for fill, corner in (("edge", (200, 0, 0)), ("gray", (128, 128, 128))):
        out = Image.open(io.BytesIO(mk.pad_image(buf.getvalue(), 2, 1, 0, 0, fill)))
        assert out.size == (6, 3) and out.getpixel((0, 0)) == corner and out.getpixel((2, 1)) == (200, 0, 0)
    mirrored = Image.open(io.BytesIO(mk.pad_image(buf.getvalue(), 1, 0, 0, 0, "mirror")))
    assert mirrored.getpixel((0, 0)) == (200, 0, 0)
    m = mk.extend_mask(10, 10, 4, 0, 0, 0, 4)
    assert m.shape == (10, 14) and m[:, :4].min() == 1
    assert m[5, 4] > m[5, 5] > m[5, 6] > 0 and m[5, 8:].max() == 0  # 広げた辺から内側へ下がる
    assert mk.extend_mask(10, 10, 4, 0, 0, 0, 0)[:, 4:].max() == 0


def test_rgba_mask_reads_transparent_as_unpainted():
    im = Image.new("RGBA", (4, 4), (255, 255, 255, 0))
    im.putpixel((1, 1), (255, 255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    a = mk.to_array(buf.getvalue(), (4, 4))
    assert a.sum() == 1 and a[1, 1] == 1
    with pytest.raises(Invalid):
        mk.to_array(buf.getvalue(), (5, 4))


# ---------------------------------------------------------------- 依頼の下ごしらえ（置き場を使う）


@pytest.fixture
def store(monkeypatch, tmp_path):
    from v3server.image_file_storage import store_image
    from v3server.server_settings import get_settings
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))

    def put(im: Image.Image) -> dict:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        s = store_image(buf.getvalue())
        return {"sha256": s.sha256, "media_type": s.media_type}
    return put


def _req(store, name, params, mask=None, protected=None, size=(64, 48)):
    src = store(Image.new("RGB", size, (100, 100, 100)))
    prot = store(protected or Image.new("RGB", size, (0, 0, 0)))
    entries = [{"node": "source", "input": "image", "purpose": "source", "image_id": "img1", **src},
               {"node": "protected_mask", "input": "image", "purpose": "protected_mask", "image_id": None,
                "region_ids": [], **prot}]
    if mask is not None:
        entries.append({"node": "redraw_mask", "input": "image", "purpose": "mask", "image_id": None, **store(mask)})
    return {"image_process": {"name": name, "params": params, "seed": 5, "candidate_set_id": "set1"},
            "prepared_inputs": entries, "register": {"role": "panel_art"}}


def _read(sha):
    from v3server.image_file_storage import read_image
    return np.asarray(Image.open(io.BytesIO(read_image(sha))).convert("RGB"))[:, :, 0]


def test_inpaint_preparation_writes_named_nodes_and_crop(store):
    mask = Image.new("RGB", (64, 48), 0)
    mask.paste((255, 255, 255), (10, 10, 20, 20))
    prot = Image.new("RGB", (64, 48), 0)
    prot.paste((255, 255, 255), (15, 0, 64, 48))
    out = finish_image_process(_req(store, "inpaint", {**initial("inpaint"), "only_masked": True, "padding_px": 4},
                                    mask, prot))
    nodes = {e["node"]: e for e in out["prepared_inputs"]}
    assert set(nodes) == {"source", "protected_mask", "redraw_mask", "blend_mask"}
    redraw = _read(nodes["redraw_mask"]["sha256"])
    assert redraw[:, 15:].max() == 0 and redraw[15, 12] == 255
    assert set(np.unique(redraw)) <= {0, 255}  # 描くときは白黒
    blend = _read(nodes["blend_mask"]["sha256"])
    assert blend[:, 15:].max() == 0 and len(set(np.unique(blend)) - {0, 255}) > 0  # 重ねるときはぼかしたまま
    x, y, w, h = out["image_process"]["prepared"]["crop"]
    assert x == 0 and w <= 19 + 4 + 1
    assert out["image_process"]["prepared"]["geometry"] == {"scale": [1, 1], "offset": [0, 0]}


def test_inpaint_refuses_mask_fully_inside_human_region(store):
    mask = Image.new("RGB", (64, 48), 0)
    mask.paste((255, 255, 255), (30, 10, 40, 20))
    prot = Image.new("RGB", (64, 48), (255, 255, 255))
    with pytest.raises(Invalid, match="空"):
        finish_image_process(_req(store, "inpaint", initial("inpaint"), mask, prot))


def test_outpaint_preparation_pads_and_shifts_protected(store):
    prot = Image.new("RGB", (64, 48), 0)
    prot.paste((255, 255, 255), (0, 0, 8, 8))
    params = {**initial("outpaint"), "unit": "px", "left": 16, "top": 0, "right": 0, "bottom": 8}
    out = finish_image_process(_req(store, "outpaint", params, None, prot))
    prep = out["image_process"]["prepared"]
    assert prep["padded_size"] == [80, 56] and prep["geometry"] == {"scale": [1, 1], "offset": [16, 0]}
    nodes = {e["node"]: e for e in out["prepared_inputs"]}
    assert nodes["source"]["derived"] is True and nodes["source"]["image_id"] == "img1"
    p = _read(nodes["protected_mask"]["sha256"])
    assert p.shape == (56, 80) and p[0:8, 16:24].min() == 255 and p[0:8, 0:16].max() == 0
    r = _read(nodes["redraw_mask"]["sha256"])
    assert r[:, :16].min() == 0 or r[20, 0] == 255
    assert r[0:8, 16:24].max() == 0  # 人の範囲は描き足しの範囲から外す


def test_outpaint_mm_must_be_resolved_first(store):
    with pytest.raises(Invalid, match="画素"):
        finish_image_process(_req(store, "outpaint", {**initial("outpaint"), "left": 5}))


def test_preparation_refusals(store):
    with pytest.raises(Invalid, match="サーバーが書く"):
        r = _req(store, "image_to_image", initial("image_to_image"))
        r["image_process"]["prepared"] = {}
        finish_image_process(r)
    with pytest.raises(Invalid, match="受けない"):
        finish_image_process(_req(store, "image_to_image", initial("image_to_image"), Image.new("RGB", (64, 48))))
    with pytest.raises(Invalid, match="要る"):
        finish_image_process(_req(store, "inpaint", initial("inpaint")))
    with pytest.raises(Invalid, match="形の指定"):
        finish_image_process(_req(store, "image_to_image", {**initial("image_to_image"), "control": "lineart"}))
    r = _req(store, "image_to_image", initial("image_to_image"))
    r["prepared_inputs"] = [e for e in r["prepared_inputs"] if e["purpose"] != "protected_mask"]
    with pytest.raises(Invalid, match="人の手"):
        finish_image_process(r)


# ---------------------------------------------------------------- 手順の組み方


def _info(name, **kw):
    base = {"source_size": [64, 48], "geometry": {"scale": [1, 1], "offset": [0, 0]}}
    return {**base, **kw}


def test_text_to_image_graph_and_step_override():
    p = build_prompt("text_to_image", SD, {**initial("text_to_image"), "prompt": "a", "width": 64, "height": 64,
                                           "steps": 9}, 7, {"source_size": None}, "x")
    assert "LoadImage" not in classes(p)
    ks = next(n for n in p.values() if n["class_type"] == "KSampler")
    assert ks["inputs"]["seed"] == 7 and ks["inputs"]["steps"] == 9 and ks["inputs"]["cfg"] == 7


def test_inpaint_graph_uses_named_masks_red_channel_and_paste_back():
    p = build_prompt("inpaint", SD, initial("inpaint"), 1, _info("inpaint", crop=None), "x")
    assert {"source", "redraw_mask", "protected_mask"} <= set(p)
    masks = [n for n in p.values() if n["class_type"] == "ImageToMask"]
    assert masks and all(n["inputs"]["channel"] == "red" for n in masks)
    assert classes(p).count("ImageCompositeMasked") == 2  # 範囲で重ね、人の範囲を貼り戻す
    assert "SetLatentNoiseMask" in classes(p) and "DifferentialDiffusion" not in classes(p)
    noise = next(n for n in p.values() if n["class_type"] == "SetLatentNoiseMask")
    assert p[noise["inputs"]["mask"][0]]["inputs"]["image"][0] == "redraw_mask"  # 描くのは白黒のマスク
    first = next(n for n in p.values() if n["class_type"] == "ImageCompositeMasked"
                 and n["inputs"]["mask"][0] != prot_mask_of(p))
    assert p[first["inputs"]["mask"][0]]["inputs"]["image"][0] == "blend_mask"  # 重ねるのはぼかしたマスク
    last = [n for n in p.values() if n["class_type"] == "ImageCompositeMasked"]
    save = next(n for n in p.values() if n["class_type"] == "SaveImage")
    prot_mask = [k for k, n in p.items() if n["class_type"] == "ImageToMask" and n["inputs"]["image"][0] == "protected_mask"][0]
    final = p[save["inputs"]["images"][0]]
    assert final["class_type"] == "ImageCompositeMasked" and final["inputs"]["mask"][0] == prot_mask
    assert final["inputs"]["source"] == ["source", 0]
    assert len(last) == 2


def prot_mask_of(p):
    return [k for k, n in p.items() if n["class_type"] == "ImageToMask" and n["inputs"]["image"][0] == "protected_mask"][0]


def test_inpaint_crop_and_encode_choices():
    p = build_prompt("inpaint", SD, {**initial("inpaint"), "encode": "inpaint_encode",
                                     "only_masked": True}, 1, _info("inpaint", crop=[4, 4, 20, 10]), "x")
    assert "ImageCrop" in classes(p) and "CropMask" in classes(p)
    enc = next(n for n in p.values() if n["class_type"] == "VAEEncodeForInpaint")
    assert enc["inputs"]["grow_mask_by"] == 0
    assert classes(p).count("CropMask") == 2  # 描くマスクと重ねるマスクの両方を切り出す
    scale = [n for n in p.values() if n["class_type"] == "ImageScale"]
    assert any(n["inputs"]["width"] == 512 and n["inputs"]["height"] == 256 for n in scale)  # 長い辺を得意な大きさへ
    mask_scales = [n for n in scale if n["inputs"]["upscale_method"] == "bilinear"]
    assert mask_scales  # マスクは行き過ぎない方法で拡大する


def test_outpaint_graph_works_on_padded_size():
    p = build_prompt("outpaint", SD, {**initial("outpaint"), "unit": "px", "left": 16}, 1,
                     {"source_size": [64, 48], "padded_size": [80, 48], "margins_px": [16, 0, 0, 0],
                      "geometry": {"scale": [1, 1], "offset": [16, 0]}}, "x")
    assert "ImageScale" not in classes(p)  # 80x48 は 8 の倍数なので拡大縮小しない


def test_control_requires_controlnet_in_settings_and_inserts_union():
    params = {**initial("image_to_image"), "control": "lineart"}
    with pytest.raises(Invalid, match="ControlNet"):
        build_prompt("image_to_image", SD, params, 1, _info("i2i"), "x")
    p = build_prompt("image_to_image", {**SD, "controlnet_name": "union_promax.safetensors"}, params, 1,
                     _info("i2i"), "x")
    assert "control" in p and "ImageInvert" in classes(p)
    t = next(n for n in p.values() if n["class_type"] == "SetUnionControlNetType")
    assert t["inputs"]["type"] == "canny/lineart/anime_lineart/mlsd"
    ks = next(n for n in p.values() if n["class_type"] == "KSampler")
    assert p[ks["inputs"]["positive"][0]]["class_type"] == "ControlNetApplyAdvanced"


def test_instruction_edit_graph_crops_region_and_restores_size():
    params = {**initial("instruction_edit"), "instruction": "笑顔にする"}
    p = build_prompt("instruction_edit", EDIT, params, 3, _info("e", use_region=True, crop=[8, 8, 32, 24]), "x")
    assert classes(p).count("TextEncodeQwenImage21") == 1 and "QwenImage21Cache" in classes(p)
    enc_id, enc = next((k, n) for k, n in p.items() if n["class_type"] == "TextEncodeQwenImage21")
    assert enc["inputs"]["resolution"] == 1024 and p[enc["inputs"]["images.image_1"][0]]["class_type"] == "ImageCrop"
    ks = next(n for n in p.values() if n["class_type"] == "KSampler")
    assert ks["inputs"]["latent_image"] == [enc_id, 2] and ks["inputs"]["denoise"] == 1.0  # 元の絵の大きさの空の潜在
    assert "LoraLoaderModelOnly" in classes(p) and "CropMask" in classes(p)
    assert "blend_mask" in p and "redraw_mask" not in p
    back = [n for n in p.values() if n["class_type"] == "ImageScale"]
    assert any(n["inputs"]["width"] == 32 and n["inputs"]["height"] == 24 for n in back)
    ct = next(n for n in p.values() if n["class_type"] == "ColorTransfer")
    assert ct["inputs"]["method"] == "reinhard_lab" and p[ct["inputs"]["image_ref"][0]]["class_type"] == "ImageCrop"
    whole = build_prompt("instruction_edit", EDIT, {**params, "color_match": "none"}, 3,
                         _info("e", use_region=False, crop=None), "x")
    assert "blend_mask" not in whole and "protected_mask" in whole and "ColorTransfer" not in classes(whole)


def test_instruction_edit_preparation_sends_only_blend_mask(store):
    mask = Image.new("RGB", (64, 48), 0)
    mask.paste((255, 255, 255), (10, 10, 30, 30))
    params = {**initial("instruction_edit"), "instruction": "a"}
    out = finish_image_process(_req(store, "instruction_edit", params, mask))
    assert {e["node"] for e in out["prepared_inputs"]} == {"source", "protected_mask", "blend_mask"}
    whole = finish_image_process(_req(store, "instruction_edit", params))
    assert {e["node"] for e in whole["prepared_inputs"]} == {"source", "protected_mask"}


def test_binarize_and_diffuse_fill():
    assert mk.binarize(np.array([0.2, 0.5, 0.9], np.float32)).tolist() == [0, 1, 1]
    a = np.zeros((20, 30, 3), np.uint8)
    a[:, :15] = (200, 0, 0)
    a[:, 15:] = (0, 0, 200)
    im = Image.fromarray(a)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    out = np.asarray(Image.open(io.BytesIO(mk.pad_image(buf.getvalue(), 10, 4, 10, 4, "diffuse"))).convert("RGB"))
    assert out.shape == (28, 50, 3)
    assert (out[4:24, 10:40] == a).all()  # 元の画素は変えない
    assert tuple(out[14, 0]) == (200, 0, 0) and tuple(out[14, 49]) == (0, 0, 200)  # 近い色が流れ込む


def test_settings_are_checked():
    with pytest.raises(Invalid, match="comfy_graph_settings"):
        build_prompt("inpaint", None, initial("inpaint"), 1, _info("i"), "x")
    with pytest.raises(Invalid, match="正しくない"):
        build_prompt("inpaint", {**SD, "native_long_side": 1}, initial("inpaint"), 1, _info("i"), "x")


# ---------------------------------------------------------------- 描き足すの量を画素へ


def test_resolve_outpaint_mm_and_frame():
    pl = {"crop_px": [0, 0, 100, 50], "dest_box_mm": [10, 10, 60, 35]}  # 2 px / mm
    r = resolve_outpaint({**initial("outpaint"), "unit": "mm", "left": 5, "bottom": 2.5}, pl, None, (100, 50))
    assert (r["unit"], r["left"], r["bottom"], r["top"]) == ("px", 10, 5, 0)
    f = resolve_outpaint({**initial("outpaint"), "unit": "frame"}, pl, (5, 10, 60, 40), (100, 50))
    assert (f["left"], f["top"], f["right"], f["bottom"]) == (10, 0, 0, 10)
    with pytest.raises(Invalid, match="回転"):
        resolve_outpaint({**initial("outpaint"), "left": 1}, {**pl, "rotation_deg": 10}, None, (100, 50))
    with pytest.raises(Invalid, match="置き場"):
        resolve_outpaint({**initial("outpaint"), "left": 1}, None, None, (100, 50))


# ---------------------------------------------------------------- 置き場の引き継ぎ


def test_carry_same_size_keeps_placement():
    pl = {"crop_px": [10, 0, 90, 50], "dest_box_mm": [0, 0, 40, 25]}
    out = carry(pl, (100, 50), (100, 50), Geometry.identity())
    assert out["crop_px"] == [10, 0, 90, 50] and out["dest_box_mm"] == [0, 0, 40, 25]


def test_carry_outpaint_extends_edges_that_were_used_and_keeps_visible_part():
    pl = {"crop_px": [0, 0, 90, 50], "dest_box_mm": [0, 0, 45, 25]}  # 2 px / mm。右は切り抜いていた
    out = carry(pl, (100, 50), (120, 60), Geometry(1, 1, 20, 10))  # 左に20、上に10 広げた
    assert out["crop_px"] == [0, 0, 110, 60]
    assert out["dest_box_mm"] == [-10, -5, 45, 25]  # 元の画素は同じ mm に残る


def test_carry_back_to_smaller_version_shrinks_box():
    pl = {"crop_px": [0, 0, 120, 60], "dest_box_mm": [-10, -5, 50, 25]}
    out = carry(pl, (120, 60), (100, 50), Geometry(1, 1, 20, 10).inverse())
    assert out["crop_px"] == [0, 0, 100, 50] and out["dest_box_mm"] == [0, 0, 50, 25]


def test_carry_rotated_placement_does_not_extend():
    pl = {"crop_px": [0, 0, 100, 50], "dest_box_mm": [0, 0, 50, 25], "rotation_deg": 15}
    out = carry(pl, (100, 50), (120, 60), Geometry(1, 1, 20, 10))
    assert out["crop_px"] == [20, 10, 120, 60] and out["dest_box_mm"] == [0, 0, 50, 25]


def test_relation_through_common_ancestor_and_unknown():
    v = {"base": Version("base", 100, 50, None, None),
         "out": Version("out", 120, 50, "base", Geometry(1, 1, 20, 0)),
         "inp": Version("inp", 100, 50, "base", Geometry.identity()),
         "other": Version("other", 64, 64, None, None)}
    g = relation(v, "inp", "out")
    assert (g.ox, g.oy) == (20, 0)
    assert relation(v, "out", "base").ox == -20
    assert relation(v, "other", "out") is None
    placed, how = placement_for({"crop_px": [0, 0, 64, 64], "dest_box_mm": [0, 0, 10, 10]}, v["other"], v["out"], v,
                                (0, 0, 30, 10))
    assert how == "cover" and placed["crop_px"] == [0, 0, 120, 50]
    x0, y0, x1, y1 = placed["dest_box_mm"]
    assert x0 <= 0 and y0 <= 0 and x1 >= 30 and y1 >= 10


def test_cover_without_any_box_is_refused():
    with pytest.raises(Invalid):
        placement_for(None, None, Version("a", 10, 10, None, None), {}, None)
    assert cover(10, 20, (0, 0, 10, 10))["dest_box_mm"] == [0, -5, 10, 15]


# ---------------------------------------------------------------- 送り手


@pytest.fixture
def comfy(monkeypatch):
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/prompt":
            seen["prompt"] = json.loads(req.content)["prompt"]
            return httpx.Response(200, json={"prompt_id": "p1"})
        if req.url.path.startswith("/history/"):
            return httpx.Response(200, json={"p1": {"status": {"status_str": "success", "messages": []},
                                                    "outputs": {"9": {"images": [{"filename": "o.png", "subfolder": "",
                                                                                  "type": "output"}]}}}})
        if req.url.path == "/view":
            return httpx.Response(200, content=b"png")
        return httpx.Response(404)
    monkeypatch.setattr(comfyui_sender, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(comfyui_sender.httpx, "AsyncClient",
                        partial(httpx.AsyncClient, transport=httpx.MockTransport(handler)))
    return seen


SERVICE = Service(name="comfy", kind="image", location="local", adapter="comfyui", endpoint="http://comfy",
                  send_mode="serial", max_concurrency=1)


async def test_sender_builds_graph_from_registry_and_returns_seed(comfy):
    sp = ServiceProcess(process="text_to_image", comfy_workflow=None, comfy_wait_seconds=5, comfy_check_choices=False,
                        comfy_graph_settings=SD)
    req = {"image_process": {"name": "text_to_image", "seed": 42, "prepared": {"source_size": None},
                             "params": {**initial("text_to_image"), "prompt": "a"}},
           "register": {"role": "panel_art"}}
    r = await call_comfyui(SERVICE, sp, req)
    assert r.seed == 42 and r.settings["prompt"] == "a"
    assert any(n["class_type"] == "KSampler" and n["inputs"]["seed"] == 42 for n in comfy["prompt"].values())
    with pytest.raises(AdapterError) as e:
        await call_comfyui(SERVICE, sp, {**req, "overrides": {"1": {}}})
    assert e.value.kind == "refused"
    sp.comfy_graph_settings = None
    with pytest.raises(AdapterError) as e:
        await call_comfyui(SERVICE, sp, req)
    assert e.value.kind == "refused" and "comfy_graph_settings" in e.value.detail


# ---------------------------------------------------------------- PNG の文字の欄


def test_strip_png_text_keeps_pixels_and_dpi():
    im = Image.new("RGB", (4, 4), (1, 2, 3))
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", json.dumps({"x": 1}))
    info.add_text("workflow", "{}")
    buf = io.BytesIO()
    im.save(buf, format="PNG", pnginfo=info, dpi=(350, 350))
    out = Image.open(io.BytesIO(strip_png_text(buf.getvalue())))
    assert out.text == {} and round(out.info["dpi"][0]) == 350
    assert np.array_equal(np.asarray(out), np.asarray(im))
    plain = io.BytesIO()
    im.save(plain, format="PNG")
    assert strip_png_text(plain.getvalue()) == plain.getvalue()



def test_初めから開くまとまりは入力欄にある():
    for spec in SPECS.values():
        groups = {p.get("x-group") for p in describe(spec)["params_schema"]["properties"].values()}
        for g in spec.open_groups:
            assert g in groups, (spec.name, g)
