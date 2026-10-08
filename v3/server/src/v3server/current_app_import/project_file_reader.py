"""今のアプリ（ブラウザだけで動く版）が保存したプロジェクトのファイルを読む。

ファイルの形（js/core/compression/lz4.js の buffersToLz4Blob と、js/project-management.js の保存）
- 入れ物：先頭4バイト（リトルエンディアンの32ビット）が見出しの長さ。見出しは JSON の [{"name","size"}...]。
  その後ろが LZ4 フレームで縮めた中身で、ほどくと見出しの順に size バイトずつ並ぶ
- プロジェクトの保存（メニューの「プロジェクトを保存」）は、ページごとの入れ物（lz4_part_N.lz4）を、もう1つの入れ物で包む
- ページの入れ物の中身（js/core/compression/project-compression.js）
  - state_000000.json…：取り消しの記録。最後の番号が今の姿。中身は fabric.js のキャンバスの JSON を、もう1回 JSON の文字にしたもの
  - <sha256>.img：絵の data URL の文字。フキダシの格子（speechBubbleGrid）の JSON も同じ形で入る
  - canvas_info.json：キャンバスの画素の大きさと、ページの mm の大きさ
  - text2img_basePrompt.json：プロジェクトの基本のプロンプト
  - fonts.json・reference_sheets.json：利用者の書体・参照の絵
  - preview-image.jpeg：一覧に出す小さな絵（中身から作り直せる）

1ページだけの入れ物（ページの一覧で1枚を保存したもの）も受ける。外側の入れ物に state_ が無く lz4_part_ だけがあれば
プロジェクト、state_ があれば1ページとして読む。どちらでもなければ止める。
古い zip の形（js/core/compression/project-compression.js の loadZip）は読まない（未対応。止める）。
"""

import base64
import binascii
import json
import struct
from dataclasses import dataclass, field
from typing import Any

import lz4.frame


class ProjectFileError(ValueError):
    pass


@dataclass
class CurrentAppPage:
    # ファイルの中の何番目のページか（0から）
    index: int
    # fabric.js のキャンバスの JSON（最後の状態）
    canvas: dict[str, Any]
    canvas_width_px: float
    canvas_height_px: float
    page_width_mm: float
    page_height_mm: float
    # 名前（拡張子なし）→ 中身の文字（data URL か JSON）
    stored_values: dict[str, str]
    base_prompt: dict[str, Any]
    fonts: list[Any]
    reference_sheets: list[Any]
    # 取り消しの記録の数（今の姿を除く）
    history_count: int
    # 中身に入っていたが、読む対象でないファイルの名前
    other_files: list[str] = field(default_factory=list)


@dataclass
class CurrentAppProject:
    pages: list[CurrentAppPage]
    # 1ページだけのファイルか
    single_page: bool


def unpack_container(data: bytes) -> list[tuple[str, bytes]]:
    """入れ物を (名前, 中身) の並びにほどく。"""
    if len(data) < 4:
        raise ProjectFileError("ファイルが短すぎる（今のアプリのプロジェクトではない）")
    (header_size,) = struct.unpack("<I", data[:4])
    if header_size <= 0 or header_size > len(data) - 4:
        raise ProjectFileError("見出しの長さが正しくない（今のアプリのプロジェクトではない）")
    try:
        header = json.loads(data[4:4 + header_size].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProjectFileError(f"見出しを読めない: {e}") from e
    if not isinstance(header, list) or not all(isinstance(h, dict) and "name" in h and "size" in h for h in header):
        raise ProjectFileError("見出しの形が正しくない")
    try:
        body = lz4.frame.decompress(data[4 + header_size:])
    except RuntimeError as e:
        raise ProjectFileError(f"LZ4 の中身をほどけない: {e}") from e
    if sum(h["size"] for h in header) != len(body):
        raise ProjectFileError("見出しの大きさの合計と、ほどいた中身の大きさが合わない")
    out, offset = [], 0
    for h in header:
        out.append((str(h["name"]), body[offset:offset + h["size"]]))
        offset += h["size"]
    return out


def _json_file(files: dict[str, bytes], name: str, required: bool) -> Any:
    if name not in files:
        if required:
            raise ProjectFileError(f"ページの中に {name} が無い")
        return None
    return json.loads(files[name].decode("utf-8"))


def read_page(index: int, entries: list[tuple[str, bytes]]) -> CurrentAppPage:
    files = dict(entries)
    states = sorted(n for n in files if n.startswith("state_") and n.endswith(".json"))
    if not states:
        raise ProjectFileError(f"{index + 1}ページ目に state_*.json が無い")
    state = json.loads(files[states[-1]].decode("utf-8"))
    # 保存は JSON の文字をもう1回 JSON にしている（js/layer/image-history-management.js の captureState）
    if isinstance(state, str):
        state = json.loads(state)
    if not isinstance(state, dict) or not isinstance(state.get("objects"), list):
        raise ProjectFileError(f"{index + 1}ページ目の {states[-1]} が fabric.js のキャンバスの形でない")
    info = _json_file(files, "canvas_info.json", required=True)
    for k in ("width", "height", "pageWidthMm", "pageHeightMm"):
        if not isinstance(info.get(k), (int, float)) or info[k] <= 0:
            raise ProjectFileError(f"{index + 1}ページ目の canvas_info.json に {k} が無い")
    stored = {n[:-4]: files[n].decode("utf-8") for n in files if n.endswith(".img")}
    known = set(states) | {n for n in files if n.endswith(".img")} | {
        "canvas_info.json", "text2img_basePrompt.json", "fonts.json", "reference_sheets.json", "preview-image.jpeg"}
    return CurrentAppPage(
        index=index, canvas=state, canvas_width_px=float(info["width"]), canvas_height_px=float(info["height"]),
        page_width_mm=float(info["pageWidthMm"]), page_height_mm=float(info["pageHeightMm"]), stored_values=stored,
        base_prompt=_json_file(files, "text2img_basePrompt.json", required=False) or {},
        fonts=_json_file(files, "fonts.json", required=False) or [],
        reference_sheets=_json_file(files, "reference_sheets.json", required=False) or [],
        history_count=len(states) - 1, other_files=sorted(n for n in files if n not in known))


def read_project_file(data: bytes) -> CurrentAppProject:
    outer = unpack_container(data)
    names = [n for n, _ in outer]
    if any(n.startswith("state_") for n in names):
        return CurrentAppProject(pages=[read_page(0, outer)], single_page=True)
    if names and all(n.startswith("lz4_part_") for n in names):
        # 並びは保存した時のページの順（js/project-management.js が btmProjectsMap の順に包む）
        return CurrentAppProject(pages=[read_page(i, unpack_container(part)) for i, (_, part) in enumerate(outer)],
                                 single_page=False)
    raise ProjectFileError(f"今のアプリのプロジェクトの中身でない: {names[:5]}")


def data_url_bytes(value: str) -> bytes:
    """.img に入っている data URL（data:image/png;base64,...）の中身。base64 でない data URL は読まない（止める）。"""
    head, sep, body = value.partition(",")
    if not sep or not head.startswith("data:") or not head.endswith(";base64"):
        raise ProjectFileError(f"絵が base64 の data URL でない: {value[:40]}")
    try:
        return base64.b64decode(body, validate=True)
    except binascii.Error as e:
        raise ProjectFileError(f"絵の base64 を読めない: {e}") from e
