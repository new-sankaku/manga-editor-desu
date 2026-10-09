"""送り先の制限（V3ハーネス設計 11章・17章の6）。

- ローカル（local）は外へ出ないので、どの作品からも送ってよい
- API（api）は、作品の送ってよい先に載っているものだけ
- 載っていない先へは送らない。別の先へ自動で回さない（方針7）

「ローカル」と言えるもの（proves_local）。登録した人の申告（location）だけでは信じない（点検5 5-2）。
- アダプターが送り先へ直接送る物（comfyui・detector）で、
- endpoint の URL が、このサーバーと同じ PC を指す（127.0.0.0/8・::1 の数字のアドレスか、localhost）
これを満たさない物は、location を local と書いても API と同じに扱う（作品の送ってよい先に載せる）。
- litellm はローカルと言えない：LiteLLM 自体はローカルでも、その先のモデルが外の API かは LiteLLM の設定次第で、ここからは見えない
- 社内の別の PC（10.x・192.168.x など）もローカルと言えない：そのアドレスが外へつながる中継でないかを、ここからは確かめられない。
  社内の ComfyUI などは api として登録し、作品ごとに送ってよい先へ載せる
- localhost の名前の引き方（/etc/hosts）は確かめていない（未検証）。数字のアドレスなら確か
"""

import ipaddress
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.service_and_job_tables import Service, WorkDestination
from v3server.messages import m

# 送り先へ直接送るアダプター。この外（litellm）は、その先がどこかを URL から決められない
DIRECT_ADAPTERS = ("comfyui", "detector")


def proves_local(adapter: str, endpoint: str | None) -> tuple[bool, str]:
    """(ローカルと言えるか, 言えない理由)。"""
    if adapter not in DIRECT_ADAPTERS:
        return False, m("{adapter} は送った先のその先が見えないので、ローカルと言えない", adapter=adapter)
    if endpoint is None:
        return False, m("endpoint が無い")
    host = urlsplit(endpoint).hostname
    if host is None:
        return False, m("endpoint の URL が読めない: {endpoint}", endpoint=endpoint)
    if host == "localhost":
        return True, ""
    try:
        if ipaddress.ip_address(host).is_loopback:
            return True, ""
    except ValueError:
        pass
    return False, m("endpoint の URL（{host}）がこのサーバーと同じ PC ではない", host=host)


def is_local(service: Service) -> bool:
    return service.location == "local" and proves_local(service.adapter, service.endpoint)[0]


def effective_location(service: Service) -> str:
    """画面と API に出す場所。ローカルと言えない local は api と出す。"""
    return "local" if is_local(service) else "api"


async def is_allowed(session: AsyncSession, work_id: str, service: Service) -> bool:
    if is_local(service):
        return True
    return await session.get(WorkDestination, (work_id, service.id)) is not None
