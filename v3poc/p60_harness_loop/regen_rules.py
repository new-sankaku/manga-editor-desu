"""検査の結果から、次の回の画像生成の語句を決める（ワークフローの中で動く。入出力だけの関数）。
「検査の結果を使う作り直し」（guided）と「seed だけ変える作り直し」（blind）を比べるのが (a)。
語句は画像生成のモデルに渡す英語の語句で、LLM のプロンプトではない。"""
from __future__ import annotations


def failure_signature(check: dict) -> str:
    bad = [r["id"] for r in check["results"] if r["status"] != "合格"]
    return f"{'+'.join(bad)}:{check['persons']}:{check['touch']}"


def adjustments_for(spec: dict, check: dict) -> dict:
    """1つの不合格の候補から、足す語句と外す語句を決める。"""
    add: list[str] = []
    neg: list[str] = []
    n, exp = check["persons"], spec["expected_persons"]
    if n > exp:
        if exp == 1:
            add += ["(solo:1.4)", "(single person:1.3)"]
            neg += ["crowd", "multiple people", "2girls"]
        else:
            add += [f"(exactly {exp} people:1.3)"]
            neg += ["crowd", "group", "3girls"]
    elif n < exp:
        if exp == 1:
            add += ["(1girl:1.4)", "(one person clearly visible:1.2)"]
            neg += ["no humans", "empty scenery"]
        else:
            add += ["(2girls:1.5)", "(two girls side by side:1.3)"]
            neg += ["solo"]
    if spec["full_body"] and check["touch"]:
        add += ["(full body:1.4)", "(wide shot:1.3)", "feet visible", "small figure in distance"]
        neg += ["close-up", "cropped", "out of frame"]
    return {"add": add, "neg": neg}


def merge(base: dict, extra: dict) -> dict:
    add = list(base["add"]) + [a for a in extra["add"] if a not in base["add"]]
    neg = list(base["neg"]) + [a for a in extra["neg"] if a not in base["neg"]]
    return {"add": add, "neg": neg}
