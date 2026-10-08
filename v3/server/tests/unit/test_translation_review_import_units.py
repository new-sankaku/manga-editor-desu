"""今のアプリのプロジェクトの読み取り・形の計算・行の案、確認の状態の移り方、締切の見込み。"""

import io
import json
import pathlib
import struct
import zipfile
from datetime import UTC, datetime, timedelta

import lz4.frame
import pytest

from v3server.current_app_import.fabric_geometry import css_color, object_polygon_px, path_points, point_in_polygon
from v3server.current_app_import.import_plan import TakenImage, build_import_plan, referenced_image_keys
from v3server.current_app_import.project_file_reader import (
    ProjectFileError,
    data_url_bytes,
    read_project_file,
    unpack_container,
)
from v3server.image_file_storage import inspect_image_file
from v3server.name_structure.reading_direction import PageSpec
from v3server.operations.review_operations import move_kind
from v3server.review_progress import PageStatus, estimate
from v3server.v3_error_types import Invalid

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "current_app_project_4pages.lz4"
A4 = PageSpec(frame_width_mm=180, frame_height_mm=270, trim_width_mm=210, trim_height_mm=297, bleed_mm=3,
              gutter_x_mm=2, gutter_y_mm=5)


def container(files: list[tuple[str, bytes]]) -> bytes:
    """js/core/compression/lz4.js の buffersToLz4Blob と同じ形。"""
    header = json.dumps([{"name": n, "size": len(b)} for n, b in files]).encode()
    return struct.pack("<I", len(header)) + header + lz4.frame.compress(b"".join(b for _, b in files))


def page_files(objects: list[dict], width=600, height=848.57) -> list[tuple[str, bytes]]:
    state = json.dumps(json.dumps({"version": "5.3.0", "objects": objects}))
    info = {"width": width, "height": height, "pageWidthMm": 210, "pageHeightMm": 297}
    return [("state_000000.json", b'"{}"'), ("state_000001.json", state.encode()),
            ("canvas_info.json", json.dumps(info).encode())]


# ---------------------------------------------------------------- 読み取り


def test_本物のファイルを読む():
    p = read_project_file(FIXTURE.read_bytes())
    assert not p.single_page and len(p.pages) == 4
    assert [len(x.canvas["objects"]) for x in p.pages] == [0, 10, 0, 2]
    assert p.pages[1].page_width_mm == 210 and p.pages[1].history_count > 0


def test_1ページのファイルも読み_最後の状態を使う():
    p = read_project_file(container(page_files([{"type": "rect"}])))
    assert p.single_page and p.pages[0].canvas["objects"] == [{"type": "rect"}] and p.pages[0].history_count == 1


@pytest.mark.parametrize("data", [b"", b"\x05\x00\x00\x00abc", b"\x02\x00\x00\x00{}xx"])
def test_形の違うファイルは止める(data):
    with pytest.raises(ProjectFileError):
        unpack_container(data)


def test_古いzipの形と中身の違う入れ物は止める():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.json", "{}")
    with pytest.raises(ProjectFileError):
        read_project_file(buf.getvalue())
    with pytest.raises(ProjectFileError, match="中身でない"):
        read_project_file(container([("other.bin", b"x")]))
    with pytest.raises(ProjectFileError, match="canvas_info"):
        read_project_file(container(page_files([])[:2]))


def test_dataURLはbase64だけ読む():
    assert data_url_bytes("data:image/png;base64,AAEC") == b"\x00\x01\x02"
    with pytest.raises(ProjectFileError):
        data_url_bytes("data:image/svg+xml,<svg/>")


# ---------------------------------------------------------------- 形の計算


def test_回転と反転のある四角の外形():
    rect = {"type": "rect", "left": 100, "top": 100, "width": 20, "height": 10, "originX": "center",
            "originY": "center", "angle": 90, "scaleX": 1, "scaleY": 1}
    pts = object_polygon_px(rect)
    xs, ys = sorted(round(x) for x, _ in pts), sorted(round(y) for _, y in pts)
    assert (xs[0], xs[-1], ys[0], ys[-1]) == (95, 105, 90, 110)
    flipped = object_polygon_px(rect | {"angle": 0, "flipX": True})
    assert sorted(round(x) for x, _ in flipped) == [90, 90, 110, 110]


def test_曲線の道を点にする():
    (ring,) = path_points([["M", 0, 0], ["Q", 10, 10, 20, 0], ["L", 20, 20], ["Z"]])
    assert ring[0] == (0, 0) and (20, 20) in ring and len(ring) > 4
    assert point_in_polygon((10, 10), [(0, 0), (20, 0), (20, 20), (0, 20)])


