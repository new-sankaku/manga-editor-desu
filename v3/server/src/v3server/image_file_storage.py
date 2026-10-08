"""絵のファイルの置き場。中身の sha256 を名前にして置くので、同じ絵は1つだけ置かれ、置いた物は書き換えない。
置き場は設定 V3_IMAGE_STORE で選ぶ（V3サーバーの土台 1.4）。
- local: サーバーの手元のフォルダ（V3_IMAGE_DIR）。開発用
- s3: S3互換の置き場（本番は SeaweedFS）。キーは手元のフォルダと同じ `<先頭2文字>/<sha256>`
選んだ置き場に届かなければ止める。もう一方の置き場を代わりに使うことはしない。"""

import hashlib
import io
import pathlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
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


class ImageStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def check(self) -> None:
        """使える状態かを確かめる（起動時と GET /health/ready）。使えなければ例外。"""


class LocalFolderStore:
    def __init__(self, folder: str):
        self.root = pathlib.Path(folder)

    def _path(self, key: str) -> pathlib.Path:
        return self.root / key

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(p)

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

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

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
    store, key = image_store(), _key(info.sha256)
    if not store.exists(key):
        store.put(key, data)
    return info


def read_image(sha256: str) -> bytes:
    return image_store().get(_key(sha256))
