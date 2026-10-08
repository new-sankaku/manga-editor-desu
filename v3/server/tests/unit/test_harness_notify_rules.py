"""知らせの決まり（harness_notify.rules）を、出来事の形だけで確かめる。"""

import pytest

from v3server.harness.harness_notify import NotificationSettings, rules


def kinds(out):
    return [(n["kind"], n["level"]) for n in out]


def test_判断待ちになった作業と止まった作業を知らせる():
    assert kinds(rules("unit", {"unit_id": "u", "status": "awaiting_review", "attempt": 1}, None)) == [("generated", "info")]
    out = rules("unit", {"unit_id": "u", "status": "blocked", "attempt": 1, "stop_reason": "閾値が未設定"}, None)
    assert kinds(out) == [("failed", "warn")] and "閾値が未設定" in out[0]["title"]
    assert rules("unit", {"unit_id": "u", "status": "running", "attempt": 1}, None) == []


def test_止まった理由が変われば別の知らせ_同じなら同じ鍵():
    a = rules("unit", {"unit_id": "u", "status": "stopped", "attempt": 2, "stop_reason": "上限回数"}, None)
    b = rules("unit", {"unit_id": "u", "status": "stopped", "attempt": 2, "stop_reason": "上限回数"}, None)
    c = rules("unit", {"unit_id": "u", "status": "stopped", "attempt": 2, "stop_reason": "予算"}, None)
    assert a[0]["dedupe"] == b[0]["dedupe"] != c[0]["dedupe"]


def test_予算に近づいた知らせは割合を人が決めたときだけ():
    p = {"unit_id": "u", "status": "running", "attempt": 1, "cost_used": 8, "budget_cost": 10}
    assert rules("unit", p, None) == []
    s = NotificationSettings(kinds=["budget_near"], budget_near_ratio=0.8)
    assert kinds(rules("unit", p, s)) == [("budget_near", "warn")]
    assert rules("unit", {**p, "cost_used": 7.9}, s) == []


def test_判断待ちの知らせは決めた回数から上げる():
    s = NotificationSettings(kinds=["review_overdue"], escalate_after_notices=3)
    lv = [rules("review_notice", {"unit_id": "u", "attempt": 1, "waited_notices": n}, s)[0]["level"] for n in (1, 2, 3)]
    assert lv == ["warn", "warn", "escalated"]
    # 回数を決めていなければ上げない
    assert rules("review_notice", {"unit_id": "u", "attempt": 1, "waited_notices": 9}, None)[0]["level"] == "warn"


def test_工程の承認待ちを知らせる():
    out = rules("stage", {"stage_run_id": "r", "stage": "S4", "status": "awaiting_review"}, None)
    assert kinds(out) == [("stage_review", "info")]


def test_知らない種類と範囲の外の割合は断る():
    with pytest.raises(ValueError, match="知らない知らせの種類"):
        NotificationSettings(kinds=["mail"])
    with pytest.raises(ValueError):
        NotificationSettings(kinds=[], budget_near_ratio=1.5)
    with pytest.raises(ValueError):
        NotificationSettings(kinds=[], webhooks=[{"url": "ftp://x"}])
