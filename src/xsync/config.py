"""Configuration file management for Xsync."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Optional

import tomli_w

from xsync.models import (
    DiscordConfig,
    GlobalConfig,
    Mirror,
    MirrorType,
    TelegramConfig,
    XsyncConfig,
)

_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "xsync"
_CONFIG_FILE = "config.toml"


def get_config_dir(config_dir: Optional[Path] = None) -> Path:
    """Return the configuration directory, creating it if needed."""
    path = config_dir or _DEFAULT_CONFIG_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path(config_dir: Optional[Path] = None) -> Path:
    """Return the path to the config TOML file."""
    return get_config_dir(config_dir) / _CONFIG_FILE


def load_config(config_dir: Optional[Path] = None) -> XsyncConfig:
    """Load and return the Xsync configuration from disk.

    If the config file does not exist, returns a default :class:`XsyncConfig`.
    """
    path = get_config_path(config_dir)
    if not path.exists():
        return XsyncConfig()  # pyright: ignore[reportCallIssue]
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    return _parse_raw(raw)


def save_config(cfg: XsyncConfig, config_dir: Optional[Path] = None) -> None:
    """Persist the Xsync configuration to disk."""
    path = get_config_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _serialise(cfg)
    with path.open("wb") as fh:
        tomli_w.dump(raw, fh)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _serialise(cfg: XsyncConfig) -> dict:
    """Convert an :class:`XsyncConfig` to a plain dict suitable for TOML."""
    data: dict = {
        "version": cfg.version,
        "global": {
            "default_rsync_options": cfg.global_config.default_rsync_options,
            "log_dir": cfg.global_config.log_dir,
            "max_log_files": cfg.global_config.max_log_files,
            "parallel_jobs": cfg.global_config.parallel_jobs,
            "daemon_interval": cfg.global_config.daemon_interval,
            "api_enabled": cfg.global_config.api_enabled,
            "api_port": cfg.global_config.api_port,
            "telegram": {
                "bot_token": cfg.global_config.telegram.bot_token or "",
                "chat_id": cfg.global_config.telegram.chat_id or "",
                "notify_on_success": cfg.global_config.telegram.notify_on_success,
                "notify_on_failure": cfg.global_config.telegram.notify_on_failure,
                "notify_on_start": cfg.global_config.telegram.notify_on_start,
                "notify_on_finish": cfg.global_config.telegram.notify_on_finish,
                "notify_on_progress": cfg.global_config.telegram.notify_on_progress,
            },
            "discord": {
                "webhook_url": cfg.global_config.discord.webhook_url or "",
                "notify_on_success": cfg.global_config.discord.notify_on_success,
                "notify_on_failure": cfg.global_config.discord.notify_on_failure,
                "notify_on_start": cfg.global_config.discord.notify_on_start,
                "notify_on_finish": cfg.global_config.discord.notify_on_finish,
                "notify_on_progress": cfg.global_config.discord.notify_on_progress,
            },
        },
        "mirrors": {},
    }
    for name, mirror in cfg.mirrors.items():
        entry: dict = {
            "url": mirror.url,
            "local_path": mirror.local_path,
            "mirror_type": mirror.mirror_type.value,
            "enabled": mirror.enabled,
            "description": mirror.description,
            "rsync_options": mirror.rsync_options,
            "http_options": mirror.http_options,
        }
        if mirror.bandwidth_limit is not None:
            entry["bandwidth_limit"] = mirror.bandwidth_limit
        if mirror.last_sync is not None:
            entry["last_sync"] = mirror.last_sync.isoformat()
        entry["last_status"] = mirror.last_status.value
        if mirror.last_size is not None:
            entry["last_size"] = mirror.last_size
        data["mirrors"][name] = entry
    return data


def _parse_raw(raw: dict) -> XsyncConfig:
    """Parse a raw TOML dict into an :class:`XsyncConfig`."""
    global_raw = raw.get("global", {})
    telegram_raw = global_raw.get("telegram", {})
    telegram = TelegramConfig(
        bot_token=telegram_raw.get("bot_token") or None,
        chat_id=telegram_raw.get("chat_id") or None,
        notify_on_success=telegram_raw.get("notify_on_success", True),
        notify_on_failure=telegram_raw.get("notify_on_failure", True),
        notify_on_start=telegram_raw.get("notify_on_start", False),
        notify_on_finish=telegram_raw.get("notify_on_finish", False),
        notify_on_progress=telegram_raw.get("notify_on_progress", False),
    )
    discord_raw = global_raw.get("discord", {})
    discord = DiscordConfig(
        webhook_url=discord_raw.get("webhook_url") or None,
        notify_on_success=discord_raw.get("notify_on_success", True),
        notify_on_failure=discord_raw.get("notify_on_failure", True),
        notify_on_start=discord_raw.get("notify_on_start", False),
        notify_on_finish=discord_raw.get("notify_on_finish", False),
        notify_on_progress=discord_raw.get("notify_on_progress", False),
    )
    global_config = GlobalConfig(
        default_rsync_options=global_raw.get(
            "default_rsync_options", ["-avz", "--delete"]
        ),
        log_dir=global_raw.get("log_dir", ""),
        max_log_files=global_raw.get("max_log_files", 30),
        parallel_jobs=global_raw.get("parallel_jobs", 1),
        daemon_interval=global_raw.get("daemon_interval", 3600),
        api_enabled=global_raw.get("api_enabled", False),
        api_port=global_raw.get("api_port", 58080),
        telegram=telegram,
        discord=discord,
    )

    mirrors: dict[str, Mirror] = {}
    for name, mraw in raw.get("mirrors", {}).items():
        last_sync_raw = mraw.get("last_sync")
        from datetime import datetime

        last_sync = datetime.fromisoformat(last_sync_raw) if last_sync_raw else None
        mirrors[name] = Mirror(
            name=name,
            url=mraw["url"],
            local_path=mraw["local_path"],
            mirror_type=MirrorType(mraw.get("mirror_type", "rsync")),
            enabled=mraw.get("enabled", True),
            description=mraw.get("description", ""),
            rsync_options=mraw.get("rsync_options", ["-avz", "--delete"]),
            http_options=mraw.get("http_options", []),
            bandwidth_limit=mraw.get("bandwidth_limit"),
            last_sync=last_sync,
            last_status=mraw.get("last_status", "never"),
            last_size=mraw.get("last_size"),
        )

    return XsyncConfig(
        version=raw.get("version", 1),
        global_config=global_config,
        mirrors=mirrors,
    )
