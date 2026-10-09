"""英語の訳：書き出し（print_export）・生成サービスへの送信（service_senders）・依頼のキュー（generation_queue）が出す文のうち、
記録に残してから画面に出す物（書き出しの失敗の理由、依頼の失敗の理由、呼び出しの記録）。"""

MESSAGES = {
    # 書き出しを断る理由（print_export/export_runner.py・book_layout.py。ExportRun.detail と工程のステップの理由に入る）
    "ページ {id} が無いか、削除されている": "Page {id} does not exist or has been deleted",
    "紙 {paper}px がページ {page}px より小さい": "The paper {paper} px is smaller than the page {page} px",
    "ページ {id} の色の種類が決まっていない（ページの color_mode か、作品の preferences.print）":
        "The color mode of page {id} is not set (the page's color_mode or the work's preferences.print)",
    "ページ {id} の解像度が決まっていない（ページの dpi か、作品の preferences.print）":
        "The resolution of page {id} is not set (the page's dpi or the work's preferences.print)",
    "ページ {id} のノンブルの出し方が決まっていない（ページの種類 page_kind か nombre_display）":
        "The page number style of page {id} is not set (the page type page_kind or nombre_display)",
    "1ページ目を左に置くか（作品の first_page_is_left）が決まっていないので、ノンブルの左右を決められない":
        "Whether page 1 goes on the left (the work's first_page_is_left) is not set, "
        "so the side of the page numbers cannot be decided",
    "見開き {id} の片方のページだけを書き出そうとした（見開きは2ページとも渡す）":
        "Only one page of spread {id} was given for export (pass both pages of a spread)",
    "見開きのページがあるのに、見開きの出し方（spread_output：split・joined・both）が決まっていない":
        "There are spread pages, but how to output spreads (spread_output: split, joined, both) is not set",
    "PDF は見開きを split（ノドで2ページ）でしか出せない（PDF のページの大きさを揃えるため）":
        "PDF can only output spreads as split (two pages divided at the gutter), to keep the PDF page sizes the same",
    "PSD は見開きを joined（1枚）でしか出せない（レイヤーをノドで切らずに渡すため）":
        "PSD can only output spreads as joined (one sheet), so that layers are not cut at the gutter",
    "V3_EXPORT_DIR が無い。書き出したファイルを置く所が無い":
        "V3_EXPORT_DIR is not set. There is nowhere to put the exported files",
    "作品 {id} が無い": "Work {id} does not exist",
    "作品の入稿の設定（preferences.print：略号・色の種類・解像度・安全線）が無い":
        "The work has no submission settings (preferences.print: code, color mode, resolution, safe area)",
    "紙 {paper}mm が塗り足し込みのページ {width:.1f}x{height:.1f}mm より小さい":
        "The paper {paper} mm is smaller than the page with bleed {width:.1f}x{height:.1f} mm",
    "ページ {id} のノンブルの出し方・番号・左右が決まっていない":
        "The page number style, number, or side of page {id} is not set",
    "PSD は見開きを1枚で書く（分けた見開きはレイヤーを持たない）":
        "PSD writes a spread as one sheet (a split spread has no layers)",
    "V3_PSD_WRITER_SCRIPT が無い。PSD を書けない": "V3_PSD_WRITER_SCRIPT is not set. PSD files cannot be written",
    "知らない書き出しの形: {format}": "Unknown export format: {format}",
    "見開き {id} の2ページの色の種類が違う（{left}・{right}）":
        "The two pages of spread {id} have different color modes ({left}, {right})",
    "見開き {id} の2ページの解像度が違う（{left}・{right}）":
        "The two pages of spread {id} have different resolutions ({left}, {right})",
    "ページ {id} が見開きの左右のどちらか決まっていない":
        "Whether page {id} is the left or right page of the spread is not set",
    "書き出しを {attempts} 回やり直しても終わらなかった（{cause}）":
        "The export did not finish after {attempts} attempts ({cause})",
    # ページを描く・色の種類にする・CMYK にする（page_render.py・color_mode_output.py・cmyk_conversion.py）
    "見開き {id} の絵の置き場が決まっていない": "The image placement of spread {id} is not set",
    "見開きの高さ {spread_height} がページの高さ {page_height} と違う":
        "The spread height {spread_height} does not match the page height {page_height}",
    "レイヤー {marker} の役 {name} を、2階調で閾値にするか網点にするか決めていない":
        "It is not decided whether layer {marker} with role {name} becomes bilevel by threshold or by dots",
    "2階調のページがあるのに、2階調にするルール（作品の preferences.print.bilevel）が無い":
        "There are bilevel pages, but the work has no bilevel conversion rule (preferences.print.bilevel)",
    "知らない色の種類: {color_mode}": "Unknown color mode: {color_mode}",
    "CMYK にするのは RGB の絵だけ（{mode}）": "Only RGB images can be converted to CMYK ({mode})",
    # PDF・PSD のファイルを書く（print_pdf_export.py・layered_psd_request.py）
    "2値のページがあるのに、2値の符号化が決まっていない": "There are bilevel pages, but the bilevel encoding is not set",
    "2値の符号化が不明です: {codec}": "Unknown bilevel encoding: {codec}",
    "CMYK のページに ICC プロファイルが付いていない": "A CMYK page has no ICC profile attached",
    "ページが1枚もありません": "There are no pages",
    "紙 {paper}mm が塗り足し込みのページ {canvas}mm より小さい":
        "The paper {paper} mm is smaller than the page with bleed {canvas} mm",
    "{number}ページ目のピクセル数 {size} が、寸法と dpi から計算した {expected} と違います":
        "The pixel size {size} of page {number} does not match {expected}, the size calculated from the dimensions and dpi",
    "レイヤー {name} に絵が無い": "Layer {name} has no image",
    "文字のレイヤー {name} は、文字の情報と描いた画像（png_path）の両方が要る":
        "Text layer {name} needs both the text information and the rendered image (png_path)",
    "PSD の書き出しが失敗しました（終了コード {code}）: {stderr}": "Writing the PSD failed (exit code {code}): {stderr}",
    # ComfyUI への送信（service_senders/comfyui_sender.py。依頼の失敗の理由に入る）
    "ノード {node} ({class_type}): {error}": "Node {node} ({class_type}): {error}",
    "{what} が JSON でない: {error}": "{what} is not JSON: {error}",
    "{what} が辞書でない: {type}": "{what} is not a JSON object: {type}",
    "{what} が {status}。ComfyUI の API ではない": "{what} returned {status}. This is not the ComfyUI API",
    "ノード {node}: {class_type} が ComfyUI に無い": "Node {node}: {class_type} is not installed in ComfyUI",
    "ノード {node} ({class_type}) の {name}={value} は選べない":
        "{name}={value} on node {node} ({class_type}) is not an available choice",
    "history に status が無い": "history has no status",
    "history の messages が一覧でない": "messages in history is not a list",
    "ComfyUI で止められた（{node} の実行中）": "Interrupted in ComfyUI (while running {node})",
    "実行に失敗（{node_type} ノード {node_id}）: {error}": "Execution failed ({node_type}, node {node_id}): {error}",
    "history が error なのに execution_error が無い": "history reports an error but has no execution_error",
    "/queue の形が違う: {error}": "The /queue response has an unexpected shape: {error}",
    "画像の指定の形が違う: {image}": "The image reference has an unexpected shape: {image}",
    "{service} に URL が無い": "{service} has no URL",
    "画像生成の処理（image_process）に overrides は使えない（引数で渡す）":
        "overrides cannot be used with an image generation process (image_process); pass the values as parameters",
    "{service} の {process} に手順が無い": "{process} on {service} has no workflow",
    "{service} の {process} に待ちの上限（comfy_wait_seconds）が決まっていない":
        "No wait limit (comfy_wait_seconds) is set for {process} on {service}",
    "request.register.role が無い。受け取った絵の役目が決まらない":
        "request.register.role is missing, so the role of the received image cannot be decided",
    "手順にノード {node} が無い（上げる絵の入れ先）": "The workflow has no node {node} (where the uploaded image goes)",
    "/upload/image が {status}": "/upload/image returned {status}",
    "/upload/image が {status}: {body}": "/upload/image returned {status}: {body}",
    "/upload/image の返事に name が無い": "The /upload/image response has no name",
    "history の中身が辞書でない": "The history entry is not a JSON object",
    "ComfyUI の待ちにも実行中にも履歴にも無い（再起動か、外から消された）":
        "Not found in ComfyUI's pending queue, running queue, or history "
        "(ComfyUI was restarted, or the item was removed from outside)",
    "{seconds} 秒待っても終わらない（comfy_wait_seconds）": "Not finished after waiting {seconds} seconds (comfy_wait_seconds)",
    "手順にノード {node} が無い": "The workflow has no node {node}",
    "/prompt の返事に prompt_id が無い": "The /prompt response has no prompt_id",
    "history に outputs が無い": "history has no outputs",
    "画像が返っていない": "No images were returned",
    # 検出器・LiteLLM への送信（detector_sender.py・litellm_sender.py）
    "検出器に無い API: {endpoint}": "The detector has no such API: {endpoint}",
    "絵が足りない: {missing}": "Missing images: {missing}",
    "置き場に絵が無い: {error}": "The image is not in the image storage: {error}",
    "時間切れ: {detail}": "Timed out: {detail}",
    "{service} の {process} にモデルが決まっていない": "No model is set for {process} on {service}",
    # 依頼を送る活動（generation_queue/service_call_activity.py。呼び出しの記録と依頼の失敗の理由に入る）
    "送った後、答えを残す前にワーカーが止まった。送り先で処理されたか・費用がかかったかは分からない":
        "The worker stopped after sending, before the response was saved. "
        "It is unknown whether the destination processed the request or charged for it",
    "{service} は {process} を受けられない": "{service} cannot take {process}",
    "{service} の月の予算の上限に達した": "{service} has reached its monthly budget limit",
    "送っている間に取り消した。送り先で費用がかかったかは提供元による（未確認）":
        "Cancelled while sending. Whether the destination charged for it depends on the provider (not verified)",
    "絵の登録を断られた: {reason}": "Registering the image was refused: {reason}",
    "答えを正本に入れるのを断られた: {reason}": "Saving the result to the work's data was refused: {reason}",
}
