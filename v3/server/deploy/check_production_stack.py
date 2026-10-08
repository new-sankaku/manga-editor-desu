"""本番の形（compose.prod.yaml）を外から確かめる。ログイン・権限・絵の置き場・控えと戻しの突き合わせ。

  uv run python deploy/check_production_stack.py <env ファイル> <compose の project 名> seed <状態の JSON>
      Keycloak に利用者を3人作り、ブラウザと同じ手順（Caddy の TLS 越し）でログインして、作品・ページ・絵を作り、
      2人目を作品の viewer にする。ログイン・ログアウト・見出しで名乗れないこと・CSRF の見出しも確かめる。
  uv run python deploy/check_production_stack.py <env> <project> verify <状態の JSON>
      seed で作ったものが読めるか（作者と viewer は読める・作品に居ない3人目は 403）、絵の中身の sha256 が合うか。
  uv run python deploy/check_production_stack.py <env> <project> fingerprint <出力の JSON>
      データベース v3・openfga・keycloak の全部の表の行数と中身のハッシュ、絵の置き場の全部の物の sha256。
      控えを取った元と、戻した先で取り、diff で比べる（V3サーバーの土台 1.4.4）。

Caddy の内部の CA（V3_TLS=internal）の根の証明書を caddy のコンテナから取り出して、TLS を確かめて話す。
"""

import html
import io
import json
import pathlib
import re
import subprocess
import sys
import uuid

import httpx
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
COMPOSE_FILE = HERE.parent / "compose.prod.yaml"


def load_env(path: str) -> dict[str, str]:
    out = {}
    for line in pathlib.Path(path).read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            out[k] = v
    return out


class Stack:
    def __init__(self, env_path: str, project: str):
        self.env_path, self.project, self.env = env_path, project, load_env(env_path)
        self.public = self.env["V3_PUBLIC_URL"]
        self.ca = HERE / f".check-ca-{project}.crt"

    def compose(self, *args: str, stdin: str | None = None) -> str:
        cmd = ["docker", "compose", "-p", self.project, "--env-file", self.env_path, "-f", str(COMPOSE_FILE), *args]
        done = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
        if done.returncode != 0:
            raise RuntimeError(f"{' '.join(args[:3])} が失敗: {done.stderr[-2000:]}")
        return done.stdout

    def tls_client(self) -> httpx.Client:
        self.compose("cp", "caddy:/data/caddy/pki/authorities/local/root.crt", str(self.ca))
        return httpx.Client(base_url=self.public, verify=str(self.ca), timeout=30)

    # ---- Keycloak の管理（127.0.0.1 の管理の口）
    def kc_admin(self) -> httpx.Client:
        base = f"http://127.0.0.1:{self.env['V3_KEYCLOAK_ADMIN_PORT']}/kc"
        r = httpx.post(f"{base}/realms/master/protocol/openid-connect/token", data={
            "grant_type": "password", "client_id": "admin-cli",
            "username": self.env["KC_BOOTSTRAP_ADMIN_USERNAME"], "password": self.env["KC_BOOTSTRAP_ADMIN_PASSWORD"]})
        r.raise_for_status()
        return httpx.Client(base_url=f"{base}/admin/realms/v3", timeout=30,
                            headers={"Authorization": f"Bearer {r.json()['access_token']}"})

    def create_user(self, name: str, password: str) -> None:
        with self.kc_admin() as kc:
            r = kc.post("/users", json={
                "username": name, "enabled": True, "email": f"{name}@example.invalid", "emailVerified": True,
                "firstName": name, "lastName": "test",
                "credentials": [{"type": "password", "value": password, "temporary": False}]})
            assert r.status_code == 201, r.text


