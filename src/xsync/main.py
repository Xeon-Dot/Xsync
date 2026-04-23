"""Xsync — Linux mirror synchronization and management CLI."""

from __future__ import annotations

import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from xsync.api import format_size
from xsync.config import get_config_dir, get_config_path, load_config, save_config
from xsync.discord import notify_sync_finish as notify_discord_finish
from xsync.discord import notify_sync_progress as notify_discord_progress
from xsync.discord import notify_sync_result as notify_discord
from xsync.discord import notify_sync_start as notify_discord_start
from xsync.models import Mirror, MirrorType, SyncStatus, XsyncConfig
from xsync.sync import diff_mirror, purge_old_logs, sync_mirror
from xsync.telegram import notify_sync_finish as notify_telegram_finish
from xsync.telegram import notify_sync_progress as notify_telegram_progress
from xsync.telegram import notify_sync_result as notify_telegram
from xsync.telegram import notify_sync_start as notify_telegram_start

app = typer.Typer(
    name="xsync",
    help="Linux mirror synchronization and management CLI.",
    add_completion=True,
    no_args_is_help=True,
)
mirror_app = typer.Typer(help="Manage mirror configurations.", no_args_is_help=True)
config_app = typer.Typer(
    help="Manage global Xsync configuration.", no_args_is_help=True
)
daemon_app = typer.Typer(
    help="Manage the background sync daemon.", no_args_is_help=True
)
api_app = typer.Typer(help="Manage the API server.", no_args_is_help=True)

app.add_typer(mirror_app, name="mirror")
app.add_typer(config_app, name="config")
app.add_typer(daemon_app, name="daemon")
app.add_typer(api_app, name="api")

console = Console()

# ---------------------------------------------------------------------------
# Shared option
# ---------------------------------------------------------------------------

ConfigDirOption = Annotated[
    Optional[Path],
    typer.Option(
        "--config-dir",
        "-C",
        help="Path to Xsync configuration directory.",
        envvar="XSYNC_CONFIG_DIR",
        show_default=False,
    ),
]


# ---------------------------------------------------------------------------
# xsync init
# ---------------------------------------------------------------------------


@app.command()
def init(
    config_dir: ConfigDirOption = None,
) -> None:
    """Initialise the Xsync configuration directory."""
    cfg_dir = get_config_dir(config_dir)
    cfg_path = get_config_path(config_dir)

    if cfg_path.exists():
        rprint(f"[yellow]Configuration already exists at[/yellow] {cfg_path}")
        return

    cfg = XsyncConfig()
    save_config(cfg, config_dir)
    rprint(f"[green]✓ Initialised Xsync configuration at[/green] {cfg_dir}")


# ---------------------------------------------------------------------------
# xsync mirror add
# ---------------------------------------------------------------------------


@mirror_app.command("add")
def mirror_add(
    name: Annotated[str, typer.Argument(help="Unique mirror name (slug).")],
    url: Annotated[
        str, typer.Argument(help="Source URL (rsync://, http://, https://, ftp://).")
    ],
    local_path: Annotated[str, typer.Argument(help="Local destination directory.")],
    mirror_type: Annotated[
        MirrorType,
        typer.Option("--type", "-t", help="Sync protocol."),
    ] = MirrorType.RSYNC,
    description: Annotated[
        str, typer.Option("--description", "-d", help="Short description.")
    ] = "",
    bandwidth_limit: Annotated[
        Optional[str],
        typer.Option("--bwlimit", "-b", help="Bandwidth limit for rsync (e.g. '10m')."),
    ] = None,
    rsync_opts: Annotated[
        Optional[str],
        typer.Option(
            "--rsync-opts",
            help="Space-separated rsync options (overrides defaults, e.g. '-avz --delete').",  # noqa: E501
        ),
    ] = None,
    config_dir: ConfigDirOption = None,
) -> None:
    """Add a new mirror to the configuration."""
    cfg = load_config(config_dir)

    if name in cfg.mirrors:
        rprint(f"[red]Error:[/red] Mirror [bold]{name}[/bold] already exists.")
        raise typer.Exit(1)

    rsync_options = (
        rsync_opts.split() if rsync_opts else cfg.global_config.default_rsync_options
    )

    try:
        mirror = Mirror(
            name=name,
            url=url,
            local_path=local_path,
            mirror_type=mirror_type,
            description=description,
            bandwidth_limit=bandwidth_limit,
            rsync_options=rsync_options,
        )
    except Exception as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    cfg.mirrors[name] = mirror
    save_config(cfg, config_dir)
    rprint(f"[green]✓ Added mirror[/green] [bold]{name}[/bold]  →  {url}")


