"""絵から、その絵を作るための指示文（プロンプト）を読み取らせる問い（今のアプリの「画像からプロンプトを読む」。
V3細部の決めごと 10.4）。読み取った文は案で、人が設定資料の生成の設定などに写して使う。

今のアプリは画像生成のサーバーの読み取り（タグの推定）を使う。ここは VLM に聞く。どちらが合うかは未検証。
"""

from pydantic import BaseModel, Field

from v3server.llm_questions.answer_json_reader import read_answer


def build_read_prompt_question(style_note: str | None) -> str:
    """style_note は、人が書いた指示文の書き方の希望（つなぐ生成のモデルに合わせて人が書く）。無ければ書き方を問わない。"""
    style = (f"指示文の書き方は、次の希望に合わせてください。\n{style_note}\n" if style_note
             else "指示文の書き方は決めていません。\n")
    return f"""添えた画像は、漫画の作画に使う絵です。この絵を画像生成で作り直すための指示文を書いてください。
{style}
書くときに選べることと、その結果：
・絵に写っている物だけを書く：作り直したときに元の絵に近くなるが、写っていない所は生成任せになる
・絵から推し量れることまで書く：足りない所を補えるが、外れると元の絵に無い物が出る
・描き方を書く：同じ描き方の絵が出やすくなるが、つなぐモデルが受けない言い方だと効かない
・避けたい物（否定の指示文）を書く：崩れを減らせることがあるが、書き過ぎると絵が乏しくなる
どれを入れるかは、絵を見て決めてください。読み取れない所は書かないでください。

出力はJSONだけにしてください。形式：{{"prompt":"...","negative_prompt":"... か null","unsure":["読み取りに自信の無い所を短く。無ければ空"]}}"""


class ReadPromptAnswer(BaseModel):
    prompt: str = Field(min_length=1)
    negative_prompt: str | None
    unsure: list[str]


def parse_read_prompt_answer(answer: str) -> ReadPromptAnswer:
    return read_answer(answer, ReadPromptAnswer)
