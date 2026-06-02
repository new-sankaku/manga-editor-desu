# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi",
#     "uvicorn[standard]",
# ]
# ///
import mimetypes
import re
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

mimetypes.add_type('application/javascript', '.js')

ROOT = Path(__file__).parent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response.headers['Service-Worker-Allowed'] = '/'
        return response


app.add_middleware(NoCacheMiddleware)

HOME = Path.home().resolve()


def resolve_within_home(rel_path: str) -> Path:
    candidate = (HOME / rel_path).resolve() if rel_path else HOME
    try:
        candidate.relative_to(HOME)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path is outside of HOME")
    return candidate


def to_relative(target: Path) -> str:
    rel = target.relative_to(HOME).as_posix()
    return "" if rel == "." else rel


@app.get("/api/folders")
def list_folders(path: str = Query(default="")):
    target = resolve_within_home(path)
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Not a directory")

    entries = []
    try:
        children = sorted(target.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    for child in children:
        if child.name.startswith('.'):
            continue
        if not child.is_dir():
            continue
        try:
            resolved = child.resolve()
            resolved.relative_to(HOME)
        except (ValueError, OSError):
            continue
        entries.append({
            "name": child.name,
            "path": to_relative(resolved),
        })

    rel_self = to_relative(target)
    parent = None if target == HOME else to_relative(target.parent)

    return {
        "home": str(HOME),
        "path": rel_self,
        "displayPath": str(target),
        "parent": parent,
        "entries": entries,
    }


@app.get("/api/files")
def list_files(path: str = Query(default=""), pattern: str = Query(default="")):
    target = resolve_within_home(path)
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Not a directory")

    compiled = None
    if pattern:
        try:
            compiled = re.compile(pattern)
        except re.error:
            raise HTTPException(status_code=400, detail="Invalid pattern")

    try:
        children = sorted(target.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    entries = []
    for child in children:
        if child.name.startswith('.'):
            continue
        if not child.is_file():
            continue
        if compiled and not compiled.search(child.name):
            continue
        try:
            resolved = child.resolve()
            resolved.relative_to(HOME)
            size = resolved.stat().st_size
        except (ValueError, OSError):
            continue
        entries.append({
            "name": child.name,
            "path": to_relative(resolved),
            "size": size,
        })

    return {
        "path": to_relative(target),
        "displayPath": str(target),
        "entries": entries,
    }


@app.get("/api/file")
def get_file(path: str = Query(...)):
    target = resolve_within_home(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not a file")
    return FileResponse(str(target))


app.mount("/", StaticFiles(directory=str(ROOT), html=True), name="static")


if __name__ == '__main__':
    PORT = 8125
    ADDRESS = "0.0.0.0"
    print(f"Server running at http://0.0.0.0:{PORT}")
    uvicorn.run(
        "server_fastapi:app",
        host=ADDRESS,
        port=PORT,
        reload=True,
        reload_dirs=[str(ROOT)],
    )
