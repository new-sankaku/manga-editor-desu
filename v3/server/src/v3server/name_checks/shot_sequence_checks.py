"""写す範囲・角度・人物の並びの検査（試作 p27 `check.py`、V3ハーネス設計 6章）。
同じ範囲と角度の連続・寄りの連続・全身の間隔・場面の中の距離の組み合わせ・場所を見せるコマ・目の高さ以外の割合・人数・会話する2人の左右。"""
from v3server.name_checks.check_report_types import (
    CheckResult,
    Finding,
    Thresholds,
    count_limit_result,
    fixed_rule_result,
    limit_result,
    no_data_result,
    rounded,
)
from v3server.name_structure.name_draft_schema import NameDraft, NamePanel, ShotRange
from v3server.panel_layout.reading_direction_mirror import page_reading_sequence

THRESHOLD_KEYS = {
    "same_shot_angle_next_max": "前のコマと同じ範囲・同じ角度になる回数の上限（1話）",
    "close_shot_run_max": "寄り（胸から上・顔・部分）が続く数の上限",
    "pages_without_full_body_max": "全身か、それより広く写すコマが無いページが続く数の上限",
    "shot_classes_per_scene_min": "1つの場面の中の距離の種類（遠・中・寄り）の数の下限",
    "unusual_angle_ratio_max": "目の高さ以外の角度のコマの割合の上限（1話）",
    "characters_max": "登場人物の数の上限（1話）",
    "people_per_panel_max": "1コマに写る人物の数の上限",
}

# 課題35「寄りや胸から上の絵ばかり続く」の寄り
_CLOSE: set[ShotRange] = {"胸から上", "顔", "部分"}
# 課題38「全身のコマが少ない」：全身と、それより広く写すもの
_FULL_OR_WIDER: set[ShotRange] = {"遠景", "引き", "全身"}
# 課題34「遠景・中くらいの距離・寄りの組み合わせ」の3つへの分け方。形の7つの範囲を広い方から3つに分けた
_SHOT_CLASS: dict[ShotRange, str] = {"遠景": "遠", "引き": "遠", "全身": "中", "膝上": "中", "胸から上": "寄り", "顔": "寄り", "部分": "寄り"}
# 課題76・168「場所を見せるコマ」：広く写し、背景を描くコマ（p27 で場面の始めの引きとして数えた範囲と同じ）
_PLACE_SHOTS: set[ShotRange] = {"遠景", "引き"}
_PLACE_BACKGROUNDS = {"描き込む", "簡略"}


def _reading_panels(draft: NameDraft) -> list[tuple[int, NamePanel]]:
    pm = {p.n: p for p in draft.all_panels()}
    return [(pg.page, pm[n]) for pg in draft.pages for n in page_reading_sequence(pg) if n in pm]


