"""権限。中身は OpenFGA が持つ。モデルは openfga/model.fga（model.json は fga model transform で作る）。

AIの作業は、頼んだ人の権限で確かめる（V3ハーネス設計 4.3・14章）。
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import SystemValue

MODEL_PATH = Path(__file__).resolve().parents[2] / "openfga" / "model.json"

# 作品の役。画面と API で受け付ける名前
WORK_ROLES = ("author", "editor", "assistant", "client", "translator", "viewer")


class AuthzError(Exception):
    pass


@dataclass(frozen=True)
class Tuple:
    user: str
    relation: str
    object: str

    def as_key(self) -> dict[str, str]:
        return {"user": self.user, "relation": self.relation, "object": self.object}


class Authz:
    def __init__(self, store_id: str, model_id: str, client: httpx.AsyncClient):
        self.store_id = store_id
        self.model_id = model_id
        self._client = client

    async def check(self, user: str, relation: str, obj: str) -> bool:
        r = await self._client.post(
            f"/stores/{self.store_id}/check",
            json={
                "authorization_model_id": self.model_id,
                "tuple_key": {"user": f"user:{user}", "relation": relation, "object": obj},
            },
        )
        r.raise_for_status()
        return bool(r.json()["allowed"])

    async def write(self, writes: list[Tuple] = (), deletes: list[Tuple] = ()) -> None:
        body: dict = {"authorization_model_id": self.model_id}
        if writes:
            body["writes"] = {"tuple_keys": [t.as_key() for t in writes], "on_duplicate": "ignore"}
        if deletes:
            body["deletes"] = {"tuple_keys": [t.as_key() for t in deletes], "on_missing": "ignore"}
        if len(body) == 1:
            return
        r = await self._client.post(f"/stores/{self.store_id}/write", json=body)
        if r.status_code >= 400:
            raise AuthzError(r.text)

    async def read(self, obj: str) -> list[Tuple]:
        tuples: list[Tuple] = []
        token = ""
        while True:
            body: dict = {"tuple_key": {"object": obj}, "page_size": 100}
            if token:
                body["continuation_token"] = token
            r = await self._client.post(f"/stores/{self.store_id}/read", json=body)
            r.raise_for_status()
            data = r.json()
            tuples += [Tuple(t["key"]["user"], t["key"]["relation"], t["key"]["object"]) for t in data["tuples"]]
            token = data.get("continuation_token") or ""
            if not token:
                return tuples

async def _get_value(session: AsyncSession, key: str) -> str | None:
    row = await session.get(SystemValue, key)
    return row.value if row else None


async def _set_value(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(SystemValue, key)
    if row:
        row.value = value
    else:
        session.add(SystemValue(key=key, value=value))


async def open_authz(session: AsyncSession) -> Authz:
    """ストアが無ければ作り、model.json が変わっていれば新しいモデルを書く。"""
    client = httpx.AsyncClient(base_url=get_settings().openfga_url, timeout=10)
    model_text = MODEL_PATH.read_text(encoding="utf-8")
    model_hash = hashlib.sha256(model_text.encode()).hexdigest()

    store_id = await _get_value(session, "openfga_store_id")
    if store_id is None:
        r = await client.post("/stores", json={"name": "v3-server"})
        r.raise_for_status()
        store_id = r.json()["id"]
        await _set_value(session, "openfga_store_id", store_id)

    model_id = await _get_value(session, "openfga_model_id")
    if model_id is None or await _get_value(session, "openfga_model_hash") != model_hash:
        r = await client.post(f"/stores/{store_id}/authorization-models", json=json.loads(model_text))
        r.raise_for_status()
        model_id = r.json()["authorization_model_id"]
        await _set_value(session, "openfga_model_id", model_id)
        await _set_value(session, "openfga_model_hash", model_hash)

    await session.commit()
    return Authz(store_id, model_id, client)

