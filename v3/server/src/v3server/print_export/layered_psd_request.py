"""ページの層（print_export/page_render.py の Node）を PSD にする依頼（JSON）を組み、
PSD 書き出しのプロセス（v3/psd_writer、Node の ag-psd）を呼ぶ。

層の順は V3細部の決めごと 10.3（page_render.py の docstring と同じ）。どの層の名前も「名前 [id]」で終わる。
プロセスへは標準入力の JSON で渡し、標準出力で書いた PSD を読み戻した層の一覧を受け取る。
Node の場所と書き出しの script は呼ぶ側が渡す（ここに置かない）。

ペンの線は PSD では画素の層になる（線の値はサーバーに残る。PSD から線には戻せない）。
"""
import json
import pathlib
import subprocess
from typing import Literal, Optional

from pydantic import BaseModel, Field

from v3server.print_export.page_render import Node

BlendMode = Literal["normal", "multiply", "screen", "overlay", "darken", "lighten"]


class TextInfo(BaseModel):
    """文字層の文字の情報。層の画素は png_path に描いた絵を使う（ag-psd は文字を描かないため）。"""

    text: str
    orientation: Literal["vertical", "horizontal"]
    font_name: str
    font_size: float = Field(gt=0)
    color_rgb: tuple[int, int, int]
    # 文字の基準位置（ページの画素）
    x: float
    y: float


class PsdLayer(BaseModel):
    """1つの層かグループ。children があればグループ（png_path は持たない）。"""

    name: str
    png_path: Optional[pathlib.Path] = None
    children: Optional[list["PsdLayer"]] = None
    hidden: bool = False
    blend_mode: BlendMode = "normal"
    opacity: float = Field(default=1.0, ge=0, le=1)
    # 層の画素を置く左上（ページの画素）
    left: int = 0
    top: int = 0
    text: Optional[TextInfo] = None


def psd_layers_from_nodes(nodes: list[Node], png_dir: pathlib.Path, offset: tuple[int, int] = (0, 0)
                          ) -> list[PsdLayer]:
    """Node を PsdLayer にし、絵を png_dir に書く。offset は紙の上でのページの左上（紙がページより大きいとき）。"""
    out = []
    for n in nodes:
        if n.children is not None:
            out.append(PsdLayer(name=n.full_name, children=psd_layers_from_nodes(n.children, png_dir, offset),
                                hidden=n.hidden, blend_mode=n.blend, opacity=n.opacity))
            continue
        if n.image is None:
            raise ValueError(f"層 {n.full_name} に絵が無い")
        path = png_dir / f"{n.marker}.png"
        n.image.save(path)
        text = None
        if n.text is not None:
            text = TextInfo(**{**n.text, "x": n.text["x"] + offset[0], "y": n.text["y"] + offset[1]})
        out.append(PsdLayer(name=n.full_name, png_path=path, hidden=n.hidden, blend_mode=n.blend, opacity=n.opacity,
                            left=n.left + offset[0], top=n.top + offset[1], text=text))
    return out


def build_psd_request(width: int, height: int, composite_png: Optional[pathlib.Path], layers: list[PsdLayer],
                      output_path: pathlib.Path) -> dict:
    """書き出しプロセスに渡す辞書を組む。layers は下の層が先。"""

    def check(ls: list[PsdLayer]):
        for la in ls:
            if la.text is not None and la.png_path is None:
                raise ValueError(f"文字の層 {la.name} は、文字の情報と描いた画像（png_path）の両方が要る")
            if la.children:
                check(la.children)

    check(layers)
    return {
        "width": width,
        "height": height,
        "composite_png": str(composite_png) if composite_png else None,
        "output_path": str(output_path),
        "layers": [json.loads(layer.model_dump_json(exclude_none=True)) for layer in layers],
    }


class PsdWriterError(RuntimeError):
    """書き出しのプロセスが失敗した。"""


def write_layered_psd(request: dict, node_executable: str, writer_script: pathlib.Path, timeout_seconds: float) -> dict:
    """書き出しのプロセスを呼び、読み戻した層の一覧（辞書）を返す。失敗したら PsdWriterError。"""
    done = subprocess.run([node_executable, str(writer_script)], input=json.dumps(request, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8", timeout=timeout_seconds)
    if done.returncode != 0:
        raise PsdWriterError(f"PSD の書き出しが失敗しました（終了コード {done.returncode}）: {done.stderr.strip()[:500]}")
    return json.loads(done.stdout)


PsdLayer.model_rebuild()
