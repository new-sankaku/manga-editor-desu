"""print_export の試験。寸法（mm）・2値の可逆・網点の濃さ・PSD の依頼を書き出しのプロセスが受けて書けること。"""
import json
import pathlib
import subprocess
import tempfile

import numpy as np
import pypdf
import pytest
from PIL import Image

from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.binarize_and_halftone import binarize, compose_line_and_tone, halftone_screen
from v3server.print_export.layered_psd_request import (PageLayerSet, PsdLayer, PsdWriterError, TextInfo, build_page_psd_request,
                                                       write_layered_psd)
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


def _layer_set(tmp_path):
    p = lambda n, c: _png(tmp_path / f"{n}.png", 20, 30, c)
    return PageLayerSet(
        panel_frame=PsdLayer(name="x", png_path=p("frame", (0, 0, 0, 255))),
        ai_art_by_panel=[PsdLayer(name="コマ1の絵", png_path=p("a1", (255, 200, 190, 255)), blend_mode="multiply", opacity=0.5),
                         PsdLayer(name="コマ2の絵", png_path=p("a2", (150, 190, 255, 255)), hidden=True)],
        hand_drawn=PsdLayer(name="x", png_path=p("hand", (0, 0, 0, 0))),
        balloon=PsdLayer(name="x", png_path=p("balloon", (255, 255, 255, 255))),
        typeset_texts=[PsdLayer(name="セリフ1", png_path=p("t1", (0, 0, 0, 255)),
                                text=TextInfo(text="きょうは\n早いね", orientation="vertical", font_name="TestFont", font_size=12,
                                              color_rgb=(0, 0, 0), x=5, y=5))],
        sfx=PsdLayer(name="x", png_path=p("sfx", (0, 0, 0, 255))),
    )


def test_psd_writer_receives_request_and_layers_read_back(tmp_path):
    composite = _png(tmp_path / "comp.png", 20, 30, (255, 255, 255, 255))
    out = tmp_path / "page.psd"
    req = build_page_psd_request(20, 30, composite, _layer_set(tmp_path), out)
    json.dumps(req)  # JSON にできる形
    back = write_layered_psd(req, "node", WRITER, 60)
    assert out.stat().st_size > 0
    names = [(l["name"], l["depth"]) for l in back["layers"]]
    assert names == [("コマ枠", 0), ("AIの絵", 0), ("コマ1の絵", 1), ("コマ2の絵", 1), ("人の手", 0), ("フキダシ", 0),
                     ("写植", 0), ("セリフ1", 1), ("描き文字", 0)]
    by = {l["name"]: l for l in back["layers"]}
    assert by["AIの絵"]["group"] and by["写植"]["group"]
    assert by["コマ1の絵"]["blend_mode"] == "multiply" and by["コマ1の絵"]["opacity"] == pytest.approx(0.5, abs=0.01)
    assert by["コマ2の絵"]["hidden"] is True
    assert by["セリフ1"]["text"] == "きょうは\n早いね" and by["セリフ1"]["orientation"] == "vertical"


def test_psd_writer_failure_raises(tmp_path):
    req = build_page_psd_request(20, 30, None, _layer_set(tmp_path), tmp_path / "x.psd")
    req["layers"][0]["png_path"] = str(tmp_path / "missing.png")
    with pytest.raises(PsdWriterError):
        write_layered_psd(req, "node", WRITER, 60)
