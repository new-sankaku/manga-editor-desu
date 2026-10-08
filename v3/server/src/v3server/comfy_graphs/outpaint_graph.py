"""描き足す（アウトペイント）。絵の外側を広げて描く。

広げた絵（元の絵を広げた分の真ん中に置き、外側を端を伸ばす・折り返す・灰色で埋めたもの）と、広げた所のマスク（内側へぼかしの幅だけ
にじませたもの）は、サーバーが依頼を受けるときに作る（generation_queue/image_process_inputs.py）。
ComfyUI の側では、広げた絵を元の絵として「囲んで直す」と同じ手順で描く。人の手の範囲は広げた絵の上の位置へずらして貼り戻す。
"""
from __future__ import annotations

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph
from v3server.comfy_graphs.inpaint_graph import Encode, build_inpaint
from v3server.comfy_graphs.model_loader_nodes import DiffusionSettings, Extras


def build_outpaint(settings: DiffusionSettings, positive_text: str, negative_text: str, seed: int, denoise: float,
                   encode: Encode, padded_size: tuple[int, int], extras: Extras,
                   filename_prefix: str) -> ComfyNodeGraph:
    return build_inpaint(settings, positive_text, negative_text, seed, denoise, encode, padded_size, None, extras,
                         filename_prefix)
