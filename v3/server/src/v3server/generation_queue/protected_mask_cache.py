"""人の手の範囲を重ねたマスクの絵を作る所（1か所）。画面に見せる口（http_routes/image_generation_routes.py）と、
依頼を受けるとき（input_image_preparation.py）の両方がここを使うので、同じ範囲・同じ描き方になる。

消しゴムで消すたびに範囲（画素のマスク）が1つ増える。毎回全部のマスクを読み直して重ねると、範囲の数に比例して遅くなる
（4960×7016 で 20 個 13 秒。llm_doc/V3画像生成の機能と画面.md 6.6）。そこで、範囲の並びの先頭からの部分ごとに
控え（protected_mask_cache）を引き、いちばん長く当たった控えに残りの範囲だけを重ねる。"""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.text_and_layer_tables import ProtectedMaskCache, ProtectedRegion
from v3server.comfy_graphs.protected_region_mask import protected_mask_png
from v3server.image_file_storage import image_exists, read_image, store_image


def _prefix_keys(width: int, height: int, regions: list[ProtectedRegion]) -> list[str]:
    """keys[i] は先頭 i 個の範囲を重ねたマスクの key（i = 0..len）。範囲の中身も入れる（id だけに頼らない）。"""
    h = hashlib.sha256(f"protected-mask|{width}x{height}".encode())
    keys = [h.hexdigest()]
    for r in regions:
        h.update(json.dumps([r.id, r.polygon_px, r.mask_sha256], separators=(",", ":")).encode())
        keys.append(h.hexdigest())
    return keys


async def protected_mask_sha256(session: AsyncSession, width: int, height: int,
                                regions: list[ProtectedRegion]) -> str:
    """範囲（古い順。input_image_preparation.protected_regions_for の並び）を重ねたマスク（PNG）の置き場の sha256。"""
    keys = _prefix_keys(width, height, regions)
    rows = (await session.execute(select(ProtectedMaskCache).where(ProtectedMaskCache.key.in_(keys)))).scalars()
    # 控えの絵が置き場から消えていれば、その控えは使わない（置き場を替えた・片付けたとき）。
    # 範囲が無いとき（i = 0）は控えを引かない（全部黒の絵を作るだけ）
    hit = {row.key: row.sha256 for row in rows if image_exists(row.sha256)}
    done = max((i for i, k in enumerate(keys) if i > 0 and k in hit), default=None)
    if done == len(regions):
        return hit[keys[done]]
    rest = regions[done:] if done else regions
    start = [read_image(hit[keys[done]])] if done else []
    data = protected_mask_png(width, height, [r.polygon_px for r in rest if r.polygon_px is not None],
                              start + [read_image(r.mask_sha256) for r in rest if r.mask_sha256])
    stored = store_image(data)
    if regions:
        stmt = insert(ProtectedMaskCache).values(key=keys[-1], sha256=stored.sha256, region_count=len(regions))
        await session.execute(stmt.on_conflict_do_update(index_elements=["key"], set_={"sha256": stored.sha256}))
    return stored.sha256
