"""動いている検出器のプロセス（v3/detector_server）へ、サーバーの送り手から送る。
V3_TEST_DETECTOR_URL が無ければ飛ばす（検出器は別に起動する。起動の仕方は v3detector/detector_http_app.py）。"""

import io
import os
import pathlib
from types import SimpleNamespace

import pytest
from PIL import Image

from v3server.service_senders.detector_sender import call_detector
from v3server.service_senders.sender_result_types import AdapterError

URL = os.environ.get("V3_TEST_DETECTOR_URL")
SHEET = pathlib.Path(__file__).resolve().parents[4] / "v3poc" / "p02_instruction" / "out" / "sheet_1.png"
pytestmark = pytest.mark.skipif(URL is None, reason="V3_TEST_DETECTOR_URL が無い")


def stored_crop(tmp_path, monkeypatch) -> str:
    from v3server.image_file_storage import store_image
    from v3server.server_settings import get_settings
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))
    with Image.open(SHEET) as im:
        crop = im.convert("RGB").crop((0, 0, min(im.width, 400), min(im.height, 400)))
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return store_image(buf.getvalue()).sha256


async def test_検出器へ送って枠が返る(tmp_path, monkeypatch):
    sha = stored_crop(tmp_path, monkeypatch)
    service = SimpleNamespace(endpoint=URL, name="detector")
    res = await call_detector(service, SimpleNamespace(process="detect"), {
        "endpoint": "/person_face_head", "images": {"image": sha}, "form": {"edge_px": 3}})
    assert {"persons", "faces", "heads"} <= set(res.output)


async def test_口や絵が足りなければ送らずに断る(tmp_path, monkeypatch):
    sha = stored_crop(tmp_path, monkeypatch)
    service = SimpleNamespace(endpoint=URL, name="detector")
    with pytest.raises(AdapterError) as e:
        await call_detector(service, SimpleNamespace(process="detect"), {"endpoint": "/nsfw", "images": {"image": sha}})
    assert e.value.kind == "refused"
    with pytest.raises(AdapterError) as e:
        await call_detector(service, SimpleNamespace(process="detect"), {"endpoint": "/identity_ccip",
                                                                         "images": {"image_a": sha}})
    assert e.value.kind == "refused"
