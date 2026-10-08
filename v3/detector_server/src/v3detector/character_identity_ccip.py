"""同一キャラ判定（CCIP）。「違う」で落とす専用。

注意（試作 p17・p43 の結果）: 似た別人を「同じ」と判定する。眼鏡の有無が違うだけの別人を 95%、
別の黒髪の男子を 94%、小さく写った少女と少年を 73% 「同じ」とした。
そのため「差が大きい（違う）」で候補を落とすためにだけ使う。「同じ」と出ても同一人物の
証拠にはならない（通す判断に使ってはいけない）。
閾値は呼ぶ側が渡す。None のときは imgutils の既定（ccip_default_threshold）をそのまま返す。
"""
from PIL import Image
from imgutils.metrics import (ccip_default_threshold, ccip_difference,
                              ccip_extract_feature)

NOTE = ("CCIP は違うで落とす専用。似た別人を94〜95%同じと判定したので、"
        "same=true は同一人物の証拠にならない。通す判断に使わない。")


def ccip_compare(a: Image.Image, b: Image.Image, threshold: float | None = None) -> dict:
    th = ccip_default_threshold() if threshold is None else threshold
    diff = float(ccip_difference(ccip_extract_feature(a), ccip_extract_feature(b)))
    return {
        "difference": round(diff, 4),
        "threshold": float(th),
        "threshold_is_imgutils_default": threshold is None,
        "same": diff < th,
        "note": NOTE,
    }
