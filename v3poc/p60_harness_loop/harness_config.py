"""P60 の設定。口・置き場・コマの中身・上限の初めの値。
置き場は環境の変数で変えられる。既定値はこの試作を流したときのコンテナの作業用フォルダ。"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
OUT = HERE / "out"

SCRATCH = Path(os.environ.get(
    "P60_SCRATCH",
    "/tmp/claude-0/-home-user-manga-editor-desu/7c13d5bd-5dec-59f7-a309-dc94f311bcf2/scratchpad/p60"))
# ComfyUI の本体と venv（p56 で入れた物を借りる。モデルは SD1.5 を分けた3つ）
COMFY_DIR = Path(os.environ.get(
    "COMFY_DIR",
    "/tmp/claude-0/-home-user-manga-editor-desu/fa704f96-c74d-4d28-a8d6-2b724e85a763/scratchpad/comfy"))
# Claude の CLI を呼ぶ空のフォルダ（CLAUDE.md を読ませない）
LLM_EMPTY_DIR = Path(os.environ.get("P60_LLM_DIR", str(SCRATCH.parent / "empty_llm")))

COMFY_PORT = int(os.environ.get("P60_COMFY_PORT", "63260"))
DETECTOR_PORT = int(os.environ.get("P60_DETECTOR_PORT", "63261"))
API_PORT = int(os.environ.get("P60_API_PORT", "63262"))
TEMPORAL_PORT = int(os.environ.get("P60_TEMPORAL_PORT", "64260"))
TEMPORAL_UI_PORT = TEMPORAL_PORT + 1
TEMPORAL_CONTAINER = "p60-temporal"

COMFY_URL = f"http://127.0.0.1:{COMFY_PORT}"
DETECTOR_URL = f"http://127.0.0.1:{DETECTOR_PORT}"
TEMPORAL_ADDR = f"localhost:{TEMPORAL_PORT}"
TASK_QUEUE = "p60-harness"

# 絵の置き場（版の登録の代わり）。登録の記録は 1 行ずつ追記する
STORE = SCRATCH / "store"
REGISTRY_LOG = SCRATCH / "registrations.jsonl"
COMFY_OUT = SCRATCH / "comfy_out"
COMFY_IN = SCRATCH / "comfy_in"

# 画像生成の中身。小さくして CPU で1枚の時間を抑える
DIFFUSION = {
    "model": {"kind": "separate", "unet_name": "sd15_unet_fp16.safetensors", "weight_dtype": "default",
              "clip_name": "sd15_te_fp16.safetensors", "clip_type": "stable_diffusion",
              "vae_name": "sd15_vae_fp16.safetensors"},
    "loras": [],
    "sampler": {"steps": int(os.environ.get("P60_STEPS", "8")), "cfg": 7.0,
                "sampler_name": "dpmpp_2m", "scheduler": "karras"},
    "native_long_side": 512,
    "controlnet_name": None,
}
WIDTH = int(os.environ.get("P60_W", "320"))
HEIGHT = int(os.environ.get("P60_H", "320"))

# 画風とキャラの見た目の固定部分（設計 8.1 の 1：プログラムが設定資料から組む）
STYLE_FIXED = "anime style, manga illustration, clean lineart, simple background"
CHARACTER_FIXED = "girl with short black hair, white shirt, dark skirt"
NEGATIVE_FIXED = "text, speech bubble, watermark, signature, lowres, blurry"

# 1ページ3コマ。expected_persons は検査の「人数」、full_body は「見切れ」の検査を掛けるか
PANELS = [
    {"panel": 1, "shot": "引き", "expected_persons": 1, "full_body": True, "target_ja": "通りに立つ少女1人の全身。頭から足まで入る",
     "variable": "1girl, solo, standing on a street, full body"},
    {"panel": 2, "shot": "膝上", "expected_persons": 2, "full_body": False, "target_ja": "教室で向かい合って話す少女2人。膝から上",
     "variable": "2girls, two girls talking face to face in a classroom, cowboy shot"},
    {"panel": 3, "shot": "胸から上", "expected_persons": 1, "full_body": False, "target_ja": "驚いた顔の少女1人。胸から上",
     "variable": "1girl, solo, upper body, surprised face, looking at viewer"},
]

# 1回の作業の上限の初めの値（作業ごとに上書きできる。動いている間も update で変えられる）
DEFAULT_LIMITS = {
    "max_attempts": 4,          # 作り直しの回数を含めた生成の回の上限
    "candidates_per_attempt": 2,  # 1回の生成で作る候補の数（内側の繰り返し）
    "budget_usd": 1.00,         # 評価役（Claude）の費用の上限。手元の ComfyUI は 0 と数える（決めごと 4.6）
    "budget_seconds": 1800,     # 作業の経過時間の上限
    "resend_limit": 2,          # 通信の失敗の送り直し（作り直しとは別に数える、決めごと 4.5）
    "eval_repeats": 2,          # 評価役に同じ絵を聞く回数（ぶれを測る）
    "eval_min_score": 3,        # この点以上で評価役の合格
    "same_failure_reset": 2,    # 同じ失敗がこの回数続いたら文脈を捨てて出直す（設計 10 章の 6）
    "error_stop": 3,            # エラーがこの回数続いたら止める
}

EDGE_PX = 4  # 見切れの判定で端に触れたとみなす幅

# 試作の Python（v3/server の venv のパッケージを読むだけで借り、websockets だけ足した venv）
POC_PY = Path(os.environ.get("P60_PY", str(SCRATCH / "venv_api/bin/python")))
