"""コマの中身から画像生成のタグの列を作らせる問いと、作り直させる問い（試作 p30）。

試作で分かったこと（V3検証の結果 6-4）
- 理由を伝えずに作り直させると、前のタグとの重なりは理由ありより小さかった（0.374 と 0.46）。
  ただし理由なしの作り直しどうしは似る（0.524）。絵での比較は未検証。
"""
from pydantic import BaseModel

from v3server.llm_questions.ai_look_signs import AI_LOOK_SIGNS
from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer
from v3server.messages import ms

_FORMAT = '出力はJSONだけにしてください。形式：{"tags":"カンマ区切りのタグ"}'  # i18n:prompt
# 作り直しの選び方と、それぞれで起きること（決め打ちにしない。CLAUDE.md）
_REDO_CHOICES = """新しいタグの列の作り方には、次のような手があります。どれを選ぶか、どこまで変えるかは任せます。
・理由に当たるタグだけを変え、ほかは残す：前の絵で合っていた所は残りやすいが、理由に書かれていない問題も残る
・タグの列を大きく組み替える：前と違う絵になりやすいが、前の絵で合っていた所も変わることがある
・タグを減らして短くする：指示どうしのぶつかりは減るが、コマの中身のうち描かれない所が出やすい
・タグを足して細かくする：狙いを細かく伝えられるが、モデルが一部のタグを無視しやすくなる"""  # i18n:prompt
# AIらしい絵の避け方（決め打ちにしない。CLAUDE.md）
_AI_LOOK = f"""この作品では、いかにもAIで作ったと見える絵は、コマの中身に合っていても採用されません。AIらしく見える所：{AI_LOOK_SIGNS}。
品質と画風の言葉は、頼む人が決めてこのタグの列とは別に足します。避け方には次のような手があります。どれを使うか、使わないかは任せます。
・画材や描き方を表すタグを入れる：手で描いた絵に寄りやすいが、渡す先のモデルが知らない言葉は無視されるか、絵が崩れる
・光・つや・描き込みの多さを強めるタグを入れない：光沢と描き込みすぎを避けやすいが、絵が平たく見えることがある
・人物の顔や体つきの特徴をコマの中身から拾ってタグにする：整いすぎた同じ顔を避けやすいが、タグが増えてほかのタグが効きにくくなる
・何も足さない：コマの中身は伝わりやすいが、AIらしい絵になりやすい"""  # i18n:prompt


def _head(panel_content: str, model_description: str) -> str:  # i18n:prompt
    if not panel_content.strip():
        raise ValueError("panel_content が空")  # i18n:dev
    if not model_description.strip():
        raise ValueError("model_description が空")  # i18n:dev
    return f"""次の漫画の1コマを、画像生成のモデルに渡すタグの列にしてください。

渡す先のモデル：{model_description}

コマの中身：{panel_content}

{_AI_LOOK}
"""


def build_first_tags_question(panel_content: str, model_description: str) -> str:
    """model_description は渡す先のモデルが受け付ける言葉の説明（接続先の設定から渡す）。"""
    return _head(panel_content, model_description) + "\n" + _FORMAT


def build_redo_tags_question(  # i18n:prompt
    panel_content: str,
    model_description: str,
    previous_tags: list[str],
    reason: str | None,
) -> str:
    """reason は採用されなかった理由。人が理由を付けなかったときは None を渡す（理由なしと書く）。"""
    if not previous_tags:
        raise ValueError("previous_tags が空")  # i18n:dev
    if reason is None:
        ask = "このタグの列で作った絵は採用されませんでした。理由は分かりません。\n" + _REDO_CHOICES
    else:
        if not reason.strip():
            raise ValueError("reason が空の文字列。理由が無いときは None を渡す")  # i18n:dev
        ask = f"このタグの列で作った絵は採用されませんでした。採用されなかった理由：{reason}\n" + _REDO_CHOICES
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
        raise BrokenAnswerError(ms("タグが1つも無い"), answer)
    return tags
