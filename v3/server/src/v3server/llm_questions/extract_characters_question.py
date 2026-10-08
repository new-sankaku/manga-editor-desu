"""企画の文（あらすじ・読者・メモ）から、登場人物を抜き出させる問い（今のアプリの「人物を抜き出す」。
V3細部の決めごと 10.4 の企画・設定資料）。抜き出した人物は、AIの案（proposed）として設定資料に入る。人が採るまで使わない。
"""

from pydantic import BaseModel, Field

from v3server.llm_questions.answer_json_reader import read_answer


def build_extract_characters_question(plan_text: str, known_names: list[str]) -> str:
    known = ("すでに設定資料にいる人物：" + "、".join(known_names) + "\n" if known_names
             else "設定資料にはまだ人物がいません。\n")
    return f"""次の文は、漫画の企画です。

---
{plan_text}
---

{known}この企画から、登場人物を抜き出してください。

抜き出すときに選べることと、その結果：
・名前の出ている人物だけにする：確かな人物だけになるが、名前の無い大事な人物が落ちる
・名前の無い人物も、役割を名前の代わりにして入れる：落ちは減るが、企画に書いていない人物を作ってしまうことがある
・企画から推し量れる特徴まで書く：作画に使いやすいが、外れた特徴が設定資料に入る（人が直す手間が増える）
すでに設定資料にいる人物は、出さないでください（同じ人物が2件になる）。

出力はJSONだけにしてください。形式：{{"characters":[{{"name":"...","traits":"企画から分かる人物の特徴。無ければ null","notes":"企画のどこから抜き出したか。無ければ null"}}]}}"""


class ExtractedCharacter(BaseModel):
    name: str = Field(min_length=1)
    traits: str | None
    notes: str | None


class _Answer(BaseModel):
    characters: list[ExtractedCharacter]


def parse_extract_characters_answer(answer: str) -> list[ExtractedCharacter]:
    return read_answer(answer, _Answer).characters