def test_色():
    hex_, alpha = css_color("rgba(255, 0, 0, 0.5)")
    assert hex_.upper() == "#FF0000" and alpha == 0.5
    assert css_color("transparent") is None and css_color(None) is None
    assert css_color("black")[1] == 1


# ---------------------------------------------------------------- 行の案と報告


def fixture_plan(tmp_dir: pathlib.Path):
    proj = read_project_file(FIXTURE.read_bytes())
    imgs = {}
    for i, (k, v) in enumerate(referenced_image_keys(proj).items()):
        path = tmp_dir / f"{i}.bin"
        path.write_bytes(data_url_bytes(v))
        st = inspect_image_file(path)
        imgs[k] = TakenImage(st.sha256, st.media_type, st.width, st.height, st.dpi)
    return proj, build_import_plan(proj, A4, "rtl", imgs, FIXTURE.name, "試験")


def test_本物のファイルの物はどれも1回だけ報告に出る(tmp_path):
    proj, plan = fixture_plan(tmp_path)
    keys = [(e.page_index, e.object_index) for e in plan.entries if e.object_index is not None]
    assert sorted(keys) == sorted((p.index, i) for p in proj.pages for i in range(len(p.canvas["objects"])))
    counts = plan.counts()
    assert counts["source_objects"] == 12 and counts["pages"] == 4
    assert {e.source_kind for e in plan.entries if e.status == "unmapped"} == {"pen_stroke"}
    assert all(e.note for e in plan.entries if e.status in ("unmapped", "converted"))
    assert len(plan.panels) == 3 and len(plan.texts) == 4 and len(plan.panel_images) == 1 and len(plan.layers) == 1


def test_コマの位置は基本枠からのmmで_読む順は右から(tmp_path):
    _, plan = fixture_plan(tmp_path)
    p2 = [p for p in plan.panels if p.page_id == plan.pages[1].id]
    assert [p.order for p in p2] == [0, 1]
    # 見本は上下2段（斜めの境目）。上の段が先
    first, second = (min(y for _, y in p.frame["polygon_mm"]) for p in p2)
    assert first < second
    assert all(p.frame_style == {"line_width_mm": 0.6, "line_color": "#000000"} for p in plan.panels)
    for p in plan.panels:
        assert all(-A4.bleed_mm - 20 < x < A4.trim_width_mm and -20 < y < A4.trim_height_mm
                   for x, y in p.frame["polygon_mm"])


def test_寸法の違うページは物を入れず報告する():
    proj = read_project_file(container(page_files([{"type": "rect", "isPanel": True}])))
    proj.pages[0].page_width_mm = 182
    plan = build_import_plan(proj, A4, "rtl", {}, "x", "試験")
    assert len(plan.pages) == 1 and not plan.panels
    assert [e.status for e in plan.entries if e.object_index is not None] == ["unmapped"]


def test_入口で止めた絵は入れず理由を残す():
    proj = read_project_file(FIXTURE.read_bytes())
    blocked = {k: TakenImage(None, None, None, None, None, blocked="判定で止めた") for k in referenced_image_keys(proj)}
    plan = build_import_plan(proj, A4, "rtl", blocked, "x", "試験")
    assert not plan.images
    assert sum(1 for e in plan.entries if "判定で止めた" in e.note) == 2


# ---------------------------------------------------------------- 確認の状態


def test_確認の状態の移り方():
    assert move_kind("draft", "in_review") == "submit"
    assert move_kind("needs_changes", "in_review") == "submit"
    assert move_kind("in_review", "approved") == "decide"
    assert move_kind("approved", "draft") == "decide"
    for before, after in (("draft", "approved"), ("needs_changes", "approved"), ("approved", "needs_changes")):
        with pytest.raises(Invalid):
            move_kind(before, after)


def test_締切の見込み_未検証():
    now = datetime(2026, 10, 8, tzinfo=UTC)
    created = now - timedelta(days=10)
    rest = [PageStatus("p2", 2, "draft"), PageStatus("p3", 3, "in_review")]
    e = estimate(now, created, 5, rest, now + timedelta(days=3))
    assert e["per_page_seconds"] == timedelta(days=2).total_seconds()
    assert e["projected_finish"] == now + timedelta(days=4) and e["on_track"] is False
    assert e["late_page_ids"] == ["p3"] and "未検証" in e["note"]
    none = estimate(now, created, 0, rest, None)
    assert none["projected_finish"] is None and none["reason"]
