"""原稿の上の物の見た目の形。人が画面で決めても、AIが決めても、書き出しが読んでも同じ形（V3細部の決めごと 10.1・10.4）。

- 仕上げ（白黒化・明るさ・ぼかし・重ね方）：Adjustment の並び。並んだ順に当てる。消さずに外せる（元の絵は変えない）
- 文字の飾り：TextDecoration（今のアプリ js/sidebar/text/text-decor-presets.js の値の形に合わせた。寸法は文字の大きさとの比）
- ルビ：Ruby（文字の何文字目から何文字目に付けるか）
- フキダシの形：BalloonShape（型の名前と、外形の多角形。自分で描いた形は型の名前が無い）
- 枠の線と塗り：FrameStyle
- トーン・集中線・スピード線：ToneSpec と、貼る所 ToneTarget（コマ・囲む・塗る）
- 図形（絵記号）：ShapeSpec（線・塗り・影）
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Color = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
Polygon = Annotated[list[tuple[float, float]], Field(min_length=3)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- 仕上げ


class Monochrome(_Strict):
    kind: Literal["monochrome"]
    # 2値にするときの境（0〜255）。無ければ灰色の濃淡にする
    threshold: int | None = Field(default=None, ge=0, le=255)


class Brightness(_Strict):
    kind: Literal["brightness"]
    # -1（真っ黒）〜 0（そのまま）〜 1（真っ白）
    amount: float = Field(ge=-1, le=1)


class Blur(_Strict):
    kind: Literal["blur"]
    # ぼかしの半径（mm。書き出しの解像度で画素に直す）
    radius_mm: float = Field(gt=0)


BlendMode = Literal["normal", "multiply", "screen", "overlay", "darken", "lighten"]


class Blend(_Strict):
    kind: Literal["blend"]
    mode: BlendMode


Adjustment = Annotated[Monochrome | Brightness | Blur | Blend, Field(discriminator="kind")]


class Adjustments(_Strict):
    items: list[Adjustment]

    @model_validator(mode="after")
    def _one_blend(self):
        if sum(1 for a in self.items if a.kind == "blend") > 1:
            raise ValueError("重ね方は1つだけ")
        return self


def checked_adjustments(items: list[dict]) -> list[dict]:
    """仕上げの並びを確かめて JSON の形にする（層・文字・コマ・図形・トーンで同じ）。"""
    from v3server.v3_error_types import Invalid

    try:
        return Adjustments.model_validate({"items": items}).model_dump(mode="json")["items"]
    except ValueError as e:
        raise Invalid(f"仕上げの値が正しくない: {e}") from e


def blend_mode_of(adjustments: list[dict]) -> str:
    for a in adjustments:
        if a["kind"] == "blend":
            return a["mode"]
    return "normal"


# ---------------------------------------------------------------- 文字


class Edge(_Strict):
    color: Color
    # 文字の外側に出す幅（文字の大きさとの比）
    ratio: float = Field(gt=0)


class Glow(_Strict):
    color: Color
    ratio: float = Field(gt=0)
    blur_ratio: float = Field(default=0, ge=0)


class Shadow(_Strict):
    color: Color
    opacity: float = Field(ge=0, le=1)
    # ずれ（文字の大きさとの比。右下へ）
    ratio: float = Field(ge=0)
    blur_ratio: float = Field(default=0, ge=0)


class Ghost(_Strict):
    """同じ文字をずらして重ねる（色ずれ・ベタ影）。"""
    color: Color
    dx_ratio: float
    dy_ratio: float
    ratio: float = Field(ge=0)
    opacity: float = Field(default=1, ge=0, le=1)
    blur_ratio: float = Field(default=0, ge=0)


class Band(_Strict):
    """文字の後ろの帯。"""
    color: Color
    opacity: float = Field(ge=0, le=1)


class TextDecoration(_Strict):
    # 今のアプリの飾りの型の名前（plain・standard など）。値は下の項目に展開して持つ（型の値が後で変わっても見た目が変わらない）
    preset: str | None = None
    fill: Color | None = None
    edge: Edge | None = None
    glow: Glow | None = None
    shadow: Shadow | None = None
    ghosts: list[Ghost] = Field(default_factory=list)
    band: Band | None = None
    # 字間（文字の大きさとの比）
    spacing_ratio: float = 0


class Ruby(_Strict):
    # 親の文字の範囲（文字の何文字目から、何文字目の手前まで）
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)


def check_ruby(text: str, ruby: list[dict] | None) -> None:
    if not ruby:
        return
    spans = sorted((r["start"], r["end"]) for r in ruby)
    for s, e in spans:
        if e <= s or e > len(text):
            raise ValueError(f"ルビの範囲 {s}〜{e} が文字（{len(text)}文字）の外か、空")
    for (_, e0), (s1, _) in zip(spans, spans[1:], strict=False):
        if s1 < e0:
            raise ValueError("ルビの範囲が重なっている")


class BalloonShape(_Strict):
    # none はフキダシの線を描かない（文字だけ）
    kind: Literal["preset", "custom", "none"]
    # 型の名前（今のアプリのフキダシの型の名前）。自分で描いた形は無い
    preset: str | None = None
    # 外形（基本枠の座標・mm）。型を選んだときも、画面が型を箱に合わせた外形を入れる（書き出しはこの外形を描く）
    outline_mm: Polygon | None = None
    line_width_mm: float | None = Field(default=None, ge=0)
    line_color: Color | None = None
    fill_color: Color | None = None
    # しっぽ（先は文字の tail_target_mm）。根元の幅と曲がり（しっぽの長さとの比。正は進む向きの左へ、負は右へ膨らむ）。
    # しっぽの先があるのにどちらかが無ければ、書き出しは止める
    tail_base_width_mm: float | None = Field(default=None, gt=0)
    tail_bend_ratio: float | None = Field(default=None, ge=-1, le=1)

    @model_validator(mode="after")
    def _kind(self):
        if self.kind == "none":
            if self.preset or self.outline_mm or self.tail_base_width_mm is not None or self.tail_bend_ratio is not None:
                raise ValueError("線を描かないフキダシには型も外形もしっぽも無い")
            return self
        if self.outline_mm is None:
            raise ValueError("フキダシの外形（outline_mm）が要る")
        if self.kind == "preset" and not self.preset:
            raise ValueError("型のフキダシには型の名前（preset）が要る")
        if self.kind == "custom" and self.preset:
            raise ValueError("自分で描いたフキダシには型の名前が無い")
        return self


# ---------------------------------------------------------------- コマの枠


class FrameStyle(_Strict):
    line_width_mm: float = Field(ge=0)
    line_color: Color
    # 塗り（コマの中の地の色）。無ければ塗らない
    fill_color: Color | None = None
    # 図形のコマのとき、どの形から作ったか（画面で形として直すため）。多角形そのものは frame.polygon_mm
    shape: str | None = None


# ---------------------------------------------------------------- トーン・集中線・スピード線


class ToneTargetPanel(_Strict):
    kind: Literal["panel"]
    panel_id: str


class ToneTargetPolygon(_Strict):
    kind: Literal["polygon"]
    polygon_mm: Polygon


class ToneTargetMask(_Strict):
    """塗って決めた所。白が貼る所の絵（作品の絵として登録したもの）を、box_mm に置く。"""
    kind: Literal["mask"]
    image_id: str


ToneTarget = Annotated[ToneTargetPanel | ToneTargetPolygon | ToneTargetMask, Field(discriminator="kind")]


class ToneSpec(_Strict):
    kind: Literal["dots", "lines", "sand", "gradient", "snow", "focus_lines", "speed_lines"]
    target: ToneTarget
    color: Color = "#000000"
    # 濃さ（0〜1）
    density: float = Field(ge=0, le=1)
    # 線数（網点・線のトーン。1インチの線の数）
    lines_per_inch: float | None = Field(default=None, gt=0)
    # 角度（度）。網点・線・スピード線の向き、グラデの向き
    angle_deg: float = 0
    # 集中線・スピード線の本数
    line_count: int | None = Field(default=None, gt=0)
    # 集中線の中心（基本枠の座標・mm）と、線を描かない真ん中の半径の比（0〜1）
    center_mm: tuple[float, float] | None = None
    inner_ratio: float | None = Field(default=None, ge=0, lt=1)
    # 砂目・雪の粒の大きさ（mm）
    grain_mm: float | None = Field(default=None, gt=0)
    # 絵の乱れを決める種。同じ種なら同じ絵になる
    seed: int | None = None
    # グラデの終わりの濃さ（0〜1）。始まりは density。グラデは網点にする（白黒の原稿で灰色のまま印刷へ行かないように）
    density_end: float | None = Field(default=None, ge=0, le=1)
    # グラデの網点の角度（angle_deg はグラデの向き）と形
    screen_angle_deg: float | None = None
    dot_shape: Literal["round", "line", "square"] | None = None

    @model_validator(mode="after")
    def _needs(self):
        need = {"dots": ("lines_per_inch",), "lines": ("lines_per_inch",), "sand": ("grain_mm", "seed"),
                "gradient": ("lines_per_inch", "density_end", "screen_angle_deg", "dot_shape"),
                "snow": ("grain_mm", "seed"),
                "focus_lines": ("line_count", "center_mm", "inner_ratio", "seed"),
                "speed_lines": ("line_count", "seed")}[self.kind]
        missing = [k for k in need if getattr(self, k) is None]
        if missing:
            raise ValueError(f"{self.kind} には {missing} が要る")
        return self


# ---------------------------------------------------------------- 図形（絵記号）


class ShapeStroke(_Strict):
    color: Color
    width_mm: float = Field(gt=0)


class ShapeFill(_Strict):
    color: Color
    opacity: float = Field(default=1, ge=0, le=1)


class ShapeShadow(_Strict):
    color: Color
    dx_mm: float
    dy_mm: float
    blur_mm: float = Field(default=0, ge=0)
    opacity: float = Field(ge=0, le=1)


class ShapeSpec(_Strict):
    # rect・ellipse は box_mm いっぱいに描く。polygon・path は points_mm。symbol は絵記号（名前と外形）
    kind: Literal["rect", "ellipse", "polygon", "path", "symbol"]
    points_mm: list[tuple[float, float]] | None = None
    # 絵記号の名前（探すときに使う）。外形は points_mm で持つ（画面が絵記号を箱に合わせた外形を入れる）
    symbol_name: str | None = None
    stroke: ShapeStroke | None = None
    fill: ShapeFill | None = None
    shadow: ShapeShadow | None = None

    @model_validator(mode="after")
    def _kind(self):
        if self.kind in ("polygon", "symbol") and (not self.points_mm or len(self.points_mm) < 3):
            raise ValueError(f"{self.kind} には3つ以上の点（points_mm）が要る")
        if self.kind == "path" and (not self.points_mm or len(self.points_mm) < 2):
            raise ValueError("path には2つ以上の点が要る")
        if self.kind == "symbol" and not self.symbol_name:
            raise ValueError("絵記号には名前（symbol_name）が要る")
        if self.kind in ("rect", "ellipse") and self.points_mm:
            raise ValueError(f"{self.kind} は箱いっぱいに描くので点を持たない")
        if self.stroke is None and self.fill is None:
            raise ValueError("線も塗りも無い図形は見えない")
        return self
