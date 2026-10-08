"""状態・段・工程の名前。画面とサーバーで同じ名前を使う（llm_doc/V3調査/AIハーネスのオープンソース実装の調査.md 6章）。"""

# 実行の状態（1つだけ取る）
QUEUED = "queued"                    # 順番待ち（送り先が空くのを待つ）
RUNNING = "running"                  # 実行中
WAITING_LIMIT = "waiting_limit"      # 回数・同時実行の上限で待つ
WAITING_BUDGET = "waiting_budget"    # 送り先の予算の上限で待つ
AWAITING_REVIEW = "awaiting_review"  # 判断待ち（人の採用・却下）
PAUSED = "paused"                    # 人が止めた
CANCELLING = "cancelling"            # 取り消しを頼んだが、まだ止まっていない
RETRYING = "retrying"                # 通信の失敗や作業者の停止のあと、同じ呼び出しをやり直している
STOPPED = "stopped"                  # 上限・判定できない・断られた・上流が変わった。人の判断を待つ
FAILED = "failed"                    # 直さないと進めないエラー
CANCELLED = "cancelled"
DONE = "done"
BLOCKED = "blocked"                  # 閾値が未設定などで、人が決めるまで進めない

STATES = (QUEUED, RUNNING, WAITING_LIMIT, WAITING_BUDGET, AWAITING_REVIEW, PAUSED, CANCELLING, RETRYING, STOPPED,
          FAILED, CANCELLED, DONE, BLOCKED)
TERMINAL = frozenset({DONE, CANCELLED, FAILED})
# 人を待っている状態と、送り先を待っている状態（画面で分ける）
WAITING_HUMAN = frozenset({AWAITING_REVIEW, PAUSED, STOPPED, BLOCKED})
WAITING_SERVICE = frozenset({QUEUED, WAITING_LIMIT, WAITING_BUDGET, RETRYING})

# 作業の中の段（設計 10章の1回の作業の回り方）
CUT_OUT = "cut_out"
CONTEXT = "context"
GENERATE = "generate"
CHECK = "check"
EVALUATE = "evaluate"
REVIEW = "review"
FINALIZE = "finalize"
STEPS = (CUT_OUT, CONTEXT, GENERATE, CHECK, EVALUATE, REVIEW, FINALIZE)

# 作り直しの辺（画面のグラフの戻りの辺）。（どこから, どこへ, 理由）
RETRY_EDGES = (
    (CHECK, CONTEXT, "検査で全部落ちた"),
    (EVALUATE, CONTEXT, "評価で選べない・割れた"),
    (REVIEW, CONTEXT, "却下（理由つき）"),
    (REVIEW, GENERATE, "人が直した絵から続ける"),
)

STAGES = ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7")
STAGE_TITLES = {"S0": "企画", "S1": "構成", "S2": "設定資料", "S3": "ネーム", "S4": "作画", "S5": "仕上げ",
                "S6": "総合", "S7": "書き出し"}
# 作業を切り出す工程と作業の種類。ここに無い工程は、作業を切り出さず工程の検査と人の判断だけを回す
UNIT_KIND_OF_STAGE = {"S3": "name_draft", "S4": "panel_drawing"}
# 決めごと 5.2：判断待ちは工程の前のものから
STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}
