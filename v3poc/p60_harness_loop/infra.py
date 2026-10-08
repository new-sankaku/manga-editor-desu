"""P60 が自分で立てるもの（Temporal・ComfyUI・検出器）の起動と停止。v3 の compose の Temporal は使わない。
実行: v3/server/.venv/bin/python infra.py start|stop|status|restart_temporal"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_config import (COMFY_DIR, COMFY_IN, COMFY_OUT, COMFY_PORT, COMFY_URL, DETECTOR_PORT,  # noqa: E402
                            DETECTOR_URL, POC_PY, REPO, SCRATCH, TEMPORAL_CONTAINER, TEMPORAL_PORT, TEMPORAL_UI_PORT)

PIDS = SCRATCH / "pids"


def _wait(url: str, sec: int) -> bool:
    for _ in range(sec):
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    return False


def start_temporal(fresh: bool) -> None:
    data = SCRATCH / "temporal"
    if fresh:
        subprocess.run(["docker", "rm", "-f", TEMPORAL_CONTAINER], capture_output=True)
        subprocess.run(["rm", "-rf", str(data)])
    data.mkdir(parents=True, exist_ok=True)
    os.chmod(data, 0o777)
    r = subprocess.run(["docker", "start", TEMPORAL_CONTAINER], capture_output=True)
    if r.returncode != 0:
        subprocess.run(["docker", "run", "-d", "--name", TEMPORAL_CONTAINER, "-p", f"{TEMPORAL_PORT}:7233",
                        "-p", f"{TEMPORAL_UI_PORT}:8233", "-v", f"{data}:/data", "temporalio/temporal:1.9.1",
                        "server", "start-dev", "--ip", "0.0.0.0", "--db-filename", "/data/temporal.db"],
                       check=True, capture_output=True)
    if not _wait(f"http://127.0.0.1:{TEMPORAL_UI_PORT}", 60):
        raise RuntimeError("Temporal が起きない")


def stop_temporal(remove: bool) -> None:
    subprocess.run(["docker", "stop", TEMPORAL_CONTAINER], capture_output=True)
    if remove:
        subprocess.run(["docker", "rm", "-f", TEMPORAL_CONTAINER], capture_output=True)


def _spawn(name: str, cmd: list[str], cwd: Path, env: dict | None = None) -> int:
    PIDS.mkdir(parents=True, exist_ok=True)
    log = open(SCRATCH / f"{name}.log", "ab")
    p = subprocess.Popen(cmd, cwd=str(cwd), stdout=log, stderr=log, start_new_session=True,
                         env={**os.environ, **(env or {})})
    (PIDS / name).write_text(str(p.pid))
    return p.pid


def _kill(name: str, sig: int = signal.SIGTERM) -> bool:
    f = PIDS / name
    if not f.exists():
        return False
    pid = int(f.read_text())
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass
    f.unlink()
    return True


def start_comfy() -> None:
    if _wait(COMFY_URL + "/system_stats", 1):
        return
    COMFY_OUT.mkdir(parents=True, exist_ok=True)
    COMFY_IN.mkdir(parents=True, exist_ok=True)
    if os.environ.get("P60_COMFY_MOCK") == "1":  # 【模型】口だけ ComfyUI と同じ物（mock_comfy.py）
        here = Path(__file__).resolve().parent
        _spawn("comfy", [str(POC_PY), str(here / "mock_comfy.py")], here)
        if not _wait(COMFY_URL + "/system_stats", 60):
            raise RuntimeError("ComfyUI の模型が起きない")
        return
    _spawn("comfy", [str(COMFY_DIR / "venv/bin/python"), str(COMFY_DIR / "ComfyUI/main.py"), "--cpu", "--port",
                     str(COMFY_PORT), "--listen", "127.0.0.1", "--preview-method", "latent2rgb",
                     "--output-directory", str(COMFY_OUT), "--input-directory", str(COMFY_IN)], COMFY_DIR)
    if not _wait(COMFY_URL + "/system_stats", 120):
        raise RuntimeError("ComfyUI が起きない")


def start_detector() -> None:
    if _wait(DETECTOR_URL + "/health", 1):
        return
    d = REPO / "v3/detector_server"
    _spawn("detector", [str(d / ".venv/bin/python"), "-m", "v3detector.detector_http_app", "--port", str(DETECTOR_PORT)],
           d, {"HF_HUB_OFFLINE": "1"})
    if not _wait(DETECTOR_URL + "/health", 120):
        raise RuntimeError("検出器が起きない")


def start_worker() -> int:
    here = Path(__file__).resolve().parent
    pid = _spawn("worker", [str(POC_PY), str(here / "worker.py")], here)
    for _ in range(60):
        if b"worker ready" in (SCRATCH / "worker.log").read_bytes()[-2000:]:
            return pid
        time.sleep(0.5)
    raise RuntimeError("作業者が起きない")


def kill_worker(hard: bool = True) -> bool:
    return _kill("worker", signal.SIGKILL if hard else signal.SIGTERM)


def start_api() -> None:
    here = Path(__file__).resolve().parent
    _spawn("api", [str(POC_PY), str(here / "api_server.py")], here)
    from harness_config import API_PORT
    if not _wait(f"http://127.0.0.1:{API_PORT}/api/health", 60):
        raise RuntimeError("API が起きない")


def stop_all() -> None:
    for n in ("api", "worker", "detector", "comfy"):
        _kill(n)
    stop_temporal(remove=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "start":
        start_temporal(fresh="--fresh" in sys.argv)
        start_comfy()
        start_detector()
        print("started")
    elif cmd == "stop":
        stop_all()
        print("stopped")
    elif cmd == "status":
        for n in ("api", "worker", "detector", "comfy"):
            print(n, (PIDS / n).exists())
