"""コマの絵の写す範囲・角度・人物の向きを画像から判定させる問い（試作 p11 judge_angle.py）。

試作で分かったこと（V3検証の結果 3-19）
- 8枚ずつ見せて、59枚中55〜56枚が当たった。外れは区分の境目（上半身と胸から上）。
- 正解も判定も同じ系統のモデルなので、甘めに出ている可能性がある。
- 試作の選択肢は5択（向きと角度をまとめた物・距離）だった。ここではネームの形の選択肢に揃えて、
  写す範囲・角度・向きを分けて聞く。この選択肢での精度は未検証。
- 一度に多くの画像を並べると答えが変わることがある（評価役の試作 p32）。何枚ずつ聞くかは呼ぶ側が決める。
"""
from typing import get_args

from pydantic import BaseModel

from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer
from v3server.name_structure.name_draft_schema import CameraAngle, Facing, ShotRange


def _quoted(literal) -> str:
    return "".join(f"「{x}」" for x in get_args(literal))


def build_shot_angle_question(image_count: int) -> str:
    """画像は呼ぶ側が image_count 枚、この順に添える。画像は添えた順の番号で呼ぶ（ファイルの名前を答えに使わせない）。"""
    if image_count < 1:
        raise ValueError("image_count は1以上")
    return f"""添えた{image_count}枚の画像は、どれも漫画の1コマ用の絵です。画像は添えた順に1から番号で呼びます。

各画像について、3つを判定してください。
・写す範囲：{_quoted(ShotRange)}から1つ。「引き」は人物が画面の中で小さく、場所が主になっているもの
・角度：{_quoted(CameraAngle)}から1つ。人物を写すカメラの高さと位置
・向き：{_quoted(Facing)}から1つ。いちばん大きく写っている人物の顔が、画面の中で向いている方。人物が写っていなければ null

出力はJSONだけにしてください。形式：{{"items":[{{"image":画像の番号,"shot":"...","angle":"...","facing":"... か null"}}]}}"""


class ShotAngleJudgement(BaseModel):
    # 添えた順の番号（1から）
    image: int
    shot: ShotRange
    angle: CameraAngle
    # 人物が写っていなければ None
    facing: Facing | None


class _ShotAngleAnswer(BaseModel):
    items: list[ShotAngleJudgement]


def parse_shot_angle_answer(answer: str, image_count: int) -> list[ShotAngleJudgement]:
    """答えを、添えた順に並んだ判定に読む。番号の抜け・重なりは BrokenAnswerError。"""
    items = read_answer(answer, _ShotAngleAnswer).items
    got = sorted(x.image for x in items)
    if got != list(range(1, image_count + 1)):
        raise BrokenAnswerError(f"画像の番号が 1〜{image_count} に揃っていない: {got}", answer)
    return sorted(items, key=lambda x: x.image)
