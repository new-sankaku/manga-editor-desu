"""英語の訳：ネームの形・ComfyUI の手順の組み立て・評価モデルの答えの読み取りが出す文のうち、記録に残してから画面に出す物
（ネームの未定の項目の場所、画像生成の依頼の失敗の理由、工程のステップの失敗の理由に入る）。"""

MESSAGES = {
    # ネームの未定の項目の場所（name_structure/name_draft_schema.py）。検査の「データなし」の理由と、答えの形が崩れた理由に入る
    "{page}ページ": "Page {page}",
    "{page}ページ コマ{n}": "Page {page} panel {n}",
    # ComfyUI の手順の組み立て（comfy_graphs/）
    "切り出しは囲んだ範囲があるときだけ": "Cropping is only available when there is a selection",
    "人物の枠が空です: {box}": "The figure box is empty: {box}",
    "範囲が1つもありません": "There are no regions",
    "範囲の {name}={value} が {step} ピクセル刻みではありません": "Region {name}={value} is not a multiple of {step} pixels",
    # 評価モデルの答えの読み取り（judge_procedures/）
    "候補に無い名前: {pick}": "The response names an image that is not among the candidates: {pick}",
    "組の番号が 1〜{count} に揃っていない: {ids}": "The pair numbers in the response do not cover 1 to {count}: {ids}",
}
