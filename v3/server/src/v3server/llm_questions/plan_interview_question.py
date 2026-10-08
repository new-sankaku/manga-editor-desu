"""企画の聞き取り（S0）の問い。作業役が先に人へ質問し、答えがそろったら企画を書く（設計 5.2、候補1・71）。

1回の答えに「人への質問」と「企画の案」の両方を入れられる形にする。質問だけ・案だけ・両方のどれを出すかは作業役が
選ぶ。人は質問に答える（答えは次の回の問いに入る）か、案を採る。

試作で確かめていない（未検証）：質問の数と中身の良し悪し、答えを重ねたときに企画が人の言葉から離れないか。
"""

from pydantic import BaseModel, Field

from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer

PLAN_FIELDS = {"synopsis": "あらすじ", "audience": "読者", "exclusions": "入れないもの", "notes": "メモ"}


def build_plan_interview_question(request: str, current: dict[str, object], answers: list[str],
                                  required: list[str]) -> str:
    now = "\n".join(f"- {PLAN_FIELDS[k]}：{v}" for k, v in current.items() if v not in (None, "", []))
    talk = "\n\n".join(f"人の答え{i + 1}：\n{a}" for i, a in enumerate(answers))
    need = "、".join(PLAN_FIELDS[k] for k in required)
    return (
        "これから漫画の企画を書きます。次は作者の最初の要望です。\n\n"
        f"要望：\n{request}\n\n"
        + (f"今の企画（作者が書いた物を含む）：\n{now}\n\n" if now else "")
        + (f"これまでに作者へ聞いた質問への答え：\n{talk}\n\n" if talk else "")
        + f"企画には {need} が要ります。\n"
        "作者へ質問を返すことも、企画の案を書くことも、両方することもできます。"
        "質問が多いと作者の手間が増え、聞かずに書くと作者の考えと違う企画になって書き直しが増えます。"
        "要望と答えから決められない所を推測で埋めると、後の工程（構成・ネーム）がその推測の上に積み上がります。\n"
        "案を書かないときは plan を null にしてください。今の企画にある項目を書き換えるかどうかも選べます。"
        "書き換えると作者が書いた言葉が消えるので、作者は採る前に見比べることになります。\n\n"
        '出力はJSONだけにしてください。形式：{"questions":[{"ask":"作者への質問","why":"聞く理由"}],'
        '"plan":{"synopsis":"あらすじ","audience":"読者","exclusions":["入れないもの"],"notes":"メモ"} または null}'
    )


class InterviewQuestion(BaseModel):
    ask: str = Field(min_length=1)
    why: str


class PlanDraft(BaseModel):
    synopsis: str | None = None
    audience: str | None = None
    exclusions: list[str] | None = None
    notes: str | None = None


class PlanInterviewAnswer(BaseModel):
    questions: list[InterviewQuestion]
    plan: PlanDraft | None


def parse_plan_interview_answer(answer: str) -> PlanInterviewAnswer:
    out = read_answer(answer, PlanInterviewAnswer)
    if not out.questions and out.plan is None:
        raise BrokenAnswerError("質問も企画の案も無い", answer)
    return out


def missing_fields(plan: PlanDraft | None, required: list[str]) -> list[str]:
    values = plan.model_dump() if plan else {}
    return [k for k in required if values.get(k) in (None, "", [])]
