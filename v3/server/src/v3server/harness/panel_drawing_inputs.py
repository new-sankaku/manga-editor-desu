"""作画（S4）の1コマの作り方を決める所（設計 8.1 の「生成」の中身）。panel_drawing_steps.py の文脈の段が呼ぶ。

コマごとに、使える入力から道（route）を1つ決める。足りない入力は「足りない」と道の記録（missing）に書く（黙って飛ばさない）。
- rough：人が描いた下絵（コマの絵の line_art で、人が描いた物）がある。下絵を線画の形の指定にして1回で描く（設計 8.1 の場面4。
  背景と人物を分けない）
- background_crop：場所の正本の背景の絵と、コマの向きが同じ。正本の絵からコマの分を切り出し（crop_px）、その上に人物の範囲だけを
  囲んで描く（inpaint）
- background_3d：場所の正本に箱の3D（scene3d）があり、コマの向きのカメラがある。奥行きか線画を描いて背景を作り（text_to_image）、
  その上に人物の範囲だけを囲んで描く（inpaint）
- single：背景の入力が無い。人物と背景を1回で描く

人物の置き場は、作業の決めごと person_placement で「範囲ごとの文（region）」か「骨格（pose）」のどちらか1つを渡す（両方は渡さない）。
ネームに人物の範囲（box_mm）が無ければ置き場は渡さず、そのことを missing に書く。
骨格の図（pose_skeleton_image）が描けるのは立ち姿だけ（試作 p14）。座る・走る姿勢は未検証。
"""

import base64
import io
import math
from typing import Any, Literal

from PIL import Image, ImageChops
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from v3server.background_scene3d.box_scene_depth_render import Box, Camera, LineSettings, render_depth_and_line
from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry
from v3server.canonical_tables.work_tree_tables import Panel
from v3server.comfy_graphs.pose_skeleton_image import FigureBox, draw_standing_pose
from v3server.generation_queue.image_process_registry import spec_for
from v3server.harness import queue_calls as q
from v3server.operations.image_placement_carry import frame_bbox

ControlName = Literal["pose", "depth", "lineart"]


class ControlUse(BaseModel):
    """形の指定の効き。値は頼む人が決める（p18 は奥行き・線画で 0.8・0.8。骨格・下絵の値は未検証）。"""

    model_config = ConfigDict(extra="forbid")
    strength: float = Field(ge=0, le=2)
    end: float = Field(ge=0, le=1)


class BackgroundSpec(BaseModel):
    """場所の正本から背景を作るときの決めごと。"""

    model_config = ConfigDict(extra="forbid")
    # 3D の場所から何を描いて渡すか
    control: Literal["depth", "lineart"]
    # 線画を引くときの、奥行きの飛びと線の太さ（box_scene_depth_render.LineSettings。試作 p18 は 0.05・2）
    depth_jump_log: float = Field(gt=0)
    thickness_px: int = Field(ge=1)
    # 背景を作る text_to_image の引数（文・大きさ・形の指定以外）
    params: dict[str, Any]
    # 背景の上に人物を描く inpaint の引数（文・形の指定以外）
    composite_params: dict[str, Any]


class FixSpec(BaseModel):
    """直させる段の決めごと。落ちた所（絵の中の文字・顔）だけを囲み、inpaint か指示で直す。"""

    model_config = ConfigDict(extra="forbid")
    process: Literal["inpaint", "instruction_edit"]
    # 処理の引数のうち、文以外（inpaint は prompt・negative_prompt、instruction_edit は instruction を作業が入れる）
    params: dict[str, Any]
    # 直す所の種類ごとの言葉。inpaint は文の後ろに足す言葉、instruction_edit は指示の文そのもの
    words: dict[Literal["text", "face"], str]
    # 落ちた範囲を囲む前に広げる画素
    grow_px: int = Field(ge=0, le=512)


