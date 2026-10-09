"""接続先の様子を読む：接続できるか・いま走っている数・入っているモデル（生成サービスの画面）。

アダプター（comfyui_sender.py など）と同じ URL へ、読むだけの API を呼ぶ。正本も依頼も変えない。
- ComfyUI：/system_stats（バージョン・PC）、/queue（走っている・待っている数）、/object_info（ノードの選べる値。名前が
  *_name の選択肢をモデルの一覧として返す。どの入力がモデルかは ComfyUI が決めていないので、名前で拾う。拾い漏れはありうる）
- LiteLLM：/v1/models（接続したモデルの名前）。URL は接続先ではなく設定の V3_LITELLM_URL（アダプターと同じ）
- 検出器：/health
API の呼び出しは _client の1か所で作る（試験はここを差し替える）。
"""

from typing import Any

import httpx

from v3server.canonical_tables.service_and_job_tables import Service
from v3server.messages import m
from v3server.server_settings import get_settings
from v3server.service_senders.comfyui_sender import combo_options

TIMEOUT = 15


class InspectionError(Exception):
    """接続先が答えなかった・答えの形が違う。state は Service.state に入れる値。"""

    def __init__(self, state: str, detail: str):
        super().__init__(detail)
        self.state = state
        self.detail = detail


def _client(base_url: str, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT, headers=headers or {})


def _target(service: Service) -> tuple[str, dict[str, str]]:
    if service.adapter == "litellm":
        s = get_settings()
        if s.litellm_master_key is None:
            raise InspectionError("key_rejected", m("LITELLM_MASTER_KEY が設定されていない"))
        return s.litellm_url, {"Authorization": f"Bearer {s.litellm_master_key}"}
    if not service.endpoint:
        raise InspectionError("stopped", m("{service} の URL（endpoint）が無い", service=service.name))
    return service.endpoint, {}


async def _get_json(service: Service, path: str) -> Any:
    base, headers = _target(service)
    try:
        async with _client(base, headers) as client:
            r = await client.get(path)
    except httpx.HTTPError as e:
        raise InspectionError("stopped", m("{path} に接続できない: {error}: {reason}", path=path,
                                           error=type(e).__name__, reason=str(e))) from e
    if r.status_code in (401, 403):
        raise InspectionError("key_rejected", m("{path} が {status} を返した（鍵が通らない）", path=path,
                                                status=r.status_code))
    if r.status_code >= 400:
        raise InspectionError("stopped", m("{path} が {status} を返した: {body}", path=path, status=r.status_code,
                                           body=r.text[:200]))
    try:
        return r.json()
    except ValueError as e:
        raise InspectionError("stopped", m("{path} の答えが JSON でない", path=path)) from e


HEALTH_PATH = {"comfyui": "/system_stats", "litellm": "/v1/models", "detector": "/health"}


async def connection_test(service: Service) -> dict[str, Any]:
    """接続を試す。答えた中身（バージョン・PC など）を返す。接続できなければ InspectionError。"""
    body = await _get_json(service, HEALTH_PATH[service.adapter])
    if service.adapter == "comfyui":
        if not isinstance(body, dict) or "system" not in body:
            raise InspectionError("stopped", m("/system_stats の形が ComfyUI と違う"))
        return {"system": body.get("system"), "devices": body.get("devices", [])}
    if service.adapter == "litellm":
        return {"model_count": len(_model_ids(body))}
    return {"health": body}


def _model_ids(body: Any) -> list[str]:
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise InspectionError("stopped", m("/v1/models の形が OpenAI 互換と違う"))
    return sorted(str(entry.get("id")) for entry in body["data"] if isinstance(entry, dict) and entry.get("id"))


async def running_state(service: Service) -> dict[str, Any]:
    """接続先の側で走っている・待っている数（ComfyUI だけ。ほかは API が無いので None）。"""
    if service.adapter != "comfyui":
        return {"running": None, "pending": None,
                "note": m("{adapter} にはキューを読む API が無い", adapter=service.adapter)}
    q = await _get_json(service, "/queue")
    if not isinstance(q, dict) or not isinstance(q.get("queue_running"), list) \
            or not isinstance(q.get("queue_pending"), list):
        raise InspectionError("stopped", m("/queue の形が ComfyUI と違う"))
    return {"running": len(q["queue_running"]), "pending": len(q["queue_pending"])}


def models_from_object_info(info: dict[str, Any]) -> dict[str, list[str]]:
    """/object_info の、名前が *_name の選択肢の入力を、入力の名前ごとに集める（ckpt_name・lora_name・vae_name など）。"""
    out: dict[str, set[str]] = {}
    for node in info.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("input") or {}
        for group in ("required", "optional"):
            for name, spec in (inputs.get(group) or {}).items():
                options = combo_options(spec)
                if name.endswith("_name") and options:
                    out.setdefault(name, set()).update(str(o) for o in options)
    return {k: sorted(v) for k, v in sorted(out.items())}


async def installed_models(service: Service) -> dict[str, Any]:
    if service.adapter == "comfyui":
        info = await _get_json(service, "/object_info")
        if not isinstance(info, dict):
            raise InspectionError("stopped", m("/object_info の形が ComfyUI と違う"))
        stats = await _get_json(service, "/system_stats")
        return {"models": models_from_object_info(info), "system_stats": stats}
    if service.adapter == "litellm":
        return {"models": {"model": _model_ids(await _get_json(service, "/v1/models"))}}
    return {"models": {}, "note": m("検出器のモデルは検出器の側で決まる（読む API が無い）")}
