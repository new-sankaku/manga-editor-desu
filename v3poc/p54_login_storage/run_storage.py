"""P54-2: S3互換ストレージ（MinIO ソースビルド / SeaweedFS / Garage / RustFS）を Docker で立て、boto3 で漫画の画像置き場に要る操作を確かめる。

使い方: python run_storage.py minio seaweedfs garage rustfs   （引数に選んだものだけ。1つずつ作り直して測る）

確かめること（各製品、同じ手順）
1. 立ち上がり: compose up から list_buckets が通るまでの秒数、使用メモリ（待機中・50MB投入後）、イメージの大きさ
2. 基本: バケット作成、置く（PNG）、取る（SHA-256 一致）、head、一覧（prefix）、単体削除、一括削除
3. 署名付きURL（期限つき）: GET を httpx で取れる／期限後は 403／ブラウザ（Playwright・別オリジン）から
   <img> 表示、fetch での GET（CORS 設定あり）、署名付き PUT で画面から直接アップロードできる
4. 版の保持: put_bucket_versioning → 同じキーを3回置く → 版の一覧・版指定の取得 → 削除（削除マーカー）→ 版指定ならまだ取れる
5. 分割アップロード: 50MB を 8MB 単位（7分割）で upload_file（並列4）→ ETag の "-7" と SHA-256 一致、
   低水準の create/upload_part/list_parts/abort も
boto3 の既定設定で全部やり、落ちたものだけ request_checksum_calculation=when_required で再試行して、設定の違いで通るかを記録する。
結果は out/storage_<名前>.json
"""
import hashlib, io, json, os, sys, time, uuid
import boto3, httpx
from botocore.config import Config
from botocore.exceptions import ClientError
from PIL import Image
from playwright.sync_api import sync_playwright
from common import *

AK, SK = "p54accesskey", "p54secretkey-throwaway"
PRODUCTS = {
    "minio":     dict(dir="minio", port=61200, images=["p54-minio-src:latest"], label="MinIO（ソースビルド）"),
    "seaweedfs": dict(dir="seaweedfs", port=61210, images=["chrislusf/seaweedfs:latest"], label="SeaweedFS 4.48"),
    "garage":    dict(dir="garage", port=61220, images=["dxflrs/garage:v2.4.1"], label="Garage v2.4.1"),
    "rustfs":    dict(dir="rustfs", port=61230, images=["rustfs/rustfs:1.0.1"], label="RustFS 1.0.1"),
}
GK_ID, GK_SECRET = "GK" + "0123456789abcdef01234567", "ab" * 32  # Garage の鍵の形式（GK＋24桁16進、秘密は64桁16進）。試作用の使い捨て
BROWSER_ORIGIN_PORT = 61090
TMP = Path(os.environ.get("P54_TMP", "/tmp/claude-0/-home-user-manga-editor-desu/fa704f96-c74d-4d28-a8d6-2b724e85a763/scratchpad/p54tmp")); TMP.mkdir(exist_ok=True)


def client(port, strict_checksum=False):
    kw = dict(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 2}, connect_timeout=10, read_timeout=120)
    if strict_checksum:
        kw.update(request_checksum_calculation="when_required", response_checksum_validation="when_required")
    return boto3.client("s3", endpoint_url=f"http://127.0.0.1:{port}", aws_access_key_id=AK if True else None,
                        aws_secret_access_key=SK, region_name="us-east-1", config=Config(**kw))


def sha(b): return hashlib.sha256(b).hexdigest()


def png_bytes(seed=0):
    import random
    rnd = random.Random(seed)
    im = Image.frombytes("RGB", (512, 512), bytes(rnd.getrandbits(8) for _ in range(512 * 512 * 3)))
    buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()


def err(e):
    if isinstance(e, ClientError):
        return f"{e.response['Error'].get('Code')}: {e.response['Error'].get('Message','')[:120]}"
    return f"{type(e).__name__}: {str(e)[:160]}"


