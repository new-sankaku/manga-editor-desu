"""画像生成の処理に渡すマスクと絵を、依頼を受けるときに描く（numpy と Pillow だけ。ComfyUI の側では読んで使うだけ）。

- 描き直す範囲のマスク：広げる（grow）→ ぼかす（feather。外側へだけ）→ 人の手の範囲を引く。人の手の範囲は最後に引くので、
  ぼかしで人の範囲へにじむことは無い（ComfyUI の側でも最後に元の画素で貼り戻す。comfy_graphs/source_and_masks.py）。
  ここまでの物を、描いた絵を重ねるときのなじませるマスクにし、白黒にした物（binarize）を描くときのマスクにする
- 描き足す：元の絵を広げた分の真ん中に置き、外側を埋める（周りの色を流し込む・端を伸ばす・折り返す・灰色）。広げた所のマスクは、
  広げた辺から内側へぼかしの幅だけ 1→0 へ下げる。人の手の範囲は広げた絵の上の位置へずらす
- 囲んだ所だけ大きくして直す：マスクの白い所を囲む四角に余白を足し、絵の内側に収めた切り出しの四角を決める

マスクの絵は白黒の RGB（赤のチャンネルを読む。ai-verification.md 1.1 の原因B）。
"""
from __future__ import annotations

import io
from typing import Literal

import numpy as np
from PIL import Image, ImageFilter

from v3server.v3_error_types import Invalid

Fill = Literal["diffuse", "edge", "mirror", "gray"]
GRAY = 128


def to_array(data: bytes, size: tuple[int, int] | None = None) -> np.ndarray:
    """マスクの PNG を 0〜1 の float 配列（高さ×幅）にする。size があれば大きさを確かめる。"""
    im = Image.open(io.BytesIO(data))
    if size is not None and im.size != size:
        raise Invalid(f"マスクの大きさ {im.size[0]}x{im.size[1]} が元の絵 {size[0]}x{size[1]} と違う")
    if im.mode in ("RGBA", "LA"):
        # 透明な所は塗っていない所とみなす（画面のマスクは透明の上に塗る）
        rgba = im.convert("RGBA")
        a = np.asarray(rgba.getchannel("A"), dtype=np.float32) / 255
        r = np.asarray(rgba.getchannel("R"), dtype=np.float32) / 255
        return r * a
    return np.asarray(im.convert("RGB").getchannel("R"), dtype=np.float32) / 255


def to_png(mask: np.ndarray) -> bytes:
    v = np.clip(np.rint(mask * 255), 0, 255).astype(np.uint8)
    im = Image.fromarray(v, mode="L").convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _max_1d(a: np.ndarray, radius: int, axis: int) -> np.ndarray:
    """幅 2*radius+1 の窓の最大（1つの軸）。窓を倍々に広げるので、手数は半径の対数。"""
    if radius <= 0:
        return a
    n = a.shape[axis]
    width = 2 * radius + 1

    def shift(x: np.ndarray, k: int) -> np.ndarray:
        # x[i] ← x[i + k]（はみ出しは 0）
        out = np.zeros_like(x)
        if k < n:
            src = [slice(None)] * x.ndim
            dst = [slice(None)] * x.ndim
            src[axis], dst[axis] = slice(k, None), slice(0, n - k)
            out[tuple(dst)] = x[tuple(src)]
        return out

    pad = [(0, 0)] * a.ndim
    pad[axis] = (radius, radius)
    m = np.pad(a, pad)
    n = m.shape[axis]
    covered = 1
    while covered * 2 <= width:
        m = np.maximum(m, shift(m, covered))
        covered *= 2
    if covered < width:
        m = np.maximum(m, shift(m, width - covered))
    sl = [slice(None)] * a.ndim
    sl[axis] = slice(0, a.shape[axis])
    return m[tuple(sl)]


def grow(mask: np.ndarray, px: int) -> np.ndarray:
    """白い所を px だけ広げる（正方形の窓）。0 なら変えない。"""
    if px < 0:
        raise Invalid("広げる量は0以上")
    return _max_1d(_max_1d(mask, px, 0), px, 1)


def feather(mask: np.ndarray, px: int) -> np.ndarray:
    """境目の外側へ px の幅で 1→0 に下げる。範囲の中はちょうど 1 のまま（0.99 のような値を作らない。
    マスクの値が 1 に届かないと描き直しが効かないことがある。調査 2.1 の Stabilize Mask と同じ問題）。
    ガウスぼかし（半径 px/2）の 0.5 以上を 1 にし、0.5 未満を 2 倍する。0 なら変えない。"""
    if px < 0:
        raise Invalid("ぼかしの幅は0以上")
    if px == 0:
        return mask
    im = Image.fromarray(np.clip(np.rint(mask * 255), 0, 255).astype(np.uint8), mode="L")
    blurred = np.asarray(im.filter(ImageFilter.GaussianBlur(px / 2)), dtype=np.float32) / 255
    return np.where(mask >= 0.5, 1.0, np.clip(blurred * 2, 0, 1)).astype(np.float32)


def redraw_mask(mask: np.ndarray, protected: np.ndarray, grow_px: int, feather_px: int) -> np.ndarray:
    """描き直す範囲（広げる→ぼかす→人の手の範囲を引く）。"""
    out = feather(grow((mask >= 0.5).astype(np.float32), grow_px), feather_px)
    return np.where(protected >= 0.5, 0.0, out).astype(np.float32)


