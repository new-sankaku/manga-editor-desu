"""範囲ごとに文を当てる（2人を左右に分けるなど）。移す元は試作 p23 `regional`。

KSampler に今つながっている positive に、範囲付きの文を足してつなぎ替える。
制御（`controlnet_nodes.py`）の前でも後でも呼べる。
"""
from __future__ import annotations

from dataclasses import dataclass

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph, Node

# ConditioningSetArea の幅・高さ・位置は 8 画素刻み（ComfyUI の入力の定義）
AREA_STEP = 8


@dataclass(frozen=True)
class RegionPrompt:
    """1つの範囲の文。位置と大きさは生成する絵の画素。"""

    text: str
    x: int
    y: int
    width: int
    height: int
    strength: float


def left_right_regions(width: int, height: int, left_text: str, right_text: str, strength: float) -> list[RegionPrompt]:
    """絵を左右の半分に分け、それぞれに文を当てる（試作 p23 の分け方）。"""
    half = width // 2
    return [
        RegionPrompt(left_text, 0, 0, half, height, strength),
        RegionPrompt(right_text, half, 0, width - half, height, strength),
    ]


def regional_positive(graph: ComfyNodeGraph, positive, clip, regions: list[RegionPrompt]):
    """全体の文（positive）に範囲ごとの文を足した ConditioningCombine の出力を返す。clip は CLIP の出力。
    model_loader_nodes.add_text_and_extras が、処理の引数 regions があるときに呼ぶ（形の指定より前）。"""
    _check(regions)
    combined = None
    for r in regions:
        enc = graph.add('CLIPTextEncode', text=r.text, clip=clip)
        area = graph.add('ConditioningSetArea', conditioning=enc[0], width=r.width, height=r.height,
                         x=r.x, y=r.y, strength=r.strength)
        combined = area[0] if combined is None else graph.add(
            'ConditioningCombine', conditioning_1=combined, conditioning_2=area[0])[0]
    return graph.add('ConditioningCombine', conditioning_1=positive, conditioning_2=combined)[0]


def _check(regions: list[RegionPrompt]) -> None:
    if not regions:
        raise ValueError('範囲が1つもありません')
    for r in regions:
        for name in ('x', 'y', 'width', 'height'):
            if getattr(r, name) % AREA_STEP:
                raise ValueError(f'範囲の {name}={getattr(r, name)} が {AREA_STEP} 画素刻みではありません')


def apply_regional_prompts(graph: ComfyNodeGraph, sampler: Node, clip_source: Node, regions: list[RegionPrompt]) -> Node:
    """範囲ごとの文を足し、全体の文と合わせた ConditioningCombine を返す。

    clip_source は CLIP を出すノード（CheckpointLoaderSimple なら出力1番）。
    試作 p23：カラーの2人は左右の範囲ごとの文で 6/6 正しく分かれた（1つの文に全部だと0）。
    白黒では 2/6〜3/6 で、ほかは複数コマのページの絵になった。白黒の2人はこれだけでは足りない。
    """
    if not regions:
        raise ValueError('範囲が1つもありません')
    for r in regions:
        for name in ('x', 'y', 'width', 'height'):
            if getattr(r, name) % AREA_STEP:
                raise ValueError(f'範囲の {name}={getattr(r, name)} が {AREA_STEP} 画素刻みではありません')
    combined = None
    for r in regions:
        enc = graph.add('CLIPTextEncode', text=r.text, clip=clip_source[1])
        area = graph.add('ConditioningSetArea', conditioning=enc[0], width=r.width, height=r.height,
                         x=r.x, y=r.y, strength=r.strength)
        combined = area[0] if combined is None else graph.add(
            'ConditioningCombine', conditioning_1=combined, conditioning_2=area[0])[0]
    whole = graph.add('ConditioningCombine', conditioning_1=graph.input_link(sampler, 'positive'), conditioning_2=combined)
    graph.connect(sampler, 'positive', whole[0])
    return whole
