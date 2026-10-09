"""英語の訳：AIハーネスの、返事に入れて画面に出す名前と説明（工程の名前・通知の種類・閾値の意味と出典・採れない理由）。"""

MESSAGES = {
    # 工程の名前（harness_states.py。画面の辞書 v3/web/i18n/en/harness.js と同じ訳）
    "企画": "Planning",
    "構成": "Outline",
    "設定資料": "Reference sheets",
    "ネーム": "Storyboard",
    "作画": "Drawing",
    "仕上げ": "Finishing",
    "総合": "Overall review",
    "書き出し": "Export",
    # 通知の種類の説明（harness_notify.py）
    "候補ができて人の判断を待っている": "Candidates are ready and waiting for your decision",
    "作業が止まった・失敗した（閾値未設定・上限・エラー・断られた）":
        "A task stopped or failed (threshold not set, limit reached, error, or refused)",
    "作業の費用が予算の上限に近づいた": "A task's cost is close to the budget limit",
    "判断待ちが長い": "A decision has been pending for a long time",
    "工程の承認を待っている": "A pipeline is waiting for approval",
    # 閾値の意味（panel_drawing_steps.py・overall_review_steps.py）
    "人物の検出の score の下限": "Minimum score for detecting a person",
    "見切れとみなす、枠が絵の端から何ピクセル以内か":
        "How many pixels from the image edge a detected box may be to count as cut off",
    "絵の中の文字の検出の score の下限": "Minimum score for detecting text in the image",
    "ネームの人物の範囲と検出した人物の重なり（IoU）の下限（ネームに人物の範囲があるコマ）":
        "Minimum overlap (IoU) between the character area in the storyboard and the detected person "
        "(panels whose storyboard has a character area)",
    "同じ人物とみなす CCIP の差の上限（設定資料に人物の絵があるコマ）":
        "Maximum CCIP difference to count as the same character "
        "(panels whose character has an image in the reference sheets)",
    "顔がフキダシに隠れてよい割合の上限（フキダシを置いたコマ）":
        "Maximum share of a face that a balloon may cover (panels with balloons placed)",
    "見開きの黒いピクセルの割合の上限（0〜1）": "Maximum share of black pixels in a spread (0 to 1)",
    "ページの白いピクセルの割合の上限（0〜1）": "Maximum share of white pixels on a page (0 to 1)",
    # 閾値をいつ読むか・どの工程が読むか・値の案の出典（threshold_proposals.py）
    "いつも": "Always",
    "条件が揃ったコマ": "Panels that meet the condition",
    "S4・S5": "S4, S5",
    "測っていない": "Not measured",
    "{doc}（文字の検出器。文字あり38枚・なし10枚で、0.05 は見つけた33・誤り3、0.1 は31・2、0.2 は24・1、0.3 は全部見逃した）":
        "{doc} (text detector. With 38 images that have text and 10 that do not: 0.05 found 33 with 3 false hits, "
        "0.1 found 31 with 2, 0.2 found 24 with 1, and 0.3 missed them all)",
    "{doc}（CCIP の既定の閾値。人物を切り抜いて比べると、別の人物を94〜95%「同じ」とした組があった。「違う」で落とす専用に使う）":
        "{doc} (default CCIP threshold. When characters were cropped and compared, some sets judged different "
        "characters as \"same\" 94 to 95% of the time. Use it only to drop candidates judged \"different\")",
    "{doc}（骨格の図を渡したときの IoU は約0.72〜0.81、形の指定なしは0.13前後。下限の値は測っていない）":
        "{doc} (IoU was about 0.72 to 0.81 when a pose skeleton was given and around 0.13 without shape control. "
        "The minimum value was not measured)",
    # 採れない候補を採ろうとしたときの理由（plan_interview_steps.py）
    "企画の案の無い候補（質問だけ）は採れない。質問に答える（answer）":
        "A candidate with no planning draft (questions only) cannot be accepted. Answer the questions (answer)",
    "必須項目のそろわない案は採れない。質問に答えるか却下して作り直す":
        "A draft missing required fields cannot be accepted. Answer the questions, or reject it and regenerate",
    # 判断待ちの一覧で、知らない種類を渡されたとき（harness_routes.py。理由の後ろに、選べる種類を並べる）
    "{reason}（{kinds}）": "{reason} ({kinds})",
}
