"""伏線の回収漏れと食い違いを探す問い（試作 p46）。
聞き方は2つ。問題のある行だけを挙げさせる（issues）／伏線に見える行を全部並べて状態を付けさせる（setups）。

試作で分かったこと（V3検証の結果 5-22）
- 4話・22行の台本で、どちらの聞き方でも回収漏れ2つ・食い違い2つを全部見つけた。
- 一部だけ回収された伏線は挙げず、並べる聞き方では「回収済み」とした。境目の伏線は人が見る必要がある。
- 台本は短い物。長い連載での精度は未検証。
"""
from typing import Literal

from pydantic import BaseModel, field_validator

from v3server.llm_questions.answer_json_reader import read_answer, require_known_ids
from v3server.llm_questions.contradiction_question import ScriptLine, script_lines_text

IssueKind = Literal["未回収", "食い違い"]
SetupState = Literal["回収済み", "未回収", "食い違い"]


def _head(settings: str, lines: list[ScriptLine]) -> str:
    episodes = len({x.episode for x in lines})
    return f"""次は連載漫画の{episodes}話分の台本と、その設定です。

設定：
{settings}

台本（行の番号・話数・中身）：
{script_lines_text(lines)}

"""


def build_foreshadow_issues_question(settings: str, lines: list[ScriptLine]) -> str:
    """問題のある行だけを挙げさせる問いの文。"""
    return _head(settings, lines) + (
        "この台本で、前の話で置いた伏線や手がかりが後の話で回収されていない所と、回収のしかたが前の描写と食い違っている所を探してください。\n"
        "伏線か日常の描写か迷う行は、挙げても挙げなくても構いません。挙げすぎると作者が直す手間が増え、挙げないと読者が引っかかる所が残ります。\n\n"
        '出力はJSONだけにしてください。形式：{"issues":[{"line":"行の番号","kind":"未回収 か 食い違い","why":"理由"}]}'
    )


def build_foreshadow_setups_question(settings: str, lines: list[ScriptLine]) -> str:
    """伏線に見える行を全部並べ、それぞれの状態を付けさせる問いの文。"""
    return _head(settings, lines) + (
        "この台本で、後の話で回収されることを読者が期待しそうな行（伏線や手がかり）を並べ、それぞれがどうなったかを付けてください。\n"
        "状態は「回収済み」「未回収」「食い違い」（回収はされたが前の描写と合わない）のどれかです。\n"
        "伏線か日常の描写か迷う行は、並べても並べなくても構いません。並べすぎると作者が読む手間が増え、並べないと見落としが残ります。\n\n"
        '出力はJSONだけにしてください。形式：{"setups":[{"line":"伏線の行の番号","payoff":"回収の行の番号（無ければ空）",'
        '"state":"回収済み か 未回収 か 食い違い","why":"理由"}]}'
    )


class ForeshadowIssue(BaseModel):
    line: str
    kind: IssueKind
    why: str


class ForeshadowSetup(BaseModel):
    line: str
    # 回収の行。無ければ None（答えでは空の文字列）
    payoff: str | None
    state: SetupState
    why: str

    @field_validator("payoff", mode="before")
    @classmethod
    def _empty_is_none(cls, v):
        return None if v == "" else v


class _IssuesAnswer(BaseModel):
    issues: list[ForeshadowIssue]


class _SetupsAnswer(BaseModel):
    setups: list[ForeshadowSetup]


def parse_foreshadow_issues_answer(answer: str, lines: list[ScriptLine]) -> list[ForeshadowIssue]:
    issues = read_answer(answer, _IssuesAnswer).issues
    require_known_ids([x.line for x in issues], {x.line_id for x in lines}, "行の番号", answer)
    return issues


def parse_foreshadow_setups_answer(answer: str, lines: list[ScriptLine]) -> list[ForeshadowSetup]:
    setups = read_answer(answer, _SetupsAnswer).setups
    ids = [x.line for x in setups] + [x.payoff for x in setups if x.payoff is not None]
    require_known_ids(ids, {x.line_id for x in lines}, "行の番号", answer)
    return setups
