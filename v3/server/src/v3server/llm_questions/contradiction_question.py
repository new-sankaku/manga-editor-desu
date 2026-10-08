"""話の食い違いを探す問い（試作 p28）。口調・設定・物の状態・時間の観点で、設定や前の行と食い違う行を挙げさせる。

試作で分かったこと（V3検証の結果 2-11・3-22・5-22）
- 3話の台本に入れた12か所を、全部の観点を1回で聞いても、観点ごとに分けて聞いても、ほぼ全部見つけた。誤りの指摘は0。
  この難しさでは分けても差がほぼ出ない。長い連載での精度は未検証。
"""
from dataclasses import dataclass

from pydantic import BaseModel

from v3server.llm_questions.answer_json_reader import read_answer, require_known_ids

# 観点の名前と、問いに書く説明。説明に台本の中身に寄った例は書かない（答えがその例に寄るため）
CONTRADICTION_VIEWS: dict[str, str] = {
    "口調": "登場人物の話し方が、設定の話し方と合っているか",
    "設定": "人物について設定に書かれていることと、台本の描写が合っているか",
    "物の状態": "物や体の状態が、前の行で起きたことと合っているか",
    "時間": "時間の流れと、前の話で起きたこと・話したことが、後の行と合っているか",
}


@dataclass(frozen=True)
class ScriptLine:
    """台本の1行。line_id は問いと答えで行を指す番号。"""

    line_id: str
    episode: int
    text: str


def script_lines_text(lines: list[ScriptLine]) -> str:
    """台本の行を「番号（第n話）中身」で並べる。伏線の問いでも使う。"""
    if not lines:
        raise ValueError("台本の行が空")
    ids = [x.line_id for x in lines]
    if len(ids) != len(set(ids)):
        raise ValueError("台本の行の番号が重なっている")
    return "\n".join(f"{x.line_id}（第{x.episode}話）{x.text}" for x in lines)


def build_contradiction_question(settings: str, lines: list[ScriptLine], views: list[str]) -> str:
    """views は CONTRADICTION_VIEWS の名前の並び。全部を1回で聞くか、観点ごとに分けて聞くかは呼ぶ側が決める。"""
    if not views:
        raise ValueError("views が空")
    unknown = [v for v in views if v not in CONTRADICTION_VIEWS]
    if unknown:
        raise ValueError(f"知らない観点: {unknown}")
    vs = "\n".join(f"・{v}：{CONTRADICTION_VIEWS[v]}" for v in views)
    return f"""次は漫画の台本と、その設定です。台本の中で、設定や前の行と食い違っている行を探してください。

見る観点：
{vs}

食い違いかどうか迷う行は、挙げても挙げなくても構いません。挙げすぎると直す人の手間が増え、挙げないと矛盾が残ります。

設定：
{settings}

台本（行の番号・話数・中身）：
{script_lines_text(lines)}

出力はJSONだけにしてください。形式：{{"issues":[{{"line":"行の番号","why":"何と食い違っているか"}}]}}"""


class ContradictionIssue(BaseModel):
    line: str
    why: str


class _ContradictionAnswer(BaseModel):
    issues: list[ContradictionIssue]


def parse_contradiction_answer(answer: str, lines: list[ScriptLine]) -> list[ContradictionIssue]:
    """答えを指摘の並びに読む。問いに無い行の番号を挙げたら BrokenAnswerError。"""
    issues = read_answer(answer, _ContradictionAnswer).issues
    require_known_ids([x.line for x in issues], {x.line_id for x in lines}, "行の番号", answer)
    return issues
