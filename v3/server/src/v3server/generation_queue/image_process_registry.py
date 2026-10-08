"""画像生成の処理の一覧（文から絵・絵から作り直す・似た別案・囲んで直す・描き足す・指示で直す）。

処理を足すときは、ここに1つ書き足し、ComfyUI の手順を組む関数（comfy_graphs/ の下）を1つ書く。ほかの所は変えない。
- 依頼の受け付け（job_start_and_control.enqueue）と、送り先を決めるとき（service_routes.put_route）は、ai_task・ai_action を
  ここから読む（known_processes.py が取り込む）
- 依頼を受けるときのマスク・絵の下ごしらえ（image_process_preparation.py）は、ここの prepare を呼ぶ
- 送り手（service_senders/comfyui_sender.py）は、ここの build で手順を組む。中身（モデル名など）はつなぎ先と処理の組ごとに
  人が入れたもの（ServiceProcess.comfy_graph_settings）を settings_model で確かめて使う
- 画面（v3/web/）は、ここの引数の形（JSON Schema）から入力欄を作る。欄の名前・初めの値・まとまり・部品は
  json_schema_extra の x-initial・x-group・x-widget・x-unit・x-labels に書く

引数はどれも依頼に書く（サーバーに隠れた既定値を置かない）。初めの値（x-initial）は画面が欄に入れておく値で、サーバーは使わない。
手数（steps）と文の効き（cfg）だけは書かなくてよく、書かなければつなぎ先の中身の値を使う（V3細部の決めごと 12章の優先の順）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph
from v3server.comfy_graphs.controlnet_nodes import ControlKind, ControlSettings
from v3server.comfy_graphs.image_to_image_graph import build_image_to_image
from v3server.comfy_graphs.inpaint_graph import CropBox, build_inpaint, work_size_for
from v3server.comfy_graphs.instruction_edit_graph import EditSettings, build_instruction_edit
from v3server.comfy_graphs.model_loader_nodes import DiffusionSettings, Extras
from v3server.comfy_graphs.outpaint_graph import build_outpaint
from v3server.comfy_graphs.text_to_image_graph import build_text_to_image_process
from v3server.generation_queue import image_process_inputs as mk
from v3server.v3_error_types import Invalid

# ---------------------------------------------------------------- 引数の形


def _f(title: str, initial: Any = None, group: str = "基本", widget: str | None = None, unit: str | None = None,
       labels: dict[str, str] | None = None, **kw) -> Any:
    extra: dict[str, Any] = {"x-group": group}
    if initial is not None:
        extra["x-initial"] = initial
    if widget:
        extra["x-widget"] = widget
    if unit:
        extra["x-unit"] = unit
    if labels:
        extra["x-labels"] = labels
    return Field(title=title, json_schema_extra=extra, **kw)


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 書かなければつなぎ先の中身の値（12章の優先の順）
    steps: int | None = _f("手数", group="細かい設定", widget="number", default=None, ge=1, le=200)
    cfg: float | None = _f("文の効き（CFG）", group="細かい設定", widget="number", default=None, ge=0, le=50)


class _Prompted(_Params):
    prompt: str = _f("このコマの指示", "", widget="textarea")
    negative_prompt: str = _f("入れないもの", "", widget="textarea")


CONTROL_UNION_TYPES = {"lineart": "canny/lineart/anime_lineart/mlsd", "scribble": "hed/pidi/scribble/ted",
                       "pose": "openpose", "depth": "depth"}


class _Controlled(_Prompted):
    """形の指定（線画・落書き・骨格・奥行き）。絵は依頼の input_images に purpose=control で渡す。
    効き方は p08（ラフの線画は効かなかった）・p18（3Dの線画と奥行きは効いた）。強さと終わりの初めの値は p18 の 0.8・0.8
    （SDXL と xinsir の union promax）。落書きと骨格は試作で確かめていない。"""

    control: Literal["none", "lineart", "scribble", "pose", "depth"] = _f(
        "形の指定", "none", group="形の指定", widget="select",
        labels={"none": "使わない", "lineart": "線画", "scribble": "落書き", "pose": "骨格", "depth": "奥行き"})
    control_strength: float = _f("形の効き", 0.8, group="形の指定", widget="slider", ge=0, le=2)
    control_end: float = _f("効かせる所（終わり）", 0.8, group="形の指定", widget="slider", ge=0, le=1)
    control_invert: bool = _f("白地に黒い線（反転して渡す）", True, group="形の指定", widget="check")


class TextToImageParams(_Controlled):
    width: int = _f("幅", 1024, widget="number", unit="px", ge=64, le=4096, multiple_of=8)
    height: int = _f("高さ", 1024, widget="number", unit="px", ge=64, le=4096, multiple_of=8)


class ImageToImageParams(_Controlled):
    strength: float = _f("変える強さ", 0.6, widget="slider", ge=0.01, le=1)


class VariationParams(_Prompted):
    # 「少し」「大きく」の2つ（Fooocus の Vary の形）。値は未検証
    strength: float = Field(title="変える強さ", ge=0.01, le=1, json_schema_extra={
        "x-group": "基本", "x-initial": 0.3, "x-widget": "slider", "x-presets": {"少し": 0.3, "大きく": 0.55}})


ENCODE_LABELS = {"noise_mask": "元の絵から描く", "inpaint_encode": "範囲を消してから描く"}
Encode = Literal["noise_mask", "inpaint_encode"]


class InpaintParams(_Controlled):
    denoise: float = _f("変える強さ", 0.75, widget="slider", ge=0.01, le=1)
    grow_px: int = _f("範囲を広げる", 6, widget="number", unit="px", ge=0, le=256)
    feather_px: int = _f("境目のぼかし", 8, widget="number", unit="px", ge=0, le=256)
    encode: Encode = _f("描き方", "noise_mask", widget="select", labels=ENCODE_LABELS)
    only_masked: bool = _f("囲んだ所だけ大きくして直す", False, group="囲んだ所だけ", widget="check")
    padding_px: int = _f("周りの余白", 32, group="囲んだ所だけ", widget="number", unit="px", ge=0, le=2048)


class OutpaintParams(_Controlled):
    # px と mm は辺ごとの量。frame は量を書かず、コマの枠まで広げる（量は依頼を受けるときに px へ直す）
    unit: Literal["px", "mm", "frame"] = _f("広げ方", "mm", group="広げる", widget="select",
                                           labels={"px": "画素で", "mm": "mm で", "frame": "コマの枠まで"})
    left: float = _f("左", 0, group="広げる", widget="number", ge=0, le=4096)
    top: float = _f("上", 0, group="広げる", widget="number", ge=0, le=4096)
    right: float = _f("右", 0, group="広げる", widget="number", ge=0, le=4096)
    bottom: float = _f("下", 0, group="広げる", widget="number", ge=0, le=4096)
    # 下塗りは描く前に広げた所を埋める物。調査の「LaMa、または色を流し込む」の後の方を初めの値にした（LaMa はカスタムノードが要る）
    fill: Literal["diffuse", "edge", "mirror", "gray"] = _f(
        "広げた所の下塗り", "diffuse", group="広げる", widget="select",
        labels={"diffuse": "周りの色を流し込む", "edge": "端を伸ばす", "mirror": "折り返す", "gray": "灰色"})
    feather_px: int = _f("境目のぼかし", 16, widget="number", unit="px", ge=0, le=256)
    encode: Encode = _f("描き方", "noise_mask", widget="select", labels=ENCODE_LABELS)
    denoise: float = _f("変える強さ", 1.0, widget="slider", ge=0.01, le=1)


class InstructionEditParams(_Params):
    # 空の潜在から描くモデル（Qwen-Image 2.1）なので、変える強さは無い（comfy_graphs/instruction_edit_graph.py）
    instruction: str = _f("直す指示", "", widget="textarea", min_length=1)
    negative_prompt: str = _f("入れないもの", "", widget="textarea")
    # 直した後に色を元の絵に合わせる（ComfyUI 標準の ColorTransfer）。初めの値は未検証
    color_match: Literal["none", "reinhard_lab", "mkl_lab", "histogram"] = _f(
        "色を元の絵に合わせる", "reinhard_lab", group="直した後", widget="select",
        labels={"none": "合わせない", "reinhard_lab": "平均と広がり（Lab）", "mkl_lab": "色の分布（Lab・MKL）",
                "histogram": "ヒストグラム"})
    color_strength: float = _f("合わせる強さ", 1.0, group="直した後", widget="slider", ge=0, le=1)
    grow_px: int = _f("範囲を広げる", 6, group="囲んだ範囲", widget="number", unit="px", ge=0, le=256)
    feather_px: int = _f("境目のぼかし", 8, group="囲んだ範囲", widget="number", unit="px", ge=0, le=256)
    padding_px: int = _f("周りの余白", 64, group="囲んだ範囲", widget="number", unit="px", ge=0, le=2048)


# ---------------------------------------------------------------- 下ごしらえ（依頼を受けるとき。image_process_preparation.py が呼ぶ）


@dataclass
class PrepIn:
    """下ごしらえに渡すもの。配列は高さ×幅の 0〜1。"""

    source: bytes | None
    source_size: tuple[int, int] | None
    mask: np.ndarray | None
    protected: np.ndarray | None
    # 形の指定の絵を渡したか
    has_control: bool = False


@dataclass
class PrepOut:
    """下ごしらえの結果。source が None なら元の絵をそのまま送る。redraw・blend が None ならそのマスクは送らない。
    redraw は描くときの白黒のマスク（REDRAW_MASK）、blend は重ねるときのぼかしたマスク（BLEND_MASK）。
    手順が読むマスクだけを返す（送り手は、手順に無い入れ先へ絵を上げようとすると断る）。"""

    source: bytes | None = None
    redraw: np.ndarray | None = None
    blend: np.ndarray | None = None
    protected: np.ndarray | None = None
    # 手順を組むときに使う値（大きさ・切り出し）と、出来上がりの絵と元の絵の画素の対応（geometry）
    info: dict[str, Any] = field(default_factory=dict)


def _check_control(p: Any, i: PrepIn) -> None:
    wants = getattr(p, "control", "none") != "none"
    if wants and not i.has_control:
        raise Invalid("形の指定には絵（purpose=control）が要る")
    if i.has_control and not wants:
        raise Invalid("形の指定の絵があるのに、形の指定が「使わない」")


def _identity(size: tuple[int, int] | None) -> dict[str, Any]:
    return {"source_size": list(size) if size else None, "geometry": {"scale": [1, 1], "offset": [0, 0]}}


def _prep_plain(p: Any, i: PrepIn) -> PrepOut:
    _check_control(p, i)
    return PrepOut(protected=i.protected, info=_identity(i.source_size))


def _prep_inpaint(p: InpaintParams, i: PrepIn) -> PrepOut:
    _check_control(p, i)
    redraw = mk.redraw_mask(i.mask, i.protected, p.grow_px, p.feather_px)
    info = _identity(i.source_size)
    info["crop"] = list(mk.crop_box(redraw, p.padding_px)) if p.only_masked else None
    if not p.only_masked:
        mk.crop_box(redraw, 0)  # 空の範囲を断る
    return PrepOut(redraw=mk.binarize(redraw), blend=redraw, protected=i.protected, info=info)


def _prep_outpaint(p: OutpaintParams, i: PrepIn) -> PrepOut:
    _check_control(p, i)
    if p.unit != "px":
        raise Invalid("描き足すの量は、依頼を受ける前に画素へ直す（resolve_outpaint）")
    l, t, r, b = (int(round(v)) for v in (p.left, p.top, p.right, p.bottom))  # noqa: E741  左・上・右・下
    if l + t + r + b == 0:
        raise Invalid("広げる量がどの辺も0")
    w, h = i.source_size
    redraw = mk.extend_mask(w, h, l, t, r, b, p.feather_px)
    protected = mk.shift_into(i.protected, l, t, r, b)
    redraw = np.where(protected >= 0.5, 0.0, redraw).astype(np.float32)
    padded = mk.pad_image(i.source, l, t, r, b, p.fill)
    return PrepOut(source=padded, redraw=mk.binarize(redraw), blend=redraw, protected=protected,
                   info={"source_size": [w, h], "padded_size": [w + l + r, h + t + b], "margins_px": [l, t, r, b],
                         "geometry": {"scale": [1, 1], "offset": [l, t]}})


def _prep_edit(p: InstructionEditParams, i: PrepIn) -> PrepOut:
    _check_control(p, i)
    info = _identity(i.source_size)
    if i.mask is None:
        info["use_region"] = False
        info["crop"] = None
        return PrepOut(protected=i.protected, info=info)
    redraw = mk.redraw_mask(i.mask, i.protected, p.grow_px, p.feather_px)
    info["use_region"] = True
    info["crop"] = list(mk.crop_box(redraw, p.padding_px))
    # 空の潜在から描くので、描くときのマスクは要らない。重ねるときのマスクだけ送る
    return PrepOut(blend=redraw, protected=i.protected, info=info)


# ---------------------------------------------------------------- 手順を組む（送り手が呼ぶ）


def _sampler(settings: DiffusionSettings | EditSettings, p: _Params) -> Any:
    over = {k: v for k, v in (("steps", p.steps), ("cfg", p.cfg)) if v is not None}
    return settings.model_copy(update={"sampler": settings.sampler.model_copy(update=over)})


def _extras(s: DiffusionSettings, p: Any) -> Extras:
    control = None
    kind = getattr(p, "control", "none")
    if kind != "none":
        if s.controlnet_name is None:
            raise Invalid("このつなぎ先の中身に ControlNet（controlnet_name）が無いので、形の指定を使えない")
        control = ControlSettings(kind=ControlKind.POSE if kind == "pose" else ControlKind.DEPTH if kind == "depth"
                                  else ControlKind.LINE, controlnet_name=s.controlnet_name,
                                  union_type=CONTROL_UNION_TYPES[kind], strength=p.control_strength,
                                  start_percent=0.0, end_percent=p.control_end, invert_image=p.control_invert)
    return Extras(control=control)


def _build_t2i(s: DiffusionSettings, p: TextToImageParams, seed: int, info: dict, prefix: str) -> ComfyNodeGraph:
    return build_text_to_image_process(_sampler(s, p), p.prompt, p.negative_prompt, seed, p.width, p.height, _extras(s, p), prefix)


def _build_i2i(s: DiffusionSettings, p: ImageToImageParams, seed: int, info: dict, prefix: str) -> ComfyNodeGraph:
    return build_image_to_image(_sampler(s, p), p.prompt, p.negative_prompt, seed, p.strength,
                                tuple(info["source_size"]), _extras(s, p), prefix)


def _build_inpaint(s: DiffusionSettings, p: InpaintParams, seed: int, info: dict, prefix: str) -> ComfyNodeGraph:
    crop = None
    if info.get("crop"):
        x, y, w, h = info["crop"]
        crop = CropBox(x, y, w, h, *work_size_for(w, h, s.native_long_side))
    return build_inpaint(_sampler(s, p), p.prompt, p.negative_prompt, seed, p.denoise, p.encode,
                         tuple(info["source_size"]), crop, _extras(s, p), prefix)


def _build_outpaint(s: DiffusionSettings, p: OutpaintParams, seed: int, info: dict, prefix: str) -> ComfyNodeGraph:
    return build_outpaint(_sampler(s, p), p.prompt, p.negative_prompt, seed, p.denoise, p.encode,
                          tuple(info["padded_size"]), _extras(s, p), prefix)


def _build_edit(s: EditSettings, p: InstructionEditParams, seed: int, info: dict, prefix: str) -> ComfyNodeGraph:
    return build_instruction_edit(_sampler(s, p), p.instruction, p.negative_prompt, seed, p.color_match,
                                  p.color_strength, tuple(info["source_size"]), info["use_region"],
                                  tuple(info["crop"]) if info["crop"] else None, prefix)


# ---------------------------------------------------------------- 一覧

Need = Literal["none", "optional", "required"]


@dataclass(frozen=True)
class ImageProcessSpec:
    name: str
    label: str
    # 画面の説明（1行）
    hint: str
    ai_task: str
    ai_action: str
    params_model: type[_Params]
    settings_model: type[BaseModel]
    source: Literal["none", "required"]
    mask: Need
    # 画面のキャンバスで使う道具（mask：囲む、extend：広げる枠）
    canvas_tool: Literal["none", "mask", "extend"]
    prepare: Callable[[Any, PrepIn], PrepOut]
    build: Callable[[Any, Any, int, dict, str], ComfyNodeGraph]
    # 入力欄で初めから開いて出すまとまり（x-group の名前。「基本」はいつも開く）
    open_groups: tuple[str, ...] = ()


SPECS: dict[str, ImageProcessSpec] = {
    s.name: s
    for s in (
        ImageProcessSpec("text_to_image", "文から作る", "指示の文から新しく描く", "drawing", "propose",
                         TextToImageParams, DiffusionSettings, "none", "none", "none", _prep_plain, _build_t2i),
        ImageProcessSpec("image_to_image", "絵から作り直す", "今の絵を元に、指示と変える強さで描き直す", "drawing",
                         "propose", ImageToImageParams, DiffusionSettings, "required", "none", "none", _prep_plain,
                         _build_i2i),
        ImageProcessSpec("variation", "似た別案", "今の絵に近いまま、シードを変えて別の案を出す", "drawing", "propose",
                         VariationParams, DiffusionSettings, "required", "none", "none", _prep_plain, _build_i2i),
        ImageProcessSpec("inpaint", "囲んで直す", "囲んだ所だけ描き直す。人の手の範囲は囲めない", "drawing",
                         "propose", InpaintParams, DiffusionSettings, "required", "required", "mask", _prep_inpaint,
                         _build_inpaint),
        ImageProcessSpec("outpaint", "描き足す", "絵の外側を広げて描く", "drawing", "propose", OutpaintParams,
                         DiffusionSettings, "required", "none", "extend", _prep_outpaint, _build_outpaint,
                         open_groups=("広げる",)),
        ImageProcessSpec("instruction_edit", "指示で直す", "文の指示で直す。囲めば囲んだ所だけ変える", "drawing",
                         "propose", InstructionEditParams, EditSettings, "required", "optional", "mask", _prep_edit,
                         _build_edit),
    )
}


def spec_for(name: str) -> ImageProcessSpec:
    spec = SPECS.get(name)
    if spec is None:
        raise Invalid(f"画像生成の処理 {name} は無い（{', '.join(SPECS)}）")
    return spec


def parse_params(spec: ImageProcessSpec, params: Any) -> _Params:
    try:
        return spec.params_model.model_validate(params)
    except ValueError as e:
        raise Invalid(f"{spec.label} の引数が正しくない: {e}") from e


def parse_settings(spec: ImageProcessSpec, settings: Any) -> BaseModel:
    if settings is None:
        raise Invalid(f"{spec.label} の中身（comfy_graph_settings）が決まっていない")
    try:
        return spec.settings_model.model_validate(settings)
    except ValueError as e:
        raise Invalid(f"{spec.label} の中身（comfy_graph_settings）が正しくない: {e}") from e


def build_prompt(name: str, settings: Any, params: Any, seed: int, info: dict, prefix: str) -> dict[str, Any]:
    spec = spec_for(name)
    return spec.build(parse_settings(spec, settings), parse_params(spec, params), seed, info, prefix).to_prompt()


def describe(spec: ImageProcessSpec) -> dict[str, Any]:
    """画面に渡す処理の説明（入力欄を作る JSON Schema を含む）。"""
    return {"name": spec.name, "label": spec.label, "hint": spec.hint, "ai_task": spec.ai_task,
            "ai_action": spec.ai_action, "source": spec.source, "mask": spec.mask, "canvas_tool": spec.canvas_tool,
            "open_groups": list(spec.open_groups), "params_schema": spec.params_model.model_json_schema()}


# ---------------------------------------------------------------- 描き足すの量を画素へ直す（依頼を受ける前。コマの置き場が要る）


def resolve_outpaint(params: dict[str, Any], placement: dict[str, Any] | None, frame_bbox_mm: tuple | None,
                     image_size: tuple[int, int]) -> dict[str, Any]:
    """mm とコマの枠までを、元の絵の画素の量に直した引数を返す（unit は px）。

    mm と画素の比は、今の置き場（切り抜きの画素と置き場の mm）から決める。回転・傾き・反転のある置き場では、
    辺と向きが合わないので断る。コマの枠までは、絵の全体（切り抜きの外も含む）がコマの枠の外接する四角を覆う量。"""
    p = OutpaintParams.model_validate(params)
    if p.unit == "px":
        return p.model_dump()
    if placement is None:
        raise Invalid("この絵はコマに置かれていない。mm・コマの枠までで広げるには置き場が要る")
    from v3server.name_structure.image_placement import ImagePlacement

    pl = ImagePlacement.model_validate(placement)
    if not pl.is_identity():
        raise Invalid("回転・傾き・反転のある置き場では、mm・コマの枠までで広げられない（画素で指定する）")
    x0, y0, x1, y1 = pl.crop_px
    a, b, c, d = pl.dest_box_mm
    sx, sy = (x1 - x0) / (c - a), (y1 - y0) / (d - b)  # 画素 / mm
    if p.unit == "mm":
        amounts = (p.left * sx, p.top * sy, p.right * sx, p.bottom * sy)
    else:
        if frame_bbox_mm is None:
            raise Invalid("コマの枠が決まっていない")
        fx0, fy0, fx1, fy1 = frame_bbox_mm
        w, h = image_size
        # 絵の全体の mm の四角
        ix0, iy0 = a - x0 / sx, b - y0 / sy
        ix1, iy1 = ix0 + w / sx, iy0 + h / sy
        amounts = (max(0, ix0 - fx0) * sx, max(0, iy0 - fy0) * sy, max(0, fx1 - ix1) * sx, max(0, fy1 - iy1) * sy)
    left, top, right, bottom = (float(int(np.ceil(v - 1e-6))) for v in amounts)
    return {**p.model_dump(), "unit": "px", "left": left, "top": top, "right": right, "bottom": bottom}
