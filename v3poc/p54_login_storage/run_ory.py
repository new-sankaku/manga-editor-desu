"""P54-1b: Ory（Kratos 26.2.0 ＋ Hydra 26.2.0 ＋ 参照UI）で、登録 → ログイン → OIDC 認可コード（PKCE）でトークン → FastAPI で検証、を確かめる。

確かめること
1. compose を作り直した状態から、Kratos の /health/ready と Hydra の OIDC 設定が出るまでの時間、使用メモリ、画像の大きさ
2. Hydra の認可 URL → 参照UIのログイン画面 →「Sign up」で登録（Kratos の session フック）→ 認可コードが戻る → PKCE でトークン
3. 別のブラウザ文脈からパスワードでログインし、同じ sub（Kratos の identity ID）が得られる
4. verifier/app.py が、Hydra の JWT アクセストークン（access_token 戦略 jwt）から sub を取り出せる。
   断る側: 署名が別の鍵／改ざん／宛先違い／トークン無し／間違った PKCE verifier／間違ったパスワード
5. 設定ファイルの量（ファイル数・行数）
結果は out/ory.json
"""
import json, time, uuid
import httpx, jwt
from playwright.sync_api import sync_playwright
from cryptography.hazmat.primitives.asymmetric import rsa
from urllib.parse import urlencode
from common import *

HYDRA, HYDRA_ADMIN = "http://127.0.0.1:61102", "http://127.0.0.1:61103"
CB_PORT, VER_PORT = 61090, 61091
CLIENT = "v3-web"
R = {"product": "Ory (Kratos + Hydra + 参照UI)", "checks": {}}
cfg = HERE / "ory"

sh(f"cd {cfg} && docker compose -p p54 down -v")
t0 = time.time()
sh(f"cd {cfg} && docker compose -p p54 up -d")
wait_http("http://127.0.0.1:61100/health/ready", t0=t0)
wait_http(HYDRA + "/.well-known/openid-configuration", t0=t0)
R["startup_seconds_to_ready"] = round(wait_http("http://127.0.0.1:61104/health/ready", t0=t0), 1)
time.sleep(5)
R["memory_mib_idle"] = mem_mib()
R["image_mb"] = image_sizes(["oryd/kratos:v26.2.0", "oryd/hydra:v26.2.0", "oryd/kratos-selfservice-ui-node:latest"])
cfgfiles = [cfg / "compose.yaml", cfg / "kratos/kratos.yml", cfg / "kratos/identity.schema.json", cfg / "hydra/hydra.yml"]
R["config_files"] = {"files": len(cfgfiles), "lines": count_lines(cfgfiles),
                     "note": "別に Hydra のクライアント登録（管理APIへの POST 1回、下の client_body）が要る"}

REDIRECT = f"http://127.0.0.1:{CB_PORT}/cb"
client_body = dict(client_id=CLIENT, client_name="v3-web", token_endpoint_auth_method="none",
                   grant_types=["authorization_code", "refresh_token"], response_types=["code"],
                   scope="openid offline_access profile email", redirect_uris=[REDIRECT],
                   audience=["v3-api"], skip_consent=True, access_token_strategy="jwt")
r = httpx.post(HYDRA_ADMIN + "/admin/clients", json=client_body)
R["client_registered"] = r.status_code
assert r.status_code in (200, 201), r.text

cb = CallbackServer(CB_PORT)
disc = httpx.get(HYDRA + "/.well-known/openid-configuration").json()
email = f"p54-{uuid.uuid4().hex[:6]}@example.test"
pw = "p54-Throwaway-pw1-xyz"


def auth_url(challenge, state):
    return disc["authorization_endpoint"] + "?" + urlencode(dict(
        client_id=CLIENT, response_type="code", scope="openid offline_access", redirect_uri=REDIRECT, audience="v3-api",
        state=state, code_challenge=challenge, code_challenge_method="S256"))


def token(code, verifier):
    return httpx.post(disc["token_endpoint"], data=dict(
        grant_type="authorization_code", code=code, redirect_uri=REDIRECT, client_id=CLIENT, code_verifier=verifier))


def wait_cb(page):
    for _ in range(150):
        if cb.params.get("code"): return
        time.sleep(0.2)
    page.screenshot(path=str(OUT / "ory_fail.png"))
    raise RuntimeError("callback not reached: " + page.url + " | " + page.inner_text("body")[:300])