def garage_init(cfgdir):
    def g(*a): return sh(f"cd {cfgdir} && docker compose -p p54 exec -T garage /garage {' '.join(a)}")
    for _ in range(60):
        r = g("status")
        if r.returncode == 0 and "ID" in r.stdout: break
        time.sleep(1)
    node = [l.split()[0] for l in r.stdout.splitlines() if l.strip() and not l.startswith(("==", "ID"))][0]
    steps = [g("layout", "assign", "-z", "dc1", "-c", "1G", node), g("layout", "apply", "--version", "1"),
             g("key", "import", "--yes", "-n", "p54", GK_ID, GK_SECRET), g("key", "allow", "--create-bucket", GK_ID)]
    return [(s.returncode, (s.stdout + s.stderr)[-200:]) for s in steps]


# ---- 各試験。(s3, bucket, ctx) を受け取り、True か詳細(dict)を返す。例外は呼び出し側で記録 ----
def t_basic(s3, b, ctx):
    data = ctx["png"]; k = "work1/page001.png"
    s3.put_object(Bucket=b, Key=k, Body=data, ContentType="image/png")
    s3.put_object(Bucket=b, Key="work1/page002.png", Body=data)
    s3.put_object(Bucket=b, Key="work2/page001.png", Body=data)
    got = s3.get_object(Bucket=b, Key=k)
    body = got["Body"].read()
    h = s3.head_object(Bucket=b, Key=k)
    lst = s3.list_objects_v2(Bucket=b, Prefix="work1/")
    keys = [o["Key"] for o in lst.get("Contents", [])]
    s3.delete_object(Bucket=b, Key="work1/page002.png")
    after_one = [o["Key"] for o in s3.list_objects_v2(Bucket=b, Prefix="work1/").get("Contents", [])]
    s3.delete_objects(Bucket=b, Delete={"Objects": [{"Key": "work1/page001.png"}, {"Key": "work2/page001.png"}]})
    after_all = s3.list_objects_v2(Bucket=b).get("KeyCount", 0)
    ok = sha(body) == sha(data) and h["ContentType"] == "image/png" and sorted(keys) == ["work1/page001.png", "work1/page002.png"] \
        and after_one == ["work1/page001.png"] and after_all == 0
    return {"ok": ok, "content_type": h["ContentType"], "listed": keys}


def t_presign(s3, b, ctx):
    data = ctx["png"]; k = "presign/page.png"
    s3.put_object(Bucket=b, Key=k, Body=data, ContentType="image/png")
    url = s3.generate_presigned_url("get_object", Params={"Bucket": b, "Key": k}, ExpiresIn=6)
    r = httpx.get(url)
    res = {"get_ok": r.status_code == 200 and sha(r.content) == sha(data)}
    # 署名を1文字変えると断られる
    bad = url[:-3] + ("aaa" if not url.endswith("aaa") else "bbb")
    res["tampered_url_rejected"] = httpx.get(bad).status_code in (400, 401, 403)
    # ブラウザ（別オリジン）
    try:
        s3.put_bucket_cors(Bucket=b, CORSConfiguration={"CORSRules": [{
            "AllowedOrigins": [f"http://127.0.0.1:{BROWSER_ORIGIN_PORT}"], "AllowedMethods": ["GET", "PUT", "HEAD"],
            "AllowedHeaders": ["*"], "ExposeHeaders": ["ETag"], "MaxAgeSeconds": 300}]})
        res["cors_put"] = True
    except Exception as e:
        res["cors_put"] = err(e)
    url2 = s3.generate_presigned_url("get_object", Params={"Bucket": b, "Key": k}, ExpiresIn=120)
    up_key = "presign/uploaded-from-browser.png"
    put_url = s3.generate_presigned_url("put_object", Params={"Bucket": b, "Key": up_key, "ContentType": "image/png"}, ExpiresIn=120)
    page = ctx["page"]
    res["browser_img_load"] = page.evaluate("""(u) => new Promise(r => { const i = new Image(); i.onload = () => r({w: i.naturalWidth}); i.onerror = () => r('error'); i.src = u; })""", url2)
    res["browser_fetch_get"] = page.evaluate("""async (u) => { try { const r = await fetch(u); const b = await r.arrayBuffer(); return {status: r.status, bytes: b.byteLength}; } catch (e) { return 'error: ' + e.message; } }""", url2)
    res["browser_fetch_put"] = page.evaluate("""async ([u, n]) => { try { const r = await fetch(u, {method: 'PUT', headers: {'Content-Type': 'image/png'}, body: new Uint8Array(n).fill(7)}); return {status: r.status}; } catch (e) { return 'error: ' + e.message; } }""", [put_url, 4096])
    try:
        res["browser_put_arrived"] = s3.head_object(Bucket=b, Key=up_key)["ContentLength"] == 4096
    except Exception as e:
        res["browser_put_arrived"] = err(e)
    # 期限
    time.sleep(max(0, 7 - 0))
    r2 = httpx.get(url)
    res["expired_status"] = r2.status_code
    res["expired_rejected"] = r2.status_code in (400, 401, 403)
    res["ok"] = res["get_ok"] and res["tampered_url_rejected"] and res["expired_rejected"] \
        and isinstance(res["browser_img_load"], dict) and res["browser_img_load"].get("w", 0) > 0 \
        and isinstance(res["browser_fetch_get"], dict) and res["browser_fetch_get"]["status"] == 200 \
        and isinstance(res["browser_fetch_put"], dict) and res["browser_fetch_put"]["status"] == 200 and res["browser_put_arrived"] is True
    return res


