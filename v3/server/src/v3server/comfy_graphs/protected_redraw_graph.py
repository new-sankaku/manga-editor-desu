"""描き直しと、人の範囲の貼り戻し。移す元は試作 p05 `graph`。

描き直す範囲のマスクだけでは、範囲の外（人の範囲）でも画素の78%が変わった。
描き直した後に、元の画素で貼り戻すと0%になった。だから貼り戻しは必ず入れる。外す引数は作らない（設計 9.2）。
描き直す範囲が誤って人の範囲に掛かると、貼り戻しても人の範囲の14%が変わった。
そのため人の範囲のマスクを別に受け取り、描き直す範囲から引いてから使う（引く手は試作では未検証）。
"""
from __future__ import annotations

from dataclasses import dataclass

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph, Node
from v3server.comfy_graphs.text_to_image_graph import SamplerSettings

# マスクの画像は白黒で、赤のチャンネルを読む
MASK_CHANNEL = 'red'


@dataclass(frozen=True)
class ProtectedRedrawGraph:
    """組んだ手順と要所のノード。"""

    graph: ComfyNodeGraph
    checkpoint: Node
    sampler: Node
    redraw_mask: Node   # 人の範囲を引いた後の、実際に描き直す範囲
    paste_back: Node    # 元の画素で貼り戻すノード
    save: Node


def build_protected_redraw(
    settings: SamplerSettings,
    image_name: str,
    redraw_mask_name: str,
    protected_mask_name: str | None,
    positive_text: str,
    negative_text: str,
    seed: int,
    denoise: float,
    filename_prefix: str,
) -> ProtectedRedrawGraph:
    """元の絵の一部を描き直し、描き直す範囲の外を元の画素に戻す手順を組む。

    redraw_mask_name：白が描き直す範囲。
    protected_mask_name：白が人の範囲（確定印のある所）。人の範囲が無いときは None を明示する。
      渡したときは、描き直す範囲からこの範囲を引く。
    画像の名前はどれも ComfyUI の input に上げた名前（上げるのは `service_senders/`）。
    """
    g = ComfyNodeGraph()
    ckpt = g.add('CheckpointLoaderSimple', ckpt_name=settings.checkpoint_name)
    pos = g.add('CLIPTextEncode', text=positive_text, clip=ckpt[1])
    neg = g.add('CLIPTextEncode', text=negative_text, clip=ckpt[1])
    source = g.add('LoadImage', image=image_name)
    redraw_img = g.add('LoadImage', image=redraw_mask_name)
    mask = g.add('ImageToMask', image=redraw_img[0], channel=MASK_CHANNEL)
    if protected_mask_name is not None:
        protected_img = g.add('LoadImage', image=protected_mask_name)
        protected = g.add('ImageToMask', image=protected_img[0], channel=MASK_CHANNEL)
        mask = g.add('MaskComposite', destination=mask[0], source=protected[0], x=0, y=0, operation='subtract')
    encoded = g.add('VAEEncode', pixels=source[0], vae=ckpt[2])
    noise_masked = g.add('SetLatentNoiseMask', samples=encoded[0], mask=mask[0])
    sampler = g.add(
        'KSampler',
        model=ckpt[0], positive=pos[0], negative=neg[0], latent_image=noise_masked[0],
        seed=seed, steps=settings.steps, cfg=settings.cfg,
        sampler_name=settings.sampler_name, scheduler=settings.scheduler, denoise=denoise,
    )
    decoded = g.add('VAEDecode', samples=sampler[0], vae=ckpt[2])
    paste_back = g.add('ImageCompositeMasked', destination=source[0], source=decoded[0], x=0, y=0,
                       resize_source=False, mask=mask[0])
    save = g.add('SaveImage', images=paste_back[0], filename_prefix=filename_prefix)
    return ProtectedRedrawGraph(g, ckpt, sampler, mask, paste_back, save)