class DrawingSpec(BaseModel):
    """作画の作業の中身の決めごと。作業を頼む人が渡す（設計 8.1 の固定の部分のうち、人物以外）。"""

    model_config = ConfigDict(extra="forbid")

    # 渡す先のモデルが受け付ける言葉の説明（タグを作らせる問いに入れる）
    model_description: str = Field(min_length=1)
    quality_words: str
    style_words: str
    negative_words: str
    # 長い辺の画素（コマの縦横比で短い辺を決める。8の倍数に丸める）
    long_side: int = Field(ge=64, le=4096)
    # 処理の引数のうち、文・大きさ以外（形の指定など。処理の形でそのまま確かめる）
    base_params: dict[str, Any]
    # 人が直した絵から続けるときの、変える強さなど（image_to_image の引数のうち文・大きさ以外）
    redraw_params: dict[str, Any] | None = None
    # 人物の置き場の渡し方（どちらか1つ）。region：人物ごとの範囲に文を当てる / pose：骨格の図を形の指定で渡す
    person_placement: Literal["region", "pose"]
    # region のときの範囲の文の強さ（ConditioningSetArea の strength）
    region_strength: float | None = Field(default=None, ge=0, le=10)
    # 形の指定ごとの効き（使う物だけ書く。使うのに無ければ作業は blocked）
    controls: dict[ControlName, ControlUse]
    # 場所の正本から背景を作るとき（無ければ、正本があっても使わず、そのことを道の記録に書く）
    background: BackgroundSpec | None = None
    # 直させる段（無ければ直させず、検査で全部落ちたら全部を作り直す。そのことを出来事に書く）
    fix: FixSpec | None = None

    @model_validator(mode="after")
    def _params_fit(self) -> "DrawingSpec":
        """処理の引数の形を、頼む前（工程を始めるとき）に確かめる。文と大きさは作業が入れるので仮の値で見る。"""
        text = {"prompt": "x", "negative_prompt": ""}
        spec_for("text_to_image").params_model.model_validate({**self.base_params, **text, "width": 64, "height": 64})
        if self.redraw_params is not None:
            spec_for("image_to_image").params_model.model_validate({**self.redraw_params, **text})
        if self.person_placement == "region" and self.region_strength is None:
            raise ValueError("person_placement=region には region_strength が要る")
        if self.background is not None:
            spec_for("text_to_image").params_model.model_validate(
                {**self.background.params, **text, "width": 64, "height": 64})
            spec_for("inpaint").params_model.model_validate({**self.background.composite_params, **text})
        if self.fix is not None:
            if self.fix.process == "inpaint":
                spec_for("inpaint").params_model.model_validate({**self.fix.params, **text})
            else:
                spec_for("instruction_edit").params_model.model_validate({**self.fix.params, "instruction": "x"})
        return self


def size_for_frame(frame: dict[str, Any] | None, long_side: int) -> tuple[int, int]:
    box = frame_bbox(frame)
    if box is None:
        raise q.blocked("コマの枠が無い。ネームで枠を決めてから作画する")
    w, h = box[2] - box[0], box[3] - box[1]
    if w <= 0 or h <= 0:
        raise q.blocked("コマの枠の大きさが0")
    if w >= h:
        return long_side // 8 * 8, max(64, math.floor(long_side * h / w / 8) * 8)
    return max(64, math.floor(long_side * w / h / 8) * 8), long_side // 8 * 8


def box_in_panel(frame: dict[str, Any], box_mm: Any) -> list[float]:
    """ページの mm の箱を、コマの枠の外接の四角に対する 0〜1 の割合にする（はみ出しは枠に切る）。"""
    fx0, fy0, fx1, fy1 = frame_bbox(frame)
    fw, fh = fx1 - fx0, fy1 - fy0
    x0, y0, x1, y1 = box_mm
    clamp = lambda v: min(1.0, max(0.0, v))  # noqa: E731
    return [clamp((x0 - fx0) / fw), clamp((y0 - fy0) / fh), clamp((x1 - fx0) / fw), clamp((y1 - fy0) / fh)]


def box_px(box: list[float], width: int, height: int) -> list[int]:
    return [round(box[0] * width), round(box[1] * height), round(box[2] * width), round(box[3] * height)]


