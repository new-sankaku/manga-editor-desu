"""10.4 で足した、答えが決まる部品の試験：線の消しゴム・線の値・ページの層（書き出し）・文字を描く・紙の大きさの PDF・
PSD の書き出しと戻しの結び付け（小さな合成の PSD）・アプリが中身を知っている処理。"""

import io
import json
import pathlib
from types import SimpleNamespace

import numpy as np
import pypdf
import pytest
from PIL import Image
from pydantic import ValidationError

from v3server.generation_queue.known_processes import KNOWN_PROCESSES, check_process_task
from v3server.hand_tools.pen_stroke_raster import PixelEraserStroke, erase_pixels
from v3server.hand_tools.vector_strokes import (
    StrokeValues,
    crossing_indices,
    erase,
    moved,
    resample,
    stroke_box,
    stroke_cache_problem,
)
from v3server.llm_questions.extract_characters_question import (
    build_extract_characters_question,
    parse_extract_characters_answer,
)
from v3server.llm_questions.read_prompt_question import build_read_prompt_question, parse_read_prompt_answer
from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.layered_psd_request import build_psd_request, psd_layers_from_nodes, write_layered_psd
from v3server.print_export.page_render import (
    LAYER_NAME_PANEL_FRAME,
    PageContent,
    RenderRefused,
    mm_to_px_matrix,
    render_page,
)
from v3server.print_export.print_pdf_export import canvas_size_px, paper_size_px, write_print_pdf
from v3server.print_export.psd_import_matching import (
    ExportedLayer,
    clean_name,
    import_actions,
    marker_of,
    match_layers,
    read_psd,
)
from v3server.print_export.text_render import TextRenderError, font_path, render_texts
from v3server.v3_error_types import Invalid

ROOT = pathlib.Path(__file__).resolve().parents[3]
WRITER = ROOT / "psd_writer" / "write_layered_psd.js"
TEXT_SCRIPT = str(ROOT / "psd_writer" / "render_text.js")
FONT_DIR = "/usr/share/fonts/opentype/ipafont-gothic"
NODE = "/opt/node22/bin/node"
needs_font = pytest.mark.skipif(not pathlib.Path(FONT_DIR, "ipag.ttf").exists(), reason="試験の書体が無い")

SPEC = PageSpec(frame_width_mm=30, frame_height_mm=44, trim_width_mm=36, trim_height_mm=51, bleed_mm=3,
                gutter_x_mm=1, gutter_y_mm=2)
DPI = 100


# ---------------------------------------------------------------- 線


def _line(x0, x1, y=0.0, n=11):
    return [(x0 + (x1 - x0) * i / (n - 1), y, 0.5, float(i)) for i in range(n)]


def test_vector_eraser_three_modes():
    pts = _line(0, 10)
    path = [(5, -2), (5, 2)]
    touched = erase(pts, 0.5, path, 1.0, "touched", [])
    assert len(touched) == 2
    assert max(p[0] for p in touched[0]) < 5 < min(p[0] for p in touched[1])
    # 交わりまで：縦の線が x=2 と x=8 で交わる。消しゴムは x=5 → 2〜8 が消え、両端が残る
    others = [[(2, -3, .5, 0), (2, 3, .5, 1)], [(8, -3, .5, 0), (8, 3, .5, 1)]]
    left_right = erase(pts, 0.5, path, 1.0, "to_crossings", others)
    assert len(left_right) == 2
    assert max(p[0] for p in left_right[0]) <= 2.01 and min(p[0] for p in left_right[1]) >= 7.99
    # 交わりが無ければ線ごと消える
    assert erase(pts, 0.5, path, 1.0, "to_crossings", []) == []
    assert erase(pts, 0.5, path, 1.0, "whole", []) == []
    # 触れていなければ None（変えない）
    assert erase(pts, 0.5, [(50, 50), (51, 51)], 1.0, "touched", []) is None


