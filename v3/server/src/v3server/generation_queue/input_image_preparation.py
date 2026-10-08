"""依頼に入れる絵（作り直し・囲んで直すの元の絵、参照、マスク）を、依頼を受けるときに確かめて形にする。

request の形（ComfyUI の処理）
- input_images: [{"node": ノード番号, "input": 入力名, "image_id": 絵, "purpose": "source" | "reference" | "mask"}]
  source は描き直す元の絵。生成した絵・人が描いた絵・持ち込んだ絵のどれでもよい（出どころで分けない）
  purpose=mask は image_id の代わりに region_px（元の絵の画素の多角形の一覧）を渡してもよい（囲んで頼む。V3細部の決めごと 10.1）。
  そのときは、ここで元の絵（source。1枚だけ）と同じ大きさのマスク（白が囲んだ所）を描く。
  control は形の指定（線画・落書き・骨格・奥行き）の絵。image_id か png_base64 で渡す。
  png_base64（画面で塗ったマスク・描いた形の PNG。元の絵と同じ大きさ。白か不透明の所が囲んだ所）でもよい
- protected_mask_input: {"node": ノード番号, "input": 入力名}。人の手の範囲のマスクを入れる所

ここで行うこと
- 絵が作品の物かを確かめ、置き場の名前（sha256）を prepared_inputs に書く。送り手（comfyui_sender.py）はこれだけを見て上げる
- 元の絵（source）に人の手の範囲（ProtectedRegion）があれば、マスクを描いて必ず渡す。入れる所（protected_mask_input）が
  無い依頼は断る（人の範囲を描き直させないため。V3細部の決めごと 10.2）。範囲は、元の絵と、同じ大きさのまま続く前の版のものを使う
- 元の絵が1枚なら、生成した絵の元の版（register.based_on_image_id）をその絵にする
prepared_inputs は依頼する側が書けない（書いてあれば断る）。
画像生成の処理（request.image_process）は、最後に image_process_preparation.py でマスクと絵を下ごしらえする。
"""

import base64
import binascii
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.text_and_layer_tables import ProtectedRegion
from v3server.comfy_graphs.protected_region_mask import protected_mask_png
from v3server.generation_queue.protected_mask_cache import protected_mask_sha256
from v3server.hand_tools.vector_strokes import refuse_stale_stroke_cache
from v3server.image_file_storage import store_image
from v3server.operations.operation_base import get_in_work
from v3server.v3_error_types import Invalid

PURPOSES = ("source", "reference", "mask", "control")


async def protected_regions_for(session: AsyncSession, img: ImageFile) -> list[ProtectedRegion]:
    """この絵と、同じ大きさのまま続く前の版に付いた人の手の範囲（外したものは除く）。"""
    ids, cur = [], img
    while cur is not None and (cur.width, cur.height) == (img.width, img.height) and cur.id not in ids:
        ids.append(cur.id)
        cur = await session.get(ImageFile, cur.based_on_image_id) if cur.based_on_image_id else None
    q = select(ProtectedRegion).where(ProtectedRegion.image_id.in_(ids), ProtectedRegion.removed.is_(False))
    return list((await session.execute(q.order_by(ProtectedRegion.created_at))).scalars())


def _slot(entry: Any, what: str) -> tuple[str, str]:
    if not isinstance(entry, dict) or not isinstance(entry.get("node"), str) or not isinstance(entry.get("input"), str):
        raise Invalid(f"{what} には node と input（文字）が要る: {entry!r}")
    return entry["node"], entry["input"]


def _polygons(value: Any) -> list[list[tuple[float, float]]]:
    try:
        polys = [[(float(x), float(y)) for x, y in poly] for poly in value]
    except (TypeError, ValueError) as e:
        raise Invalid(f"region_px は多角形（[x, y] の一覧）の一覧: {e}") from e
    if not polys or any(len(p) < 3 for p in polys):
        raise Invalid("region_px の多角形は1つ以上、どれも3点以上")
    return polys


