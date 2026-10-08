"""原稿として出す形（V3点検の結果 §3）の計算の部品：本の並び・見開き・ノンブル・色の種類・グラデの網点・
フキダシのしっぽ・入稿前の確かめの計算・設定の形。データベースは使わない。"""

import io
import pathlib
from types import SimpleNamespace

import numpy as np
import pypdf
import pytest
from PIL import Image
from shapely.geometry import Polygon

from v3server.name_structure.item_styles import BalloonShape, ToneSpec
from v3server.name_structure.print_settings import BilevelSettings, NombreSettings, PrintSettings, TextSpan, check_spans
from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.book_layout import (
    check_spreads,
    left_page_of_spread,
    nombre_place,
    page_sides,
    spread_problem,
)
from v3server.print_export.color_mode_output import ColorModeError, page_image
from v3server.print_export.export_runner import ExportRefused, check_spread_output, export_units
from v3server.print_export.page_render import (
    LAYER_NAME_NOMBRE,
    Node,
    PageContent,
    RenderRefused,
    SpreadContent,
    _tone_alpha,
    balloon_geometry,
    gutter_x_px,
    mm_to_px_matrix,
    render_page,
    render_spread,
    split_spread,
    spread_size_px,
    tail_polygon,
)
from v3server.print_export.preflight_checks import effective_dpi, has_color, page_count_problem, safe_area_overrun
from v3server.print_export.print_pdf_export import canvas_size_px, write_print_pdf
from v3server.print_export.text_render import font_path, render_texts
from v3server.server_settings import get_settings

ROOT = pathlib.Path(__file__).resolve().parents[3]
TEXT_SCRIPT = str(ROOT / "psd_writer" / "render_text.js")
FONT_DIR = "/usr/share/fonts/opentype/ipafont-gothic"
NODE = get_settings().node_executable  # .env の V3_NODE_EXECUTABLE（サーバーと同じ node）
needs_font = pytest.mark.skipif(not pathlib.Path(FONT_DIR, "ipag.ttf").exists(), reason="試験の書体が無い")

SPEC = PageSpec(frame_width_mm=30, frame_height_mm=44, trim_width_mm=36, trim_height_mm=51, bleed_mm=3,
                gutter_x_mm=1, gutter_y_mm=2)
DPI = 100
TYPESETTING = {"line_spacing_ratio": 0.3, "line_break": "character", "tate_chu_yoko_max_digits": 2,
               "tate_chu_yoko_marks": True, "align": "start"}
NOMBRE = {"font_family": "ipag", "font_size_pt": 8, "hidden_font_size_pt": 5, "color": "#000000", "start_number": 1,
          "numbering_scope": "episode",
          "position": {"vertical": "bottom", "horizontal": "outer", "edge_mm": 5, "side_mm": 4},
          "hidden_position": {"bottom_mm": 3, "gutter_mm": 2},
          "display_by_kind": {"cover": "none", "color_page": "hidden", "body": "visible", "blank": "hidden"}}
PRINT = {"file_code": "ABC", "color_mode": "bilevel", "dpi_by_color_mode": {"bilevel": 600, "grayscale": 350,
                                                                              "color": 350},
         "bilevel": {"threshold": 128, "pdf_codec": "flate",
                     "image_screen": {"lines_per_inch": 20, "angle_deg": 45, "dot_shape": "round"}},
         "safe_area": {"top_mm": 5, "bottom_mm": 5, "gutter_mm": 6, "outer_mm": 4},
         "page_count_multiple": 4, "page_count_scope": "episode"}


def _png(img):
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


# ---------------------------------------------------------------- 本の並び・見開き


