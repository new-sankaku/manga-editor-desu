"""利用者に見せる文（v3server/messages.py の m()・ms()）の包み方と訳に、漏れが無いかを確かめる（llm_doc/V3細部の決めごと.md 24.5）。

コードを読むだけで、データベースは要らない。次を止める。
  1. m()・ms() の1つ目が文字列そのものでない・文の中の {名前} と渡した値が合わない
  2. 日本語の文字列を、m()・ms() に包まず、印も付けずに置いている（docstring・ログ・assert の文は除く）
  3. 使っている文が辞書に無い・辞書に使っていない文がある・訳に日本語が残る・訳の {名前} が元と違う
  4. 残す文（ms()）が、つなぐ・JSON・例外を通っても、出す所でその言語の文に戻る
印（その文のどこかの行の末尾のコメント。def の行に書けば、その関数の中は全部）
  # i18n:dev     作る人だけが見る文（画面に届かない）
  # i18n:prompt  LLM に送る文（日本語のまま）
  # i18n:data    文ではなく値（比べる・鍵にする日本語）
"""

import ast
import asyncio
import copy
import json
import pathlib
import pickle
import re
import string

import pytest
from starlette.requests import Request

from v3server.message_catalog import CATALOG
from v3server.messages import LANGS, Message, has_packed, m, ms, render, render_tree, request_lang, text_of
from v3server.v3_error_types import Invalid

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "v3server"
JA = re.compile(r"[぀-ヿ一-鿿]")
# 画面に届かない例外（プログラムの誤り・設定の誤りで起動時に止まるもの）。日本語の文を m() に包まなくてよい
DEV_ONLY = {"RuntimeError", "AssertionError", "TypeError", "NotImplementedError", "KeyError", "LookupError", "SystemExit",
            "AttributeError", "ImportError"}
MARK = re.compile(r"#.*\bi18n:(dev|prompt|data)\b")


def _sources() -> list[tuple[pathlib.Path, str, ast.Module]]:
    out = []
    for path in sorted(SRC.rglob("*.py")):
        if "message_catalog" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        out.append((path, text, ast.parse(text)))
    return out


SOURCES = _sources()


def _where(path: pathlib.Path, node: ast.AST) -> str:
    return f"{path.relative_to(SRC).as_posix()}:{getattr(node, 'lineno', 0)}"


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name is not None}


def _is_m(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("m", "ms")


def _m_calls() -> list[tuple[pathlib.Path, ast.Call]]:
    return [(path, node) for path, _, tree in SOURCES for node in ast.walk(tree) if _is_m(node)]


def _templates() -> dict[str, str]:
    """使っている文 → 最初に出てきた場所。"""
    used: dict[str, str] = {}
    for path, call in _m_calls():
        first = call.args[0] if call.args else None
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            used.setdefault(first.value, _where(path, call))
    return used


def test_m_is_called_with_a_literal_and_matching_values():
    bad = []
    for path, call in _m_calls():
        first = call.args[0] if call.args else None
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)) or len(call.args) != 1:
            bad.append(f"{_where(path, call)}: m() の1つ目は文字列をそのまま書く（f 文字列・変数・連結は不可）")
            continue
        if any(k.arg is None for k in call.keywords):
            bad.append(f"{_where(path, call)}: m() に **値 を渡さない（名前を1つずつ書く）")
            continue
        fields, given = _fields(first.value), {k.arg for k in call.keywords}
        if not all(f.isidentifier() for f in fields):
            bad.append(f"{_where(path, call)}: 文の中の {{名前}} は、名前だけにする（{{a.b}} や {{a[0]}} は不可）")
        elif fields != given:
            bad.append(f"{_where(path, call)}: 文の {{名前}} {sorted(fields)} と、渡した値 {sorted(given)} が合わない")
    assert not bad, "\n".join(bad)


def test_japanese_text_in_exceptions_is_wrapped():
    bad = []
    for path, text, tree in SOURCES:
        lines = text.splitlines()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
                continue
            func = node.exc.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name in DEV_ONLY:
                continue
            # 例外に渡した値の全部（HTTPException(403, "…") や detail="…" も）を見る。m() の中の文は数えない
            given = [*node.exc.args, *(k.value for k in node.exc.keywords)]
            inside_m = {id(c) for a in given for n in ast.walk(a) if _is_m(n) and n.args for c in ast.walk(n.args[0])}
            loose = [n for a in given for n in ast.walk(a)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str) and JA.search(n.value) and id(n) not in inside_m]
            if not loose:
                continue
            span = lines[node.lineno - 1:(node.end_lineno or node.lineno)]
            if any(MARK.search(line) for line in span):
                continue
            bad.append(f"{_where(path, node)}: {name}(…) に日本語の文を m() に包まずに渡している")
    assert not bad, f"{len(bad)} 件\n" + "\n".join(bad)


