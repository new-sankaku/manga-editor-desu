"""作業が使う上流の版（決めごと 5.4、調査 5.1 の7）。

版は上流の行の中身から作る短い指紋。作業を切り出したときの版を HarnessUnit.upstream_used に残し、
今の版と比べて違えば「古い」印を付ける（upstream_watch.py）。下流へ順に伝えるのではなく、各作業が自分の入力と比べる。

上流の鍵ごとに、変わったときの扱い（effect）を持つ。
- redraw：作り直しが要る（ネームのコマの中身・枠が変わった → そのコマの作画。企画・設定資料 → ネーム）
- recheck：検査だけやり直す（設定資料の人物を変えた → その人物が出るコマの検査結果。閾値を変えた → 検査結果）
"""

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.canonical_tables.threshold_and_finding_tables import Threshold
from v3server.canonical_tables.work_tree_tables import Panel

# 作画の検査が読む閾値の鍵（drawing_checks.py と同じ物を読む）
DRAWING_THRESHOLD_PREFIX = "harness.drawing."


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def _entry(version: str | None, effect: str, label: str) -> dict[str, Any]:
    return {"v": version, "effect": effect, "label": label}


def panel_people_names(panel: Panel) -> list[str]:
    return [p["name"] for p in (panel.content.get("people") or []) if isinstance(p, dict) and p.get("name")]


async def characters_by_name(session: AsyncSession, work_id: str) -> dict[str, MaterialEntry]:
    rows = (await session.execute(select(MaterialEntry).where(
        MaterialEntry.work_id == work_id, MaterialEntry.kind == "character", MaterialEntry.removed.is_(False),
        MaterialEntry.proposal_state == "adopted"))).scalars().all()
    return {m.name: m for m in rows}


def material_version(m: MaterialEntry | None) -> str | None:
    if m is None:
        return None
    return fingerprint({"name": m.name, "traits": m.traits, "clothes": m.clothes, "generation": m.generation})


async def drawing_thresholds_version(session: AsyncSession, work_id: str) -> str:
    rows = (await session.execute(select(Threshold).where(
        Threshold.work_id == work_id, Threshold.key.like(DRAWING_THRESHOLD_PREFIX + "%")))).scalars().all()
    return fingerprint(sorted((t.key, t.value, t.status) for t in rows))


async def panel_drawing_upstream(session: AsyncSession, work_id: str, panel_id: str) -> dict[str, dict[str, Any]]:
    panel = await session.get(Panel, panel_id)
    out: dict[str, dict[str, Any]] = {}
    if panel is None or panel.removed:
        out[f"panel:{panel_id}"] = _entry(None, "redraw", "コマ（消えた）")
        return out
    out[f"panel:{panel_id}"] = _entry(fingerprint({"content": panel.content, "frame": panel.frame, "role": panel.role}),
                                      "redraw", "ネームのコマ")
    chars = await characters_by_name(session, work_id)
    for name in panel_people_names(panel):
        m = chars.get(name)
        out[f"material:{name}"] = _entry(material_version(m), "recheck", f"設定資料の人物 {name}")
    out["thresholds:drawing"] = _entry(await drawing_thresholds_version(session, work_id), "recheck", "作画の検査の閾値")
    return out


async def name_draft_upstream(session: AsyncSession, work_id: str) -> dict[str, dict[str, Any]]:
    plan = (await session.execute(select(WorkPlan).where(WorkPlan.work_id == work_id))).scalar_one_or_none()
    chars = await characters_by_name(session, work_id)
    return {
        "plan": _entry(fingerprint({"synopsis": plan.synopsis, "audience": plan.audience, "exclusions": plan.exclusions})
                       if plan else None, "redraw", "企画"),
        "materials:characters": _entry(fingerprint(sorted((n, material_version(m)) for n, m in chars.items())),
                                       "redraw", "設定資料の人物"),
    }


async def upstream_of(session: AsyncSession, kind: str, work_id: str, target_id: str) -> dict[str, dict[str, Any]]:
    if kind == "panel_drawing":
        return await panel_drawing_upstream(session, work_id, target_id)
    if kind == "name_draft":
        return await name_draft_upstream(session, work_id)
    raise ValueError(f"知らない作業の種類: {kind}")


def stale_entries(used: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """使った版と今の版の違い。上流が増えた（コマに人物が足された）ときも違いとして返す。"""
    out = []
    for key in sorted(set(used) | set(current)):
        u, c = used.get(key), current.get(key)
        uv, cv = (u or {}).get("v"), (c or {}).get("v")
        if u is not None and c is not None and uv == cv:
            continue
        ref = c or u
        reason = (f"{ref['label']}が変わった" if u is not None and c is not None
                  else f"{ref['label']}が足された" if u is None else f"{ref['label']}が無くなった")
        out.append({"upstream_key": key, "used_version": uv, "current_version": cv, "effect": ref["effect"],
                    "reason": reason})
    return out
