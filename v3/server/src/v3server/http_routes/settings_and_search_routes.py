"""利用者ごとの設定と、探すの口（V3細部の決めごと 10.4 の設定・探す）。

- 利用者ごとの設定（画面の言語・自動で残す・ショートカットキーなど）は、その人だけの物で作品の正本ではないので、
  操作の窓口を通さない（出来事の一覧に入らない・取り消しも無い）。自分の設定だけを読み書きできる
- 作品ごとの設定は POST /works/{id}/ops の set_work_settings（preferences）
- 探すは読むだけ。置き換えは POST /works/{id}/ops の replace_text（1回で取り消せる）
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from v3server.canonical_tables.material_and_setting_tables import UserSetting
from v3server.http_routes.http_dependencies import ActorDep, AuthzDep, SessionDep, require, row
from v3server.operations.operation_base import work_obj
from v3server.operations.text_search_and_replace import find_matches, match_view

router = APIRouter()

SETTING_FIELDS = ("user_id", "language", "autosave", "autosave_interval_seconds", "other", "updated_at")


class UserSettingValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str | None = Field(default=None, max_length=16)
    autosave: bool | None = None
    autosave_interval_seconds: int | None = Field(default=None, gt=0)
    other: dict[str, Any] = Field(default_factory=dict)


@router.get("/me/settings")
async def get_my_settings(session: SessionDep, actor: ActorDep):
    s = await session.get(UserSetting, actor.id)
    if s is None:
        # 設定がまだ無い（値を補わず、無いことをそのまま返す）
        return {"user_id": actor.id, "language": None, "autosave": None, "autosave_interval_seconds": None,
                "other": {}, "updated_at": None}
    return row(s, *SETTING_FIELDS)


@router.put("/me/settings")
async def put_my_settings(values: UserSettingValues, session: SessionDep, actor: ActorDep):
    s = await session.get(UserSetting, actor.id)
    if s is None:
        s = UserSetting(user_id=actor.id)
        session.add(s)
    for k, v in values.model_dump().items():
        setattr(s, k, v)
    await session.commit()
    await session.refresh(s)
    return row(s, *SETTING_FIELDS)


@router.get("/works/{work_id}/search")
async def search(work_id: str, q: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                 kinds: Annotated[list[str], Query()] = ["text", "name", "setting", "annotation"],  # noqa: B006  FastAPI の既定値。書き換えない
                 page_ids: Annotated[list[str] | None, Query()] = None):
    await require(authz, actor, "can_view", work_obj(work_id))
    return [match_view(obj, field) for obj, field in await find_matches(session, work_id, q, set(kinds), page_ids)]
