"""保存と再起動の確かめ（v3/web/test/persistence_e2e.mjs）の作品を、操作の窓口（本物の口）から作る。

画面で確かめる編集（コマ・文字・トーン・層・絵・ページの設定・ペン・訳文・確認の状態・キー）はここでは入れない。
ここで入れるのは、その前提だけ：つなぎ先と送り先（管理者）・作品の設定・閾値・話とページ・ハーネスのコマ・訳す文字。
ハーネスは偽の LLM・検出器・ComfyUI（fake_workers_main.py・fake_comfy_main.py）で、話2の工程 S4 を始める。

  uv run python tests/persistence/seed_work.py --api http://127.0.0.1:8961 --comfy http://127.0.0.1:8963 \
      --admin pe-admin --author pe-author

出力は1行の JSON（作品・話・ページ・コマ・文字の id）。絵は小さくする（大きさを確かめる試験ではない）。
"""

import argparse
import asyncio
import io
import json
import uuid

import httpx
from PIL import Image, ImageDraw

# 試験と同じ値（tests/integration/test_harness.py・test_image_generation.py）
SD = {"model": {"kind": "separate", "unet_name": "u.safetensors", "weight_dtype": "default", "clip_name": "c.safetensors",
                "clip_type": "stable_diffusion", "vae_name": "v.safetensors"},
      "loras": [], "sampler": {"steps": 4, "cfg": 7, "sampler_name": "euler", "scheduler": "normal"},
      "native_long_side": 512, "controlnet_name": None}
HARNESS_FRAME = {"polygon_mm": [[0, 0], [60, 0], [60, 40], [0, 40]], "bleeds": False}
CONTENT = {"content": "主人公が振り返る", "shot": "胸から上", "angle": "目の高さ",
           "people": [{"name": "アオイ", "face": "中", "facing": "正面"}]}
THRESHOLDS = {"person_score": 0.5, "edge_px": 4, "text_score": 0.5}
DRAWING = {"model_description": "Stable Diffusion 1.5 系。英語のタグをカンマ区切りで受ける",
           "quality_words": "best quality", "style_words": "manga style", "negative_words": "lowres",
           "long_side": 256, "base_params": {"steps": 4, "cfg": 7, "control": "none", "control_strength": 1.0,
                                             "control_end": 1.0, "control_invert": False},
           "redraw_params": {"steps": 4, "cfg": 7, "control": "none", "control_strength": 1.0, "control_end": 1.0,
                             "control_invert": False, "strength": 0.6}}
HARNESS_PROCESSES = ["harness_panel_tags", "harness_detect_person", "harness_detect_text", "harness_shot_angle",
                     "harness_pick", "harness_name_draft", "harness_contradiction", "harness_foreshadow"]
PAGE_SPEC = {"frame_width_mm": 150, "frame_height_mm": 220, "trim_width_mm": 182, "trim_height_mm": 257,
             "bleed_mm": 3, "gutter_x_mm": 3, "gutter_y_mm": 6}
# 書き出しは小さい解像度で（速さのため。解像度の値は画面で変える：ページの設定）
PRINT = {"file_code": "PE", "color_mode": "grayscale", "dpi_by_color_mode": {"bilevel": 150, "grayscale": 100, "color": 100},
         "bilevel": {"threshold": 128, "pdf_codec": "ccitt_g4",
                     "image_screen": {"lines_per_inch": 60, "angle_deg": 45, "dot_shape": "round"}},
         "safe_area": {"top_mm": 10, "bottom_mm": 10, "gutter_mm": 12, "outer_mm": 8},
         "page_count_multiple": 4, "page_count_scope": "episode"}
NOMBRE = {"font_family": "ipam", "font_size_pt": 9, "hidden_font_size_pt": 6, "color": "#000000",
          "start_number": 1, "numbering_scope": "episode",
          "position": {"vertical": "bottom", "horizontal": "outer", "edge_mm": 5, "side_mm": 5},
          "hidden_position": {"bottom_mm": 3, "gutter_mm": 3},
          "display_by_kind": {"cover": "none", "color_page": "hidden", "body": "visible", "blank": "hidden"}}