# ---------------------------------------------------------------------------
# xsync mirror remove
# ---------------------------------------------------------------------------


@mirror_app.command("remove")
def mirror_remove(
    name: Annotated[str, typer.Argument(help="Mirror name to remove.")],
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")
    ] = False,
    config_dir: ConfigDirOption = None,
) -> None:
    """Remove a mirror from the configuration."""
    cfg = load_config(config_dir)

    if name not in cfg.mirrors:
        rprint(f"[red]Error:[/red] Mirror [bold]{name}[/bold] not found.")
        raise typer.Exit(1)

    if not yes:
        typer.confirm(f"Remove mirror '{name}'?", abort=True)

    del cfg.mirrors[name]
    save_config(cfg, config_dir)
    rprint(f"[green]✓ Removed mirror[/green] [bold]{name}[/bold]")


# ---------------------------------------------------------------------------
# xsync mirror list
# ---------------------------------------------------------------------------


@mirror_app.command("list")
def mirror_list(
    config_dir: ConfigDirOption = None,
) -> None:
    """List all configured mirrors."""
    cfg = load_config(config_dir)

    if not cfg.mirrors:
        rprint(
            "[yellow]No mirrors configured.[/yellow]  Run [bold]xsync mirror add[/bold] to add one."  # noqa: E501
        )
        return

    table = Table(title="Configured Mirrors", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Type", style="magenta")
    table.add_column("URL")
    table.add_column("Local Path")
    table.add_column("Enabled")
    table.add_column("Last Status")
    table.add_column("Last Sync")

    for mirror in cfg.mirrors.values():
        status_style = _status_style(mirror.last_status)
        table.add_row(
            mirror.name,
            mirror.mirror_type.value,
            mirror.url,
            mirror.local_path,
            "[green]✓[/green]" if mirror.enabled else "[red]✗[/red]",
            f"[{status_style}]{mirror.last_status.value}[/{status_style}]",
            mirror.last_sync.strftime("%Y-%m-%d %H:%M UTC")
            if mirror.last_sync
            else "—",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# xsync mirror show
# ---------------------------------------------------------------------------


@mirror_app.command("show")
def mirror_show(
    name: Annotated[str, typer.Argument(help="Mirror name.")],
    config_dir: ConfigDirOption = None,
) -> None:
    """Show detailed information about a single mirror."""
    cfg = load_config(config_dir)
    mirror = _get_mirror(cfg, name)

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    rows = [
        ("Name", mirror.name),
        ("Description", mirror.description or "—"),
        ("URL", mirror.url),
        ("Local Path", mirror.local_path),
        ("Type", mirror.mirror_type.value),
        ("Enabled", "yes" if mirror.enabled else "no"),
        ("Rsync Options", " ".join(mirror.rsync_options)),
        ("HTTP Options", " ".join(mirror.http_options) if mirror.http_options else "—"),
        ("Bandwidth Limit", mirror.bandwidth_limit or "—"),
        ("Last Sync", mirror.last_sync.isoformat() if mirror.last_sync else "—"),
        ("Last Status", mirror.last_status.value),
    ]
    for key, value in rows:
        table.add_row(key, value)

    console.print(table)


# ---------------------------------------------------------------------------
# xsync mirror enable / disable
# ---------------------------------------------------------------------------


@mirror_app.command("enable")
def mirror_enable(
    name: Annotated[str, typer.Argument(help="Mirror name.")],
    config_dir: ConfigDirOption = None,
) -> None:
    """Enable a mirror."""
    _set_mirror_enabled(name, True, config_dir)


@mirror_app.command("disable")
def mirror_disable(
    name: Annotated[str, typer.Argument(help="Mirror name.")],
    config_dir: ConfigDirOption = None,
) -> None:
    """Disable a mirror (skip during sync)."""
    _set_mirror_enabled(name, False, config_dir)


def _set_mirror_enabled(name: str, enabled: bool, config_dir: Optional[Path]) -> None:
    cfg = load_config(config_dir)
    mirror = _get_mirror(cfg, name)
    mirror.enabled = enabled
    cfg.mirrors[name] = mirror
    save_config(cfg, config_dir)
    state = "enabled" if enabled else "disabled"
    rprint(f"[green]✓[/green] Mirror [bold]{name}[/bold] {state}.")


# ---------------------------------------------------------------------------
# xsync mirror diff
# ---------------------------------------------------------------------------


@mirror_app.command("diff")
def mirror_diff(
    name: Annotated[str, typer.Argument(help="Mirror name.")],
    config_dir: ConfigDirOption = None,
) -> None:
    """Show rsync dry-run diff for a mirror (what would change)."""
    cfg = load_config(config_dir)
    mirror = _get_mirror(cfg, name)

    try:
        output = diff_mirror(mirror)
    except Exception as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if not output.strip():
        rprint("[dim]No changes.[/dim]")
    else:
        print(output)


# ---------------------------------------------------------------------------
# xsync sync
# ---------------------------------------------------------------------------


@app.command()
def sync(
    names: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="Mirror name(s) to sync. Omit to sync all enabled mirrors."
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", "-n", help="Print the sync command without executing it."
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Print subprocess output to console."),
    ] = False,
    config_dir: ConfigDirOption = None,
) -> None:
    """Sync one or more mirrors."""
    cfg = load_config(config_dir)
    cfg_dir = get_config_dir(config_dir)
    log_dir_base = (
        Path(cfg.global_config.log_dir)
        if cfg.global_config.log_dir
        else cfg_dir / "logs"
    )

    targets = _resolve_sync_targets(cfg, names)
    if not targets:
        rprint("[yellow]No mirrors to sync.[/yellow]")
        return

    if dry_run:
        any_failure = False
        for mirror in targets:
            rprint(
                f"\n[bold cyan]Syncing[/bold cyan] [bold]{mirror.name}[/bold]  ({mirror.url})"  # noqa: E501
            )
            from xsync.sync import _build_command

            try:
                cmd = _build_command(mirror)
                rprint(f"  [dim]dry-run command:[/dim] {' '.join(cmd)}")
            except Exception as exc:
                rprint(f"  [red]Could not build command:[/red] {exc}")
                any_failure = True
        if any_failure:
            raise typer.Exit(1)
        return

    def _make_progress_cb(name: str):
        last_milestone = [-1]

        def _cb(pct: int) -> None:
            if pct > last_milestone[0]:
                last_milestone[0] = pct
                notify_telegram_progress(cfg.global_config.telegram, name, pct)
                notify_discord_progress(cfg.global_config.discord, name, pct)

        return _cb

    def _sync_one(mirror: Mirror) -> tuple[Mirror, SyncResult]:
        log_dir = log_dir_base / mirror.name
        on_progress = None
        if (
            cfg.global_config.telegram.notify_on_progress
            or cfg.global_config.discord.notify_on_progress
        ):
            on_progress = _make_progress_cb(mirror.name)
        result = sync_mirror(mirror, log_dir, verbose=verbose, on_progress=on_progress)
        return mirror, result

    # Send start notifications before kicking off threads
    for mirror in targets:
        notify_telegram_start(cfg.global_config.telegram, mirror.name)
        notify_discord_start(cfg.global_config.discord, mirror.name)

    any_failure = False
    completed = []

    if cfg.global_config.parallel_jobs > 1 and len(targets) > 1:
        with ThreadPoolExecutor(max_workers=cfg.global_config.parallel_jobs) as executor:
            futures = [executor.submit(_sync_one, m) for m in targets]
            for future in as_completed(futures):
                mirror, result = future.result()
                completed.append((mirror, result))
    else:
        for mirror in targets:
            mirror, result = _sync_one(mirror)
            completed.append((mirror, result))

    # Process results sequentially to avoid config race conditions
    for mirror, result in completed:
        mirror.last_sync = datetime.now(tz=timezone.utc)
        mirror.last_status = result.status
        if result.status == SyncStatus.SUCCESS and result.size_bytes is not None:
            mirror.previous_size = mirror.last_size
            mirror.last_size = result.size_bytes
        cfg.mirrors[mirror.name] = mirror
        save_config(cfg, config_dir)

        notify_telegram(
            cfg.global_config.telegram,
            mirror.name,
            result.status,
            result.duration_seconds,
            result.error,
        )
        notify_discord(
            cfg.global_config.discord,
            mirror.name,
            result.status,
            result.duration_seconds,
            result.error,
        )
        notify_telegram_finish(
            cfg.global_config.telegram,
            mirror.name,
            result.status,
            result.duration_seconds,
            result.error,
        )
        notify_discord_finish(
            cfg.global_config.discord,
            mirror.name,
            result.status,
            result.duration_seconds,
            result.error,
        )

        log_dir = log_dir_base / mirror.name
        purge_old_logs(log_dir, mirror.name, cfg.global_config.max_log_files)

        style = _status_style(result.status)
        rprint(
            f"\n[bold cyan]Syncing[/bold cyan] [bold]{mirror.name}[/bold]  ({mirror.url})"
        )
        rprint(
            f"  [{style}]{result.status.value.upper()}[/{style}]  "
            f"({result.duration_seconds:.1f}s)  "
            f"log → {result.log_path}"
        )
        if result.error:
            rprint(f"  [red]Error:[/red] {result.error}")
            any_failure = True

    if any_failure:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# xsync status
# ---------------------------------------------------------------------------


@app.command()
def status(
    names: Annotated[
        Optional[list[str]],
        typer.Argument(help="Mirror name(s). Omit to show all."),
    ] = None,
    config_dir: ConfigDirOption = None,
) -> None:
    """Show sync status of mirrors."""
    cfg = load_config(config_dir)

    if not cfg.mirrors:
        rprint("[yellow]No mirrors configured.[/yellow]")
        return

    targets = _resolve_sync_targets(cfg, names, skip_disabled=False)

    table = Table(title="Mirror Status", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Enabled")
    table.add_column("Last Status")
    table.add_column("Last Sync")
    table.add_column("Last Size")
    table.add_column("Trend")

    for mirror in targets:
        style = _status_style(mirror.last_status)
        size_str = format_size(mirror.last_size) if mirror.last_size else "—"
        trend = "—"
        if mirror.last_size is not None and mirror.previous_size is not None:
            delta = mirror.last_size - mirror.previous_size
            if delta > 0:
                trend = f"[green]+{format_size(delta)}[/green]"
            elif delta < 0:
                trend = f"[red]-{format_size(abs(delta))}[/red]"
            else:
                trend = "[dim]0 B[/dim]"
        table.add_row(
            mirror.name,
            "[green]✓[/green]" if mirror.enabled else "[red]✗[/red]",
            f"[{style}]{mirror.last_status.value}[/{style}]",
            mirror.last_sync.strftime("%Y-%m-%d %H:%M UTC")
            if mirror.last_sync
            else "—",
            size_str,
            trend,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# xsync log
# ---------------------------------------------------------------------------


@app.command()
def log(
    name: Annotated[str, typer.Argument(help="Mirror name.")],
    lines: Annotated[
        int, typer.Option("--lines", "-n", help="Number of lines to show.")
    ] = 50,
    config_dir: ConfigDirOption = None,
) -> None:
    """Show the latest sync log for a mirror."""
    cfg = load_config(config_dir)
    _get_mirror(cfg, name)  # ensure it exists

    cfg_dir = get_config_dir(config_dir)
    log_dir_base = (
        Path(cfg.global_config.log_dir)
        if cfg.global_config.log_dir
        else cfg_dir / "logs"
    )
    log_dir = log_dir_base / name

    logs = sorted(log_dir.glob(f"{name}-*.log"))
    if not logs:
        rprint(f"[yellow]No log files found for mirror[/yellow] [bold]{name}[/bold].")
        return

    latest = logs[-1]
    rprint(f"[dim]Log file:[/dim] {latest}\n")

    with latest.open(encoding="utf-8") as fh:
        all_lines = fh.readlines()

    output_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
    for line in output_lines:
        rprint(line, end="")


# ---------------------------------------------------------------------------
# xsync config show
# ---------------------------------------------------------------------------


@config_app.command("show")
def config_show(
    config_dir: ConfigDirOption = None,
) -> None:
    """Show the current global configuration."""
    cfg = load_config(config_dir)
    cfg_path = get_config_path(config_dir)

    rprint(f"[dim]Config file:[/dim] {cfg_path}\n")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    gc = cfg.global_config
    table.add_row("default_rsync_options", " ".join(gc.default_rsync_options))
    table.add_row("log_dir", gc.log_dir or "(config_dir/logs)")
    table.add_row("max_log_files", str(gc.max_log_files))
    table.add_row("parallel_jobs", str(gc.parallel_jobs))
    table.add_row("daemon_interval", str(gc.daemon_interval))
    table.add_row("daemon_schedule", gc.daemon_schedule or "(not set)")
    table.add_row("api_enabled", str(gc.api_enabled))
    table.add_row("api_port", str(gc.api_port))
    table.add_row("mirrors_count", str(len(cfg.mirrors)))
    tg = gc.telegram
    masked_token = (tg.bot_token[:6] + "…") if tg.bot_token else "(not set)"
    table.add_row("telegram.bot_token", masked_token)
    table.add_row("telegram.chat_id", tg.chat_id or "(not set)")
    table.add_row("telegram.notify_on_success", str(tg.notify_on_success))
    table.add_row("telegram.notify_on_failure", str(tg.notify_on_failure))
    table.add_row("telegram.notify_on_start", str(tg.notify_on_start))
    table.add_row("telegram.notify_on_finish", str(tg.notify_on_finish))
    table.add_row("telegram.notify_on_progress", str(tg.notify_on_progress))
    dc = gc.discord
    masked_webhook = (
        (dc.webhook_url[:32] + "…" if len(dc.webhook_url) > 32 else dc.webhook_url)
        if dc.webhook_url
        else "(not set)"
    )
    table.add_row("discord.webhook_url", masked_webhook)
    table.add_row("discord.notify_on_success", str(dc.notify_on_success))
    table.add_row("discord.notify_on_failure", str(dc.notify_on_failure))
    table.add_row("discord.notify_on_start", str(dc.notify_on_start))
    table.add_row("discord.notify_on_finish", str(dc.notify_on_finish))
    table.add_row("discord.notify_on_progress", str(dc.notify_on_progress))

    console.print(table)


# ---------------------------------------------------------------------------
# xsync config set
# ---------------------------------------------------------------------------


@config_app.command("set")
def config_set(
    key: Annotated[
        str,
        typer.Argument(help="Config key (e.g. max_log_files, parallel_jobs, log_dir)."),
    ],
    value: Annotated[str, typer.Argument(help="New value.")],
    config_dir: ConfigDirOption = None,
) -> None:
    """Set a global configuration value."""
    cfg = load_config(config_dir)
    gc = cfg.global_config

    int_keys = {"max_log_files", "parallel_jobs", "daemon_interval", "api_port"}
    list_keys = {"default_rsync_options"}
    str_keys = {"log_dir", "daemon_schedule"}
    bool_keys = {"api_enabled"}
    telegram_str_keys = {"telegram.bot_token", "telegram.chat_id"}
    telegram_bool_keys = {
        "telegram.notify_on_success",
        "telegram.notify_on_failure",
        "telegram.notify_on_start",
        "telegram.notify_on_finish",
        "telegram.notify_on_progress",
    }
    discord_str_keys = {"discord.webhook_url"}
    discord_bool_keys = {
        "discord.notify_on_success",
        "discord.notify_on_failure",
        "discord.notify_on_start",
        "discord.notify_on_finish",
        "discord.notify_on_progress",
    }

    if key in int_keys:
        try:
            setattr(gc, key, int(value))
        except ValueError:
            rprint(f"[red]Error:[/red] '{key}' requires an integer value.")
            raise typer.Exit(1)
    elif key in list_keys:
        setattr(gc, key, value.split())
    elif key in str_keys:
        setattr(gc, key, value)
    elif key in bool_keys:
        if value.lower() in ("true", "1", "yes"):
            setattr(gc, key, True)
        elif value.lower() in ("false", "0", "no"):
            setattr(gc, key, False)
        else:
            rprint(f"[red]Error:[/red] '{key}' requires a boolean value (true/false).")
            raise typer.Exit(1)
    elif key in telegram_str_keys:
        attr = key.split(".")[1]
        setattr(gc.telegram, attr, value or None)
    elif key in telegram_bool_keys:
        attr = key.split(".")[1]
        if value.lower() in ("true", "1", "yes"):
            setattr(gc.telegram, attr, True)
        elif value.lower() in ("false", "0", "no"):
            setattr(gc.telegram, attr, False)
        else:
            rprint(f"[red]Error:[/red] '{key}' requires a boolean value (true/false).")
            raise typer.Exit(1)
    elif key in discord_str_keys:
        attr = key.split(".")[1]
        setattr(gc.discord, attr, value or None)
    elif key in discord_bool_keys:
        attr = key.split(".")[1]
        if value.lower() in ("true", "1", "yes"):
            setattr(gc.discord, attr, True)
        elif value.lower() in ("false", "0", "no"):
            setattr(gc.discord, attr, False)
        else:
            rprint(f"[red]Error:[/red] '{key}' requires a boolean value (true/false).")
            raise typer.Exit(1)
    else:
        all_keys = (
            int_keys
            | list_keys
            | str_keys
            | bool_keys
            | telegram_str_keys
            | telegram_bool_keys
            | discord_str_keys
            | discord_bool_keys
        )
        valid = ", ".join(sorted(all_keys))
        rprint(f"[red]Error:[/red] Unknown key '{key}'. Valid keys: {valid}")
        raise typer.Exit(1)

    cfg.global_config = gc
    save_config(cfg, config_dir)
    rprint(f"[green]✓[/green] Set [bold]{key}[/bold] = {value!r}")


# ---------------------------------------------------------------------------
# xsync config validate
# ---------------------------------------------------------------------------


@config_app.command("validate")
def config_validate(
    config_dir: ConfigDirOption = None,
) -> None:
    """Validate the current configuration and report issues."""
    cfg = load_config(config_dir)
    errors: list[str] = []
    warnings: list[str] = []

    if not shutil.which("rsync"):
        warnings.append("rsync not found on PATH")
    if not shutil.which("wget"):
        warnings.append("wget not found on PATH")

    for name, mirror in cfg.mirrors.items():
        if mirror.mirror_type == MirrorType.RSYNC and not shutil.which("rsync"):
            errors.append(f"[{name}] rsync mirror but rsync not installed")
        if mirror.mirror_type in (MirrorType.HTTP, MirrorType.FTP) and not shutil.which("wget"):
            errors.append(f"[{name}] http/ftp mirror but wget not installed")
        parent = Path(mirror.local_path).parent
        if not parent.exists():
            errors.append(f"[{name}] parent directory does not exist: {parent}")
        elif not os.access(parent, os.W_OK):
            errors.append(f"[{name}] parent directory not writable: {parent}")

    tg = cfg.global_config.telegram
    if tg.bot_token and not tg.chat_id:
        warnings.append("telegram.bot_token set but chat_id missing")
    if tg.chat_id and not tg.bot_token:
        warnings.append("telegram.chat_id set but bot_token missing")

    dc = cfg.global_config.discord
    if dc.webhook_url and not dc.webhook_url.startswith("https://discord.com/api/webhooks/"):
        warnings.append("discord.webhook_url does not look like a Discord webhook URL")

    if errors:
        rprint(f"[red]{len(errors)} error(s) found:[/red]")
        for e in errors:
            rprint(f"  [red]✗[/red] {e}")
    if warnings:
        rprint(f"[yellow]{len(warnings)} warning(s) found:[/yellow]")
        for w in warnings:
            rprint(f"  [yellow]![/yellow] {w}")
    if not errors and not warnings:
        rprint("[green]✓ Configuration is valid.[/green]")

    if errors:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# xsync daemon start / stop / status
# ---------------------------------------------------------------------------


@daemon_app.command("start")
def daemon_start(
    names: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="Mirror name(s) to sync. Omit to sync all enabled mirrors."
        ),
    ] = None,
    interval: Annotated[
        Optional[int],
        typer.Option(
            "--interval",
            "-i",
            help="Sync interval in seconds. Overrides daemon_interval from config.",
            show_default=False,
        ),
    ] = None,
    api: Annotated[
        bool,
        typer.Option(
            "--api",
            "-a",
            help="Enable API server alongside daemon.",
        ),
    ] = False,
    api_port: Annotated[
        Optional[int],
        typer.Option(
            "--api-port",
            help="API server port. Overrides api_port from config.",
        ),
    ] = None,
    config_dir: ConfigDirOption = None,
) -> None:
    """Start the background sync daemon.

    The daemon forks into the background and keeps running even after the
    terminal is closed or the user logs out.  Sync results are written to
    the daemon log file inside the config directory.
    """
    from xsync.daemon import (  # noqa: PLC0415
        daemonize,
        get_daemon_log_file,
        get_pid_file,
        is_running,
        read_pid,
        run_daemon_loop,
    )

    cfg = load_config(config_dir)
    cfg_dir = get_config_dir(config_dir)
    pid_file = get_pid_file(cfg_dir)

    if is_running(pid_file):
        existing_pid = read_pid(pid_file)
        rprint(f"[yellow]Daemon is already running (PID {existing_pid}).[/yellow]")
        raise typer.Exit(1)

    sync_interval = (
        interval if interval is not None else cfg.global_config.daemon_interval
    )
    log_file = get_daemon_log_file(cfg_dir)

    enable_api = api or cfg.global_config.api_enabled
    final_api_port = api_port if api_port is not None else cfg.global_config.api_port

    if enable_api:
        rprint(
            f"[green]Starting Xsync daemon[/green] "
            f"(interval={sync_interval}s, log={log_file}, api=enabled, port={final_api_port})"
        )
    else:
        rprint(
            f"[green]Starting Xsync daemon[/green] "
            f"(interval={sync_interval}s, log={log_file})"
        )

    daemonize(log_file)
    run_daemon_loop(
        cfg_dir, names if names else None, sync_interval, enable_api, final_api_port
    )


@daemon_app.command("stop")
def daemon_stop(
    config_dir: ConfigDirOption = None,
    force: bool = typer.Option(
        False, "--force", help="Send SIGKILL instead of SIGTERM."
    ),
) -> None:
    """Stop the running background sync daemon."""
    from xsync.daemon import (
        get_pid_file,
        is_running,
        read_pid,
        stop_daemon,
    )

    cfg_dir = get_config_dir(config_dir)
    pid_file = get_pid_file(cfg_dir)

    if not is_running(pid_file):
        rprint("[yellow]Daemon is not running.[/yellow]")
        return

    pid = read_pid(pid_file)
    if stop_daemon(pid_file, force):
        sig = "SIGKILL" if force else "SIGTERM"
        rprint(f"[green]✓ Sent {sig} to daemon (PID {pid}).[/green]")
    else:
        rprint("[red]Failed to stop daemon.[/red]")
        raise typer.Exit(1)


@daemon_app.command("status")
def daemon_status(
    config_dir: ConfigDirOption = None,
) -> None:
    """Show whether the background sync daemon is running."""
    from xsync.daemon import (
        get_daemon_log_file,
        get_pid_file,
        is_running,
        read_pid,
    )

    cfg_dir = get_config_dir(config_dir)
    pid_file = get_pid_file(cfg_dir)
    log_file = get_daemon_log_file(cfg_dir)

    if is_running(pid_file):
        pid = read_pid(pid_file)
        rprint(f"[green]● Daemon is running[/green] (PID {pid})")
        rprint(f"  [dim]log →[/dim] {log_file}")
    else:
        rprint("[dim]○ Daemon is not running[/dim]")


@daemon_app.command("restart")
def daemon_restart(
    names: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="Mirror name(s) to sync. Omit to sync all enabled mirrors."
        ),
    ] = None,
    interval: Annotated[
        Optional[int],
        typer.Option(
            "--interval",
            "-i",
            help="Sync interval in seconds. Overrides daemon_interval from config.",
            show_default=False,
        ),
    ] = None,
    api: Annotated[
        bool,
        typer.Option(
            "--api",
            "-a",
            help="Enable API server alongside daemon.",
        ),
    ] = False,
    api_port: Annotated[
        Optional[int],
        typer.Option(
            "--api-port",
            help="API server port. Overrides api_port from config.",
        ),
    ] = None,
    config_dir: ConfigDirOption = None,
    force: bool = typer.Option(
        False, "--force", help="Use SIGKILL to stop the daemon."
    ),
) -> None:
    """Restart the background sync daemon."""
    from xsync.daemon import (
        get_pid_file,
        is_running,
        read_pid,
        stop_daemon,
    )

    cfg_dir = get_config_dir(config_dir)
    pid_file = get_pid_file(cfg_dir)

    if is_running(pid_file):
        pid = read_pid(pid_file)
        if stop_daemon(pid_file, force):
            sig = "SIGKILL" if force else "SIGTERM"
            rprint(f"[yellow]Stopping daemon ({sig}, PID {pid})...[/yellow]")
            time.sleep(1)
        else:
            rprint("[red]Failed to stop daemon.[/red]")
            raise typer.Exit(1)

    daemon_start(
        names=names,
        interval=interval,
        api=api,
        api_port=api_port,
        config_dir=config_dir,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_mirror(cfg: XsyncConfig, name: str) -> Mirror:
    if name not in cfg.mirrors:
        rprint(f"[red]Error:[/red] Mirror [bold]{name}[/bold] not found.")
        raise typer.Exit(1)
    return cfg.mirrors[name]


def _resolve_sync_targets(
    cfg: XsyncConfig,
    names: Optional[list[str]],
    skip_disabled: bool = True,
) -> list[Mirror]:
    """Return the list of mirrors to operate on."""
    if names:
        mirrors = []
        for n in names:
            mirrors.append(_get_mirror(cfg, n))
        return mirrors

    mirrors = list(cfg.mirrors.values())
    if skip_disabled:
        mirrors = [m for m in mirrors if m.enabled]
    return mirrors


def _status_style(status: SyncStatus) -> str:
    return {
        SyncStatus.SUCCESS: "green",
        SyncStatus.FAILED: "red",
        SyncStatus.RUNNING: "yellow",
        SyncStatus.PENDING: "blue",
        SyncStatus.NEVER: "dim",
    }.get(status, "white")


# ---------------------------------------------------------------------------
# xsync api start / stop / status
# ---------------------------------------------------------------------------


@api_app.command("start")
def api_start(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="API server port."),
    ] = 58080,
    config_dir: ConfigDirOption = None,
) -> None:
    """Start the API server."""
    from xsync.api import init_api_state, run_api_server

    cfg_dir = get_config_dir(config_dir)
    init_api_state(config_dir)
    rprint(f"[green]Starting Xsync API server[/green] on port {port}")
    rprint(f"[dim]Config directory: {cfg_dir}[/dim]")
    rprint(f"[dim]API endpoint: http://0.0.0.0:{port}/api/status[/dim]")
    run_api_server(port=port)


@api_app.command("stop")
def api_stop(
    config_dir: ConfigDirOption = None,
) -> None:
    """Stop the API server (when running as a separate process)."""
    rprint("[yellow]Use Ctrl+C to stop the API server.[/yellow]")


@api_app.command("status")
def api_status(
    config_dir: ConfigDirOption = None,
) -> None:
    """Show API server status."""
    rprint("[dim]API server runs in foreground. Use 'xsync api start' to start.[/dim]")


if __name__ == "__main__":
    app()
