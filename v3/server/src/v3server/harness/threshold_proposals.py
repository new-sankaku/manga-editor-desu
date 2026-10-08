"""ハーネスが読む閾値の一覧と、値の案（出典つき）。

- 閾値は作品ごとに人が置く（set_threshold の操作）。ここは置くための材料を出すだけで、黙って値を入れない
- 案の値は、試作で測った数があるものだけ。測っていないものは value を None にし、測った数があればそれを出典として並べる
- 案を使って置くときの検証の状態は unverified（その作品で人が確かめたら verified に変える。V3ハーネス設計 7章）
"""

from typing import Any

from v3server.harness.overall_review_steps import NEEDED as OVERALL_NEEDED
from v3server.harness.overall_review_steps import PREFIX as OVERALL_PREFIX
from v3server.harness.panel_drawing_steps import CONDITIONAL_THRESHOLDS, THRESHOLDS
from v3server.harness.upstream_versions import DRAWING_THRESHOLD_PREFIX

RESULTS = "llm_doc/V3検証の結果.md"

# 鍵 → 案。value が None の鍵は、測った数が無いか、測った数から下限・上限を決められないもの
PROPOSALS: dict[str, dict[str, Any]] = {
    DRAWING_THRESHOLD_PREFIX + "text_score": {
        "value": 0.05,
        "source": f"{RESULTS}（文字の検出器。文字あり38枚・なし10枚で、0.05 は見つけた33・誤り3、0.1 は31・2、0.2 は24・1、"
                  "0.3 は全部見逃した）",
    },
    DRAWING_THRESHOLD_PREFIX + "ccip_threshold": {
        "value": 0.178,
        "source": f"{RESULTS}（CCIP の既定の閾値。人物を切り抜いて比べると、別の人物を94〜95%「同じ」とした組があった。"
                  "「違う」で落とす専用に使う）",
    },
    DRAWING_THRESHOLD_PREFIX + "person_iou_min": {
        "value": None,
        "source": f"{RESULTS}（骨格の図を渡したときの IoU は約0.72〜0.81、形の指定なしは0.13前後。下限の値は測っていない）",
    },
    DRAWING_THRESHOLD_PREFIX + "person_score": {"value": None, "source": "測っていない"},
    DRAWING_THRESHOLD_PREFIX + "edge_px": {"value": None, "source": "測っていない"},
    DRAWING_THRESHOLD_PREFIX + "face_covered_max": {"value": None, "source": "測っていない"},
    OVERALL_PREFIX + "spread_black_max": {"value": None, "source": "測っていない"},
    OVERALL_PREFIX + "page_white_max": {"value": None, "source": "測っていない"},
}

# 鍵 → 何の閾値か・どの工程が読むか
MEANINGS: dict[str, dict[str, str]] = {
    **{DRAWING_THRESHOLD_PREFIX + k: {"meaning": v, "stage": "S4", "when": "いつも"} for k, v in THRESHOLDS.items()},
    **{DRAWING_THRESHOLD_PREFIX + k: {"meaning": v, "stage": "S4", "when": "条件が揃ったコマ"}
       for k, v in CONDITIONAL_THRESHOLDS.items()},
    **{OVERALL_PREFIX + k: {"meaning": v, "stage": "S6", "when": "いつも"} for k, v in OVERALL_NEEDED.items()},
}
MEANINGS[DRAWING_THRESHOLD_PREFIX + "face_covered_max"]["stage"] = "S4・S5"


def threshold_rows(current: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """current は作品の閾値 {鍵: {value, source, status}}。鍵ごとに今の値と案を並べる。"""
    if set(PROPOSALS) != set(MEANINGS):
        raise RuntimeError(f"案と意味の鍵が合わない: {sorted(set(PROPOSALS) ^ set(MEANINGS))}")
    return [{"key": k, **MEANINGS[k], "current": current.get(k), "proposal": PROPOSALS[k]} for k in MEANINGS]
