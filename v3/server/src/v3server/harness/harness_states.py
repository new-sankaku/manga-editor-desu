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
FIX = "fix"                          # 直させる：検査で落ちた所（文字・顔）だけを囲んで直し、直した候補だけ検査し直す
EVALUATE = "evaluate"
REVIEW = "review"
FINALIZE = "finalize"
STEPS = (CUT_OUT, CONTEXT, GENERATE, CHECK, FIX, EVALUATE, REVIEW, FINALIZE)

# 作り直しの辺（画面のグラフの戻りの辺）。（どこから, どこへ, 理由）
RETRY_EDGES = (
    (CHECK, FIX, "落ちた所だけ直す"),
    (FIX, CHECK, "直した候補だけ検査し直す"),
    (CHECK, CONTEXT, "直せない・直す上限で全部を作り直す"),
    (EVALUATE, CONTEXT, "評価で選べない・割れた"),
    (REVIEW, CONTEXT, "却下（理由つき）"),
    (REVIEW, GENERATE, "人が直した絵から続ける"),
)

STAGES = ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7")
STAGE_TITLES = {"S0": "企画", "S1": "構成", "S2": "設定資料", "S3": "ネーム", "S4": "作画", "S5": "仕上げ",
                "S6": "総合", "S7": "書き出し"}
# 工程と作業の種類（設計 7章の工程の表）。どの工程も作業を切り出す。人だけで決める所は、作業の中の段を人の判断にする
# （例：S5 の吹き出しの置き場は人が置き、プログラムは検査だけ。S7 の入稿は人が決める）
UNIT_KIND_OF_STAGE = {"S0": "plan_interview", "S1": "structure", "S2": "settings_sheet", "S3": "name_draft",
                      "S4": "panel_drawing", "S5": "page_finishing", "S6": "overall_review", "S7": "export"}
# 人が採るまで終わらない工程（完成条件に human_approve を必ず足す）。S4 は検査と評価役で終えてよい（設計 8.1）、
# S5 は人が置いた物をプログラムが検査するだけなので、人の採用を条件にするかは頼む人が決める
HUMAN_APPROVE_STAGES = frozenset({"S0", "S1", "S2", "S3", "S6", "S7"})
# 決めごと 5.2：判断待ちは工程の前のものから
STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}
