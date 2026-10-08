"""読む向きと、ページの寸法の規格。値は作品の設定から渡す（ここに既定の値は置かない）。"""
from typing import Literal

from pydantic import BaseModel, Field

# 右から読む（日本の漫画）・左から読む（V3細部の決めごと 1.5）
ReadingDirection = Literal["right_to_left", "left_to_right"]


class PageSpec(BaseModel):
    """1ページの寸法（mm）。基本枠の左上を原点にし、x は右、y は下へ増える。"""

    # 基本枠（コマを置く範囲）の幅と高さ
    frame_width_mm: float = Field(gt=0)
    frame_height_mm: float = Field(gt=0)
    # 仕上がり（裁ち落とした後）の幅と高さ。基本枠の周りの余白を含む
    trim_width_mm: float = Field(gt=0)
    trim_height_mm: float = Field(gt=0)
    # 塗り足し（仕上がりの外へ伸ばす幅）
    bleed_mm: float = Field(ge=0)
    # コマの間の隙間。左右（同じ段の中）と上下（段と段の間）
    gutter_x_mm: float = Field(ge=0)
    gutter_y_mm: float = Field(ge=0)

    def frame_origin_in_trim(self) -> tuple[float, float]:
        """仕上がりの左上から見た基本枠の左上。基本枠は仕上がりの真ん中に置く。"""
        return ((self.trim_width_mm - self.frame_width_mm) / 2, (self.trim_height_mm - self.frame_height_mm) / 2)
