"""print_export の試験。寸法（mm）・2値の可逆・網点の濃さ・PSD の依頼を書き出しのプロセスが受けて書けること。"""
import json
import pathlib
import subprocess

import numpy as np
import pypdf
import pytest
from PIL import Image

from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.binarize_and_halftone import binarize, compose_line_and_tone, halftone_screen
from v3server.print_export.layered_psd_request import (PsdWriterError, build_psd_request, psd_layers_from_nodes,
                                                       write_layered_psd)
from v3server.print_export.page_render import Node
from v3server.print_export.print_pdf_export import bilevel_image_from_black_mask, canvas_size_px, write_print_pdf

# 試験用の寸法（実際の値は作品の設定から来る）
SPEC = PageSpec(frame_width_mm=30, frame_height_mm=44, trim_width_mm=36, trim_height_mm=51, bleed_mm=3,
                gutter_x_mm=1, gutter_y_mm=2)
WRITER = pathlib.Path(__file__).resolve().parents[3] / "psd_writer" / "write_layered_psd.js"


def _sample_black(dpi):
    w, h = canvas_size_px(SPEC, dpi)
    gray = np.full((h, w), 255, np.uint8)
    gray[h // 4: h // 4 + 6, 10: w - 10] = 0
    tone = np.full((h, w), 180, np.uint8)
    return compose_line_and_tone(gray, tone, 128, dpi, 60, 45, "round")


@pytest.mark.parametrize("dpi", [350, 600])
def test_page_size_in_mm_and_boxes(dpi, tmp_path):
    black = _sample_black(dpi)
    out = tmp_path / "a.pdf"
    write_print_pdf([bilevel_image_from_black_mask(black)], SPEC, dpi, "ccitt_g4", out)
    page = pypdf.PdfReader(str(out)).pages[0]
    mm = lambda v: float(v) / 72 * 25.4
    assert mm(page.mediabox.width) == pytest.approx(42.0, abs=0.001)
    assert mm(page.mediabox.height) == pytest.approx(57.0, abs=0.001)
    assert mm(page.trimbox.width) == pytest.approx(36.0, abs=0.001)
    assert mm(page.trimbox.height) == pytest.approx(51.0, abs=0.001)
    assert mm(page.bleedbox.width) == pytest.approx(42.0, abs=0.001)


@pytest.mark.parametrize("codec", ["ccitt_g4", "flate"])
def test_bilevel_is_lossless(codec, tmp_path):
    black = _sample_black(350)
    out = tmp_path / "b.pdf"
    write_print_pdf([bilevel_image_from_black_mask(black)], SPEC, 350, codec, out)
    # poppler で取り出す（pypdf は1ビットの Flate を正しく取り出せなかった。p51）
    subprocess.run(["pdfimages", "-png", str(out), str(tmp_path / "x")], check=True)
    got = np.asarray(Image.open(tmp_path / "x-000.png"))
    assert np.array_equal(got == 0, black)


def test_gray_is_lossless_and_size_mismatch_raises(tmp_path):
    w, h = canvas_size_px(SPEC, 350)
    gray = (np.arange(w * h).reshape(h, w) % 251).astype(np.uint8)
    out = tmp_path / "c.pdf"
    write_print_pdf([Image.fromarray(gray, "L")], SPEC, 350, "flate", out)
    subprocess.run(["pdfimages", "-png", str(out), str(tmp_path / "y")], check=True)
    assert np.array_equal(np.asarray(Image.open(tmp_path / "y-000.png")), gray)
    with pytest.raises(ValueError):
        write_print_pdf([Image.fromarray(gray[:-1], "L")], SPEC, 350, "flate", tmp_path / "d.pdf")


@pytest.mark.parametrize("dpi,lpi,shape", [(600, 60, "round"), (350, 60, "round"), (350, 85, "round"), (600, 60, "line"), (600, 60, "square")])
def test_halftone_density_matches_target(dpi, lpi, shape):
    for dark in (0.1, 0.3, 0.5, 0.7, 0.9):
        gray = np.full((int(dpi * 0.6), int(dpi * 0.6)), round(255 * (1 - dark)), np.uint8)
        got = halftone_screen(gray, dpi, lpi, 45, shape).mean()
        assert got == pytest.approx(dark, abs=0.01), (dpi, lpi, shape, dark)


def test_halftone_angle_changes_pattern_and_bad_arguments():
    gray = np.full((200, 200), 128, np.uint8)
    assert not np.array_equal(halftone_screen(gray, 600, 60, 0, "round"), halftone_screen(gray, 600, 60, 45, "round"))
    with pytest.raises(ValueError):
        halftone_screen(gray, 600, 60, 45, "triangle")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        binarize(gray, 0)


def test_binarize_threshold():
    gray = np.array([[0, 127, 128, 255]], np.uint8)
    assert binarize(gray, 128).tolist() == [[True, True, False, False]]


def _png(path, w, h, rgba):
    Image.fromarray(np.tile(np.array(rgba, np.uint8), (h, w, 1)), "RGBA").save(path)
    return path


def _solid(w, h, rgba):
    return Image.fromarray(np.tile(np.array(rgba, np.uint8), (h, w, 1)), "RGBA")


A = "a" * 32
B = "b" * 32
T = "c" * 32


def _nodes():
    return [
        Node("紙", "9" * 32 + "-paper", _solid(20, 30, (255, 255, 255, 255))),
        Node("コマ1", A, children=[Node("コマの絵", A + "-image", _solid(10, 10, (255, 200, 190, 255)), 2, 3,
                                       "multiply", 0.5, table="panels")], table="panels"),
        Node("コマ2", B, children=[Node("panel_art", "d" * 32, _solid(5, 5, (150, 190, 255, 255)), hidden=True,
                                       table="panel_layers")], table="panels"),
        Node("コマ枠", "9" * 32 + "-frame", _solid(20, 30, (0, 0, 0, 255)), table="pages"),
        Node("写植", "9" * 32 + "-typeset", children=[
            Node("セリフ", T, _solid(4, 8, (0, 0, 0, 255)), 5, 5, table="text_items",
                 text={"text": "きょうは\n早いね", "orientation": "vertical", "font_name": "TestFont", "font_size": 12,
                       "color_rgb": [0, 0, 0], "x": 5.0, "y": 5.0})]),
    ]


def test_psd_writer_receives_request_and_layers_read_back(tmp_path):
    composite = _png(tmp_path / "comp.png", 24, 34, (255, 255, 255, 255))
    out = tmp_path / "page.psd"
    layers = psd_layers_from_nodes(_nodes(), tmp_path, offset=(2, 2))
    req = build_psd_request(24, 34, composite, layers, out)
    json.dumps(req)  # JSON にできる形
    back = write_layered_psd(req, "node", WRITER, 60)
    assert out.stat().st_size > 0
    names = [(l["name"].split(" [")[0], l["depth"]) for l in back["layers"]]
    assert names == [("紙", 0), ("コマ1", 0), ("コマの絵", 1), ("コマ2", 0), ("panel_art", 1), ("コマ枠", 0),
                     ("写植", 0), ("セリフ", 1)]
    # どの層の名前も「名前 [id]」で終わる
    assert all(l["name"].endswith("]") for l in back["layers"])
    by = {l["name"].split(" [")[0]: l for l in back["layers"]}
    assert by["コマの絵"]["blend_mode"] == "multiply" and by["コマの絵"]["opacity"] == pytest.approx(0.5, abs=0.01)
    assert by["panel_art"]["hidden"] is True
    assert by["セリフ"]["text"] == "きょうは\n早いね" and by["セリフ"]["orientation"] == "vertical"
    # 紙の上の置き場（offset）が層の位置に足されている
    assert req["layers"][1]["children"][0]["left"] == 4 and req["layers"][1]["children"][0]["top"] == 5


def test_psd_writer_failure_raises(tmp_path):
    req = build_psd_request(20, 30, None, psd_layers_from_nodes(_nodes(), tmp_path), tmp_path / "x.psd")
    req["layers"][0]["png_path"] = str(tmp_path / "missing.png")
    with pytest.raises(PsdWriterError):
        write_layered_psd(req, "node", WRITER, 60)
