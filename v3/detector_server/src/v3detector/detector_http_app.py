"""検出器の HTTP の口（CPU）。画像のファイルを受け取り、枠と値を JSON で返す。

起動（ポートは既定を持たない。引数で渡す）:
    cd v3/detector_server
    uv run python -m v3detector.detector_http_app --port <ポート> [--host <ホスト>]
    （ホストの既定は 127.0.0.1）
モデルの重みは初回の呼び出しで Hugging Face から落ちる。以降はキャッシュを使う。

閾値・画素数・余白などの数値は呼ぶ側がフォームの項目で渡す。コードには既定の値を置かない。
省略できる閾値を省いた場合は imgutils の関数の既定に任せる（応答の説明にその旨を載せる）。

口の一覧（すべて multipart/form-data。画像は項目 image。結果は JSON）:
  GET  /health                      生きているか。{"status": "ok"}
  POST /person_face_head            入力: image, edge_px(必須), score_threshold(省略可)
                                    出力: width, height, persons[], faces[], heads[]
                                    各枠: x0,y0,x1,y1,score,h_ratio,area_ratio,touch(T/B/L/R の連結)
  POST /text_regions                入力: image, score_threshold(省略可)
                                    出力: width, height, texts[{x0,y0,x1,y1,score}]
  POST /identity_ccip               入力: image_a, image_b, threshold(省略可)
                                    出力: difference, threshold, same, note ほか。
                                    「違う」で落とす専用。same=true は同一人物の証拠にならない
                                    （似た別人を94〜95%「同じ」とした）
  POST /age_rating                  入力: image
                                    出力: rating{区分: 確率}
  POST /hands                       入力: image, score_threshold(省略可), crop_margin_ratio(省略可)
                                    出力: width, height, hands[{x0,y0,x1,y1,score,
                                    crop_png_base64(crop_margin_ratio を渡したときだけ)}]
画像が読めないときは 422、必須項目が無いときは 422 を返す。
"""
import argparse
import io
import os

# CPU で動かす（試作と同じ。GPU の提供元を探しに行かせない）
os.environ.setdefault("ONNXRUNTIME_PROVIDERS", "CPUExecutionProvider")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from PIL import Image, UnidentifiedImageError  # noqa: E402

from v3detector.age_rating_score import age_rating_scores  # noqa: E402
from v3detector.character_identity_ccip import NOTE as CCIP_NOTE  # noqa: E402
from v3detector.character_identity_ccip import ccip_compare  # noqa: E402
from v3detector.hand_detection import detect_hands_with_crops  # noqa: E402
from v3detector.person_face_detection import detect_person_face_head  # noqa: E402
from v3detector.text_region_detection import detect_text_regions  # noqa: E402


def _read_image(upload: UploadFile) -> Image.Image:
    try:
        im = Image.open(io.BytesIO(upload.file.read()))
        im.load()
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(status_code=422, detail=f"画像として読めません: {e}")
    return im.convert("RGB")


def create_app() -> FastAPI:
    app = FastAPI(title="V3 検出器", description="人物・顔・頭、文字、手、年齢区分、同一キャラ判定（CCIP）。"
                  "閾値は呼ぶ側が渡す。省略した閾値は imgutils の既定に任せる。")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/person_face_head", summary="人物・顔・頭の枠と端への接触")
    def person_face_head(image: UploadFile = File(...), edge_px: int = Form(...),
                         score_threshold: float | None = Form(None)) -> dict:
        return detect_person_face_head(_read_image(image), edge_px, score_threshold)

    @app.post("/text_regions", summary="絵の中の文字の枠")
    def text_regions(image: UploadFile = File(...),
                     score_threshold: float | None = Form(None)) -> dict:
        return detect_text_regions(_read_image(image), score_threshold)

    @app.post("/identity_ccip", summary="同一キャラ判定（違うで落とす専用）",
              description=CCIP_NOTE)
    def identity_ccip(image_a: UploadFile = File(...), image_b: UploadFile = File(...),
                      threshold: float | None = Form(None)) -> dict:
        return ccip_compare(_read_image(image_a), _read_image(image_b), threshold)

    @app.post("/age_rating", summary="年齢区分の確率")
    def age_rating(image: UploadFile = File(...)) -> dict:
        return age_rating_scores(_read_image(image))

    @app.post("/hands", summary="手の枠と切り抜き")
    def hands(image: UploadFile = File(...), score_threshold: float | None = Form(None),
              crop_margin_ratio: float | None = Form(None)) -> dict:
        return detect_hands_with_crops(_read_image(image), score_threshold, crop_margin_ratio)

    return app


def main() -> None:
    import uvicorn
    ap = argparse.ArgumentParser(description="V3 検出器の起動")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    uvicorn.run(create_app(), host=a.host, port=a.port)


if __name__ == "__main__":
    main()