def test_page_sides_and_spread_rule():
    assert page_sides(4, True) == ["left", "right", "left", "right"]
    assert page_sides(3, False) == ["right", "left", "right"]
    # 右から読む本：前のページが右・後ろが左。1ページ目が右なら 1-2 が見開きになり、2-3 はならない
    sides = page_sides(4, False)
    assert spread_problem(0, 1, sides, "rtl") is None
    assert spread_problem(1, 2, sides, "rtl") is not None
    # 左から読む本は逆
    assert spread_problem(0, 1, sides, "ltr") is not None
    assert spread_problem(1, 2, sides, "ltr") is None
    assert "隣り合っていない" in spread_problem(0, 2, sides, "rtl")
    assert left_page_of_spread("rtl") == "second" and left_page_of_spread("ltr") == "first"


def test_check_spreads_reports_broken_and_doubled():
    pages = [SimpleNamespace(id=f"p{i}") for i in range(4)]
    work = SimpleNamespace(first_page_is_left=False, reading_direction="rtl")
    ok = SimpleNamespace(id="s1", first_page_id="p0", second_page_id="p1")
    bad = SimpleNamespace(id="s2", first_page_id="p1", second_page_id="p2")
    gone = SimpleNamespace(id="s3", first_page_id="p3", second_page_id="pX")
    got = check_spreads(pages, [ok, bad, gone], work)
    assert [s.id for s, _ in got] == ["s2", "s2", "s3"]
    assert "2つの見開き" in got[0][1]
    undecided = SimpleNamespace(first_page_is_left=None, reading_direction="rtl")
    assert "first_page_is_left" in check_spreads(pages, [ok], undecided)[0][1]


def _plan(pid, index, spread=None, half=None):
    return SimpleNamespace(page=SimpleNamespace(id=pid), index=index, spread=spread, spread_half=half)


def test_export_units_and_spread_output_rules():
    sp = SimpleNamespace(id="s", first_page_id="a", second_page_id="b")
    plans = {"a": _plan("a", 1, sp, "right"), "b": _plan("b", 2, sp, "left"), "c": _plan("c", 3)}
    units = export_units(["a", "b", "c"], plans)
    assert [(u[0] and u[0].id, [p.page.id for p in u[1]]) for u in units] == [("s", ["b", "a"]), (None, ["c"])]
    with pytest.raises(ExportRefused, match="片方"):
        export_units(["a"], {"a": plans["a"]})
    with pytest.raises(ExportRefused, match="spread_output"):
        check_spread_output("png", None, True)
    with pytest.raises(ExportRefused, match="PDF"):
        check_spread_output("pdf", "joined", True)
    with pytest.raises(ExportRefused, match="PSD"):
        check_spread_output("psd", "split", True)
    check_spread_output("png", None, False)
    check_spread_output("png", "both", True)


# ---------------------------------------------------------------- ノンブル


def test_nombre_place_outer_center_hidden():
    ns = NombreSettings.model_validate(NOMBRE)
    left = nombre_place(ns, "visible", 7, "left", SPEC)
    right = nombre_place(ns, "visible", 8, "right", SPEC)
    # 小口：左のページは左の端、右のページは右の端
    assert (left.x_mm, left.anchor_x) == (4, "left") and (right.x_mm, right.anchor_x) == (32, "right")
    assert left.y_mm == 46 and left.anchor_y == "bottom" and left.text == "7" and not left.hidden
    center = NombreSettings.model_validate({**NOMBRE, "position": {**NOMBRE["position"], "horizontal": "center"}})
    assert nombre_place(center, "visible", 1, "left", SPEC).x_mm == 18
    # 隠し：ノドの近くに小さく（左のページのノドは右の端）
    h = nombre_place(ns, "hidden", 3, "left", SPEC)
    assert (h.x_mm, h.anchor_x, h.font_size_pt, h.hidden) == (34, "right", 5, True)
    assert nombre_place(ns, "hidden", 3, "right", SPEC).x_mm == 2
    assert nombre_place(ns, "none", 3, "right", SPEC) is None


