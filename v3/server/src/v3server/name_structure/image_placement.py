"""コマ・層の絵の切り抜きと置き場。人が画面で決めても、AIが決めても同じ形。"""
from pydantic import BaseModel, ConfigDict, model_validator


class ImagePlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 絵のどこを使うか（絵の画素の [x0, y0, x1, y1]）
    crop_px: tuple[int, int, int, int]
    # 切り抜いた所をページのどこに置くか（基本枠の座標・mm の [x0, y0, x1, y1]）。コマの枠の外へ出た分は枠で隠れる
    dest_box_mm: tuple[float, float, float, float]
    # 置いた後の回転（度、時計回り）
    rotation_deg: float = 0.0

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
