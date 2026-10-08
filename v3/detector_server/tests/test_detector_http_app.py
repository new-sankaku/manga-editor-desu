"""各口が小さな画像で答えを返すことの試験。
人物の絵は v3poc/p02_instruction/out/sheet_1.png の一覧画像から試験の中で切り抜く
（リポジトリに画像を足さない）。モデルの重みは初回に Hugging Face から落ちる。"""
import base64
import io
import pathlib
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from v3detector.detector_http_app import create_app

SHEET = pathlib.Path(__file__).resolve().parents[3] / "v3poc" / "p02_instruction" / "out" / "sheet_1.png"
# 一覧画像の中の切り抜き位置（左, 上, 右, 下）。行 from_below の2番目・3番目、行 from_behind の8番目（文字あり）
TILE_BELOW_2 = (294, 455, 434, 660)
TILE_BELOW_3 = (438, 455, 578, 660)
TILE_TEXT = (1010, 4, 1150, 208)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def sheet():
    if not SHEET.exists():
        pytest.skip(f"一覧画像が無い: {SHEET}")
    return Image.open(SHEET).convert("RGB")


def png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def files(**kw):
    return {k: (k + ".png", png(v), "image/png") for k, v in kw.items()}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_person_face_head(client, sheet):
    t0 = time.time()
    r = client.post("/person_face_head", files=files(image=sheet.crop(TILE_BELOW_2)), data={"edge_px": 3})
    print("person_face_head 秒", round(time.time() - t0, 2))
    assert r.status_code == 200
    j = r.json()
    assert (j["width"], j["height"]) == (140, 205)
    assert len(j["persons"]) >= 1 and len(j["faces"]) >= 1 and len(j["heads"]) >= 1
    b = j["persons"][0]
    assert {"x0", "y0", "x1", "y1", "score", "h_ratio", "area_ratio", "touch"} <= set(b)


def test_person_face_head_requires_edge_px(client, sheet):
    r = client.post("/person_face_head", files=files(image=sheet.crop(TILE_BELOW_2)))
    assert r.status_code == 422


def test_unreadable_image(client):
    r = client.post("/age_rating", files={"image": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 422


def test_text_regions(client, sheet):
    t0 = time.time()
    r = client.post("/text_regions", files=files(image=sheet.crop(TILE_TEXT)))
    print("text_regions 秒", round(time.time() - t0, 2))
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j["texts"], list)
    # 閾値を高くすると枠は増えない（閾値が効いている）
    r2 = client.post("/text_regions", files=files(image=sheet.crop(TILE_TEXT)), data={"score_threshold": 0.99})
    assert len(r2.json()["texts"]) <= len(j["texts"])


def test_identity_ccip(client, sheet):
    a, b = sheet.crop(TILE_BELOW_2), sheet.crop(TILE_BELOW_3)
    t0 = time.time()
    r = client.post("/identity_ccip", files=files(image_a=a, image_b=b))
    print("identity_ccip 秒", round(time.time() - t0, 2))
    j = r.json()
    assert r.status_code == 200
    assert j["threshold_is_imgutils_default"] is True
    assert "違う" in j["note"] and "同一人物の証拠にならない" in j["note"]
    # 呼ぶ側が渡した閾値が使われる
    r2 = client.post("/identity_ccip", files=files(image_a=a, image_b=b), data={"threshold": 0.0})
    assert r2.json()["threshold"] == 0.0 and r2.json()["same"] is False
    # 自分自身との差は小さい
    r3 = client.post("/identity_ccip", files=files(image_a=a, image_b=a))
    assert r3.json()["difference"] < j["difference"] + 1e-6


def test_age_rating(client, sheet):
    t0 = time.time()
    r = client.post("/age_rating", files=files(image=sheet.crop(TILE_BELOW_2)))
    print("age_rating 秒", round(time.time() - t0, 2))
    assert r.status_code == 200
    rating = r.json()["rating"]
    assert len(rating) >= 2 and abs(sum(rating.values()) - 1) < 0.01


def test_hands(client, sheet):
    t0 = time.time()
    r = client.post("/hands", files=files(image=sheet.crop(TILE_BELOW_2)), data={"crop_margin_ratio": 0.1})
    print("hands 秒", round(time.time() - t0, 2))
    assert r.status_code == 200
    for h in r.json()["hands"]:
        Image.open(io.BytesIO(base64.b64decode(h["crop_png_base64"]))).load()
    # 全体の画像から手が出る一覧も確かめる（切り抜き指定なしなら crop は付かない）
    r2 = client.post("/hands", files=files(image=sheet))
    assert r2.status_code == 200
    assert all("crop_png_base64" not in h for h in r2.json()["hands"])