TYPESETTING = {"line_spacing_ratio": 0.15, "line_break": "phrase", "tate_chu_yoko_max_digits": 2,
               "tate_chu_yoko_marks": True, "align": "start"}
LIMITS = {"unit": {"max_attempts": 3, "candidates_per_attempt": 2, "budget_cost": 1000, "budget_seconds": 900,
                   "error_stop": 3, "same_failure_restart": 2, "eval_repeats": 1, "disagreement_stop": 2,
                   "review_notice_seconds": 3600, "resend_limit": 0},
          "max_parallel_units": 2, "completion": ["checks_pass", "evaluator_pick", "human_approve"]}


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def small_png(w=160, h=120, seed=1) -> bytes:
    im = Image.new("L", (w, h), 230)
    d = ImageDraw.Draw(im)
    d.ellipse([w * 0.2, h * 0.15, w * 0.8, h * 0.85], outline=40, width=4)
    d.line([(0, h * 0.75), (w, h * 0.6 + seed)], fill=90, width=3)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def nid() -> str:
    return uuid.uuid4().hex


async def seed(api: str, comfy: str, admin: str, author: str) -> dict:
    async with httpx.AsyncClient(base_url=api, timeout=30) as c:
        async def call(method, path, who, **kw):
            r = await c.request(method, path, headers={"X-V3-User": who, "X-V3-Request": "1"}, **kw)
            if r.status_code >= 300:
                raise SystemExit(f"{method} {path} → {r.status_code} {r.text}")
            return r.json() if r.content else None

        # つなぎ先（管理者）。ComfyUI・LLM・検出器（LLM と検出器は作業者の中で偽物に差し替える）
        async def service(**body):
            return (await call("POST", "/services", admin, json={"name": f"pe-{nid()[:6]}", **body}))["id"]

        async def route(sid, process, **settings):
            await call("PUT", f"/services/{sid}/processes/{process}", admin, json=settings)
            await call("PUT", f"/routes/{process}", admin, json={"service_id": sid, "resend_limit": 0,
                                                                  "regenerate_limit": 0, "ai_task": "drawing",
                                                                  "ai_action": "propose"})

        comfy_sid = await service(location="local", kind="image", adapter="comfyui", endpoint=comfy,
                                  send_mode="parallel", max_concurrency=4)
        for name in ("text_to_image", "image_to_image"):
            await route(comfy_sid, name, comfy_graph_settings=SD, comfy_wait_seconds=300)
        llm_sid = await service(location="api", kind="text", adapter="litellm", send_mode="parallel", max_concurrency=6)
        det_sid = await service(location="local", kind="image", adapter="detector", endpoint="http://127.0.0.1:1",
                                send_mode="parallel", max_concurrency=6)
        for process in HARNESS_PROCESSES:
            if "detect" in process:
                await route(det_sid, process)
            else:
                await route(llm_sid, process, model="fake", cost_per_call=1)

        wid = (await call("POST", "/works", author, json={"title": "保存と再起動の確かめ", "reading_direction": "rtl",
                                                          "text_direction": "vertical", "medium": "paper"}))["id"]

        async def op(body):
            return await call("POST", f"/works/{wid}/ops", author, json=body)

        vol, ep1, ep2, ep3 = nid(), nid(), nid(), nid()
        p1, p2 = nid(), nid()
        await op({"type": "allow_destination", "service_id": llm_sid, "allowed": True})
        await op({"type": "add_volume", "id": vol, "number": 1})
        await op({"type": "add_episode", "id": ep1, "volume_id": vol, "number": 1, "title": "原稿"})
        await op({"type": "add_episode", "id": ep2, "volume_id": vol, "number": 2, "title": "工程（確認待ちにする）"})
        await op({"type": "add_episode", "id": ep3, "volume_id": vol, "number": 3, "title": "工程（作業者を止める）"})
        await op({"type": "set_work_settings", "page_spec": PAGE_SPEC, "first_page_is_left": False,
                  "preferences": {"language": "ja",
                                  "fonts_by_kind": {"balloon": "ipam", "caption": "ipam",
                                                    "drawn_sfx": "ipam"},
                                  "frame_style": {"line_width_mm": 0.5, "line_color": "#000000"},
                                  "typesetting": TYPESETTING, "print": PRINT, "nombre": NOMBRE}})
        await op({"type": "set_threshold", "key": "panel_short_side_min_mm", "value": {"value": 10},
                  "source": "保存と再起動の確かめ", "status": "unverified"})
        for k, v in THRESHOLDS.items():
            await op({"type": "set_threshold", "key": f"harness.drawing.{k}", "value": {"value": v},
                      "source": "保存と再起動の確かめ", "status": "verified"})
        await op({"type": "add_material_entry", "kind": "character", "name": "アオイ", "traits": "短い青い髪",
                  "generation": {"prompt": "1girl, short blue hair"}})

        # 話1：ページ 2 枚。1ページ目にコマ 2（上のコマに小さい絵と文字 2）。ページを足す・見開き・コマ・文字は画面で
        await op({"type": "add_page", "id": p1, "episode_id": ep1, "number": 1})
        await op({"type": "add_page", "id": p2, "episode_id": ep1, "number": 2})
        await op({"type": "update_page", "id": p1, "page_kind": "body"})
        top, low = nid(), nid()
        await op({"type": "add_panel", "id": top, "page_id": p1, "order": 1, "frame": {"polygon_mm": rect(0, 0, 150, 100),
                                                                                       "bleeds": False}})
        await op({"type": "add_panel", "id": low, "page_id": p1, "order": 2, "frame": {"polygon_mm": rect(0, 106, 150, 220),
                                                                                       "bleeds": False}})
        img = await call("POST", f"/works/{wid}/panels/{top}/image", author,
                         files={"image": ("seed.png", small_png(), "image/png")}, data={"origin": "human_drawn"})
        await op({"type": "update_panel", "id": top, "image_placement": {
            "crop_px": [0, 0, 160, 120], "dest_box_mm": [0, 0, 150, 112.5], "rotation_deg": 0, "skew_x_deg": 0,
            "skew_y_deg": 0, "flip_h": False, "flip_v": False}})
        texts = []
        for i, (x, words) in enumerate([(130, "ここが\n入口か"), (100, "誰も\nいない")]):
            tid = nid()
            box = [x - 6, 8, x + 6, 34]
            await op({"type": "add_text_item", "id": tid, "panel_id": top, "item_kind": "caption", "order": i + 1,
                      "text": words, "writing_direction": "vertical", "font_size_pt": 9,
                      "decoration": {"fill": "#000000"}, "box_mm": box, "balloon_shape": {"kind": "none"}})
            texts.append(tid)

        # 話2・話3：工程のコマ（1つずつ）
        hp = {}
        for ep in (ep2, ep3):
            page, panel = nid(), nid()
            await op({"type": "add_page", "id": page, "episode_id": ep, "number": 1})
            await op({"type": "add_panel", "id": panel, "page_id": page, "order": 1, "frame": HARNESS_FRAME,
                      "content": CONTENT})
            hp[ep] = {"page": page, "panel": panel}

        stage = await call("POST", f"/works/{wid}/harness/stages", author, json={
            "episode_id": ep2, "stage": "S4", "limits": LIMITS, "spec": {"drawing": DRAWING}})
        return {"workId": wid, "episodes": [ep1, ep2, ep3], "pages": [p1, p2], "panels": [top, low],
                "image": img["id"], "texts": texts, "harnessPanels": hp, "stageRun": stage["stage_run_id"],
                "limits": LIMITS, "drawing": DRAWING}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--api", required=True)
    p.add_argument("--comfy", required=True)
    p.add_argument("--admin", required=True)
    p.add_argument("--author", required=True)
    a = p.parse_args()
    print(json.dumps(asyncio.run(seed(a.api, a.comfy, a.admin, a.author)), ensure_ascii=False))