def test_settings_require_every_value():
    with pytest.raises(ValueError, match="解像度が無い"):
        PrintSettings.model_validate({**PRINT, "dpi_by_color_mode": {"bilevel": 600}})
    with pytest.raises(ValueError, match="ノンブルの出し方が無い"):
        NombreSettings.model_validate({**NOMBRE, "display_by_kind": {"body": "visible"}})
    with pytest.raises(ValueError, match="書式が1つも無い"):
        TextSpan(start=0, end=1)
    check_spans("あいう", [{"start": 0, "end": 1}, {"start": 1, "end": 3}])
    with pytest.raises(ValueError, match="重なって"):
        check_spans("あいう", [{"start": 0, "end": 2}, {"start": 1, "end": 3}])
    with pytest.raises(ValueError, match="外"):
        check_spans("あい", [{"start": 0, "end": 3}])
    with pytest.raises(ValueError, match="gradient"):
        ToneSpec.model_validate({"kind": "gradient", "target": {"kind": "panel", "panel_id": "x"}, "density": 0.2,
                                 "lines_per_inch": 30})
    with pytest.raises(ValueError, match="しっぽ"):
        BalloonShape(kind="none", tail_bend_ratio=0.1)


# ---------------------------------------------------------------- グラデの網点


def test_gradient_tone_is_halftone_with_rising_density():
    ts = ToneSpec.model_validate({"kind": "gradient", "target": {"kind": "panel", "panel_id": "x"}, "density": 0.1,
                                  "density_end": 0.9, "angle_deg": 0, "lines_per_inch": 40,
                                  "screen_angle_deg": 45, "dot_shape": "round"})
    alpha = np.asarray(_tone_alpha(ts, (0, 0, 400, 100), 600, None))
    # 網点なので白か黒だけ（灰色のまま印刷へ行かない）
    assert set(np.unique(alpha)) <= {0, 255}
    left, right = (alpha[:, :80] > 0).mean(), (alpha[:, -80:] > 0).mean()
    assert left < 0.25 and right > 0.75 and left < right


# ---------------------------------------------------------------- しっぽ


def test_tail_polygon_reaches_tip_and_joins_body():
    body = Polygon([(0, 0), (100, 0), (100, 60), (0, 60)])
    tail = tail_polygon(body, (150, 120), 20, 0.2)
    assert tail is not None and tail.distance(Polygon([(149, 119), (151, 119), (151, 121), (149, 121)])) < 1.5
    # 根元は外形の中に入るので、和を取ると1つの形
    assert body.union(tail).geom_type == "Polygon"
    assert tail_polygon(body, (50, 30), 20, 0) is None
    # 曲がりの向きで膨らむ側が替わる
    a, b = tail_polygon(body, (150, 30), 20, 0.4), tail_polygon(body, (150, 30), 20, -0.4)
    assert a.centroid.y > 30 > b.centroid.y or a.centroid.y < 30 < b.centroid.y


def test_balloon_geometry_needs_tail_settings():
    m = mm_to_px_matrix(SPEC, DPI)
    t = SimpleNamespace(id="t", tail_target_mm=[30, 45])
    outline = [(4, 24), (16, 24), (16, 41), (4, 41)]
    with pytest.raises(RenderRefused, match="しっぽ"):
        balloon_geometry(t, BalloonShape(kind="custom", outline_mm=outline), m)
    g = balloon_geometry(t, BalloonShape(kind="custom", outline_mm=outline, tail_base_width_mm=3,
                                         tail_bend_ratio=0), m)
    body = balloon_geometry(SimpleNamespace(id="t", tail_target_mm=None),
                            BalloonShape(kind="custom", outline_mm=outline), m)
    assert g.area > body.area and g.geom_type == "Polygon"


# ---------------------------------------------------------------- 色の種類


def _leaf(name, img, table, left=0, top=0):
    return Node(name, "m" + name, img, left, top, table=table)