with sync_playwright() as pw_:
    br = pw_.chromium.launch()
    cb.params = {}
    v, c = pkce(); st = secrets.token_urlsafe(8)
    ctx = br.new_context(); page = ctx.new_page()
    page.goto(auth_url(c, st))
    page.click("text=Sign up")
    page.fill("input[name='traits.email']", email)
    page.fill("input[name='traits.name']", "P54 User")
    page.click("button[name=method][value=profile]")        # Kratos 26 の登録は2段（項目 → パスワード）
    page.fill("input[name=password]", pw)
    page.click("button[name=method][value=password]")
    wait_cb(page)
    assert cb.params["state"] == st
    r = token(cb.params["code"], v)
    R["checks"]["register_and_code_pkce_token"] = r.status_code == 200
    tok = r.json()
    acc = jwt.decode(tok["access_token"], options={"verify_signature": False})
    idc = jwt.decode(tok["id_token"], options={"verify_signature": False}, audience=CLIENT)
    R["token_claims"] = {"access": {k: acc.get(k) for k in ("iss", "sub", "aud", "client_id", "scp", "exp", "iat")},
                         "id": {k: idc.get(k) for k in ("sub", "iss", "aud")},
                         "expires_in": tok["expires_in"], "has_refresh_token": "refresh_token" in tok,
                         "access_token_is_jwt": tok["access_token"].count(".") == 2}
    sub1 = idc["sub"]
    rr = httpx.post(disc["token_endpoint"], data=dict(grant_type="refresh_token", refresh_token=tok["refresh_token"], client_id=CLIENT)).json()
    R["checks"]["code_reuse_rejected"] = token(cb.params["code"], v).status_code == 400
    ctx.close()

    # 別文脈でログイン
    cb.params = {}
    v2, c2 = pkce()
    ctx = br.new_context(); page = ctx.new_page()
    page.goto(auth_url(c2, "state-002"))
    try:
        page.wait_for_selector("input[name=identifier]", timeout=8000)
    except Exception:
        raise RuntimeError("login page not shown: " + page.url + " | " + page.inner_text("body")[:400])
    page.fill("input[name=identifier]", email)
    page.fill("input[name=password]", pw)
    page.click("button[name=method][value=password]")
    wait_cb(page)
    code2 = cb.params["code"]
    R["checks"]["wrong_pkce_verifier_rejected"] = token(code2, "x" * 50).status_code == 400
    cb.params = {}
    v3, c3 = pkce()
    page.goto(auth_url(c3, "state-003"))   # ログイン済み（Hydra と Kratos のセッション）なので画面なしで戻る
    wait_cb(page)
    r2 = token(cb.params["code"], v3)
    sub2 = jwt.decode(r2.json()["id_token"], options={"verify_signature": False}, audience=CLIENT)["sub"]
    R["checks"]["login_second_context_same_sub"] = (sub1 == sub2)
    R["checks"]["sso_second_auth_without_password_screen"] = r2.status_code == 200
    ctx.close()

    # sub が Kratos の identity ID と一致するか（管理APIで確認）
    ids = httpx.get("http://127.0.0.1:61101/admin/identities", params={"credentials_identifier": email}).json()
    R["checks"]["sub_equals_kratos_identity_id"] = bool(ids) and ids[0]["id"] == sub1

    # 間違ったパスワード
    cb.params = {}
    ctx = br.new_context(); page = ctx.new_page()
    page.goto(auth_url(pkce()[1], "state-004"))
    page.fill("input[name=identifier]", email); page.fill("input[name=password]", "wrong-pw")
    page.click("button[name=method][value=password]")
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    R["checks"]["wrong_password_rejected"] = (not cb.params.get("code")) and ("password" in body.lower())
    ctx.close(); br.close()

srv = start_verifier(VER_PORT, issuer=HYDRA, audience="v3-api")
try:
    def who(h): return httpx.get(f"http://127.0.0.1:{VER_PORT}/whoami", headers=h)
    ok = who({"Authorization": "Bearer " + tok["access_token"]})
    R["verifier_ok_response"] = ok.json() if ok.status_code == 200 else ok.text
    R["checks"]["verifier_returns_sub"] = ok.status_code == 200 and ok.json()["id"] == sub1
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    hdr = jwt.get_unverified_header(tok["access_token"])
    forged = jwt.encode(dict(acc), key, algorithm="RS256", headers={"kid": hdr["kid"]})
    R["checks"]["forged_signature_rejected"] = who({"Authorization": "Bearer " + forged}).status_code == 401
    parts = tok["access_token"].split(".")
    tampered = parts[0] + "." + jwt.utils.base64url_encode(json.dumps({**acc, "sub": "someone-else"}).encode()).decode() + "." + parts[2]
    R["checks"]["tampered_payload_rejected"] = who({"Authorization": "Bearer " + tampered}).status_code == 401
    R["checks"]["no_token_rejected"] = who({}).status_code == 401
    R["checks"]["id_token_wrong_audience_rejected"] = who({"Authorization": "Bearer " + tok["id_token"]}).status_code == 401
    R["checks"]["expired_forged_rejected"] = who({"Authorization": "Bearer " + jwt.encode({**acc, "exp": int(time.time()) - 10}, key, algorithm="RS256")}).status_code == 401
    R["checks"]["refreshed_token_accepted"] = "access_token" in rr and who({"Authorization": "Bearer " + rr["access_token"]}).status_code == 200
    R["note_expiry"] = "期限切れの実トークンでの検査は未実施（偽造鍵のため鍵の検査で先に断られる）"
finally:
    srv.terminate(); cb.close()

R["memory_mib_after_use"] = mem_mib()
R["license"] = {"kratos": "Apache-2.0", "hydra": "Apache-2.0", "ui-node": "Apache-2.0（イメージ内 package.json）"}
(OUT / "ory.json").write_text(json.dumps(R, indent=2, ensure_ascii=False))
print(json.dumps(R, indent=2, ensure_ascii=False))
