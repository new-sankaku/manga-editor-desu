"""操作の窓口が返す失敗。API ではそれぞれ決まった状態コードにする（http_routes/http_app_factory.py）。"""


class V3Error(Exception):
    code = "error"
    # API の返事に detail と一緒に入れる値（無ければ入れない）
    extra: dict | None = None


class NotFound(V3Error):
    code = "not_found"


class Forbidden(V3Error):
    code = "forbidden"


class Locked(V3Error):
    code = "locked"


class Invalid(V3Error):
    code = "invalid"


class NotUndoable(V3Error):
    code = "not_undoable"


class UndoConflictError(V3Error):
    """取り消しが、後の出来事が変えた項目を上書きする（点検1 8-1）。取り消しは当てず、記録を残す（undo_conflicts）。"""

    code = "undo_conflict"

    def __init__(self, message: str, conflicts: list[dict], record_id: str | None = None):
        super().__init__(message)
        self.conflicts = conflicts
        self.extra = {"conflicts": conflicts, "undo_conflict_id": record_id}


class HumanHandProtected(V3Error):
    """AIが、人の手の印か人の確定印の付いた所を変えようとした（V3細部の決めごと 10.2）。"""

    code = "human_hand_protected"


class AiInvolvementRefused(V3Error):
    """作業のAIの関与で、AIのその手が許されていない（V3ハーネス設計 4.2）。"""

    code = "ai_involvement_refused"


class FixedByPerson(V3Error):
    """人が「動かさない」を掛けた層・物を変えようとした。人もAIも変えられない。外せるのは人だけ。"""

    code = "fixed_by_person"


class QueueNotRunning(V3Error):
    """依頼を待ち行列に入れられなかった（制御の作業者が動いていない）。依頼は止めてある（stopped）。"""

    code = "queue_not_running"