def test_stroke_values_rules():
    ok = dict(brush="pencil", points=[(0, 0, .5, 0), (1, 1, .5, 1)], width_mm=0.5, color="#000000", opacity=1)
    StrokeValues.model_validate(ok)
    with pytest.raises(ValidationError):  # 乱れのある筆は seed が要る
        StrokeValues.model_validate({**ok, "brush": "crayon"})
    StrokeValues.model_validate({**ok, "brush": "crayon", "seed": 3})
    with pytest.raises(ValidationError):  # 消しゴムは色を持たない
        StrokeValues.model_validate({**ok, "brush": "eraser"})
    with pytest.raises(ValidationError):  # 時刻が逆
        StrokeValues.model_validate({**ok, "points": [(0, 0, .5, 1), (1, 1, .5, 0)]})
    assert moved([(1, 2, .5, 0)], 1, -1) == [[2, 1, .5, 0]]
    # 筆圧の無い線（null）は受ける。1本の中で混ざるのは断る
    StrokeValues.model_validate({**ok, "points": [(0, 0, None, 0), (1, 1, None, 1)]})
    with pytest.raises(ValidationError):
        StrokeValues.model_validate({**ok, "points": [(0, 0, None, 0), (1, 1, .5, 1)]})
    assert moved([(1, 2, None, 0)], 1, -1) == [[2, 1, None, 0]]


def test_pressure_free_strokes_resample_and_erase_without_inventing_pressure():
    pts = [(0, 0, None, 0), (4, 0, None, 4)]
    assert all(p[2] is None for p in resample(pts, 1))
    pieces = erase(pts, 0.5, [(2, -1), (2, 1)], 0.5, "touched", [])
    assert len(pieces) == 2 and all(p[2] is None for piece in pieces for p in piece)


def test_crossings_use_the_index_and_match_the_plain_rule():
    # 索引で絞った答えが、全部の区間の組を調べた答えと同じになる（ずらした線をたくさん並べて比べる）
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def plain(points, others):
        return [i for i, (a, b) in enumerate(zip(points, points[1:], strict=False))
                if any((orient(c, d, a) > 0) != (orient(c, d, b) > 0) and (orient(a, b, c) > 0) != (orient(a, b, d) > 0)
                       for o in others for c, d in zip(o, o[1:], strict=False))]

    rng = np.random.default_rng(3)
    pts = [(x, float(np.sin(x)), .5, x) for x in np.linspace(0, 20, 60)]
    others = [[(float(x), float(y), .5, i) for i, (x, y) in enumerate(rng.uniform(-2, 22, size=(5, 2)))]
              for _ in range(40)] + [[(2, -3, .5, 0), (2, 3, .5, 1)], [(50, 50, .5, 0), (60, 60, .5, 1)]]
    assert crossing_indices(pts, others) == plain(pts, others) and crossing_indices(pts, others)
    assert crossing_indices(pts, []) == [] and crossing_indices(pts[:1], others) == []
    assert stroke_box([(1, 2, None, 0), (3, -1, None, 1)], 1.0) == (0.5, -1.5, 3.5, 2.5)


def test_pixel_eraser_makes_mask():
    buf = io.BytesIO()
    Image.new("RGBA", (20, 20), (0, 0, 0, 255)).save(buf, format="PNG")
    out, mask = erase_pixels(buf.getvalue(), [PixelEraserStroke(points=[(10, 10)], width_px=4)])
    im, m = Image.open(io.BytesIO(out)), Image.open(io.BytesIO(mask))
    assert im.getpixel((10, 10))[3] == 0 and im.getpixel((0, 0))[3] == 255
    assert m.getpixel((10, 10)) == 255 and m.getpixel((0, 0)) == 0


def test_pixel_eraser_box_matches_whole_image_drawing():
    """線の範囲だけで計算しても、絵全体に線を描いて引いた（前の作り方）のと同じ画素になる。"""
    from PIL import ImageChops, ImageDraw

    def whole(base_png, strokes):
        im = Image.open(io.BytesIO(base_png)).convert("RGBA")
        alpha, erased = im.getchannel("A"), Image.new("L", im.size, 0)
        for s in strokes:
            m = Image.new("L", im.size, 0)
            d, r = ImageDraw.Draw(m), s.width_px / 2
            if len(s.points) > 1:
                d.line(s.points, fill=255, width=max(1, round(s.width_px)), joint="curve")
            for x, y in s.points:
                d.ellipse((x - r, y - r, x + r, y + r), fill=255)
            alpha = ImageChops.subtract(alpha, m.point(lambda v, o=s.opacity: round(v * o)))
            erased = ImageChops.lighter(erased, m)
        return np.asarray(alpha), np.asarray(erased.point(lambda v: 255 if v else 0))

    rng = np.random.default_rng(5)
    a = rng.integers(0, 256, size=(90, 120, 4), dtype=np.uint8)
    base = _png_bytes(Image.fromarray(a, "RGBA"))
    for _ in range(25):
        strokes = [PixelEraserStroke(points=[tuple(map(float, p)) for p in rng.uniform(-20, 140, size=(int(rng.integers(1, 6)), 2))],
                                     width_px=float(rng.uniform(0.5, 30)), opacity=float(rng.choice([1, .5, .33, .7])))
                   for _ in range(int(rng.integers(1, 4)))]
        out, mask = erase_pixels(base, strokes)
        alpha, erased = whole(base, strokes)
        assert (np.asarray(Image.open(io.BytesIO(out)))[..., 3] == alpha).all()
        assert (np.asarray(Image.open(io.BytesIO(out)))[..., :3] == a[..., :3]).all()
        assert (np.asarray(Image.open(io.BytesIO(mask))) == erased).all()


