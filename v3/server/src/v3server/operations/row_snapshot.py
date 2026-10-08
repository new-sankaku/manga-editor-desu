"""いくつもの行を1回で変える操作（コマを分ける・合わせる・型を当てる・置き換え・ペン・PSD の戻しなど）を、1回で取り消すための部品。

- RowChanges：操作の中で行を変える・足すときに使う。変える前の値を覚え、取り消しの操作（RestoreRows）を組む。
  項目を変えるのは human_hand_guard.change_with_human_hand を通す（人の手の印・判断待ち・動かさない・AIの関与が同じにかかる）
- RestoreRows：覚えた値に戻す操作。戻す前の値を覚えて、同じ形の操作を取り消しとして返すので、取り消しの取り消しもできる

戻す操作は人だけが出せる（AIが出すと、人の手の印の付いた値を前の値に戻せてしまうため）。
"""

from typing import Any, Literal

from v3server.canonical_tables.episode_plan_tables import EpisodePlan, Foreshadowing
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.canonical_tables.page_item_tables import (
    AnnotationItem,
    PageItem,
    PanelTemplate,
    PenStroke,
)
from v3server.canonical_tables.text_and_layer_tables import (
    HeldAiChange,
    PanelLayer,
    ProtectedRegion,
    TextItem,
)
from v3server.canonical_tables.translation_review_import_tables import ElementGenerationSetting, TextItemTranslation
from v3server.canonical_tables.work_tree_tables import Page, Panel
from v3server.operations.human_hand_guard import change_with_human_hand, json_value, refuse_if_fixed
from v3server.operations.operation_base import ApplyContext, OpBase, Scope, page_obj, work_obj
from v3server.v3_error_types import Invalid, NotFound

ROW_MODELS = {m.__tablename__: m for m in (Page, Panel, TextItem, PanelLayer, ProtectedRegion, HeldAiChange, PageItem,
                                            AnnotationItem, PenStroke, PanelTemplate, MaterialEntry, WorkPlan,
                                            TextItemTranslation, ElementGenerationSetting, EpisodePlan,
                                            Foreshadowing)}


class RowChanges:
    def __init__(self, ctx: ApplyContext):
        self.ctx = ctx
        self.before: dict[str, dict[str, dict[str, Any]]] = {}

    def _remember(self, obj, fields) -> None:
        row = self.before.setdefault(obj.__tablename__, {}).setdefault(obj.id, {})
        for f in fields:
            row.setdefault(f, json_value(getattr(obj, f)))

    def change(self, obj, changes: dict[str, Any], mark_as_human: bool | None = None) -> None:
        """人の手の印を付けて変える（AIなら印を外す）。AIが人の手の印の付いた項目に当たったら、その項目は判断待ちに置いて
        残りを変える（human_hand_guard.py）。"""
        if not changes:
            return
        self._remember(obj, [*changes, "human_hand_fields"])
        change_with_human_hand(self.ctx, obj, changes, mark_as_human=mark_as_human)

    def set_plain(self, obj, changes: dict[str, Any]) -> None:
        """人の手の印を持たない表の項目（状態・抜いた印）を変える。"""
        refuse_if_fixed(obj)
        self._remember(obj, list(changes))
        for k, v in changes.items():
            setattr(obj, k, v)

    def renumber(self, obj, changes: dict[str, Any]) -> None:
        """番号を数え直す（間にコマが入った・抜けた分のずれ）。物を動かすのではないので、人の手の印も「動かさない」も見ない。"""
        self._remember(obj, list(changes))
        for k, v in changes.items():
            setattr(obj, k, v)

    def bump_strokes(self, layer) -> None:
        """層の線の版を1つ進める。版は戻さない（取り消しでも進める）ので、同じ版の数が別の線の組を指すことはない。"""
        refuse_if_fixed(layer)
        layer.stroke_revision += 1

    def remove(self, obj) -> None:
        refuse_if_fixed(obj)
        self._remember(obj, ["removed"])
        obj.removed = True

    def created(self, obj) -> None:
        self.ctx.session.add(obj)
        self.before.setdefault(obj.__tablename__, {})[obj.id] = {"removed": True}

    def inverse(self, page_ids: list[str], label: str) -> dict[str, Any]:
        return {"type": "restore_rows", "label": label, "page_ids": sorted(set(page_ids)), "snapshot": self.before}


class RestoreRows(OpBase):
    """覚えた値に行を戻す（ほかの操作の取り消し）。"""

    type: Literal["restore_rows"] = "restore_rows"
    # 何の取り消しか（出来事の一覧に出す）
    label: str
    # 当たるページ。1ページならそのページを描ける人、2ページ以上かページに属さない行は作者。赤入れだけなら赤入れを付けられる人
    page_ids: list[str]
    snapshot: dict[str, dict[str, dict[str, Any]]]

    async def scope(self, session, work):
        for table in self.snapshot:
            if table not in ROW_MODELS:
                raise Invalid(f"戻せない表: {table}")
        locks = [("page", p) for p in self.page_ids]
        if set(self.snapshot) == {"annotation_items"}:
            # 赤入れだけなら、赤入れを付けられる人が戻せる
            return Scope("can_comment", work_obj(work.id), locks)
        if len(self.page_ids) == 1 and not ({"material_entries", "work_plans", "panel_templates", "episode_plans", "foreshadowings"} & set(self.snapshot)):
            return Scope("can_draw", page_obj(self.page_ids[0]), locks, page_tree=self.page_ids[0])
        return Scope("can_manage", work_obj(work.id), locks)

    async def apply(self, ctx):
        if ctx.actor.kind != "human":
            raise Invalid("まとめて戻す操作は人だけが出せる")
        now: dict[str, dict[str, dict[str, Any]]] = {}
        stroke_layers: set[str] = set()
        for table, rows in self.snapshot.items():
            model = ROW_MODELS[table]
            for rid, values in rows.items():
                obj = await ctx.session.get(model, rid)
                if obj is None or obj.work_id != ctx.work.id:
                    raise NotFound(f"{table}:{rid}")
                current = {k: json_value(getattr(obj, k)) for k in values}
                if current == values:
                    continue
                refuse_if_fixed(obj)
                now.setdefault(table, {})[rid] = current
                for k, v in values.items():
                    setattr(obj, k, v)
                if table == "pen_strokes":
                    stroke_layers.add(obj.layer_id)
        for lid in sorted(stroke_layers):
            # 線が戻ったので、層の絵（控え）は古くなる
            (await ctx.session.get(PanelLayer, lid)).stroke_revision += 1
        return {"type": self.type, "label": self.label, "page_ids": self.page_ids, "snapshot": now}
