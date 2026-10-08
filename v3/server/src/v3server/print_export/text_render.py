"""書き出しの文字を絵にする。描くのは Node の v3/psd_writer/render_text.js（@napi-rs/canvas 1.0.10）。

PNG・PDF・PSD のどの書き出しも、文字はここを通して描く（同じ文字が書き出しの種類で違う絵にならないように）。
書体は V3_FONT_DIR の中のファイルで、書体の名前（font_family）はファイルの名前から拡張子を除いたもの。
見つからなければ止める（ほかの書体で描かない）。
"""

import io
import json
import pathlib
import subprocess
import tempfile

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


def render_texts(items: list[dict], node_executable: str, script: str, timeout_seconds: float = 120
                 ) -> list[Image.Image]:
    """items は render_text.js の入力の形（output_path はここで付ける）。描いた RGBA の絵を同じ順で返す。"""
    with tempfile.TemporaryDirectory() as tmp:
        req = {"items": [{**it, "output_path": str(pathlib.Path(tmp) / f"{i}.png")} for i, it in enumerate(items)]}
        done = subprocess.run([node_executable, script], input=json.dumps(req, ensure_ascii=False), capture_output=True,
                              text=True, encoding="utf-8", timeout=timeout_seconds)
        if done.returncode != 0:
            raise TextRenderError(f"文字を描けなかった（終了コード {done.returncode}）: {done.stderr.strip()[:500]}")
        out = []
        for it, info in zip(req["items"], json.loads(done.stdout)["items"], strict=False):
            if info["opaque_pixels"] == 0:
                raise TextRenderError(f"文字 {it['id']} を描いたが、見える画素が無い（書体に字が無い・文字が空 など）")
            out.append(Image.open(io.BytesIO(pathlib.Path(it["output_path"]).read_bytes())).convert("RGBA"))
        return out