# ---------------------------------------------------------------- ページの層


def _png_bytes(img):
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


PID, P1, L1, T1, I1 = "9" * 32, "a" * 32, "b" * 32, "c" * 32, "d" * 32
FRAME_STYLE = {"line_width_mm": 0.5, "line_color": "#000000"}
TYPESETTING = {"line_spacing_ratio": 0.3, "line_break": "character", "tate_chu_yoko_max_digits": 2,
               "tate_chu_yoko_marks": True, "align": "start"}


def _content(**over):
    panel = SimpleNamespace(id=P1, order=0, frame={"polygon_mm": [(0, 0), (30, 0), (30, 20), (0, 20)]},
                            frame_style=None, image_id="img1",
                            image_placement={"crop_px": [0, 0, 10, 10], "dest_box_mm": [0, 0, 30, 20]},
                            adjustments=[])
    hand = SimpleNamespace(id=L1, panel_id=P1, role="human_hand", image_id="img2", stack_order=0, opacity=1.0,
                           visible=True, placement={"crop_px": [0, 0, 4, 4], "dest_box_mm": [2, 2, 6, 6]},
                           adjustments=[], stroke_revision=0, image_stroke_revision=None)
    text = SimpleNamespace(id=T1, order=0, item_kind="dialogue", text="あい", speaker=None, box_mm=[5, 25, 15, 40],
                           font_size_pt=12, font_family="ipag", writing_direction="vertical",
                           decoration={"fill": "#000000"}, ruby=[], transform=None, opacity=1.0, adjustments=[],
                           panel_id=P1, tail_target_mm=None, joined_to_previous=False, spans=[], typesetting=None,
                           balloon_shape={"kind": "custom", "outline_mm": [(4, 24), (16, 24), (16, 41), (4, 41)],
                                          "line_width_mm": 0.3, "line_color": "#000000", "fill_color": "#ffffff"})
    tone = SimpleNamespace(id=I1, item_kind="tone", box_mm=[0, 0, 30, 20], transform=None, stack_order=0, opacity=1.0,
                           visible=True, adjustments=[],
                           spec={"kind": "dots", "target": {"kind": "panel", "panel_id": P1}, "density": 0.3,
                                 "lines_per_inch": 30})
    values = dict(page_id=PID, spec=SPEC, text_direction="vertical", preferences={"frame_style": FRAME_STYLE, "typesetting": TYPESETTING},
                  panels=[panel], layers=[hand], texts=[text], page_items=[tone],
                  images={"img1": "x", "img2": "y"})
    values.update(over)
    return PageContent(**values)


IMAGES = {"img1": _png_bytes(Image.new("RGBA", (10, 10), (200, 100, 50, 255))),
          "img2": _png_bytes(Image.new("RGBA", (4, 4), (0, 0, 255, 255)))}


def _render(content):
    return render_page(content, DPI, lambda iid: IMAGES[iid],
                       lambda items: render_texts(items, NODE, TEXT_SCRIPT), lambda f: font_path(FONT_DIR, f))


