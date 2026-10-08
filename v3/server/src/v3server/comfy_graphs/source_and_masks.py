"""元の絵・描き直す範囲・人の手の範囲を読むノードと、人の手の範囲を元の画素で貼り戻すノード。
絵から作り直す・囲んで直す・描き足す・指示で直すが共通に使う。

- 読む絵のノードは名前で置く（source・redraw_mask・protected_mask）。送り手（service_senders/comfyui_sender.py）が
  /upload/image に上げた名前を、この名前のノードの image に入れる。入力名の一致で書き換えないので、マスクのノードに
  元の絵が入ることは起きない（ai-verification.md 1.1 の原因A）
- マスクの絵は白黒で、赤のチャンネルを読む（ImageToMask）。アルファを読むと値が反転し、不透明な PNG では全面0になる
  （ai-verification.md 1.1 の原因B）
- マスクの中身（広げる・ぼかす・人の手の範囲を引く）はサーバーが依頼を受けるときに描く
  （generation_queue/image_process_inputs.py）。ここでは読んで使うだけ
- 人の手の範囲は、出来上がった絵に元の画素で必ず貼り戻す（試作 p05：描き直す範囲の指定だけでは人の範囲の78%の画素が変わり、
  貼り戻すと0%）。外す引数は作らない
"""
from __future__ import annotations

from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph, NodeOutput

SOURCE = "source"
REDRAW_MASK = "redraw_mask"
# なじませるマスク（ぼかしの幅で 1→0。人の手の範囲は 0）。描いた絵を元の絵に重ねるときに使う。描くときは REDRAW_MASK（白黒）
BLEND_MASK = "blend_mask"
PROTECTED_MASK = "protected_mask"
# マスクの絵は白黒。赤のチャンネルを読む
MASK_CHANNEL = "red"
CONTROL = "control"
# 大きさをそろえる方法（ComfyUI の ImageScale の選択肢）
RESIZE_METHOD = "lanczos"
# マスクの大きさをそろえる方法。lanczos は境目で 0〜1 の外へはみ出す（行き過ぎ）ので、マスクには使わない
MASK_RESIZE_METHOD = "bilinear"


def load_image(g: ComfyNodeGraph, name: str) -> NodeOutput:
    """送り手が上げた絵を読むノード。image は送り手が入れる（ここでは空）。"""
    return g.add_named(name, "LoadImage", image="")[0]


def load_mask(g: ComfyNodeGraph, name: str) -> NodeOutput:
    return g.add("ImageToMask", image=load_image(g, name), channel=MASK_CHANNEL)[0]


def resize(g: ComfyNodeGraph, image: NodeOutput, width: int, height: int) -> NodeOutput:
    return g.add("ImageScale", image=image, upscale_method=RESIZE_METHOD, width=width, height=height,
                 crop="disabled")[0]


def mask_resize(g: ComfyNodeGraph, mask: NodeOutput, width: int, height: int) -> NodeOutput:
    as_image = g.add("MaskToImage", mask=mask)[0]
    scaled = g.add("ImageScale", image=as_image, upscale_method=MASK_RESIZE_METHOD, width=width, height=height,
                   crop="disabled")[0]
    return g.add("ImageToMask", image=scaled, channel=MASK_CHANNEL)[0]


def multiple_of_8(n: int) -> int:
    """VAE は 8 の倍数に切り詰めるので、送る前に近い 8 の倍数へ拡大縮小する（切り詰めると位置がずれる）。"""
    return max(8, int(round(n / 8)) * 8)


def composite(g: ComfyNodeGraph, destination: NodeOutput, source: NodeOutput, mask: NodeOutput,
              x: int = 0, y: int = 0) -> NodeOutput:
    """mask の白い所だけ source を destination に重ねる。ComfyUI はマスクを source の大きさに引き伸ばすので、
    source とマスクは同じ大きさで渡すこと。"""
    return g.add("ImageCompositeMasked", destination=destination, source=source, x=x, y=y, resize_source=False,
                 mask=mask)[0]


def paste_back_protected(g: ComfyNodeGraph, generated: NodeOutput, original: NodeOutput,
                         protected: NodeOutput) -> NodeOutput:
    """人の手の範囲を元の画素に戻す。generated と original は同じ大きさ。"""
    return composite(g, generated, original, protected)


def save(g: ComfyNodeGraph, image: NodeOutput, filename_prefix: str) -> None:
    g.add("SaveImage", images=image, filename_prefix=filename_prefix)
