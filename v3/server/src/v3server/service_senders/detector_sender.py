"""検出器のプロセス（v3/detector_server）へ送る。絵は置き場（image_file_storage）から sha256 で読んで送る。

依頼の request の形
- endpoint: 検出器の口（DETECTOR_ENDPOINTS のどれか）
- images: 項目の名前 → 絵の sha256（同一キャラ判定は image_a・image_b、ほかは image）
- form: 閾値など、口ごとの項目（省略した項目は検出器の側で imgutils の既定に任せる）
"""

from typing import Any

import httpx

from v3server.canonical_tables.service_and_job_tables import Service, ServiceProcess
from v3server.image_file_storage import read_image
from v3server.service_senders.sender_result_types import AdapterError, AdapterResult

# 検出器の口と、要る絵の項目
DETECTOR_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "/person_face_head": ("image",),
    "/text_regions": ("image",),
    "/identity_ccip": ("image_a", "image_b"),
    "/age_rating": ("image",),
    "/hands": ("image",),
}


async def call_detector(service: Service, sp: ServiceProcess, request: dict[str, Any]) -> AdapterResult:
    endpoint = request.get("endpoint")
    if endpoint not in DETECTOR_ENDPOINTS:
        raise AdapterError("refused", f"検出器に無い口: {endpoint}")
    images = request.get("images", {})
    missing = [k for k in DETECTOR_ENDPOINTS[endpoint] if k not in images]
    if missing:
        raise AdapterError("refused", f"絵が足りない: {missing}")
    try:
        files = {k: (f"{k}.png", read_image(images[k]), "application/octet-stream") for k in DETECTOR_ENDPOINTS[endpoint]}
    except FileNotFoundError as e:
        raise AdapterError("refused", f"置き場に絵が無い: {e}") from e
    form = {k: str(v) for k, v in request.get("form", {}).items()}
    try:
        async with httpx.AsyncClient(base_url=service.endpoint, timeout=300) as client:
            r = await client.post(endpoint, files=files, data=form)
    except httpx.TimeoutException as e:
        raise AdapterError("transport", f"時間切れ: {e}") from e
    except httpx.TransportError as e:
        raise AdapterError("transport", str(e)) from e
    if r.status_code >= 500:
        raise AdapterError("transport", f"{r.status_code} {r.text[:500]}")
    if r.status_code >= 400:
        raise AdapterError("refused", f"{r.status_code} {r.text[:500]}")
    try:
        data = r.json()
    except ValueError as e:
        raise AdapterError("broken_response", r.text[:500]) from e
    if not isinstance(data, dict):
        raise AdapterError("broken_response", r.text[:500])
    return AdapterResult(output=data, settings={"endpoint": endpoint, **request.get("form", {})})
