"""英語の訳：AIハーネスの作画・仕上げ・総合・書き出しのステップが、記録に残してから工程の画面に出す文
（harness/ の panel_drawing_steps.py・panel_drawing_inputs.py・page_finishing_steps.py・overall_review_steps.py・
export_steps.py。検査の名前と結果・止まった理由・候補を落とした理由・作り方の記録・選んだ理由）。"""

MESSAGES = {
    # ---- 作画（panel_drawing_steps.py）：検査の名前
    "大きさ": "Size",
    "人数": "Number of people",
    "見切れ": "Cut off",
    "人物の位置（IoU）": "Character position (IoU)",
    "顔と吹き出しの重なり": "Face and balloon overlap",
    "絵の中の文字・吹き出し": "Text or balloons in the image",
    "手": "Hands",
    "年齢区分": "Age rating",
    "同じ人物（CCIP）": "Same character (CCIP)",
    "写す範囲": "Shot range",
    "角度": "Angle",
    "背景": "Background",
    "視線": "Gaze",
    "ぼやけ・線の潰れ": "Blur or crushed lines",
    "服・アクセサリー・小物": "Clothes, accessories and props",
    # 検査の結果
    "{width}x{height}（依頼した {want_width}x{want_height}）": "{width}x{height} (requested {want_width}x{want_height})",
    "検出 {found} 人・ネーム {want} 人": "{found} detected, {want} in the storyboard",
    "端に接した人物 {count}（{sides}）": "People touching the edge: {count} ({sides})",
    "{people}（下限 {low}）": "{people} (minimum {low})",
    "ネームに人物の範囲が無いので比べない": "Not compared: the storyboard has no character areas",
    "人物がいない": "No characters",
    "いちばん隠れた顔 {worst:.0%}（上限 {high:.0%}）。顔の検出 {faces}":
        "Most covered face {worst:.0%} (maximum {high:.0%}). Faces detected: {faces}",
    "フキダシを置いていない（仕上げ S5 で置いた後に検査する）":
        "No balloons are placed yet (checked after they are placed in Finishing, S5)",
    "文字の範囲 {count}": "Text areas: {count}",
    "手の検出 {count}。崩れの判定器は無いので人が見る":
        "Hands detected: {count}. There is no detector for malformed hands, so a person checks them",
    "いちばん高い区分 {top}（記録だけ。判定に使わない）": "Highest rating: {top} (recorded only; not used to judge)",
    "設定資料の {name} に絵が無いので比べない": "Not compared: {name} has no image in the reference sheets",
    "{name} に当たる検出の人物が決められない": "Could not tell which detected person is {name}",
    "{name} は小さい（高さ {ratio}。p43 で差が大きく出た）":
        "{name} is small (height {ratio}; small figures gave large differences in prototype p43)",
    "{name} 差 {difference}（閾値 {threshold}）": "{name}: difference {difference} (threshold {threshold})",
    "{name} 差 {difference}（閾値 {threshold}）。違う人物と出た":
        "{name}: difference {difference} (threshold {threshold}). Judged to be a different character",
    "VLM {judged}・ネーム {want}": "VLM: {judged}, storyboard: {want}",
    "手段が無い。人が確かめる": "No way to check this automatically. A person checks it",
    # 止まった理由
    "{key}（{meaning}）": "{key} ({meaning})",
    "作画の検査の閾値が未設定: {thresholds}": "Thresholds for the drawing check are not set: {thresholds}",
    "このコマの検査に要る閾値が未設定: {thresholds}": "Thresholds needed to check this panel are not set: {thresholds}",
    "コマが無い（消された）": "The panel does not exist (it was removed)",
    "人の確定印のあるコマは、AIが作り直さない（設計 9.2）":
        "AI does not redo a panel that a person has marked as confirmed (design 9.2)",
    "設定資料に人物 {name} が無い（採った人物だけを使う）":
        "Character {name} is not in the reference sheets (only accepted characters are used)",
    "設定資料の人物 {name} に生成の言葉（generation.prompt）が無い。特徴の言葉は毎回全部入れる（試作 p17）ので、人が設定資料に書く":
        "Character {name} in the reference sheets has no generation prompt (generation.prompt). "
        "All trait words are sent every time (prototype p17), so a person writes them in the reference sheets",
    "タグの答えの形が崩れた: {error}": "The answer for the tags was malformed: {error}",
    "手動で修正した絵から続けるには、作業の決めごとに redraw_params（image_to_image の引数）が要る":
        "Continuing from a manually edited image needs redraw_params (image_to_image parameters) in the task settings",
    "生成が全部断られた: {detail}": "Every generation was refused: {detail}",
    "生成が全部止まった": "Every generation stopped",
    "写す範囲・角度の答えの形が崩れた: {error}": "The answer for shot range and angle was malformed: {error}",
    "評価モデルの答えの形が崩れた: {error}": "The evaluator's answer was malformed: {error}",
    # 候補を落とした理由・直せない理由
    "生成が止まった（{kind}）: {detail}": "Generation stopped ({kind}): {detail}",
    "検査で落ちた: {names}": "Failed the check: {names}",
    "作業の決めごとに fix（直させるステップの引数）が無い": "The task settings have no fix (parameters for the fix step)",
    "検査で落ちた所を直させた（{process}・{kinds}）。直した候補を使う":
        "The parts that failed the check were fixed ({process}: {kinds}). The fixed candidate is used instead",
    "直す依頼が止まった（{kind}）: {detail}": "The fix job stopped ({kind}): {detail}",
    # 選んだ理由
    "選べる候補が無い": "No candidate can be picked",
    "比べる相手が無い（通った候補が1枚）": "Nothing to compare with (only one candidate passed)",
    "通った候補が1枚なので比べずに選んだ": "Only one candidate passed, so it was picked without comparing",
    "くり返すと1位が変わった": "The top candidate changed between repeats",
    "1位が1枚に決まらない（同点）": "No single top candidate (tie)",
    "勝ち＋引き分けの半分がいちばん多い": "Highest score (wins plus half of the ties)",
    # 工程の検査（コマをまたぐ一致）で比べなかった理由
    "設定資料に絵のある人物が1人だけ写るコマでない":
        "Not a panel showing exactly one character who has an image in the reference sheets",
    "検出の人物 {count} 人（1人で高さ2割以上のときだけ比べる）":
        "{count} people detected (compared only when there is one person at least 20% of the image height)",
    # ---- 作画の作り方の記録（panel_drawing_inputs.py）：使った入力・足りない入力
    "人物 {name} の範囲（ネームの box_mm）が無い": "Character {name} has no area (box_mm in the storyboard)",
    "人物 {name} の範囲": "Area of character {name}",
    "人物の範囲が揃わないので、人物の置き場（範囲ごとの文・骨格）は渡さない":
        "Not every character has an area, so character placement (regional prompts or skeleton) is not sent",
    "人が描いた下絵（線画の形の指定。背景と人物を分けずに描く）":
        "Hand-drawn rough sketch (used as line art shape guidance; background and characters are drawn together)",
    "ネームに場所（location）が無い。背景の正本は使えない":
        "The storyboard has no location. The canonical background cannot be used",
    "設定資料に場所 {location} の背景（採った物）が無い":
        "The reference sheets have no accepted background for location {location}",
    "ネームにコマの向き（view）が無い。正本の向きと比べられない":
        "The storyboard has no view for the panel. It cannot be compared with the view of the canonical background",
    "作業の決めごとに background（背景を作る引数）が無いので、場所の正本は使わない":
        "The task settings have no background (parameters for making backgrounds), "
        "so the canonical background of the location is not used",
    "人物の範囲が無いと背景の上に人物を描けないので、場所の正本は使わない":
        "Characters cannot be drawn over a background without their areas, "
        "so the canonical background of the location is not used",
    "場所 {location} の正本の背景の絵（向き {view} が同じ）を切り出した":
        "Cropped the canonical background image of location {location} (same view: {view})",
    "ネームの切り出す範囲（background_crop）": "Crop area from the storyboard (background_crop)",
    "ネームに切り出す範囲が無いので、正本の絵の真ん中をコマの縦横比で切り出した":
        "The storyboard has no crop area, so the center of the canonical image was cropped to the panel's aspect ratio",
    "場所 {location} の箱の3D（向き {view} のカメラ）から奥行きを描いた":
        "Rendered a depth image from the 3D boxes of location {location} (camera for view {view})",
    "場所 {location} の箱の3D（向き {view} のカメラ）から線画を描いた":
        "Rendered line art from the 3D boxes of location {location} (camera for view {view})",
    "場所 {location} の正本に、向き {view} の絵も3Dのカメラも無い":
        "The canonical data of location {location} has neither an image nor a 3D camera for view {view}",
    # 止まった理由
    "コマの枠が無い。ネームで枠を決めてから作画する": "The panel has no frame. Set the frame in the storyboard before drawing",
    "コマの枠の大きさが0": "The panel frame has zero size",
    "作業の決めごとの controls に {name} の効き（strength・end）が無い。この形の指定を使うには要る":
        "controls in the task settings has no strength and end for {name}. They are needed to use this shape guidance",
    "人物のいないコマで正本の背景を使うには、作業の決めごとに redraw_params が要る":
        "Using the canonical background in a panel with no characters needs redraw_params in the task settings",
    "設定資料の場所 {location} に背景の生成の言葉（generation.prompt）が無い":
        "Location {location} in the reference sheets has no generation prompt for its background (generation.prompt)",
    # ---- 仕上げ（page_finishing_steps.py）
    "作品の寸法（page_spec）がまだ決まっていない": "The page dimensions of the work (page_spec) are not set yet",
    "フキダシ・文字がまだ置かれていない。仕上げは人が置く工程なので、置いてから再開する":
        "No balloons or text are placed yet. Finishing is a stage where a person places them; place them and then resume",
    "人が置いた今の状態（AIは置かない）": "The current state as placed by a person (AI does not place anything)",
    "仕上げは人が置く工程。候補は人が置いた今の状態の1つだけ":
        "Finishing is a stage where a person places things. The only candidate is the current state as placed by a person",
    "候補は人が置いた今の状態の1つだけ": "The only candidate is the current state as placed by a person",
    "仕上げは人が置いた物を正本のまま使う": "Finishing uses what the person placed as it is, as the canonical data",
    "読む順の答えの形が崩れた: {error}": "The answer for the reading order was malformed: {error}",
    "読む順（{page}ページ）": "Reading order (page {page})",
    "コマの順と同じ": "Same as the panel order",
    "判定の順 {order}（コマの順 1〜{count}）": "Judged order {order} (panel order 1–{count})",
    "顔と吹き出しの重なり（{page}ページ {panel}コマ）": "Face and balloon overlap (page {page}, panel {panel})",
    "いちばん隠れた顔 {worst:.0%}（上限 {high:.0%}、閾値は{status}）。顔の検出 {faces}":
        "Most covered face {worst:.0%} (maximum {high:.0%}, threshold is {status}). Faces detected: {faces}",
    "ネームの検査の閾値が未設定: {keys}": "Thresholds for the storyboard check are not set: {keys}",
    # ---- 総合（overall_review_steps.py）
    "作品の寸法（page_spec）と1ページ目の位置（first_page_is_left）がまだ決まっていない":
        "The page dimensions of the work (page_spec) and the side of the first page (first_page_is_left) are not set yet",
    "ページ {page} を描けない: {error}": "Page {page} cannot be rendered: {error}",
    "話にページが無い": "The episode has no pages",
    "ページの要約の答えの形が崩れた: {error}": "The answer for the page summaries was malformed: {error}",
    "構成との比べの答えの形が崩れた: {error}": "The answer for the comparison with the outline was malformed: {error}",
    "今の原稿を測った物なので候補は1つ": "This measures the current manuscript, so there is one candidate",
    "今の原稿を測った候補は1つ": "There is one candidate: the measurement of the current manuscript",
    "見開きの黒（{first}・{second}ページ）": "Black in the spread (pages {first} and {second})",
    "ページの白（{page}ページ）": "White in the page (page {page})",
    "{ratio:.0%}（上限 {high:.0%}、閾値は{status}）": "{ratio:.0%} (maximum {high:.0%}, threshold is {status})",
    "構成との食い違い": "Differences from the outline",
    "構成（S1）が無いので比べない": "Not compared: there is no outline (S1)",
    "無い": "None",
    "{page}ページ：{why}": "Page {page}: {why}",
    "人が総合の判定を見て完成とした": "A person reviewed the overall results and marked it complete",
    # ---- 書き出し（export_steps.py）
    "{format} を書き出せない: {error}": "{format} cannot be exported: {error}",
    "プログラム（書き出し）": "Program (export)",
    "同じ原稿を同じ形で書き出すので候補は1つ":
        "The same manuscript is exported in the same format, so there is one candidate",
    "入稿前の確かめ": "Pre-submission check",
    "error {errors}・warning {warnings}": "{errors} errors, {warnings} warnings",
    "書き出し（{format}）": "Export ({format})",
    "{count} ファイル（{run_id}）": "{count} files ({run_id})",
    "書き出した物は1つ": "There is one export",
    "人が提出すると決めた。入稿先へ送る API は無い（人が持ち出す）":
        "A person decided to submit it. There is no API to send it to the publisher (a person takes the files out)",
}