def check_same_shot_angle_next(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """前のコマと写す範囲も角度も同じになる回数（p27）。"""
    seq = _reading_panels(draft)
    items = [Finding(page=pb, panel=b.n, value=f"{b.shot}・{b.angle}", note=f"コマ{a.n}と同じ範囲・角度")
             for (_, a), (pb, b) in zip(seq, seq[1:]) if (a.shot, a.angle) == (b.shot, b.angle)]
    return count_limit_result("same_shot_angle_next", "同じ範囲・角度の連続", thresholds, "same_shot_angle_next_max", items)


def check_close_shot_run(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """寄り（胸から上・顔・部分）が読む順に何個続くか（課題35）。ページをまたいで数える。"""
    seq = _reading_panels(draft)
    measured = []
    i = 0
    while i < len(seq):
        if seq[i][1].shot not in _CLOSE:
            i += 1
            continue
        j = i
        while j + 1 < len(seq) and seq[j + 1][1].shot in _CLOSE:
            j += 1
        run = j - i + 1
        measured.append((float(run), Finding(page=seq[i][0], panel=seq[i][1].n, value=run, note=f"ここから寄りが{run}個続く")))
        i = j + 1
    value = max((int(v) for v, _ in measured), default=0)
    return limit_result("close_shot_run", "寄りの連続", thresholds, "close_shot_run_max", "max", value, measured)


def check_full_body_interval(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """全身か、それより広く写すコマが無いページが何ページ続くか（課題38。個人の講座では2〜4ページに1回）。"""
    measured = []
    run_start: int | None = None
    run = 0
    for pg in draft.pages:
        if any(p.shot in _FULL_OR_WIDER for p in pg.panels):
            if run:
                measured.append((float(run), Finding(page=run_start, value=run, note=f"ここから{run}ページ全身のコマが無い")))
            run, run_start = 0, None
        else:
            run_start = pg.page if run == 0 else run_start
            run += 1
    if run:
        measured.append((float(run), Finding(page=run_start, value=run, note=f"ここから{run}ページ全身のコマが無い")))
    value = max((int(v) for v, _ in measured), default=0)
    return limit_result("full_body_interval", "全身のコマの間隔", thresholds, "pages_without_full_body_max", "max", value, measured)


def _scenes(draft: NameDraft) -> list[tuple[int, list[tuple[int, NamePanel]]]]:
    """読む順に、場面の番号が変わるところで区切る。同じ番号に戻ってきたら、別の区切りとして数える。"""
    out: list[tuple[int, list[tuple[int, NamePanel]]]] = []
    for page, p in _reading_panels(draft):
        if not out or out[-1][0] != p.scene:
            out.append((p.scene, []))
        out[-1][1].append((page, p))
    return out


def check_shot_classes_per_scene(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """場面の区切りごとに、遠・中・寄りの何種類を使ったか（課題34）。
    遠は遠景・引き、中は全身・膝上、寄りは胸から上・顔・部分。1コマだけの区切りは種類が1つになる。"""
    measured = []
    for scene, ps in _scenes(draft):
        kinds = sorted({_SHOT_CLASS[p.shot] for _, p in ps})
        measured.append((float(len(kinds)), Finding(page=ps[0][0], panel=ps[0][1].n, value=len(kinds),
                                                     note=f"場面{scene}の距離の種類 {kinds}")))
    value = min((int(v) for v, _ in measured), default=None)
    return limit_result("shot_classes_per_scene", "場面の中の距離の組み合わせ", thresholds, "shot_classes_per_scene_min", "min",
                        value, measured)


def _place_runs(draft: NameDraft) -> list[tuple[str, list[tuple[int, NamePanel]]]] | None:
    """読む順に、場所が変わるところで区切る。全部のコマに location があれば場所の名前で、どのコマにも無ければ場面の番号で区切る。
    一部のコマにだけあるときは、どちらで区切っても誤るので None を返す。"""
    seq = _reading_panels(draft)
    has = [p.location is not None for _, p in seq]
    if any(has) and not all(has):
        return None
    out: list[tuple[str, list[tuple[int, NamePanel]]]] = []
    for page, p in seq:
        key = p.location if p.location is not None else f"場面{p.scene}"
        if not out or out[-1][0] != key:
            out.append((key, []))
        out[-1][1].append((page, p))
    return out


def check_place_shown(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """場所が変わった後に、場所を見せるコマ（遠景か引きで、背景を描き込むか簡略に描く）があるか（課題76・168）。
    前に同じ場所で場所を見せていれば省いてよい（課題76）。場所は NamePanel.location、無ければ場面の番号を場所とみなす。"""
    title = "場所を見せるコマ"
    runs = _place_runs(draft)
    if runs is None:
        return no_data_result("place_shown", title, "場所（location）が一部のコマにしか無い")
    shown: set[str] = set()
    findings = []
    for place, ps in runs:
        has = any(p.shot in _PLACE_SHOTS and p.background in _PLACE_BACKGROUNDS for _, p in ps)
        if has:
            shown.add(place)
        elif place not in shown:
            findings.append(Finding(page=ps[0][0], panel=ps[0][1].n, value=place, note="場所が変わったのに場所を見せるコマが無い"))
    return fixed_rule_result("place_shown", title, findings)


def check_unusual_angle_ratio(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """目の高さ以外の角度のコマの割合（p27 で26〜39%、1つだけ70%）。"""
    ps = draft.all_panels()
    if not ps:
        return no_data_result("unusual_angle_ratio", "目の高さ以外の角度の割合", "コマが無い")
    ratio = sum(p.angle != "目の高さ" for p in ps) / len(ps)
    f = Finding(value=rounded(ratio), note=f"{len(ps)}コマ中{sum(p.angle != '目の高さ' for p in ps)}コマが目の高さ以外")
    return limit_result("unusual_angle_ratio", "目の高さ以外の角度の割合", thresholds, "unusual_angle_ratio_max", "max",
                        rounded(ratio), [(ratio, f)])


def check_characters(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """登場人物の数（課題100）。名前が違えば別の人物として数える。外れたら、各人物が初めて出るコマを挙げる。"""
    first: dict[str, Finding] = {}
    for page, p in _reading_panels(draft):
        for f in p.people:
            first.setdefault(f.name, Finding(page=page, panel=p.n, value=f.name, note="初めて出る"))
    return count_limit_result("characters", "登場人物の数", thresholds, "characters_max", list(first.values()))


def check_people_per_panel(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    measured = [(float(len(p.people)), Finding(page=page, panel=p.n, value=len(p.people), note="写る人物の数"))
                for page, p in _reading_panels(draft)]
    value = max((int(v) for v, _ in measured), default=None)
    return limit_result("people_per_panel", "1コマの人物の数", thresholds, "people_per_panel_max", "max", value, measured)


def check_conversation_sides(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """同じ場面の中で、2人が一緒に写るコマどうしの左右が入れ替わっていないか（課題39）。
    人物の範囲（box_mm）の中心の x で左右を決める。絵は読む向きで反転しないので、ページの上の左右をそのまま比べる。
    範囲の無い人物は見ない。1人だけのコマの向き（facing）からの推し量りはしない（課題40は対象外）。"""
    title = "会話する2人の左右"
    findings = []
    looked = 0
    for scene, ps in _scenes(draft):
        last: dict[tuple[str, str], tuple[bool, int]] = {}
        for page, p in ps:
            placed = sorted((f for f in p.people if f.box_mm is not None), key=lambda f: f.name)
            for i, a in enumerate(placed):
                for b in placed[i + 1:]:
                    looked += 1
                    a_left = (a.box_mm[0] + a.box_mm[2]) < (b.box_mm[0] + b.box_mm[2])
                    key = (a.name, b.name)
                    if key in last and last[key][0] != a_left:
                        findings.append(Finding(page=page, panel=p.n, value=f"{a.name}・{b.name}",
                                                note=f"コマ{last[key][1]}と左右が入れ替わっている"))
                    last[key] = (a_left, p.n)
    if looked == 0:
        return no_data_result("conversation_sides", title, "2人以上の人物の位置があるコマが無い")
    return fixed_rule_result("conversation_sides", title, findings)


SHOT_SEQUENCE_CHECKS = [
    check_same_shot_angle_next, check_close_shot_run, check_full_body_interval, check_shot_classes_per_scene, check_place_shown,
    check_unusual_angle_ratio, check_characters, check_people_per_panel, check_conversation_sides,
]
