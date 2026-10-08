"""絵の中の文字の枠を返す（imgutils の detect_text）。

移す元は p22。試作では閾値 0.05（imgutils の既定）が合い、0.3 では全部見逃した。
この値はコードに置かない。呼ぶ側が score_threshold を渡す。None なら imgutils の既定。
"""
from PIL import Image
from imgutils.detect import detect_text


def detect_text_regions(image: Image.Image, score_threshold: float | None = None) -> dict:
    kw = {} if score_threshold is None else {"threshold": score_threshold}
    boxes = []
    for (x0, y0, x1, y1), _label, score in detect_text(image, **kw):
        boxes.append({"x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1),
                      "score": round(float(score), 3)})
    return {"width": image.width, "height": image.height, "texts": boxes}
