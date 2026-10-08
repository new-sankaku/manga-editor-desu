"""LLM の答えの文字列から JSON を取り出し、決まった形に読む。

取り出せない・形が合わないときは BrokenAnswerError を出す。サーバーの失敗の種類では
broken_response（返ってきた形が崩れている。使わない・送り直さない）に当たる。
足りない値を埋めて読み進めることはしない（崩れた答えを正しい答えに見せないため）。
"""
import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

# サーバーの失敗の種類の名前（generation_queue の送り直さない種類の一覧と同じ綴り）
BROKEN_RESPONSE_KIND = "broken_response"

# 答えの中の最初の「{」から最後の「}」まで。前後の説明や ``` の囲みを除くため
_OBJECT_SPAN = re.compile(r"\{.*\}", re.S)

ModelT = TypeVar("ModelT", bound=BaseModel)


class BrokenAnswerError(Exception):
    """返ってきた形が崩れている。failure_kind はサーバーの失敗の種類の名前。"""

    failure_kind = BROKEN_RESPONSE_KIND

    def __init__(self, detail: str, answer: str):
        super().__init__(f"{BROKEN_RESPONSE_KIND}: {detail}")
        self.detail = detail
        # 記録に残すための答えの頭。長い答えをそのまま持ち回らない
        self.answer_head = answer[:500]


def extract_json_object(answer: str) -> dict:
    """答えの文字列から JSON の物（辞書）を1つ取り出す。"""
    m = _OBJECT_SPAN.search(answer)
    if m is None:
        raise BrokenAnswerError("答えに JSON の物が無い", answer)
    try:
        value = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise BrokenAnswerError(f"JSON として読めない: {e}", answer) from e
    if not isinstance(value, dict):
        raise BrokenAnswerError("JSON の一番外が物（辞書）でない", answer)
    return value


def read_answer(answer: str, model: type[ModelT]) -> ModelT:
    """答えから JSON を取り出し、model の形に読む。形が合わなければ BrokenAnswerError。"""
    value = extract_json_object(answer)
    try:
        return model.model_validate(value)
    except ValidationError as e:
        raise BrokenAnswerError(f"形が合わない: {e.error_count()}か所 {e.errors()[0]['loc']} {e.errors()[0]['msg']}", answer) from e


def require_known_ids(found: list[str], known: set[str], what: str, answer: str) -> None:
    """答えが挙げた番号が、問いで渡した番号の中にあるか。無い番号があれば BrokenAnswerError。"""
    unknown = sorted({x for x in found if x not in known})
    if unknown:
        raise BrokenAnswerError(f"問いに無い{what}: {unknown}", answer)
