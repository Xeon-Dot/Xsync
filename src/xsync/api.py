"""FastAPI server for Xsync."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from xsync.config import get_config_dir, load_config
from xsync.models import SyncStatus

_api_state: dict = {
    "config_dir": None,
    "sync_status": {},
    "current_mirror": None,
}


def format_size(size_bytes: int) -> str:
    """Convert bytes to human readable size string."""
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    size = float(size_bytes)
    for unit in units:
        if abs(size) < 1024.0:
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024.0
    return f"{size:.2f} EiB"


def get_directory_size(path: str) -> int:
    """Calculate total size of a directory in bytes."""
    total = 0
    try:
        p = Path(path)
        if p.exists():
            for entry in p.rglob("*"):
                if entry.is_file():
                    total += entry.stat().st_size
    except (OSError, PermissionError):
        pass
    return total


class MirrorStatusResponse(BaseModel):
    name: str
    enabled: bool
    status: str
    last_sync: Optional[str] = None
    last_size: Optional[int] = None
    size_bytes: int = 0
    size_human: str = "0 B"


class StatusResponse(BaseModel):
    daemon_running: bool = False
    mirrors: list[MirrorStatusResponse] = []


app = FastAPI(
    title="Xsync API",
    description="API for monitoring Xsync mirror synchronization",
    version="0.1.0",
)


@app.get("/api/status")
async def get_status() -> StatusResponse:
    """Get the status of all mirrors."""
    config_dir = _api_state.get("config_dir")
    cfg = load_config(config_dir)
    cfg_dir = get_config_dir(config_dir)

    mirrors_status: list[MirrorStatusResponse] = []
    for name, mirror in cfg.mirrors.items():
        size_bytes = mirror.last_size if mirror.last_size is not None else 0
        mirrors_status.append(
            MirrorStatusResponse(
                name=name,
                enabled=mirror.enabled,
                status=mirror.last_status.value,
                last_sync=mirror.last_sync.isoformat() if mirror.last_sync else None,
                last_size=mirror.last_size,
                size_bytes=size_bytes,
                size_human=format_size(size_bytes),
            )
        )

    from xsync.daemon import get_pid_file, is_running

    pid_file = get_pid_file(cfg_dir)
    daemon_running = is_running(pid_file)

    return StatusResponse(
        daemon_running=daemon_running,
        mirrors=mirrors_status,
    )


@app.get("/api/mirrors")
async def list_mirrors() -> list[str]:
    """List all mirror names."""
    config_dir = _api_state.get("config_dir")
    cfg = load_config(config_dir)
    return list(cfg.mirrors.keys())


@app.get("/api/mirrors/{name}")
async def get_mirror_status(name: str):
    """Get status of a specific mirror."""
    config_dir = _api_state.get("config_dir")
    cfg = load_config(config_dir)

    if name not in cfg.mirrors:
        return JSONResponse(
            status_code=404, content={"error": f"Mirror '{name}' not found"}
        )

    mirror = cfg.mirrors[name]
    size_bytes = mirror.last_size if mirror.last_size is not None else 0

    return MirrorStatusResponse(
        name=name,
        enabled=mirror.enabled,
        status=mirror.last_status.value,
        last_sync=mirror.last_sync.isoformat() if mirror.last_sync else None,
        last_size=mirror.last_size,
        size_bytes=size_bytes,
        size_human=format_size(size_bytes),
    )


@app.get("/api/mirrors/{name}/size")
async def get_mirror_size(name: str):
    """Get the size of a mirror's local directory."""
    config_dir = _api_state.get("config_dir")
    cfg = load_config(config_dir)

    if name not in cfg.mirrors:
        return JSONResponse(
            status_code=404, content={"error": f"Mirror '{name}' not found"}
        )

    mirror = cfg.mirrors[name]
    size_bytes = mirror.last_size if mirror.last_size is not None else 0

    return {
        "name": name,
        "local_path": mirror.local_path,
        "size_bytes": size_bytes,
        "size_human": format_size(size_bytes),
    }


def set_sync_status(mirror_name: str, status: SyncStatus) -> None:
    """Update the sync status for a mirror."""
    _api_state["sync_status"][mirror_name] = status


def get_sync_status(mirror_name: str) -> SyncStatus:
    """Get the current sync status for a mirror."""
    return _api_state["sync_status"].get(mirror_name, SyncStatus.PENDING)


def set_current_mirror(mirror_name: Optional[str]) -> None:
    """Set the currently syncing mirror."""
    _api_state["current_mirror"] = mirror_name


def get_current_mirror() -> Optional[str]:
    """Get the currently syncing mirror."""
    return _api_state.get("current_mirror")


def init_api_state(config_dir: Optional[Path] = None) -> None:
    """Initialize the API state with config directory."""
    _api_state["config_dir"] = config_dir


def run_api_server(host: str = "0.0.0.0", port: int = 58080) -> None:
    """Run the FastAPI server."""
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_api_server_thread(
    host: str = "0.0.0.0", port: int = 58080
) -> threading.Thread:
    """Start the API server in a background thread."""
    thread = threading.Thread(
        target=run_api_server,
        kwargs={"host": host, "port": port},
        daemon=True,
    )
    thread.start()
    return thread
