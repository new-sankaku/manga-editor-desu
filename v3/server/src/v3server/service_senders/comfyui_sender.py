"""ComfyUI に送り、終わりを待つ。"""

import asyncio
from typing import Any

import httpx

from v3server.canonical_tables.service_and_job_tables import Service, ServiceProcess
from v3server.service_senders.sender_result_types import AdapterError, AdapterResult


async def call_comfyui(service: Service, sp: ServiceProcess, request: dict[str, Any]) -> AdapterResult:
    """画像。手元の ComfyUI の /prompt に手順を送り、/history で終わりを待つ。

    未検証: V3 のサーバーからはまだ ComfyUI に送っていない（この環境に ComfyUI が無い）。
    request["overrides"] は {ノード番号: {入力名: 値}}。手順の中の値を差し替える。
    """
    if service.endpoint is None:
        raise AdapterError("refused", f"{service.name} に住所が無い")
    if sp.comfy_workflow is None:
        raise AdapterError("refused", f"{service.name} の {sp.process} に手順が無い")
    prompt = {k: {**v, "inputs": dict(v.get("inputs", {}))} for k, v in sp.comfy_workflow.items()}
    for node_id, inputs in request.get("overrides", {}).items():
        if node_id not in prompt:
            raise AdapterError("refused", f"手順にノード {node_id} が無い")
        prompt[node_id]["inputs"].update(inputs)
    try:
        async with httpx.AsyncClient(base_url=service.endpoint, timeout=30) as client:
            r = await client.post("/prompt", json={"prompt": prompt})
            if r.status_code >= 400:
                raise AdapterError("refused", f"{r.status_code} {r.text[:500]}")
            prompt_id = r.json()["prompt_id"]
            while True:
                h = await client.get(f"/history/{prompt_id}")
                h.raise_for_status()
                hist = h.json().get(prompt_id)
                if hist is not None:
                    break
                await asyncio.sleep(1)
    except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
        raise AdapterError("transport", str(e)) from e
    except (ValueError, KeyError) as e:
        raise AdapterError("broken_response", str(e)) from e

    status = hist.get("status", {})
    if status.get("status_str") == "error":
        raise AdapterError("refused", str(status.get("messages"))[:500])
    images = [img for out in hist.get("outputs", {}).values() for img in out.get("images", [])]
    if not images:
        raise AdapterError("broken_response", "画像が返っていない")
    return AdapterResult(output={"prompt_id": prompt_id, "images": images}, settings=request.get("overrides", {}))