def t_versioning(s3, b, ctx):
    s3.put_bucket_versioning(Bucket=b, VersioningConfiguration={"Status": "Enabled"})
    st = s3.get_bucket_versioning(Bucket=b).get("Status")
    k = "ver/page.png"; vids = []
    for i in range(3):
        vids.append(s3.put_object(Bucket=b, Key=k, Body=f"v{i}".encode())["VersionId"])
    lv = s3.list_object_versions(Bucket=b, Prefix="ver/")
    n = len(lv.get("Versions", []))
    old = s3.get_object(Bucket=b, Key=k, VersionId=vids[0])["Body"].read()
    s3.delete_object(Bucket=b, Key=k)
    lv2 = s3.list_object_versions(Bucket=b, Prefix="ver/")
    marker = len(lv2.get("DeleteMarkers", []))
    try:
        s3.get_object(Bucket=b, Key=k); cur = "still readable"
    except ClientError as e:
        cur = e.response["Error"]["Code"]
    still = s3.get_object(Bucket=b, Key=k, VersionId=vids[2])["Body"].read()
    ok = st == "Enabled" and len(set(vids)) == 3 and n == 3 and old == b"v0" and marker == 1 and still == b"v2"
    return {"ok": ok, "status": st, "versions": n, "delete_markers": marker, "current_after_delete": cur}


def t_multipart(s3, b, ctx):
    from boto3.s3.transfer import TransferConfig
    f = TMP / "big50.bin"
    if not f.exists() or f.stat().st_size != 50 * 1024 * 1024:
        f.write_bytes(os.urandom(50 * 1024 * 1024))
    want = hashlib.sha256(f.read_bytes()).hexdigest()
    cfg = TransferConfig(multipart_threshold=8 * 1024 * 1024, multipart_chunksize=8 * 1024 * 1024, max_concurrency=4)
    t = time.time(); s3.upload_file(str(f), b, "big/50mb.bin", Config=cfg); up = time.time() - t
    h = s3.head_object(Bucket=b, Key="big/50mb.bin")
    out = TMP / "big50.down"
    t = time.time(); s3.download_file(b, "big/50mb.bin", str(out), Config=cfg); down = time.time() - t
    same = hashlib.sha256(out.read_bytes()).hexdigest() == want
    out.unlink()
    res = {"size_ok": h["ContentLength"] == 50 * 1024 * 1024, "etag": h["ETag"], "multipart_etag": "-" in h["ETag"], "sha_match": same,
           "upload_seconds": round(up, 2), "download_seconds": round(down, 2)}
    # 低水準: 開始 → 2分割 → 一覧 → 中止
    mp = s3.create_multipart_upload(Bucket=b, Key="big/aborted.bin")
    uid = mp["UploadId"]
    s3.upload_part(Bucket=b, Key="big/aborted.bin", UploadId=uid, PartNumber=1, Body=b"a" * (5 * 1024 * 1024))
    s3.upload_part(Bucket=b, Key="big/aborted.bin", UploadId=uid, PartNumber=2, Body=b"b" * 1024)
    parts = s3.list_parts(Bucket=b, Key="big/aborted.bin", UploadId=uid).get("Parts", [])
    listed = [u["UploadId"] for u in s3.list_multipart_uploads(Bucket=b).get("Uploads", [])]
    s3.abort_multipart_upload(Bucket=b, Key="big/aborted.bin", UploadId=uid)
    listed2 = [u["UploadId"] for u in s3.list_multipart_uploads(Bucket=b).get("Uploads", [])]
    res.update(parts=len(parts), in_progress_listed=uid in listed, gone_after_abort=uid not in listed2)
    try:
        s3.head_object(Bucket=b, Key="big/aborted.bin"); res["aborted_object_exists"] = True
    except ClientError:
        res["aborted_object_exists"] = False
    res["ok"] = res["size_ok"] and res["multipart_etag"] and same and len(parts) == 2 and res["in_progress_listed"] and res["gone_after_abort"] and not res["aborted_object_exists"]
    return res


