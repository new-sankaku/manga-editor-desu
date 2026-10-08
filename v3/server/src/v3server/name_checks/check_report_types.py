"""検査の結果と指摘の形。合格は1行、失敗だけ詳しく（どのページ・どのコマ・何の値）。
閾値は渡された辞書から読む。コードに値を書かない（V3ハーネス設計 7.1）。"""
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel

# 合格・不合格：判定した。閾値未設定：閾値が渡されていないので値だけ返す。
# データなし：計算に要る値（枠・人物の位置・吹き出しの位置など）がネームにまだ無い
CheckStatus = Literal["合格", "不合格", "閾値未設定", "データなし"]
Thresholds = Mapping[str, float]
Bound = Literal["max", "min"]


class Finding(BaseModel):
    """指摘1つ。どこで・何の値か。"""

    page: int | None = None
    panel: int | None = None
    balloon: int | None = None
    value: float | int | str | None = None
    note: str

    def line(self) -> str:
        where = []
        if self.page is not None:
            where.append(f"{self.page}ページ")
        if self.panel is not None:
            where.append(f"コマ{self.panel}")
        if self.balloon is not None:
            where.append(f"吹き出し{self.balloon + 1}")
        head = "・".join(where)
        val = "" if self.value is None else f"（値 {self.value}）"
        return f"{head}：{self.note}{val}" if head else f"{self.note}{val}"


class CheckResult(BaseModel):
    """検査1つの結果。value は検査全体を表す値（最大・最小・割合など）。"""

    check_id: str
    title: str
    status: CheckStatus
    value: float | int | str | None = None
    # 判定に使った閾値の鍵と値。閾値の要らない検査は None
    threshold_key: str | None = None
    threshold_value: float | None = None
    findings: list[Finding] = []

    def report_lines(self) -> list[str]:
        if self.status == "データなし":
            return [f"[{self.status}] {self.title}：{self.value}"]
        val = "" if self.value is None else f" 値 {self.value}"
        lim = "" if self.threshold_value is None else f" 閾値 {self.threshold_key}={self.threshold_value}"
        head = f"[{self.status}] {self.title}{val}{lim}"
        if self.status != "不合格":
            return [head]
        return [head] + [f"  - {f.line()}" for f in self.findings]


class CheckReport(BaseModel):
    results: list[CheckResult]

    def report_lines(self) -> list[str]:
        return [line for r in self.results for line in r.report_lines()]

    def by_id(self, check_id: str) -> CheckResult:
        for r in self.results:
            if r.check_id == check_id:
                return r
        raise KeyError(check_id)


def fixed_rule_result(check_id: str, title: str, findings: list[Finding], value: float | int | str | None = None) -> CheckResult:
    """閾値の要らない検査。指摘が無ければ合格。"""
    return CheckResult(check_id=check_id, title=title, status="不合格" if findings else "合格", value=value, findings=findings)


def no_data_result(check_id: str, title: str, reason: str) -> CheckResult:
    """計算に要る値がネームに無い。合否を出さない。"""
    return CheckResult(check_id=check_id, title=title, status="データなし", value=reason)


def limit_result(check_id: str, title: str, thresholds: Thresholds, key: str, bound: Bound,
                 value: float | int | None, measured: list[tuple[float, Finding]]) -> CheckResult:
    """閾値の要る検査。measured は項目ごとの（丸める前の値, 指摘の形）。
    閾値が無ければ「閾値未設定」で値だけ返す。あれば、閾値を外れた項目だけを指摘にする。
    bound が "max" なら値が閾値を超えたら外れ、"min" なら閾値を下回ったら外れ。
    測る対象が無い（例：段に1コマずつしか無く縦線が無い）ときは value を None、measured を空で渡す。"""
    if key not in thresholds:
        return CheckResult(check_id=check_id, title=title, status="閾値未設定", value=value, threshold_key=key)
    lim = float(thresholds[key])
    bad = [f for v, f in measured if (v > lim if bound == "max" else v < lim)]
    return CheckResult(check_id=check_id, title=title, status="不合格" if bad else "合格", value=value,
                       threshold_key=key, threshold_value=lim, findings=bad)


def rounded(x: float) -> float:
    """報告に載せる値の桁を揃える（判定は丸める前の値で行う）。"""
    return round(x, 3)


def count_limit_result(check_id: str, title: str, thresholds: Thresholds, key: str, items: list[Finding]) -> CheckResult:
    """話全体での数（該当する所の数）に上限の閾値を当てる。外れたら、該当する所を全部挙げる。"""
    n = len(items)
    if key not in thresholds:
        return CheckResult(check_id=check_id, title=title, status="閾値未設定", value=n, threshold_key=key)
    lim = float(thresholds[key])
    bad = n > lim
    return CheckResult(check_id=check_id, title=title, status="不合格" if bad else "合格", value=n,
                       threshold_key=key, threshold_value=lim, findings=items if bad else [])
