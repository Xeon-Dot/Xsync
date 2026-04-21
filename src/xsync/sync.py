"""Mirror synchronization engine for Xsync."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from xsync.models import Mirror, MirrorType, SyncStatus

logger = logging.getLogger(__name__)

# Matches rsync --info=progress2 lines: "to-chk=<remaining>/<total>"
_RSYNC_TOCHK_RE = re.compile(r"to-chk=(\d+)/(\d+)")


class SyncResult:
    """Result of a single mirror sync run."""

    def __init__(
        self,
        mirror_name: str,
        status: SyncStatus,
        duration_seconds: float = 0.0,
        log_path: Optional[Path] = None,
        error: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ) -> None:
        self.mirror_name = mirror_name
        self.status = status
        self.duration_seconds = duration_seconds
        self.log_path = log_path
        self.error = error
        self.size_bytes = size_bytes

    def __repr__(self) -> str:
        return (
            f"SyncResult(mirror={self.mirror_name!r}, status={self.status.value!r}, "
            f"duration={self.duration_seconds:.1f}s)"
        )


def sync_mirror(
    mirror: Mirror,
    log_dir: Path,
    dry_run: bool = False,
    verbose: bool = False,
    on_progress: Optional[Callable[[int], None]] = None,
) -> SyncResult:
    """Run a sync for the given mirror and return a :class:`SyncResult`.

    Args:
        mirror: The mirror configuration to sync.
        log_dir: Directory where log files are written.
        dry_run: If *True*, build the command but do not execute it.
        verbose: If *True*, print subprocess output to console.
        on_progress: Optional callback invoked with an integer 0–100 each time
            a new 10 % progress milestone is reached (rsync only).  The callback
            is called with ``0`` immediately before the process starts and with
            ``100`` when the file-transfer loop completes.

    Returns:
        A :class:`SyncResult` describing the outcome.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = log_dir / f"{mirror.name}-{timestamp}.log"

    try:
        cmd = _build_command(mirror)
    except FileNotFoundError as exc:
        return SyncResult(
            mirror_name=mirror.name,
            status=SyncStatus.FAILED,
            log_path=log_path,
            error=str(exc),
        )

    if dry_run:
        return SyncResult(
            mirror_name=mirror.name,
            status=SyncStatus.PENDING,
            log_path=log_path,
            error=None,
        )

    Path(mirror.local_path).mkdir(parents=True, exist_ok=True)

    # Inject --info=progress2 for rsync when a progress callback is supplied so
    # that we can parse "to-chk=X/Y" lines from the output stream.
    track_progress = on_progress is not None and mirror.mirror_type == MirrorType.RSYNC
    if track_progress:
        cmd = _inject_rsync_progress_flag(cmd)

    start = datetime.now(tz=timezone.utc)
    error_msg: Optional[str] = None

    try:
        with log_path.open("w", encoding="utf-8") as log_fh:
            log_fh.write(f"# Xsync log — {mirror.name}\n")
            log_fh.write(f"# Started: {start.isoformat()}\n")
            log_fh.write(f"# Command: {' '.join(cmd)}\n\n")

            if track_progress:
                returncode = _run_with_progress(cmd, log_fh, on_progress, verbose)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
            else:
                returncode = _run_without_progress(cmd, log_fh, verbose)

        end = datetime.now(tz=timezone.utc)
        duration = (end - start).total_seconds()

        if returncode == 0:
            status = SyncStatus.SUCCESS
        else:
            status = SyncStatus.FAILED
            error_msg = f"Process exited with code {returncode}"
    except FileNotFoundError as exc:
        end = datetime.now(tz=timezone.utc)
        duration = (end - start).total_seconds()
        status = SyncStatus.FAILED
        error_msg = f"Command not found: {exc}"
        with log_path.open("a", encoding="utf-8") as log_fh:
            log_fh.write(f"\n# ERROR: {error_msg}\n")
    except Exception as exc:  # noqa: BLE001
        end = datetime.now(tz=timezone.utc)
        duration = (end - start).total_seconds()
        status = SyncStatus.FAILED
        error_msg = str(exc)
        with log_path.open("a", encoding="utf-8") as log_fh:
            log_fh.write(f"\n# ERROR: {error_msg}\n")

    with log_path.open("a", encoding="utf-8") as log_fh:
        log_fh.write(
            f"\n# Finished: {end.isoformat()}  Duration: {duration:.1f}s  Status: {status.value}\n"  # noqa: E501
        )

    size_bytes = None
    if status == SyncStatus.SUCCESS:
        size_bytes = get_directory_size(mirror.local_path)

    return SyncResult(
        mirror_name=mirror.name,
        status=status,
        duration_seconds=duration,
        log_path=log_path,
        error=error_msg,
        size_bytes=size_bytes,
    )