def test_bilevel_threshold_for_lines_and_screen_for_pictures():
    size = (200, 100)
    gray = Image.new("RGBA", (100, 100), (128, 128, 128, 255))
    paper = Node("紙", "p-paper", Image.new("RGBA", size, (255, 255, 255, 255)))
    bs = BilevelSettings.model_validate(PRINT["bilevel"])
    # 同じ灰色：線の層（閾値 128 より暗くない → 白）と、コマの絵（網点 → 約半分が黒）
    nodes = [paper, Node("コマ1", "c", children=[_leaf("コマの絵", gray, "panels")]),
             _leaf("line_art", gray, "panel_layers", left=100)]
    out = page_image(nodes, size, "bilevel", 600, bs)
    assert out.mode == "1"
    arr = np.asarray(out.convert("L"))
    assert 0.35 < (arr[:, :100] == 0).mean() < 0.65
    assert (arr[:, 100:] == 0).mean() == 0
    assert page_image(nodes, size, "grayscale", 600, None).mode == "L"
    assert page_image(nodes, size, "color", 600, None).mode == "RGB"
    with pytest.raises(ColorModeError, match="bilevel"):
        page_image(nodes, size, "bilevel", 600, None)
    with pytest.raises(ColorModeError, match="役"):
        page_image([_leaf("知らない役", gray, "panel_layers")], size, "bilevel", 600, bs)


def test_pdf_with_per_page_dpi_and_mixed_modes(tmp_path):
    pages = [Image.new("1", canvas_size_px(SPEC, 600), 1), Image.new("RGB", canvas_size_px(SPEC, 350), (255, 0, 0))]
    out = tmp_path / "a.pdf"
    write_print_pdf(pages, SPEC, [600, 350], "ccitt_g4", out)
    r = pypdf.PdfReader(out)
    assert len(r.pages) == 2
    assert float(r.pages[0].mediabox.width) == pytest.approx(float(r.pages[1].mediabox.width), abs=0.01)
    with pytest.raises(ValueError, match="符号化"):
        write_print_pdf(pages[:1], SPEC, [600], None, out)


# ---------------------------------------------------------------- 見開き


P_LEFT, P_RIGHT = "1" * 32, "2" * 32
FRAME = {"line_width_mm": 0.5, "line_color": "#000000"}


def _page(pid, color, nombre=None):
    # 塗り足しより外まで広げたコマ（座標は基本枠。仕上がりの左上は (-3, -3.5)）に、1色の絵
    panel = SimpleNamespace(id=pid[:31] + "p", order=0, frame={"polygon_mm": [(-7, -7), (43, -7), (43, 52), (-7, 52)]},
                            frame_style=None, image_id=f"img-{pid}",
                            image_placement={"crop_px": [0, 0, 10, 10], "dest_box_mm": [-7, -7, 43, 52]},
                            adjustments=[])
    return PageContent(page_id=pid, spec=SPEC, text_direction="vertical",
                       preferences={"frame_style": FRAME, "typesetting": TYPESETTING}, panels=[panel], layers=[],
                       texts=[], page_items=[], images={f"img-{pid}": "x"}, nombre=nombre)


IMAGES = {f"img-{P_LEFT}": _png(Image.new("RGBA", (10, 10), (255, 0, 0, 255))),
          f"img-{P_RIGHT}": _png(Image.new("RGBA", (10, 10), (0, 0, 255, 255))),
          "wide": _png(Image.new("RGBA", (20, 10), (0, 255, 0, 255)))}


def _no_text(items):
    assert not items
    return []


