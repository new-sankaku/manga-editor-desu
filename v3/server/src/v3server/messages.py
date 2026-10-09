"""利用者に見せる文を、言語ごとに出す入口（llm_doc/V3細部の決めごと.md 24.5）。

- 文は日本語のまま書いて ``m("コマ {id} には枠がまだ無い", id=panel.id)`` と包む。1つ目は文字列をそのまま書く（f 文字列・変数・連結は不可）。
- ``m()`` が返すのは str の一種（Message）。中身は日本語の文そのものなので、今までの文字列と同じに使える（比べる・つなぐ・保存する）。
  日本語で出すときの文は、包む前と1文字も変わらない。
- 言語を決めるのは、返事を作る所だけ（http_routes/http_app_factory.py の失敗の返事）。そこで ``render(文, 言語)`` を呼ぶ。
- 値に Message を入れたとき（失敗の文の中に、別の失敗の文を入れる）は、中の文も同じ言語で出す。
  例外から文を取り出すときは ``text_of(e)`` を使う（``str(e)`` は普通の str になり、訳せなくなる）。
- 訳は message_catalog/<言語>/ に置く。左が日本語の文（m() に書いた文字列）、右が訳。
- 辞書に無い文は、頭に ⚠ を付けて日本語で出す（黙って別の言語で出さない）。抜けは tests/unit/test_message_catalog.py が止める。
- 訳すのは、返事を作る時に決まる文だけ。データベースに残した文（検査の結果・工程の理由・通知）は、残した時の日本語のまま。
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from v3server.message_catalog import CATALOG

LANGS = ("ja", "en")
LANG_HEADER = "x-v3-lang"
# 今の呼び出しの言語。呼び出しを受けた所（http_app_factory.py の RequestLanguage）が入れ、返事を作る所が読む
_request_lang: ContextVar[str] = ContextVar("v3_request_lang", default="ja")


class Message(str):
    """日本語の文と、その元（文の形と値）を持つ文字列。"""

    template: str
    values: dict[str, Any]

    def __new__(cls, template: str, values: dict[str, Any] | None = None) -> Message:
        values = values or {}
        text = super().__new__(cls, template.format(**values))
        text.template = template
        text.values = values
        return text

    def __getnewargs__(self) -> tuple[str, dict[str, Any]]:  # 写しを作るとき（pickle・copy）に元を落とさない
        return (self.template, self.values)


def m(template: str, /, **values: Any) -> Message:
    """利用者に見せる文を作る。"""
    return Message(template, values)


def text_of(error: BaseException) -> str:
    """例外の文。m() で作った文なら、元を持ったまま返す（別の文の値に入れても訳せる）。"""
    first = error.args[0] if error.args else ""
    return first if isinstance(first, Message) else str(error)


def request_lang(headers: Any) -> str:
    """呼び出しの言語。画面が X-V3-Lang で送る。無い・知らない言語なら日本語。"""
    value = (headers.get(LANG_HEADER) or "").strip().lower()
    return value if value in LANGS else "ja"


def render(text: Any, lang: str) -> str:
    """文を lang で出す。m() で作っていない文は、そのまま返す。"""
    if lang == "ja" or not isinstance(text, Message):
        return str(text)
    translated = CATALOG[lang].get(text.template)
    if translated is None:
        return f"⚠ {text}"
    return translated.format(**{k: render(v, lang) for k, v in text.values.items()})


def set_current_lang(lang: str) -> None:
    _request_lang.set(lang)


def current_lang() -> str:
    return _request_lang.get()


def render_tree(value: Any, lang: str) -> Any:
    """返事の中身（dict・list の入れ子）の中の m() の文を、その言語の文に替える。ほかの値は変えない。"""
    if lang == "ja":
        return value
    if isinstance(value, Message):
        return render(value, lang)
    if isinstance(value, dict):
        return {key: render_tree(item, lang) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [render_tree(item, lang) for item in value]
    return value
