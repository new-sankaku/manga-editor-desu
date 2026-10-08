"""今のアプリのプロジェクト（project_file_reader.py で読んだもの）を、V3 の正本の行の案と、取り込みの報告に直す。

データベースは見ない（計算だけ）。行を書くのは操作 import_current_app_project（operations/current_app_import_operations.py）。

元の物は、どれも報告（ReportEntry）に1行ずつ載る。黙って落とす物は無い。状態は4つ
- mapped：そのまま入れた
- converted：形を変えて入れた（何が変わったかを note に書く）
- unmapped：入れられなかった（理由を note に書く）
- not_needed：中身から作り直せる控えなので入れない（フキダシの文字の箱・一覧の小さな絵・取り消しの記録）

物の見分け方（今のアプリが付ける印による）
- コマ：isPanel が真の polygon・rect
- フキダシ：customType が speechBubbleSVG（線のグループ）・speechBubbleText（文字）・speechBubbleRect（文字の箱の控え）、
  freehandBubblePath・freehandBubbleText・freehandBubbleRect（手で描いたフキダシ）
- 文字：textbox・i-text・text・vertical-textbox
- トーン・効果線：今のアプリが付ける名前（TONE_IMAGE_NAMES・EFFECT_IMAGE_NAMES）の image。人が名前を変えた物は普通の絵になる
- 絵：それ以外の image
- ペンの線：customType の無い path
"""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cmp_to_key
from typing import Any, Literal

from pydantic import BaseModel, Field

from v3server.canonical_tables.table_base import new_id
from v3server.current_app_import.fabric_geometry import (
    GeometryError,
    Point,
    center_of,
    css_color,
    object_matrix,
    object_polygon_px,
    path_rings_px,
    point_in_polygon,
    polygon_area,
    scaled_size,
)
from v3server.current_app_import.project_file_reader import (
    CurrentAppPage,
    CurrentAppProject,
)
from v3server.name_structure.reading_direction import PageSpec
from v3server.panel_layout.panel_frame_editing import reading_first
from v3server.panel_layout.panel_geometry import rect_polygon

Status = Literal["mapped", "converted", "unmapped", "not_needed"]

TONE_IMAGE_NAMES = {"Tone", "Snow Tone", "Tone Noise"}
EFFECT_IMAGE_NAMES = {"Speed Line", "Focus Line"}
TEXT_TYPES = {"textbox", "i-text", "text", "vertical-textbox"}
BALLOON_OUTLINE_TYPES = {"speechBubbleSVG", "freehandBubblePath"}
BALLOON_TEXT_TYPES = {"speechBubbleText", "freehandBubbleText"}
BALLOON_BOX_TYPES = {"speechBubbleRect", "freehandBubbleRect"}
# コマ・絵ごとのAIの設定として持つ項目（js/core/settings.js の commonProperties のうちAIの設定）
SETTING_PREFIXES = ("text2img_", "img2img")
SETTING_KEYS = {"tempPrompt", "tempNegative", "tempSeed"}
# ページの寸法を同じとみなす差（mm）。今のアプリは mm を小数で持つので、丸めの差だけ許す
PAGE_SIZE_TOLERANCE_MM = 0.5
PT_PER_MM = 72 / 25.4


class ReportEntry(BaseModel):
    page_index: int
    # キャンバスの中の何番目の物か。ページ全体の物（書体・参照の絵・取り消しの記録）は無い
    object_index: int | None = None
    source_kind: str
    source_name: str | None = None
    status: Status
    target_table: str | None = None
    target_id: str | None = None
    note: str = ""


class PlannedPage(BaseModel):
    id: str
    source_index: int


class PlannedPanel(BaseModel):
    id: str
    page_id: str
    order: int
    frame: dict[str, Any]
    # 枠の線（name_structure/item_styles.py の FrameStyle）。今のアプリのコマの線から作る。線が無ければ None
    frame_style: dict[str, Any] | None = None


