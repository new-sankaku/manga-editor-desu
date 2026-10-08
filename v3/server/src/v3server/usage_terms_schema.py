"""利用の条件の形（V3細部の決めごと 20章）。サービスの規約の要点と、持ち込んだ絵の条件を同じ形で持つ。
人が確かめて入れる。分からない項目は unknown と書く（空欄で済ませない）。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

YesNoUnknown = Literal["yes", "no", "unknown"]


class UsageTerms(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 商用に使えるか
    commercial_use: YesNoUnknown
    # 出力（持ち込んだ絵なら絵そのもの）の権利が誰にあるか。書いた人の言葉のまま
    rights_holder: str = Field(min_length=1)
    # 送った絵が学習に使われるか（サービスの規約）。持ち込んだ絵では、学習に使ってよいか
    training_use: YesNoUnknown
    # クレジットの表記が要るか
    credit_required: YesNoUnknown
    credit_text: str | None = None
    # 規約・許諾のURLか、どこで確かめたかの説明。どちらかは要る
    terms_url: str | None = None
    terms_note: str | None = None
    # 確かめた日
    checked_on: date

    @model_validator(mode="after")
    def _where_checked(self):
        if not self.terms_url and not self.terms_note:
            raise ValueError("規約・許諾のURL（terms_url）か、確かめた所の説明（terms_note）が要る")
        return self
