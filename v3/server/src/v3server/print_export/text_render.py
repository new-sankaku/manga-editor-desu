"""書き出しの文字を絵にする。描くのは Node の v3/psd_writer/render_text.js（@napi-rs/canvas 1.0.10）。
組版（縦書きの字形・禁則・縦中横・自動の改行）は v3/psd_writer/text_layout.js（HarfBuzz・UAX #14・UAX #50・budoux）。

PNG・PDF・PSD のどの書き出しも、文字はここを通して描く（同じ文字が書き出しの種類で違う絵にならないように）。
書体は V3_FONT_DIR の中のファイルで、書体の名前（font_family）はファイルの名前から拡張子を除いたもの。
見つからなければ止める（ほかの書体で描かない）。
"""

import io
import json
import pathlib
import subprocess
import tempfile
from dataclasses import dataclass

from PIL import Image

FONT_SUFFIXES = (".ttf", ".otf", ".ttc")


class TextRenderError(RuntimeError):
    pass


def font_path(font_dir: str | None, family: str) -> str:
    if not font_dir:
        raise TextRenderError("V3_FONT_DIR が無い。書体のファイルが無いので文字を描けない")
    root = pathlib.Path(font_dir)
    found = [p for p in root.rglob("*") if p.suffix.lower() in FONT_SUFFIXES and p.stem == family]
    if not found:
        raise TextRenderError(f"書体 {family} のファイルが {font_dir} に無い（ファイルの名前から拡張子を除いたものが書体の名前）")
    if len(found) > 1:
        raise TextRenderError(f"書体 {family} のファイルが2つ以上ある: {[str(p) for p in found]}")
    return str(found[0])


@dataclass
class RenderedText:
    """描いた文字。image は RGBA（measure のときは None）。block_w・block_h は文字のブロックの画素（絵の真ん中にある）。"""

    image: Image.Image | None
    block_w: float
    block_h: float
    overflow: bool
    lines: int
    missing_chars: list[str]


def _call(req: dict, node_executable: str, script: str, timeout_seconds: float) -> list[dict]:
    done = subprocess.run([node_executable, script], input=json.dumps(req, ensure_ascii=False), capture_output=True,
                          text=True, encoding="utf-8", timeout=timeout_seconds)
    if done.returncode != 0:
        raise TextRenderError(f"文字を描けなかった（終了コード {done.returncode}）: {done.stderr.strip()[:500]}")
    return json.loads(done.stdout)["items"]


def _run(items: list[dict], node_executable: str, script: str, timeout_seconds: float, measure_only: bool
         ) -> list[RenderedText]:
    with tempfile.TemporaryDirectory() as tmp:
        req = {"items": [{**it, "output_path": str(pathlib.Path(tmp) / f"{i}.png"), "measure_only": measure_only}
                         for i, it in enumerate(items)]}
        out = []
        for it, info in zip(req["items"], _call(req, node_executable, script, timeout_seconds), strict=False):
            image = None
            if not measure_only:
                if info["missing_chars"]:
                    raise TextRenderError(f"文字 {it['id']} の書体に無い字がある: {''.join(info['missing_chars'])}"
                                          "（ほかの書体では描かない。書体を替えるか、文字の一部の書式で書体を選ぶ）")
                if info["opaque_pixels"] == 0:
                    raise TextRenderError(f"文字 {it['id']} を描いたが、見える画素が無い（文字が空 など）")
                image = Image.open(io.BytesIO(pathlib.Path(it["output_path"]).read_bytes())).convert("RGBA")
            out.append(RenderedText(image, info["block_w"], info["block_h"], info["overflow"], info["lines"],
                                    info["missing_chars"]))
        return out


def render_texts(items: list[dict], node_executable: str, script: str, timeout_seconds: float = 120
                 ) -> list[RenderedText]:
    """items は render_text.js の入力の形（output_path はここで付ける）。描いた文字を同じ順で返す。
    書体に無い字があれば止める。"""
    return _run(items, node_executable, script, timeout_seconds, False)


def measure_texts(items: list[dict], node_executable: str, script: str, timeout_seconds: float = 120
                  ) -> list[RenderedText]:
    """描かずに組むだけ（入稿前の確かめ：はみ出し・書体に無い字）。"""
    return _run(items, node_executable, script, timeout_seconds, True)


def layout_texts(items: list[dict], node_executable: str, script: str, timeout_seconds: float = 120) -> list[dict]:
    """描かずに組み、行の切れ目と字の置き場を返す（render_text.js の layoutDetail。画面が書き出しと同じ組み方で字を置く）。
    返す形：{id, overflow, lines, block_w, block_h, missing_chars, layout: {block_origin, lines, glyphs, ruby}}（画素）。"""
    req = {"items": [{**it, "measure_only": True, "layout_detail": True} for it in items]}
    return _call(req, node_executable, script, timeout_seconds)
