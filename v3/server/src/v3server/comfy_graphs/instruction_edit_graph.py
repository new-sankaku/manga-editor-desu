"""指示で直す（「笑顔にして」「背景を夜に」など）。Qwen-Image 2.1 を ComfyUI 標準の部品で組む。

試作 p26（v3poc/p26_edit/run.py）で対象の PC の ComfyUI に流した組み方をそのまま使う：
UNETLoader → QwenImage21Cache、CLIPLoader（type=qwen_image）、TextEncodeQwenImage21 に元の絵を images.image_1 で渡す。
TextEncodeQwenImage21 の3つ目の出力は、元の絵の大きさの空の潜在（ほかの大きさでは直す位置がずれる、とノードの説明にある）。
空の潜在から描くので、描き直す強さ（denoise）はいつも 1.0。
利用条件は Qwen Research License（非商用）。利用者は商用に使わないので使う（2026-10-08 の判断。V3検証の結果 1-15）。

直した後の処理：
- 出力は 32 の倍数に丸められる（V3検証の結果 1-15。1216→1248）。切り出した大きさへ戻す
- 色を元の絵に合わせる（ComfyUI 標準の ColorTransfer。参照は切り出した元の絵）。p26 で背景だけ色が付いた件への手当て。効き方は未検証
- 囲んだ範囲があれば、なじませるマスク（blend_mask）で元の絵に重ね、範囲の外は元の画素に戻す
- 人の手の範囲は必ず元の画素で貼り戻す
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph
from v3server.comfy_graphs.model_loader_nodes import LoraUse, SamplerSettings, _Strict, add_sampler
from v3server.comfy_graphs.source_and_masks import (
    BLEND_MASK,
    PROTECTED_MASK,
    SOURCE,
    composite,
    load_image,
    load_mask,
    paste_back_protected,
    resize,
    save,
)

ColorMatch = Literal["none", "reinhard_lab", "mkl_lab", "histogram"]


class EditSettings(_Strict):
    """指示で直すの中身。値はどれも人が入れる（ComfyUI の models の下の名前）。p26 の値は
    unet qwen_image_2.1_int8_convrot・clip qwen3vl_8b_int8_convrot・vae qwen_image_2.1_vae_bf16・25手・cfg 1.0・euler・simple。"""

    unet_name: str = Field(min_length=1)
    weight_dtype: str = Field(min_length=1)
    clip_name: str = Field(min_length=1)
    # CLIPLoader の type。Qwen-Image 2.1 では qwen_image
    clip_type: str = Field(min_length=1)
    vae_name: str = Field(min_length=1)
    # モデルにだけ効く追加学習。strength_clip は使わない
    loras: list[LoraUse]
    # TextEncodeQwenImage21 の resolution（元の絵をおよそ resolution×resolution の画素にして渡す。32 の倍数）
    resolution: int = Field(ge=0, le=4096, multiple_of=32)
    # QwenImage21Cache の device・dtype
    cache_device: Literal["auto", "gpu", "cpu", "off"]
    cache_dtype: str = Field(min_length=1)
    sampler: SamplerSettings


def build_instruction_edit(settings: EditSettings, instruction: str, negative_text: str, seed: int,
                           color_match: ColorMatch, color_strength: float, source_size: tuple[int, int],
                           use_region: bool, crop: tuple[int, int, int, int] | None,
                           filename_prefix: str) -> ComfyNodeGraph:
    """crop（x, y, 幅, 高さ）があれば、そこだけ切り出してモデルに渡し、戻すときに元の大きさへ直して同じ場所に重ねる。"""
    if crop is not None and not use_region:
        raise ValueError("切り出しは囲んだ範囲があるときだけ")
    g = ComfyNodeGraph()
    model = g.add('UNETLoader', unet_name=settings.unet_name, weight_dtype=settings.weight_dtype)[0]
    for lora in settings.loras:
        model = g.add('LoraLoaderModelOnly', model=model, lora_name=lora.name, strength_model=lora.strength_model)[0]
    model = g.add('QwenImage21Cache', model=model, device=settings.cache_device, dtype=settings.cache_dtype)[0]
    clip = g.add('CLIPLoader', clip_name=settings.clip_name, type=settings.clip_type, device='default')[0]
    vae = g.add('VAELoader', vae_name=settings.vae_name)[0]
    src = load_image(g, SOURCE)
    protected = load_mask(g, PROTECTED_MASK)
    part, (pw, ph) = src, source_size
    if crop is not None:
        x, y, pw, ph = crop
        part = g.add('ImageCrop', image=src, width=pw, height=ph, x=x, y=y)[0]
    enc = g.add('TextEncodeQwenImage21', clip=clip, prompt=instruction, negative_prompt=negative_text,
                resolution=settings.resolution, vae=vae, **{'images.image_1': part})
    decoded = g.add('VAEDecode', samples=add_sampler(g, settings.sampler, model, enc[0], enc[1], enc[2], seed, 1.0),
                    vae=vae)[0]
    out = resize(g, decoded, pw, ph)
    if color_match != 'none':
        out = g.add('ColorTransfer', image_target=out, image_ref=part, method=color_match, source_stats='per_frame',
                    strength=color_strength)[0]
    if use_region:
        blend = load_mask(g, BLEND_MASK)
        if crop is not None:
            x, y, _, _ = crop
            out = composite(g, src, out, g.add('CropMask', mask=blend, x=x, y=y, width=pw, height=ph)[0], x, y)
        else:
            out = composite(g, src, out, blend)
    save(g, paste_back_protected(g, out, src, protected), filename_prefix)
    return g
