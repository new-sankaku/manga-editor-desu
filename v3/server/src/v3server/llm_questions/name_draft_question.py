"""ネームを作る問い（試作 p27）。あらすじと登場人物から、ページ・コマ・写し方・吹き出しを JSON で出させる。

試作で分かったこと（V3検証の結果 2-3〜2-16）
- 読む順の崩れはほぼ出ないが、段の中のコマを逆の向きから書くことがある（書き方の揺れ）。
- 同じ段の割りの繰り返し・大きいコマの無いページ・吹き出しの字数の超過は出る。数えるのは name_checks の役目。
- 数で見られるのは形だけで、良し悪しは漫画を描く人の判定が要る。
"""
from typing import get_args

from pydantic import BaseModel

from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer
from v3server.name_structure.name_draft_schema import (
    BackgroundKind,
    BalloonKind,
    CameraAngle,
    FaceSize,
    Facing,
    NameDraft,
    NamePage,
    PanelShape,
    PanelSize,
    ShotRange,
    StoryRole,
)
from v3server.name_structure.reading_direction import PageSpec, ReadingDirection


def _choices(literal) -> str:
    """ネームの形の選択肢を「・」でつなぐ。形と問いの選択肢をずらさないため、形から作る。"""
    return "・".join(get_args(literal))


def book_rule_text(reading_direction: ReadingDirection, first_page_is_left: bool) -> str:
    """本の並びとコマの読む向きの説明。アプリの制約なので断定で書く。"""
    first_side = "左" if first_page_is_left else "右"
    if reading_direction == "right_to_left":
        return (
            "本の決まり：右から左へ読む本です。見開きでは右のページを先に、左のページを後に読み、左のページの次はめくりになります。"
            f"1ページ目は{first_side}のページです。\n"
            "コマは各ページの中で右上から左下へ読みます。"
        )
    return (
        "本の決まり：左から右へ読む本です。見開きでは左のページを先に、右のページを後に読み、右のページの次はめくりになります。"
        f"1ページ目は{first_side}のページです。\n"
        "コマは各ページの中で左上から右下へ読みます。"
    )


def build_name_draft_question(
    plot: str,
    characters: list[tuple[str, str]],
    page_count: int,
    reading_direction: ReadingDirection,
    first_page_is_left: bool,
) -> str:
    """ネームを作る問いの文。characters は（名前, 人物と話し方の説明）の並び。"""
    if page_count < 1:
        raise ValueError("page_count は1以上")
    if not characters:
        raise ValueError("characters が空")
    charas = "\n".join(f"{name}（{profile}）" for name, profile in characters)
    row_from = "右" if reading_direction == "right_to_left" else "左"
    return f"""あなたは日本の漫画のネームを切る人です。次のあらすじから、{page_count}ページの読み切りのネームを作ってください。

あらすじ：
{plot}

登場人物（話し方）：
{charas}

{book_rule_text(reading_direction, first_page_is_left)}

各コマについて、次を決めてください。どれも選び方で読みやすさが変わります。
・大きさ（{_choices(PanelSize)}）：大きいコマは見せ場が立つが、多いとどれも立たなくなる
・形（{_choices(PanelShape)}）：四角以外は勢いが出るが、読む順が迷いやすくなり、多いと見づらい
・写す範囲（{_choices(ShotRange)}）：遠くから写すと場所と位置関係が分かり、近くから写すと感情が伝わる。同じ範囲が続くと単調になる
・角度（{_choices(CameraAngle)}）：変えると変化が付くが、理由のない角度は読む人を迷わせる
・写る人物ごとの顔の大きさ（{_choices(FaceSize)}）と向き（{_choices(Facing)}）
・背景（{_choices(BackgroundKind)}）：描くと場所が分かり、省くと人物に目が行く
・場面の番号（場所か時間が変わったら次の番号）
・話の中での役目（{_choices(StoryRole)}のどれか）
・ページの最後のコマなら、次のページを読ませる引きになっているか（はい・いいえ）
・吹き出し（話す人・種類（{_choices(BalloonKind)}）・文）と描き文字の擬音
・コマの中身（何が描かれているか）

各ページについて、段の分け方（上から順に、各段に入るコマの番号を{row_from}から並べたもの）と、見開きにするかを決めてください。

出力はJSONだけにしてください。説明は書かないでください。形式：
{{"pages":[{{"page":ページ番号,"spread":真偽,"rows":[[コマ番号,...],...],"panels":[{{"n":コマ番号,"size":"...","shape":"...","shot":"...","angle":"...",
"people":[{{"name":"...","face":"...","facing":"..."}}],"background":"...","scene":場面の番号,"role":"...","hook":真偽,"content":"...",
"balloons":[{{"speaker":"...","kind":"...","text":"..."}}],"sfx":["..."]}}]}}]}}
コマ番号は作品の最初から通し番号にしてください。"""


class _NameDraftAnswer(BaseModel):
    pages: list[NamePage]


def parse_name_draft_answer(
    answer: str,
    reading_direction: ReadingDirection,
    page_spec: PageSpec,
    first_page_is_left: bool,
) -> NameDraft:
    """答えをネームの形に読む。選択肢の外の値・欠けた欄は BrokenAnswerError。中身の良し悪しは見ない。
    ネームの形は未定（None）の項目を許すが（人が枠だけ描いた・取り込んだネームのため）、AI には全部の欄を埋めさせる。
    欠けた欄を未定として受け取ると、問いの答えが崩れたことに気付けないため。"""
    pages = read_answer(answer, _NameDraftAnswer).pages
    draft = NameDraft(
        reading_direction=reading_direction,
        page_spec=page_spec,
        first_page_is_left=first_page_is_left,
        pages=pages,
    )
    missing = draft.undecided_fields()
    if missing:
        raise BrokenAnswerError(f"欠けた欄がある: {', '.join(f'{k}（{v[0]} ほか{len(v)}か所）' for k, v in missing.items())}",
                                answer)
    return draft
