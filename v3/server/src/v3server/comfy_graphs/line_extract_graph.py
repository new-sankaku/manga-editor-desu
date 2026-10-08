"""絵から線画を抜く。移す元は試作 p20 `extract`。

前処理のノードの名前（comfyui_controlnet_aux の Manga2Anime_LineArt_Preprocessor など）は設定から渡す。
出てくる線画は黒地に白い線。線・ベタ・トーンに分けるときは `layer_split/` にそのまま渡せる。
"""
from __future__ import annotations

from dataclasses import dataclass

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph, Node


@dataclass(frozen=True)
class LineExtractGraph:
    graph: ComfyNodeGraph
    extract: Node
    save: Node


def build_line_extract(image_name: str, preprocessor_class_type: str, resolution: int, filename_prefix: str) -> LineExtractGraph:
    """線画を抜く手順を組む。

    試作 p20：Manga2Anime の線はきれいで、AnimeLineArt は網点の模様まで線として拾った。
    """
    g = ComfyNodeGraph()
    src = g.add('LoadImage', image=image_name)
    extract = g.add(preprocessor_class_type, image=src[0], resolution=resolution)
    save = g.add('SaveImage', images=extract[0], filename_prefix=filename_prefix)
    return LineExtractGraph(g, extract, save)
