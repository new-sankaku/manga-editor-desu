"""つなぎ先の呼び方。1回送って結果か失敗を返すだけ。送り直しと待ちは generation_queue/generation_workflow.py が持つ。

失敗の種類（V3細部の決めごと 4.5）
- rate_limited: 回数・同時実行の制限。待って同じ先に送り直す
- transport: 時間切れ・通信の失敗。同じ先に送り直す（回数は処理ごとの resend_limit）
- refused: 内容で断られた。送り直さない
- broken_response: 返ってきた形が崩れている。使わない
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from v3server.canonical_tables.service_and_job_tables import Service, ServiceProcess


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


def retry_after_seconds(r: httpx.Response) -> float | None:
    v = r.headers.get("retry-after")
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


