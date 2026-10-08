"""文から絵を作る基本の手順（SDXL の checkpoint 1つ）。移す元は試作 `common/comfy.py` の `t2i`。

モデルのファイル名・サンプラーの設定は呼ぶ側が設定から渡す。ここに既定値は置かない。
制御（`controlnet_nodes.py`）と範囲ごとの文（`regional_prompt_nodes.py`）は、
ここで返す KSampler の positive・negative をつなぎ替えて足す。
"""
from __future__ import annotations

from dataclasses import dataclass

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph, Node, NodeOutput


@dataclass(frozen=True)
class SamplerSettings:
    """KSampler に渡す設定。どれも設定から読む。"""

    checkpoint_name: str
    steps: int
    cfg: float
    sampler_name: str
    scheduler: str


@dataclass(frozen=True)
class TextToImageGraph:
    """組んだ手順と、後からつなぎ替える要所のノード。"""

    graph: ComfyNodeGraph
    checkpoint: Node
    positive: Node
    negative: Node
    sampler: Node
    decoded: Node
    save: Node

    @property
    def model(self) -> NodeOutput:
        return self.checkpoint[0]

    @property
    def clip(self) -> NodeOutput:
        return self.checkpoint[1]

    @property
    def vae(self) -> NodeOutput:
        return self.checkpoint[2]


def build_text_to_image(
    settings: SamplerSettings,
    positive_text: str,
    negative_text: str,
    seed: int,
    width: int,
    height: int,
    filename_prefix: str,
) -> TextToImageGraph:
    """文から絵を1枚作る手順を組む。

    言葉だけでは人物はほとんどコマの真ん中に立つ（試作 p14・p15）。位置を決めたいときは骨格の制御を足す。
    """
    g = ComfyNodeGraph()
    ckpt = g.add('CheckpointLoaderSimple', ckpt_name=settings.checkpoint_name)
    pos = g.add('CLIPTextEncode', text=positive_text, clip=ckpt[1])
    neg = g.add('CLIPTextEncode', text=negative_text, clip=ckpt[1])
    latent = g.add('EmptyLatentImage', width=width, height=height, batch_size=1)
    sampler = g.add(
        'KSampler',
        model=ckpt[0], positive=pos[0], negative=neg[0], latent_image=latent[0],
        seed=seed, steps=settings.steps, cfg=settings.cfg,
        sampler_name=settings.sampler_name, scheduler=settings.scheduler, denoise=1.0,
    )
    decoded = g.add('VAEDecode', samples=sampler[0], vae=ckpt[2])
    save = g.add('SaveImage', images=decoded[0], filename_prefix=filename_prefix)
    return TextToImageGraph(g, ckpt, pos, neg, sampler, decoded, save)


def build_text_to_image_process(settings: 'DiffusionSettings', positive_text: str, negative_text: str, seed: int,
                                width: int, height: int, extras: 'Extras', filename_prefix: str) -> ComfyNodeGraph:
    """画像生成の処理「文から作る」（generation_queue/image_process_registry.py）の手順。
    上の build_text_to_image と同じ形で、モデルの読み方（checkpoint か別々のファイルか）と追加学習を中身から決める。"""
    from v3server.comfy_graphs.model_loader_nodes import add_model_loaders, add_sampler, add_text_and_extras
    from v3server.comfy_graphs.source_and_masks import save

    g = ComfyNodeGraph()
    m = add_model_loaders(g, settings)
    model, pos, neg = add_text_and_extras(g, m, positive_text, negative_text, extras)
    latent = g.add('EmptyLatentImage', width=width, height=height, batch_size=1)[0]
    sampled = add_sampler(g, settings.sampler, model, pos, neg, latent, seed, 1.0)
    save(g, g.add('VAEDecode', samples=sampled, vae=m.vae)[0], filename_prefix)
    return g
