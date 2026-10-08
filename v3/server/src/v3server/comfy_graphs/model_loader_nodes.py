"""画像生成の処理（generation_queue/image_process_registry.py）が使う、モデルを読むノードとサンプラーの設定。

つなぎ先と処理の組ごとの中身（ServiceProcess.comfy_graph_settings）の形をここで決める。値はどれも人が入れる。ここに既定値は置かない
（モデル名は環境ごとに利用者が選ぶ。V3細部の決めごと 12章）。

モデルの読み方は2つ。
- checkpoint：1つのファイルにモデル・文の読み手・VAE が入っている（CheckpointLoaderSimple）
- separate：別々のファイル（UNETLoader・CLIPLoader・VAELoader）。試験の CPU の ComfyUI はこの形（Stable Diffusion 1.5 を分けた3つ）
追加学習（LoRA）は、どちらの読み方にも何個でも重ねられる（LoraLoader）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from typing import TYPE_CHECKING

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph, NodeOutput

if TYPE_CHECKING:
    from v3server.comfy_graphs.controlnet_nodes import ControlSettings


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckpointModel(_Strict):
    kind: Literal["checkpoint"]
    checkpoint_name: str = Field(min_length=1)


class SeparateModel(_Strict):
    kind: Literal["separate"]
    unet_name: str = Field(min_length=1)
    weight_dtype: str = Field(min_length=1)
    clip_name: str = Field(min_length=1)
    # CLIPLoader の type（stable_diffusion・qwen_image など）
    clip_type: str = Field(min_length=1)
    vae_name: str = Field(min_length=1)


class LoraUse(_Strict):
    name: str = Field(min_length=1)
    strength_model: float
    strength_clip: float


class SamplerSettings(_Strict):
    steps: int = Field(ge=1, le=200)
    cfg: float = Field(ge=0, le=50)
    sampler_name: str = Field(min_length=1)
    scheduler: str = Field(min_length=1)


class DiffusionSettings(_Strict):
    """文から絵・絵から作り直す・囲んで直す・描き足すの中身。"""

    model: Annotated[CheckpointModel | SeparateModel, Field(discriminator="kind")]
    loras: list[LoraUse]
    sampler: SamplerSettings
    # このモデルが得意な絵の長い辺（px）。「囲んだ所だけ大きくして直す」で、囲んだ所をこの大きさに拡大して描く。
    # 画面は「作る」の大きさの初めの値にも使う
    native_long_side: int = Field(ge=64, le=4096)
    # 形の指定（線画・落書き・骨格・奥行き）に使う ControlNet のファイル名。多用途版（xinsir union promax。Apache-2.0）を想定。
    # 無ければ null と書く（そのつなぎ先では形の指定を受けない）
    controlnet_name: str | None


@dataclass(frozen=True)
class Extras:
    """処理の引数から決まる、手順に足す物。control は形の指定（ControlNet。controlnet_nodes.py）。"""

    control: "ControlSettings | None"


def add_text_and_extras(g: ComfyNodeGraph, m: LoadedModel, positive_text: str, negative_text: str,
                        extras: Extras) -> tuple[NodeOutput, NodeOutput, NodeOutput]:
    """文を読み、形の指定を掛けて (model, positive, negative) を返す。形の指定の絵は名前のノード control。"""
    from v3server.comfy_graphs.controlnet_nodes import control_conditioning
    from v3server.comfy_graphs.source_and_masks import CONTROL, load_image

    pos = g.add("CLIPTextEncode", text=positive_text, clip=m.clip)[0]
    neg = g.add("CLIPTextEncode", text=negative_text, clip=m.clip)[0]
    model = m.model
    if extras.control is not None:
        applied = control_conditioning(g, pos, neg, extras.control, load_image(g, CONTROL))
        pos, neg = applied[0], applied[1]
    return model, pos, neg


@dataclass(frozen=True)
class LoadedModel:
    model: NodeOutput
    clip: NodeOutput
    vae: NodeOutput


def add_model_loaders(g: ComfyNodeGraph, settings: DiffusionSettings) -> LoadedModel:
    m = settings.model
    if isinstance(m, CheckpointModel):
        ckpt = g.add("CheckpointLoaderSimple", ckpt_name=m.checkpoint_name)
        model, clip, vae = ckpt[0], ckpt[1], ckpt[2]
    else:
        model = g.add("UNETLoader", unet_name=m.unet_name, weight_dtype=m.weight_dtype)[0]
        clip = g.add("CLIPLoader", clip_name=m.clip_name, type=m.clip_type)[0]
        vae = g.add("VAELoader", vae_name=m.vae_name)[0]
    for lora in settings.loras:
        n = g.add("LoraLoader", model=model, clip=clip, lora_name=lora.name, strength_model=lora.strength_model,
                  strength_clip=lora.strength_clip)
        model, clip = n[0], n[1]
    return LoadedModel(model, clip, vae)


def add_sampler(g: ComfyNodeGraph, s: SamplerSettings, model: NodeOutput, positive: NodeOutput,
                negative: NodeOutput, latent: NodeOutput, seed: int, denoise: float) -> NodeOutput:
    return g.add("KSampler", model=model, positive=positive, negative=negative, latent_image=latent, seed=seed,
                 steps=s.steps, cfg=s.cfg, sampler_name=s.sampler_name, scheduler=s.scheduler, denoise=denoise)[0]
