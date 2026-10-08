"""段と比を決める問い（試作 p12 の B 案）。1ページのコマを段に分け、段の高さの比と段の中のコマの幅の比を出させる。
座標は panel_layout が比から計算する。

試作で分かったこと（V3検証の結果 2-1・2-2）
- 見せ場のコマを最後の段に置くために、コマの順番を入れ替えることがある（24回中6回）。段の中を逆の向きから並べることもある。
  どちらも読む順の検査（name_checks）で見つかるので、ここでは答えの形だけを確かめる。
- どの答えも段を横に割っただけの単調な割りになりやすい。
"""
from pydantic import BaseModel, Field

from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer
from v3server.name_structure.name_draft_schema import NamePage
from v3server.name_structure.reading_direction import ReadingDirection


def build_layout_tier_question(page: NamePage, reading_direction: ReadingDirection) -> str:
    """page のコマ（番号・大きさ・中身）を台本として渡す問いの文。"""
    if not page.panels:
        raise ValueError("page にコマが無い")
    if reading_direction == "right_to_left":
        page_way, cell_way = "右から左、上から下", "右から左"
    else:
        page_way, cell_way = "左から右、上から下", "左から右"
    script = "\n".join(f"{p.n}.（{p.size}）{p.content}" for p in page.panels)
    return f"""あなたは日本の漫画のネームを切る人です。次の台本の1ページ分を、コマ割りにしてください。
ページは{page_way}に読みます。コマの番号の順に読まれる必要があります。
各コマには大きさの希望（大・中・小）が付いています。

台本：
{script}

コマ割りを「段」と「比」だけで決めてください。座標はプログラムが計算します。
ページを上から下へ段に分け、各段の高さを比で決めます。各段の中を、{cell_way}へコマに分け、各コマの幅を比で決めます。

決め方にはいくつかの手があります。
・段の数を増やす：コマが小さくなり、情報は多く入るが見せ場が弱くなる
・1段に入れるコマを増やす：テンポは速くなるが、1コマが細くなる
・大きなコマに高い比を与える：見せ場が立つが、他の段が窮屈になる

出力はJSONだけにしてください。説明は書かないでください。形式：
{{"rows":[{{"h":段の高さの比,"cells":[{{"n":コマ番号,"w":幅の比}}]}}]}}
cellsは{cell_way}の順に並べます。"""


class _Cell(BaseModel):
    n: int
    w: float = Field(gt=0)


class _Row(BaseModel):
    h: float = Field(gt=0)
    cells: list[_Cell] = Field(min_length=1)


class _TierAnswer(BaseModel):
    rows: list[_Row] = Field(min_length=1)


class LayoutTiers(BaseModel):
    """段の分け方と比。NamePage の rows・row_height_ratios・cell_width_ratios に入れる値。"""

    rows: list[list[int]]
    row_height_ratios: list[float]
    cell_width_ratios: list[list[float]]


def parse_layout_tier_answer(answer: str) -> LayoutTiers:
    """答えを段と比に読む。同じコマが2回出るのは形の崩れとして扱う。順番の入れ替え・コマの抜けは検査に任せる。"""
    d = read_answer(answer, _TierAnswer)
    numbers = [c.n for r in d.rows for c in r.cells]
    if len(numbers) != len(set(numbers)):
        raise BrokenAnswerError("同じコマ番号が2回以上ある", answer)
    return LayoutTiers(
        rows=[[c.n for c in r.cells] for r in d.rows],
        row_height_ratios=[r.h for r in d.rows],
        cell_width_ratios=[[c.w for c in r.cells] for r in d.rows],
    )


def apply_layout_tiers(page: NamePage, tiers: LayoutTiers) -> NamePage:
    """page に段と比を入れた写しを返す。page そのものは変えない。"""
    return page.model_copy(
        update={
            "rows": tiers.rows,
            "row_height_ratios": tiers.row_height_ratios,
            "cell_width_ratios": tiers.cell_width_ratios,
        }
    )
