"""年齢区分の判定（imgutils の anime_rating_score）。

返す値は区分ごとの確率。しきい値で合否にはせず、値だけを返す（閾値は呼ぶ側）。
NSFW・写実・美しさの判定器は移さない（効かなかった手）。
"""
from PIL import Image
from imgutils.validate import anime_rating_score


def age_rating_scores(image: Image.Image) -> dict:
    return {"rating": {k: round(float(v), 3) for k, v in anime_rating_score(image).items()}}
