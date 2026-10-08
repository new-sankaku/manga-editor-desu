"""p56: V3 サーバーの ComfyUI への送信（call_comfyui）を、本物の ComfyUI（CPU）で確かめる。

実行: v3/server/.venv/bin/python -I run.py   （ComfyUI は別に起動済み。COMFY_DIR・COMFY_PY で場所を指す）
v3/server のソースは直さず、そのまま import して呼ぶ。

確かめること
 1. /object_info、/models、/models/{フォルダ}、/system_stats、/embeddings で入っているモデル・ノードの一覧が取れるか
 2. call_comfyui で /prompt に送り、/history で終わりを待つ形が今の ComfyUI の API で動くか
 3. 絵のファイルを /view で受け取れるか（call_comfyui は受け取りを書いていない。試作の側で受け取る）
 4. seed を固定して2回送ると同じ絵か（実行結果の再利用を /free で消して、本当に2回計算させる）
 5. 取り消し: 順番待ちの物を /queue で消す、実行中の物を /interrupt で止める。call_comfyui から見て何が返るか
 6. 壊れたワークフロー（存在しないノード・足りない入力・選べない値・実行時の失敗）で ComfyUI が返す物と、
    call_comfyui の失敗の種類（refused / broken_response / transport）
 7. 返事の形が崩れた先（偽のサーバー）に対する種類の分け方
 8. ComfyUI のプロセスを途中で落としたときの振る舞いと、落ちている間・再起動後
結果は out/result.json。絵は out/ に数枚だけ置く。
"""

import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "v3/server/src"))

import httpx  # noqa: E402

from v3server.canonical_tables.service_and_job_tables import Service, ServiceProcess  # noqa: E402
from v3server.service_senders.comfyui_sender import call_comfyui  # noqa: E402
from v3server.service_senders.sender_result_types import AdapterError  # noqa: E402

PORT = 63188
URL = f"http://127.0.0.1:{PORT}"
COMFY_DIR = Path(os.environ.get(
    "COMFY_DIR",
    "/tmp/claude-0/-home-user-manga-editor-desu/fa704f96-c74d-4d28-a8d6-2b724e85a763/scratchpad/comfy"))
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
RESULT: dict = {}
BASE = json.loads((HERE / "workflow.json").read_text())
SIZE = 128  # CPU で数十秒に収めるための小ささ


def save():
    (OUT / "result.json").write_text(json.dumps(RESULT, ensure_ascii=False, indent=1))


def svc(endpoint=URL):
    return Service(name="comfy-local", kind="image", location="local", adapter="comfyui",
                   endpoint=endpoint, send_mode="serial", max_concurrency=1)


def proc(wf):
    return ServiceProcess(process="draw", comfy_workflow=wf)


def wf(seed=1, steps=2, prefix="p56", size=SIZE):
    w = json.loads(json.dumps(BASE))
    w["7"]["inputs"].update(seed=seed, steps=steps)
    w["6"]["inputs"].update(width=size, height=size)
    w["9"]["inputs"]["filename_prefix"] = prefix
    return w


async def send(workflow, overrides=None, endpoint=URL, timeout=None):
    """call_comfyui を呼び、結果か失敗の種類を返す。"""
    t = time.time()
    try:
        coro = call_comfyui(svc(endpoint), proc(workflow), {"overrides": overrides or {}})
        r = await (asyncio.wait_for(coro, timeout) if timeout else coro)
        return {"ok": True, "seconds": round(time.time() - t, 1), "output": r.output, "model": r.model,
                "settings": r.settings, "seed": r.seed}
    except AdapterError as e:
        return {"ok": False, "kind": e.kind, "detail": e.detail[:600], "seconds": round(time.time() - t, 1)}
    except asyncio.TimeoutError:
        return {"ok": False, "kind": "(戻らない)", "detail": f"{timeout}秒待っても call_comfyui が戻らない",
                "seconds": round(time.time() - t, 1)}
    except Exception as e:  # AdapterError に分類されずに漏れた例外を記録する
        return {"ok": False, "kind": "(分類されない例外)", "detail": f"{type(e).__name__}: {e}"[:600],
                "seconds": round(time.time() - t, 1)}


