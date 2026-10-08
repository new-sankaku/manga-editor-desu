"""手の枠と切り抜き（imgutils の detect_hands）。移す元は p21・p42。

score の下限は呼ぶ側が渡す。None なら imgutils の既定。
切り抜きは枠の周りに margin_ratio（枠の長辺に対する比。呼ぶ側が渡す）を足して画像の中に収める。
"""
import base64
import io

from PIL import Image
from imgutils.detect import detect_hands


def detect_hand_boxes(image: Image.Image, score_threshold: float | None = None) -> list[dict]:
    kw = {} if score_threshold is None else {"conf_threshold": score_threshold}
    return [{"x0": int(b[0]), "y0": int(b[1]), "x1": int(b[2]), "y1": int(b[3]),
             "score": round(float(s), 3)} for b, _l, s in detect_hands(image, **kw)]


def crop_box(image: Image.Image, box: dict, margin_ratio: float) -> Image.Image:
    m = int(margin_ratio * max(box["x1"] - box["x0"], box["y1"] - box["y0"]))
    return image.crop((max(box["x0"] - m, 0), max(box["y0"] - m, 0),
                       min(box["x1"] + m, image.width), min(box["y1"] + m, image.height)))


def detect_hands_with_crops(image: Image.Image, score_threshold: float | None,
                            margin_ratio: float | None) -> dict:
    """margin_ratio が None のときは切り抜きを付けない。付ける場合は PNG の base64。"""
    hands = detect_hand_boxes(image, score_threshold)
    if margin_ratio is not None:
        for hd in hands:
            buf = io.BytesIO()
            crop_box(image, hd, margin_ratio).save(buf, format="PNG")
            hd["crop_png_base64"] = base64.b64encode(buf.getvalue()).decode()
    return {"width": image.width, "height": image.height, "hands": hands}
