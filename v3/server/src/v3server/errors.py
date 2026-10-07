"""操作の窓口が返す失敗。API ではそれぞれ決まった状態コードにする（api/app.py）。"""


class V3Error(Exception):
    code = "error"


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