async def prepare_input_images(session: AsyncSession, work_id: str, request: dict[str, Any]) -> dict[str, Any]:
    out = await _prepare(session, work_id, request)
    if "image_process" in out:
        from v3server.generation_queue.image_process_preparation import finish_image_process

        out = finish_image_process(out)
    return out


def _png(value: Any) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError) as e:
        raise Invalid(f"png_base64 が base64 でない: {e}") from e


async def _prepare(session: AsyncSession, work_id: str, request: dict[str, Any]) -> dict[str, Any]:
    if "prepared_inputs" in request:
        raise Invalid("prepared_inputs はサーバーが書く。依頼に入れられない")
    entries = request.get("input_images")
    mask_slot = request.get("protected_mask_input")
    if entries is None:
        if mask_slot is not None:
            raise Invalid("元の絵（input_images）が無いのに protected_mask_input がある")
        return request
    if not isinstance(entries, list):
        raise Invalid("input_images は一覧で渡す")
    prepared, sources, regions_in = [], [], []
    for e in entries:
        node, inp = _slot(e, "input_images")
        if e.get("purpose") not in PURPOSES:
            raise Invalid(f"input_images の purpose は {PURPOSES} のどれか: {e!r}")
        if e["purpose"] == "mask" and "region_px" in e:
            if "image_id" in e:
                raise Invalid("マスクは image_id か region_px のどちらか")
            regions_in.append((node, inp, _polygons(e["region_px"])))
            continue
        if e["purpose"] in ("mask", "control") and "png_base64" in e:
            if "image_id" in e:
                raise Invalid("マスク・形の指定の絵は image_id か png_base64 のどちらか")
            stored = store_image(_png(e["png_base64"]))
            prepared.append({"node": node, "input": inp, "purpose": e["purpose"], "image_id": None,
                             "sha256": stored.sha256, "media_type": stored.media_type, "painted": True})
            continue
        img = await get_in_work(session, ImageFile, e.get("image_id", ""), work_id)
        await refuse_stale_stroke_cache(session, img.id)
        prepared.append({"node": node, "input": inp, "purpose": e["purpose"], "image_id": img.id, "sha256": img.sha256,
                         "media_type": img.media_type})
        if e["purpose"] == "source":
            sources.append(img)
    for node, inp, polys in regions_in:
        if len(sources) != 1:
            raise Invalid("囲んだ範囲（region_px）のマスクは、元の絵（purpose=source）が1枚のときだけ描ける")
        stored = store_image(protected_mask_png(sources[0].width, sources[0].height, polys))
        prepared.append({"node": node, "input": inp, "purpose": "mask", "image_id": None, "sha256": stored.sha256,
                         "media_type": stored.media_type, "region_px": polys, "for_image_id": sources[0].id})
    protected = [(img, await protected_regions_for(session, img)) for img in sources]
    with_regions = [(img, rs) for img, rs in protected if rs]
    if len(with_regions) > 1:
        raise Invalid("人の手の範囲のある元の絵が2枚以上ある。マスクを1つに決められない")
    if with_regions and mask_slot is None:
        raise Invalid(f"元の絵 {with_regions[0][0].id} に人の手の範囲がある。protected_mask_input を手順に用意して渡す")
    if mask_slot is not None:
        node, inp = _slot(mask_slot, "protected_mask_input")
        if not sources:
            raise Invalid("protected_mask_input は元の絵（purpose=source）と一緒に渡す")
        img, regions = with_regions[0] if with_regions else (sources[0], [])
        mask_sha = await protected_mask_sha256(session, img.width, img.height, regions)
        prepared.append({"node": node, "input": inp, "purpose": "protected_mask", "image_id": None,
                         "sha256": mask_sha, "media_type": "image/png",
                         "region_ids": [r.id for r in regions], "for_image_id": img.id})
    out = {**request, "prepared_inputs": prepared}
    register = out.get("register")
    if isinstance(register, dict) and len(sources) == 1 and "based_on_image_id" not in register:
        out["register"] = {**register, "based_on_image_id": sources[0].id}
    return out
