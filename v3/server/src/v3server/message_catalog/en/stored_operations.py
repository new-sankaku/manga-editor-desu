"""英語の訳：残してから出す文（ms()）のうち、操作（operations/）の取り消しの名前・判断待ちの理由・案のメモ、
今のアプリからの取り込みの報告（current_app_import/）、絵の出どころのメモ、入口の判定の記録、箱で組んだ場所の図の失敗。"""

MESSAGES = {
    # 取り消しの名前（出来事の一覧に出る。operations/ の各ファイル）
    "赤入れを付けた取り消し": "Undo adding markup",
    "赤入れを直した取り消し": "Undo editing markup",
    "赤入れの依頼の記録の取り消し": "Undo recording the markup job",
    "話の構成を変えた取り消し": "Undo changing the episode outline",
    "前の話から引き継いだ取り消し": "Undo carrying over from the previous episode",
    "伏線を足した取り消し": "Undo adding foreshadowing",
    "伏線を変えた取り消し": "Undo changing foreshadowing",
    "企画を変えた取り消し": "Undo changing the planning",
    "設定資料を足した取り消し": "Undo adding a reference sheet",
    "設定資料を変えた取り消し": "Undo changing a reference sheet",
    "構成を書いた取り消し": "Undo writing the outline",
    "トーン・図形を置いた取り消し": "Undo placing a screentone or shape",
    "トーン・図形を変えた取り消し": "Undo changing a screentone or shape",
    "仕上げをまとめて外した取り消し": "Undo removing all finishing",
    "ペンの線を足した取り消し": "Undo adding pen strokes",
    "ペンの線を変えた取り消し": "Undo changing pen strokes",
    "ペンの線を消した取り消し": "Undo removing pen strokes",
    "線の消しゴムの取り消し": "Undo the stroke eraser",
    "線の画像を付けた取り消し": "Undo attaching the line image",
    "ピクセルの消しゴムの取り消し": "Undo the pixel eraser",
    "PSD の戻しの取り消し": "Undo importing the PSD back",
    "判断待ち {id} の取り消し": "Undo the decision on item {id}",
    "「{find}」を「{replace}」に置き換えた取り消し": "Undo replacing \"{find}\" with \"{replace}\"",
    "削除する・戻すを判断待ちにした取り消し": "Undo holding a remove or restore for a decision",
    "今のアプリのプロジェクト {name} の取り込み": "Import of current-app project {name}",
    "コマを分ける": "Split panel",
    "コマを合わせる": "Merge panels",
    "ばらばらに割る": "Split randomly",
    "図形のコマを足す": "Add shape panel",
    "コマの型を保存する": "Save panel template",
    "コマの型を当てる": "Apply panel template",
    # 確認の記録のコメント（review_operations.py。取り消しの記録に入れる）
    "取り消し": "Undo",
    # 判断待ちの理由（panel_frame_operations.py・psd_import_operations.py）
    "手動編集の印の付いたコマ・文字に当たる": "This touches panels or text with manual-edit marks",
    "{reason}（{language} の訳文は書き出した後に削除された）": "{reason} (the {language} translation was deleted after the export)",
    "書き出したレイヤーが PSD に無い": "An exported layer is missing from the PSD",
    "人が「動かさない」にしている物のレイヤーが変わった": "The layer of an item locked by a person was changed",
    "どのページの物でもないレイヤー（見開きの絵・見開きの紙）のピクセルが変わった":
        "The pixels of a layer that belongs to no page (spread image or spread paper) were changed",
    "書き出した後に、元の物が削除された": "The original item was deleted after the export",
    "どのコマにも入っていない新しいレイヤー": "A new layer that is not inside any panel",
    "「動かさない」のコマに入った新しいレイヤー": "A new layer inside a locked panel",
    "文字のレイヤーのピクセルが変わった": "The pixels of a text layer were changed",
    "線や形の値から描いたレイヤーのピクセルが変わった": "The pixels of a layer drawn from stroke or shape values were changed",
    # ネームの案のメモ（panel_layout_proposal.py）
    "コマ割りの計算。固定した枠 {panels}": "Calculated panel layout. Pinned frames: {panels}",
    # 手動編集の範囲のメモ（pen_stroke_operations.py）
    "消しゴムで消した所": "Area erased with the eraser",
    # 今のアプリの形の読み取り（current_app_import/fabric_geometry.py）
    "知らない {key}: {value}": "Unknown {key}: {value}",
    "多角形の点が3つ無い": "The polygon has fewer than three points",
    "線の命令の形が正しくない: {command}": "The path command is malformed: {command}",
    "読めない線の命令: {command}": "Unsupported path command: {command}",
    "色の形でない: {value}": "Not a color value: {value}",
    "読めない色: {value}": "Could not read the color: {value}",
    # 今のアプリの絵の読み取り（current_app_import/project_file_reader.py）
    "絵が base64 の data URL でない: {head}": "The image is not a base64 data URL: {head}",
    "絵の base64 を読めない: {reason}": "Could not decode the image's base64: {reason}",
    # 取り込みの報告：文字（current_app_import/import_plan.py）
    "文字の色の不透明度 {opacity} は移していない": "Text color opacity {opacity} was not carried over",
    "文字の縁（{color}・太さ {width}）は移していない": "Text outline ({color}, width {width}) was not carried over",
    "文字の背景色（{color}）は移していない": "Text background color ({color}) was not carried over",
    "太さ {weight} は移していない": "Font weight {weight} was not carried over",
    "字の形 {style} は移していない": "Font style {style} was not carried over",
    "下線・取り消し線は移していない": "Underline and strikethrough were not carried over",
    "文字の一部だけの書式（styles）は移していない": "Formatting applied to part of the text (styles) was not carried over",
    "画像の文字の効果（{effect}）は移していない": "The image-text effect ({effect}) was not carried over",
    "コマの外の文字は V3 で置く所が無い（文字はコマに属する）。文字: {text}":
        "Text outside any panel has no place in V3 (text belongs to a panel). Text: {text}",
    "書体の名前 {family} をそのまま入れた（書き出しは V3_FONT_DIR に同じ名前の書体が要る）":
        "Font name {family} was kept as is (export needs a font with the same name in V3_FONT_DIR)",
    "フキダシの線が見つからないので、線の無い文字として入れた": "The balloon line was not found, so the text was imported without a line",
    "フキダシに入っていない文字はナレーションの箱（caption）として入れた。描き文字なら種類を直す":
        "Text outside a balloon was imported as a narration box (caption). Change the kind if it is a sound effect",
    # 取り込みの報告：コマ
    "コマの形 {type} は読めない": "Panel shape {type} is not supported",
    "コマの形を読めない: {reason}": "Could not read the panel shape: {reason}",
    "読む順は位置から決めた（今のアプリは読む順を持たない）":
        "Reading order was decided from position (the current app has no reading order)",
    "枠の線（{color}・太さ {width}px）を枠の線（frame_style）に入れた":
        "The frame line ({color}, width {width}px) was imported as the frame line (frame_style)",
    "枠の線の不透明度 {opacity} は移していない（V3 の枠の線は不透明）":
        "Frame line opacity {opacity} was not carried over (V3 frame lines are opaque)",
    "コマの塗り {fill} は移していない": "Panel fill {fill} was not carried over",
    # 取り込みの報告：フキダシ
    "フキダシの線を読めない: {reason}": "Could not read the balloon line: {reason}",
    "フキダシの線に輪が無い": "The balloon line has no closed outline",
    "外形を1つの多角形にした（曲線は点の列に直した）": "The outline was made into one polygon (curves were converted to points)",
    "ほかの {n} 本の線（穴・点線・飾り）は移していない": "The other {n} lines (holes, dotted lines, decoration) were not carried over",
    "フキダシの格子（speechBubbleGrid）は移していない": "The balloon grid (speechBubbleGrid) was not carried over",
    "フキダシの文字の箱の控え。文字の箱から作り直せる": "A copy of the balloon's text box. It can be rebuilt from the text box",
    "フキダシの文字がコマの外にある": "The balloon's text is outside any panel",
    "フキダシに文字が無い（V3 のフキダシは文字に付く）": "The balloon has no text (in V3 a balloon is attached to text)",
    # 取り込みの報告：絵
    "絵の中身がプロジェクトに無い（.img が無い）": "The image data is missing from the project (no .img)",
    "絵を入れられない: {reason}": "Could not import the image: {reason}",
    "コマの外の絵は V3 で置く所が無い（レイヤーはコマに属する）": "An image outside any panel has no place in V3 (layers belong to a panel)",
    "トーン・効果線は今のアプリでは絵なので、絵のレイヤーとして入れた（網点の値には戻せない）":
        "Screentones and effect lines are images in the current app, so they were imported as image layers "
        "(they cannot be turned back into dot values)",
    "絵の効果（filters: {filters}）は移していない": "Image effects (filters: {filters}) were not carried over",
    "重ね方 {mode} は移していない": "Blend mode {mode} was not carried over",
    "コマの絵（panels.image_id）として入れた": "Imported as the panel image (panels.image_id)",
    # 取り込みの報告：ペンの線
    "筆は鉛筆（pencil）として入れた（今のアプリの path は筆の種類を持たない）":
        "The brush was imported as pencil (a path in the current app has no brush type)",
    "点の時刻は今のアプリに無いので 0 を入れた（筆圧も無いので null）":
        "Point times do not exist in the current app, so 0 was used (pressure does not exist either, so null)",
    "線の画像は画面が線から描く。画面で開いて描くまで、書き出しと入稿前の確かめは止まる":
        "The line image is drawn by the screen from the strokes. "
        "Export and the pre-submission check stop until it is opened and drawn in the screen",
    "模様の筆（模様・縦線・横線）の線は、模様が今のアプリの絵で、V3 の筆の模様に直せない":
        "Strokes of a pattern brush (pattern, vertical lines, horizontal lines) use an image from the current app as the pattern "
        "and cannot be converted to a V3 brush pattern",
    "ペンの線を読めない: {reason}": "Could not read the pen stroke: {reason}",
    "線の色か点が無い（見えない線）": "The stroke has no color or no points (an invisible stroke)",
    "線の太さが 0": "The stroke width is 0",
    "線の不透明度が 0（見えない線）": "The stroke opacity is 0 (an invisible stroke)",
    "線の中の塗り {fill} は移していない": "Fill {fill} inside the stroke was not carried over",
    "今のアプリの消しゴムで消した所（eraser）は移していない。消した所も線が見える":
        "Areas erased with the current app's eraser (eraser) were not carried over. The strokes stay visible in the erased areas",
    "コマの外の線は V3 で置く所が無い（レイヤーはコマに属する）": "A stroke outside any panel has no place in V3 (layers belong to a panel)",
    # 取り込みの報告：ほかの物・ページ
    "絵記号（アイコンの SVG）は V3 の図形の形に直せない": "A symbol (icon SVG) cannot be converted to a V3 shape",
    "V3 に受ける所が無い物（type={type}, customType={custom_type}）":
        "V3 has no place for this object (type={type}, customType={custom_type})",
    "ページの寸法 {width}x{height}mm が作品の仕上がり {trim_width}x{trim_height}mm と違う":
        "Page size {width}x{height}mm differs from the work's trim size {trim_width}x{trim_height}mm",
    "キャンバスの縦横の比がページの mm の比と合わない": "The canvas aspect ratio does not match the page's ratio in mm",
    "{why}。ページだけ作り、中の物は入れていない": "{why}. Only the page was created; its contents were not imported",
    "取り消しの記録 {n} 件は移さない（最後の姿だけ）": "{n} undo history entries are not carried over (only the final state)",
    "プロジェクトに入っていた書体 {n} 個は受ける API が無い（V3 の書体は V3_FONT_DIR に置く）":
        "There is no API to receive the {n} fonts in the project (V3 fonts go in V3_FONT_DIR)",
    "参照の絵 {n} 枚は受ける API が無い（設定資料に人が入れ直す）":
        "There is no API to receive the {n} reference images (a person adds them to the reference sheets again)",
    "読む対象でないファイル {name}": "File {name} is not one this import reads",
    # 絵の出どころのメモ（image_files.source_note。import_plan.py・http_routes/translation_review_import_routes.py）
    "今のアプリのプロジェクト {file} の {page}ページ目の {nth}番目の物（{name}）。{origin}":
        "Object {nth} ({name}) on page {page} of current-app project {file}. {origin}",
    "今のアプリのプロジェクト {name}（sha256 {sha}）から取り込んだ": "Imported from current-app project {name} (sha256 {sha})",
    # 入口の判定の記録（image_intake.py）
    "規制の判定の手段がまだ決まっていない（V3ハーネス設計 12章）。判定していない":
        "The method for the content screening is not decided yet (V3 harness design, chapter 12). Not screened",
    # 箱で組んだ場所の図（background_scene3d/box_scene_depth_render.py）
    "箱が1つもありません": "There are no boxes",
    "線の太さは1ピクセル以上にしてください": "The line thickness must be at least 1 pixel",
    "カメラから箱が1つも見えません": "No box is visible from the camera",
}
