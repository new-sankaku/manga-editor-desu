"""要求の本体の大きさの上限（V3_REQUEST_MAX_BYTES。点検5 3-1）。

全部の口にかける（口ごとに書かない）。Content-Length が上限を超えていれば読まずに 413 を返す。
Content-Length が無い・偽っている要求も、読んだ量を数えて上限を超えたところで止める。
アップロードは Starlette が一時ファイルに書くので（UploadFile）、上限までは円盤に書かれる。
"""

import json

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from v3server.server_settings import get_settings


def _too_large_body(limit: int) -> bytes:
    return json.dumps({"code": "too_large", "detail": f"要求の本体が上限（{limit} バイト。V3_REQUEST_MAX_BYTES）を超えた"},
                      ensure_ascii=False).encode()


class RequestSizeLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = get_settings().request_max_bytes
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            body = _too_large_body(limit)
            await send({"type": "http.response.start", "status": 413,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return
        received = 0

        async def counted() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # FastAPI は本体を読む途中の HTTPException をそのまま返す（ほかの例外は 400 にする）
                    raise HTTPException(413, _too_large_body(limit).decode())
            return message

        await self.app(scope, counted, send)
