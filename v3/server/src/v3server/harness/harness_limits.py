"""作業の上限・予算・完成条件と、止まる理由の決め方（設計 10章）。

上限の値はどれも作業を頼む人が渡す。サーバーに隠れた既定値を置かない（CLAUDE.md）。
設計に数のある物（エラーが3回続いたら止める・同じ失敗が2回で文脈を捨てる）だけは、その数を初めの値として画面が欄に入れる
（INITIAL。サーバーは使わない）。
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# 完成条件の名前
COMPLETION = {
    "checks_pass": "検査を通った候補がある",
    "evaluator_pick": "評価役が1枚を選んだ",
    "human_approve": "人が採用した",
}

# 画面が欄に入れておく値（設計 10章の6 の数）。サーバーは使わない
INITIAL: dict[str, Any] = {"error_stop": 3, "same_failure_restart": 2}


class UnitLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 品質の作り直しの回数の上限（1回 = 文脈→生成→検査→評価）
    max_attempts: int = Field(ge=1, le=50)
    # 1回に作る候補の数（設計 8.1 の k）
    candidates_per_attempt: int = Field(ge=1, le=8)
    # 費用の上限（呼び出しの記録の費用の合計。つなぎ先の単価の単位）
    budget_cost: float = Field(ge=0)
    # 時間の上限（段を動かした秒の合計。判断待ちと一時停止は数えない）
    budget_seconds: float = Field(gt=0)
    # エラーが続いたら止める回数（設計 10章の6：3回）
    error_stop: int = Field(ge=1)
    # 同じ失敗がこの回数続いたら、文脈を捨てて出直す（設計 10章の6：2回）
    same_failure_restart: int = Field(ge=1)
    # 直させる段の回数の上限（1回の生成の中で。0 なら直させず、検査で全部落ちたらすぐ全部を作り直す）。
    # 上限に達しても落ちたままなら、全部を作り直すことを出来事（fix_fallback）に書いてから作り直す
    max_fix_rounds: int = Field(ge=0, le=5)
    # 評価役に同じ問いを何回聞くか。答えが割れたら「割れた」として数える
    eval_repeats: int = Field(ge=1, le=5)
    # 評価が割れた回数がこれに達したら止める
    disagreement_stop: int = Field(ge=1)
    # 判断待ちがこの秒を超えたら、知らせを出す（締切。決めごと 19章）。止めはしない
    review_notice_seconds: float = Field(gt=0)
    # 通信の失敗の送り直し（RetryPolicy。品質の作り直しとは別。決めごと 4.5）
    resend_limit: int = Field(ge=0, le=10)


class StageLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: UnitLimits
    # 同時に回す作業の数
    max_parallel_units: int = Field(ge=1, le=64)
    completion: list[str] = Field(min_length=1)


def check_completion(names: list[str]) -> None:
    unknown = [n for n in names if n not in COMPLETION]
    if unknown:
        raise ValueError(f"知らない完成条件: {unknown}（{', '.join(COMPLETION)}）")


def check_limit_change(limits: dict[str, Any], used: dict[str, float], new: dict[str, Any]) -> dict[str, Any]:
    """走っている作業の上限を変える。使った分より小さくはできない。変えた後の上限を返す（Update の検証から呼ぶ）。"""
    unknown = set(new) - set(UnitLimits.model_fields)
    if unknown:
        raise ValueError(f"知らない上限: {sorted(unknown)}")
    merged = UnitLimits.model_validate({**limits, **new}).model_dump()
    if merged["max_attempts"] < used["attempt"]:
        raise ValueError(f"回数の上限 {merged['max_attempts']} が、もう使った {used['attempt']} 回より小さい")
    if merged["budget_cost"] < used["cost"]:
        raise ValueError(f"費用の上限 {merged['budget_cost']} が、もう使った {used['cost']} より小さい")
    if merged["budget_seconds"] < used["seconds"]:
        raise ValueError(f"時間の上限 {merged['budget_seconds']} 秒が、もう使った {used['seconds']:.0f} 秒より小さい")
    return merged


def stop_reason(limits: dict[str, Any], s: dict[str, Any]) -> str | None:
    """次の回を始める前に、止まる理由があるかを見る。s は作業の流れの状態（unit_workflow.py）。"""
    if s.get("refused"):
        return f"内容で断られた（送り直さない）: {s['refused']}"
    if s["errors_in_row"] >= limits["error_stop"]:
        return f"エラーが{s['errors_in_row']}回続いた"
    if s["disagreements"] >= limits["disagreement_stop"]:
        return f"評価役の答えが{s['disagreements']}回割れた"
    if s["attempt"] >= limits["max_attempts"]:
        return f"上限回数（{limits['max_attempts']}回）に達した"
    if s["cost_used"] >= limits["budget_cost"]:
        return f"予算（費用 {s['cost_used']}/{limits['budget_cost']}）に達した"
    if s["seconds_used"] >= limits["budget_seconds"]:
        return f"予算（時間 {s['seconds_used']:.0f}/{limits['budget_seconds']:.0f} 秒）に達した"
    return None


def note_failure(s: dict[str, Any], signature: str, limits: dict[str, Any]) -> bool:
    """品質の失敗を数える。同じ失敗が same_failure_restart 回続いたら True（次の回は文脈を捨てて出直す）。"""
    if s.get("last_failure") == signature:
        s["same_failure"] += 1
    else:
        s["last_failure"], s["same_failure"] = signature, 1
    s["failures"].append(signature)
    if s["same_failure"] >= limits["same_failure_restart"]:
        s["same_failure"] = 0
        s["last_failure"] = None
        return True
    return False
