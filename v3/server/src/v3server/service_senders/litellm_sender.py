"""LLM・VLM を LiteLLM 経由で呼ぶ。"""

from typing import Any

import httpx

from v3server.canonical_tables.service_and_job_tables import Service, ServiceProcess
from v3server.server_settings import get_settings
from v3server.service_senders.sender_result_types import (
    AdapterError,
    AdapterResult,
    retry_after_seconds,
)


async def call_litellm(service: Service, sp: ServiceProcess, request: dict[str, Any]) -> AdapterResult:
    """文章・VLM。LiteLLM Proxy の OpenAI 互換の口へ送る。APIキーは LiteLLM だけが持つ（11章の鍵）。"""
    settings = get_settings()
    if settings.litellm_master_key is None:
        raise AdapterError("transport", "LITELLM_MASTER_KEY が設定されていない")
    if sp.model is None:
        raise AdapterError("refused", f"{service.name} の {sp.process} にモデルが決まっていない")
    params = request.get("params", {})
    body = {"model": sp.model, "messages": request["messages"], **params}
    try:
        async with httpx.AsyncClient(base_url=settings.litellm_url, timeout=600) as client:
            r = await client.post(
                "/v1/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
    except httpx.TimeoutException as e:
        raise AdapterError("transport", f"時間切れ: {e}") from e
    except httpx.TransportError as e:
        raise AdapterError("transport", str(e)) from e

    if r.status_code == 429:
        raise AdapterError("rate_limited", r.text[:500], retry_after_seconds(r))
    if r.status_code >= 500:
        raise AdapterError("transport", f"{r.status_code} {r.text[:500]}")
    if r.status_code >= 400:
        raise AdapterError("refused", f"{r.status_code} {r.text[:500]}")
    try:
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise AdapterError("broken_response", r.text[:500]) from e
    return AdapterResult(
        output={"text": text, "finish_reason": data["choices"][0].get("finish_reason")},
        model=data.get("model", sp.model),
        settings=params,
        seed=params.get("seed"),
        tokens_in=usage.get("prompt_tokens"),
        tokens_out=usage.get("completion_tokens"),
    )