def login(stack: Stack, username: str, password: str) -> httpx.Client:
    """ブラウザと同じ手順：/auth/login → Keycloak のログインの画面 → 名前とパスワード → /auth/callback。"""
    c = stack.tls_client()
    r = c.get("/auth/login", params={"next": "/web/"}, follow_redirects=True)
    assert "kc-form-login" in r.text, f"Keycloak のログインの画面にならない: {r.status_code} {r.url}"
    action = html.unescape(re.search(r'id="kc-form-login"[^>]*action="([^"]+)"', r.text).group(1))
    r = c.post(action, data={"username": username, "password": password, "credentialId": ""},
               follow_redirects=True)
    assert r.status_code == 200 and str(r.url) == f"{stack.public}/web/", f"ログインできない: {r.status_code} {r.url}"
    return c


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (uuid.uuid4().int % 256, 80, 160)).save(buf, "PNG")
    return buf.getvalue()


W = {"X-V3-Request": "1"}


def seed(stack: Stack, state_path: str) -> None:
    users = {k: (f"{k}-{uuid.uuid4().hex[:6]}", uuid.uuid4().hex) for k in ("author", "viewer", "outsider")}
    for name, pw in users.values():
        stack.create_user(name, pw)
    checks = []

    anon = stack.tls_client()
    assert anon.get("/health").json()["auth_mode"] == "oidc"
    assert anon.get("/health/ready").status_code == 200, anon.get("/health/ready").text
    assert anon.get("/works", headers={"X-V3-User": "someone"}).status_code == 401
    checks.append("見出し X-V3-User だけでは 401")
    assert anon.get("/kc/admin/master/console/").status_code == 404
    assert anon.get("/kc/realms/master/.well-known/openid-configuration").status_code == 404
    checks.append("Keycloak の管理と master は Caddy の外から 404")
    assert anon.get("/auth/login").status_code in (302, 307)

    a = login(stack, *users["author"])
    me = a.get("/auth/me").json()
    assert me["mode"] == "oidc" and me["name"] == users["author"][0] and me["openfga_user"] == f"user:{me['id']}"
    checks.append("ログインして /auth/me が Keycloak の sub と OpenFGA の user を返す")
    work = {"title": "控えの確かめ", "reading_direction": "rtl", "text_direction": "vertical", "medium": "paper"}
    assert a.post("/works", json=work).status_code == 403
    checks.append("クッキーで書き換えるとき X-V3-Request が無ければ 403")
    r = a.post("/works", json=work, headers=W)
    assert r.status_code == 201, r.text
    wid = r.json()["id"]
    vol, ep, page = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
    v = login(stack, *users["viewer"])
    viewer_id = v.get("/auth/me").json()["id"]
    page_spec = {"frame_width_mm": 150, "frame_height_mm": 220, "trim_width_mm": 182, "trim_height_mm": 257,
                 "bleed_mm": 3, "gutter_x_mm": 2, "gutter_y_mm": 5}
    for op in [{"type": "set_work_settings", "page_spec": page_spec, "first_page_is_left": True},
               {"type": "add_volume", "id": vol, "number": 1},
               {"type": "add_episode", "id": ep, "volume_id": vol, "number": 1},
               {"type": "add_page", "id": page, "episode_id": ep, "number": 1},
               {"type": "set_member", "user": viewer_id, "role": "viewer", "granted": True}]:
        r = a.post(f"/works/{wid}/ops", json=op, headers=W)
        assert r.status_code == 200, r.text
    images = []
    for _ in range(3):
        data = png()
        r = a.post(f"/works/{wid}/images", headers=W, files={"image": ("a.png", data, "image/png")},
                   data={"role": "panel_art", "origin": "human_drawn", "page_id": page})
        assert r.status_code == 201, r.text
        images.append(r.json() | {"bytes_sha256": __import__("hashlib").sha256(data).hexdigest()})
    checks.append("作品・ページ・絵3枚を作り、viewer を招いた（絵は S3 の置き場へ）")
    r = a.post(f"/works/{wid}/exports", headers=W, json={"format": "png", "page_ids": [page], "dpi": 72})
    assert r.status_code == 201, r.text
    run = r.json()
    for _ in range(120):
        run = a.get(f"/works/{wid}/exports/{run['id']}").json()
        if run["status"] in ("done", "failed"):
            break
        __import__("time").sleep(0.5)
    assert run["status"] == "done", run
    f = a.get(f"/works/{wid}/exports/{run['id']}/files/{run['outputs'][0]['file']}")
    assert f.status_code == 200 and f.content[:8] == b"\x89PNG\r\n\x1a\n"
    checks.append("書き出し（PNG）が Temporal（PostgreSQL に保存する本番の形）と作業者を通って終わり、ファイルを受け取れた")
    assert v.get(f"/works/{wid}").status_code == 200
    o = login(stack, *users["outsider"])
    assert o.get(f"/works/{wid}").status_code == 403
    checks.append("viewer は読め、作品に居ない人は 403（OpenFGA）")
    r = a.get("/auth/logout")
    assert r.status_code == 303 and "/kc/realms/v3/protocol/openid-connect/logout" in r.headers["location"]
    assert a.get("/auth/me").status_code == 401
    checks.append("ログアウトでセッションが消え、Keycloak のログアウトへ送る")
    pathlib.Path(state_path).write_text(json.dumps(
        {"users": users, "work": wid, "page": page, "images": images, "checks": checks}, ensure_ascii=False, indent=1))
    print("\n".join(f"ok: {c}" for c in checks))


