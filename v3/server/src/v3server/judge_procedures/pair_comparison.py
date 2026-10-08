"""2枚を比べる手順（試作 p19・p32）。左右を入れ替えて2回聞き、2回が食い違えば引き分けにする。

試作で分かったこと（V3検証の結果 3-20・3-24・3-25・3-27）
- 名前を伏せないと、名前から答えが読めて甘くなる。画像は blind_image_copy の写しで見せ、組も写しの名前の順に並べる。
- 長い判定の手引きを付けたり、一度に多くの組を並べたりすると、答えが変わる（36組で元と違う組が9・12）。
  何組ずつ聞くか・比べる観点の文の長さは呼ぶ側が決めるが、短く・少なく聞く方が元の答えに近かった。
- 「同じ」を選べなくすると、逆の答えが増えた（2→4）。この手順では「同じ」を必ず選べるようにしてある。
"""
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from v3server.judge_procedures.blind_image_copy import BlindCopies, make_blind_copies
from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer

# LLM を呼ぶ関数。問いの文と、添える画像の場所（この順に添える）を受け取り、答えの文字列を返す
AskWithImages = Callable[[str, list[str]], Awaitable[str]]

AnswerChoice = Literal["A", "B", "同じ"]
PairSide = Literal["left", "right", "tie"]


@dataclass(frozen=True)
class ImagePair:
    """比べる2枚（元の画像の場所）。left・right は呼ぶ側の呼び方で、評価役に見せる A・B とは別。"""

    left: str
    right: str


@dataclass(frozen=True)
class PairOutcome:
    pair: ImagePair
    # 1回目（left を A に見せた）と2回目（right を A に見せた）の答えを、left・right に直したもの
    first: PairSide
    second: PairSide
    # 2回が同じならその答え、食い違えば引き分け
    verdict: PairSide

    @property
    def consistent(self) -> bool:
        return self.first == self.second


def build_pair_question(criterion: str, image_names: list[str], pair_lines: list[tuple[int, str, str]]) -> str:
    """criterion は「AとBのどちらが〜かを答えてください。」のような、比べる観点の文。
    image_names は添える順の写しの名前。pair_lines は（組の番号, A の名前, B の名前）。"""
    if not criterion.strip():
        raise ValueError("criterion が空")
    names = "\n".join(image_names)
    pairs = "\n".join(f"組{i}：A＝{a}　B＝{b}" for i, a, b in pair_lines)
    return f"""添えた画像は、どれも漫画の1コマ用の絵です。添えた順に、次の名前で呼びます。
{names}

下の各組について、{criterion}差が見分けられないときは「同じ」を選べます。「同じ」を選びすぎると順が分からなくなり、無理に選ぶと見分けられない差を作ってしまいます。
{pairs}

出力はJSONだけにしてください。形式：{{"pairs":[{{"id":組の番号,"choice":"A か B か 同じ"}}]}}"""


class _PairChoice(BaseModel):
    id: int
    choice: AnswerChoice


class _PairAnswer(BaseModel):
    pairs: list[_PairChoice]


def parse_pair_answer(answer: str, pair_count: int) -> dict[int, AnswerChoice]:
    """答えを組の番号ごとの選択に読む。組の抜け・重なりは BrokenAnswerError（抜けた組を引き分けとして埋めない）。"""
    items = read_answer(answer, _PairAnswer).pairs
    ids = sorted(x.id for x in items)
    if ids != list(range(1, pair_count + 1)):
        raise BrokenAnswerError(f"組の番号が 1〜{pair_count} に揃っていない: {ids}", answer)
    return {x.id: x.choice for x in items}


def _to_side(choice: AnswerChoice, swapped: bool) -> PairSide:
    if choice == "同じ":
        return "tie"
    a_is_left = not swapped
    return "left" if (choice == "A") == a_is_left else "right"


async def _ask_once(
    ask: AskWithImages,
    blind: BlindCopies,
    ordered_pairs: list[ImagePair],
    criterion: str,
    swapped: bool,
) -> dict[int, PairSide]:
    images = blind.sorted_originals([x for p in ordered_pairs for x in (p.left, p.right)])
    lines = []
    for i, p in enumerate(ordered_pairs, start=1):
        a, b = (p.right, p.left) if swapped else (p.left, p.right)
        lines.append((i, blind.blind_name(a), blind.blind_name(b)))
    prompt = build_pair_question(criterion, [blind.blind_name(x) for x in images], lines)
    answer = await ask(prompt, [str(blind.blind_path_by_original[x]) for x in images])
    choices = parse_pair_answer(answer, len(ordered_pairs))
    return {i: _to_side(c, swapped) for i, c in choices.items()}


async def compare_pairs(
    ask: AskWithImages,
    pairs: list[ImagePair],
    criterion: str,
    blind_dir: str,
    salt: str,
) -> list[PairOutcome]:
    """pairs を左右入れ替えて2回聞き、組ごとの結果を pairs の順で返す。
    答えの形が崩れていれば BrokenAnswerError をそのまま出す（片方の回だけで結果を作らない）。"""
    if not pairs:
        raise ValueError("pairs が空")
    if any(p.left == p.right for p in pairs):
        raise ValueError("同じ画像どうしの組がある")
    blind = make_blind_copies([x for p in pairs for x in (p.left, p.right)], blind_dir, salt)

    # 並びから狙いの順が読めないよう、組も写しの名前の順に並べる（左右を入れ替えても同じ順）
    def pair_key(p: ImagePair) -> str:
        return "".join(sorted((blind.blind_name(p.left), blind.blind_name(p.right))))

    ordered = sorted(pairs, key=pair_key)
    first, second = await asyncio.gather(
        _ask_once(ask, blind, ordered, criterion, swapped=False),
        _ask_once(ask, blind, ordered, criterion, swapped=True),
    )
    by_pair: dict[int, PairOutcome] = {}
    for i, p in enumerate(ordered, start=1):
        x, y = first[i], second[i]
        by_pair[id(p)] = PairOutcome(pair=p, first=x, second=y, verdict=x if x == y else "tie")
    return [by_pair[id(p)] for p in pairs]
