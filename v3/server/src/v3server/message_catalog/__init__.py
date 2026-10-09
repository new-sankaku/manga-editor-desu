"""利用者に見せる文の訳（v3server/messages.py が読む）。

message_catalog/<言語>/<まとまり>.py が ``MESSAGES = {"日本語の文": "訳", …}`` を持つ。ここで言語ごとに1つにまとめる。
同じ文が2つのまとまりにあって訳が違えば、読み込む時に止める。
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path


def _load(lang: str) -> dict[str, str]:
    merged: dict[str, str] = {}
    package = f"{__name__}.{lang}"
    for info in pkgutil.iter_modules([str(Path(__file__).parent / lang)]):
        for key, value in importlib.import_module(f"{package}.{info.name}").MESSAGES.items():
            if merged.get(key, value) != value:
                raise ValueError(f"message_catalog/{lang}: 同じ文の訳がまとまりで違う: {key!r}")
            merged[key] = value
    return merged


CATALOG: dict[str, dict[str, str]] = {"en": _load("en")}
