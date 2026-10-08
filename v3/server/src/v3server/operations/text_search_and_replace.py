"""探す・置き換え（V3細部の決めごと 10.4・17章）。

探す所と置き換える所は、下の SEARCH_FIELDS の1か所で決める。探すのは読むだけ（操作の窓口を通さない）。
置き換えは1つの操作（ReplaceText）で、当たった全部を1回で変え、1回で取り消せる。
人の手の印の付いた所にAIが当たったときは、その所を判断待ちに置く。「動かさない」の付いた行に当たったら、何も変えずに止める。
ルビの付いた文字で、置き換えで字数が変わる所は、ルビの位置がずれるので止める（ルビを先に直す）。
"""

from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.canonical_tables.page_item_tables import AnnotationItem
from v3server.canonical_tables.text_and_layer_tables import TextItem
from v3server.operations.operation_base import OpBase, Scope, page_obj, work_obj
from v3server.operations.row_snapshot import RowChanges
from v3server.v3_error_types import Invalid

SearchKind = Literal["text", "name", "setting", "annotation"]

# (探す物の種類, 表, 項目, 置き換えられるか)
SEARCH_FIELDS: list[tuple[SearchKind, Any, str, bool]] = [
    ("text", TextItem, "text", True),
    ("text", TextItem, "speaker", True),
    ("name", MaterialEntry, "name", True),
    ("setting", MaterialEntry, "traits", True),
    ("setting", MaterialEntry, "notes", True),
    ("setting", WorkPlan, "synopsis", True),
    ("setting", WorkPlan, "audience", True),
    ("setting", WorkPlan, "notes", True),
    ("annotation", AnnotationItem, "body", False),
]


async def _rows(session: AsyncSession, work_id: str, model, page_ids: list[str] | None):
    q = select(model).where(model.work_id == work_id)
    if hasattr(model, "removed"):
        q = q.where(model.removed.is_(False))
    if page_ids is not None:
        if not hasattr(model, "page_id"):
            return []
        q = q.where(model.page_id.in_(page_ids))
    return list((await session.execute(q)).scalars())


async def find_matches(session: AsyncSession, work_id: str, query: str, kinds: set[str],
                       page_ids: list[str] | None = None, replaceable_only: bool = False) -> list[tuple[Any, str]]:
    """(行, 項目) の一覧。大文字・小文字も含めて、そのままの文字で探す。"""
    if not query:
        raise Invalid("探す文字が空")
    out = []
    for kind, model, field, replaceable in SEARCH_FIELDS:
        if kind not in kinds or (replaceable_only and not replaceable):
            continue
        for obj in await _rows(session, work_id, model, page_ids):
            v = getattr(obj, field)
            if isinstance(v, str) and query in v:
                out.append((obj, field))
    return out


def match_view(obj, field: str) -> dict[str, Any]:
    return {"table": obj.__tablename__, "id": obj.id, "field": field, "value": getattr(obj, field),
            "page_id": getattr(obj, "page_id", None), "panel_id": getattr(obj, "panel_id", None)}


class ReplaceText(OpBase):
    type: Literal["replace_text"] = "replace_text"
    find: str
    replace: str
    kinds: list[Literal["text", "name", "setting"]]
    # 置き換えるページ（文字だけに効く）。無ければ作品の全部
    page_ids: list[str] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        if self.page_ids is not None and len(self.page_ids) == 1 and set(self.kinds) == {"text"}:
            return Scope("can_draw", page_obj(self.page_ids[0]), [("page", self.page_ids[0])],
                         page_tree=self.page_ids[0])
        # 当たる文字のあるページを全部ロックで確かめる（ほかの人が直している所は置き換えない）
        hit = await find_matches(session, work.id, self.find, set(self.kinds), self.page_ids, replaceable_only=True)
        pages = sorted({getattr(o, "page_id") for o, _ in hit if getattr(o, "page_id", None)})
        return Scope("can_manage", work_obj(work.id), [("page", p) for p in pages])

    async def apply(self, ctx):
        if self.find == self.replace:
            raise Invalid("置き換える前と後が同じ")
        matches = await find_matches(ctx.session, ctx.work.id, self.find, set(self.kinds), self.page_ids,
                                     replaceable_only=True)
        if not matches:
            raise Invalid("当たる所が無い")
        by_obj: dict[str, tuple[Any, dict[str, Any]]] = {}
        for obj, field in matches:
            new = getattr(obj, field).replace(self.find, self.replace)
            if field == "text" and getattr(obj, "ruby", None) and len(new) != len(obj.text):
                raise Invalid(f"文字 {obj.id} にルビがあり、置き換えで字数が変わる（ルビを先に直す）")
            by_obj.setdefault(f"{obj.__tablename__}:{obj.id}", (obj, {}))[1][field] = new
        rc = RowChanges(ctx)
        page_ids = set()
        for obj, changes in by_obj.values():
            pid = getattr(obj, "page_id", None)
            if pid:
                page_ids.add(pid)
            rc.change(obj, changes)
        return rc.inverse(sorted(page_ids), f"「{self.find}」を「{self.replace}」に置き換えた取り消し")