def test_spread_clips_pages_at_gutter_and_splits_with_bleed():
    sc = SpreadContent("s", _page(P_LEFT, "red"), _page(P_RIGHT, "blue"), None, None, [], {})
    r = render_spread(sc, DPI, lambda i: IMAGES[i], _no_text, lambda f: "x")
    assert (r.width, r.height) == spread_size_px(SPEC, DPI)
    gx = gutter_x_px(SPEC, DPI)
    img = np.asarray(r.composite)
    # 左のページの絵（赤）は塗り足しの分もノドを越えない。右のページ（青）も同じ
    assert tuple(img[100, gx - 3]) == (255, 0, 0) and tuple(img[100, gx + 3]) == (0, 0, 255)
    left, right = split_spread(r.composite, SPEC, DPI)
    assert left.size == right.size == canvas_size_px(SPEC, DPI)
    # 分けた左のページの右の塗り足しには、右のページの絵が入る（ノドをまたぐ絵が切れ目で途切れない）
    assert left.getpixel((left.width - 2, 100)) == (0, 0, 255)
    assert right.getpixel((1, 100)) == (255, 0, 0)


def test_spread_image_crosses_gutter():
    # コマの絵の無いページに、見開きの絵（緑）を全面に置く
    left, right = _page(P_LEFT, "red"), _page(P_RIGHT, "blue")
    for p in (left, right):
        p.panels[0].image_id = None
    sc = SpreadContent("s", left, right, "wide", {"crop_px": [0, 0, 20, 10], "dest_box_mm": [-7, -7, 79, 52]}, [],
                       {"wide": "y"})
    r = render_spread(sc, DPI, lambda i: IMAGES[i], _no_text, lambda f: "x")
    gx = gutter_x_px(SPEC, DPI)
    assert r.composite.getpixel((gx, 100)) == (0, 255, 0)
    assert [n.name for n in r.nodes][:2] == ["紙", "見開きの絵"]


@needs_font
def test_nombre_is_drawn_at_its_place():
    from v3server.print_export.book_layout import nombre_place as place
    nb = place(NombreSettings.model_validate(NOMBRE), "visible", 12, "left", SPEC)
    page = _page(P_LEFT, "red", nb)
    page.panels = []
    r = render_page(page, DPI, lambda i: IMAGES[i], lambda items: render_texts(items, NODE, TEXT_SCRIPT),
                    lambda f: font_path(FONT_DIR, f))
    node = r.nodes[-1]
    assert node.name == LAYER_NAME_NOMBRE
    k = DPI / 25.4
    # 左の端は小口から 4mm、下の端は仕上がりの下から 5mm（塗り足し 3mm を足した画素）
    bbox = node.image.getbbox()
    assert abs(node.left + bbox[0] - (4 + 3) * k) < 3
    assert abs(node.top + bbox[3] - (51 - 5 + 3) * k) < 3


# ---------------------------------------------------------------- 入稿前の確かめの計算


def test_preflight_calculations():
    pl = {"crop_px": [0, 0, 600, 400], "dest_box_mm": [0, 0, 50.8, 33.866]}
    assert effective_dpi(pl) == pytest.approx(300, rel=1e-3)
    assert not has_color(Image.new("RGB", (4, 4), (90, 90, 90)))
    im = Image.new("RGBA", (4, 4), (90, 90, 90, 255))
    im.putpixel((0, 0), (90, 91, 90, 255))
    assert has_color(im)
    im.putpixel((0, 0), (255, 0, 0, 0))  # 見えない画素の色は数えない
    assert not has_color(im)
    ps = PrintSettings.model_validate(PRINT)
    # 左のページはノドが右（36-6=30 より右に出ると、ノド）
    assert safe_area_overrun([(10, 10), (31, 10), (31, 20), (10, 20)], "left", SPEC, ps) == ["ノド"]
    assert safe_area_overrun([(10, 10), (31, 10), (31, 20), (10, 20)], "right", SPEC, ps) == []
    assert safe_area_overrun([(3, 2), (10, 2), (10, 47), (3, 47)], "right", SPEC, ps) == ["上", "下", "ノド"]
    assert page_count_problem(16, 4) is None and page_count_problem(18, 8) is not None
    assert page_count_problem(17, None) is None