def _loose_japanese(text: str, tree: ast.Module) -> list[tuple[int, str]]:
    """m()・ms() に包んでいなくて、印も無い日本語の文字列（行, 文字列の頭）。docstring・ログ・assert の文は数えない。"""
    lines = text.splitlines()
    skip: set[int] = set()
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                skip.add(id(first.value))
        logged = (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                  and node.func.value.id in ("log", "logger", "logging"))
        if _is_m(node) or logged:
            skip.update(id(inner) for inner in ast.walk(node))
        if isinstance(node, ast.Assert) and node.msg is not None:
            skip.update(id(inner) for inner in ast.walk(node.msg))
    compound = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.AsyncFor,
                ast.AsyncWith, ast.Match)
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str) and JA.search(node.value)) or id(node) in skip:
            continue
        parent = parents.get(id(node))
        if isinstance(parent, ast.JoinedStr):  # f 文字列のかけらは、f 文字列ごとに1回だけ数える
            if next(v for v in parent.values if isinstance(v, ast.Constant) and JA.search(str(v.value))) is not node:
                continue
        up, statement, marked = node, None, False
        while id(up) in parents:
            up = parents[id(up)]
            if statement is None and isinstance(up, ast.stmt):
                statement = up
                # 印は、その文のどこかの行に書く。複合文（if・for・def など）は中身まで見ずに、文字列のある行だけ見る
                span = lines[up.lineno - 1:(up.end_lineno or up.lineno)]
                if isinstance(up, compound):
                    span = [lines[node.lineno - 1], lines[(node.end_lineno or node.lineno) - 1]]
                marked = any(MARK.search(line) for line in span)
            if isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef)):  # def の行に印があれば、その関数の中は全部
                marked = marked or any(MARK.search(line) for line in lines[up.lineno - 1:up.body[0].lineno - 1])
        if not marked:
            out.append((node.lineno, node.value[:40].replace("\n", " ")))
    return out


def test_japanese_text_is_wrapped_or_marked():
    """日本語の文字列は、m()・ms() に包むか、印（dev・prompt・data）を付ける。包み忘れた文は、英語の画面に日本語のまま出る。"""
    bad = [f"{path.relative_to(SRC).as_posix()}:{lineno}: {value}"
           for path, text, tree in SOURCES for lineno, value in _loose_japanese(text, tree)]
    assert not bad, f"{len(bad)} 件\n" + "\n".join(bad)


def test_stored_mark_is_gone():
    """`# i18n:stored`（残す文は訳さない、の印）はもう使わない。残す文は ms() に包む。"""
    bad = [f"{path.relative_to(SRC).as_posix()}:{i}" for path, text, _ in SOURCES
           for i, line in enumerate(text.splitlines(), 1) if re.search(r"#.*\bi18n:stored\b", line)]
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("lang", [lang for lang in LANGS if lang != "ja"])
def test_every_message_is_translated(lang):
    used, catalog = _templates(), CATALOG[lang]
    bad = [f"{where}: 辞書（{lang}）に無い: {template!r}" for template, where in used.items() if template not in catalog]
    bad += [f"辞書（{lang}）にあるが使っていない: {template!r}" for template in catalog if template not in used]
    for template, translated in catalog.items():
        if JA.search(translated):
            bad.append(f"訳に日本語が残っている: {template!r} → {translated!r}")
        if _fields(template) != _fields(translated):
            bad.append(f"訳の {{名前}} が元と違う: {template!r} → {translated!r}")
    assert not bad, f"{len(bad)} 件\n" + "\n".join(bad)


def test_message_is_the_japanese_text_and_keeps_its_source():
    text = m("コマ {id} には枠がまだ無い", id="p1")
    assert text == "コマ p1 には枠がまだ無い" and isinstance(text, str)
    assert json.dumps({"detail": text}, ensure_ascii=False) == '{"detail": "コマ p1 には枠がまだ無い"}'
    for clone in (pickle.loads(pickle.dumps(text)), copy.deepcopy(text)):
        assert clone == text and clone.template == text.template and clone.values == text.values
    assert text_of(Invalid(text)) is text
    assert text_of(ValueError("plain")) == "plain" and not isinstance(text_of(ValueError("plain")), Message)


