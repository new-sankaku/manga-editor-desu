"""layer_split の試験。小さな合成画像で、線・ベタ・トーン・紙の白の分け方を確かめる。"""
import numpy as np
import pytest
from PIL import Image

from v3server.layer_split.line_solid_tone_split import SplitThresholds, grey_array, mean_difference, split_line_solid_tone

TH = SplitThresholds(solid_below=50, paper_white_from=215, line_on_from=128, line_value_ceiling=80)


def _sample():
    # 横に4つの帯：紙の白・トーン・ベタ・線（線の所の元の画素は灰色）
    pic = np.full((4, 8), 250, np.uint8)
    pic[:, 2:4] = 140
    pic[:, 4:6] = 20
    pic[:, 6:8] = 120
    line = np.zeros((4, 8), np.uint8)  # 黒地に白い線
    line[:, 6:8] = 255
    return pic, line


def test_split_regions():
    pic, line = _sample()
    r = split_line_solid_tone(pic, line, TH)
    # 紙の白はどの層にも入らない
    for layer in (r.line, r.solid, r.tone):
        assert (layer[:, 0:2] == 255).all()
    # トーンは元の濃さのまま、トーンの層だけ
    assert (r.tone[:, 2:4] == 140).all() and (r.solid[:, 2:4] == 255).all() and (r.line[:, 2:4] == 255).all()
    # ベタは真っ黒、ベタの層だけ
    assert (r.solid[:, 4:6] == 0).all() and (r.tone[:, 4:6] == 255).all()
    # 線は上限の濃さで、線の層だけ（トーンの濃さでも線が勝つ）
    assert (r.line[:, 6:8] == 80).all() and (r.tone[:, 6:8] == 255).all() and (r.solid[:, 6:8] == 255).all()
    assert (r.line_ratio, r.solid_ratio, r.tone_ratio) == (0.25, 0.25, 0.25)
    assert r.line.dtype == np.uint8


def test_line_keeps_darker_original():
    pic, line = _sample()
    pic[:, 6:8] = 10
    r = split_line_solid_tone(pic, line, TH)
    assert (r.line[:, 6:8] == 10).all()
    assert (r.solid[:, 6:8] == 255).all()  # 線の所はベタにしない


def test_recomposed_and_difference():
    pic, line = _sample()
    r = split_line_solid_tone(pic, line, TH)
    expect = np.array([255] * 2 + [140] * 2 + [0] * 2 + [80] * 2, np.uint8)
    assert (r.recomposed == expect).all()
    # 差：白 5×2、ベタ 20×2、線 40×2 → 8列の平均
    assert mean_difference(pic, r.recomposed) == pytest.approx((5 * 2 + 20 * 2 + 40 * 2) / 8)


def test_rejects_bad_input():
    pic, line = _sample()
    with pytest.raises(ValueError):
        split_line_solid_tone(pic, line[:, :4], TH)
    with pytest.raises(ValueError):
        split_line_solid_tone(np.stack([pic] * 3, -1), line, TH)
    with pytest.raises(ValueError):
        split_line_solid_tone(pic, line, SplitThresholds(200, 100, 128, 80))


def test_grey_array_resizes():
    im = Image.new('RGB', (4, 2), (255, 255, 255))
    a = grey_array(im, (8, 4))
    assert a.shape == (4, 8) and a.dtype == np.uint8 and (a == 255).all()
