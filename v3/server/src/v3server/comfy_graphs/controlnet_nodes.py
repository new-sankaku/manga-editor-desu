"""骨格・線画・奥行きの制御（ControlNet）を、KSampler の手前に差し込む。

移す元は試作 p14 `g_pose`・p18 `graph`（制御の部分）・p20 `with_line`。3か所で同じ組み方だったものを1つにした。
KSampler に今つながっている positive・negative を受けて制御を掛け、KSampler をつなぎ替える。
何度呼んでも制御が鎖のようにつながるので、骨格と奥行きを重ねることもできる（重ねたときの効き方は未検証）。

効かなかったので移さない手：線画の制御でラフを渡す（p08）、参照画像の部品 IP-Adapter（p09・p17・p18）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph, Node, NodeOutput


class ControlKind(Enum):
    """制御で渡す図の種類。"""

    POSE = 'pose'    # 骨格の図（`pose_skeleton_image.py`）
    LINE = 'line'    # 線画（3Dの線画、線画を抜いた絵）
    DEPTH = 'depth'  # 奥行きの図（近いほど白。`background_scene3d/`）


@dataclass(frozen=True)
class ControlSettings:
    """制御1つの設定。モデルのファイル名と多用途版の種類名は設定から渡す。

    union_type：多用途版（xinsir union など）のときに SetUnionControlNetType に渡す種類名。
      専用のモデルのときは None を明示する。
    invert_image：図を白黒反転してから渡すか。
      試作 p20 は白地に黒い線の線画を反転して渡した（制御は黒地に白い線を受け取るため）。
      p18 は 3D の白地に黒い線画を反転せずに渡し、線の重なり 0.97 だった。どちらが良いかは未検証。
    """

    kind: ControlKind
    controlnet_name: str
    union_type: str | None
    strength: float
    start_percent: float
    end_percent: float
    invert_image: bool


def insert_control(graph: ComfyNodeGraph, sampler: Node, control: ControlSettings, image_name: str) -> Node:
    """制御を1つ差し込み、ControlNetApplyAdvanced のノードを返す。

    image_name は ComfyUI の input に上げた画像の名前（上げるのは `service_senders/`）。
    骨格（p14）：Illustrious 系の checkpoint では windsingai の骨格が横長・縦長・標準で 9/9 だった。
      xinsir 系は横長で人物の周りに白い縁取りが出た。thibaud の骨格は非営利だけなので使わない。
    奥行き・線画（p18）：壁・床・机・道の並びは向きを変えても揃うが、壁に何を描くかは揃わない。
    線画（p20）：線画から作ったトーンの絵に、特徴の言葉の色が漏れた。
    """
    image = graph.add('LoadImage', image=image_name)
    apply = control_conditioning(graph, graph.input_link(sampler, 'positive'), graph.input_link(sampler, 'negative'),
                                 control, image[0])
    graph.connect(sampler, 'positive', apply[0])
    graph.connect(sampler, 'negative', apply[1])
    return apply


def control_conditioning(graph: ComfyNodeGraph, positive: NodeOutput, negative: NodeOutput,
                         control: ControlSettings, image_out: NodeOutput) -> Node:
    """positive・negative に制御を掛けた ControlNetApplyAdvanced のノード（[0] が positive、[1] が negative）。
    insert_control と、画像生成の処理（generation_queue/image_process_registry.py）の両方が使う。"""
    cn_out = graph.add('ControlNetLoader', control_net_name=control.controlnet_name)[0]
    if control.union_type is not None:
        cn_out = graph.add('SetUnionControlNetType', control_net=cn_out, type=control.union_type)[0]
    if control.invert_image:
        image_out = graph.add('ImageInvert', image=image_out)[0]
    return graph.add(
        'ControlNetApplyAdvanced',
        positive=positive,
        negative=negative,
        control_net=cn_out,
        image=image_out,
        strength=control.strength,
        start_percent=control.start_percent,
        end_percent=control.end_percent,
    )