def test_stored_message_survives_text_handling_and_is_rendered_at_the_output(monkeypatch):
    """残す文（ms()）は、f 文字列・JSON・例外の文を通っても、出す所でその言語の文に戻る。"""
    monkeypatch.setitem(CATALOG, "en", {"{name} に URL が無い": "{name} has no URL", "送れなかった: {reason}": "Could not send: {reason}",
                                        "足りない: {names}（{n} 件）": "Missing: {names} ({n})", "幅が足りない（{mm}mm）": "Too narrow ({mm} mm)"})
    inner = ms("{name} に URL が無い", name="comfy1")
    assert has_packed(inner) and "comfy1" in inner and inner != "comfy1 に URL が無い"
    assert render(inner, "ja") == "comfy1 に URL が無い" and render(inner, "en") == "comfy1 has no URL"
    # つなぐ・例外にする・JSON にして読み戻す
    travelled = json.loads(json.dumps({"reason": str(ValueError(f"refused: {inner}"))}))["reason"]
    assert render(travelled, "ja") == "refused: comfy1 に URL が無い" and render(travelled, "en") == "refused: comfy1 has no URL"
    # 別の文の値に入れる（ms() の中に ms()、ms() の中に m()）。並びはその言語の区切りでつなぐ。数は書式を保つ
    outer = ms("送れなかった: {reason}", reason=inner)
    assert render(outer, "ja") == "送れなかった: comfy1 に URL が無い" and render(outer, "en") == "Could not send: comfy1 has no URL"
    assert render(ms("送れなかった: {reason}", reason=m("幅が足りない（{mm}mm）", mm=3)), "en") == "Could not send: Too narrow (3 mm)"
    listed = ms("足りない: {names}（{n} 件）", names=["顔", inner], n=2)
    assert render(listed, "ja") == "足りない: 顔、comfy1 に URL が無い（2 件）" and render(listed, "en") == "Missing: 顔, comfy1 has no URL (2)"
    assert render(ms("辞書に無い文 {n:.1f}", n=1.25), "ja") == "辞書に無い文 1.2" and render(ms("辞書に無い文 {n:.1f}", n=1.25), "en") == "⚠ 辞書に無い文 1.2"
    # 同じ文と値なら同じ文字列（重なりを省く所が今までどおり働く）
    assert ms("{name} に URL が無い", name="comfy1") == inner
    # 返事の中身は、日本語でも文に戻す
    tree = {"items": [{"reason": travelled, "n": 1}], "plain": "そのまま"}
    assert render_tree(tree, "ja") == {"items": [{"reason": "refused: comfy1 に URL が無い", "n": 1}], "plain": "そのまま"}
    assert render_tree(tree, "en")["items"][0]["reason"] == "refused: comfy1 has no URL"


def test_stored_message_in_a_response_is_rendered_in_japanese_too():
    from v3server.http_routes.http_app_factory import LocalizedJSONResponse
    from v3server.messages import set_current_lang

    set_current_lang("ja")
    body = LocalizedJSONResponse({"reason": ms("{name} に URL が無い", name="comfy1"), "big": [1, 2, 3]}).body
    assert json.loads(body) == {"reason": "comfy1 に URL が無い", "big": [1, 2, 3]}


def test_render_translates_nested_messages_and_marks_missing_ones(monkeypatch):
    monkeypatch.setitem(CATALOG, "en", {"分けられない: {reason}": "Cannot split: {reason}", "幅が足りない（{mm}mm）": "Too narrow ({mm} mm)"})
    inner = m("幅が足りない（{mm}mm）", mm=3)
    outer = m("分けられない: {reason}", reason=inner)
    assert render(outer, "ja") == "分けられない: 幅が足りない（3mm）"
    assert render(outer, "en") == "Cannot split: Too narrow (3 mm)"
    assert render("包んでいない文", "en") == "包んでいない文"
    assert render(m("辞書に無い文"), "en") == "⚠ 辞書に無い文"


def test_request_lang_reads_the_header():
    assert request_lang({"x-v3-lang": "en"}) == "en"
    assert request_lang({"x-v3-lang": " EN "}) == "en"
    assert request_lang({}) == "ja" and request_lang({"x-v3-lang": "fr"}) == "ja"


