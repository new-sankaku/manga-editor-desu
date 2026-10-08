"""候補から1枚を選ばせる手順（試作 p33）。どれも狙いに合わなければ「なし」を許す。

試作で分かったこと（V3検証の結果 4-14）
- 1枚だけ作ると狙いどおりは 0.824。3枚から選ばせると、選んだ33回が全部狙いどおりで、「なし」の3回は全部外れの組と一致した。
- 名前を伏せないと、名前から答えが読めて甘くなる（p19）。画像は blind_image_copy の写しで見せ、写しの名前の順に並べる。
- 長い説明を付けたり一度に多く並べたりすると、評価役の答えが変わる（p32）。候補の数・狙いの文の長さは呼ぶ側が決める。
"""
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from v3server.judge_procedures.blind_image_copy import make_blind_copies
from v3server.judge_procedures.pair_comparison import AskWithImages
from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer

NONE_PICKED = "なし"


@dataclass(frozen=True)
class CandidatePick:
    # 選ばれた候補（元の画像の場所）。「なし」なら None
    picked: str | None
    why: str


def build_candidate_question(target: str, image_names: list[str]) -> str:
    """target は狙いの文（コマの役目・人物・場所など）。image_names は添える順の写しの名前。"""
    if not target.strip():
        raise ValueError("target が空")
    names = "\n".join(image_names)
    return f"""添えた{len(image_names)}枚は、どれも漫画の1コマ用に、同じ狙いで作った絵です。添えた順に、次の名前で呼びます。
{names}

狙い：{target}
1枚の絵が1つのコマです（絵の中にさらにコマが並んでいるものは狙いに合いません）。

狙いにいちばん合う1枚を選んでください。どれも狙いに合わなければ「{NONE_PICKED}」と答えてください。
「{NONE_PICKED}」を選ぶと作り直しになり時間がかかります。合わない絵を選ぶと、そのまま次の工程に進みます。

出力はJSONだけにしてください。形式：{{"pick":"名前 か {NONE_PICKED}","why":"理由"}}"""


class _PickAnswer(BaseModel):
    pick: str
    why: str


def parse_candidate_answer(answer: str, image_names: list[str]) -> tuple[str | None, str]:
    """答えを（選ばれた写しの名前か None, 理由）に読む。名前でも「なし」でもなければ BrokenAnswerError。
    画像をファイルの場所で読ませる呼び方では場所ごと答えることがあるので、最後の名前の部分で照らす。"""
    d = read_answer(answer, _PickAnswer)
    pick = d.pick.strip()
    if pick == NONE_PICKED:
        return None, d.why
    name = Path(pick).name
    if name not in image_names:
        raise BrokenAnswerError(f"候補に無い名前: {pick}", answer)
    return name, d.why


async def pick_candidate(
    ask: AskWithImages,
    candidates: list[str],
    target: str,
    blind_dir: str,
    salt: str,
) -> CandidatePick:
    """candidates（元の画像の場所）から、狙いに合う1枚を選ばせる。"""
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidates に同じ画像が重なっている")
    blind = make_blind_copies(candidates, blind_dir, salt)
    ordered = blind.sorted_originals(candidates)
    names = [blind.blind_name(x) for x in ordered]
    answer = await ask(build_candidate_question(target, names), [str(blind.blind_path_by_original[x]) for x in ordered])
    name, why = parse_candidate_answer(answer, names)
    return CandidatePick(picked=None if name is None else blind.original_of(name), why=why)
