"""画像生成の処理（request.image_process）の下ごしらえ。input_image_preparation.prepare_input_images の最後に呼ぶ。

request.image_process の形: {"name": 処理, "params": 引数, "seed": シード, "candidate_set_id": 候補のまとまり,
"requested_params": 画面で入れたままの引数（描き足すの mm など。「この設定でもう一度」に使う）}

ここで行うこと
- 引数を処理の形（image_process_registry.py）で確かめる。prepared はサーバーが書く（書いてあれば断る）
- 元の絵・描き直す範囲・人の手の範囲の数を、処理の決まり（source・mask）と合わせる。元の絵がある処理は、人の手の範囲の
  マスク（protected_mask）を必ず持つ（範囲が無ければ全部黒）
- 処理の prepare でマスクと絵を描き、置き場に置いて、prepared_inputs の入れ先を名前のノード（source・redraw_mask・
  blend_mask・protected_mask）へ書き直す。描いた値（大きさ・切り出し・出来上がりと元の絵の画素の対応）を image_process.prepared に書く
"""
from __future__ import annotations

import io
from typing import Any

from PIL import Image

from v3server.comfy_graphs.source_and_masks import BLEND_MASK, CONTROL, PROTECTED_MASK, REDRAW_MASK, SOURCE
from v3server.generation_queue import image_process_inputs as mk
from v3server.generation_queue.image_process_registry import PrepIn, parse_params, spec_for
from v3server.image_file_storage import read_image, store_image
from v3server.v3_error_types import Invalid

SEED_MAX = 2**53 - 1


def _slot(node: str, entry: dict[str, Any], stored=None, **extra) -> dict[str, Any]:
    out = {**entry, "node": node, "input": "image", **extra}
    if stored is not None:
        out.update(sha256=stored.sha256, media_type=stored.media_type)
    return out


def finish_image_process(request: dict[str, Any]) -> dict[str, Any]:
    ip = request["image_process"]
    if not isinstance(ip, dict):
        raise Invalid("image_process は辞書で渡す")
    if "prepared" in ip:
        raise Invalid("image_process.prepared はサーバーが書く。依頼に入れられない")
    spec = spec_for(ip.get("name", ""))
    params = parse_params(spec, ip.get("params"))
    seed = ip.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= SEED_MAX:
        raise Invalid(f"image_process.seed は 0〜{SEED_MAX} の整数")
    entries = request.get("prepared_inputs", [])
    by = {k: [e for e in entries if e["purpose"] == k]
          for k in ("source", "mask", "protected_mask", "reference", "control")}
    if len(by["control"]) > 1:
        raise Invalid("形の指定の絵は1枚")
    has_control = bool(by["control"])
    if by["reference"]:
        raise Invalid(f"{spec.label} は参照の絵を受けない")
    if spec.source == "none":
        if len(entries) != len(by["control"]):
            raise Invalid(f"{spec.label} は元の絵を受けない")
        out = spec.prepare(params, PrepIn(None, None, None, None, has_control))
        return {**request, "prepared_inputs": [_slot(CONTROL, e) for e in by["control"]],
                "image_process": {**ip, "params": params.model_dump(), "prepared": out.info}}
    if len(by["source"]) != 1:
        raise Invalid(f"{spec.label} は元の絵（purpose=source）を1枚渡す")
    if len(by["protected_mask"]) != 1:
        raise Invalid(f"{spec.label} は人の手の範囲のマスク（protected_mask_input）を必ず渡す")
    if len(by["mask"]) > 1:
        raise Invalid("描き直す範囲のマスクは1つ")
    if by["mask"] and spec.mask == "none":
        raise Invalid(f"{spec.label} は描き直す範囲を受けない")
    if not by["mask"] and spec.mask == "required":
        raise Invalid(f"{spec.label} は描き直す範囲（purpose=mask）が要る")

    src, prot = by["source"][0], by["protected_mask"][0]
    source_bytes = read_image(src["sha256"])
    size = Image.open(io.BytesIO(source_bytes)).size
    mask = mk.to_array(read_image(by["mask"][0]["sha256"]), size) if by["mask"] else None
    protected = mk.to_array(read_image(prot["sha256"]), size)
    out = spec.prepare(params, PrepIn(source_bytes, size, mask, protected, has_control))

    new_entries = []
    for e in entries:
        if e["purpose"] == "source":
            if out.source is not None:
                new_entries.append(_slot(SOURCE, e, store_image(out.source), derived=True))
            else:
                new_entries.append(_slot(SOURCE, e))
        elif e["purpose"] == "control":
            new_entries.append(_slot(CONTROL, e))
        elif e["purpose"] == "protected_mask":
            new_entries.append(_slot(PROTECTED_MASK, e, store_image(mk.to_png(out.protected))))
    base = by["mask"][0] if by["mask"] else {"purpose": "mask", "image_id": None}
    # 描くときは白黒（redraw）、重ねるときはぼかしたまま（blend）。どちらを返すかは処理の prepare が決める
    for node, arr in ((REDRAW_MASK, out.redraw), (BLEND_MASK, out.blend)):
        if arr is not None:
            new_entries.append(_slot(node, base, store_image(mk.to_png(arr))))
    return {**request, "prepared_inputs": new_entries,
            "image_process": {**ip, "params": params.model_dump(), "prepared": out.info}}
