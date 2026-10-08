"""絵のファイルの置き場。中身の sha256 を名前にして置くので、同じ絵は1つだけ置かれ、置いた物は書き換えない。
置き場は設定 V3_IMAGE_STORE で選ぶ（V3サーバーの土台 1.3。s3 は 1.4.2）。
- local: サーバーの手元のフォルダ（V3_IMAGE_DIR）。開発用
- s3: S3互換の置き場（本番は SeaweedFS）。キーは手元のフォルダと同じ `<先頭2文字>/<sha256>`
選んだ置き場に届かなければ止める。もう一方の置き場を代わりに使うことはしない。

置く前の中身は、どちらの置き場でも一度サーバーの一時ファイルに少しずつ書く（アップロードを丸ごとメモリに読まないため。点検5 3-1）。
一時ファイルの場所は置き場が決める：local は置き場のフォルダの中の staging（置くときは名前を変えるだけ）、
s3 は OS の一時フォルダ（tempfile の既定。置くときは S3 へ送ってから消す）。"""

import hashlib
import os
import pathlib
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import BinaryIO, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
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


class ImageStore(Protocol):
    def staging_dir(self) -> pathlib.Path | None:
        """置く前の一時ファイルを書くフォルダ。None なら OS の一時フォルダ。"""
    def put_file(self, key: str, path: pathlib.Path) -> None:
        """一時ファイル path の中身を key に置く。path は置いた後に残っていてもよい（呼ぶ側が消す）。"""
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def check(self) -> None:
        """使える状態かを確かめる（起動時と GET /health/ready）。使えなければ例外。"""


class LocalFolderStore:
    def __init__(self, folder: str):
        self.root = pathlib.Path(folder)

    def _path(self, key: str) -> pathlib.Path:
        return self.root / key

    def staging_dir(self) -> pathlib.Path:
        """置き場と同じ円盤に置き、置くときは名前を変えるだけにする。"""
        d = self.root / "staging"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def put_file(self, key: str, path: pathlib.Path) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        path.replace(p)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def check(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        probe = self.root / ".write-check"
        probe.write_bytes(b"")
        probe.unlink()


class S3Store:
    def __init__(self, endpoint_url: str, bucket: str, region: str, access_key_id: str, secret_access_key: str):
        self.bucket = bucket
        self.client = boto3.client(
            "s3", endpoint_url=endpoint_url, region_name=region,
            aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key,
            # 送り直しは boto3 の標準の回数だけ。届かなければ例外にして止める
            config=Config(s3={"addressing_style": "path"}, retries={"mode": "standard"}),
        )

    def staging_dir(self) -> None:
        return None

    def put_file(self, key: str, path: pathlib.Path) -> None:
        # upload_file はファイルから少しずつ送る（大きければ分けて送る）
        self.client.upload_file(str(path), self.bucket, key)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        return True

    def check(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


@lru_cache
def _store_for(kind: str, image_dir: str | None, endpoint_url: str | None, bucket: str | None,
               region: str | None, access_key_id: str | None, secret_access_key: str | None) -> ImageStore:
    if kind == "local":
        if not image_dir:
            raise RuntimeError("V3_IMAGE_STORE=local だが V3_IMAGE_DIR が空。絵の置き場が無い")
        return LocalFolderStore(image_dir)
    assert endpoint_url and bucket and region and access_key_id and secret_access_key  # 設定の読み込みで確かめてある
    return S3Store(endpoint_url, bucket, region, access_key_id, secret_access_key)


def image_store() -> ImageStore:
    """設定どおりの置き場。設定を試験で差し替えても、その値の置き場を返す。"""
    s = get_settings()
    return _store_for(s.image_store, s.image_dir, s.s3_endpoint_url, s.s3_bucket, s.s3_region,
                      s.s3_access_key_id, s.s3_secret_access_key)


def _key(sha256: str) -> str:
    return f"{sha256[:2]}/{sha256}"


@contextmanager
def staged_file(source: BinaryIO | bytes) -> Iterator[pathlib.Path]:
    """中身を一時ファイルに少しずつ書き、その住所を渡す。抜けるときに残っていれば消す（置いたら残らない）。
    アップロードを丸ごとメモリに読まないため（点検5 3-1）。"""
    fd, name = tempfile.mkstemp(dir=image_store().staging_dir(), suffix=".part")
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
    """一時ファイル（staged_file）を置き場に置く。同じ中身が既にあれば置かない。一時ファイルは staged_file が消す。"""
    info = inspect_image_file(path)
    store, key = image_store(), _key(info.sha256)
    if not store.exists(key):
        store.put_file(key, path)
    return info


def store_image(data: bytes) -> StoredImage:
    with staged_file(data) as path:
        return store_image_file(path)


def read_image(sha256: str) -> bytes:
    return image_store().get(_key(sha256))
