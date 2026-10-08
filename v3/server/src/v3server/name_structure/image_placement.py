"""コマ・層の絵の切り抜きと置き場。人が画面で決めても、AIが決めても同じ形。
回転・傾き・反転は、文字・図形と同じ置き方の形（item_transform.py の ItemTransform）を受け継ぐ。"""
import numpy as np
from pydantic import model_validator

from v3server.name_structure.item_transform import ItemTransform, transform_matrix


class ImagePlacement(ItemTransform):
    # 絵のどこを使うか（絵の画素の [x0, y0, x1, y1]）
    crop_px: tuple[int, int, int, int]
    # 切り抜いた所をページのどこに置くか（基本枠の座標・mm の [x0, y0, x1, y1]）。コマの枠の外へ出た分は枠で隠れる
    dest_box_mm: tuple[float, float, float, float]

    @model_validator(mode="after")
    def _boxes(self):
        x0, y0, x1, y1 = self.crop_px
        if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
            raise ValueError(f"切り抜きの範囲が正しくない: {self.crop_px}")
        a, b, c, d = self.dest_box_mm
        if c <= a or d <= b:
            raise ValueError(f"置き場の範囲が正しくない: {self.dest_box_mm}")
        return self

    def fits_image(self, width: int, height: int) -> bool:
        return self.crop_px[2] <= width and self.crop_px[3] <= height

    def image_px_to_page_mm(self) -> np.ndarray:
        """絵の画素の座標 → 基本枠の mm（置き方を当てた後）の 3x3 の行列。"""
        x0, y0, x1, y1 = self.crop_px
        a, b, c, d = self.dest_box_mm
        sx, sy = (c - a) / (x1 - x0), (d - b) / (y1 - y0)
        scale = np.array([[sx, 0, a - x0 * sx], [0, sy, b - y0 * sy], [0, 0, 1]], float)
        return transform_matrix(self, self.dest_box_mm) @ scale
