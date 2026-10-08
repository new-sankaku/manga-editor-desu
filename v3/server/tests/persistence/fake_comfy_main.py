"""偽の ComfyUI（tests/integration/harness_fakes.py の FakeComfyServer）を、決めた口で1つのプロセスとして動かす。
保存と再起動の確かめ（v3/web/test/persistence_e2e.mjs）が使う。本物の ComfyUI の振る舞いを確かめる物ではない。

  uv run python tests/persistence/fake_comfy_main.py --port 8963 --steps 20 --step-seconds 0.3

作業者を止めて起こしても、このプロセスは動かしたままにする（ComfyUI は作業者とは別の機械にあるのと同じ形）。
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "integration"))

from harness_fakes import FakeComfyServer  # noqa: E402


async def main(port: int, steps: int, step_seconds: float) -> None:
    comfy = FakeComfyServer(steps=steps, step_seconds=step_seconds)
    comfy.port, comfy.url = port, f"http://127.0.0.1:{port}"
    await comfy.start()
    print("COMFY READY", comfy.url, flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--steps", type=int, default=20)
    p.add_argument("--step-seconds", type=float, default=0.3)
    a = p.parse_args()
    asyncio.run(main(a.port, a.steps, a.step_seconds))