def region_px8(box: list[float], width: int, height: int) -> dict[str, int]:
    """割合の箱を、範囲ごとの文の 8 画素刻みの範囲にする（絵の外へは出さない）。"""
    x = min(width - 8, math.floor(box[0] * width / 8) * 8)
    y = min(height - 8, math.floor(box[1] * height / 8) * 8)
    w = max(8, math.ceil((box[2] - box[0]) * width / 8) * 8)
    h = max(8, math.ceil((box[3] - box[1]) * height / 8) * 8)
    return {"x": x, "y": y, "width": min(w, (width - x) // 8 * 8), "height": min(h, (height - y) // 8 * 8)}


def aspect_crop(img_w: int, img_h: int, want_w: int, want_h: int, box: list[float] | None) -> tuple[list[int], str]:
    """正本の絵から切り出す範囲（画素）。ネームに切り出す範囲（background_crop）があればそれ、無ければ絵の真ん中を
    コマの縦横比でいちばん大きく取る（取り方を返して道の記録に書く）。"""
    if box is not None:
        return box_px(box, img_w, img_h), "ネームの切り出す範囲（background_crop）"
    ratio = want_w / want_h
    if img_w / img_h > ratio:
        cw, ch = round(img_h * ratio), img_h
    else:
        cw, ch = img_w, round(img_w / ratio)
    x0, y0 = (img_w - cw) // 2, (img_h - ch) // 2
    return [x0, y0, x0 + cw, y0 + ch], "ネームに切り出す範囲が無いので、正本の絵の真ん中をコマの縦横比で切り出した"


def png_b64(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def pose_image(width: int, height: int, boxes: list[list[float]]) -> str:
    """人物ごとの立ち姿の骨格を1枚に重ねる（黒地。明るい方を残す）。"""
    out = Image.new("RGB", (width, height), "black")
    for b in boxes:
        out = ImageChops.lighter(out, draw_standing_pose(width, height, FigureBox(*b)))
    return png_b64(out)


def scene_image(scene: dict[str, Any], view: str, width: int, height: int, bg: BackgroundSpec) -> str:
    cam = scene["cameras"][view]
    boxes = [Box(*b) for b in scene["boxes"]]
    camera = Camera(tuple(cam["position"]), float(cam["yaw_degrees"]), float(cam["pitch_degrees"]),
                    float(cam["fov_degrees"]))
    out = render_depth_and_line(boxes, camera, width, height, LineSettings(bg.depth_jump_log, bg.thickness_px))
    return png_b64(out.depth if bg.control == "depth" else out.line)


def control_fields(spec: DrawingSpec, name: ControlName, invert: bool) -> dict[str, Any]:
    use = spec.controls.get(name)
    if use is None:
        raise q.blocked(f"作業の決めごとの controls に {name} の効き（strength・end）が無い。この形の指定を使うには要る")
    return {"control": "lineart" if name == "lineart" else name, "control_strength": use.strength,
            "control_end": use.end, "control_invert": invert}


async def background_of(session, work_id: str, location: str | None) -> MaterialEntry | None:
    if not location:
        return None
    return (await session.execute(select(MaterialEntry).where(
        MaterialEntry.work_id == work_id, MaterialEntry.kind == "background", MaterialEntry.name == location,
        MaterialEntry.removed.is_(False), MaterialEntry.proposal_state == "adopted"))).scalar_one_or_none()


async def human_rough(session, panel: Panel) -> ImageFile | None:
    return (await session.execute(select(ImageFile).where(
        ImageFile.panel_id == panel.id, ImageFile.role == "line_art", ImageFile.origin == "human_drawn",
        ImageFile.discarded.is_(False)).order_by(ImageFile.created_at.desc()).limit(1))).scalar_one_or_none()


async def plan_panel(session, work_id: str, panel: Panel, spec: DrawingSpec, people: list[dict[str, Any]],
                     width: int, height: int) -> dict[str, Any]:
    """道・人物の範囲・背景の入力・足りない入力を決める。people は [{name, prompt}]（文脈の段が設定資料から組んだ物）。"""
    c = panel.content
    used: list[str] = []
    missing: list[str] = []
    figs = []
    for p, src in zip(people, [x for x in (c.get("people") or []) if isinstance(x, dict) and x.get("name")], strict=True):
        box = box_in_panel(panel.frame, src["box_mm"]) if src.get("box_mm") else None
        if box is None:
            missing.append(f"人物 {p['name']} の範囲（ネームの box_mm）が無い")
        else:
            used.append(f"人物 {p['name']} の範囲")
        face = box_in_panel(panel.frame, src["face_box_mm"]) if src.get("face_box_mm") else None
        figs.append({**p, "box": box, "face_box": face})
    boxes_ok = bool(figs) and all(f["box"] is not None for f in figs)
    plan: dict[str, Any] = {"people": figs, "placement": spec.person_placement if boxes_ok else None,
                            "size": [width, height], "used": used, "missing": missing}
    if figs and not boxes_ok:
        missing.append("人物の範囲が揃わないので、人物の置き場（範囲ごとの文・骨格）は渡さない")
    rough = await human_rough(session, panel)
    if rough is not None:
        used.append("人が描いた下絵（線画の形の指定。背景と人物を分けずに描く）")
        return {**plan, "route": "rough", "rough_image_id": rough.id}
    loc = await background_of(session, work_id, c.get("location"))
    view = c.get("view")
    if not c.get("location"):
        missing.append("ネームに場所（location）が無い。背景の正本は使えない")
        return {**plan, "route": "single"}
    if loc is None:
        missing.append(f"設定資料に場所 {c['location']} の背景（採った物）が無い")
        return {**plan, "route": "single"}
    gen = loc.generation or {}
    canonical = gen.get("canonical") or {}
    scene = gen.get("scene3d") or {}
    if view is None:
        missing.append("ネームにコマの向き（view）が無い。正本の向きと比べられない")
        return {**plan, "route": "single", "location": loc.name}
    if spec.background is None:
        missing.append("作業の決めごとに background（背景を作る引数）が無いので、場所の正本は使わない")
        return {**plan, "route": "single", "location": loc.name}
    if figs and not boxes_ok:
        missing.append("人物の範囲が無いと背景の上に人物を描けないので、場所の正本は使わない")
        return {**plan, "route": "single", "location": loc.name}
    location_prompt = gen.get("prompt")
    if canonical.get("image_id") and canonical.get("view") == view:
        img = await session.get(ImageFile, canonical["image_id"])
        crop, how = aspect_crop(img.width, img.height, width, height, c.get("background_crop"))
        used.append(f"場所 {loc.name} の正本の背景の絵（向き {view} が同じ）を切り出した")
        if c.get("background_crop") is None:
            missing.append(how)
        if not figs and spec.redraw_params is None:
            raise q.blocked("人物のいないコマで正本の背景を使うには、作業の決めごとに redraw_params が要る")
        return {**plan, "route": "background_crop", "location": loc.name, "view": view,
                "background": {"image_id": img.id, "crop_px": crop, "how": how},
                "size": [crop[2] - crop[0], crop[3] - crop[1]]}
    if (scene.get("cameras") or {}).get(view) and scene.get("boxes"):
        if not location_prompt:
            raise q.blocked(f"設定資料の場所 {loc.name} に背景の生成の言葉（generation.prompt）が無い")
        used.append(f"場所 {loc.name} の箱の3D（向き {view} のカメラ）から{'奥行き' if spec.background.control == 'depth' else '線画'}を描いた")
        return {**plan, "route": "background_3d", "location": loc.name, "view": view,
                "background": {"scene3d": scene, "prompt": location_prompt}}
    missing.append(f"場所 {loc.name} の正本に、向き {view} の絵も3Dのカメラも無い")
    return {**plan, "route": "single", "location": loc.name}


def placement_params(spec: DrawingSpec, plan: dict[str, Any], width: int, height: int) -> tuple[dict[str, Any], str | None]:
    """人物の置き場の引数（範囲ごとの文か骨格の形の指定）と、骨格の図（base64）。"""
    if plan["placement"] == "region":
        regions = [{"text": f["prompt"], **region_px8(f["box"], width, height), "strength": spec.region_strength}
                   for f in plan["people"]]
        return {"regions": regions}, None
    if plan["placement"] == "pose":
        return control_fields(spec, "pose", invert=False), pose_image(width, height, [f["box"] for f in plan["people"]])
    return {}, None


def people_mask(plan: dict[str, Any], width: int, height: int) -> list[list[list[int]]]:
    out = []
    for f in plan["people"]:
        x0, y0, x1, y1 = box_px(f["box"], width, height)
        out.append([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    return out
