"""利用者に見せる文を、言語ごとに出す入口（llm_doc/V3細部の決めごと.md 24.5）。

- 文は日本語のまま書いて ``m("コマ {id} には枠がまだ無い", id=panel.id)`` と包む。1つ目は文字列をそのまま書く（f 文字列・変数・連結は不可）。
- ``m()`` が返すのは str の一種（Message）。中身は日本語の文そのものなので、今までの文字列と同じに使える（比べる・つなぐ・保存する）。
  日本語で出すときの文は、包む前と1文字も変わらない。
- 言語を決めるのは、返事を作る所だけ（http_routes/http_app_factory.py の失敗の返事）。そこで ``render(文, 言語)`` を呼ぶ。
- 値に Message を入れたとき（失敗の文の中に、別の失敗の文を入れる）は、中の文も同じ言語で出す。
  例外から文を取り出すときは ``text_of(e)`` を使う（``str(e)`` は普通の str になり、訳せなくなる）。
- 訳は message_catalog/<言語>/ に置く。左が日本語の文（m() に書いた文字列）、右が訳。
- 辞書に無い文は、頭に ⚠ を付けて日本語で出す（黙って別の言語で出さない）。抜けは tests/unit/test_message_catalog.py が止める。
- データベースや Temporal の記録に残してから出す文（検査の結果・工程の理由・依頼の失敗の理由・通知）は ``ms()`` で作る。
  ``ms()`` が返すのは普通の str で、中身は「文の形と値」を包んだ物（下の「包んだ文」）。日本語の文そのものではない。
  f 文字列に入れる・つなぐ・JSON にする・例外の文にする・Temporal を通す、のどれをしても包みは残る。
  画面へ出す所（返事を作る所・SSE）と LLM へ送る所で ``render()`` が文に戻す。日本語で出すときも ``render()`` を通す。
  コードの中で文の中身を比べる・切る・探すことはしない（包みの中身を比べることになる）。試験で文を見るときは ``render(文, "ja")``。
- 迷ったら ``ms()`` を使う。``ms()`` の文をその場の返事に入れても、``render()`` が同じように戻す。
"""

from __future__ import annotations

import json
import re
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


# 包んだ文：開く印 + JSON の [文の形, 値] + 閉じる印。印は私用領域の文字で、利用者の文には出てこない。
# JSON の中の印は \\uXXXX に直すので、包みの中に生の印は入らない（入れ子でも、外から順に探せる）
_OPEN, _CLOSE = "\ue000", "\ue001"
_PACKED = re.compile(f"{_OPEN}([^{_OPEN}{_CLOSE}]*){_CLOSE}")
# 値に並び（list）を渡したときの区切り
_LIST_SEPARATOR = {"ja": "、", "en": ", "}


def _portable(value: Any) -> Any:
    if isinstance(value, Message):
        return _pack(value.template, value.values)
    if value is None or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_portable(item) for item in value]
    return str(value)


def ms(template: str, /, **values: Any) -> str:
    """残してから出す文を作る（包んだ文を返す）。値には、数・文字列・別の文（m()・ms()）・それらの並びを渡せる。"""
    return _pack(template, values)


def _pack(template: str, values: dict[str, Any]) -> str:
    body = json.dumps([template, {key: _portable(value) for key, value in values.items()}],
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _OPEN + body.replace(_OPEN, "\\ue000").replace(_CLOSE, "\\ue001") + _CLOSE


def _shown(value: Any, lang: str) -> Any:
    if isinstance(value, list):
        return _LIST_SEPARATOR[lang].join(str(_shown(item, lang)) for item in value)
    return render(value, lang) if isinstance(value, str) else value


def _unpack(packed: re.Match[str], lang: str) -> str:
    template, values = json.loads(packed.group(1))
    if lang == "ja":
        return template.format(**{key: _shown(value, "ja") for key, value in values.items()})
    translated = CATALOG[lang].get(template)
    if translated is None:
        return f"⚠ {_unpack(packed, 'ja')}"
    return translated.format(**{key: _shown(value, lang) for key, value in values.items()})


def has_packed(text: str) -> bool:
    return _OPEN in text


def text_of(error: BaseException) -> str:
    """例外の文。m() で作った文なら、元を持ったまま返す（別の文の値に入れても訳せる）。"""
    first = error.args[0] if error.args else ""
    return first if isinstance(first, Message) else str(error)


def request_lang(headers: Any) -> str:
    """呼び出しの言語。画面が X-V3-Lang で送る。無い・知らない言語なら日本語。"""
    value = (headers.get(LANG_HEADER) or "").strip().lower()
    return value if value in LANGS else "ja"


def render(text: Any, lang: str) -> str:
    """文を lang で出す。m() の文はその言語の文に、文の中の包んだ文（ms()）はどの言語でも文に戻す。ほかの文はそのまま返す。"""
    if lang == "ja" or not isinstance(text, Message):
        out = str(text)
    else:
        translated = CATALOG[lang].get(text.template)
        if translated is None:
            return f"⚠ {render(str(text), 'ja')}"
        out = translated.format(**{k: render(v, lang) for k, v in text.values.items()})
    return _PACKED.sub(lambda packed: _unpack(packed, lang), out) if _OPEN in out else out


def set_current_lang(lang: str) -> None:
    _request_lang.set(lang)


def current_lang() -> str:
    return _request_lang.get()


def render_tree(value: Any, lang: str) -> Any:
    """返事の中身（dict・list の入れ子）の中の m() の文と包んだ文（ms()）を、その言語の文に替える。ほかの値は変えない。"""
    if isinstance(value, str):
        return render(value, lang) if _OPEN in value or (lang != "ja" and isinstance(value, Message)) else value
    if isinstance(value, dict):
        return {key: render_tree(item, lang) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [render_tree(item, lang) for item in value]
    return value
