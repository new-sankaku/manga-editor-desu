"""原稿として出すための設定の形（V3細部の決めごと 1章・3章・7章）。作品の preferences とページの行が持つ。

- 本の構成：ページの種類（表紙・カラー・本文・白ページ）と、ノンブル（位置・書体・始まりの番号・隠すページ）
- 色と解像度：ページごとの色の種類（2階調・グレー・カラー）と解像度。作品の既定をページが上書きする
- 2階調にするときの決まり（線と文字の閾値・絵の網点）
- 安全線（文字を入れてよい範囲）と、入稿のページ数の決まり（4か8の倍数）
- 写植の組版（行間・自動の改行・縦中横・揃え）と、文字の一部の書式（TextSpan）

どの値も、決まっていなければ書き出しは止める（既定の値は置かない）。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from v3server.name_structure.item_styles import Color

PageKind = Literal["cover", "color_page", "body", "blank"]
ColorMode = Literal["bilevel", "grayscale", "color"]
NombreDisplay = Literal["visible", "hidden", "none"]
DotShape = Literal["round", "line", "square"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Screen(_Strict):
    """網点の決まり（線数・角度・形）。"""

    lines_per_inch: float = Field(gt=0)
    angle_deg: float
    dot_shape: DotShape


class BilevelSettings(_Strict):
    """2階調のページの作り方。線・文字・コマ枠・フキダシ・トーンは閾値で、コマの絵（線画の層を除く）は網点で2値にする
    （線を網点に通すと縁が点々に切れるため。print_export/binarize_and_halftone.py）。"""

    # 閾値（1〜255）。これより暗い画素を黒にする
    threshold: int = Field(ge=1, le=255)
    # コマの絵の灰色を網点にする決まり
    image_screen: Screen
    # PDF の中の2値の絵の符号化
    pdf_codec: Literal["flate", "ccitt_g4"]


class SafeArea(_Strict):
    """安全線：仕上がりの端から内側へ、この幅より内に文字を入れる。ノド（綴じる側）と小口（外側）を分けて持つ。"""

    top_mm: float = Field(ge=0)
    bottom_mm: float = Field(ge=0)
    gutter_mm: float = Field(ge=0)
    outer_mm: float = Field(ge=0)


class PrintSettings(_Strict):
    """作品の入稿の設定。値は入稿先の規定から人が入れる（決めごと 3章：規定の値は未調査）。"""

    # 作品の略号（ファイル名「略号_話_ページ3桁」の先頭。決めごと 7章）
    file_code: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    # ページの色の種類の既定（ページの color_mode が上書きする）
    color_mode: ColorMode
    # 色の種類ごとの解像度の既定（ページの dpi が上書きする）
    dpi_by_color_mode: dict[ColorMode, int]
    # 2階調のページがあるときに要る
    bilevel: BilevelSettings | None = None
    safe_area: SafeArea
    # 入稿のページ数の決まり（話か巻のページ数がこの倍数）。決まりが無い入稿先（Web など）は None
    page_count_multiple: Literal[4, 8] | None
    # ページ数を数える範囲
    page_count_scope: Literal["episode", "volume"]

    @model_validator(mode="after")
    def _all_modes(self):
        missing = {"bilevel", "grayscale", "color"} - set(self.dpi_by_color_mode)
        if missing:
            raise ValueError(f"色の種類 {sorted(missing)} の解像度が無い")
        if any(v <= 0 for v in self.dpi_by_color_mode.values()):
            raise ValueError("解像度は正の数")
        return self


class NombrePosition(_Strict):
    """見えるノンブルの置き場。仕上がりの端からの距離（mm）。横は小口側か真ん中。"""

    vertical: Literal["top", "bottom"]
    horizontal: Literal["outer", "center"]
    # 仕上がりの上か下の端から、文字の箱の端まで
    edge_mm: float = Field(ge=0)
    # 小口の端から、文字の箱の端まで（horizontal が outer のとき）
    side_mm: float = Field(ge=0)


class HiddenNombrePosition(_Strict):
    """隠しノンブルの置き場：ノドの近く（綴じると見えなくなる所）。仕上がりの下の端とノドの端からの距離（mm）。"""

    bottom_mm: float = Field(ge=0)
    gutter_mm: float = Field(ge=0)


class NombreSettings(_Strict):
    font_family: str = Field(min_length=1)
    font_size_pt: float = Field(gt=0)
    hidden_font_size_pt: float = Field(gt=0)
    color: Color
    # 範囲の最初のページの番号
    start_number: int
    # 番号を数える範囲：話ごとに数え直すか、巻を通して数えるか
    numbering_scope: Literal["episode", "volume"]
    position: NombrePosition
    hidden_position: HiddenNombrePosition
    # ページの種類ごとに、見せる・隠し（ノドの近くに小さく）・出さない。ページの nombre_display が上書きする
    display_by_kind: dict[PageKind, NombreDisplay]

    @model_validator(mode="after")
    def _all_kinds(self):
        missing = {"cover", "color_page", "body", "blank"} - set(self.display_by_kind)
        if missing:
            raise ValueError(f"ページの種類 {sorted(missing)} のノンブルの出し方が無い")
        return self


class Typesetting(_Strict):
    """写植の組版（v3/psd_writer/text_layout.js）。"""

    # 行と行の間（文字の大きさとの比）
    line_spacing_ratio: float = Field(ge=0)
    # 自動の改行：none（人が入れた改行だけ）・character（禁則を守って字の間で）・phrase（文節の切れ目で。入らない文節は字の間で）
    line_break: Literal["none", "character", "phrase"]
    # 縦中横にする半角の数字の桁数の上限（0 は縦中横にしない）
    tate_chu_yoko_max_digits: int = Field(ge=0, le=4)
    # 「!?」など2字の感嘆符・疑問符を縦中横にするか
    tate_chu_yoko_marks: bool
    # 行の揃え：start（縦書きは天、横書きは左）・center
    align: Literal["start", "center"]


class TextSpan(_Strict):
    """文字の一部の書式（何文字目から何文字目の手前まで）。番号はルビと同じ数え方（改行も1字）。"""

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    font_family: str | None = None
    # 文字の大きさとの比
    size_ratio: float | None = Field(default=None, gt=0)
    # 太らせる線の太さ（文字の大きさとの比）。書体に太字が無いときに使う
    embolden_ratio: float | None = Field(default=None, gt=0)
    color: Color | None = None

    @model_validator(mode="after")
    def _something(self):
        if self.font_family is None and self.size_ratio is None and self.embolden_ratio is None and self.color is None:
            raise ValueError("書式が1つも無い")
        return self


def check_spans(text: str, spans: list[dict] | None) -> None:
    if not spans:
        return
    rng = sorted((s["start"], s["end"]) for s in spans)
    n = len(text)
    for s, e in rng:
        if e <= s or e > n:
            raise ValueError(f"書式の範囲 {s}〜{e} が文字（{n}文字）の外か、空")
    for (_, e0), (s1, _) in zip(rng, rng[1:]):
        if s1 < e0:
            raise ValueError("書式の範囲が重なっている")