class PlannedImage(BaseModel):
    id: str
    # プロジェクトの中の絵の名前（.img の名前）
    key: str
    page_id: str
    panel_id: str
    role: str
    sha256: str
    media_type: str
    width: int
    height: int
    dpi: int | None = None
    source_note: str


class PlannedPanelImage(BaseModel):
    panel_id: str
    image_id: str
    placement: dict[str, Any]


class PlannedLayer(BaseModel):
    id: str
    panel_id: str
    role: str
    image_id: str
    stack_order: int
    visible: bool
    opacity: float
    placement: dict[str, Any]


class PlannedText(BaseModel):
    id: str
    panel_id: str
    values: dict[str, Any]


class PlannedSetting(BaseModel):
    id: str
    target_kind: Literal["project_base", "panel", "image"]
    page_id: str | None = None
    panel_id: str | None = None
    image_id: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    source_values: dict[str, Any] = Field(default_factory=dict)


class ImportPlan(BaseModel):
    pages: list[PlannedPage] = Field(default_factory=list)
    panels: list[PlannedPanel] = Field(default_factory=list)
    images: list[PlannedImage] = Field(default_factory=list)
    panel_images: list[PlannedPanelImage] = Field(default_factory=list)
    layers: list[PlannedLayer] = Field(default_factory=list)
    texts: list[PlannedText] = Field(default_factory=list)
    settings: list[PlannedSetting] = Field(default_factory=list)
    entries: list[ReportEntry] = Field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {"mapped": 0, "converted": 0, "unmapped": 0, "not_needed": 0}
        for e in self.entries:
            out[e.status] += 1
        out["source_objects"] = sum(1 for e in self.entries if e.object_index is not None)
        out["pages"] = len(self.pages)
        return out


@dataclass
class TakenImage:
    """入口（image_intake.py）を通った絵。止めた絵は blocked に理由を入れる。"""

    sha256: str | None
    media_type: str | None
    width: int | None
    height: int | None
    dpi: int | None
    blocked: str | None = None


@dataclass
class _Ctx:
    page: CurrentAppPage
    spec: PageSpec
    mm_per_px: float
    origin: Point
    direction: Literal["rtl", "ltr"]
    file_name: str

    def mm(self, pts: list[Point]) -> list[tuple[float, float]]:
        ox, oy = self.origin
        return [(round(x * self.mm_per_px - ox, 3), round(y * self.mm_per_px - oy, 3)) for x, y in pts]

    def box_mm(self, obj: dict[str, Any]) -> tuple[list[float], Point]:
        """物の箱（回す前、基本枠の mm）と、真ん中（キャンバスの画素）。回転・反転は置き方（transform）に別に持つ。"""
        cx, cy = center_of(obj)
        w, h = scaled_size(obj)
        (x0, y0), (x1, y1) = self.mm([(cx - w / 2, cy - h / 2), (cx + w / 2, cy + h / 2)])
        return [x0, y0, x1, y1], (cx, cy)


def _transform(obj: dict[str, Any]) -> dict[str, Any]:
    return {"rotation_deg": float(obj.get("angle") or 0.0), "skew_x_deg": float(obj.get("skewX") or 0.0),
            "skew_y_deg": float(obj.get("skewY") or 0.0), "flip_h": bool(obj.get("flipX")),
            "flip_v": bool(obj.get("flipY"))}


def _settings_of(obj: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in obj.items() if k.startswith(SETTING_PREFIXES) or k in SETTING_KEYS}


def _name(obj: dict[str, Any]) -> str | None:
    n = obj.get("name")
    return n if isinstance(n, str) else None


def _cmp_reading(direction):
    def cmp(a: list[Point], b: list[Point]) -> int:
        return -1 if reading_first(a, b, direction) == 0 else 1
    return cmp_to_key(cmp)


def _same_size(page: CurrentAppPage, spec: PageSpec) -> bool:
    return (abs(page.page_width_mm - spec.trim_width_mm) <= PAGE_SIZE_TOLERANCE_MM
            and abs(page.page_height_mm - spec.trim_height_mm) <= PAGE_SIZE_TOLERANCE_MM)


