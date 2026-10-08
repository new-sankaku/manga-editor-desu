"""ネームの構造データ（V3ハーネス設計 5.3・6章）。試作 p27 の出力の形を元にした。
LLM の答えも、人が画面で直したものも、取り込んだものも、この形で持つ。中身の良し悪しはここでは確かめない（name_checks の役目）。

人が枠だけ描いたネームや、取り込んだネームには、まだ決めていない項目がある（大きさ・写す範囲・人物など）。
その項目は None（未定）で持つ。推し量って埋めない（V3ハーネス設計 1章の芯5）。
未定の項目を使う検査は「データなし」になる（name_checks/name_check_runner.py）。AI の答えは未定を許さない
（llm_questions/name_draft_question.py が undecided_fields で確かめる）。"""
from typing import Literal

from pydantic import BaseModel, Field

from v3server.name_structure.reading_direction import PageSpec, ReadingDirection

PanelSize = Literal["大", "中", "小"]
PanelShape = Literal["四角", "斜め", "枠なし", "断ち切り"]
ShotRange = Literal["遠景", "引き", "全身", "膝上", "胸から上", "顔", "部分"]
CameraAngle = Literal["目の高さ", "見下ろし", "見上げ", "真横", "背後", "真上"]
FaceSize = Literal["大", "中", "小", "見えない"]
Facing = Literal["右", "左", "正面", "後ろ"]
BackgroundKind = Literal["描き込む", "簡略", "なし", "効果線やトーンだけ"]
StoryRole = Literal["起", "承", "転", "結"]
BalloonKind = Literal["台詞", "叫び", "心の声", "ナレーション"]


class FigureInPanel(BaseModel):
    """コマに写る人物1人。"""

    name: str
    face: FaceSize
    facing: Facing
    # 枠の中での人物の範囲（基本枠の座標・mm）。配置を決めた後にだけ入る
    box_mm: tuple[float, float, float, float] | None = None
    face_box_mm: tuple[float, float, float, float] | None = None


class Balloon(BaseModel):
    """吹き出し1つ。位置は仕上げ（S5）で決めるまで無い。"""

    # 話者と種類は、取り込んだネームでは分からないことがある（未定は None）
    speaker: str | None = None
    kind: BalloonKind | None = None
    text: str
    # 吹き出しの楕円を囲む四角（基本枠の座標・mm）。仕上げで置いた後にだけ入る
    box_mm: tuple[float, float, float, float] | None = None
    # 同じコマの1つ前の吹き出しと、わざとつなげて（重ねて）描くか。無ければ決めていない（つなげない扱い）
    joined_to_previous: bool | None = None


class PanelFrame(BaseModel):
    """コマの枠。多角形の頂点（基本枠の座標・mm）。断ち切りは基本枠の外へ出る。"""

    polygon_mm: list[tuple[float, float]] = Field(min_length=3)
    bleeds: bool


class NamePanel(BaseModel):
    """コマ1つ。番号は作品の最初からの通し番号。"""

    n: int
    # ここから sfx までは、未定なら None（人が枠だけ描いた・取り込んだネーム）
    size: PanelSize | None = None
    shape: PanelShape | None = None
    shot: ShotRange | None = None
    angle: CameraAngle | None = None
    people: list[FigureInPanel] | None = None
    background: BackgroundKind | None = None
    scene: int | None = None
    role: StoryRole | None = None
    hook: bool | None = None
    content: str | None = None
    balloons: list[Balloon] | None = None
    sfx: list[str] | None = None
    # コマ割りの計算（panel_layout）の後にだけ入る
    frame: PanelFrame | None = None
    # 場所の名前。同じ名前なら同じ場所。無ければ場面の番号を場所とみなす
    location: str | None = None
    # わざと重ねて置くコマの番号（重ねたコマ）。ここに挙げた組の重なりは指摘しない。無ければ重ねない
    overlaps: list[int] | None = None


class NamePage(BaseModel):
    """1ページ。rows は上の段から順に、段の中のコマの番号を読む順に並べたもの。"""

    page: int
    spread: bool
    # 段の割り。人が自由に枠を描いたページや取り込んだページでは未定（None）。そのときの読む順はコマの番号の順
    rows: list[list[int]] | None = None
    panels: list[NamePanel]
    # 段の高さの比と、段ごとのコマの幅の比（読む順）。決めていなければ無い
    row_height_ratios: list[float] | None = None
    cell_width_ratios: list[list[float]] | None = None
    # 段ごとの区切りの傾き（読む順の隣り合うコマの間ごと）。区切りの下端の x − 上端の x を段の高さで割った値（基本枠の座標）。
    # 0 なら縦の区切り。無ければ全部縦。角度は定数として扱う（制約の計算が線形で済む範囲）
    cut_slants: list[list[float]] | None = None
    # 見開き（spread）のページが2ページ分を占めるか。True なら左右の2ページとして数え、座標は左のページの基本枠の左上を原点に
    # 右のページまで続く（ノドは x = 基本枠の幅 + 基本枠の左右の余白）。無ければ1ページとして数える（ノドの検査の対象外）
    spread_occupies_two_pages: bool | None = None


class NameDraft(BaseModel):
    """1話のネーム。"""

    reading_direction: ReadingDirection
    page_spec: PageSpec
    # 1ページ目を左のページに置くか（V3ハーネス設計 6章「1ページ目が左」）
    first_page_is_left: bool
    pages: list[NamePage]

    def all_panels(self) -> list[NamePanel]:
        return [p for pg in self.pages for p in pg.panels]

    def undecided_fields(self) -> dict[str, list[str]]:
        """未定の項目の名前 → 未定の場所（「1ページ」「1ページ コマ3」）。全部決まっていれば空。
        項目の名前は NamePanel・NamePage の項目名。吹き出しの項目は "balloons.kind" の形。"""
        out: dict[str, list[str]] = {}

        def add(field: str, where: str) -> None:
            out.setdefault(field, []).append(where)

        for pg in self.pages:
            if pg.rows is None:
                add("rows", f"{pg.page}ページ")
            for p in pg.panels:
                where = f"{pg.page}ページ コマ{p.n}"
                for field in PANEL_DECIDABLE_FIELDS:
                    if getattr(p, field) is None:
                        add(field, where)
                for b in p.balloons or []:
                    for field in BALLOON_DECIDABLE_FIELDS:
                        if getattr(b, field) is None:
                            add(f"balloons.{field}", where)
        return out


# 未定（None）で持てる項目。検査の「要る項目」（name_checks/name_check_runner.py）はこの名前で書く
PANEL_DECIDABLE_FIELDS = ("size", "shape", "shot", "angle", "people", "background", "scene", "role", "hook", "content",
                          "balloons", "sfx")
BALLOON_DECIDABLE_FIELDS = ("speaker", "kind")
