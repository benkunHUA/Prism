"""把前端构建产物挂到根路径，供单端口部署使用。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_spa(app: FastAPI, directory: str) -> None:
    """挂载 dist/：/assets 走静态文件，其余未命中路径回落 index.html（前端路由）。"""
    root = Path(directory).resolve()
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        target = _within(root, full_path) if full_path else None
        return FileResponse(target if target else root / "index.html")


def _within(root: Path, relative: str) -> Path | None:
    """只在 root 内取文件，挡掉 ../ 穿越。"""
    candidate = (root / relative).resolve()
    if candidate.is_file() and root in candidate.parents:
        return candidate
    return None
