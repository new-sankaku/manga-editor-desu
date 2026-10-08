"""待ち行列の名前と、依頼の順番の決め方。

- 人が画面で頼んだものを、AIが工程を進めるための依頼より先に送る（V3細部の決めごと 4.4）。Temporal は数が小さいほど先
- 優先順位が同じ依頼の中では、作品ごとに順に回す（公平さの鍵に作品の ID。V3ハーネス設計 2.4 の29）。
  試作 p57：作品Aの30件の後に頼んだ作品Bの5件が、公平さを切ると31〜35番目、入れると1・3・5・7・9番目に送られた。
  サーバー側で matching.enableFairness を入れていないと、鍵は無視される（compose.yaml）
"""

from datetime import timedelta

from temporalio.common import Priority

CONTROL_QUEUE = "v3-control"

PRIORITY_KEY = {"human": 1, "ai": 3}

# 制限に当たったとき、提供元が待ち時間を返さなかった場合に待つ時間
RATE_LIMIT_WAIT = timedelta(seconds=30)

# 依頼を受ける口が、送信をつなぎ先の待ち行列に入れ終えるまで待つ長さ。超えたら制御の作業者が動いていないとして依頼を止める
QUEUE_ENTRY_WAIT = timedelta(seconds=30)


def service_queue(service_id: str) -> str:
    return f"v3-service-{service_id}"


def job_priority(requested_via: str, work_id: str) -> Priority:
    return Priority(priority_key=PRIORITY_KEY[requested_via], fairness_key=work_id)
