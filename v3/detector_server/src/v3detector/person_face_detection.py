"""人物・顔・頭の枠と、画像の端への接触を返す（dghs-imgutils、CPU）。

移す元は v3poc/common/detect.py。
閾値（score の下限）は呼ぶ側が渡す。None のときは imgutils の関数の既定に任せる
（コードに値を置かない）。端に接したとみなす画素数も呼ぶ側が渡す。
"""
from PIL import Image
from imgutils.detect import detect_faces, detect_heads, detect_person


def _box(b, w: int, h: int, edge_px: int) -> dict:
    (x0, y0, x1, y1), _label, score = b
    touch = "".join(
        k for k, v in (("T", y0 <= edge_px), ("B", y1 >= h - edge_px),
                       ("L", x0 <= edge_px), ("R", x1 >= w - edge_px)) if v
    )
    return {
        "x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1),
        "score": round(float(score), 3),
        "h_ratio": round((y1 - y0) / h, 3),
        "area_ratio": round((x1 - x0) * (y1 - y0) / (w * h), 3),
        "touch": touch,  # 接した辺の頭文字（T 上・B 下・L 左・R 右）
    }


def _kwargs(score_threshold: float | None) -> dict:
    # None なら imgutils の既定に任せる
    return {} if score_threshold is None else {"conf_threshold": score_threshold}


def detect_person_face_head(image: Image.Image, edge_px: int,
                            score_threshold: float | None = None) -> dict:
    w, h = image.size
    kw = _kwargs(score_threshold)
    return {
        "width": w, "height": h,
        "persons": [_box(b, w, h, edge_px) for b in detect_person(image, **kw)],
        "faces": [_box(b, w, h, edge_px) for b in detect_faces(image, **kw)],
        "heads": [_box(b, w, h, edge_px) for b in detect_heads(image, **kw)],
    }
