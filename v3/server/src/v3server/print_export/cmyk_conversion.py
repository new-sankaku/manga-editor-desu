"""カラーのページを、入稿先の ICC プロファイルで CMYK にする（Pillow の ImageCms。中は LittleCMS）。

- 元の色は sRGB とみなす（ImageCms.createProfile("sRGB")）。画面・生成の絵は RGB で、色の決まりが付いていない絵が多い
- 作った絵には ICC プロファイルを付ける。PDF では img2pdf がそれを ICCBased の色空間にする（試験で確かめた）
- 入稿先のプロファイル（Japan Color など）はサーバーに置かない（配ってよいかは入稿先・配る元の条件による）。
  人が V3_ICC_DIR に置いたファイルを、作品の設定の名前で読む。無ければ止める（RGB のまま黙って出さない）
- 刷った色が合うかは未検証（実機の印刷で確かめていない）。PDF/X の OutputIntent は付けていない
"""
import io
import pathlib
from functools import lru_cache

from PIL import Image, ImageCms

from v3server.name_structure.print_settings import ColorOutput

_INTENTS = {
    "perceptual": ImageCms.Intent.PERCEPTUAL,
    "relative_colorimetric": ImageCms.Intent.RELATIVE_COLORIMETRIC,
    "saturation": ImageCms.Intent.SATURATION,
    "absolute_colorimetric": ImageCms.Intent.ABSOLUTE_COLORIMETRIC,
}


class CmykRefused(ValueError):
    pass


def profile_path(icc_dir: str | None, co: ColorOutput) -> pathlib.Path:
    """プロファイルのファイル。置き場が無い・ファイルが無い・CMYK のプロファイルでないときは止める。"""
    if not icc_dir:
        raise CmykRefused("カラーを CMYK にする設定があるのに、ICC プロファイルのフォルダ（V3_ICC_DIR）が無い")
    path = pathlib.Path(icc_dir) / co.profile
    if not path.is_file():
        raise CmykRefused(f"ICC プロファイル {co.profile} が {icc_dir} に無い")
    _check(str(path), path.stat().st_mtime_ns)
    return path


@lru_cache(maxsize=8)
def _check(path: str, _mtime: int) -> str:
    try:
        prof = ImageCms.getOpenProfile(path)
    except (OSError, ImageCms.PyCMSError) as e:
        raise CmykRefused(f"ICC プロファイル {path} が読めない: {e}") from e
    space = prof.profile.xcolor_space.strip()
    if space != "CMYK":
        raise CmykRefused(f"ICC プロファイル {path} は CMYK でない（{space}）")
    return ImageCms.getProfileDescription(prof).strip()


@lru_cache(maxsize=8)
def _transform(path: str, _mtime: int, intent: str, bpc: bool) -> tuple[ImageCms.ImageCmsTransform, bytes]:
    dst = ImageCms.getOpenProfile(path)
    flags = ImageCms.Flags.BLACKPOINTCOMPENSATION if bpc else ImageCms.Flags.NONE
    t = ImageCms.buildTransform(ImageCms.createProfile("sRGB"), dst, "RGB", "CMYK",
                                renderingIntent=_INTENTS[intent], flags=flags)
    return t, dst.tobytes()


def profile_description(icc_dir: str | None, co: ColorOutput) -> str:
    path = profile_path(icc_dir, co)
    return _check(str(path), path.stat().st_mtime_ns)


def to_cmyk(img: Image.Image, icc_dir: str | None, co: ColorOutput) -> Image.Image:
    """RGB の絵を CMYK に。返す絵の info["icc_profile"] に入稿先のプロファイルを付ける。"""
    if img.mode != "RGB":
        raise CmykRefused(f"CMYK にするのは RGB の絵だけ（{img.mode}）")
    path = profile_path(icc_dir, co)
    t, icc = _transform(str(path), path.stat().st_mtime_ns, co.intent, co.black_point_compensation)
    out = ImageCms.applyTransform(img, t)
    out.info["icc_profile"] = icc
    return out


def cmyk_tiff_bytes(img: Image.Image, dpi: float) -> bytes:
    """PDF に入れるための CMYK の TIFF（Deflate で可逆。プロファイル付き）。"""
    buf = io.BytesIO()
    img.save(buf, format="TIFF", compression="tiff_adobe_deflate", dpi=(dpi, dpi),
             icc_profile=img.info["icc_profile"])
    return buf.getvalue()
