"""吹き出しが顔を隠す割合（試作 p47、検証の一覧 3-15）。重ねる前の顔の位置（FigureInPanel.face_box_mm）から計算する。
試作 p47：重ねた後の絵だけから顔の検出器で隠れを見つける手は、4割隠れても顔が見つかり（81→76）、使えなかった。
吹き出しを置く側は重ねる前の顔の位置を知っているので、楕円と顔の四角の重なりの計算だけで分かる。
同じコマの人物の顔だけを見る（吹き出しがコマをまたいで隣のコマの顔を隠す場合は見ない）。"""
from v3server.name_checks.check_report_types import (
    CheckResult,
    Finding,
    Thresholds,
    limit_result,
    no_data_result,
    rounded,
)
from v3server.name_structure.name_draft_schema import NameDraft
from v3server.panel_layout.panel_geometry import ellipse_box_coverage

THRESHOLD_KEYS = {
    "face_covered_ratio_max": "吹き出し1つが顔の四角を覆う割合の上限（0〜1）",
}


def face_coverages(draft: NameDraft) -> list[tuple[float, Finding]]:
    """（覆う割合, 指摘の形）を、位置のある吹き出しと顔の範囲の組ごとに。"""
    out = []
    for pg in draft.pages:
        for p in pg.panels:
            faces = [f for f in p.people if f.face_box_mm is not None]
            for k, b in enumerate(p.balloons):
                if b.box_mm is None:
                    continue
                for f in faces:
                    c = ellipse_box_coverage(b.box_mm, f.face_box_mm)
                    out.append((c, Finding(page=pg.page, panel=p.n, balloon=k, value=rounded(c), note=f"{f.name}の顔を覆う割合")))
    return out


def check_balloon_face_overlap(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    title = "吹き出しが顔を隠す割合"
    measured = face_coverages(draft)
    if not measured:
        return no_data_result("balloon_face_overlap", title, "同じコマに、位置のある吹き出しと顔の範囲の組が無い")
    value = rounded(max(v for v, _ in measured))
    return limit_result("balloon_face_overlap", title, thresholds, "face_covered_ratio_max", "max", value, measured)
