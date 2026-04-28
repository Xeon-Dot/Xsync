"""Shared utility functions for Xsync."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional


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


def disk_usage_for_path(path: str) -> Optional[tuple[float, Path]]:
    """Return ``(used_percent, filesystem_path)`` for the filesystem at *path*.

    Returns ``None`` if the path does not exist or usage cannot be determined.
    """
    target = Path(path)
    usage_path = target if target.exists() else target.parent
    if not usage_path.exists():
        return None
    try:
        usage = shutil.disk_usage(usage_path)
    except OSError:
        return None
    if usage.total == 0:
        return None
    return usage.used / usage.total * 100, usage_path


def make_progress_callback(
    telegram_cfg,
    discord_cfg,
    name: str,
) -> Callable[[int], None]:
    """Return a progress callback that sends notifications at each 10 % milestone.

    The returned callable accepts a ``pct`` integer (0–100) and fires
    Telegram / Discord progress notifications when a new 10 % milestone is
    reached.
    """
    from xsync.discord import notify_sync_progress as _discord_progress
    from xsync.telegram import notify_sync_progress as _telegram_progress

    last_milestone: int = -1

    def _cb(pct: int) -> None:
        nonlocal last_milestone
        if pct > last_milestone:
            last_milestone = pct
            _telegram_progress(telegram_cfg, name, pct)
            _discord_progress(discord_cfg, name, pct)

    return _cb
