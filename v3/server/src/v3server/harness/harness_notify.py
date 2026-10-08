"""ハーネスの知らせ（決めごと 17章）。

- 出す所は1か所：ハーネスの出来事を足す所（harness_record.add_event）が、出来事ごとに rules() を通す。出来事を足す
  所はどの段・どの口からでもここを通るので、知らせの漏れが出ない
- 出す先
  - アプリの中の一覧（harness_notifications）。作品の決まりの行が無ければ、全部の種類をここにだけ出す
  - 外：作品の決まり（harness_notification_settings.webhooks）で入れた Webhook にだけ出す。既定では送らない
    （自動で走る機能は既定で止める。決めごと 17章）。送るのは send_pending_forever（ハーネスの作業者の中で回す）
  - メール：送る所は作っていない。CHANNEL_SENDERS に "email" の送り手を足し、決まりの検査（NotificationSettings）で
    受けるようにすれば、同じ届けた記録（harness_notification_deliveries）と送り直しで動く
  - ブラウザの知らせ：知らせを足すと出来事 notification も足すので、画面は SSE で受けて出す
- 判断待ちが長い（review_notice）：届いた回数が作品の決まりの escalate_after_notices 以上なら level を escalated に
  上げ、Webhook の種類の絞り込みを越えて全部の送り先へ送る
- 招いた人の赤入れ・締切（19章）の知らせは、ハーネスの出来事に無いので出していない（未実装）
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.harness_tables import (
    HarnessEvent,
    HarnessNotification,
    HarnessNotificationDelivery,
    HarnessNotificationSetting,
)
from v3server.canonical_tables.table_base import new_id
from v3server.database_engine import get_sessionmaker

log = logging.getLogger(__name__)

KINDS = {
    "generated": "候補ができて人の判断を待っている",
    "failed": "作業が止まった・失敗した（閾値未設定・上限・エラー・断られた）",
    "budget_near": "作業の費用が予算の上限に近づいた",
    "review_overdue": "判断待ちが長い",
    "stage_review": "工程の承認を待っている",
}
STOP_STATUSES = ("stopped", "blocked", "failed")
# Webhook の送り直し：回数の上限と、間（秒。回ごとに倍）
SEND_ATTEMPTS = 5
SEND_BACKOFF_SECONDS = 5
SEND_TIMEOUT_SECONDS = 10
POLL_SECONDS = 1.0


class Webhook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    # 本体の HMAC-SHA256 の署名に使う鍵（X-V3-Signature）。無ければ署名しない。決まりを置き直すとき、書かなければ
    # 同じ URL の今の鍵を使い、空の文字なら外す（読み出しの口は鍵を返さないため）
    secret: str | None = None
    # 送る種類（無ければ作品の kinds と同じ）
    kinds: list[str] | None = None


class NotificationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kinds: list[str]
    webhooks: list[Webhook] = Field(default_factory=list)
    # 判断待ちの知らせが何回目から escalated にするか（無ければ上げない）
    escalate_after_notices: int | None = Field(default=None, ge=1)
    # 費用がこの割合に達したら budget_near（無ければ出さない。割合は人が決める）
    budget_near_ratio: float | None = Field(default=None, gt=0, lt=1)

    @model_validator(mode="after")
    def _known_kinds(self) -> "NotificationSettings":
        unknown = {*self.kinds, *(k for w in self.webhooks for k in (w.kinds or []))} - set(KINDS)
        if unknown:
            raise ValueError(f"知らない知らせの種類: {sorted(unknown)}（{', '.join(KINDS)}）")
        return self


def rules(kind: str, payload: dict[str, Any], s: NotificationSettings | None) -> list[dict[str, Any]]:
    """出来事1つから出す知らせ（種類・重さ・題・同じ物を2回出さない鍵）。"""
    out = []
    uid, status, attempt = payload.get("unit_id"), payload.get("status"), payload.get("attempt")
    if kind == "unit" and uid and status == "awaiting_review":
        out.append({"kind": "generated", "level": "info", "title": f"候補ができました（{attempt}回目）",
                    "dedupe": f"{uid}:generated:{attempt}"})
    if kind == "unit" and uid and status in STOP_STATUSES:
        reason = payload.get("stop_reason") or ""
        out.append({"kind": "failed", "level": "warn", "title": f"作業が止まりました：{reason}"[:200],
                    "dedupe": f"{uid}:{status}:{attempt}:" + hashlib.sha256(reason.encode()).hexdigest()[:12]})
    if (kind in ("unit", "step") and uid and s is not None and s.budget_near_ratio is not None
            and payload.get("budget_cost") and payload.get("cost_used") is not None
            and payload["cost_used"] >= s.budget_near_ratio * float(payload["budget_cost"])):
        out.append({"kind": "budget_near", "level": "warn",
                    "title": f"費用が予算の {s.budget_near_ratio:.0%} に達しました（{payload['cost_used']} / "
                             f"{payload['budget_cost']}）", "dedupe": f"{uid}:budget_near"})
    if kind == "review_notice" and uid:
        n = int(payload.get("waited_notices") or 0)
        escalate = s is not None and s.escalate_after_notices is not None and n >= s.escalate_after_notices
        out.append({"kind": "review_overdue", "level": "escalated" if escalate else "warn",
                    "title": f"判断待ちが長くなっています（知らせ {n} 回目）", "dedupe": f"{uid}:overdue:{attempt}:{n}"})
    if kind == "stage" and status == "awaiting_review" and payload.get("stage_run_id"):
        out.append({"kind": "stage_review", "level": "info", "title": f"{payload.get('stage')} の工程の承認を待っています",
                    "dedupe": f"{payload['stage_run_id']}:stage_review"})
    return out


async def settings_of(session: AsyncSession, work_id: str) -> NotificationSettings | None:
    row = await session.get(HarnessNotificationSetting, work_id)
    if row is None:
        return None
    return NotificationSettings(kinds=row.kinds, webhooks=row.webhooks, escalate_after_notices=row.escalate_after_notices,
                                budget_near_ratio=row.budget_near_ratio)


async def on_event(session: AsyncSession, event: HarnessEvent) -> None:
    """出来事を足した直後に呼ぶ（add_event の中）。知らせを足し、外への届けを待ちに積む。"""
    if event.kind == "notification":
        return
    # 決まりの行を読む前に、決まりに関係なく出す物があるかを見る（多くの出来事は何も出さない）
    if not rules(event.kind, event.payload, None) and event.kind not in ("unit", "step"):
        return
    s = await settings_of(session, event.work_id)
    shown = set(s.kinds) if s is not None else set(KINDS)
    for n in rules(event.kind, event.payload, s):
        if n["kind"] not in shown and n["level"] != "escalated":
            continue
        res = await session.execute(insert(HarnessNotification).values(
            id=new_id(), work_id=event.work_id, kind=n["kind"], level=n["level"], title=n["title"],
            body={"event_kind": event.kind, **event.payload}, stage_run_id=event.stage_run_id, unit_id=event.unit_id,
            event_id=event.id, dedupe_key=n["dedupe"]).on_conflict_do_nothing(index_elements=["dedupe_key"])
            .returning(HarnessNotification.id))
        nid = res.scalar_one_or_none()
        if nid is None:
            continue
        for w in (s.webhooks if s is not None else []):
            if n["level"] == "escalated" or n["kind"] in (w.kinds if w.kinds is not None else s.kinds):
                session.add(HarnessNotificationDelivery(notification_id=nid, channel="webhook", target=str(w.url),
                                                        status="pending", attempts=0))
        session.add(HarnessEvent(work_id=event.work_id, stage_run_id=event.stage_run_id, unit_id=event.unit_id,
                                 kind="notification", payload={"id": nid, **{k: n[k] for k in ("kind", "level", "title")}}))


# ---------------------------------------------------------------- 外へ届ける


async def _send_webhook(target: str, body: dict[str, Any], s: NotificationSettings) -> None:
    data = json.dumps(body, ensure_ascii=False, default=str).encode()
    headers = {"Content-Type": "application/json"}
    hook = next((w for w in s.webhooks if str(w.url) == target), None)
    if hook is None:
        raise RuntimeError("作品の決まりから送り先が外された")
    if hook.secret:
        headers["X-V3-Signature"] = "sha256=" + hmac.new(hook.secret.encode(), data, hashlib.sha256).hexdigest()
    async with httpx.AsyncClient(timeout=SEND_TIMEOUT_SECONDS) as client:
        r = await client.post(target, content=data, headers=headers)
        r.raise_for_status()


CHANNEL_SENDERS = {"webhook": _send_webhook}


def now() -> datetime:
    return datetime.now(UTC)


async def send_pending_once(limit: int = 20) -> int:
    """届けていない知らせを送る。送れた・諦めた数を返す。"""
    done = 0
    async with get_sessionmaker()() as session:
        rows = (await session.execute(
            select(HarnessNotificationDelivery, HarnessNotification)
            .join(HarnessNotification, HarnessNotification.id == HarnessNotificationDelivery.notification_id)
            .where(HarnessNotificationDelivery.status == "pending", HarnessNotificationDelivery.next_at <= now())
            .order_by(HarnessNotificationDelivery.next_at).limit(limit)
            .with_for_update(skip_locked=True, of=HarnessNotificationDelivery))).all()
        for d, n in rows:
            s = await settings_of(session, n.work_id)
            body = {"id": n.id, "work_id": n.work_id, "kind": n.kind, "level": n.level, "title": n.title,
                    "unit_id": n.unit_id, "stage_run_id": n.stage_run_id, "created_at": n.created_at.isoformat(),
                    "body": n.body}
            d.attempts += 1
            try:
                if s is None:
                    raise RuntimeError("作品の知らせの決まりが消された")
                await CHANNEL_SENDERS[d.channel](d.target, body, s)
                d.status, d.sent_at, d.last_error = "sent", now(), None
                done += 1
            except Exception as e:  # noqa: BLE001  送り先の失敗は記録して送り直す（作業は止めない）
                d.last_error = f"{type(e).__name__}: {e}"[:500]
                if d.attempts >= SEND_ATTEMPTS:
                    d.status = "failed"
                    done += 1
                else:
                    d.next_at = now() + timedelta(seconds=SEND_BACKOFF_SECONDS * 2 ** (d.attempts - 1))
        await session.commit()
    return done


async def send_pending_forever() -> None:
    while True:
        try:
            await send_pending_once()
        except Exception:  # noqa: BLE001
            log.exception("知らせを外へ届けられない")
        await asyncio.sleep(POLL_SECONDS)
