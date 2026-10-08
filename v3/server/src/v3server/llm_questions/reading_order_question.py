"""コマの読む順を画像から判定させる問い（試作 p11・p45）。番号を振っていないコマ割りの画像を1枚添え、
読む順にコマの中心の座標を並べさせる。座標は、いちばん近いコマの中心に当てて番号に直す。

試作で分かったこと（V3検証の結果 3-17）
- 四角のコマ8種・斜めのコマを含む8種で、ほぼ当たった。外れたのは、列で横の隙間の高さがずれた、人でも迷う割り。
- 重ねたコマ・実際の漫画のページでは未検証。
"""
import math

from pydantic import BaseModel, Field

from v3server.llm_questions.answer_json_reader import BrokenAnswerError, read_answer
from v3server.name_structure.reading_direction import ReadingDirection


def build_reading_order_question(
    reading_direction: ReadingDirection,
    frame_width: float,
    frame_height: float,
    has_slanted_panels: bool,
) -> str:
    """画像は呼ぶ側が1枚添える。frame_width・frame_height は画像の座標の目盛り（基本枠の大きさ）。"""
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("目盛りは正の値")
    way = "右から左、上から下" if reading_direction == "right_to_left" else "左から右、上から下"
    slanted = "枠の辺が斜めのコマもあります。" if has_slanted_panels else ""
    return f"""添えた画像は、漫画の1ページのコマ割りです。コマには番号が振られていません。{slanted}
このページは{way}へ読みます。
各コマを、ページの中の位置で呼んでください。呼び方は、コマの中心の座標（左上を原点、右と下が増える向き、横{frame_width:g}・縦{frame_height:g}の目盛り）です。
読む順に、コマの中心の座標を並べてください。
出力はJSONだけにしてください。形式：{{"order":[[x,y],[x,y]]}}"""


class _OrderAnswer(BaseModel):
    order: list[tuple[float, float]] = Field(min_length=1)


def parse_reading_order_answer(answer: str) -> list[tuple[float, float]]:
    """答えを、読む順に並んだ座標に読む。"""
    return read_answer(answer, _OrderAnswer).order


def assign_points_to_panels(
    points: list[tuple[float, float]],
    panel_centers: dict[int, tuple[float, float]],
    answer: str,
) -> list[int]:
    """座標ごとに、中心がいちばん近いコマの番号を返す（読む順）。
    座標の数がコマの数と違うときは、答えの形が崩れているとして BrokenAnswerError。
    同じコマに2つの座標が当たるのは判定の外れとして返す（呼ぶ側が正しい順と比べる）。"""
    if not panel_centers:
        raise ValueError("panel_centers が空")
    if len(points) != len(panel_centers):
        raise BrokenAnswerError(f"座標の数 {len(points)} がコマの数 {len(panel_centers)} と違う", answer)
    return [min(panel_centers, key=lambda n: math.dist(panel_centers[n], p)) for p in points]