def pixel_hash(png: bytes) -> str:
    """PNG の画素だけのハッシュ。ComfyUI は手順の JSON を PNG の文字欄に埋めるので、ファイル全体の比較では保存名の違いが混ざる。"""
    import struct
    import zlib
    pos, idat = 8, b""
    while pos < len(png):
        n, typ = struct.unpack(">I4s", png[pos:pos + 8])
        if typ == b"IDAT":
            idat += png[pos + 8:pos + 8 + n]
        pos += 12 + n
    return hashlib.sha256(zlib.decompress(idat)).hexdigest()


async def view(c, img):
    r = await c.get("/view", params={"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]})
    return r


async def part_info(c):
    d = {}
    for path in ["/system_stats", "/models", "/models/unet", "/models/vae", "/models/text_encoders", "/models/clip",
                 "/models/checkpoints", "/models/loras", "/embeddings", "/queue", "/history"]:
        r = await c.get(path)
        try:
            body = r.json()
        except ValueError:
            body = r.text[:200]
        if isinstance(body, dict) and path == "/system_stats":
            body = {"system": {k: body["system"].get(k) for k in ("comfyui_version", "python_version", "pytorch_version", "ram_total")},
                    "devices": body.get("devices")}
        d[path] = {"status": r.status_code, "body": body}
    r = await c.get("/object_info")
    oi = r.json()
    d["/object_info"] = {"status": r.status_code, "bytes": len(r.content), "nodes": len(oi),
                         "has": [n for n in ("KSampler", "UNETLoader", "CheckpointLoaderSimple", "LoraLoader", "SaveImage") if n in oi]}
    for n in ("UNETLoader", "CheckpointLoaderSimple", "LoraLoader"):
        r = await c.get(f"/object_info/{n}")
        d[f"/object_info/{n}"] = {"status": r.status_code,
                                  "inputs": r.json().get(n, {}).get("input", {}).get("required", {})}
    RESULT["1_一覧"] = d
    save()


async def part_send(c):
    d = {}
    a = await send(wf(seed=11, prefix="p56a"))
    d["初回(seed11)"] = a
    img = a["output"]["images"][0] if a["ok"] else None
    if img:
        r = await view(c, img)
        d["view"] = {"status": r.status_code, "content_type": r.headers.get("content-type"), "bytes": len(r.content)}
        (OUT / "seed11_a.png").write_bytes(r.content)
        d["sha256_a"] = hashlib.sha256(r.content).hexdigest()
        d["pixels_a"] = pixel_hash(r.content)
        d["call_comfyui_の戻りに画像の中身"] = "images は {filename, subfolder, type} の一覧だけで、中身(bytes)は無い"
    # 同じ手順をそのまま再送: ComfyUI は結果を再利用する
    b = await send(wf(seed=11, prefix="p56a"))
    d["同じ手順の再送(再利用あり)"] = {k: b.get(k) for k in ("ok", "seconds", "output", "kind", "detail")}
    # 保存先の名前だけ変える（画像を計算し直さず保存だけやり直す）。再利用を消してから本当に2回目を計算させる
    await c.post("/free", json={"free_memory": True})
    t = time.time()
    b2 = await send(wf(seed=11, prefix="p56b"))
    d["再利用を消して再送(seed11)"] = b2
    if b2["ok"]:
        r = await view(c, b2["output"]["images"][0])
        (OUT / "seed11_b.png").write_bytes(r.content)
        d["sha256_b"] = hashlib.sha256(r.content).hexdigest()
        d["pixels_b"] = pixel_hash(r.content)
        d["ファイル全体が同じか"] = d["sha256_b"] == d.get("sha256_a")
        d["画素が同じか(seed固定2回)"] = d["pixels_b"] == d.get("pixels_a")
    await c.post("/free", json={"free_memory": True})
    c3 = await send(wf(seed=12, prefix="p56c"))
    d["別seed(seed12)"] = c3
    if c3["ok"]:
        r = await view(c, c3["output"]["images"][0])
        (OUT / "seed12.png").write_bytes(r.content)
        d["pixels_seed12"] = pixel_hash(r.content)
        d["別seedで違う絵か"] = d["pixels_seed12"] != d.get("pixels_a")
    # 履歴の形
    h = (await c.get("/history", params={"max_items": 1})).json()
    pid = next(iter(h))
    d["history1件の形"] = {"keys": list(h[pid].keys()), "status": h[pid]["status"]["status_str"],
                         "message種別": [m[0] for m in h[pid]["status"]["messages"]]}
    RESULT["2_送信と受け取りとseed"] = d
    save()


async def queue_state(c):
    q = (await c.get("/queue")).json()
    return [x[1] for x in q["queue_running"]], [x[1] for x in q["queue_pending"]]


async def post_prompt(c, w):
    r = await c.post("/prompt", json={"prompt": w})
    return r.json()["prompt_id"]


async def wait_running(c, pid, limit=60):
    t = time.time()
    while time.time() - t < limit:
        run, _ = await queue_state(c)
        if pid in run:
            return True
        await asyncio.sleep(0.5)
    return False


async def part_cancel(c):
    d = {}
    # (a) 生の API: 実行中A、順番待ちB・C。Bを /queue で消し、Aを /interrupt で止める
    A = await post_prompt(c, wf(seed=21, steps=40, prefix="p56A"))
    B = await post_prompt(c, wf(seed=22, steps=2, prefix="p56B"))
    C = await post_prompt(c, wf(seed=23, steps=2, prefix="p56C"))
    d["実行中が見えるまで"] = await wait_running(c, A)
    d["状態(A実行中,B・C待ち)"] = {"running": (await queue_state(c))[0] == [A], "pending": len((await queue_state(c))[1])}
    r = await c.post("/queue", json={"delete": [B]})
    d["待ちのBを消す"] = {"status": r.status_code, "text": r.text[:100], "queue_after": len((await queue_state(c))[1])}
    hb = (await c.get(f"/history/{B}")).json()
    d["消したBのhistory"] = hb if not hb else "あり"
    r = await c.post("/queue", json={"delete": [A]})
    d["実行中のAを /queue の delete で消す"] = {"status": r.status_code, "まだ実行中": A in (await queue_state(c))[0]}
    t = time.time()
    r = await c.post("/interrupt", json={})
    d["interrupt"] = {"status": r.status_code}
    ha = {}
    while time.time() - t < 120:
        ha = (await c.get(f"/history/{A}")).json()
        if ha:
            break
        await asyncio.sleep(0.5)
    d["interrupt後にhistoryへ出るまで(秒)"] = round(time.time() - t, 1)
    if ha:
        st = ha[A]["status"]
        d["Aのhistory"] = {"status_str": st["status_str"], "completed": st["completed"],
                          "messages種別": [m[0] for m in st["messages"]],
                          "interrupted詳細": [m[1] for m in st["messages"] if m[0] == "execution_interrupted"],
                          "outputs": ha[A]["outputs"]}
    # Cは続いて実行されるか
    t = time.time()
    hc = {}
    while time.time() - t < 150:
        hc = (await c.get(f"/history/{C}")).json()
        if hc:
            break
        await asyncio.sleep(1)
    d["interrupt後に後ろのCは動くか"] = hc[C]["status"]["status_str"] if hc else "動かない(150秒)"
    r = await c.post("/interrupt", json={})
    d["何も実行していないときの/interrupt"] = {"status": r.status_code}

    # (b) call_comfyui 越し: X(実行中)・Y(待ち)。Yを /queue で消す→call_comfyui は戻るか。Xを /interrupt→種類
    X = asyncio.create_task(send(wf(seed=31, steps=40, prefix="p56X")))
    for _ in range(60):
        run, _p = await queue_state(c)
        if run:
            break
        await asyncio.sleep(0.5)
    xid = (await queue_state(c))[0][0]
    Y = asyncio.create_task(send(wf(seed=32, steps=2, prefix="p56Y")))
    for _ in range(60):
        _r, pend = await queue_state(c)
        if pend:
            break
        await asyncio.sleep(0.5)
    yid = (await queue_state(c))[1][0]
    await c.post("/queue", json={"delete": [yid]})
    yres = await asyncio.wait_for(asyncio.shield(Y), 25) if False else None
    try:
        yres = await asyncio.wait_for(asyncio.shield(Y), 25)
    except asyncio.TimeoutError:
        yres = {"ok": False, "kind": "(戻らない)", "detail": "待ちから消されたあと25秒たっても call_comfyui が戻らない（/history に出ないので1秒ごとに見続ける）"}
    d["call_comfyui越し: 待ちから消された依頼"] = yres
    await c.post("/interrupt", json={})
    d["call_comfyui越し: 実行中に/interrupt された依頼"] = await asyncio.wait_for(X, 120)
    if not Y.done():
        Y.cancel()
        d["Y後始末"] = "戻らないので asyncio で取り消した（call_comfyui 側に上限の時間が無い）"
    RESULT["3_取り消し"] = d
    save()


async def part_broken(c):
    d = {}
    # 実行時に失敗する手順用: VAE のファイルを unet の置き場に置く（型を判別できず読み込みで失敗する）
    bogus = COMFY_DIR / "ComfyUI/models/unet/bogus_not_a_unet.safetensors"
    if not bogus.exists():
        bogus.write_bytes((COMFY_DIR / "ComfyUI/models/vae/sd15_vae_fp16.safetensors").read_bytes())

    def mk(f):
        w = wf(seed=41, steps=2, prefix="p56bad")
        f(w)
        return w

    cases = {
        "存在しないノード": lambda w: w["7"].update(class_type="NoSuchSamplerNode"),
        "足りない入力(KSamplerのmodel)": lambda w: w["7"]["inputs"].pop("model"),
        "選べない値(sampler_name)": lambda w: w["7"]["inputs"].update(sampler_name="no_such_sampler"),
        "存在しないモデル名": lambda w: w["1"]["inputs"].update(unet_name="nothing.safetensors"),
        "つなぎ先のノード番号が無い": lambda w: w["7"]["inputs"].update(positive=["99", 0]),
        "範囲外の値(width=0)": lambda w: w["6"]["inputs"].update(width=0),
        "出力ノードが無い": lambda w: w.pop("9"),
        "実行時の失敗(型を判別できないモデル)": lambda w: w["1"]["inputs"].update(unet_name="bogus_not_a_unet.safetensors"),
    }
    for name, f in cases.items():
        w = mk(f)
        raw = await c.post("/prompt", json={"prompt": w})
        try:
            rb = raw.json()
        except ValueError:
            rb = raw.text[:300]
        rec = {"生のPOST/prompt": {"status": raw.status_code,
                                 "body": (json.dumps(rb, ensure_ascii=False)[:500] if not isinstance(rb, str) else rb)}}
        if raw.status_code == 200:  # 実行時失敗の例では積まれてしまっているので、終わるまで待つ
            pid = rb["prompt_id"]
            for _ in range(60):
                h = (await c.get(f"/history/{pid}")).json()
                if h:
                    rec["生のhistory"] = {"status_str": h[pid]["status"]["status_str"],
                                        "messages種別": [m[0] for m in h[pid]["status"]["messages"]]}
                    break
                await asyncio.sleep(1)
        rec["call_comfyui"] = await send(w, timeout=90)
        d[name] = rec
    d["overridesが手順に無いノード"] = await send(wf(), overrides={"99": {"seed": 1}})
    RESULT["4_壊れた手順"] = d
    save()


class Fake(BaseHTTPRequestHandler):
    mode = ""

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        m = self.server.mode
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if m == "html200":
            self._send(200, "<html>proxy login</html>", "text/html")
        elif m == "no_prompt_id":
            self._send(200, '{"ok": true}')
        elif m == "500":
            self._send(500, "boom", "text/plain")
        elif m == "429":
            self.send_response(429)
            self.send_header("Retry-After", "7")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif m == "503":
            self._send(503, "unavailable", "text/plain")
        else:
            self._send(200, '{"prompt_id": "abc"}')

    def do_GET(self):
        m = self.server.mode
        if m == "history_html":
            self._send(200, "<html>x</html>", "text/html")
        elif m == "history_noimg":
            self._send(200, '{"abc": {"status": {"status_str": "success"}, "outputs": {"9": {}}}}')
        elif m == "history_list":
            self._send(200, '["abc"]')
        elif m == "history_500":
            self._send(500, "x", "text/plain")
        elif m == "history_nostatus_error":
            self._send(200, '{"abc": {"status": {"status_str": "error", "messages": []}, "outputs": {}}}')
        else:
            self._send(404, "{}")


async def part_fake():
    d = {}
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    ep = f"http://127.0.0.1:{srv.server_address[1]}"
    for mode in ["html200", "no_prompt_id", "500", "503", "429", "history_html", "history_noimg", "history_list",
                 "history_500", "history_nostatus_error"]:
        srv.mode = mode
        d[mode] = await send(wf(), endpoint=ep, timeout=20)
    srv.shutdown()
    d["住所に誰もいない(接続拒否)"] = await send(wf(), endpoint="http://127.0.0.1:1", timeout=20)
    RESULT["5_偽のサーバー"] = d
    save()


def comfy_pids():
    out = subprocess.run(["pgrep", "-f", "ComfyUI/main.py"], capture_output=True, text=True).stdout.split()
    return [int(x) for x in out]


def start_comfy():
    log = open(COMFY_DIR / "comfy.log", "ab")
    subprocess.Popen([str(COMFY_DIR / "venv/bin/python"), str(COMFY_DIR / "ComfyUI/main.py"), "--cpu", "--port", str(PORT),
                      "--listen", "127.0.0.1"], stdout=log, stderr=log, cwd=str(COMFY_DIR), start_new_session=True)


async def part_kill(c):
    d = {}
    X = asyncio.create_task(send(wf(seed=51, steps=40, prefix="p56K")))
    for _ in range(60):
        run, _p = await queue_state(c)
        if run:
            break
        await asyncio.sleep(0.5)
    kid = (await queue_state(c))[0][0]
    await asyncio.sleep(3)
    for p in comfy_pids():
        os.kill(p, signal.SIGKILL)
    t = time.time()
    d["実行中にkill -9した依頼"] = await asyncio.wait_for(X, 90)
    d["実行中にkill -9した依頼"]["落ちてから戻るまで"] = round(time.time() - t, 1)
    d["落ちている間に送る"] = await send(wf(seed=52), timeout=30)
    start_comfy()
    t = time.time()
    up = False
    async with httpx.AsyncClient(base_url=URL, timeout=5) as c2:
        while time.time() - t < 180:
            try:
                if (await c2.get("/system_stats")).status_code == 200:
                    up = True
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
        d["再起動して応答するまで(秒)"] = round(time.time() - t, 1) if up else "応答しない"
        if up:
            h = (await c2.get(f"/history/{kid}")).json()
            d["再起動後に、落ちた時の依頼のhistory"] = h if not h else "あり"
            d["再起動後の送信"] = await send(wf(seed=53, steps=2, prefix="p56R"), timeout=400)
    RESULT["6_プロセスを落とす"] = d
    save()


async def main():
    only = set(sys.argv[1:])
    async with httpx.AsyncClient(base_url=URL, timeout=60) as c:
        for name, fn in [("info", part_info), ("send", part_send), ("cancel", part_cancel), ("broken", part_broken),
                         ("fake", None), ("kill", part_kill)]:
            if only and name not in only:
                continue
            print("==", name, flush=True)
            if fn is None:
                await part_fake()
            else:
                await fn(c)
    # 前回の結果を残すため、読み直して重ねる
    save()


if __name__ == "__main__":
    prev = OUT / "result.json"
    if prev.exists() and len(sys.argv) > 1:
        RESULT.update(json.loads(prev.read_text()))
    asyncio.run(main())
