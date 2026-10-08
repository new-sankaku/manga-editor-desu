"""S3互換の置き場（image_file_storage.S3Store）。本物の置き場が要る。

V3_TEST_S3_ENDPOINT_URL・V3_TEST_S3_ACCESS_KEY_ID・V3_TEST_S3_SECRET_ACCESS_KEY が無ければ飛ばす。
SeaweedFS で確かめた（V3サーバーの土台 8章）。バケットは試験ごとに作って消す。"""

import io
import os
import uuid

import boto3
import pytest
from PIL import Image

from v3server.image_file_storage import image_store, read_image, store_image
from v3server.server_settings import get_settings

ENDPOINT = os.environ.get("V3_TEST_S3_ENDPOINT_URL")
pytestmark = pytest.mark.skipif(not ENDPOINT, reason="V3_TEST_S3_ENDPOINT_URL が無い")


@pytest.fixture
def s3_settings(monkeypatch):
    keys = {"s3_endpoint_url": ENDPOINT, "s3_region": "us-east-1",
            "s3_access_key_id": os.environ.get("V3_TEST_S3_ACCESS_KEY_ID"),
            "s3_secret_access_key": os.environ.get("V3_TEST_S3_SECRET_ACCESS_KEY")}
    bucket = f"v3-test-{uuid.uuid4().hex[:8]}"
    client = boto3.client("s3", endpoint_url=ENDPOINT, region_name="us-east-1",
                          aws_access_key_id=keys["s3_access_key_id"],
                          aws_secret_access_key=keys["s3_secret_access_key"])
    client.create_bucket(Bucket=bucket)
    s = get_settings()
    for k, v in {**keys, "image_store": "s3", "s3_bucket": bucket}.items():
        monkeypatch.setattr(s, k, v)
    yield client, bucket
    for o in client.list_objects_v2(Bucket=bucket).get("Contents", []):
        client.delete_object(Bucket=bucket, Key=o["Key"])
    client.delete_bucket(Bucket=bucket)


def png(color) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, "PNG")
    return buf.getvalue()


def test_置いた絵をsha256で取り出せ_同じ絵は1つだけ置かれる(s3_settings):
    client, bucket = s3_settings
    image_store().check()
    a = store_image(png((255, 0, 0)))
    again = store_image(png((255, 0, 0)))
    b = store_image(png((0, 0, 255)))
    assert a.sha256 == again.sha256 != b.sha256
    assert read_image(a.sha256) == png((255, 0, 0))
    keys = sorted(o["Key"] for o in client.list_objects_v2(Bucket=bucket)["Contents"])
    assert keys == sorted([f"{a.sha256[:2]}/{a.sha256}", f"{b.sha256[:2]}/{b.sha256}"])


def test_無い絵とバケットは例外で止まる(s3_settings, monkeypatch):
    with pytest.raises(Exception, match="NoSuchKey"):
        read_image("0" * 64)
    monkeypatch.setattr(get_settings(), "s3_bucket", "v3-test-no-such-bucket")
    with pytest.raises(Exception, match="404"):
        image_store().check()
