"""MangaImport v1（llm_doc/Manga2Manga計画.md「中間フォーマット MangaImport v1」）を、ネームの形（NamePage）に読む。

MangaImport は、既存の漫画や人が描いたネームの絵を外の解析（manga-analyzer。MagiV2 などはこのリポジトリに持ち込まない）にかけた結果。
座標はページ画像の 0〜1 の値なので、ページ画像が仕上がりの範囲か、塗り足しまで含む範囲かを呼ぶ側が決めて渡す（推し量らない）。

読むもの
- コマの枠（points の多角形）→ PanelFrame（基本枠の座標・mm）。is_bleed → 断ち切り
- コマの形：bleed → 断ち切り。normal → 軸に沿った四角なら「四角」、そうでなければ「斜め」。inferred（解析が推定したコマ）→ 未定
- 読む順（reading_order）→ コマの番号の順
- 吹き出し：文字（OCR の実測）・箱・話者（分かれば）。種類は下の対応表だけ読み、ほかは未定
読まないもの（未定のまま。推し量らない）
- 大きさ（大・中・小）・写す範囲・角度・人物・背景・場面・起承転結・ヒキ・中身・段の割り・擬音
落とすもの（元の文書は案に丸ごと残す）
- excluded のセリフ、どのコマにも属さないセリフ。dropped に理由と一緒に返す
"""
from dataclasses import dataclass, field
from typing import Any, Literal

from v3server.name_structure.name_draft_schema import (
    Balloon,
    NamePage,
    NamePanel,
    PanelFrame,
)
from v3server.name_structure.reading_direction import PageSpec

ImageCovers = Literal["trim", "trim_with_bleed"]

# bubble_type → 吹き出しの種類。対応が決まっているものだけ（whisper・inverted・none は種類を決めない）
BUBBLE_KIND = {"normal": "台詞", "shout": "叫び", "monologue": "心の声", "narration": "ナレーション"}


class MangaImportError(ValueError):
    """MangaImport の形が崩れている。"""


@dataclass
class ReadResult:
    pages: list[NamePage]
    dropped: list[dict[str, Any]] = field(default_factory=list)


def _to_mm(spec: PageSpec, covers: ImageCovers):
    ox, oy = spec.frame_origin_in_trim()
    if covers == "trim":
        w, h, shift = spec.trim_width_mm, spec.trim_height_mm, 0.0
    else:
        w, h, shift = spec.trim_width_mm + 2 * spec.bleed_mm, spec.trim_height_mm + 2 * spec.bleed_mm, spec.bleed_mm

    def conv(x: float, y: float) -> tuple[float, float]:
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise MangaImportError(f"座標が 0〜1 の外: {(x, y)}")
        return (x * w - shift - ox, y * h - shift - oy)
    return conv


def _is_axis_rect(points: list[tuple[float, float]]) -> bool:
    if len(points) != 4:
        return False
    xs, ys = {round(p[0], 9) for p in points}, {round(p[1], 9) for p in points}
    return len(xs) == 2 and len(ys) == 2


def _shape(panel: dict[str, Any], points: list[tuple[float, float]]) -> str | None:
    kind = panel.get("shape")
    if panel.get("is_bleed") or kind == "bleed":
        return "断ち切り"
    if kind == "normal":
        return "四角" if _is_axis_rect(points) else "斜め"
    if kind == "inferred":
        return None
    raise MangaImportError(f"知らないコマの形: {kind!r}")


def read_manga_import(doc: dict[str, Any], spec: PageSpec, covers: ImageCovers, first_page_number: int,
                      first_panel_number: int) -> ReadResult:
    if doc.get("format") != "manga-editor-import" or doc.get("version") != 1:
        raise MangaImportError("format=manga-editor-import・version=1 の文書ではない")
    conv = _to_mm(spec, covers)
    result = ReadResult(pages=[])
    n = first_panel_number
    for pi, page in enumerate(sorted(doc.get("pages", []), key=lambda p: p["index"])):
        panels_in = sorted(page.get("panels", []), key=lambda p: p["reading_order"])
        number_of: dict[str, int] = {}
        built: dict[str, dict[str, Any]] = {}
        for p in panels_in:
            pts = [tuple(xy) for xy in p["points"]]
            if len(pts) < 3:
                raise MangaImportError(f"コマ {p.get('id')} の頂点が3つより少ない")
            poly = [conv(x, y) for x, y in pts]
            number_of[p["id"]] = n
            built[p["id"]] = {"n": n, "shape": _shape(p, pts), "frame": PanelFrame(polygon_mm=poly,
                                                                                    bleeds=bool(p.get("is_bleed"))),
                              "balloons": []}
            n += 1
        for b in sorted(page.get("balloons", []), key=lambda b: b["reading_order"]):
            if b.get("excluded"):
                result.dropped.append({"page_index": page["index"], "balloon_id": b.get("id"), "text": b.get("text"),
                                       "reason": f"解析が除外した（{b.get('exclusion_reason')}）"})
                continue
            target = built.get(b.get("panel_id"))
            if target is None:
                result.dropped.append({"page_index": page["index"], "balloon_id": b.get("id"), "text": b.get("text"),
                                       "reason": "どのコマにも属さない"})
                continue
            box = b["bbox"]
            x0, y0 = conv(box["x"], box["y"])
            x1, y1 = conv(box["x"] + box["w"], box["y"] + box["h"])
            target["balloons"].append(Balloon(speaker=b.get("speaker"), kind=BUBBLE_KIND.get(b.get("type")),
                                              text=b["text"], box_mm=(x0, y0, x1, y1)))
        result.pages.append(NamePage(page=first_page_number + pi, spread=False,
                                     panels=[NamePanel(**v) for v in built.values()]))
    if not result.pages:
        raise MangaImportError("ページが無い")
    return result
