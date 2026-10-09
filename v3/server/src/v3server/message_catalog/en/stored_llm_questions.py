"""英語の訳：LLM の答えを読む所（llm_questions）が、答えの形が崩れていたときに出す文。工程のステップの失敗の理由に入る。"""

MESSAGES = {
    # 答えから JSON を取り出す・決まった形に読む
    "答えに JSON オブジェクトが無い": "The response contains no JSON object",
    "JSON として読めない: {error}": "The response could not be read as JSON: {error}",
    "JSON の一番外がオブジェクト（辞書）でない": "The outermost JSON value is not an object (dictionary)",
    "形が合わない: {count}か所 {loc} {msg}":
        "The response does not match the expected format: {count} error(s), first at {loc}: {msg}",
    "問いに無い{what}: {unknown}": "The response refers to {what} that are not in the question: {unknown}",
    "行の番号": "line numbers",
    # ネーム・段と比
    "欠けた欄がある: {fields}": "Some fields are missing: {fields}",
    "{field}（{first} ほか{count}か所）": "{field} ({first}; {count} in total)",
    "同じコマ番号が2回以上ある": "The same panel number appears more than once",
    # 企画・構成・設定資料
    "質問も企画の案も無い": "The response has neither questions nor a draft plan",
    "聞いていない観点がある: {unknown}": "The response includes criteria that were not asked about: {unknown}",
    "答えの無い観点がある: {missing}": "Some criteria have no answer: {missing}",
    "同じ名前が2回ある": "The same name appears twice",
    "設定に無い名前がある: {unknown}": "The response uses names that are not among the given characters: {unknown}",
    # 作画・仕上げ・総合
    "タグが1つも無い": "The response contains no tags",
    "画像の番号が 1〜{count} に揃っていない: {got}": "The image numbers are not exactly 1 to {count}: {got}",
    "座標の数 {points} がコマの数 {panels} と違う":
        "The number of coordinates ({points}) does not match the number of panels ({panels})",
    "絵の番号が 1〜{count} にそろっていない": "The image numbers are not exactly 1 to {count}",
    "無いページの番号がある: {unknown}": "The response refers to page numbers that do not exist: {unknown}",
}
