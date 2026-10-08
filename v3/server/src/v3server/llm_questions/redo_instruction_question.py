"""コマの中身から画像生成のタグの列を作らせる問いと、作り直させる問い（試作 p30）。

試作で分かったこと（V3検証の結果 6-4）
- 理由を伝えずに作り直させると、前のタグとの重なりは理由ありより小さかった（0.374 と 0.46）。
  ただし理由なしの作り直しどうしは似る（0.524）。絵での比較は未検証。
"""
from pydantic import BaseModel

from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer

_FORMAT = '出力はJSONだけにしてください。形式：{"tags":"カンマ区切りのタグ"}'


def _head(panel_content: str, model_description: str) -> str:
    if not panel_content.strip():
        raise ValueError("panel_content が空")
    if not model_description.strip():
        raise ValueError("model_description が空")
    return f"""次の漫画の1コマを、画像生成のモデルに渡すタグの列にしてください。

渡す先のモデル：{model_description}

コマの中身：{panel_content}
"""


def build_first_tags_question(panel_content: str, model_description: str) -> str:
    """model_description は渡す先のモデルが受け付ける言葉の説明（つなぎ先の設定から渡す）。"""
    return _head(panel_content, model_description) + "\n" + _FORMAT


def build_redo_tags_question(
    panel_content: str,
    model_description: str,
    previous_tags: list[str],
    reason: str | None,
) -> str:
    """reason は採用されなかった理由。人が理由を付けなかったときは None を渡す（理由なしと書く）。"""
    if not previous_tags:
        raise ValueError("previous_tags が空")
    if reason is None:
        ask = "このタグの列で作った絵は採用されませんでした。作り直してください。"
    else:
        if not reason.strip():
            raise ValueError("reason が空の文字列。理由が無いときは None を渡す")
        ask = f"このタグの列で作った絵は採用されませんでした。採用されなかった理由：{reason}\n作り直してください。"
    return (
        _head(panel_content, model_description)
        + f"\n前に作ったタグの列はこれです。\n{', '.join(previous_tags)}\n\n{ask}\n\n"
        + _FORMAT
    )


class _TagsAnswer(BaseModel):
    tags: str


def parse_tags_answer(answer: str) -> list[str]:
    """答えをタグの並びに読む（前後の空白を除き、空のタグは捨てる）。タグが1つも無ければ BrokenAnswerError。"""
    tags = [t.strip() for t in read_answer(answer, _TagsAnswer).tags.split(",") if t.strip()]
    if not tags:
        raise BrokenAnswerError("タグが1つも無い", answer)
    return tags
