"""英語の訳：コマ割り・ネームの形・取り込み・ペンの線・書き出し（panel_layout から print_export までの8フォルダ）。"""

MESSAGES = {
    # panel_layout
    "コマの最小の大きさは0より大きくなければならない": "Minimum panel size must be greater than 0",
    "{page}ページ：固定する枠のコマ {panels} がこのページに無い":
        "Page {page}: panels {panels} with pinned frames are not on this page",
    "{page}ページ：必須の制約が両立しない（{what}）": "Page {page}: required constraints conflict ({what})",
    "固定する枠のコマ {panels} がネームに無い": "Panels {panels} with pinned frames are not in the storyboard",
    "基本枠の上の辺": "top edge of the base frame",
    "基本枠の下の辺": "bottom edge of the base frame",
    "{row}段目の最小の高さ": "minimum height of row {row}",
    "{row}段目と{next_row}段目の隙間": "gap between rows {row} and {next_row}",
    "コマ{panel}の上端の最小の幅": "minimum width at the top of panel {panel}",
    "コマ{panel}の下端の最小の幅": "minimum width at the bottom of panel {panel}",
    "コマ{panel}の幅の比": "width ratio of panel {panel}",
    "{row}段目の高さの比": "height ratio of row {row}",
    "コマ{panel}の固定した枠": "pinned frame of panel {panel}",
    "{page}ページ：見開きのページの割りは、まだ計算できない":
        "Page {page}: the panel layout of a spread page cannot be calculated yet",
    "{page}ページ：段の割り（rows）が決まっていない": "Page {page}: the row layout (rows) is not set",
    "{page}ページ：形が未定のコマ {panels} がある": "Page {page}: panels {panels} have no shape set",
    "{page}ページ：段の高さの比かコマの幅の比が決まっていない":
        "Page {page}: row height ratios or panel width ratios are not set",
    "{page}ページ：段の数 {rows} と比の数（高さ {heights}・幅 {widths}）が合わない":
        "Page {page}: row count {rows} does not match the number of ratios (height {heights}, width {widths})",
    "{page}ページ：{row}段目にコマが無い": "Page {page}: row {row} has no panels",
    "{page}ページ：{row}段目のコマ {panels} と幅の比 {ratios} の数が合わない":
        "Page {page}: row {row} has {panels} panels but {ratios} width ratios",
    "{page}ページ：比に0以下がある": "Page {page}: a ratio is 0 or less",
    "{page}ページ：段に並べたコマの番号と、ページのコマの番号が合わない":
        "Page {page}: panel numbers in the rows do not match the panel numbers on the page",
    "{page}ページ：区切りの傾きの数が、段ごとの区切りの数（コマ数−1）と合わない":
        "Page {page}: the number of divider slants does not match the dividers per row (panel count - 1)",
    "規格の左右の隙間が上下の隙間より狭くない":
        "The horizontal gutter in the page spec is not narrower than the vertical gutter",
    "{page}ページ：斜めの区切りは constrained_tier_layout で計算する":
        "Page {page}: slanted dividers are calculated by constrained_tier_layout",
    "斜めに切るときは角度が要る": "An angle is required for a diagonal cut",
    "凹んだ枠は1本の線で2つに分けられないことがあるので切らない":
        "Concave frames are not cut because a single line may not split them in two",
    "切る線が枠を横切っていない（または間の幅が枠より広い）":
        "The cut line does not cross the frame (or the gap is wider than the frame)",
    "分けた形の幅 {width}mm が、コマの最小の大きさ {minimum}mm より細い":
        "The split piece is {width}mm wide, narrower than the minimum panel size of {minimum}mm",
    "{attempts} 回試しても切れなかった: {reason}": "Could not cut after {attempts} attempts: {reason}",
    "図形の箱が正しくない: {box}": "Invalid bounding box for the shape: {box}",
    "知らない形: {shape}": "Unknown shape: {shape}",
    # name_import
    "座標が 0〜1 の外: {point}": "Coordinates are outside 0 to 1: {point}",
    "知らないコマの形: {kind}": "Unknown panel shape: {kind}",
    "format=manga-editor-import・version=1 の文書ではない":
        "Not a document with format=manga-editor-import and version=1",
    "コマ {id} の頂点が3つより少ない": "Panel {id} has fewer than 3 vertices",
    "ページが無い": "There are no pages",
    # hand_tools
    "{brush} は色を持たない": "{brush} does not take a color",
    "{brush} は色を持つ": "{brush} requires a color",
    "{brush} は乱れのある筆なので seed が要る": "{brush} is a randomized brush, so a seed is required",
    "1本の線の中で、筆圧のある点と無い点が混ざっている":
        "A single stroke mixes points with and without pen pressure",
    "筆圧は 0〜1: {pressure}": "Pen pressure must be between 0 and 1: {pressure}",
    "点の時刻が描いた順に並んでいない": "Point timestamps are not in drawing order",
    "レイヤー {id} の線の画像が無い（線のバージョン {revision}）。画面で開いて線から描いて上げる":
        "Layer {id} has no stroke image (stroke version {revision}). Open it on screen to redraw it from the strokes "
        "and upload it",
    "レイヤー {id} の絵は古い線の画像（線のバージョン {image_revision}、今は {revision}）。画面で描き直して上げる":
        "The image of layer {id} is an outdated stroke image (stroke version {image_revision}, now {revision}). "
        "Redraw it on screen and upload it",
    # current_app_import
    "ほどいた中身が上限（{limit} バイト。V3_CURRENT_APP_IMPORT_MAX_BYTES）を超える":
        "The unpacked content exceeds the limit ({limit} bytes; V3_CURRENT_APP_IMPORT_MAX_BYTES)",
    "LZ4 の中身が途中で切れている": "The LZ4 data is truncated",
    "ファイルが短すぎる（今のアプリのプロジェクトではない）":
        "The file is too short (not a project from the current app)",
    "見出しの長さが正しくない（今のアプリのプロジェクトではない）":
        "Invalid header length (not a project from the current app)",
    "見出しを読めない: {reason}": "Cannot read the header: {reason}",
    "見出しの形が正しくない": "Invalid header format",
    "見出しの大きさが正しくない": "Invalid sizes in the header",
    "LZ4 の中身をほどけない: {reason}": "Cannot decompress the LZ4 data: {reason}",
    "見出しの大きさの合計と、ほどいた中身の大きさが合わない":
        "The total size in the header does not match the size of the unpacked content",
    "ページの中に {name} が無い": "The page has no {name}",
    "{page}ページ目に state_*.json が無い": "Page {page} has no state_*.json",
    "{page}ページ目の {file} が fabric.js のキャンバスの形でない": "{file} on page {page} is not a fabric.js canvas",
    "{page}ページ目の canvas_info.json に {key} が無い": "canvas_info.json on page {page} has no {key}",
    "今のアプリのプロジェクトの中身でない: {names}": "Not the contents of a project from the current app: {names}",
    # name_structure
    "切り抜きの範囲が正しくない: {crop}": "Invalid crop range: {crop}",
    "置き場の範囲が正しくない: {box}": "Invalid placement range: {box}",
    "重ね方は1つだけ": "Only one blend mode is allowed",
    "仕上げの値が正しくない: {reason}": "Invalid finishing values: {reason}",
    "ルビの範囲 {start}〜{end} が文字（{length}文字）の外か、空":
        "Ruby range {start}-{end} is outside the text ({length} characters) or empty",
    "ルビの範囲が重なっている": "Ruby ranges overlap",
    "線を描かないフキダシには型も外形もしっぽも無い": "A balloon with no outline has no preset, outline, or tail",
    "フキダシの外形（outline_mm）が要る": "The balloon outline (outline_mm) is required",
    "型のフキダシには型の名前（preset）が要る": "A preset balloon requires a preset name (preset)",
    "自分で描いたフキダシには型の名前が無い": "A custom-drawn balloon has no preset name",
    "{kind} には {fields} が要る": "{kind} requires {fields}",
    "{kind} には3つ以上の点（points_mm）が要る": "{kind} requires at least 3 points (points_mm)",
    "path には2つ以上の点が要る": "path requires at least 2 points",
    "絵記号には名前（symbol_name）が要る": "A symbol requires a name (symbol_name)",
    "{kind} は箱いっぱいに描くので点を持たない": "{kind} fills its box, so it takes no points",
    "線も塗りも無い図形は見えない": "A shape with neither stroke nor fill is invisible",
    "色の種類 {modes} の解像度が無い": "No resolution is set for color modes {modes}",
    "解像度は正の数": "Resolution must be a positive number",
    "ページの種類 {kinds} のノンブルの出し方が無い": "No page number display is set for page kinds {kinds}",
    "書式が1つも無い": "No formatting is set",
    "書式の範囲 {start}〜{end} が文字（{length}文字）の外か、空":
        "Format range {start}-{end} is outside the text ({length} characters) or empty",
    "書式の範囲が重なっている": "Format ranges overlap",
    # print_export
    "見開きの2ページが隣り合っていない（{first}ページ目と{second}ページ目）":
        "The two pages of the spread are not adjacent (pages {first} and {second})",
    "左": "left",
    "右": "right",
    "見開きの前のページが{got_first}・後ろのページが{got_second}になる（{first}・{second}ページ目）。"
    "この読む向きでは前が{want_first}・後ろが{want_second}":
        "The first page of the spread would be on the {got_first} and the second on the {got_second} "
        "(pages {first} and {second}). In this reading direction the first is on the {want_first} "
        "and the second on the {want_second}",
    "ページ {id} が2つの見開きに入っている": "Page {id} is in two spreads",
    "見開きのページが削除されているか、別の話にある": "A page of the spread is deleted or belongs to another episode",
    "1ページ目を左に置くか（作品の first_page_is_left）が決まっていないので、見開きの左右を決められない":
        "Whether page 1 goes on the left (the work's first_page_is_left) is not set, "
        "so the sides of the spread cannot be decided",
    "{language} の訳文が無い文字がある: {ids}": "Some text has no {language} translation: {ids}",
    "絵 {id} が無い": "Image {id} does not exist",
    "ページ {id} が無い": "Page {id} does not exist",
    "作品のページの寸法（page_spec）が決まっていない": "The page dimensions of the work (page_spec) are not set",
    "V3_TEXT_RENDER_SCRIPT が無い。文字を描けない": "V3_TEXT_RENDER_SCRIPT is not set. Text cannot be rendered",
    "知らない重ね方: {mode}": "Unknown blend mode: {mode}",
    "知らないトーン: {kind}": "Unknown screentone: {kind}",
    "コマ {id} に枠が無い": "Panel {id} has no frame",
    "コマ {id} の枠の線が決まっていない（コマの frame_style か、作品の preferences.frame_style）":
        "The frame line of panel {id} is not set (the panel's frame_style or the work's preferences.frame_style)",
    "フキダシ {id} のしっぽの根元の幅・曲がり（balloon_shape.tail_base_width_mm・tail_bend_ratio）が決まっていない":
        "The tail base width and bend of balloon {id} are not set "
        "(balloon_shape.tail_base_width_mm, tail_bend_ratio)",
    "文字「{text}」（{id}）の色（decoration.fill）が決まっていない。"
    "取り込んだ文字か古い文字は色を持たないことがある。文字の飾りで色を選び直す":
        "The color (decoration.fill) of text \"{text}\" ({id}) is not set. "
        "Imported or old text may have no color. Choose a color again in the text decoration",
    "文字 {id} の箱（box_mm）が決まっていない": "Text {id} has no text box (box_mm) yet",
    "文字 {id} の大きさ（font_size_pt）が決まっていない": "The size (font_size_pt) of text {id} is not set",
    "文字 {id} の書体が決まっていない（文字の font_family か、作品の preferences.fonts_by_kind）":
        "The font of text {id} is not set (the text's font_family or the work's preferences.fonts_by_kind)",
    "文字 {id} の組版（行間・自動の改行・縦中横）が決まっていない（文字の typesetting か、作品の preferences.typesetting）":
        "The typesetting (line spacing, automatic line breaks, tate-chu-yoko) of text {id} is not set "
        "(the text's typesetting or the work's preferences.typesetting)",
    "コマ {id} の絵の置き場が決まっていない": "The image placement of panel {id} is not set",
    "レイヤー {id} の絵の置き場が決まっていない": "The image placement of layer {id} is not set",
    "トーン {id} を貼るコマ {panel} がこのページに無い": "Panel {panel} for screentone {id} is not on this page",
    "フキダシ {id} の線（line_width_mm・line_color）が決まっていない":
        "The outline (line_width_mm, line_color) of balloon {id} is not set",
    "PSD として読めない: {reason}": "Cannot read the file as a PSD: {reason}",
    "PSD のピクセルが多すぎる: {width}×{height}（上限 {limit} ピクセル。V3_IMAGE_MAX_PIXELS）":
        "The PSD has too many pixels: {width}×{height} (limit {limit} pixels; V3_IMAGE_MAX_PIXELS)",
    "PSD のレイヤーが多すぎる: {count}（上限 {limit}。V3_PSD_MAX_LAYERS）":
        "The PSD has too many layers: {count} (limit {limit}; V3_PSD_MAX_LAYERS)",
    "PSD のレイヤー「{name}」のピクセルが多すぎる: {width}×{height}（上限 {limit} ピクセル）":
        "PSD layer \"{name}\" has too many pixels: {width}×{height} (limit {limit} pixels)",
    "V3_FONT_DIR が無い。書体のファイルが無いので文字を描けない":
        "V3_FONT_DIR is not set. Text cannot be rendered without font files",
    "書体 {family} のファイルが {folder} に無い（ファイルの名前から拡張子を除いたものが書体の名前）":
        "No file for font {family} in {folder} (the font name is the file name without its extension)",
    "書体 {family} のファイルが2つ以上ある: {files}": "There are two or more files for font {family}: {files}",
    "文字を描けなかった（終了コード {code}）: {stderr}": "Could not render the text (exit code {code}): {stderr}",
    "文字 {id} の書体に無い字がある: {chars}（ほかの書体では描かない。書体を替えるか、文字の一部の書式で書体を選ぶ）":
        "The font of text {id} is missing some characters: {chars} (no other font is substituted. "
        "Change the font, or choose a font in the formatting of part of the text)",
    "文字 {id} を描いたが、見えるピクセルが無い（文字が空 など）":
        "Text {id} was rendered but has no visible pixels (the text may be empty)",
}
