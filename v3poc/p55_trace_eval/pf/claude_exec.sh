#!/bin/bash
# P55 promptfoo の exec 型の呼び先。claude CLI を、CLAUDE.md の無い空のフォルダで呼ぶ。
# promptfoo は第1引数に「プロンプト」、第2引数に「プロバイダーの options(JSON)」、第3引数に「context(JSON)」を渡す。
# 呼び出し回数は CALLS_LOG に1行ずつ足す(費用の上限 20 回の確認用)。
EMPTY_DIR="${P55_EMPTY_DIR:?P55_EMPTY_DIR に空のフォルダを指定してください}"
CALLS_LOG="${P55_CALLS_LOG:?P55_CALLS_LOG を指定してください}"
cd "$EMPTY_DIR" || exit 1
# プロンプトは標準入力で渡す(--add-dir が後ろの引数を飲み込むため)
RAW=$(printf '%s' "$1" | claude -p --model sonnet --output-format json ${P55_ADD_DIR:+--add-dir "$P55_ADD_DIR"})
# exec 型は標準出力の文字列だけが出力になる(費用・トークンは受け取れない)。費用などは CALLS_LOG に1行の JSON で残し、出力は答えの文字だけにする。
printf '%s' "$RAW" | CALLS_LOG="$CALLS_LOG" python3 -c '
import sys, json, os, time
d = json.load(sys.stdin)
u = d.get("usage", {})
with open(os.environ["CALLS_LOG"], "a") as f:
    f.write(json.dumps({"ts": int(time.time()), "cost": d.get("total_cost_usd"), "in": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0), "out": u.get("output_tokens", 0), "ms": d.get("duration_ms"), "is_error": d.get("is_error")}) + "\n")
print(d.get("result", ""))
'
