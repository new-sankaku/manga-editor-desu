"""ページの層を PSD にする依頼（JSON）を組み、PSD 書き出しのプロセス（v3/psd_writer、Node の ag-psd）を呼ぶ。

層の順は V3細部の決めごと 10.3：下から、コマ枠、AIの絵（コマごと）、人の手、フキダシ、写植、描き文字。
プロセスへは標準入力の JSON で渡し、標準出力で書いた PSD を読み戻した層の一覧を受け取る。
Node の場所と書き出しの script は呼ぶ側が渡す（ここに置かない）。
"""
import json
import pathlib
import subprocess
from typing import Literal, Optional

from pydantic import BaseModel, Field

# 層の名前（画面に出る）
LAYER_NAME_PANEL_FRAME = "コマ枠"
LAYER_NAME_AI_ART = "AIの絵"
LAYER_NAME_HAND_DRAWN = "人の手"
LAYER_NAME_BALLOON = "フキダシ"
LAYER_NAME_TYPESET = "写植"
LAYER_NAME_SFX = "描き文字"

BlendMode = Literal["normal", "multiply"]


class TextInfo(BaseModel):
    """文字層の文字の情報。層の画素は png_path に描いた絵を使う。"""

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


class PageLayerSet(BaseModel):
    """1ページの層の元。画像はどれも RGBA の PNG（ページと同じ大きさでなくてもよい。left・top で置く）。"""

    panel_frame: PsdLayer
    ai_art_by_panel: list[PsdLayer]
    hand_drawn: PsdLayer
    balloon: PsdLayer
    typeset_texts: list[PsdLayer]
    sfx: PsdLayer


def build_page_psd_request(width: int, height: int, composite_png: Optional[pathlib.Path], layers: PageLayerSet,
                           output_path: pathlib.Path) -> dict:
    """書き出しプロセスに渡す辞書を組む。children は下の層が先。"""
    for t in layers.typeset_texts:
        if t.text is None or t.png_path is None:
            raise ValueError(f"写植の層 {t.name} は、文字の情報と描いた画像（png_path）の両方が要ります")
    ai_group = PsdLayer(name=LAYER_NAME_AI_ART, children=layers.ai_art_by_panel)
    typeset_group = PsdLayer(name=LAYER_NAME_TYPESET, children=layers.typeset_texts)
    ordered = [
        _renamed(layers.panel_frame, LAYER_NAME_PANEL_FRAME),
        ai_group,
        _renamed(layers.hand_drawn, LAYER_NAME_HAND_DRAWN),
        _renamed(layers.balloon, LAYER_NAME_BALLOON),
        typeset_group,
        _renamed(layers.sfx, LAYER_NAME_SFX),
    ]
    return {
        "width": width,
        "height": height,
        "composite_png": str(composite_png) if composite_png else None,
        "output_path": str(output_path),
        "layers": [json.loads(layer.model_dump_json(exclude_none=True)) for layer in ordered],
    }


def _renamed(layer: PsdLayer, name: str) -> PsdLayer:
    return layer.model_copy(update={"name": name})


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