def _decoration_and_notes(obj: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    notes: list[str] = []
    fill = css_color(obj.get("fill"))
    deco = {"fill": fill[0]} if fill else None
    if fill and fill[1] < 1:
        notes.append(f"文字の色の不透明度 {fill[1]} は移していない")
    if (obj.get("strokeWidth") or 0) > 0 and css_color(obj.get("stroke")):
        notes.append(f"文字の縁（{obj.get('stroke')}・太さ {obj.get('strokeWidth')}）は移していない")
    for key in ("textBackgroundColor", "backgroundColor"):
        bg = css_color(obj.get(key))
        if bg and bg[1] > 0:
            notes.append(f"文字の背景色（{obj.get(key)}）は移していない")
    if obj.get("fontWeight") not in (None, "normal", 400, "400"):
        notes.append(f"太さ {obj.get('fontWeight')} は移していない")
    if obj.get("fontStyle") not in (None, "normal"):
        notes.append(f"字の形 {obj.get('fontStyle')} は移していない")
    if obj.get("underline") or obj.get("linethrough") or obj.get("overline"):
        notes.append("下線・取り消し線は移していない")
    if obj.get("styles"):
        notes.append("文字の一部だけの書式（styles）は移していない")
    if obj.get("imageTextType"):
        notes.append(f"画像の文字の効果（{obj.get('imageTextType')}）は移していない")
    return deco, notes


class _PageBuilder:
    def __init__(self, plan: ImportPlan, ctx: _Ctx, page_id: str, images: Mapping[str, TakenImage],
                 origin_note: str):
        self.plan, self.ctx, self.page_id, self.images, self.origin_note = plan, ctx, page_id, images, origin_note
        self.objects: list[dict[str, Any]] = ctx.page.canvas["objects"]
        # 元の番号 → コマの id と外形（画素）
        self.panels: dict[int, tuple[str, list[Point]]] = {}
        self.guid_to_panel: dict[str, str] = {}
        self.balloons: dict[str, dict[str, Any]] = {}

    def entry(self, i: int | None, kind: str, obj: dict[str, Any] | None, status: Status, note: str = "",
              table: str | None = None, target: str | None = None) -> None:
        self.plan.entries.append(ReportEntry(
            page_index=self.ctx.page.index, object_index=i, source_kind=kind,
            source_name=_name(obj) if obj else None, status=status, target_table=table, target_id=target,
            note=note))

    def panel_at(self, p: Point) -> str | None:
        for pid, poly in self.panels.values():
            if point_in_polygon(p, poly):
                return pid
        return None

    # -------------------------------------------------------- コマ
    def add_panels(self) -> None:
        found = []
        for i, obj in enumerate(self.objects):
            if not obj.get("isPanel"):
                continue
            if obj.get("type") not in ("polygon", "rect"):
                self.entry(i, "panel", obj, "unmapped", f"コマの形 {obj.get('type')} は読めない")
                continue
            try:
                poly = object_polygon_px(obj)
            except GeometryError as e:
                self.entry(i, "panel", obj, "unmapped", f"コマの形を読めない: {e}")
                continue
            found.append((i, obj, poly))
        found.sort(key=lambda t: _cmp_reading(self.ctx.direction)(self.ctx.mm(t[2])))
        spec = self.ctx.spec
        for order, (i, obj, poly) in enumerate(found):
            pid = new_id()
            poly_mm = self.ctx.mm(poly)
            bleeds = any(x < -PAGE_SIZE_TOLERANCE_MM or y < -PAGE_SIZE_TOLERANCE_MM
                         or x > spec.frame_width_mm + PAGE_SIZE_TOLERANCE_MM
                         or y > spec.frame_height_mm + PAGE_SIZE_TOLERANCE_MM for x, y in poly_mm)
            notes = ["読む順は位置から決めた（今のアプリは読む順を持たない）"]
            frame_style = None
            line = css_color(obj.get("stroke"))
            width = float(obj.get("strokeWidth") or 0)
            if line and width > 0:
                scale = 1.0 if obj.get("strokeUniform") else (abs(obj.get("scaleX") or 1) + abs(obj.get("scaleY") or 1)) / 2
                frame_style = {"line_width_mm": round(width * scale * self.ctx.mm_per_px, 3), "line_color": line[0]}
                notes.append(f"枠の線（{obj.get('stroke')}・太さ {width}px）を枠の線（frame_style）に入れた")
                if line[1] < 1:
                    notes.append(f"枠の線の不透明度 {line[1]} は移していない（V3 の枠の線は不透明）")
            self.plan.panels.append(PlannedPanel(id=pid, page_id=self.page_id, order=order,
                                                 frame={"polygon_mm": poly_mm, "bleeds": bleeds},
                                                 frame_style=frame_style))
            self.panels[i] = (pid, poly)
            for g in obj.get("guids") or []:
                self.guid_to_panel[g] = pid
            if obj.get("fill") not in (None, "", "transparent", "rgba(255,255,255,0.25)"):
                notes.append(f"コマの塗り {obj.get('fill')} は移していない")
            self.entry(i, "panel", obj, "converted", "。".join(notes), "panels", pid)
            settings = _settings_of(obj)
            if settings:
                sid = new_id()
                self.plan.settings.append(PlannedSetting(
                    id=sid, target_kind="panel", page_id=self.page_id, panel_id=pid,
                    prompt=settings.get("text2img_prompt"), negative_prompt=settings.get("text2img_negative"),
                    source_values=settings))

    # -------------------------------------------------------- フキダシの線
    def collect_balloons(self) -> None:
        for i, obj in enumerate(self.objects):
            if obj.get("customType") not in BALLOON_OUTLINE_TYPES:
                continue
            try:
                if obj.get("type") == "group":
                    gm = object_matrix(obj)
                    rings = []
                    for child in obj.get("objects") or []:
                        if child.get("type") == "path":
                            rings += [(r, child) for r in path_rings_px(child, gm)]
                        elif child.get("type") in ("polygon", "rect", "ellipse", "circle"):
                            rings.append((object_polygon_px(child, gm), child))
                    scale = (gm[0][0] ** 2 + gm[1][0] ** 2) ** 0.5
                else:
                    rings = [(r, obj) for r in path_rings_px(obj)]
                    scale = 1.0
            except GeometryError as e:
                self.entry(i, "balloon_outline", obj, "unmapped", f"フキダシの線を読めない: {e}")
                continue
            rings = [(r, c) for r, c in rings if len(r) >= 3]
            if not rings:
                self.entry(i, "balloon_outline", obj, "unmapped", "フキダシの線に輪が無い")
                continue
            outer, child = max(rings, key=lambda t: polygon_area(t[0]))
            line = css_color(child.get("stroke"))
            fill = css_color(child.get("fill"))
            shape = {"kind": "custom", "outline_mm": self.ctx.mm(outer),
                     "line_width_mm": round(float(child.get("strokeWidth") or 0) * abs(child.get("scaleX") or 1)
                                            * scale * self.ctx.mm_per_px, 3),
                     "line_color": line[0] if line and line[1] > 0 else None,
                     "fill_color": fill[0] if fill and fill[1] > 0 else None}
            notes = ["外形を1つの多角形にした（曲線は点の列に直した）"]
            if len(rings) > 1:
                notes.append(f"ほかの {len(rings) - 1} 本の線（穴・点線・飾り）は移していない")
            if obj.get("speechBubbleGrid"):
                notes.append("フキダシの格子（speechBubbleGrid）は移していない")
            self.balloons[obj.get("guid") or f"#{i}"] = {"index": i, "obj": obj, "shape": shape, "notes": notes,
                                                         "guids": set(obj.get("guids") or [])}

    def balloon_for_text(self, obj: dict[str, Any]) -> dict[str, Any] | None:
        target = obj.get("targetObject") or {}
        for b in self.balloons.values():
            if obj.get("guid") in b["guids"]:
                return b
        for b in self.balloons.values():
            if target.get("left") == b["obj"].get("left") and target.get("top") == b["obj"].get("top"):
                return b
        return None

    # -------------------------------------------------------- 文字
    def add_text(self, i: int, obj: dict[str, Any], orders: dict[tuple[str, str], int]) -> None:
        in_balloon = obj.get("customType") in BALLOON_TEXT_TYPES
        balloon = self.balloon_for_text(obj) if in_balloon else None
        box, center = self.ctx.box_mm(obj)
        panel_id = self.panel_at(center)
        if panel_id is None and balloon is not None:
            panel_id = self.panel_at(center_of(balloon["obj"]))
        kind = "balloon_text" if in_balloon else "text"
        if panel_id is None:
            self.entry(i, kind, obj, "unmapped",
                       "コマの外の文字は V3 で置く所が無い（文字はコマに属する）。文字: " + str(obj.get("text") or ""))
            if balloon is not None:
                balloon["used"] = "unmapped"
            return
        item_kind = "balloon" if in_balloon else "caption"
        deco, notes = _decoration_and_notes(obj)
        values: dict[str, Any] = {
            "item_kind": item_kind, "text": str(obj.get("text") or ""),
            "writing_direction": "vertical" if obj.get("type") == "vertical-textbox" else "horizontal",
            "font_size_pt": round(float(obj.get("fontSize") or 0) * abs(float(obj.get("scaleY") or 1))
                                  * self.ctx.mm_per_px * PT_PER_MM, 2) or None,
            "box_mm": box, "font_family": obj.get("fontFamily") or None, "decoration": deco,
            "transform": _transform(obj), "opacity": float(obj.get("opacity") if obj.get("opacity") is not None else 1)}
        if obj.get("fontFamily"):
            notes.append(f"書体の名前 {obj.get('fontFamily')} をそのまま入れた（書き出しは V3_FONT_DIR に同じ名前の書体が要る）")
        if in_balloon and balloon is not None:
            values["balloon_shape"] = balloon["shape"]
            balloon["used"] = values
        elif in_balloon:
            notes.append("フキダシの線が見つからないので、線の無い文字として入れた")
        else:
            notes.append("フキダシに入っていない文字はナレーションの箱（caption）として入れた。描き文字なら種類を直す")
        key = (panel_id, item_kind)
        values["order"] = orders.get(key, 0)
        orders[key] = values["order"] + 1
        tid = new_id()
        self.plan.texts.append(PlannedText(id=tid, panel_id=panel_id, values=values))
        if balloon is not None:
            balloon["text_id"] = tid
        self.entry(i, kind, obj, "converted" if notes else "mapped", "。".join(notes), "text_items", tid)

    # -------------------------------------------------------- 絵
    def add_image(self, i: int, obj: dict[str, Any], stack: dict[str, int]) -> None:
        name = _name(obj)
        kind = "tone" if name in TONE_IMAGE_NAMES else "effect" if name in EFFECT_IMAGE_NAMES else "image"
        key = obj.get("src")
        taken = self.images.get(key) if isinstance(key, str) else None
        if taken is None:
            self.entry(i, kind, obj, "unmapped", "絵の中身がプロジェクトに無い（.img が無い）")
            return
        if taken.blocked:
            self.entry(i, kind, obj, "unmapped", f"絵を入れられない: {taken.blocked}")
            return
        box, center = self.ctx.box_mm(obj)
        panel_id = self.guid_to_panel.get(obj.get("guid")) or self.panel_at(center)
        if panel_id is None:
            self.entry(i, kind, obj, "unmapped", "コマの外の絵は V3 で置く所が無い（層はコマに属する）")
            return
        cx, cy = int(obj.get("cropX") or 0), int(obj.get("cropY") or 0)
        crop = [cx, cy, cx + round(float(obj["width"])), cy + round(float(obj["height"]))]
        if crop[2] > taken.width or crop[3] > taken.height:
            self.entry(i, kind, obj, "unmapped",
                       f"切り抜き {crop} が絵の大きさ {taken.width}x{taken.height} の外に出ている")
            return
        placement = {"crop_px": crop, "dest_box_mm": box, **_transform(obj)}
        role = {"tone": "tone", "effect": "effect", "image": "panel_art"}[kind]
        iid = new_id()
        self.plan.images.append(PlannedImage(
            id=iid, key=key, page_id=self.page_id, panel_id=panel_id, role=role, sha256=taken.sha256,
            media_type=taken.media_type, width=taken.width, height=taken.height, dpi=taken.dpi,
            source_note=f"今のアプリのプロジェクト {self.ctx.file_name} の {self.ctx.page.index + 1}ページ目の"
                        f" {i + 1}番目の物（{name or obj.get('type')}）。{self.origin_note}"))
        notes = []
        if kind != "image":
            notes.append("トーン・効果線は今のアプリでは絵なので、絵の層として入れた（網点の値には戻せない）")
        if obj.get("filters"):
            notes.append(f"絵の効果（filters: {[f.get('type') for f in obj['filters']]}）は移していない")
        if obj.get("globalCompositeOperation") not in (None, "source-over"):
            notes.append(f"重ね方 {obj.get('globalCompositeOperation')} は移していない")
        opacity = float(obj.get("opacity") if obj.get("opacity") is not None else 1)
        visible = obj.get("visible") is not False
        has_panel_image = any(pi.panel_id == panel_id for pi in self.plan.panel_images)
        if kind == "image" and not has_panel_image and opacity == 1 and visible:
            self.plan.panel_images.append(PlannedPanelImage(panel_id=panel_id, image_id=iid, placement=placement))
            table, target = "panels", panel_id
            notes.append("コマの絵（panels.image_id）として入れた")
        else:
            lid = new_id()
            order = stack.get(panel_id, 0)
            stack[panel_id] = order + 1
            self.plan.layers.append(PlannedLayer(id=lid, panel_id=panel_id, role=role, image_id=iid,
                                                 stack_order=order, visible=visible, opacity=opacity,
                                                 placement=placement))
            table, target = "panel_layers", lid
        self.entry(i, kind, obj, "converted" if notes else "mapped", "。".join(notes), table, target)
        settings = _settings_of(obj)
        if settings:
            self.plan.settings.append(PlannedSetting(
                id=new_id(), target_kind="image", page_id=self.page_id, panel_id=panel_id, image_id=iid,
                prompt=settings.get("text2img_prompt"), negative_prompt=settings.get("text2img_negative"),
                source_values=settings))

    # -------------------------------------------------------- 全体
    def build(self) -> None:
        self.add_panels()
        self.collect_balloons()
        orders: dict[tuple[str, str], int] = {}
        stack: dict[str, int] = {}
        texts = []
        for i, obj in enumerate(self.objects):
            t, ct = obj.get("type"), obj.get("customType")
            if obj.get("isPanel") or ct in BALLOON_OUTLINE_TYPES:
                continue
            if ct in BALLOON_BOX_TYPES:
                self.entry(i, "balloon_text_box", obj, "not_needed", "フキダシの文字の箱の控え。文字の箱から作り直せる")
            elif t in TEXT_TYPES:
                texts.append((i, obj))
            elif t == "image":
                self.add_image(i, obj, stack)
            elif t == "path" and not ct:
                self.entry(i, "pen_stroke", obj, "unmapped",
                           "ペンの線は今は移せない（画素の座標の線を、V3 のペンの線（mm の点の列と筆）に直す所が無い）")
            elif obj.get("isIcon"):
                self.entry(i, "icon", obj, "unmapped", "絵記号（アイコンの SVG）は V3 の図形の形に直せない")
            else:
                self.entry(i, t or "unknown", obj, "unmapped", f"V3 に受ける所が無い物（type={t}, customType={ct}）")
        # 文字は読む順に番号を振る
        boxes = {i: self.ctx.box_mm(o)[0] for i, o in texts}
        cmp = _cmp_reading(self.ctx.direction)
        texts.sort(key=lambda t: cmp(rect_polygon(tuple(boxes[t[0]]))))
        for i, obj in texts:
            self.add_text(i, obj, orders)
        for b in self.balloons.values():
            if "text_id" in b:
                self.entry(b["index"], "balloon_outline", b["obj"], "converted", "。".join(b["notes"]),
                           "text_items", b["text_id"])
            elif b.get("used") == "unmapped":
                self.entry(b["index"], "balloon_outline", b["obj"], "unmapped", "フキダシの文字がコマの外にある")
            else:
                self.entry(b["index"], "balloon_outline", b["obj"], "unmapped", "フキダシに文字が無い（V3 のフキダシは文字に付く）")


def build_import_plan(project: CurrentAppProject, spec: PageSpec, reading_direction: Literal["rtl", "ltr"],
                      images: Mapping[str, TakenImage], file_name: str, origin_note: str) -> ImportPlan:
    """images：プロジェクトの絵の名前 → 入口を通った絵。"""
    plan = ImportPlan()
    base_prompts = [p.base_prompt for p in project.pages if p.base_prompt]
    for page in project.pages:
        pid = new_id()
        plan.pages.append(PlannedPage(id=pid, source_index=page.index))
        ctx = _Ctx(page=page, spec=spec, mm_per_px=page.page_width_mm / page.canvas_width_px,
                   origin=spec.frame_origin_in_trim(), direction=reading_direction, file_name=file_name)
        builder = _PageBuilder(plan, ctx, pid, images, origin_note)
        ratio_gap = abs(page.page_height_mm / page.canvas_height_px - ctx.mm_per_px) / ctx.mm_per_px
        if not _same_size(page, spec) or ratio_gap > 0.01:
            why = (f"ページの寸法 {page.page_width_mm}x{page.page_height_mm}mm が作品の仕上がり "
                   f"{spec.trim_width_mm}x{spec.trim_height_mm}mm と違う" if not _same_size(page, spec)
                   else "キャンバスの縦横の比がページの mm の比と合わない")
            builder.entry(None, "page", None, "converted", why + "。ページだけ作り、中の物は入れていない", "pages", pid)
            for i, obj in enumerate(page.canvas["objects"]):
                builder.entry(i, obj.get("customType") or obj.get("type") or "unknown", obj, "unmapped", why)
        else:
            builder.entry(None, "page", None, "mapped", "", "pages", pid)
            builder.build()
        if page.history_count:
            builder.entry(None, "history", None, "not_needed", f"取り消しの記録 {page.history_count} 件は移さない（最後の姿だけ）")
        if page.fonts:
            builder.entry(None, "fonts", None, "unmapped",
                          f"プロジェクトに入っていた書体 {len(page.fonts)} 個は受ける口が無い（V3 の書体は V3_FONT_DIR に置く）")
        if page.reference_sheets:
            builder.entry(None, "reference_sheets", None, "unmapped",
                          f"参照の絵 {len(page.reference_sheets)} 枚は受ける口が無い（設定資料に人が入れ直す）")
        for name in page.other_files:
            builder.entry(None, "file", None, "unmapped", f"読む対象でないファイル {name}")
    if base_prompts:
        distinct = {repr(sorted(b.items())) for b in base_prompts}
        if len(distinct) == 1:
            b = base_prompts[0]
            plan.settings.append(PlannedSetting(id=new_id(), target_kind="project_base", prompt=b.get("text2img_prompt"),
                                                negative_prompt=b.get("text2img_negative"), source_values=b))
        else:
            for page, planned in zip(project.pages, plan.pages, strict=True):
                if page.base_prompt:
                    b = page.base_prompt
                    plan.settings.append(PlannedSetting(id=new_id(), target_kind="project_base", page_id=planned.id,
                                                        prompt=b.get("text2img_prompt"),
                                                        negative_prompt=b.get("text2img_negative"), source_values=b))
    return plan


def referenced_image_keys(project: CurrentAppProject) -> dict[str, str]:
    """絵の名前 → data URL。キャンバスの image が指している物だけ（フキダシの格子の JSON は入れない）。"""
    out: dict[str, str] = {}
    for page in project.pages:
        for obj in page.canvas["objects"]:
            key = obj.get("src")
            if obj.get("type") == "image" and isinstance(key, str) and key in page.stored_values:
                out[key] = page.stored_values[key]
    return out
