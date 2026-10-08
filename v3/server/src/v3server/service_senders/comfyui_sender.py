"""ComfyUI に送り、終わりを待ち、絵を受け取る（試作 p56 で本物の ComfyUI 0.39.2 に送って確かめた形）。

request の形
- overrides: {ノード番号: {入力名: 値}}。手順の中の値を差し替える
- register: {"role": 絵の役目, "page_id": ページ, "panel_id": コマ, "based_on_image_id": 元の版}。受け取った絵を登録するときの引数
  （role は必須。ほかは省ける。登録は generation_queue/service_call_activity.py が行う）
- image_process: 画像生成の処理（generation_queue/image_process_registry.py）。あれば手順は保存した物（comfy_workflow）を使わず、
  処理の build でその場で組む。中身は ServiceProcess.comfy_graph_settings。overrides は使えない
- prepared_inputs: 依頼を受けたときにサーバーが書いた、上げる絵の一覧（generation_queue/input_image_preparation.py）。
  各絵を置き場から読んで /upload/image に上げ（type=input、overwrite=true）、返ってきた名前を node・input に入れる。
  /upload/image の 4xx は refused、5xx は transport

失敗の種類
- /prompt の 429 は rate_limited（Retry-After）、5xx は transport、その他の 4xx は refused
  （400 は ComfyUI が手順を確かめて断った。error.type と node_errors の要点を detail の先頭に出す）
- /history の 429 は rate_limited、5xx は transport、その他の 4xx と、辞書でない本体は broken_response
- 実行時の失敗は refused（detail は execution_error の exception_message）。execution_interrupted は interrupted
- 待ちにも実行中にも履歴にも無い、または処理ごとの待ちの上限を超えた場合は transport

取り消し: 呼び出しが取り消されたら、待ちの物は /queue の delete、自分の依頼が実行中なら /interrupt に prompt_id を付けて呼んで止める。

進み具合: request.progress_key があれば、/prompt に client_id として渡し、WebSocket で段数と途中の絵を受けて
service_call_progress に書く（comfyui_progress.py）。
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from v3server.canonical_tables.service_and_job_tables import Service, ServiceProcess
from v3server.generation_queue.image_process_registry import build_prompt
from v3server.image_file_storage import read_image
from v3server.service_senders.comfyui_progress import ProgressListener
from v3server.service_senders.sender_result_types import (
    AdapterError,
    AdapterResult,
    retry_after_seconds,
)
from v3server.v3_error_types import Invalid

# /history を見る間隔（秒）。ComfyUI の側に待たせる口が無いので、見に行く
POLL_SECONDS = 1.0
log = logging.getLogger(__name__)

# 1回の通信の時間切れ（秒）
REQUEST_TIMEOUT = 30
# 取り消しの後始末にかける時間（秒）
CANCEL_TIMEOUT = 10
# detail に入れる文字数の上限（保存先は Text だが、画面とログで長すぎないように）
DETAIL_LIMIT = 2000


def _short(text: str) -> str:
    return text if len(text) <= DETAIL_LIMIT else text[:DETAIL_LIMIT] + "…"


def prompt_error_detail(r: httpx.Response) -> str:
    """/prompt が断った理由。error.type と node_errors の要点を先頭に出す。JSON でなければ本文の先頭。"""
    try:
        body = r.json()
        err = body["error"]
        head = f"{r.status_code} {err.get('type')}: {err.get('message')}"
        if err.get("details"):
            head += f" ({err['details']})"
        for node_id, ne in (body.get("node_errors") or {}).items():
            for e in ne.get("errors", []):
                head += f"; ノード {node_id} ({ne.get('class_type')}): {e.get('type')} {e.get('message')} {e.get('details', '')}".rstrip()
        return _short(head)
    except (ValueError, KeyError, AttributeError, TypeError):
        return _short(f"{r.status_code} {r.text}")


def _raise_for_prompt_status(r: httpx.Response) -> None:
    if r.status_code == 429:
        raise AdapterError("rate_limited", prompt_error_detail(r), retry_after_seconds(r))
    if r.status_code >= 500:
        raise AdapterError("transport", prompt_error_detail(r))
    if r.status_code >= 400:
        raise AdapterError("refused", prompt_error_detail(r))


def _json_object(r: httpx.Response, what: str) -> dict[str, Any]:
    try:
        body = r.json()
    except ValueError as e:
        raise AdapterError("broken_response", f"{what} が JSON でない: {e}") from e
    if not isinstance(body, dict):
        raise AdapterError("broken_response", f"{what} が辞書でない: {type(body).__name__}")
    return body


def _raise_for_poll_status(r: httpx.Response, what: str) -> None:
    if r.status_code == 429:
        raise AdapterError("rate_limited", f"{what} {r.status_code}", retry_after_seconds(r))
    if r.status_code >= 500:
        raise AdapterError("transport", f"{what} {r.status_code}")
    if r.status_code >= 400:
        raise AdapterError("broken_response", f"{what} が {r.status_code}。ComfyUI の口ではない")


def combo_options(spec: Any) -> list[Any] | None:
    """/object_info の入力の定義から、選べる値の一覧を取る。選択肢の入力でなければ None。"""
    if not isinstance(spec, list) or not spec:
        return None
    if isinstance(spec[0], list):
        return spec[0]
    if spec[0] == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
        return spec[1].get("options")
    return None


async def check_choices(client: httpx.AsyncClient, prompt: dict[str, Any]) -> None:
    """手順の中の選択肢の入力（モデル名・サンプラーなど）が、いまの ComfyUI で選べるか確かめる。

    入っていなければ refused（どの入力のどの値かを detail に出す）。/prompt に送っても同じ理由で 400 になるが、
    送る前に分かれば順番待ちに入れずに済む。つなぎ（["ノード番号", 番号]）の入力は見ない。
    """
    problems: list[str] = []
    infos: dict[str, dict[str, Any]] = {}
    for node_id, node in prompt.items():
        cls = node["class_type"]
        if cls not in infos:
            r = await client.get(f"/object_info/{cls}")
            _raise_for_poll_status(r, f"/object_info/{cls}")
            infos[cls] = _json_object(r, f"/object_info/{cls}").get(cls, {})
        info = infos[cls]
        if not info:
            problems.append(f"ノード {node_id}: {cls} が ComfyUI に無い")
            continue
        defs = {**info.get("input", {}).get("required", {}), **info.get("input", {}).get("optional", {})}
        for name, value in node.get("inputs", {}).items():
            if isinstance(value, list):
                continue
            options = combo_options(defs.get(name))
            if options is not None and value not in options:
                problems.append(f"ノード {node_id} ({cls}) の {name}={value!r} は選べない")
    if problems:
        raise AdapterError("refused", _short("; ".join(problems)))


def _failure_from_history(hist: dict[str, Any]) -> AdapterError | None:
    status = hist.get("status")
    if not isinstance(status, dict):
        raise AdapterError("broken_response", "history に status が無い")
    if status.get("status_str") != "error":
        return None
    messages = status.get("messages")
    if not isinstance(messages, list):
        raise AdapterError("broken_response", "history の messages が一覧でない")
    for m in messages:
        if isinstance(m, list) and len(m) == 2 and m[0] == "execution_interrupted":
            node = m[1].get("node_type") if isinstance(m[1], dict) else None
            return AdapterError("interrupted", f"ComfyUI で止められた（{node} の実行中）")
    for m in messages:
        if isinstance(m, list) and len(m) == 2 and m[0] == "execution_error" and isinstance(m[1], dict):
            e = m[1]
            return AdapterError(
                "refused", _short(f"実行に失敗（{e.get('node_type')} ノード {e.get('node_id')}）: {e.get('exception_message')}")
            )
    raise AdapterError("broken_response", "history が error なのに execution_error が無い")


async def _in_queue(client: httpx.AsyncClient, prompt_id: str) -> str | None:
    """/queue を見て、"running"・"pending"・None（どちらにも無い）を返す。"""
    r = await client.get("/queue")
    _raise_for_poll_status(r, "/queue")
    q = _json_object(r, "/queue")
    try:
        if any(item[1] == prompt_id for item in q["queue_running"]):
            return "running"
        if any(item[1] == prompt_id for item in q["queue_pending"]):
            return "pending"
    except (KeyError, IndexError, TypeError) as e:
        raise AdapterError("broken_response", f"/queue の形が違う: {e!r}") from e
    return None


async def cancel_prompt(client: httpx.AsyncClient, prompt_id: str) -> str:
    """送った物を止める。待ちなら /queue の delete、自分の依頼が実行中なら /interrupt に prompt_id を付けて呼ぶ。
    prompt_id を付けると、ComfyUI はそれが今走っているときだけ止める（ソースで確かめた。調査 3.16）ので、
    確かめてから呼ぶまでの間に次の物が動き出しても、他人の依頼は止めない。"""
    where = await _in_queue(client, prompt_id)
    if where == "pending":
        r = await client.post("/queue", json={"delete": [prompt_id]})
        r.raise_for_status()
    elif where == "running":
        r = await client.post("/interrupt", json={"prompt_id": prompt_id})
        r.raise_for_status()
    return where or "none"


async def _fetch_images(client: httpx.AsyncClient, images: list[dict[str, Any]]) -> list[bytes]:
    files = []
    for img in images:
        try:
            params = {"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]}
        except (KeyError, TypeError) as e:
            raise AdapterError("broken_response", f"画像の指定の形が違う: {img!r}") from e
        r = await client.get("/view", params=params)
        _raise_for_poll_status(r, "/view")
        files.append(r.content)
    return files


def _validate_request(service: Service, sp: ServiceProcess, request: dict[str, Any]) -> None:
    if service.endpoint is None:
        raise AdapterError("refused", f"{service.name} に住所が無い")
    if "image_process" in request:
        if request.get("overrides"):
            raise AdapterError("refused", "画像生成の処理（image_process）に overrides は使えない（引数で渡す）")
    elif sp.comfy_workflow is None:
        raise AdapterError("refused", f"{service.name} の {sp.process} に手順が無い")
    if sp.comfy_wait_seconds is None:
        raise AdapterError("refused", f"{service.name} の {sp.process} に待ちの上限（comfy_wait_seconds）が決まっていない")
    register = request.get("register")
    if not isinstance(register, dict) or not register.get("role"):
        raise AdapterError("refused", "request.register.role が無い。受け取った絵の役目が決まらない")


async def _upload_inputs(client: httpx.AsyncClient, prompt: dict[str, Any], request: dict[str, Any]) -> list[dict]:
    """元の絵・マスクを ComfyUI の input に上げ、手順の入力に名前を入れる。上げた名前の一覧を返す。"""
    uploaded = []
    for entry in request.get("prepared_inputs", []):
        node, inp = entry["node"], entry["input"]
        if node not in prompt:
            raise AdapterError("refused", f"手順にノード {node} が無い（上げる絵の入れ先）")
        ext = entry["media_type"].split("/")[-1]
        name = f"v3_{entry['sha256']}.{ext}"
        r = await client.post("/upload/image", files={"image": (name, read_image(entry["sha256"]), entry["media_type"])},
                              data={"type": "input", "overwrite": "true"})
        if r.status_code >= 500:
            raise AdapterError("transport", f"/upload/image が {r.status_code}")
        if r.status_code >= 400:
            raise AdapterError("refused", f"/upload/image が {r.status_code}: {_short(r.text)}")
        body = _json_object(r, "/upload/image")
        if not isinstance(body.get("name"), str):
            raise AdapterError("broken_response", "/upload/image の返事に name が無い")
        value = f"{body['subfolder']}/{body['name']}" if body.get("subfolder") else body["name"]
        prompt[node]["inputs"][inp] = value
        uploaded.append({"node": node, "input": inp, "name": value, "purpose": entry["purpose"],
                         "image_id": entry.get("image_id")})
    return uploaded


async def _wait_history(client: httpx.AsyncClient, prompt_id: str, limit: float) -> dict[str, Any]:
    started = time.monotonic()
    while True:
        r = await client.get(f"/history/{prompt_id}")
        _raise_for_poll_status(r, "/history")
        hist = _json_object(r, "/history").get(prompt_id)
        if hist is not None:
            if not isinstance(hist, dict):
                raise AdapterError("broken_response", "history の中身が辞書でない")
            return hist
        # 履歴にまだ無い。待ちにも実行中にも無ければ、再起動か外から消されたので、待っても出ない。
        # 見に行く間に終わっていることがあるので、無いと分かったらもう一度だけ履歴を見る
        if await _in_queue(client, prompt_id) is None:
            r = await client.get(f"/history/{prompt_id}")
            _raise_for_poll_status(r, "/history")
            hist = _json_object(r, "/history").get(prompt_id)
            if hist is None:
                raise AdapterError("transport", "ComfyUI の待ちにも実行中にも履歴にも無い（再起動か、外から消された）")
            if not isinstance(hist, dict):
                raise AdapterError("broken_response", "history の中身が辞書でない")
            return hist
        if time.monotonic() - started > limit:
            raise AdapterError("transport", f"{limit} 秒待っても終わらない（comfy_wait_seconds）")
        await asyncio.sleep(POLL_SECONDS)


async def call_comfyui(service: Service, sp: ServiceProcess, request: dict[str, Any]) -> AdapterResult:
    """画像。手元の ComfyUI の /prompt に手順を送り、/history で終わりを待ち、/view で絵を受け取る。"""
    _validate_request(service, sp, request)
    ip = request.get("image_process")
    if ip is not None:
        try:
            prompt = build_prompt(ip["name"], sp.comfy_graph_settings, ip["params"], ip["seed"], ip["prepared"],
                                  f"v3_{ip['name']}")
        except Invalid as e:
            raise AdapterError("refused", str(e)) from e
    else:
        prompt = {k: {**v, "inputs": dict(v.get("inputs", {}))} for k, v in sp.comfy_workflow.items()}
        for node_id, inputs in request.get("overrides", {}).items():
            if node_id not in prompt:
                raise AdapterError("refused", f"手順にノード {node_id} が無い")
            prompt[node_id]["inputs"].update(inputs)

    prompt_id: str | None = None
    progress_key = request.get("progress_key")
    listener = ProgressListener(service.endpoint, progress_key) if progress_key else None
    final_state = "error"
    try:
        async with httpx.AsyncClient(base_url=service.endpoint, timeout=REQUEST_TIMEOUT) as client:
            try:
                uploaded = await _upload_inputs(client, prompt, request)
                if sp.comfy_check_choices:
                    await check_choices(client, prompt)
                if listener is not None:
                    # /prompt の前につなぐ。後だと最初の段の知らせを取りこぼす
                    await listener.start()
                body = {"prompt": prompt, **({"client_id": progress_key} if progress_key else {})}
                r = await client.post("/prompt", json=body)
                _raise_for_prompt_status(r)
                body = _json_object(r, "/prompt")
                if not isinstance(body.get("prompt_id"), str):
                    raise AdapterError("broken_response", "/prompt の返事に prompt_id が無い")
                prompt_id = body["prompt_id"]
                if listener is not None:
                    listener.prompt_id = prompt_id
                hist = await _wait_history(client, prompt_id, sp.comfy_wait_seconds)
                failure = _failure_from_history(hist)
                if failure is not None:
                    raise failure
                outputs = hist.get("outputs")
                if not isinstance(outputs, dict):
                    raise AdapterError("broken_response", "history に outputs が無い")
                images = [img for out in outputs.values() if isinstance(out, dict) for img in out.get("images", [])]
                if not images:
                    raise AdapterError("broken_response", "画像が返っていない")
                files = await _fetch_images(client, images)
                final_state = "finished"
            except asyncio.CancelledError:
                final_state = "interrupted"
                # 取り消された。送った物が残っていれば止める。後始末の失敗は取り消しを妨げない
                if prompt_id is not None:
                    try:
                        await asyncio.wait_for(cancel_prompt(client, prompt_id), CANCEL_TIMEOUT)
                    except (TimeoutError, httpx.HTTPError, AdapterError) as e:
                        log.warning("ComfyUI の %s を止められなかった: %r", prompt_id, e)
                raise
    except (httpx.TimeoutException, httpx.TransportError) as e:
        raise AdapterError("transport", str(e) or type(e).__name__) from e
    finally:
        if listener is not None:
            await listener.stop(final_state)
    return AdapterResult(
        output={"prompt_id": prompt_id, "images": images, "uploaded_inputs": uploaded},
        image_files=files,
        settings=ip["params"] if ip is not None else request.get("overrides", {}),
        seed=ip["seed"] if ip is not None else None,
    )
