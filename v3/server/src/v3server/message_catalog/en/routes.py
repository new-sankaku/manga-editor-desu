"""英語の訳：API の受け口（http_routes/）と、v3server 直下の部品（ログイン・絵の置き場と入口・ロック・送り先の制限）。"""

MESSAGES = {
    # http_routes/ai_job_routes.py
    "企画の文（あらすじ・読者・メモ）がまだ無い": "The planning text (synopsis, audience, notes) is still empty",
    "削除された赤入れ": "This markup has been deleted",
    "annotation はサーバーが書く。依頼に入れられない":
        "annotation is written by the server and cannot be included in the request",
    # http_routes/export_routes.py
    "作品の言語（preferences.language）が決まっていない。どれが元の言語か分からない":
        "The work's language (preferences.language) is not set, so the source language is unknown",
    "作品 {id}": "Work {id} not found",
    "同じページが2回ある": "The same page appears twice",
    "ページ {id} は削除されている": "Page {id} has been deleted",
    "V3_TEXT_RENDER_SCRIPT が無い。文字の組み方を確かめられない":
        "V3_TEXT_RENDER_SCRIPT is not set, so the lettering layout cannot be checked",
    "書き出したファイル {name}": "Exported file {name} not found",
    "このページを PSD に書き出し終えた記録ではない": "This is not a record of a finished PSD export of this page",
    "この見開きの PSD は、左のページを記録する前に書き出した物で戻せない（書き出し直す）":
        "This spread's PSD was exported before the left page was recorded and cannot be imported back (export again)",
    # http_routes/harness_routes.py
    "知らない決めごと: {keys}": "Unknown spec keys: {keys}",
    "{stage} を始めるには spec.{key} が要る": "Starting {stage} requires spec.{key}",
    "流れが動いていない（終わったか、まだ始まっていない）": "The workflow is not running (it has finished or has not started yet)",
    "工程は人が始める": "A pipeline must be started by a person",
    "この話の工程の進行役はもう動いている（取り消してから始める）":
        "The pipeline coordinator for this episode is already running (cancel it before starting)",
    "判断は人がする": "Decisions must be made by a person",
    "{kind} の作業は質問を返さない（答えを次の文脈に入れない）":
        "{kind} tasks do not ask questions (answers are not passed to the next context)",
    "この作業の候補でない": "This is not a candidate of this task",
    "この工程の実行は終わっている（{status}）": "This pipeline run has already ended ({status})",
    "工程の承認は人がする": "A pipeline must be approved by a person",
    "決めごとは人が決める": "The spec must be set by a person",
    "終わった工程の実行（{status}）": "This pipeline run has ended ({status})",
    "もう閉じている（{status}）": "Already closed ({status})",
    "通知のルールは人が決める": "Notification rules must be set by a person",
    # http_routes/http_dependencies.py・lock_rules.py
    "{user} に {object} の {relation} が無い": "{user} does not have {relation} on {object}",
    # http_routes/image_file_routes.py
    "usage_terms が正しくない: {reason}": "usage_terms is invalid: {reason}",
    # http_routes/image_generation_routes.py
    "{what} は {fields} のどれか1つで渡す": "{what} must be given as exactly one of {fields}",
    "種を固定するときは seed を渡す": "Provide seed when the seed is fixed",
    "種を乱数にするときは seed を渡さない": "Do not provide seed when the seed is random",
    "{process} は元の絵（source_image_id）が要る": "{process} requires a source image (source_image_id)",
    "{process} は元の絵を受けない": "{process} does not take a source image",
    "種が上限を超える": "The seed exceeds the limit",
    "jobs:{id} に手動編集の範囲のマスクが無い": "jobs:{id} has no mask of manually edited areas",
    # http_routes/job_routes.py
    "止まったものだけもう一度依頼できる": "Only stopped jobs can be requested again",
    # http_routes/login_routes.py
    "V3_AUTH_MODE=oidc のときだけ使える": "Available only when V3_AUTH_MODE=oidc",
    # http_routes/name_check_routes.py
    "閾値 {key} の値の形が {{'value': 数}} でない: {value}": "Threshold {key} must have the form {{'value': number}}: {value}",
    "案の話が合わない": "The proposal belongs to a different episode",
    # http_routes/name_proposal_routes.py
    "作品の page_spec がまだ決まっていない": "The work's page_spec is not set yet",
    "MangaImport を読めない: {reason}": "Could not read the MangaImport document: {reason}",
    # http_routes/page_assignment_and_preview_routes.py
    "ページを描けない: {reason}": "Could not render the page: {reason}",
    # http_routes/pen_stroke_routes.py
    "{what} が JSON ではない: {reason}": "{what} is not valid JSON: {reason}",
    "strokes が正しくない: {reason}": "strokes is invalid: {reason}",
    "消しゴムの線が無い": "There are no eraser strokes",
    "消す絵が無い": "There is no image to erase",
    # http_routes/service_inspection_and_set_routes.py
    "接続先 {id} は {process} を受けられない（先に処理の中身を登録する）":
        "Connection {id} cannot accept {process} (register the process settings first)",
    "プリセット {name} はもうある": "Preset {name} already exists",
    "送り先がまだ無い処理がある（先に PUT /routes/{{process}} で決める）: {processes}":
        "Some processes have no destination yet (set them first with PUT /routes/{{process}}): {processes}",
    "同じ接続先が2回ある": "The same connection appears twice",
    # http_routes/service_routes.py・allowed_destinations.py
    "local と言えない（{reason}）。api として登録し、作品ごとに送ってよい先へ載せる":
        "This cannot be treated as local ({reason}). Register it as api and add it to each work's allowed destinations",
    "{adapter} は送った先のその先が見えないので、ローカルと言えない":
        "{adapter} cannot be treated as local because what lies beyond its destination is not visible",
    "endpoint が無い": "endpoint is missing",
    "endpoint の URL が読めない: {endpoint}": "Could not parse the endpoint URL: {endpoint}",
    "endpoint の URL（{host}）がこのサーバーと同じ PC ではない": "The endpoint URL ({host}) is not on the same PC as this server",
    "comfy_graph_settings は画像生成の処理（{processes}）だけに入れる":
        "comfy_graph_settings can be set only for image generation processes ({processes})",
    "services:{id} の処理 {process}": "Process {process} of services:{id} not found",
    "変える項目がない": "Nothing to change",
    "comfy_check_choices は true か false": "comfy_check_choices must be true or false",
    "その接続先はこの処理を受けられない（先に処理の中身を登録する）":
        "That connection cannot accept this process (register the process settings first)",
    # http_routes/text_typeset_routes.py
    "文字 {id} の箱（box_mm）が決まっていない": "Text {id} has no text box (box_mm) yet",
    "V3_TEXT_RENDER_SCRIPT が無い。文字を組めない": "V3_TEXT_RENDER_SCRIPT is not set, so text cannot be typeset",
    # http_routes/translation_review_import_routes.py
    "作品のページの寸法（page_spec）を先に決める": "Set the work's page size (page_spec) first",
    "usage_terms の形が正しくない: {reason}": "usage_terms has an invalid format: {reason}",
    "今のアプリのプロジェクトとして読めない: {reason}": "Could not read this as a project of the current app: {reason}",
    "言語の形が正しくない: {language}": "Invalid language format: {language}",
    # http_routes/request_size_limit.py
    "要求の本体が上限（{limit} バイト。V3_REQUEST_MAX_BYTES）を超えた":
        "The request body exceeds the limit ({limit} bytes; V3_REQUEST_MAX_BYTES)",
    # image_file_storage.py・image_intake.py
    "絵として読めない: {reason}": "Could not read this as an image: {reason}",
    "受け付けない形式: {format}": "Unsupported format: {format}",
    "絵のピクセルが多すぎる: {reason}": "The image has too many pixels: {reason}",
    "絵のピクセルが多すぎる: {width}×{height}（上限 {limit} ピクセル。V3_IMAGE_MAX_PIXELS）":
        "The image has too many pixels: {width}×{height} (limit {limit} pixels; V3_IMAGE_MAX_PIXELS)",
    "入口の判定で止めた（{judge}）: {detail}": "Blocked by the intake screening ({judge}): {detail}",
    # lock_rules.py
    "個別のロックにはページが要る": "An item lock requires a page",
    "自分のロックだけ外せる。AIのロックを取り返すときは取得する":
        "You can release only your own locks. To take back a lock held by AI, acquire it",
    # review_progress.py（成功の返事に入れる文）
    "未検証。1枚の時間は（今 − 作品を作った時）÷ 承認したページの数。キューの時間は入れていない":
        "Unverified. Time per page = (now − work creation time) ÷ approved pages. Queue time is not included",
    "この作品で承認したページがまだ無いので、1枚にかかる時間を出せない":
        "No pages of this work have been approved yet, so the time per page cannot be calculated",
    # request_authentication.py
    "X-V3-User が無い（V3_AUTH_MODE=dev_header）": "X-V3-User is missing (V3_AUTH_MODE=dev_header)",
    "Authorization は Bearer <トークン> の形で送る": "Send Authorization as Bearer <token>",
    "トークンを確かめられない: {error}": "Could not verify the token: {error}",
    "ログインしていない（/auth/login）": "Not logged in (/auth/login)",
    "クッキーで書き換えるときはヘッダー X-V3-Request: 1 が要る": "Write requests with a cookie require the header X-V3-Request: 1",
    # usage_terms_schema.py
    "規約・許諾のURL（terms_url）か、確かめた所の説明（terms_note）が要る":
        "Provide either the URL of the terms or license (terms_url) or a note on where they were checked (terms_note)",
}
