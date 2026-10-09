"""検査の結果と指摘の形。合格は1行、失敗だけ詳しく（どのページ・どのコマ・何の値）。
閾値は渡された辞書から読む。コードに値を書かない（V3ハーネス設計 7.1）。"""
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel

from v3server.messages import ms

# 合格・不合格：判定した。閾値未設定：閾値が渡されていないので値だけ返す。
# データなし：計算に要る値（枠・人物の位置・吹き出しの位置など）がネームにまだ無い
# 状態は値として持つ（コードと試験が比べる・データベースに残る）。文に入れるときの言い方は _STATUS_TEXT で引く
CheckStatus = Literal["合格", "不合格", "閾値未設定", "データなし"]  # i18n:data
_STATUS_TEXT: dict[str, str] = {  # i18n:data
    "合格": ms("合格"), "不合格": ms("不合格"), "閾値未設定": ms("閾値未設定"), "データなし": ms("データなし"),
}
Thresholds = Mapping[str, float]
Bound = Literal["max", "min"]

# ネームの値（大きさ・形・写す範囲・角度・ページの側・距離の分け方）は日本語のまま持つ（比べる・保存する）。
# 検査の文に入れるときの言い方だけ、ここで引く。ネームの形に値を足したら、ここにも足す（tests/unit/test_name_checks.py が抜けを止める）
_VALUE_TEXT: dict[str, str] = {  # i18n:data
    "大": ms("大"), "中": ms("中"), "小": ms("小"),
    "四角": ms("四角"), "斜め": ms("斜め"), "枠なし": ms("枠なし"), "断ち切り": ms("断ち切り"),
    "遠景": ms("遠景"), "引き": ms("引き"), "全身": ms("全身"), "膝上": ms("膝上"), "胸から上": ms("胸から上"), "顔": ms("顔"),
    "部分": ms("部分"),
    "目の高さ": ms("目の高さ"), "見下ろし": ms("見下ろし"), "見上げ": ms("見上げ"), "真横": ms("真横"), "背後": ms("背後"),
    "真上": ms("真上"),
    "左": ms("左"), "右": ms("右"),
    "遠": ms("遠"), "寄り": ms("寄り"),
}


def value_text(value: str | None) -> str | None:
    """ネームの値を、検査の文に入れる形にする。未定（None）はそのまま返す。"""
    return None if value is None else _VALUE_TEXT[value]


def dot_joined(parts: list[str]) -> str:
    """場所や値の言い方を「・」でつなぐ（3つまで）。言語で区切りが違うので、つないだ形ごと文として包む。"""
    if len(parts) > 3:
        raise ValueError(f"dot_joined は3つまで: {len(parts)}")  # i18n:dev
    if len(parts) == 3:
        return ms("{a}・{b}・{c}", a=parts[0], b=parts[1], c=parts[2])
    if len(parts) == 2:
        return ms("{a}・{b}", a=parts[0], b=parts[1])
    return parts[0] if parts else ""


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
            where.append(ms("{page}ページ", page=self.page))
        if self.panel is not None:
            where.append(ms("コマ{panel}", panel=self.panel))
        if self.balloon is not None:
            where.append(ms("吹き出し{balloon}", balloon=self.balloon + 1))
        head = dot_joined(where)
        if self.value is None:
            return ms("{head}：{note}", head=head, note=self.note) if head else self.note
        if head:
            return ms("{head}：{note}（値 {value}）", head=head, note=self.note, value=self.value)
        return ms("{note}（値 {value}）", note=self.note, value=self.value)


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
        status = _STATUS_TEXT[self.status]
        if self.status == "データなし":  # i18n:data
            return [ms("[{status}] {title}：{value}", status=status, title=self.title, value=self.value)]
        # 値と閾値のある・なしで文の形が変わる。かけらをつながず、形ごとに文として包む
        if self.threshold_value is None:
            head = (ms("[{status}] {title}", status=status, title=self.title) if self.value is None
                    else ms("[{status}] {title} 値 {value}", status=status, title=self.title, value=self.value))
        elif self.value is None:
            head = ms("[{status}] {title} 閾値 {key}={limit}", status=status, title=self.title,
                      key=self.threshold_key, limit=self.threshold_value)
        else:
            head = ms("[{status}] {title} 値 {value} 閾値 {key}={limit}", status=status, title=self.title, value=self.value,
                      key=self.threshold_key, limit=self.threshold_value)
        if self.status != "不合格":  # i18n:data
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
    status: CheckStatus = "不合格" if findings else "合格"  # i18n:data
    return CheckResult(check_id=check_id, title=title, status=status, value=value, findings=findings)


def no_data_result(check_id: str, title: str, reason: str) -> CheckResult:
    """計算に要る値がネームに無い。合否を出さない。"""
    return CheckResult(check_id=check_id, title=title, status="データなし", value=reason)  # i18n:data


def limit_result(check_id: str, title: str, thresholds: Thresholds, key: str, bound: Bound,
                 value: float | int | None, measured: list[tuple[float, Finding]]) -> CheckResult:
    """閾値の要る検査。measured は項目ごとの（丸める前の値, 指摘の形）。
    閾値が無ければ「閾値未設定」で値だけ返す。あれば、閾値を外れた項目だけを指摘にする。
    bound が "max" なら値が閾値を超えたら外れ、"min" なら閾値を下回ったら外れ。
    測る対象が無い（例：段に1コマずつしか無く縦線が無い）ときは value を None、measured を空で渡す。"""
    if key not in thresholds:
        return CheckResult(check_id=check_id, title=title, status="閾値未設定", value=value, threshold_key=key)  # i18n:data
    lim = float(thresholds[key])
    bad = [f for v, f in measured if (v > lim if bound == "max" else v < lim)]
    return CheckResult(check_id=check_id, title=title, status="不合格" if bad else "合格", value=value,  # i18n:data
                       threshold_key=key, threshold_value=lim, findings=bad)


def rounded(x: float) -> float:
    """報告に載せる値の桁を揃える（判定は丸める前の値で行う）。"""
    return round(x, 3)


def count_limit_result(check_id: str, title: str, thresholds: Thresholds, key: str, items: list[Finding]) -> CheckResult:
    """話全体での数（該当する所の数）に上限の閾値を当てる。外れたら、該当する所を全部挙げる。"""
    n = len(items)
    if key not in thresholds:
        return CheckResult(check_id=check_id, title=title, status="閾値未設定", value=n, threshold_key=key)  # i18n:data
    lim = float(thresholds[key])
    bad = n > lim
    return CheckResult(check_id=check_id, title=title, status="不合格" if bad else "合格", value=n,  # i18n:data
                       threshold_key=key, threshold_value=lim, findings=items if bad else [])