def verify(stack: Stack, state_path: str) -> None:
    st = json.loads(pathlib.Path(state_path).read_text())
    a = login(stack, *st["users"]["author"])
    w = a.get(f"/works/{st['work']}")
    assert w.status_code == 200, w.text
    import hashlib
    for img in st["images"]:
        r = a.get(f"/works/{st['work']}/images/{img['id']}/file")
        assert r.status_code == 200, r.text
        assert hashlib.sha256(r.content).hexdigest() == img["bytes_sha256"] == img["sha256"]
    print("ok: 作者でログインでき、作品と絵3枚が読め、絵の中身の sha256 が合う")
    assert login(stack, *st["users"]["viewer"]).get(f"/works/{st['work']}").status_code == 200
    assert login(stack, *st["users"]["outsider"]).get(f"/works/{st['work']}").status_code == 403
    print("ok: viewer は読め、作品に居ない人は 403（OpenFGA の役が戻っている）")
    assert stack.tls_client().get("/health/ready").status_code == 200
    print("ok: /health/ready")


FINGERPRINT_SQL = r"""
select format('select %L, count(*), md5(coalesce(string_agg(x::text, %L order by x::text), %L)) from %I.%I x',
              schemaname || '.' || tablename, '|', '', schemaname, tablename)
from pg_tables where schemaname not in ('pg_catalog', 'information_schema') order by 1 \gexec
"""


def fingerprint(stack: Stack, out_path: str) -> None:
    user = stack.env["POSTGRES_USER"]
    result: dict[str, dict] = {}
    for db in ("v3", "openfga", "keycloak"):
        rows = stack.compose("exec", "-T", "postgres", "psql", "-U", user, "-d", db, "-At", "-v", "ON_ERROR_STOP=1",
                             stdin=FINGERPRINT_SQL)
        result[db] = {t: f"{n} {h}" for t, n, h in (line.split("|") for line in rows.splitlines() if line)}
    lines = stack.compose("run", "--rm", "-T", "rclone", "hashsum", "sha256", "--download",
                          f"images:{stack.env['V3_S3_BUCKET']}")
    objects = {}
    for line in lines.splitlines():
        digest, key = line.split(None, 1)
        assert key.endswith(digest), f"名前と中身が違う: {key} {digest}"
        objects[key] = digest
    result["images"] = objects
    pathlib.Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True))
    print(f"表 {sum(len(result[d]) for d in ('v3', 'openfga', 'keycloak'))}・絵 {len(objects)} を {out_path} に書いた")


if __name__ == "__main__":
    env_path, project, command, path = sys.argv[1:5]
    {"seed": seed, "verify": verify, "fingerprint": fingerprint}[command](Stack(env_path, project), path)
