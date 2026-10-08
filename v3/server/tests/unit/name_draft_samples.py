"""試験に使うネームの見本。試作 p12 の「段と比」の答え（v3poc/p12_layout/out/result.json）をそのまま写した。"""
from v3server.name_structure.name_draft_schema import NameDraft, NamePage, NamePanel
from v3server.name_structure.reading_direction import PageSpec, ReadingDirection

# 試作 p12 と同じ基本枠（150×220mm、隙間 横2・縦5mm）。仕上がりは B5 の 182×257mm、塗り足し3mm
SPEC = PageSpec(frame_width_mm=150, frame_height_mm=220, trim_width_mm=182, trim_height_mm=257, bleed_mm=3,
                gutter_x_mm=2, gutter_y_mm=5)

# 台本ごとのコマの大きさ（p12 の SCRIPTS）
P12_SIZES = {
    "s1_talk": ["小", "中", "小", "小", "大", "小"],
    "s2_reveal": ["中", "小", "小", "大"],
    "s3_action": ["小", "小", "中", "中", "小", "大", "小"],
}

# p12 の答え（rows の h と cells の n・w）。崩れの数は p12 の検査の結果
P12_ANSWERS = {
    # 崩れ0、「大」がいちばん広くない
    "s1_talk_B_0": ("s1_talk", [(2, [(1, 1)]), (3, [(2, 1)]), (2, [(3, 1), (4, 1)]), (4, [(5, 3), (6, 2)])]),
    # 崩れ0、「大」がいちばん広い
    "s1_talk_B_1": ("s1_talk", [(2, [(1, 1)]), (3, [(2, 3), (3, 2)]), (2, [(4, 1)]), (4, [(5, 3), (6, 2)])]),
    # 崩れ1：段の中を左から並べた
    "s1_talk_B_4": ("s1_talk", [(2, [(1, 1)]), (2, [(2, 1)]), (2, [(4, 1), (3, 1)]), (4, [(5, 3), (6, 2)])]),
    # 崩れ1：見せ場のコマ6を最後の段に置くために、コマ7を前の段に入れた
    "s3_action_B_0": ("s3_action", [(2, [(1, 1), (2, 1)]), (3, [(3, 1), (4, 1)]), (2, [(5, 1), (7, 1)]), (4, [(6, 1)])]),
}


def panel(n: int, **kw) -> NamePanel:
    base = dict(n=n, size="中", shape="四角", shot="膝上", angle="目の高さ", people=[], background="簡略", scene=1, role="承",
                hook=False, content=f"コマ{n}", balloons=[], sfx=[])
    base.update(kw)
    return NamePanel(**base)


def p12_page(answer_id: str, page_no: int = 1) -> NamePage:
    script, rows = P12_ANSWERS[answer_id]
    sizes = P12_SIZES[script]
    ns = sorted(n for _, cells in rows for n, _ in cells)
    return NamePage(page=page_no, spread=False, rows=[[n for n, _ in cells] for _, cells in rows],
                    panels=[panel(n, size=sizes[n - 1]) for n in ns],
                    row_height_ratios=[float(h) for h, _ in rows],
                    cell_width_ratios=[[float(w) for _, w in cells] for _, cells in rows])


def draft_of(pages: list[NamePage], direction: ReadingDirection = "right_to_left", first_page_is_left: bool = True,
             spec: PageSpec = SPEC) -> NameDraft:
    return NameDraft(reading_direction=direction, page_spec=spec, first_page_is_left=first_page_is_left, pages=pages)


def simple_pages(n_pages: int, per_page: int = 2) -> list[NamePage]:
    """1ページに1段・per_page コマの、番号が通しのページを並べる。"""
    pages = []
    n = 1
    for i in range(n_pages):
        ns = list(range(n, n + per_page))
        pages.append(NamePage(page=i + 1, spread=False, rows=[ns], panels=[panel(k) for k in ns],
                              row_height_ratios=[1.0], cell_width_ratios=[[1.0] * per_page]))
        n += per_page
    return pages
