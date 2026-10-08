"""文字の言語ごとの版（翻訳）を置く・変える・抜く操作（V3細部の決めごと 2.1・2.3）。

- 元の言語の文字は TextItem.text。ほかの言語は text_item_translations に、文字1つ×言語1つで1行
- 置ける人：作品の can_translate（作者・翻訳者。openfga/model.fga）。翻訳者はページの can_draw を持たないので、
  元の文字・フキダシの位置・話者・コマなど、訳文のほかは変えられない（update_text_item はページの can_draw が要る）
- 人が置いた・変えた項目には人の手の印が付く。AI（機械の翻訳）の変更が印の付いた項目に当たると、その項目は判断待ちに置く。
  言語ごとに別の行なので、印も判断待ちも言語ごとに分かれる（human_hand_guard.py をそのまま通す）
- 作品の言語（preferences.language）が決まっていないと、どれが元の言語か分からないので置けない
"""

from typing import Literal

from pydantic import Field
from sqlalchemy import select

from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import TextItem
from v3server.canonical_tables.translation_review_import_tables import (
    TextItemTranslation,
)
from v3server.operations.ai_involvement import (
    ROW_TASK,
    require_actor_may,
    require_ai_may_change_fields,
)
from v3server.operations.human_hand_guard import change_with_human_hand, remove_or_hold
from v3server.operations.operation_base import OpBase, Scope, get_in_work, work_obj
from v3server.v3_error_types import Invalid

# BCP 47 の形（en・ja・zh-Hans・pt-BR など）。中身が正しい言語かまでは見ない
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"
TRANSLATION_FIELDS = ("text", "writing_direction", "font_size_pt")


def _scope(item: TextItem) -> Scope:
    # 文字1つのロックにだけ当たる。ページを描いている人のロックでは止めない（訳文は絵と別に直せる）
    return Scope("can_translate", work_obj(item.work_id), [("item", item.id)])


def _source_language(work) -> str:
    lang = (work.preferences or {}).get("language")
    if not lang:
        raise Invalid("作品の言語（set_work_settings の preferences.language）を先に決める。どれが元の言語か分からない")
    return lang


class SetTextTranslation(OpBase):
    """訳文を置く（無ければ足す、あれば変える）。足すときは text が要る。"""

    type: Literal["set_text_translation"] = "set_text_translation"
    text_item_id: str
    language: str = Field(pattern=LANGUAGE_PATTERN)
    text: str | None = None
    writing_direction: Literal["vertical", "horizontal"] | None = None
    font_size_pt: float | None = Field(default=None, gt=0)
    # 人の手の印をこの値にする（取り消しと、人が印を外すとき）。AIは渡せない
    human_hand_fields: list[str] | None = None
    # 足すときに使う行の id（取り消しの取り消しで同じ行に戻すため）
    id: str = Field(default_factory=new_id)

    ai_may_submit = True

    async def scope(self, session, work):
        item = await get_in_work(session, TextItem, self.text_item_id, work.id)
        return _scope(item)

    async def apply(self, ctx):
        if self.language == _source_language(ctx.work):
            raise Invalid(f"{self.language} は作品の言語。元の文字は update_text_item で変える")
        item = await ctx.session.get(TextItem, self.text_item_id)
        row = (await ctx.session.execute(select(TextItemTranslation).where(
            TextItemTranslation.text_item_id == item.id, TextItemTranslation.language == self.language))).scalar()
        changes = self.model_dump(include=set(TRANSLATION_FIELDS), exclude_unset=True)
        if row is None:
            if self.text is None:
                raise Invalid("訳文を足すときは text が要る")
            require_actor_may(ctx.actor, ctx.work, ROW_TASK["text_item_translations"], "decide")
            require_ai_may_change_fields(ctx.actor, ctx.work, "text_item_translations", set(changes))
            marks = sorted(k for k, v in changes.items() if v is not None) if ctx.actor.kind == "human" else []
            ctx.session.add(TextItemTranslation(
                id=self.id, work_id=ctx.work.id, page_id=item.page_id, text_item_id=item.id, language=self.language,
                human_hand_fields=marks, removed=False, **changes))
            return {"type": "set_text_translation_removed", "id": self.id, "removed": True}
        if row.removed:
            raise Invalid("抜いた訳文は set_text_translation_removed で戻してから変える")
        if not changes and self.human_hand_fields is None:
            raise Invalid("変える項目がない")
        if "text" in changes and changes["text"] is None:
            raise Invalid("訳文を空にするときは set_text_translation_removed で抜く")
        before = change_with_human_hand(ctx, row, changes, self.human_hand_fields)
        return {"type": self.type, "text_item_id": self.text_item_id, "language": self.language, **before}


class SetTextTranslationRemoved(OpBase):
    type: Literal["set_text_translation_removed"] = "set_text_translation_removed"
    id: str
    removed: bool

    ai_may_submit = True

    async def scope(self, session, work):
        row = await get_in_work(session, TextItemTranslation, self.id, work.id)
        item = await session.get(TextItem, row.text_item_id)
        return _scope(item)

    async def apply(self, ctx):
        row = await ctx.session.get(TextItemTranslation, self.id)
        require_actor_may(ctx.actor, ctx.work, ROW_TASK["text_item_translations"], "decide")
        before = row.removed
        if not remove_or_hold(ctx, row, self.removed):
            return None
        return {"type": self.type, "id": self.id, "removed": before}
