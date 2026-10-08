"""総合（S6）の問い。ページの絵を見て何が描かれているかを要約させる問いと、要約を構成（S1）と比べて食い違いを挙げさせる
問い（候補48）。

試作で確かめていない（未検証）：要約の精度、食い違いの見落としと出しすぎの割合。指摘として出すだけで、人が見て決める。
"""

from pydantic import BaseModel, Field

from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer


def build_page_summary_question(page_numbers: list[int]) -> str:
    listed = "、".join(f"{i + 1}枚目＝{n}ページ" for i, n in enumerate(page_numbers))
    return (
        f"漫画のページの絵を {len(page_numbers)} 枚添えます（{listed}）。\n"
        "絵ごとに、そのページで起きていることを要約してください。セリフが読めないときは、絵から分かることだけを書けます。"
        "推測で補うと後で構成と比べたときに食い違いを見落とし、絵に無いことを書かないと要約が短くなります。\n\n"
        '出力はJSONだけにしてください。形式：{"pages":[{"image":絵の番号,"summary":"要約"}]}'
    )


def build_outline_compare_question(outline_text: str, summaries: list[tuple[int, str]]) -> str:
    pages = "\n".join(f"{n}ページ：{s}" for n, s in summaries)
    return (
        "次は漫画の1話の構成（予定）と、仕上がったページの絵の要約です。\n\n"
        f"構成：\n{outline_text}\n\n要約：\n{pages}\n\n"
        "構成の予定と仕上がりが食い違っているページを挙げてください。"
        "挙げなければ作者は予定と違う原稿を出し、挙げすぎると作者が直す必要の無いページを読み直します。"
        "要約が足りずに判断できないページは、挙げても挙げなくても構いません。\n\n"
        '出力はJSONだけにしてください。形式：{"gaps":[{"page":ページの番号,"why":"食い違い"}]}'
    )


class PageSummary(BaseModel):
    image: int = Field(ge=1)
    summary: str


class _Summaries(BaseModel):
    pages: list[PageSummary]


def parse_page_summary_answer(answer: str, count: int) -> list[PageSummary]:
    got = read_answer(answer, _Summaries).pages
    if sorted(p.image for p in got) != list(range(1, count + 1)):
        raise BrokenAnswerError(f"絵の番号が 1〜{count} にそろっていない", answer)
    return sorted(got, key=lambda p: p.image)


class Gap(BaseModel):
    page: int
    why: str


class _Gaps(BaseModel):
    gaps: list[Gap]


def parse_outline_compare_answer(answer: str, pages: set[int]) -> list[Gap]:
    got = read_answer(answer, _Gaps).gaps
    unknown = sorted({g.page for g in got} - pages)
    if unknown:
        raise BrokenAnswerError(f"無いページの番号がある: {unknown}", answer)
    return got
