from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Actor:
    """操作した者。AI は頼んだ人（on_behalf_of）の権限で動く。"""

    kind: Literal["human", "ai"]
    id: str
    on_behalf_of: str | None = None

    @property
    def permission_user(self) -> str:
        if self.kind == "human":
            return self.id
        if self.on_behalf_of is None:
            raise ValueError("AIの操作には頼んだ人が要る")
        return self.on_behalf_of

    def holds(self, holder_kind: str, holder_id: str) -> bool:
        return self.kind == holder_kind and self.id == holder_id
