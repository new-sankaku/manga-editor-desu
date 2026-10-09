"""英語の訳：操作（operations/ の page_item_operations.py から後ろ。トーン・図形、コマ枠、ペンの線、PSD の戻し、確認、文字とレイヤー、訳文、作品の設定）。"""

MESSAGES = {
    # どの操作にも出る文
    "変える項目がない": "Nothing to change",
    "すでにその状態": "Already in that state",
    "{field} は空にできない": "{field} cannot be empty",
    # トーン・図形（page_item_operations.py）
    "{kind} の中身が正しくない: {reason}": "The {kind} contents are invalid: {reason}",
    "置き方（回転・傾き・反転）が正しくない: {reason}": "The transform (rotation, skew, flip) is invalid: {reason}",
    "箱の範囲が正しくない: {box}": "The box range is invalid: {box}",
    "トーンを貼るコマが、置くページ・コマと合わない":
        "The panel to apply the screentone to does not match the page or panel it is placed on",
    "コマとページが合わない": "The panel does not belong to the page",
    "動かせるのは同じページのコマの間だけ": "Items can only be moved between panels on the same page",
    "外す仕上げが無い": "There is no finishing to remove",
    # コマ枠（panel_frame_operations.py・panel_layout_proposal.py）
    "閾値 {key} が無い。コマの最小の大きさが決まらないので割りを計算しない":
        "Threshold {key} is missing. The minimum panel size is not set, so the layout is not calculated",
    "作品の寸法（page_spec）が決まっていないので、コマの間が分からない":
        "The work's dimensions (page_spec) are not set, so the panel gap is unknown",
    "コマ {id} には枠がまだ無い": "Panel {id} has no frame yet",
    "削除したコマは分けられない": "A removed panel cannot be split",
    "分けられない: {reason}": "Cannot split: {reason}",
    "合わせられるのは同じページのコマだけ": "Only panels on the same page can be merged",
    "同じコマは合わせられない": "A panel cannot be merged with itself",
    "削除したコマは合わせられない": "A removed panel cannot be merged",
    "隣り合っていない2つのコマは合わせられない（間がコマの間より広い）":
        "Two panels that are not adjacent cannot be merged (the space between them is wider than the panel gap)",
    "合わせた形がほかのコマ（番号 {order}）に重なる": "The merged shape overlaps another panel (number {order})",
    "切る数が0": "The number of cuts is 0",
    "割れない: {reason}": "Cannot divide: {reason}",
    "新しいコマの id は {count} 個要る": "{count} new panel ids are required",
    "枠のあるコマが無い": "There is no panel with a frame",
    "削除した型は当てられない": "A removed template cannot be applied",
    "コマ（番号 {order}）に中身がある。先に中身を動かすか、コマを削除する":
        "Panel (number {order}) has contents. Move the contents first, or remove the panel",
    "コマ割りを計算できない: {reason}": "Cannot calculate the panel layout: {reason}",
    # ペンの線（pen_stroke_operations.py）
    "ペンの線を持てるのは手描きレイヤー（role=human_hand）だけ": "Only a hand-drawn layer (role=human_hand) can hold pen strokes",
    "削除したレイヤーには描けない": "Cannot draw on a removed layer",
    "線の id が空か、重なっている": "The stroke ids are empty or duplicated",
    "線 {id} はもう消してある": "Stroke {id} is already erased",
    "一度に扱えるのは1つのレイヤーの線だけ": "Only strokes on a single layer can be handled at once",
    "マウスの線は筆圧を持たない（筆圧は null で送る）": "Mouse strokes have no pressure (send pressure as null)",
    "線の id が重なっている": "The stroke ids are duplicated",
    "線 {id} はもうある": "Stroke {id} already exists",
    "線 {id} をその値にできない: {reason}": "Stroke {id} cannot take that value: {reason}",
    "消しゴムがどの線にも触れていない": "The eraser did not touch any stroke",
    "線の画像は線のバージョン {made_from} から作ったが、今のバージョンは {current}。描き直して上げる":
        "The stroke image was made from stroke version {made_from}, but the current version is {current}. "
        "Redraw and upload it again",
    "レイヤーがそのコマの物ではない": "The layer does not belong to that panel",
    "ペンの線を持つレイヤーは、線の消しゴム（erase_pen_strokes）で消す":
        "A layer that holds pen strokes is erased with the stroke eraser (erase_pen_strokes)",
    "消している間に絵が替わった。今の絵で消し直す": "The image changed while erasing. Erase again on the current image",
    "消した後の絵の大きさが元の絵と違う": "The size of the erased image differs from the original image",
    # PSD の戻し（psd_import_operations.py）
    "PSD を戻すのは人だけ": "Only a person can bring an edited PSD back",
    "このページを PSD に書き出し終えた記録ではない": "This is not a record of a finished PSD export of this page",
    "この2ページを見開きの1枚に書き出した記録ではない": "This is not a record of exporting these two pages as one spread",
    "レイヤーのページ {page_id} は戻し先のページではない": "The layer's page {page_id} is not the page being brought back",
    "{kind} のレイヤーには絵（image）と置き場（box_mm）が要る":
        "A {kind} layer requires an image (image) and a placement (box_mm)",
    "{table}:{id} はこのページの物ではない": "{table}:{id} does not belong to this page",
    "ページ {id} は戻し先のページではない": "Page {id} is not the page being brought back",
    "変わったレイヤーには印（marker）が要る": "A changed layer requires a marker (marker)",
    "印 {marker} の表 {table} は戻せない": "Table {table} of marker {marker} cannot be brought back",
    "無くなったレイヤーには印（marker）が要る": "A missing layer requires a marker (marker)",
    # 確認の状態（review_operations.py）
    "{before} から {after} へは移せない": "Cannot move from {before} to {after}",
    "取り消す記録の対象が違う": "The record to undo is for a different target",
    "取り消す記録のあとに状態が変わっている。今の状態から移し直す":
        "The status changed after the record to undo. Move it again from the current status",
    "削除したページの状態は変えない": "The status of a removed page cannot be changed",
    "作品の状態は、その作品の id を target_id に渡す": "For a work's status, pass that work's id as target_id",
    "直しが要るにするときは、何を直すかをコメントに書く": "When setting Needs changes, write what to fix in the comment",
    # まとめて戻す（row_snapshot.py）
    "戻せない表: {table}": "Table cannot be restored: {table}",
    "まとめて戻す操作は人だけが出せる": "Only a person can submit a bulk restore",
    # 文字とレイヤー（text_and_layer_operations.py）
    "文字の箱の範囲が正しくない: {box}": "The text box range is invalid: {box}",
    "描き文字には話者とフキダシの種類が無い": "A sound effect has no speaker or balloon type",
    "描き文字にはしっぽが無い": "A sound effect has no tail",
    "描き文字にはフキダシの形が無い": "A sound effect has no balloon shape",
    "文字の値が正しくない: {reason}": "The text values are invalid: {reason}",
    "{field} は空にできない（ルビ・仕上げを外すときは []、置き方を戻すときは {{}}）":
        "{field} cannot be empty (use [] to remove ruby or finishing, {{}} to reset the transform)",
    "文字を動かせるのは同じページのコマの間だけ": "Text can only be moved between panels on the same page",
    "手描きレイヤーはAIが作れない": "AI cannot create a hand-drawn layer",
    "ペンの線を持つレイヤーの絵は線から作る画像。絵を替えるときは set_stroke_cache を使う":
        "The image of a layer that holds pen strokes is made from the strokes. Use set_stroke_cache to replace it",
    "手描きレイヤーはAIが変えられない": "AI cannot change a hand-drawn layer",
    # 探す・置き換える（text_search_and_replace.py）
    "探す文字が空": "The search text is empty",
    "置き換える前と後が同じ": "The text before and after replacing is the same",
    "一致する所が無い": "No matches found",
    "文字 {id} にルビがあり、置き換えで字数が変わる（ルビを先に直す）":
        "Text {id} has ruby and replacing changes its length (fix the ruby first)",
    # 訳文（text_translation_operations.py）
    "作品の言語（set_work_settings の preferences.language）を先に決める。どれが元の言語か分からない":
        "Set the work's language (preferences.language in set_work_settings) first. The source language is unknown",
    "{language} は作品の言語。元の文字は update_text_item で変える":
        "{language} is the work's language. Change the original text with update_text_item",
    "訳文を足すときは text が要る": "text is required when adding a translation",
    "削除した訳文の文字へ足すときは text が要る": "text is required when adding to a text whose translation was removed",
    "訳文を空にするときは set_text_translation_removed で削除する":
        "To clear a translation, remove it with set_text_translation_removed",
    # 作品の設定（work_setting_operations.py）
    "役が無い: {role}": "Role does not exist: {role}",
    "ローカルの接続先は常に送ってよい。足す・外すのは、ローカルと言えない先だけ（allowed_destinations.py）":
        "Local connections can always be sent to. Only destinations that are not local can be added or removed "
        "(allowed_destinations.py)",
    "閾値には出典と検証の状態が要る": "A threshold requires a source and a verification status",
    # 作品・話・ページ・コマ（work_tree_operations.py）
    "絵が決まっていないので、切り抜きと置き場を決められない": "No image is set, so the clipping and placement cannot be set",
    "切り抜き {crop} が絵の大きさ {width}x{height} の外に出ている":
        "Clipping {crop} extends outside the image size {width}x{height}",
    "人の確定印を変えられるのは人だけ": "Only a person can change the manual confirmation mark",
    "adjustments は空にできない（外すときは []）": "adjustments cannot be empty (use [] to remove them)",
    "ページの種類・色の種類・解像度・ノンブルの出し方を変えるのは人だけ":
        "Only a person can change the page type, color type, resolution, and page number display",
    "巻・話・コマの型・見開きを削除する・戻すのは人だけ":
        "Only a person can remove or restore volumes, episodes, panel templates, and spreads",
    "{head}; {tail}": "{head}; {tail}",
    "見開きに戻せない: {reasons}": "Cannot restore the spread: {reasons}",
}
