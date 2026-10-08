"""P54-1a: Keycloak 26.8.0 で、登録 → ログイン → OIDC 認可コード（PKCE）でトークン → FastAPI で検証、を確かめる。

確かめること
1. compose を作り直した状態から、/health/ready が 200 になるまでの時間と、使用メモリ、画像の大きさ
2. Playwright（Chromium）で、登録画面から利用者を作る → 認可コードが戻る → コードをトークンに替える（PKCE）
3. 同じ利用者で、別のブラウザ文脈からパスワードでログインし、同じ sub（利用者ID）が得られる
4. verifier/app.py（current_actor の置き換え案）が、アクセストークンの sub を取り出せる。
   断る側: 署名が別の鍵／改ざん／宛先違い／トークン無し／間違った PKCE verifier／間違ったパスワード
5. 設定ファイルの量（ファイル数・行数）
結果は out/keycloak.json
"""
import json, subprocess, sys, time, uuid
import httpx, jwt
from playwright.sync_api import sync_playwright
from cryptography.hazmat.primitives.asymmetric import rsa
from common import *

BASE = "http://127.0.0.1:61080/realms/manga"
CB_PORT, VER_PORT = 61090, 61091
CLIENT = "v3-web"
R = {"product": "Keycloak", "checks": {}}
cfg = HERE / "keycloak"

sh(f"cd {cfg} && docker compose -p p54 down -v")
t0 = time.time()
sh(f"cd {cfg} && docker compose -p p54 up -d")
R["startup_seconds_to_ready"] = round(wait_http("http://127.0.0.1:61081/health/ready", timeout=300, t0=t0), 1)
time.sleep(5)
R["memory_mib_idle"] = mem_mib()
R["image_mb"] = image_sizes(["quay.io/keycloak/keycloak:26.8.0"])
R["config_files"] = {"files": 2, "lines": count_lines([cfg / "compose.yaml", cfg / "realm.json"])}

cb = CallbackServer(CB_PORT)
REDIRECT = f"http://127.0.0.1:{CB_PORT}/cb"
disc = httpx.get(BASE + "/.well-known/openid-configuration").json()
user = "p54user" + uuid.uuid4().hex[:6]
pw = "p54-Throwaway-pw1"


def auth_url(challenge, state):
    from urllib.parse import urlencode
    return disc["authorization_endpoint"] + "?" + urlencode(dict(
        client_id=CLIENT, response_type="code", scope="openid profile email", redirect_uri=REDIRECT,
        state=state, code_challenge=challenge, code_challenge_method="S256"))


def token(code, verifier):
    return httpx.post(disc["token_endpoint"], data=dict(
        grant_type="authorization_code", code=code, redirect_uri=REDIRECT, client_id=CLIENT, code_verifier=verifier))


def wait_cb(page):
    for _ in range(100):
        if cb.params.get("code"): return
        time.sleep(0.2)
    raise RuntimeError("callback not reached: " + page.url)


