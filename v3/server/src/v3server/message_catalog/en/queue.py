"""英語の訳：生成の依頼を受けるとき（generation_queue）と、接続先の様子を読むとき（service_senders）の失敗の文。"""

MESSAGES = {
    # 画像生成の処理の名前（失敗の文に入る）
    "文から作る": "Text to image",
    "絵から作り直す": "Image to image",
    "似た別案": "Variation",
    "囲んで直す": "Fix selected area",
    "描き足す": "Extend",
    "指示で直す": "Edit by prompt",
    # マスクと絵の下ごしらえ
    "マスクの大きさ {mask_width}x{mask_height} が元の絵 {width}x{height} と違う":
        "Mask size {mask_width}x{mask_height} does not match the source image {width}x{height}",
    "広げる量は0以上": "The amount to extend must be 0 or more",
    "ぼかしの幅は0以上": "The feather width must be 0 or more",
    "描き直す範囲が空（手動編集の範囲を引いた後に何も残っていない）":
        "The area to redraw is empty (nothing is left after removing the manually edited area)",
    "image_process は辞書で渡す": "image_process must be an object",
    "image_process.prepared はサーバーが書く。依頼に入れられない":
        "image_process.prepared is written by the server and cannot be included in a request",
    "image_process.seed は 0〜{max} の整数": "image_process.seed must be an integer from 0 to {max}",
    "形の指定の絵は1枚": "Only one image for shape guidance is allowed",
    "{label} は参照の絵を受けない": "{label} does not take reference images",
    "{label} は元の絵を受けない": "{label} does not take a source image",
    "{label} は元の絵（purpose=source）を1枚渡す": "{label} needs exactly one source image (purpose=source)",
    "{label} は手動編集の範囲のマスク（protected_mask_input）を必ず渡す":
        "{label} always needs the mask of the manually edited area (protected_mask_input)",
    "描き直す範囲のマスクは1つ": "Only one mask for the area to redraw is allowed",
    "{label} は描き直す範囲を受けない": "{label} does not take an area to redraw",
    "{label} は描き直す範囲（purpose=mask）が要る": "{label} needs an area to redraw (purpose=mask)",
    # 画像生成の処理の一覧
    "形の指定には絵（purpose=control）が要る": "Shape guidance needs an image (purpose=control)",
    "形の指定の絵があるのに、形の指定が「使わない」":
        "An image for shape guidance was given, but shape guidance is set to \"Not used\"",
    "描き足すの量は、依頼を受ける前にピクセルへ直す（resolve_outpaint）":
        "The amount to extend must be converted to pixels before the request is accepted (resolve_outpaint)",
    "広げる量がどの辺も0": "The amount to extend is 0 on every side",
    "この接続先の中身に ControlNet（controlnet_name）が無いので、形の指定を使えない":
        "This connection's settings have no ControlNet (controlnet_name), so shape guidance cannot be used",
    "画像生成の処理 {name} は無い（{known}）": "There is no image generation process {name} ({known})",
    "{label} の引数が正しくない: {reason}": "The parameters for {label} are not valid: {reason}",
    "{label} の中身（comfy_graph_settings）が決まっていない":
        "The settings (comfy_graph_settings) for {label} are not set",
    "{label} の中身（comfy_graph_settings）が正しくない: {reason}":
        "The settings (comfy_graph_settings) for {label} are not valid: {reason}",
    "この絵はコマに置かれていない。mm・コマの枠までで広げるには置き場が要る":
        "This image is not placed in a panel. Extending by mm or to the panel frame needs a placement",
    "回転・傾き・反転のある置き場では、mm・コマの枠までで広げられない（ピクセルで指定する）":
        "A rotated, skewed or flipped placement cannot be extended by mm or to the panel frame (specify it in pixels)",
    "コマの枠が決まっていない": "The panel frame is not set",
    # 依頼に入れる絵
    "crop_px は [x0, y0, x1, y1] の整数: {value}": "crop_px must be integers [x0, y0, x1, y1]: {value}",
    "crop_px {value} が元の絵（{width}x{height}）の外に出ている":
        "crop_px {value} is outside the source image ({width}x{height})",
    "絵 {id} には手動編集の範囲がある。切り出して元の絵にはしない":
        "Image {id} has a manually edited area, so it cannot be cropped and used as the source image",
    "{what} には node と input（文字）が要る: {entry}": "{what} needs node and input (strings): {entry}",
    "region_px は多角形（[x, y] の一覧）の一覧: {reason}":
        "region_px must be a list of polygons (lists of [x, y]): {reason}",
    "region_px の多角形は1つ以上、どれも3点以上": "region_px needs at least one polygon, each with at least 3 points",
    "png_base64 が base64 でない: {reason}": "png_base64 is not valid base64: {reason}",
    "prepared_inputs はサーバーが書く。依頼に入れられない":
        "prepared_inputs is written by the server and cannot be included in a request",
    "元の絵（input_images）が無いのに protected_mask_input がある":
        "protected_mask_input was given without a source image (input_images)",
    "input_images は一覧で渡す": "input_images must be a list",
    "input_images の purpose は {purposes} のどれか: {entry}":
        "purpose in input_images must be one of {purposes}: {entry}",
    "マスクは image_id か region_px のどちらか": "A mask takes either image_id or region_px, not both",
    "マスク・形の指定の絵は image_id か png_base64 のどちらか":
        "A mask or an image for shape guidance takes either image_id or png_base64, not both",
    "囲んだ範囲（region_px）のマスクは、元の絵（purpose=source）が1枚のときだけ描ける":
        "A mask for the selected area (region_px) can only be drawn when there is exactly one source image"
        " (purpose=source)",
    "手動編集の範囲のある元の絵が2枚以上ある。マスクを1つに決められない":
        "Two or more source images have a manually edited area, so a single mask cannot be chosen",
    "元の絵 {id} に手動編集の範囲がある。protected_mask_input を手順に用意して渡す":
        "Source image {id} has a manually edited area. Add protected_mask_input to the workflow and pass it",
    "protected_mask_input は元の絵（purpose=source）と一緒に渡す":
        "protected_mask_input must be passed together with a source image (purpose=source)",
    # 依頼を受ける・取り消す・続ける
    "{user} に {object} の {relation} が無い": "{user} does not have {relation} on {object}",
    "{process} の送り先が決まっていない": "No destination is set for {process}",
    "{process} が何の作業の処理か（ai_task・ai_action）が決まっていない":
        "The task that {process} belongs to (ai_task, ai_action) is not set",
    "{service} は {process} を受けられない（先に処理の中身を登録する）":
        "{service} cannot take {process} (register the process settings first)",
    "{service} はこの作品の送ってよい先に無い": "{service} is not in this work's allowed destinations",
    "{seconds} 秒待ってもキューに入らなかった（制御の作業者が動いていない）":
        "Not queued after waiting {seconds} seconds (the control worker is not running)",
    "jobs:{id} {detail}": "jobs:{id} {detail}",
    "jobs:{id} は流れていない": "jobs:{id} is not running",
    "予算の上限で待っているものだけ続けられる": "Only requests waiting on the budget limit can be resumed",
    "{process} は ai_task={task}・ai_action={action} の処理（今は {current_task}・{current_action}）":
        "{process} is a process for ai_task={task}, ai_action={action} (currently {current_task}, {current_action})",
    # 接続先の様子を読む（接続を試す・実行状況・入っているモデル）
    "LITELLM_MASTER_KEY が設定されていない": "LITELLM_MASTER_KEY is not set",
    "{service} の URL（endpoint）が無い": "{service} has no URL (endpoint)",
    "{path} に接続できない: {error}: {reason}": "Cannot connect to {path}: {error}: {reason}",
    "{path} が {status} を返した（鍵が通らない）": "{path} returned {status} (the API key was rejected)",
    "{path} が {status} を返した: {body}": "{path} returned {status}: {body}",
    "{path} の答えが JSON でない": "The response from {path} is not JSON",
    "/system_stats の形が ComfyUI と違う": "The /system_stats response does not look like ComfyUI",
    "/v1/models の形が OpenAI 互換と違う": "The /v1/models response is not OpenAI-compatible",
    "/queue の形が ComfyUI と違う": "The /queue response does not look like ComfyUI",
    "/object_info の形が ComfyUI と違う": "The /object_info response does not look like ComfyUI",
}
