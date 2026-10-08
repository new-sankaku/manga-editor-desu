"""P54 共通: PKCE、検証用 FastAPI の起動、compose の計測、結果の書き出し。"""
from __future__ import annotations
import base64, hashlib, json, os, secrets, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
PY = os.environ.get("P54_PY", "/tmp/claude-0/-home-user-manga-editor-desu/fa704f96-c74d-4d28-a8d6-2b724e85a763/scratchpad/venv/bin/python")


def pkce():
    v = secrets.token_urlsafe(48)
    c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    return v, c


def b64json(seg: str):
    return json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def mem_mib(project="p54"):
    """compose の各コンテナの使用メモリ（MiB）。docker stats の値。"""
    r = sh(f"docker stats --no-stream --format '{{{{.Name}}}}|{{{{.MemUsage}}}}' $(docker ps -q --filter label=com.docker.compose.project={project})")
    out = {}
    for line in r.stdout.strip().splitlines():
        n, m = line.split("|")
        used = m.split("/")[0].strip()
        v = float(used.rstrip("MiBGKi"))
        if used.endswith("GiB"): v *= 1024
        elif used.endswith("KiB"): v /= 1024
        out[n] = round(v, 1)
    return out


def image_sizes(names):
    out = {}
    for n in names:
        r = sh(f"docker image inspect {n} --format '{{{{.Size}}}}'")
        out[n] = round(int(r.stdout.strip()) / 1e6, 1) if r.stdout.strip().isdigit() else None
    return out


def wait_http(url, ok=(200,), timeout=300, t0=None):
    import urllib.request, urllib.error
    t0 = t0 or time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status in ok: return time.time() - t0
        except urllib.error.HTTPError as e:
            if e.code in ok: return time.time() - t0
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(url)


class CallbackServer:
    """redirect_uri 用の受け口。ブラウザが戻ってきたときの code と state を取る。"""
    def __init__(self, port):
        self.params = {}
        outer = self
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                q = parse_qs(urlparse(self.path).query)
                outer.params = {k: v[0] for k, v in q.items()}
                self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
            def log_message(self, *a): pass
        self.srv = HTTPServer(("127.0.0.1", port), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
    def close(self): self.srv.shutdown()


def start_verifier(port, issuer, jwks_url="", audience=""):
    env = dict(os.environ, P54_ISSUER=issuer, P54_JWKS_URL=jwks_url, P54_AUDIENCE=audience, NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    p = subprocess.Popen([PY, "-m", "uvicorn", "app:app", "--app-dir", str(HERE / "verifier"), "--port", str(port), "--host", "127.0.0.1", "--log-level", "warning"], env=env)
    wait_http(f"http://127.0.0.1:{port}/docs", timeout=30)
    return p


def count_lines(paths):
    n = 0
    for p in paths:
        n += len(Path(p).read_text().splitlines())
    return n