with sync_playwright() as pw_:
    br = pw_.chromium.launch()
    # 2. 登録
    cb.params = {}
    v, c = pkce(); st = secrets.token_urlsafe(8)
    ctx = br.new_context(); page = ctx.new_page()
    page.goto(auth_url(c, st))
    page.click("text=Register")
    page.fill("#firstName", "P54"); page.fill("#lastName", "User")
    page.fill("#email", f"{user}@example.test"); page.fill("#username", user)
    page.fill("#password", pw); page.fill("#password-confirm", pw)
    page.click("input[type=submit], button[type=submit]")
    wait_cb(page)
    assert cb.params["state"] == st
    r = token(cb.params["code"], v)
    R["checks"]["register_and_code_pkce_token"] = r.status_code == 200
    tok = r.json()
    idc = jwt.decode(tok["id_token"], options={"verify_signature": False})
    acc = jwt.decode(tok["access_token"], options={"verify_signature": False})
    R["token_claims"] = {"access": {k: acc.get(k) for k in ("iss", "sub", "aud", "azp", "exp", "iat", "preferred_username", "typ")},
                         "id": {k: idc.get(k) for k in ("sub", "preferred_username", "email")},
                         "expires_in": tok["expires_in"], "has_refresh_token": "refresh_token" in tok}
    sub1 = idc["sub"]
    # 先に更新トークンを使う（同じコードの再利用を試すと、Keycloak はそのコードから作ったセッションを失効させる）
    rr = httpx.post(disc["token_endpoint"], data=dict(grant_type="refresh_token", refresh_token=tok["refresh_token"], client_id=CLIENT)).json()
    # 同じコードは二度使えない
    R["checks"]["code_reuse_rejected"] = token(cb.params["code"], v).status_code == 400
    ctx.close()

    # 3. 別文脈でログイン
    cb.params = {}
    v2, c2 = pkce(); st2 = secrets.token_urlsafe(8)
    ctx = br.new_context(); page = ctx.new_page()
    page.goto(auth_url(c2, st2))
    page.fill("#username", user); page.fill("#password", pw)
    page.click("#kc-login")
    wait_cb(page)
    code2 = cb.params["code"]
    R["checks"]["wrong_pkce_verifier_rejected"] = token(code2, "x" * 50).status_code == 400
    # コードは検証失敗で消費される場合があるので、改めて取り直す
    cb.params = {}
    v3, c3 = pkce()
    page.goto(auth_url(c3, "s3"))  # 既にログイン中（SSO）なので画面なしで戻る
    wait_cb(page)
    r2 = token(cb.params["code"], v3)
    tok2 = r2.json()
    sub2 = jwt.decode(tok2["id_token"], options={"verify_signature": False})["sub"]
    R["checks"]["login_second_context_same_sub"] = (sub1 == sub2)
    R["checks"]["sso_second_auth_without_password_screen"] = r2.status_code == 200
    ctx.close()

    # 間違ったパスワード
    ctx = br.new_context(); page = ctx.new_page()
    v4, c4 = pkce()
    page.goto(auth_url(c4, "s4"))
    page.fill("#username", user); page.fill("#password", "wrong-pw")
    page.click("#kc-login")
    page.wait_for_timeout(1500)
    R["checks"]["wrong_password_rejected"] = ("Invalid username or password" in page.content()) and not cb.params.get("code") or page.url.startswith(BASE)
    ctx.close(); br.close()

# 4. 検証用 FastAPI
srv = start_verifier(VER_PORT, issuer=BASE, audience="v3-api")
try:
    def who(h): return httpx.get(f"http://127.0.0.1:{VER_PORT}/whoami", headers=h)
    ok = who({"Authorization": "Bearer " + tok["access_token"]})
    R["verifier_ok_response"] = ok.json() if ok.status_code == 200 else ok.text
    R["checks"]["verifier_returns_sub"] = ok.status_code == 200 and ok.json()["id"] == sub1
    # 断る側
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(dict(acc), key, algorithm="RS256", headers={"kid": jwt.get_unverified_header(tok["access_token"])["kid"]})
    R["checks"]["forged_signature_rejected"] = who({"Authorization": "Bearer " + forged}).status_code == 401
    parts = tok["access_token"].split(".")
    tampered = parts[0] + "." + jwt.utils.base64url_encode(json.dumps({**acc, "sub": "someone-else"}).encode()).decode() + "." + parts[2]
    R["checks"]["tampered_payload_rejected"] = who({"Authorization": "Bearer " + tampered}).status_code == 401
    R["checks"]["no_token_rejected"] = who({}).status_code == 401
    # ID トークンの aud は client_id（v3-web）なので、宛先 v3-api の API には使えない
    R["checks"]["id_token_wrong_audience_rejected"] = who({"Authorization": "Bearer " + tok["id_token"]}).status_code == 401
    expired = jwt.encode({**acc, "exp": int(time.time()) - 10}, key, algorithm="RS256")
    R["checks"]["expired_forged_rejected"] = who({"Authorization": "Bearer " + expired}).status_code == 401
    # refresh で更新したアクセストークンも通る
    R["checks"]["refreshed_token_accepted"] = who({"Authorization": "Bearer " + rr["access_token"]}).status_code == 200
    # 実際の期限切れ: Keycloak 側で期限を短くして確かめるのは別の手間。署名付きの期限切れは PyJWT の標準検査（上は偽造鍵なので鍵で先に落ちる）
    R["note_expiry"] = "期限切れの実トークンでの検査は未実施（偽造鍵のため鍵の検査で先に断られる）。PyJWT の exp 検査は require で必須化している"
finally:
    srv.terminate(); cb.close()

R["memory_mib_after_use"] = mem_mib()
R["license"] = {"keycloak": "Apache-2.0（keycloak/keycloak の LICENSE.txt 冒頭で確認）"}
(OUT / "keycloak.json").write_text(json.dumps(R, indent=2, ensure_ascii=False))
print(json.dumps(R, indent=2, ensure_ascii=False))