@needs_font
def test_render_page_layer_order_and_names():
    page = _render(_content())
    assert (page.width, page.height) == canvas_size_px(SPEC, DPI)
    top = [(n.name, n.marker) for n in page.nodes]
    assert top == [("紙", f"{PID}-paper"), ("コマ1", P1), ("トーン・図形", f"{PID}-items"),
                   (LAYER_NAME_PANEL_FRAME, f"{PID}-frame"), ("人の手", f"{PID}-hand"),
                   ("フキダシ", f"{PID}-balloons"), ("写植", f"{PID}-typeset"), ("描き文字", f"{PID}-sfx")]
    # 枠はコマの絵より上（10.3）。紙は白で全面
    assert page.nodes[0].image.getpixel((0, 0)) == (255, 255, 255, 255)
    assert [c.marker for c in page.nodes[1].children] == [f"{P1}-image"]
    assert [c.marker for c in page.nodes[4].children] == [L1]
    assert [c.marker for c in page.nodes[5].children] == [f"{T1}-balloon"]
    typeset = page.nodes[6].children[0]
    assert typeset.marker == T1 and typeset.text["text"] == "あい"
    assert np.asarray(typeset.image)[..., 3].sum() > 0  # 文字の層に見える画素がある
    assert all(n.full_name.endswith(f"[{n.marker}]") for n in page.nodes)


def test_render_page_refuses_missing_values():
    with pytest.raises(RenderRefused, match="枠の線"):
        _render(_content(preferences={}))
    c = _content()
    c.texts[0].decoration = {}
    c.panels[0].frame_style = FRAME_STYLE
    with pytest.raises(RenderRefused, match="decoration.fill"):
        render_page(c, DPI, lambda iid: IMAGES[iid], lambda items: [], lambda f: "x")
    c = _content()
    c.texts[0].font_family = None
    with pytest.raises(RenderRefused, match="書体"):
        render_page(c, DPI, lambda iid: IMAGES[iid], lambda items: [], lambda f: "x")


@needs_font
def test_text_render_and_font_lookup(tmp_path):
    got = render_texts([{"id": "t", "text": "縦書き", "font_path": font_path(FONT_DIR, "ipag"), "font_size_px": 24,
                         "vertical": True, "color": "#000000", "box_w_px": 40, "box_h_px": 100,
                         "typesetting": TYPESETTING, "spans": [], "language": "ja",
                         "decoration": {"fill": "#000000"}, "ruby": []}], NODE, TEXT_SCRIPT)
    assert np.asarray(got[0].image)[..., 3].sum() > 0 and got[0].lines == 1 and not got[0].overflow
    with pytest.raises(TextRenderError, match="無い"):
        font_path(FONT_DIR, "存在しない書体")
    with pytest.raises(TextRenderError, match="V3_FONT_DIR"):
        font_path(None, "ipag")


def test_pdf_on_paper(tmp_path):
    paper = (SPEC.trim_width_mm + 20, SPEC.trim_height_mm + 20)
    size = paper_size_px(paper, DPI)
    out = tmp_path / "p.pdf"
    write_print_pdf([Image.new("RGB", size, (255, 255, 255))], SPEC, DPI, "flate", out, paper)
    box = pypdf.PdfReader(out).pages[0].mediabox
    assert float(box.width) == pytest.approx(paper[0] / 25.4 * 72, abs=0.5)
    with pytest.raises(ValueError, match="小さい"):
        write_print_pdf([Image.new("RGB", (10, 10))], SPEC, DPI, "flate", out, (10, 10))


# ---------------------------------------------------------------- PSD の書き出しと戻し


def test_clean_name_and_marker():
    mk = "e" * 32
    assert clean_name(f"コマ1 [{mk}]\x00") == f"コマ1 [{mk}]"
    assert clean_name(f"コマ1 [{mk}] #2") == f"コマ1 [{mk}]"
    assert marker_of(f"紙 [{mk}-paper]\x00") == f"{mk}-paper"
    assert marker_of("名前を変えた層") is None


def _write_psd(tmp_path, name, layers, w, h):
    req = build_psd_request(w, h, None, layers, tmp_path / name)
    write_layered_psd(req, NODE, WRITER, 60)
    return (tmp_path / name).read_bytes()


