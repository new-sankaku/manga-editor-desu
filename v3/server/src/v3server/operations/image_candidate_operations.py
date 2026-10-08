"""候補の絵を採る・却下する（V3画像生成の機能と画面）。

- AdoptImage：コマ（か、コマの層）の絵を別の版に替える。置き場は今の置き場から引き継ぐ（image_placement_carry.py）。
  中身は UpdatePanel・UpdatePanelLayer をそのまま当てるので、人の手の印・ロック・取り消しは同じにかかる
  （取り消すと前の絵と置き場に戻る）。候補を採るのも、前の版に戻すのも同じ操作。採るのは人だけ
- SetImageDiscarded：候補を却下する・却下を外す。消さない（一覧で隠すだけ）。人だけ。取り消せる
"""
from __future__ import annotations

from typing import Literal

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.text_and_layer_tables import PanelLayer
from v3server.canonical_tables.work_tree_tables import Panel
from v3server.operations.image_placement_carry import Version, frame_bbox, geometry_to_parent, placement_for
from v3server.operations.operation_base import OpBase, Scope, get_in_work, page_obj
from v3server.operations.text_and_layer_operations import UpdatePanelLayer
from v3server.operations.work_tree_operations import UpdatePanel
from v3server.v3_error_types import Invalid

# 版の鎖をたどる上限（循環や長すぎる鎖で止まらないように。数の決まりで、見た目の閾値ではない）
CHAIN_LIMIT = 200


async def load_versions(session, ids: list[str]) -> dict[str, Version]:
    """ids の版と、その祖先（based_on）をたどって読む。"""
    out: dict[str, Version] = {}
    sizes: dict[str, ImageFile] = {}
    for start in ids:
        cur = await session.get(ImageFile, start)
        n = 0
        while cur is not None and cur.id not in sizes and n < CHAIN_LIMIT:
            sizes[cur.id] = cur
            cur = await session.get(ImageFile, cur.based_on_image_id) if cur.based_on_image_id else None
            n += 1
    for img in sizes.values():
        parent = sizes.get(img.based_on_image_id) if img.based_on_image_id else None
        g = geometry_to_parent(img.details, (img.width, img.height),
                               (parent.width, parent.height) if parent else None) if parent else None
        out[img.id] = Version(img.id, img.width, img.height, img.based_on_image_id, g)
    return out


class AdoptImage(OpBase):
    type: Literal["adopt_image"] = "adopt_image"
    panel_id: str
    image_id: str
    # 層に採るときの層。無ければコマの絵
    layer_id: str | None = None

    async def scope(self, session, work):
        panel = await get_in_work(session, Panel, self.panel_id, work.id)
        locks = [("page", panel.page_id), ("panel", panel.id)]
        if self.layer_id is not None:
            locks.append(("item", self.layer_id))
        return Scope("can_draw", page_obj(panel.page_id), locks)

    async def apply(self, ctx):
        panel = await ctx.session.get(Panel, self.panel_id)
        img = await get_in_work(ctx.session, ImageFile, self.image_id, ctx.work.id)
        if img.discarded:
            raise Invalid("却下した絵は採れない（先に却下を外す）")
        if self.layer_id is not None:
            layer = await get_in_work(ctx.session, PanelLayer, self.layer_id, ctx.work.id)
            if layer.panel_id != panel.id:
                raise Invalid(f"層 {layer.id} はコマ {panel.id} の物ではない")
            cur_id, cur_pl = layer.image_id, layer.placement
            if cur_id is None:
                cur_id, cur_pl = panel.image_id, panel.image_placement
        else:
            cur_id, cur_pl = panel.image_id, panel.image_placement
        if cur_id == img.id and self.layer_id is None:
            raise Invalid("もうこの絵になっている")
        versions = await load_versions(ctx.session, [i for i in (cur_id, img.id) if i])
        placement, _ = placement_for(cur_pl, versions.get(cur_id) if cur_id else None, versions[img.id], versions,
                                     frame_bbox(panel.frame))
        if self.layer_id is not None:
            return await UpdatePanelLayer(id=self.layer_id, image_id=img.id, placement=placement).apply(ctx)
        return await UpdatePanel(id=panel.id, image_id=img.id, image_placement=placement).apply(ctx)


class SetImageDiscarded(OpBase):
    type: Literal["set_image_discarded"] = "set_image_discarded"
    image_id: str
    discarded: bool

    async def scope(self, session, work):
        img = await get_in_work(session, ImageFile, self.image_id, work.id)
        if img.page_id is None:
            raise Invalid("ページに付いていない絵は、候補として却下できない")
        return Scope("can_draw", page_obj(img.page_id), [("page", img.page_id)])

    async def apply(self, ctx):
        img = await ctx.session.get(ImageFile, self.image_id)
        if img.discarded == self.discarded:
            raise Invalid("すでにその状態")
        in_use = [p.id for p in (await ctx.session.execute(
            Panel.__table__.select().where(Panel.image_id == img.id, Panel.removed.is_(False)))).all()]
        if self.discarded and in_use:
            raise Invalid(f"コマ {in_use[0]} で使っている絵は却下できない")
        img.discarded = self.discarded
        return {**self.model_dump(), "discarded": not self.discarded}