TESTS = [("basic_crud_list_delete", t_basic), ("presigned_url", t_presign), ("versioning", t_versioning), ("multipart_50mb", t_multipart)]


def run_product(name, cb):
    P = PRODUCTS[name]; d = HERE / "storage" / P["dir"]
    R = {"product": P["label"], "tests": {}}
    sh(f"cd {d} && docker compose -p p54 down -v")
    t0 = time.time()
    sh(f"cd {d} && docker compose -p p54 up -d")
    if name == "garage":
        R["garage_init"] = garage_init(d)
    s3 = client(P["port"]); s3s = client(P["port"], strict_checksum=True)
    ready = None
    while time.time() - t0 < 180:
        try:
            s3.list_buckets(); ready = time.time() - t0; break
        except Exception as e:
            R["_last_ready_error"] = err(e); time.sleep(1)
    R["startup_seconds_to_ready"] = round(ready, 1) if ready else None
    if not ready:
        R["logs_tail"] = sh(f"cd {d} && docker compose -p p54 logs --tail 20").stdout[-1500:]
        return R
    time.sleep(3)
    R["memory_mib_idle"] = mem_mib()
    R["image_mb"] = image_sizes(P["images"])
    cf = [f for f in d.rglob("*") if f.is_file() and "build" not in f.parts]
    R["config_files"] = {"files": len(cf), "lines": count_lines(cf), "names": [str(f.relative_to(d)) for f in cf]}
    bucket = "p54-" + uuid.uuid4().hex[:8]
    png = png_bytes()
    with sync_playwright() as pw:
        br = pw.chromium.launch(); page = br.new_page(); page.goto(f"http://127.0.0.1:{BROWSER_ORIGIN_PORT}/")
        ctx = {"png": png, "page": page}
        try:
            s3.create_bucket(Bucket=bucket); R["create_bucket"] = True
        except Exception as e:
            R["create_bucket"] = err(e)
        for tn, fn in TESTS:
            try:
                res = fn(s3, bucket, ctx)
                R["tests"][tn] = res
            except Exception as e:
                R["tests"][tn] = {"ok": False, "error": err(e), "default_boto3_config": True}
                # 同じ試験を when_required 設定で再試行
                try:
                    res = fn(s3s, bucket, ctx)
                    R["tests"][tn]["retry_with_checksum_when_required"] = res.get("ok") if isinstance(res, dict) else res
                except Exception as e2:
                    R["tests"][tn]["retry_with_checksum_when_required"] = err(e2)
            if tn == "multipart_50mb":
                R["memory_mib_after_50mb"] = mem_mib()
        br.close()
    R["memory_mib_after_tests"] = mem_mib()
    R["logs_tail"] = None
    return R


if __name__ == "__main__":
    cb = CallbackServer(BROWSER_ORIGIN_PORT)   # ブラウザの「画面側オリジン」。空のページを返すだけ
    for name in sys.argv[1:]:
        try:
            R = run_product(name, cb)
        except Exception as e:
            R = {"product": name, "fatal": err(e)}
        (OUT / f"storage_{name}.json").write_text(json.dumps(R, indent=2, ensure_ascii=False))
        print(name, json.dumps({k: (v if k != "tests" else {t: (x.get('ok'), x.get('error')) for t, x in v.items()}) for k, v in R.items() if k in ("startup_seconds_to_ready", "tests", "fatal", "create_bucket", "memory_mib_idle")}, ensure_ascii=False))
        sh(f"cd {HERE / 'storage' / PRODUCTS[name]['dir']} && docker compose -p p54 down -v")
    cb.close()
