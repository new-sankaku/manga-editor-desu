"""構成（S1）の問い。1話のページ配分（ページごとの中身と役目）・見せ場・伏線を書かせる問いと、書いた構成を観点ごとに
判定させる問い（設計 5 の表：変化・つかみ・見せ場・ご都合主義など。観点の言葉は頼む人が渡す）。

試作で確かめていない（未検証）：構成の良し悪しの判定の精度。判定は指摘として出すだけで、候補を落とすのには使わない。
"""

from pydantic import BaseModel, Field

from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer


def build_structure_question(plot: str, characters: list[tuple[str, str]], episode_number: int, page_count: int,
                             earlier: list[str], note: str | None) -> str:
    chars = "\n".join(f"- {n}：{t}" for n, t in characters) or "（まだ無い）"
    before = "\n".join(earlier)
    return (
        f"次は漫画の企画のあらすじと登場人物です。第{episode_number}話の構成を書きます。\n\n"
        f"あらすじ：\n{plot}\n\n登場人物：\n{chars}\n\n"
        + (f"前の話までの構成：\n{before}\n\n" if before else "")
        + (f"前の案を見た作者の指摘：\n{note}\n\n" if note else "")
        + f"この話は {page_count} ページです。ページごとに、そのページで起きることと、話の中での役目を書いてください。\n"
        "見せ場をどのページに置くかで、めくった直後に見せるか、ページの終わりで引くかが変わります。"
        "見せ場が多いと一つ一つが弱くなり、少ないと間延びします。\n"
        "伏線は置いても置かなくても構いません。置くと後の話で回収する約束が増え、置かないと後の展開が唐突に見えることがあります。\n\n"
        '出力はJSONだけにしてください。形式：{"pages":[{"page":ページの番号,"summary":"そのページで起きること",'
        '"role":"話の中での役目"}],"highlights":[ページの番号],"foreshadow":[{"page":ページの番号,"setup":"置く伏線",'
        '"payoff":"回収の見込み"}]}'
    )


def build_structure_views_question(outline_text: str, views: list[str]) -> str:
    listed = "\n".join(f"- {v}" for v in views)
    return (
        "次は漫画の1話の構成です。\n\n"
        f"{outline_text}\n\n"
        f"この構成を次の観点ごとに見て、問題が無いか（ok）と理由を書いてください。\n{listed}\n\n"
        "問題が無いとして見逃すと作者がネームまで進めてから気付くことになり、問題があるとしすぎると作者が直す必要のない所を"
        "読むことになります。判断がつかない観点は ok を null にできます。\n\n"
        '出力はJSONだけにしてください。形式：{"views":[{"view":"観点","ok":真偽 または null,"why":"理由"}]}'
    )


class OutlinePage(BaseModel):
    page: int = Field(ge=1)
    summary: str = Field(min_length=1)
    role: str


class Foreshadow(BaseModel):
    page: int = Field(ge=1)
    setup: str = Field(min_length=1)
    payoff: str


class Outline(BaseModel):
    pages: list[OutlinePage] = Field(min_length=1)
    highlights: list[int]
    foreshadow: list[Foreshadow]


def parse_structure_answer(answer: str) -> Outline:
    return read_answer(answer, Outline)


def outline_text(o: dict) -> str:
    lines = [f"{p['page']}ページ：{p['summary']}（{p['role']}）" for p in o["pages"]]
    if o.get("highlights"):
        lines.append("見せ場：" + "、".join(f"{x}ページ" for x in o["highlights"]))
    lines += [f"伏線（{f['page']}ページ）：{f['setup']} → {f['payoff']}" for f in o.get("foreshadow") or []]
    return "\n".join(lines)


class ViewJudge(BaseModel):
    view: str
    ok: bool | None
    why: str


class _Views(BaseModel):
    views: list[ViewJudge]


def parse_structure_views_answer(answer: str, views: list[str]) -> list[ViewJudge]:
    got = read_answer(answer, _Views).views
    unknown = sorted({v.view for v in got} - set(views))
    if unknown:
        raise BrokenAnswerError(f"聞いていない観点がある: {unknown}", answer)
    missing = sorted(set(views) - {v.view for v in got})
    if missing:
        raise BrokenAnswerError(f"答えの無い観点がある: {missing}", answer)
    return got