@needs_font
def test_psd_round_trip_matching(tmp_path):
    page = _render(_content())
    w, h = page.width, page.height
    exported_dir = tmp_path / "exp"
    exported_dir.mkdir()
    layers = psd_layers_from_nodes(page.nodes, exported_dir)
    _write_psd(tmp_path, "out.psd", layers, w, h)

    # 書き出したときの層の記録（ExportRun.outputs の layers と同じ形）
    exported = {}

    def walk(nodes):
        for n in nodes:
            if n.children is not None:
                walk(n.children)
            else:
                exported[n.marker] = ExportedLayer(n.marker, n.table, n.left, n.top, n.image)

    walk(page.nodes)

    # 人が直した PSD を作る：コマの絵の画素を変え、人の手の層の名前を変え、コマのグループに新しい層を描き、
    # 描き文字（無い）・フキダシの層を消し、紙の名前に Krita の NUL、コマ枠に GIMP の「 #1」を付ける
    edited = json.loads(json.dumps([la.model_dump(mode="json", exclude_none=True) for la in layers]))
    panel_group = edited[1]
    art = panel_group["children"][0]
    im = Image.open(art["png_path"]).copy()
    im.putpixel((im.width // 2, im.height // 2), (1, 2, 3, 255))
    im.save(tmp_path / "art2.png")
    art["png_path"] = str(tmp_path / "art2.png")
    Image.new("RGBA", (6, 6), (9, 9, 9, 255)).save(tmp_path / "new.png")
    panel_group["children"].append({"name": "描き足し", "png_path": str(tmp_path / "new.png"), "left": 20, "top": 20,
                                    "opacity": 1, "blend_mode": "normal", "hidden": False})
    edited[0]["name"] += "\x00"
    edited[3]["name"] += " #1"
    edited[4]["children"][0]["name"] = "名前を変えた"
    edited[5]["children"] = []
    req = {"width": w, "height": h, "composite_png": None, "output_path": str(tmp_path / "edited.psd"),
           "layers": edited}
    write_layered_psd(req, NODE, WRITER, 60)

    psd_path = tmp_path / "edited.psd"
    # 層の数・画素数の上限：超えたら展開せずに止める
    from psd_tools import PSDImage

    n_layers = len(list(PSDImage.open(psd_path).descendants()))
    with pytest.raises(Invalid, match="層が多すぎる"):
        read_psd(psd_path, max_pixels=w * h, max_layers=n_layers - 1)
    with pytest.raises(Invalid, match="画素が多すぎる"):
        read_psd(psd_path, max_pixels=w * h - 1, max_layers=n_layers)
    read = read_psd(psd_path, max_pixels=w * h, max_layers=n_layers)
    matches = match_layers(read, exported)
    kinds = {(m.kind, m.marker) for m in matches}
    assert ("changed", f"{P1}-image") in kinds
    assert ("renamed", L1) in kinds
    assert ("missing", f"{T1}-balloon") in kinds
    assert ("unchanged", f"{PID}-paper") in kinds and ("unchanged", f"{PID}-frame") in kinds
    new = [m for m in matches if m.kind == "new"]
    assert len(new) == 1 and new[0].layer.parent_marker == P1

    inv = np.linalg.inv(mm_to_px_matrix(SPEC, DPI))
    acts = import_actions(matches, lambda x, y: tuple((inv @ np.array([x, y, 1.0]))[:2]))
    changed = next(a for a in acts if a.kind == "changed")
    ex = exported[f"{P1}-image"]
    # 書き出したときの範囲に切った絵
    assert changed.image.size == ex.image.size and changed.table == "panels"
    added = next(a for a in acts if a.kind == "new")
    assert added.parent_marker == P1 and added.image.size == (6, 6)
    assert added.box_mm[2] - added.box_mm[0] == pytest.approx(6 / DPI * 25.4)


# ---------------------------------------------------------------- 処理と問い


def test_known_process_task_is_fixed():
    for process, (task, action) in KNOWN_PROCESSES.items():
        check_process_task(process, task, action)
        with pytest.raises(Invalid):
            check_process_task(process, "finishing", action)
    check_process_task("自分で登録した処理", "finishing", "propose")


def test_read_prompt_and_extract_questions():
    assert "希望" in build_read_prompt_question("短く")
    a = parse_read_prompt_answer('```json\n{"prompt":"x","negative_prompt":null,"unsure":[]}\n```')
    assert a.prompt == "x"
    q = build_extract_characters_question("あらすじ", ["既にいる人"])
    assert "既にいる人" in q and "あらすじ" in q
    got = parse_extract_characters_answer('{"characters":[{"name":"A","traits":null,"notes":"1行目"}]}')
    assert got[0].name == "A"


def test_線の控えの絵が無い_古い層は理由を返す():
    layer = SimpleNamespace(id="L", stroke_revision=0, image_id=None, image_stroke_revision=None)
    assert stroke_cache_problem(layer) is None
    layer.stroke_revision = 1
    assert "無い" in stroke_cache_problem(layer)
    layer.image_id, layer.image_stroke_revision = "I", 0
    assert "古い" in stroke_cache_problem(layer)
    layer.image_stroke_revision = 1
    assert stroke_cache_problem(layer) is None