def binarize(mask: np.ndarray) -> np.ndarray:
    """0.5 以上を 1、ほかを 0 にする（描くときのマスク。値が 1 に届かない所を作らない）。"""
    return (mask >= 0.5).astype(np.float32)


def invert(mask: np.ndarray) -> np.ndarray:
    return (1.0 - mask).astype(np.float32)


def crop_box(mask: np.ndarray, padding_px: int) -> tuple[int, int, int, int]:
    """マスクの白い所を囲む四角に余白を足して、絵の内側に収めた (x, y, 幅, 高さ)。白い所が無ければ断る。"""
    ys, xs = np.nonzero(mask > 0)
    if len(xs) == 0:
        raise Invalid("描き直す範囲が空（人の手の範囲を引いた後に何も残っていない）")
    h, w = mask.shape
    x0, y0 = max(0, int(xs.min()) - padding_px), max(0, int(ys.min()) - padding_px)
    x1, y1 = min(w, int(xs.max()) + 1 + padding_px), min(h, int(ys.max()) + 1 + padding_px)
    return x0, y0, x1 - x0, y1 - y0


def _down(a: np.ndarray) -> np.ndarray:
    """2×2 の和で半分の大きさにする（奇数の辺は 0 で足す）。"""
    h, w = a.shape[:2]
    a = np.pad(a, ((0, h % 2), (0, w % 2)) + ((0, 0),) * (a.ndim - 2))
    return a.reshape(a.shape[0] // 2, 2, a.shape[1] // 2, 2, *a.shape[2:]).sum(axis=(1, 3))


def _up(a: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """bilinear で (幅, 高さ) へ広げる。"""
    chans = [np.asarray(Image.fromarray(a[..., c].astype(np.float32), mode="F").resize(size, Image.BILINEAR))
             for c in range(a.shape[2])]
    return np.stack(chans, axis=2)


def diffuse_fill(a: np.ndarray, known: np.ndarray) -> np.ndarray:
    """known の外を、周りの色を流し込んで埋める（push-pull。半分ずつ縮めて色の平均を作り、広げ直して空いた所に入れる）。
    調査の「余白を先に埋める（LaMa、または色を流し込む）」の後の方。known の所は元の画素のまま。"""
    w = known.astype(np.float32)
    levels = [(a.astype(np.float32) * w[..., None], w)]
    while max(levels[-1][1].shape) > 1:
        c, ww = levels[-1]
        levels.append((_down(c), _down(ww)))
    c, ww = levels[-1]
    filled = c / np.maximum(ww, 1e-6)[..., None]
    for c, ww in reversed(levels[:-1]):
        up = _up(filled, (ww.shape[1], ww.shape[0]))
        own = c / np.maximum(ww, 1e-6)[..., None]
        k = np.clip(ww, 0, 1)[..., None]
        filled = own * k + up * (1 - k)
    out = np.where(known[..., None], a.astype(np.float32), filled)
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def pad_image(data: bytes, left: int, top: int, right: int, bottom: int, fill: Fill) -> bytes:
    """元の絵の外側を広げる。埋め方は周りの色を流し込む（diffuse）・端を伸ばす（edge）・折り返す（mirror）・灰色（gray）。"""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    a = np.asarray(im)
    widths = ((top, bottom), (left, right), (0, 0))
    if fill == "diffuse":
        known = np.pad(np.ones(a.shape[:2], bool), widths[:2], constant_values=False)
        out = diffuse_fill(np.pad(a, widths), known)
    elif fill == "edge":
        out = np.pad(a, widths, mode="edge")
    elif fill == "mirror":
        out = np.pad(a, widths, mode="symmetric")
    else:
        out = np.pad(a, widths, mode="constant", constant_values=GRAY)
    buf = io.BytesIO()
    Image.fromarray(out, mode="RGB").save(buf, format="PNG")
    return buf.getvalue()


def extend_mask(width: int, height: int, left: int, top: int, right: int, bottom: int,
                feather_px: int) -> np.ndarray:
    """描き足すときの範囲。広げた所は 1、元の絵の中は、広げた辺からの距離が feather_px まで 1→0 へ下げる。"""
    W, H = width + left + right, height + top + bottom
    m = np.ones((H, W), dtype=np.float32)
    inner = np.zeros((height, width), dtype=np.float32)
    if feather_px > 0:
        xs = np.arange(width, dtype=np.float32)[None, :]
        ys = np.arange(height, dtype=np.float32)[:, None]
        d = np.full((height, width), np.inf, dtype=np.float32)
        if left > 0:
            d = np.minimum(d, xs + 0.5)
        if right > 0:
            d = np.minimum(d, width - xs - 0.5)
        if top > 0:
            d = np.minimum(d, ys + 0.5)
        if bottom > 0:
            d = np.minimum(d, height - ys - 0.5)
        inner = np.clip(1 - d / feather_px, 0, 1).astype(np.float32)
    m[top:top + height, left:left + width] = inner
    return m


def shift_into(mask: np.ndarray, left: int, top: int, right: int, bottom: int) -> np.ndarray:
    """元の絵の上のマスクを、広げた絵の上の位置へ移す（外側は 0）。"""
    return np.pad(mask, ((top, bottom), (left, right)), mode="constant", constant_values=0).astype(np.float32)
