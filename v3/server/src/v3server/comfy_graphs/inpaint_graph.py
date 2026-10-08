"""囲んで直す（インペイント）。マスクはサーバーが描いた2つ（generation_queue/image_process_inputs.py）：
- redraw_mask：広げる→ぼかす→人の手の範囲を引く→白黒にした物。描くとき（潜在のノイズの範囲）に使う
- blend_mask：白黒にする前の物（ぼかしの幅で 1→0）。描いた絵を元の絵に重ねるときに使う

- 潜在の作り方（encode）
  - noise_mask：元の絵を VAE で移し、範囲にだけノイズを掛ける（SetLatentNoiseMask）。変える強さを1より下げると元の形が残る
  - inpaint_encode：範囲を灰色にしてから移す（VAEEncodeForInpaint）。今のアプリの既定の手順と同じ。強さは1で使う物
    （広げる量はサーバーが描いたマスクに入っているので grow_mask_by は0）
- 囲んだ所だけ大きくして直す（crop）：範囲の周り（余白つき）を切り出し、モデルの得意な大きさへ拡大して描き、元の大きさへ戻して
  元の絵の同じ場所に重ねる。小さい範囲を細かく描くため
- 描いた絵は、なじませるマスクで元の絵に重ねる（範囲の外は元の画素のまま）。最後に人の手の範囲を元の画素で貼り戻す
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph
from v3server.comfy_graphs.model_loader_nodes import (
    DiffusionSettings,
    Extras,
    add_model_loaders,
    add_sampler,
    add_text_and_extras,
)
from v3server.comfy_graphs.source_and_masks import (
    BLEND_MASK,
    PROTECTED_MASK,
    REDRAW_MASK,
    SOURCE,
    composite,
    load_image,
    load_mask,
    mask_resize,
    multiple_of_8,
    paste_back_protected,
    resize,
    save,
)

Encode = Literal["noise_mask", "inpaint_encode"]


@dataclass(frozen=True)
class CropBox:
    """元の絵の画素の切り出し（x, y, 幅, 高さ）と、描くときの大きさ（8の倍数）。"""

    x: int
    y: int
    width: int
    height: int
    work_width: int
    work_height: int


def work_size_for(width: int, height: int, long_side: int) -> tuple[int, int]:
    """切り出した所を、長い辺が long_side になるように拡大縮小した大きさ（8の倍数）。"""
    k = long_side / max(width, height)
    return multiple_of_8(round(width * k)), multiple_of_8(round(height * k))


def build_inpaint(settings: DiffusionSettings, positive_text: str, negative_text: str, seed: int, denoise: float,
                  encode: Encode, source_size: tuple[int, int], crop: CropBox | None, extras: Extras,
                  filename_prefix: str) -> ComfyNodeGraph:
    g = ComfyNodeGraph()
    m = add_model_loaders(g, settings)
    src = load_image(g, SOURCE)
    redraw = load_mask(g, REDRAW_MASK)
    blend = load_mask(g, BLEND_MASK)
    protected = load_mask(g, PROTECTED_MASK)
    w, h = source_size
    if crop is not None:
        part = g.add('ImageCrop', image=src, width=crop.width, height=crop.height, x=crop.x, y=crop.y)[0]
        part_mask = g.add('CropMask', mask=redraw, x=crop.x, y=crop.y, width=crop.width, height=crop.height)[0]
        part_blend = g.add('CropMask', mask=blend, x=crop.x, y=crop.y, width=crop.width, height=crop.height)[0]
        tw, th = crop.work_width, crop.work_height
        pixels, work_mask = resize(g, part, tw, th), mask_resize(g, part_mask, tw, th)
    else:
        tw, th = multiple_of_8(w), multiple_of_8(h)
        same = (tw, th) == (w, h)
        pixels = src if same else resize(g, src, tw, th)
        work_mask = redraw if same else mask_resize(g, redraw, tw, th)
    if encode == 'noise_mask':
        encoded = g.add('VAEEncode', pixels=pixels, vae=m.vae)[0]
        latent = g.add('SetLatentNoiseMask', samples=encoded, mask=work_mask)[0]
    else:
        latent = g.add('VAEEncodeForInpaint', pixels=pixels, vae=m.vae, mask=work_mask, grow_mask_by=0)[0]
    model, pos, neg = add_text_and_extras(g, m, positive_text, negative_text, extras)
    decoded = g.add('VAEDecode', samples=add_sampler(g, settings.sampler, model, pos, neg, latent, seed, denoise),
                    vae=m.vae)[0]
    if crop is not None:
        merged = composite(g, src, resize(g, decoded, crop.width, crop.height), part_blend, crop.x, crop.y)
    else:
        merged = composite(g, src, decoded if (tw, th) == (w, h) else resize(g, decoded, w, h), blend)
    save(g, paste_back_protected(g, merged, src, protected), filename_prefix)
    return g
