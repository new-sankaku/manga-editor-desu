"""割りの単調さの目安（試作 p40、課題15・19・261）。枠の外接する四角から数える。
試作 p40：検査を通った LLM の割り41と市販9ページで、面積のばらつきの中央値0.582・0.45、上の辺が揃う割合0.667・0.5。
LLM の41中15は形が1種だけ（市販は最低2種）。1ページの数では弱くしか分けられないので、ここでは話全体（ページをまたいで）で見る。
斜めのコマは外接する四角で数えるので、斜めの効果は数に出ない。"""
import statistics
from typing import TypedDict

from v3server.name_checks.check_report_types import (
    Bound,
    CheckResult,
    Finding,
    Thresholds,
    no_data_result,
    rounded,
)
from v3server.name_structure.name_draft_schema import NameDraft, NamePage
from v3server.panel_layout.panel_geometry import (
    FLOAT_EPS,
    box_area,
    box_height,
    box_width,
    polygon_bbox,
)

THRESHOLD_KEYS = {
    "aspect_wide_min": "横長とみなす縦横比（幅÷高さ）の下限（形の種類を数える境目）",
    "aspect_tall_max": "縦長とみなす縦横比（幅÷高さ）の上限（形の種類を数える境目）",
    "area_cv_median_min": "面積のばらつき（標準偏差÷平均）の、ページの中央値の下限",
    "area_max_min_median_min": "いちばん大きいコマ÷いちばん小さいコマの、ページの中央値の下限",
    "single_shape_page_ratio_max": "形が1種類だけのページの割合の上限",
    "full_width_ratio_median_max": "基本枠の幅いっぱいのコマの割合の、ページの中央値の上限",
    "top_aligned_ratio_median_max": "上の辺がほかのコマと揃うコマの割合の、ページの中央値の上限",
}

_NO_FRAME = "枠の無いコマがある（コマ割りの計算の前）"


class PageMonotony(TypedDict):
    page: int
    n: int
    area_cv: float
    area_max_min: float
    # 形（横長・ほぼ四角・縦長）の種類の数。境目の閾値が渡されていなければ None
    shapes: int | None
    full_width_ratio: float
    top_aligned_ratio: float


def page_monotony(page: NamePage, draft: NameDraft, aspect_wide_min: float | None, aspect_tall_max: float | None) -> PageMonotony:
    """1ページの目安。コマが2つ未満のページには使わない（呼ぶ側で除く）。
    上の辺が揃うかは、浮動小数の誤差の幅だけ許して等しいかで見る（p40 はページの高さの2%を許していた。これは閾値になるので持たない）。"""
    W = draft.page_spec.frame_width_mm
    boxes = [polygon_bbox(p.frame.polygon_mm) for p in page.panels]
    areas = [box_area(b) for b in boxes]
    shapes = None
    if aspect_wide_min is not None and aspect_tall_max is not None:
        def kind(b: tuple[float, float, float, float]) -> int:
            r = box_width(b) / box_height(b)
            return 0 if r > aspect_wide_min else (2 if r < aspect_tall_max else 1)
        shapes = len({kind(b) for b in boxes})
    tops = [b[1] for b in boxes]
    aligned = sum(1 for i, t in enumerate(tops) if any(abs(t - u) <= FLOAT_EPS for j, u in enumerate(tops) if j != i))
    return PageMonotony(
        page=page.page, n=len(boxes),
        area_cv=statistics.pstdev(areas) / statistics.mean(areas),
        area_max_min=max(areas) / min(areas),
        shapes=shapes,
        full_width_ratio=sum(1 for b in boxes if b[0] <= FLOAT_EPS and b[2] >= W - FLOAT_EPS) / len(boxes),
        top_aligned_ratio=aligned / len(boxes),
    )


def _median_result(check_id: str, title: str, rows: list[PageMonotony], metric: str, thresholds: Thresholds, key: str,
                   bound: Bound) -> CheckResult:
    """ページごとの値の中央値に閾値を当てる。外れたら、閾値の側を外れたページを挙げる。"""
    med = statistics.median(r[metric] for r in rows)
    if key not in thresholds:
        return CheckResult(check_id=check_id, title=title, status="閾値未設定", value=rounded(med), threshold_key=key)
    lim = float(thresholds[key])
    out = med > lim if bound == "max" else med < lim
    findings = []
    if out:
        findings = [Finding(page=r["page"], value=rounded(r[metric]), note=title)
                    for r in rows if (r[metric] > lim if bound == "max" else r[metric] < lim)]
    return CheckResult(check_id=check_id, title=title, status="不合格" if out else "合格", value=rounded(med),
                       threshold_key=key, threshold_value=lim, findings=findings)


def run_monotony_checks(draft: NameDraft, thresholds: Thresholds) -> list[CheckResult]:
    ids = [("area_cv_median", "面積のばらつき（中央値）"), ("area_max_min_median", "大小の差（中央値）"),
           ("single_shape_page_ratio", "形が1種類のページの割合"), ("full_width_ratio_median", "幅いっぱいのコマの割合（中央値）"),
           ("top_aligned_ratio_median", "上の辺が揃うコマの割合（中央値）")]
    if not all(p.frame is not None for p in draft.all_panels()):
        return [no_data_result(i, t, _NO_FRAME) for i, t in ids]
    pages = [pg for pg in draft.pages if len(pg.panels) >= 2]
    if not pages:
        return [no_data_result(i, t, "コマが2つ以上のページが無い") for i, t in ids]
    wide, tall = thresholds.get("aspect_wide_min"), thresholds.get("aspect_tall_max")
    rows = [page_monotony(pg, draft, wide, tall) for pg in pages]
    out = [
        _median_result(ids[0][0], ids[0][1], rows, "area_cv", thresholds, "area_cv_median_min", "min"),
        _median_result(ids[1][0], ids[1][1], rows, "area_max_min", thresholds, "area_max_min_median_min", "min"),
    ]
    if wide is None or tall is None:
        # 形を分ける境目も閾値なので、無ければ種類の数そのものが出せない
        out.append(CheckResult(check_id=ids[2][0], title=ids[2][1], status="閾値未設定", value=None,
                               threshold_key="aspect_wide_min・aspect_tall_max"))
    else:
        single = [r for r in rows if r["shapes"] == 1]
        ratio = len(single) / len(rows)
        key = "single_shape_page_ratio_max"
        if key not in thresholds:
            out.append(CheckResult(check_id=ids[2][0], title=ids[2][1], status="閾値未設定", value=rounded(ratio), threshold_key=key))
        else:
            lim = float(thresholds[key])
            bad = ratio > lim
            out.append(CheckResult(check_id=ids[2][0], title=ids[2][1], status="不合格" if bad else "合格", value=rounded(ratio),
                                   threshold_key=key, threshold_value=lim,
                                   findings=[Finding(page=r["page"], value=1, note="形が1種類") for r in single] if bad else []))
    out.append(_median_result(ids[3][0], ids[3][1], rows, "full_width_ratio", thresholds, "full_width_ratio_median_max", "max"))
    out.append(_median_result(ids[4][0], ids[4][1], rows, "top_aligned_ratio", thresholds, "top_aligned_ratio_median_max", "max"))
    return out