def test_error_response_is_in_the_request_language(monkeypatch):
    from v3server.http_routes.http_app_factory import v3_error

    monkeypatch.setitem(CATALOG, "en", {"コマ {id} には枠がまだ無い": "Panel {id} has no frame yet"})

    def call(lang: str | None) -> dict:
        headers = [(b"x-v3-lang", lang.encode())] if lang else []
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": headers})
        response = asyncio.run(v3_error(request, Invalid(m("コマ {id} には枠がまだ無い", id="p1"))))
        return json.loads(response.body)

    assert call(None) == {"code": "invalid", "detail": "コマ p1 には枠がまだ無い"}
    assert call("en") == {"code": "invalid", "detail": "Panel p1 has no frame yet"}


def test_http_and_validation_errors_are_in_the_request_language(monkeypatch):
    from fastapi.exceptions import RequestValidationError
    from pydantic import BaseModel, ValidationError, field_validator
    from starlette.exceptions import HTTPException

    from v3server.http_routes.http_app_factory import http_error, validation_error

    monkeypatch.setitem(CATALOG, "en", {"広げる量は0以上": "The amount to extend must be 0 or more"})

    class Body(BaseModel):
        grow: int
        name: str

        @field_validator("grow")
        @classmethod
        def _grow(cls, value: int) -> int:
            if value < 0:
                raise ValueError(m("広げる量は0以上"))
            return value

    def request(lang: str | None) -> Request:
        headers = [(b"x-v3-lang", lang.encode())] if lang else []
        return Request({"type": "http", "method": "POST", "path": "/", "headers": headers})

    def http(lang: str | None) -> dict:
        return json.loads(asyncio.run(http_error(request(lang), HTTPException(403, m("広げる量は0以上")))).body)

    assert http(None) == {"detail": "広げる量は0以上"}
    assert http("en") == {"detail": "The amount to extend must be 0 or more"}

    def validation(lang: str | None) -> dict[str, str]:
        with pytest.raises(ValidationError) as caught:
            Body.model_validate({"grow": -1})
        response = asyncio.run(validation_error(request(lang), RequestValidationError(caught.value.errors())))
        assert response.status_code == 422
        return {error["loc"][0]: error["msg"] for error in json.loads(response.body)["detail"]}

    assert validation(None) == {"grow": "広げる量は0以上", "name": "Field required"}
    assert validation("en") == {"grow": "The amount to extend must be 0 or more", "name": "Field required"}


def test_messages_inside_a_successful_response_are_in_the_request_language(monkeypatch):
    """成功の返事（dict・list）の中に入れた m() の文も、呼び出しの言語で出る。本物の組み立てと同じ部品で確かめる。"""
    import httpx
    from fastapi import FastAPI

    from v3server.http_routes.http_app_factory import LocalizedJSONResponse, RequestLanguage

    monkeypatch.setitem(CATALOG, "en", {"描き足す": "Outpaint", "{name} に届かない": "Cannot reach {name}"})
    app = FastAPI(default_response_class=LocalizedJSONResponse)
    app.add_middleware(RequestLanguage)

    @app.get("/list")
    async def listing():  # 返す型は書かない（下の試験の理由）
        return {"items": [{"id": "outpaint", "label": m("描き足す")}], "error": m("{name} に届かない", name="ComfyUI"), "n": 1}

    async def get(headers: dict[str, str]) -> dict:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return (await client.get("/list", headers=headers)).json()

    assert asyncio.run(get({})) == {"items": [{"id": "outpaint", "label": "描き足す"}], "error": "ComfyUI に届かない", "n": 1}
    assert asyncio.run(get({"X-V3-Lang": "en"})) == {"items": [{"id": "outpaint", "label": "Outpaint"}],
                                                     "error": "Cannot reach ComfyUI", "n": 1}
    # 言語を付けない次の呼び出しに、前の言語が残らない
    assert asyncio.run(get({}))["error"] == "ComfyUI に届かない"


def test_routes_do_not_declare_a_response_model():
    """API の関数に返す型（-> dict や response_model）を書くと、pydantic が m() の文を普通の文字列に直してから渡すので、
    返事を作る所で訳せなくなる（上の試験の形で確かめた）。型を書いた API が増えたら、ここで止める。"""
    from fastapi.routing import APIRoute

    from v3server.http_routes.http_app_factory import app

    typed = [f"{route.path} {sorted(route.methods)}" for route in app.routes
             if isinstance(route, APIRoute) and route.response_model is not None and route.path != "/health"]
    assert not typed, " / ".join(typed)
