"""1ページ3コマのネームを v3/server の形（NameDraft）で組み、v3/server の name_checks を掛ける。
measured を渡すと、人数を描けた絵から測った値に置き換えて掛ける（S6 総合で、描いた物がネームどおりかを見る）。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from harness_config import STORE
from v3server.name_checks.name_check_runner import run_name_checks
from v3server.name_structure.name_draft_schema import FigureInPanel, NameDraft, NamePage, NamePanel
from v3server.name_structure.reading_direction import PageSpec

SPEC = PageSpec(frame_width_mm=150, frame_height_mm=220, trim_width_mm=182, trim_height_mm=257, bleed_mm=3,
                gutter_x_mm=2, gutter_y_mm=5)
# 試作の閾値（V3ハーネス設計 7章の「作りながら決める」の初めの値として、この試作で置いた）
THRESHOLDS = {"people_per_panel_max": 2, "close_shot_run_max": 2, "same_shot_angle_next_max": 1}


def _people(n: int) -> list[FigureInPanel]:
    return [FigureInPanel(name=f"人物{i + 1}", face="中", facing="正面") for i in range(n)]


def build_draft(panels: list[dict], measured: dict[int, int] | None) -> NameDraft:
    ps = []
    for p in panels:
        n = p["expected_persons"] if measured is None else measured[p["panel"]]
        ps.append(NamePanel(n=p["panel"], size="中", shape="四角", shot=p["shot"], angle="目の高さ", people=_people(n),
                            background="簡略", scene=1, role="承", hook=False, content=p["target_ja"], balloons=[], sfx=[]))
    page = NamePage(page=1, spread=False, rows=[[1], [2, 3]], panels=ps, row_height_ratios=[1.0, 1.0],
                    cell_width_ratios=[[1.0], [1.0, 1.0]])
    return NameDraft(reading_direction="right_to_left", page_spec=SPEC, first_page_is_left=True, pages=[page])


def run_page_name_checks(panels: list[dict], measured: dict | None) -> dict:
    m = None if measured is None else {int(k): v for k, v in measured.items()}
    rep = run_name_checks(build_draft(panels, m), THRESHOLDS)
    counts: dict[str, int] = {}
    for r in rep.results:
        counts[r.status] = counts.get(r.status, 0) + 1
    failed = [line for r in rep.results if r.status == "不合格" for line in r.report_lines()]
    return {"counts": counts, "failed_lines": failed, "passed": counts.get("不合格", 0) == 0,
            "measured": measured}


def compose_page(images: dict, dest: Path) -> Path:
    """上の段にコマ1、下の段にコマ2・3（右から読むので右がコマ2）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    W, H, g = 600, 860, 12
    page = Image.new("RGB", (W, H), "white")
    boxes = {1: (g, g, W - g, H // 2 - g // 2), 3: (g, H // 2 + g // 2, W // 2 - g // 2, H - g),
             2: (W // 2 + g // 2, H // 2 + g // 2, W - g, H - g)}
    for k, (x0, y0, x1, y1) in boxes.items():
        name = images.get(str(k)) or images.get(k)
        if not name:
            continue
        im = Image.open(STORE / name).convert("RGB")
        bw, bh = x1 - x0, y1 - y0
        s = max(bw / im.width, bh / im.height)
        im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
        l, t = (im.width - bw) // 2, (im.height - bh) // 2
        page.paste(im.crop((l, t, l + bw, t + bh)), (x0, y0))
    tmp = dest.with_suffix(".tmp.png")
    page.save(tmp)
    tmp.replace(dest)
    return dest
