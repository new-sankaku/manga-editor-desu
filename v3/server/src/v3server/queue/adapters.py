"""つなぎ先の呼び方。1回送って結果か失敗を返すだけ。送り直しと待ちは queue/workflows.py が持つ。

失敗の種類（V3細部の決めごと 4.5）
- rate_limited: 回数・同時実行の制限。待って同じ先に送り直す
- transport: 時間切れ・通信の失敗。同じ先に送り直す（回数は処理ごとの resend_limit）
- refused: 内容で断られた。送り直さない
- broken_response: 返ってきた形が崩れている。使わない
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from ..config import get_settings
from ..models import Service, ServiceProcess


class AdapterError(Exception):
    def __init__(self, kind: str, detail: str, retry_after: float | None = None):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail
        self.retry_after = retry_after


@dataclass
class AdapterResult:
    output: dict[str, Any]
    model: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None


Adapter = Callable[[Service, ServiceProcess, dict[str, Any]], Awaitable[AdapterResult]]


def _retry_after(r: httpx.Response) -> float | None:
    v = r.headers.get("retry-after")
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


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
        raise AdapterError("rate_limited", r.text[:500], _retry_after(r))
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


ADAPTERS: dict[str, Adapter] = {"litellm": call_litellm, "comfyui": call_comfyui}
