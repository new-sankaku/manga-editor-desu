"""絵のファイルの置き場。中身の sha256 を名前にして置くので、同じ絵は1つだけ置かれる。
今はサーバーの手元のフォルダ（V3_IMAGE_DIR）だけ。S3互換の置き場は製品を選んでから足す（V3サーバーの土台 9章）。"""

import hashlib
import io
import pathlib
from dataclasses import dataclass

from PIL import Image

from v3server.server_settings import get_settings
from v3server.v3_error_types import Invalid

# 受け付ける形式（Pillow の形式名 → 返す media_type）
ACCEPTED_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "TIFF": "image/tiff"}


@dataclass(frozen=True)
class StoredImage:
    sha256: str
    media_type: str
    width: int
    height: int
    dpi: int | None


def _root() -> pathlib.Path:
    d = get_settings().image_dir
    if d is None:
        raise RuntimeError("V3_IMAGE_DIR が設定されていない。絵の置き場が無い")
    root = pathlib.Path(d)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path(sha256: str) -> pathlib.Path:
    return _root() / sha256[:2] / sha256


def inspect_image(data: bytes) -> StoredImage:
    """形式・大きさ・解像度を読む。絵として読めない、または受け付けない形式なら止める。"""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            fmt, (w, h), dpi = im.format, im.size, im.info.get("dpi")
    except Exception as e:
        raise Invalid(f"絵として読めない: {e}") from e
    if fmt not in ACCEPTED_FORMATS:
        raise Invalid(f"受け付けない形式: {fmt}")
    return StoredImage(hashlib.sha256(data).hexdigest(), ACCEPTED_FORMATS[fmt], w, h,
                       round(float(dpi[0])) if dpi else None)


def store_image(data: bytes) -> StoredImage:
    info = inspect_image(data)
    p = _path(info.sha256)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(p)
    return info


def read_image(sha256: str) -> bytes:
    return _path(sha256).read_bytes()
