"""書き出しの大きさへの拡大。移す元は試作 p04 `up_graph`。

試作 p04（832x1216 → B5・600dpi 4300x6070）の結果：
- lanczos だけ：網点のトーンは残るが線がぼやける。
- 4x-UltraSharp：トーンが半分残り、斜めの線の模様に変わる。
- RealESRGAN（アニメ向け）：網点が消えて平らな灰色になる。線はいちばんくっきり。
白黒の原稿では、拡大の前にトーンを分けておくか（`layer_split/`）、拡大の後に網点を貼り直す工程が要る。
くっきり度（2次微分の分散）で拡大の方法を選ぶと、トーンを壊すものを選んでしまう。
"""
from __future__ import annotations

from dataclasses import dataclass

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph, Node

# 拡大のモデルの後で、狙いの大きさにそろえる方法（ComfyUI の ImageScale の選択肢）
FINAL_RESIZE_METHOD = 'lanczos'


@dataclass(frozen=True)
class UpscaleGraph:
    graph: ComfyNodeGraph
    resize: Node
    save: Node


def build_upscale(image_name: str, upscale_model_name: str | None, width: int, height: int, filename_prefix: str) -> UpscaleGraph:
    """絵を狙いの大きさに拡大する手順を組む。

    upscale_model_name：拡大のモデルのファイル名（設定から渡す）。モデルを使わず lanczos だけにするときは None を明示する。
    """
    g = ComfyNodeGraph()
    src = g.add('LoadImage', image=image_name)[0]
    if upscale_model_name is not None:
        loader = g.add('UpscaleModelLoader', model_name=upscale_model_name)
        src = g.add('ImageUpscaleWithModel', upscale_model=loader[0], image=src)[0]
    resize = g.add('ImageScale', image=src, upscale_method=FINAL_RESIZE_METHOD, width=width, height=height, crop='disabled')
    save = g.add('SaveImage', images=resize[0], filename_prefix=filename_prefix)
    return UpscaleGraph(g, resize, save)