def _inject_rsync_progress_flag(cmd: list[str]) -> list[str]:
    """Return a copy of *cmd* with ``--info=progress2`` inserted after ``rsync``."""
    if "--info=progress2" in cmd or "--progress" in cmd:
        return cmd
    return [cmd[0], "--info=progress2"] + cmd[1:]


def _run_without_progress(
    cmd: list[str],
    log_fh,
    verbose: bool,
) -> int:
    """Run *cmd* as a subprocess, writing output to *log_fh* and optionally to console.

    Returns the process exit code.
    """
    if verbose:
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        ) as proc:
            for line in proc.stdout:  # type: ignore[union-attr]  # ty:ignore[not-iterable]
                log_fh.write(line)
                print(line, end="")
        return proc.returncode
    else:
        proc = subprocess.run(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        return proc.returncode


def _run_with_progress(
    cmd: list[str],
    log_fh,
    on_progress: Callable[[int], None],
    verbose: bool = False,
) -> int:
    """Run *cmd* as a subprocess, streaming stdout line-by-line.

    Parses rsync ``to-chk=X/Y`` progress markers, fires *on_progress* at each
    new 10 % milestone, and writes all output to *log_fh*.  Returns the process
    exit code.
    """
    last_milestone = -1

    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as proc:
        for line in proc.stdout:  # type: ignore[union-attr]  # ty:ignore[not-iterable]
            log_fh.write(line)
            if verbose:
                print(line, end="")

            match = _RSYNC_TOCHK_RE.search(line)
            if match:
                remaining = int(match.group(1))
                total = int(match.group(2))
                if total > 0:
                    pct = int((total - remaining) / total * 100)
                    milestone = (pct // 10) * 10
                    if milestone > last_milestone:
                        last_milestone = milestone
                        on_progress(milestone)

    return proc.returncode


def _build_command(mirror: Mirror) -> list[str]:
    """Build the shell command list for syncing a mirror."""
    if mirror.mirror_type == MirrorType.RSYNC:
        return _build_rsync_command(mirror)
    if mirror.mirror_type in (MirrorType.HTTP, MirrorType.FTP):
        return _build_wget_command(mirror)
    raise ValueError(f"Unsupported mirror type: {mirror.mirror_type}")


def _build_rsync_command(mirror: Mirror) -> list[str]:
    """Build an rsync command."""
    if not shutil.which("rsync"):
        raise FileNotFoundError("rsync is not installed or not on PATH")
    cmd = ["rsync"] + list(mirror.rsync_options)
    if mirror.bandwidth_limit:
        cmd += [f"--bwlimit={mirror.bandwidth_limit}"]
    cmd += [mirror.url.rstrip("/") + "/", mirror.local_path.rstrip("/") + "/"]
    return cmd


def _build_wget_command(mirror: Mirror) -> list[str]:
    """Build a wget mirror command for HTTP/FTP mirrors."""
    if not shutil.which("wget"):
        raise FileNotFoundError("wget is not installed or not on PATH")
    cmd = [
        "wget",
        "--mirror",
        "--no-host-directories",
        "--directory-prefix",
        mirror.local_path,
    ] + list(mirror.http_options)
    cmd.append(mirror.url)
    return cmd


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


def purge_old_logs(log_dir: Path, mirror_name: str, max_files: int) -> int:
    """Remove old log files, keeping at most *max_files* for a mirror.

    Returns the number of files removed.
    """
    logs = sorted(log_dir.glob(f"{mirror_name}-*.log"))
    to_remove = logs[: max(0, len(logs) - max_files)]
    for f in to_remove:
        f.unlink()
    return len(to_remove)
