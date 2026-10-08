"""絵を作る文（プロンプト）を組む。設定資料の特徴の言葉は、毎回全部入れる。

移す元は試作 p17 `chara_words`・`prompt`、p15 `prompt`・`negative`、p16 `prompt`。
組み方は「画質＋絵柄＋狙い＋人物＋場所」。どの言葉も設定資料と設定から渡し、ここには書かない。
"""
from __future__ import annotations

from dataclasses import dataclass

SEPARATOR = ', '


@dataclass(frozen=True)
class CharacterSheetWords:
    """設定資料の1人分の言葉。

    count_words：人数と性別の言葉。
    feature_words：見た目の特徴の言葉（髪・目・飾り・服など）を全部。
    """

    count_words: str
    feature_words: str


@dataclass(frozen=True)
class ShotTarget:
    """狙いの絵（コマの引き、人物だけ、背景だけなど）の言葉。

    add_words：狙いに要る言葉だけ。negative_words：狙いのために足す否定の言葉（無ければ空の文字列）。
    has_person・has_place：人物・場所の言葉を入れるか。
    """

    add_words: str
    negative_words: str
    has_person: bool
    has_place: bool


def character_words(sheet: CharacterSheetWords) -> str:
    """1人分の言葉。特徴を削った版は作らない。

    試作 p17：性別だけ・性別＋髪では別人になった（目で 0/9）。全部の特徴を書くと 9/9・8/9。
    参照画像の部品（IP-Adapter）は言葉の代わりにならなかった。
    特徴の言葉に色が入ると（赤い目・緑の上着）、白黒の指定でもその色が絵に残る。
    """
    return _join([sheet.count_words, sheet.feature_words])


def shot_prompt(quality_words: str, style_words: str, target: ShotTarget,
                character: CharacterSheetWords | None, place_words: str | None) -> str:
    """狙いの絵の文を組む。人物・場所を入れる狙いなのに渡されなければ例外。

    試作 p15・p16 で分かったこと：
    - 言葉だけでは人物はほとんどコマの真ん中に立つ。位置は骨格の制御で決める。
    - 縦長のコマで場所を教室にすると、1枚の中にコマが縦に並んだ絵になった（7/9）。場所を変えると同じ狙いの言葉が効かなくなる。
    - 背景だけの街は、真上から見下ろす絵になりやすい。
    - 白黒の絵柄の言葉3種では、絵柄はほとんど変わらなかった。カラーだけははっきり変わる。
    """
    parts = [quality_words, style_words, target.add_words]
    if target.has_person:
        if character is None:
            raise ValueError('人物を入れる狙いですが、人物の言葉がありません')
        parts.append(character_words(character))
    if target.has_place:
        if place_words is None:
            raise ValueError('場所を入れる狙いですが、場所の言葉がありません')
        parts.append(place_words)
    return _join(parts)


def shot_negative(base_negative: str, target: ShotTarget) -> str:
    """否定の言葉。設定の基本の否定の言葉に、狙いの否定の言葉を足す。

    否定の言葉でフキダシを防ぐ手は効かなかった（試作 p22）ので、ここでは足さない。
    """
    return _join([base_negative, target.negative_words])


def _join(parts: list[str]) -> str:
    return SEPARATOR.join(p.strip() for p in parts if p.strip())
