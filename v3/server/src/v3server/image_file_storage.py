"""絵のファイルの置き場。中身の sha256 を名前にして置くので、同じ絵は1つだけ置かれる。
今はサーバーの手元のフォルダ（V3_IMAGE_DIR）だけ。S3互換の置き場は製品を選んでから足す（V3サーバーの土台 9章）。"""

import hashlib
import os
import pathlib
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import BinaryIO

from PIL import Image

from v3server.server_settings import get_settings
from v3server.v3_error_types import Invalid

# 一時ファイルに書く・sha256 を取るときの1回の大きさ
CHUNK_BYTES = 1024 * 1024

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


def _staging_dir() -> pathlib.Path:
    """置く前のファイルを書く所。置き場と同じ円盤に置き、置くときは名前を変えるだけにする。"""
    d = _root() / "staging"
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def staged_file(source: BinaryIO | bytes) -> Iterator[pathlib.Path]:
    """中身を一時ファイルに少しずつ書き、その住所を渡す。抜けるときに残っていれば消す（置いたら残らない）。
    アップロードを丸ごとメモリに読まないため（点検5 3-1）。"""
    fd, name = tempfile.mkstemp(dir=_staging_dir(), suffix=".part")
    path = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as out:
            if isinstance(source, bytes):
                out.write(source)
            else:
                shutil.copyfileobj(source, out, CHUNK_BYTES)
        yield path
    finally:
        path.unlink(missing_ok=True)


def _sha256_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_BYTES), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_image_file(path: pathlib.Path) -> StoredImage:
    """形式・大きさ・解像度を読む（画素は展開しない）。絵として読めない、または受け付けない形式なら止める。"""
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            fmt, (w, h), dpi = im.format, im.size, im.info.get("dpi")
    except Exception as e:
        raise Invalid(f"絵として読めない: {e}") from e
    if fmt not in ACCEPTED_FORMATS:
        raise Invalid(f"受け付けない形式: {fmt}")
    return StoredImage(_sha256_of(path), ACCEPTED_FORMATS[fmt], w, h, round(float(dpi[0])) if dpi else None)


def store_image_file(path: pathlib.Path) -> StoredImage:
    """一時ファイルを置き場に移す（同じ円盤なので名前を変えるだけ）。同じ中身が既にあれば一時ファイルは捨てる。"""
    info = inspect_image_file(path)
    p = _path(info.sha256)
    if p.exists():
        path.unlink()
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        path.replace(p)
    return info


def store_image(data: bytes) -> StoredImage:
    with staged_file(data) as path:
        return store_image_file(path)


def read_image(sha256: str) -> bytes:
    return _path(sha256).read_bytes()
