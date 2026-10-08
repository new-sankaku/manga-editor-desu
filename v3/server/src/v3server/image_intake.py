"""絵の入口。人が置いた絵・持ち込んだ絵・生成した絵は、全部ここを通って置き場に入る（V3ハーネス設計 12章の「取り込みの入口」と
「生成の出口」）。規制の判定を差し込む場所はここの1か所だけ。

今は判定の手段と閾値が決まっていない（12章「後で決めるもの」）。INTAKE_JUDGES は空で、どの絵にも
「判定していない（not_judged）」を記録する。通したことにはしない。手段を決めたら INTAKE_JUDGES に足す。
止めた絵も消さない（方針10）。置き場には置き、記録を残し、登録（RegisterImage）を断る。
判定の記録は作品データではないので、操作の窓口を通さず、その場で確定する（呼び出しの記録と同じ扱い）。

生成した絵の PNG から、文字の欄（tEXt・iTXt・zTXt）を外してから置く。ComfyUI は既定で指示文と手順（prompt・workflow）を
PNG に書き込むので、そのまま置くと、絵を落とした人・書き出した原稿に指示文が残る。指示と手順は呼び出しの記録（call_logs）と
絵の details に残る。画素は変えない（読み直して同じ画素で書き直す）。"""

import io
import pathlib
import warnings
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import BinaryIO, Literal

from PIL import Image, PngImagePlugin
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.image_file_tables import ImageIntakeScreening
from v3server.image_file_storage import StoredImage, staged_file, store_image_file
from v3server.server_settings import get_settings
from v3server.v3_error_types import Invalid

IntakeEntry = Literal["human_upload", "generated"]


@dataclass(frozen=True)
class JudgeVerdict:
    blocked: bool
    detail: str


# (手段の名前, 判定する関数)。関数は (絵の中身, 作品の id, 入口) を受け取る
# （判定の手段を足すと、絵を1回メモリに読む。手段が決まったら、ファイルの住所で渡す形を考える）
IntakeJudge = Callable[[bytes, str, IntakeEntry], Awaitable[JudgeVerdict]]
INTAKE_JUDGES: list[tuple[str, IntakeJudge]] = []

NOT_JUDGED_DETAIL = "規制の判定の手段がまだ決まっていない（V3ハーネス設計 12章）。判定していない"


# PNG に残してよい欄（色と解像度。文字の欄は外す）
_PNG_KEEP = ("dpi", "gamma", "icc_profile", "transparency", "srgb", "chromaticity")


def strip_png_text(data: bytes) -> bytes:
    """PNG の文字の欄を外した中身。PNG でなければそのまま返す。文字の欄が無ければ中身を変えない。"""
    with Image.open(io.BytesIO(data)) as im:
        if im.format != "PNG":
            return data
        im.load()
        if not getattr(im, "text", None):
            return data
        keep = {k: im.info[k] for k in _PNG_KEEP if k in im.info and k != "srgb"}
        buf = io.BytesIO()
        im.save(buf, format="PNG", pnginfo=PngImagePlugin.PngInfo(), **keep)
        return buf.getvalue()


def check_pixel_count(path: pathlib.Path) -> None:
    """画素数の上限（V3_IMAGE_MAX_PIXELS）を、画素を展開する前に確かめる（展開すると膨らむ絵で、メモリを食い潰さないため）。

    Pillow は Image.MAX_IMAGE_PIXELS を超えると警告、その2倍で止める（DecompressionBombWarning・DecompressionBombError）。
    ここでは警告も止めとして扱う。上限が Pillow の値より大きい設定は、後で絵を開く所（縮小画像・書き出し）で警告が出るので断る。"""
    limit = get_settings().image_max_pixels
    if Image.MAX_IMAGE_PIXELS is not None and limit > Image.MAX_IMAGE_PIXELS:
        raise RuntimeError(f"V3_IMAGE_MAX_PIXELS（{limit}）が Pillow の上限 Image.MAX_IMAGE_PIXELS"
                           f"（{Image.MAX_IMAGE_PIXELS}）より大きい")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as im:
                width, height = im.size
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise Invalid(f"絵の画素が多すぎる: {e}") from e
    except Exception as e:
        raise Invalid(f"絵として読めない: {e}") from e
    if width * height > limit:
        raise Invalid(f"絵の画素が多すぎる: {width}×{height}（上限 {limit} 画素。V3_IMAGE_MAX_PIXELS）")


async def take_in_image(session: AsyncSession, work_id: str, data: bytes, entry: IntakeEntry, *,
                        commit: bool = True) -> StoredImage:
    """手元にある中身（生成した絵・PSD から取った層など）を入口に通す。"""
    with staged_file(data) as path:
        check_pixel_count(path)
        if entry == "generated":
            stripped = strip_png_text(data)
            if stripped is not data:
                path.write_bytes(stripped)
        return await _take_in_staged(session, work_id, path, entry, commit)


async def take_in_upload(session: AsyncSession, work_id: str, upload: BinaryIO, *, commit: bool = True) -> StoredImage:
    """人が上げたファイルを、丸ごとメモリに読まずに一時ファイルへ写してから入口に通す。
    権限は呼ぶ側が先に確かめる（ファイルを書く前に。点検5 3-2）。"""
    with staged_file(upload) as path:
        check_pixel_count(path)
        return await _take_in_staged(session, work_id, path, "human_upload", commit)


async def _take_in_staged(session: AsyncSession, work_id: str, path: pathlib.Path, entry: IntakeEntry,
                          commit: bool) -> StoredImage:
    """絵を確かめて置き場に置き、判定を記録する。止めたときは記録を足して（commit なら確定して）から Invalid にする。
    commit=False のときは確定を呼ぶ側に任せる（生成の答えを残すのと同じ確定に入れるため）。"""
    rows = []
    data = path.read_bytes() if INTAKE_JUDGES else None
    stored = store_image_file(path)
    if not INTAKE_JUDGES:
        rows.append(ImageIntakeScreening(work_id=work_id, sha256=stored.sha256, entry=entry, status="not_judged",
                                         judge=None, detail=NOT_JUDGED_DETAIL))
    for name, judge in INTAKE_JUDGES:
        verdict = await judge(data, work_id, entry)
        rows.append(ImageIntakeScreening(work_id=work_id, sha256=stored.sha256, entry=entry,
                                         status="blocked" if verdict.blocked else "passed", judge=name,
                                         detail=verdict.detail))
    session.add_all(rows)
    if commit:
        await session.commit()
    blocked = [r for r in rows if r.status == "blocked"]
    if blocked:
        raise Invalid(f"入口の判定で止めた（{blocked[0].judge}）: {blocked[0].detail}")
    return stored
