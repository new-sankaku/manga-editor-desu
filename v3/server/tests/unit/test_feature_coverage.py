"""V3細部の決めごと 10.1 の道具と 10.4 の各行が、サーバーの一覧（feature_coverage.py）に全部載っていて、
載せた操作と口が本当にあるかを確かめる。文書は llm_doc/V3細部の決めごと.md を読む。"""

import pathlib
import re
import typing

from fastapi.routing import APIRoute

from v3server.feature_coverage import EXCLUDED, ROWS_10_4, SCREEN, TOOLS_10_1
from v3server.http_routes.http_app_factory import app
from v3server.operations.all_operation_types import Op

DOC = pathlib.Path(__file__).resolve().parents[4] / "llm_doc" / "V3細部の決めごと.md"


def _section(text: str, head: str) -> str:
    start = text.index(head)
    nxt = re.search(r"^#{2,3} ", text[start + len(head):], re.M)
    return text[start: start + len(head) + nxt.start()] if nxt else text[start:]


def doc_tools_10_1() -> set[str]:
    sec = _section(DOC.read_text(encoding="utf-8"), "### 10.1")
    bullets = [b[2:] for b in sec.splitlines() if b.startswith("- ")]
    names: set[str] = set()
    # 「（2026-10-06 に追加）」のような日付の注は道具ではない
    for group in re.findall(r"（([^）0-9]*)）", bullets[0]):
        names.update(group.split("・"))
    right = re.search(r"その右に、(.*?)を置く", bullets[0])
    names.update(right.group(1).split("・"))
    for b in bullets[1:]:
        if "：" in b:
            names.add(b.split("：", 1)[0])
    return names


def doc_rows_10_4() -> list[str]:
    sec = _section(DOC.read_text(encoding="utf-8"), "### 10.4")
    rows = [line for line in sec.splitlines() if line.startswith("| ") and not line.startswith("|---")]
    return [r.split("|")[1].strip() for r in rows[1:]]


def _op_types() -> set[str]:
    inner = typing.get_args(Op)[0] if typing.get_origin(Op) is typing.Annotated else Op
    return {a.model_fields["type"].default for a in typing.get_args(inner)}


def _routes() -> set[str]:
    out = set()

    def walk(rs):
        for r in rs:
            if isinstance(r, APIRoute):
                out.update(f"{m} {r.path}" for m in r.methods)
            elif hasattr(r, "original_router"):
                walk(r.original_router.routes)

    walk(app.routes)
    return out


def _check(table: dict, names) -> None:
    ops, routes = _op_types(), _routes()
    missing = [n for n in names if n not in table]
    assert not missing, f"一覧に無い行: {missing}"
    for name in names:
        entry = table[name]
        if entry in (SCREEN, EXCLUDED):
            continue
        assert entry.get("ops") or entry.get("routes"), name
        assert set(entry.get("ops", [])) <= ops, (name, set(entry.get("ops", [])) - ops)
        assert set(entry.get("routes", [])) <= routes, (name, set(entry.get("routes", [])) - routes)


def test_every_10_1_tool_is_mapped():
    tools = doc_tools_10_1()
    assert {"ペン", "消しゴム", "ナイフ", "手のひら", "拡大縮小"} <= tools
    _check(TOOLS_10_1, sorted(tools))


def test_every_10_4_row_is_mapped():
    rows = doc_rows_10_4()
    assert len(rows) >= 20
    _check(ROWS_10_4, rows)
    # 一覧にだけある古い行が無い
    assert set(ROWS_10_4) == set(rows)
