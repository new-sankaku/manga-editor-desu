"""置き方（V3細部の決めごと 10.4「置き方」：位置・角度・拡大・傾き・反転）。絵・文字・図形・トーンで同じ形を使う。

位置と拡大は、物ごとの箱（絵は ImagePlacement.dest_box_mm、文字は box_mm、図形・トーンは box_mm）で持つ。
ここは箱の真ん中を中心にした回転・傾き（せん断）・反転だけを持つ。種類ごとに別の形を作らない。

当てる順（箱の真ん中を原点にして）：反転 → 傾き → 回転。画面と書き出しで同じ順にする（transform_matrix の1か所）。
"""

import math

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

# 傾きは ±90 度に近づくと形がつぶれて戻せなくなる。90 度ちょうどは受け付けない（数の決まりで、見た目の閾値ではない）
_SKEW_LIMIT = 89.0


class ItemTransform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 回転（度、時計回り）
    rotation_deg: float = 0.0
    # 傾き（度）。x は横へ、y は縦へずらす
    skew_x_deg: float = Field(default=0.0, ge=-_SKEW_LIMIT, le=_SKEW_LIMIT)
    skew_y_deg: float = Field(default=0.0, ge=-_SKEW_LIMIT, le=_SKEW_LIMIT)
    # 反転（左右・上下）
    flip_h: bool = False
    flip_v: bool = False

    def is_identity(self) -> bool:
        return (self.rotation_deg % 360 == 0 and self.skew_x_deg == 0 and self.skew_y_deg == 0
                and not self.flip_h and not self.flip_v)


def transform_matrix(t: ItemTransform, box: tuple[float, float, float, float]) -> np.ndarray:
    """箱の座標の点を、置き方を当てた後の座標へ移す 3x3 の行列。箱と同じ単位（mm でも画素でも）。"""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    to_origin = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]], float)
    back = np.array([[1, 0, cx], [0, 1, cy], [0, 0, 1]], float)
    flip = np.diag([-1.0 if t.flip_h else 1.0, -1.0 if t.flip_v else 1.0, 1.0])
    skew = np.array([[1, math.tan(math.radians(t.skew_x_deg)), 0],
                     [math.tan(math.radians(t.skew_y_deg)), 1, 0], [0, 0, 1]], float)
    a = math.radians(t.rotation_deg)
    # y が下へ増える座標なので、この形で時計回りになる
    rot = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]], float)
    return back @ rot @ skew @ flip @ to_origin


def apply_matrix(m: np.ndarray, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for x, y in points:
        v = m @ np.array([x, y, 1.0])
        out.append((float(v[0]), float(v[1])))
    return out
