"""英語の訳：画像生成の画面の入力欄に出す名前（処理の説明・欄・選択肢・まとまり）と、接続先の様子の補足の文。

処理の名前（文から作る など）は queue.py にある。
"""

MESSAGES = {
    # 処理の説明（generation_queue/image_process_registry.py の SPECS）
    "指示の文から新しく描く": "Draw a new image from the prompt",
    "今の絵を元に、指示と変える強さで描き直す":
        "Redraw from the current image using the prompt and the denoising strength",
    "今の絵に近いまま、シードを変えて別の案を出す":
        "Make another version close to the current image with a different seed",
    "囲んだ所だけ描き直す。手動編集の範囲は囲めない":
        "Redraw only the selected area. Manually edited areas cannot be selected",
    "絵の外側を広げて描く": "Extend the image outward and draw the added area",
    "文の指示で直す。囲めば囲んだ所だけ変える":
        "Edit with a text prompt. If you select an area, only that area changes",
    # まとまりの名前（「基本」は画面が突き合わせる名前で、画面に出ないので訳さない）
    "細かい設定": "Advanced settings",
    "形の指定": "Shape guidance",
    "範囲": "Regions",
    "囲んだ所だけ": "Selected area only",
    "広げる": "Extension",
    "直した後": "After editing",
    "囲んだ範囲": "Selection",
    # 欄の名前
    "ステップ数": "Steps",
    "文の効き（CFG）": "CFG scale",
    "このコマの指示": "Prompt for this panel",
    "入れないもの": "Negative prompt",
    "少し": "Slight",
    "大きく": "Strong",
    "形の効き": "Guidance strength",
    "効かせる所（終わり）": "Guidance end",
    "白地に黒い線（反転して渡す）": "Black lines on white (sent inverted)",
    "範囲ごとの文": "Regional prompts",
    "幅": "Width",
    "高さ": "Height",
    "変える強さ": "Denoising strength",
    "範囲を広げる": "Expand selection",
    "境目のぼかし": "Edge feathering",
    "描き方": "Masked content",
    "囲んだ所だけ大きくして直す": "Enlarge only the selected area to fix it",
    "周りの余白": "Padding around the selection",
    "広げ方": "Extend by",
    # 辺の名前は、文の中に入れて使う所（layout_export.py の「左」「右」）と同じ文なので、訳も同じ小文字にする
    "左": "left",
    "上": "top",
    "右": "right",
    "下": "bottom",
    "広げた所の下塗り": "Fill for the extended area",
    "直す指示": "Edit prompt",
    "色を元の絵に合わせる": "Match colors to the original image",
    "合わせる強さ": "Color match strength",
    # 選択肢の名前
    "使わない": "Not used",
    "線画": "Line art",
    "落書き": "Scribble",
    "骨格": "Skeleton",
    "奥行き": "Depth",
    "元の絵から描く": "Start from the original image",
    "範囲を消してから描く": "Erase the area, then draw",
    "ピクセルで": "In pixels",
    "mm で": "In mm",
    "コマの枠まで": "To the panel frame",
    "周りの色を流し込む": "Diffuse surrounding colors",
    "端を伸ばす": "Stretch the edges",
    "折り返す": "Mirror",
    "灰色": "Gray",
    "合わせない": "Do not match",
    "平均と広がり（Lab）": "Mean and spread (Lab)",
    "色の分布（Lab・MKL）": "Color distribution (Lab, MKL)",
    "ヒストグラム": "Histogram",
    # 接続先の様子の補足（service_senders/service_inspection.py。成功の返事の note に入る）
    "{adapter} にはキューを読む API が無い": "{adapter} has no API for reading its queue",
    "検出器のモデルは検出器の側で決まる（読む API が無い）":
        "The detector's models are set on the detector side (there is no API to read them)",
}
