"""絵から作り直す（文の指示と変える強さ）。元の絵を VAE で潜在に移し、変える強さ（denoise）だけ描き直す。
人の手の範囲は最後に元の画素で貼り戻す（source_and_masks.py）。出来上がりは元の絵と同じ大きさ。"""
from __future__ import annotations

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph
from v3server.comfy_graphs.model_loader_nodes import DiffusionSettings, Extras, add_model_loaders, add_sampler, add_text_and_extras
from v3server.comfy_graphs.source_and_masks import (
    PROTECTED_MASK,
    SOURCE,
    load_image,
    load_mask,
    multiple_of_8,
    paste_back_protected,
    resize,
    save,
)


def build_image_to_image(settings: DiffusionSettings, positive_text: str, negative_text: str, seed: int,
                         strength: float, source_size: tuple[int, int], extras: Extras, filename_prefix: str) -> ComfyNodeGraph:
    g = ComfyNodeGraph()
    m = add_model_loaders(g, settings)
    src = load_image(g, SOURCE)
    protected = load_mask(g, PROTECTED_MASK)
    w, h = source_size
    w8, h8 = multiple_of_8(w), multiple_of_8(h)
    pixels = src if (w8, h8) == (w, h) else resize(g, src, w8, h8)
    latent = g.add('VAEEncode', pixels=pixels, vae=m.vae)[0]
    model, pos, neg = add_text_and_extras(g, m, positive_text, negative_text, extras)
    decoded = g.add('VAEDecode', samples=add_sampler(g, settings.sampler, model, pos, neg, latent, seed, strength),
                    vae=m.vae)[0]
    if (w8, h8) != (w, h):
        decoded = resize(g, decoded, w, h)
    save(g, paste_back_protected(g, decoded, src, protected), filename_prefix)
    return g
