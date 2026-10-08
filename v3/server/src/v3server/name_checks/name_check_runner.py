"""閾値を受け取って、ネームの検査を全部回す（V3ハーネス設計 6章・7章）。
閾値は呼ぶ側が Threshold の表から読んで辞書で渡す。渡されていない検査は「閾値未設定」として値だけ返し、合否を出さない。
閾値の要らない検査（6章の表で「要らない」）は合否を出す。枠・人物の位置・吹き出しの位置が無いと計算できない検査は「データなし」。"""
from v3server.name_checks import (
    balloon_text_checks,
    frame_shape_checks,
    page_monotony_metrics,
    page_rhythm_checks,
    shot_sequence_checks,
)
from v3server.name_checks.balloon_face_overlap import THRESHOLD_KEYS as FACE_KEYS
from v3server.name_checks.balloon_face_overlap import check_balloon_face_overlap
from v3server.name_checks.check_report_types import CheckReport, CheckResult, Thresholds
from v3server.name_structure.name_draft_schema import NameDraft

# 閾値の鍵と、その意味。画面と Threshold の表の行はこの鍵で引く
ALL_THRESHOLD_KEYS: dict[str, str] = {
    **frame_shape_checks.THRESHOLD_KEYS,
    **page_rhythm_checks.THRESHOLD_KEYS,
    **shot_sequence_checks.THRESHOLD_KEYS,
    **balloon_text_checks.THRESHOLD_KEYS,
    **page_monotony_metrics.THRESHOLD_KEYS,
    **FACE_KEYS,
}


def run_name_checks(draft: NameDraft, thresholds: Thresholds) -> CheckReport:
    """全部の検査を回す。知らない閾値の鍵が渡されたら、書き間違いを見落とさないよう例外にする。"""
    unknown = sorted(set(thresholds) - set(ALL_THRESHOLD_KEYS))
    if unknown:
        raise KeyError(f"知らない閾値の鍵 {unknown}")
    results: list[CheckResult] = []
    results += [f(draft, thresholds) for f in frame_shape_checks.FRAME_SHAPE_CHECKS]
    results += page_rhythm_checks.run_page_rhythm_checks(draft, thresholds)
    results += [f(draft, thresholds) for f in shot_sequence_checks.SHOT_SEQUENCE_CHECKS]
    results += [f(draft, thresholds) for f in balloon_text_checks.BALLOON_TEXT_CHECKS]
    results += page_monotony_metrics.run_monotony_checks(draft, thresholds)
    results.append(check_balloon_face_overlap(draft, thresholds))
    return CheckReport(results=results)
