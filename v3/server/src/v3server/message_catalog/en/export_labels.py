"""英語の訳：返事にその場で入れる説明（入稿前の確かめの結果・PSD の注意書き・ネームの読み込みで外した理由・
コマ割りで守れなかった比・ネームの検査の閾値の意味）。"""

MESSAGES = {
    # 入稿前の確かめ（print_export/preflight_checks.py）
    "上": "top",
    "下": "bottom",
    "ノド": "gutter",
    "小口": "outer edge",
    "{head}・{tail}": "{head}, {tail}",
    "ページ数 {count} が {multiple} の倍数でない（あと {rest} ページで揃う）":
        "The page count {count} is not a multiple of {multiple} (short by {rest})",
    "文字「{text}」が安全線の外に出ている（{sides}）": "Text \"{text}\" extends outside the safe area ({sides})",
    "文字「{text}」の書体に無い字がある: {chars}": "The font of text \"{text}\" is missing some characters: {chars}",
    "文字「{text}」が箱に入りきらない": "Text \"{text}\" does not fit in its text box",
    "絵 {id} の置き場が決まっていない": "The placement of image {id} is not set",
    "絵 {id} の実際の解像度 {actual}dpi が、ページの解像度 {dpi}dpi より低い":
        "The effective resolution of image {id} ({actual} dpi) is lower than the page resolution ({dpi} dpi)",
    "2階調のページに色のある絵 {id} がある（書き出しで2階調にする）":
        "A bilevel page contains color image {id} (it is converted to bilevel on export)",
    "グレーのページに色のある絵 {id} がある（書き出しでグレーにする）":
        "A grayscale page contains color image {id} (it is converted to grayscale on export)",
    "判断待ち（{kind}・{table}.{field}）が残っている": "An item still needs a decision ({kind}, {table}.{field})",
    "生成の依頼 {id}（{process}）が終わっていない（{status}）":
        "Generation request {id} ({process}) has not finished ({status})",
    "まだ選んでいない生成の候補 {id} がある（採るか却下する）":
        "Generated candidate {id} has not been decided yet (accept or reject it)",
    "作品の言語（preferences.language）が決まっていない。どれが元の言語か分からない":
        "The work's language (preferences.language) is not set, so the source language is unknown",
    "作品の入稿の設定（preferences.print）が無い": "The work has no submission settings (preferences.print)",
    "紙の作品なのに、ノンブルの設定（preferences.nombre）が無い":
        "This is a paper work, but it has no page number settings (preferences.nombre)",
    "1ページ目を左に置くか（作品の first_page_is_left）が決まっていない（見開き・ノンブル・安全線のノドが決まらない）":
        "Whether page 1 goes on the left (the work's first_page_is_left) is not set "
        "(spreads, page numbers, and the gutter side of the safe area cannot be decided)",
    "ページの種類（表紙・カラー・本文・白ページ）が決まっていない": "The page type (cover, color, body, blank page) is not set",
    "色の種類が決まっていない": "The color mode is not set",
    "解像度が決まっていない": "The resolution is not set",
    "見開きの相手のページと色の種類か解像度が違う（{color_mode} {dpi}dpi・{other_color_mode} {other_dpi}dpi）":
        "The color mode or resolution differs from the other page of the spread "
        "({color_mode} {dpi} dpi vs {other_color_mode} {other_dpi} dpi)",
    "文字「{text}」に {language} の訳文が無い": "Text \"{text}\" has no {language} translation",
    # ICC プロファイル（print_export/cmyk_conversion.py。入稿前の確かめがそのまま返す）
    "カラーを CMYK にする設定があるのに、ICC プロファイルのフォルダ（V3_ICC_DIR）が無い":
        "Color pages are set to be converted to CMYK, but the ICC profile folder (V3_ICC_DIR) is not set",
    "ICC プロファイル {profile} が {folder} に無い": "ICC profile {profile} is not in {folder}",
    "ICC プロファイル {path} が読めない: {error}": "Cannot read ICC profile {path}: {error}",
    "ICC プロファイル {path} は CMYK でない（{space}）": "ICC profile {path} is not a CMYK profile ({space})",
    # PSD の書き出しの注意書き（print_export/export_runner.py）
    "ペンの線は、PSD ではピクセルのレイヤーになります（線のデータはアプリに残ります。PSD から線には戻りません）":
        "Pen strokes become pixel layers in the PSD "
        "(the stroke data stays in the app; strokes cannot be restored from the PSD)",
    # ネームの読み込みで外したセリフの理由（name_import/manga_import_reader.py）
    "解析が除外した（{reason}）": "Excluded by the analysis ({reason})",
    "どのコマにも属さない": "Does not belong to any panel",
    # コマ割りの計算で守れなかった比（panel_layout/constrained_tier_layout.py）
    "高さ {height}（比の1あたり {unit}）": "height {height} ({unit} per ratio unit)",
    "幅 {width}（比の1あたり {unit}）": "width {width} ({unit} per ratio unit)",
    # ネームの検査の閾値の意味（name_checks/。GET /name-checks/threshold-keys）
    "吹き出し1つが顔の四角を覆う割合の上限（0〜1）": "Maximum share of a face box that one balloon may cover (0–1)",
    "吹き出し1つの文字数の上限（改行と空白は数えない）":
        "Maximum number of characters in one balloon (line breaks and spaces are not counted)",
    "吹き出し1つの行数の上限": "Maximum number of lines in one balloon",
    "1コマの吹き出しの数の上限": "Maximum number of balloons in one panel",
    "1ページの吹き出しの数の上限": "Maximum number of balloons on one page",
    "1ページのセリフの文字数の上限": "Maximum number of dialogue characters on one page",
    "コマどうしの隙間の下限（mm）": "Minimum gap between panels (mm)",
    "コマの短い辺の下限（mm）": "Minimum length of a panel's short side (mm)",
    "どのコマにも隙間にも入らない場所の上限（mm²、1ページ）":
        "Maximum area that belongs to neither a panel nor a gap (mm², per page)",
    "上下の段の縦線のずれの下限（mm）": "Minimum offset between the vertical lines of adjacent rows (mm)",
    "向かい合う2ページの段の横線のずれの下限（mm）":
        "Minimum offset between the horizontal row lines of two facing pages (mm)",
    "横長とみなす縦横比（幅÷高さ）の下限（形の種類を数える境目）":
        "Minimum aspect ratio (width ÷ height) treated as wide (the boundary used to count shape types)",
    "縦長とみなす縦横比（幅÷高さ）の上限（形の種類を数える境目）":
        "Maximum aspect ratio (width ÷ height) treated as tall (the boundary used to count shape types)",
    "面積のばらつき（標準偏差÷平均）の、ページの中央値の下限":
        "Minimum page median of the panel area variation (standard deviation ÷ mean)",
    "いちばん大きいコマ÷いちばん小さいコマの、ページの中央値の下限":
        "Minimum page median of largest panel ÷ smallest panel",
    "形が1種類だけのページの割合の上限": "Maximum share of pages with only one panel shape type",
    "基本枠の幅いっぱいのコマの割合の、ページの中央値の上限":
        "Maximum page median of the share of panels spanning the full width of the basic frame",
    "上の辺がほかのコマと揃うコマの割合の、ページの中央値の上限":
        "Maximum page median of the share of panels whose top edge aligns with another panel",
    "1ページのコマ数の上限": "Maximum number of panels on one page",
    "1ページのコマ数の下限": "Minimum number of panels on one page",
    "1ページの段の数の上限": "Maximum number of rows on one page",
    "1ページの段の数の下限": "Minimum number of rows on one page",
    "1段のコマ数の上限": "Maximum number of panels in one row",
    "同じ大きさのコマが続く数の上限": "Maximum run of consecutive panels of the same size",
    "段の割り（段ごとのコマ数）が次のページと同じになる回数の上限（1話）":
        "Maximum number of times the row layout (panels per row) matches the next page (per episode)",
    "「大」のコマが無いページの数の上限（1話）": "Maximum number of pages with no \"large\" panel (per episode)",
    "1ページの「大」のコマの数の上限": "Maximum number of \"large\" panels on one page",
    "1ページの斜めのコマの数の上限": "Maximum number of slanted panels on one page",
    "1ページの枠なし・断ち切りのコマの数の上限": "Maximum number of borderless or bleed panels on one page",
    "会話だけのコマで四角でないものの数の上限（1話）":
        "Maximum number of non-rectangular dialogue-only panels (per episode)",
    "見開きの数の上限（1話）": "Maximum number of spreads (per episode)",
    "前のコマと同じ範囲・同じ角度になる回数の上限（1話）":
        "Maximum number of times a panel repeats the previous panel's shot range and angle (per episode)",
    "寄り（胸から上・顔・部分）が続く数の上限": "Maximum run of consecutive close shots (chest up, face, detail)",
    "全身か、それより広く写すコマが無いページが続く数の上限":
        "Maximum run of consecutive pages with no full-body or wider shot",
    "1つの場面の中の距離の種類（遠・中・寄り）の数の下限":
        "Minimum number of shot distance types (long, medium, close) within one scene",
    "目の高さ以外の角度のコマの割合の上限（1話）":
        "Maximum share of panels at an angle other than eye level (per episode)",
    "登場人物の数の上限（1話）": "Maximum number of characters (per episode)",
    "1コマに写る人物の数の上限": "Maximum number of characters shown in one panel",
}
