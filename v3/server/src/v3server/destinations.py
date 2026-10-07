"""送り先の制限（V3ハーネス設計 11章・17章の6）。

- 手元（local）は外へ出ないので、どの作品からも送ってよい
- API（api）は、作品の送ってよい先に載っているものだけ
- 載っていない先へは送らない。別の先へ自動で回さない（方針7）
"""

from sqlalchemy.ext.asyncio import AsyncSession

from .models import Service, WorkDestination


async def is_allowed(session: AsyncSession, work_id: str, service: Service) -> bool:
    if service.location == "local":
        return True
    return await session.get(WorkDestination, (work_id, service.id)) is not None
