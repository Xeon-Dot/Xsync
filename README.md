# Xsync

> **Linux mirror synchronization and management CLI tool**
> Built with Python · [uv](https://docs.astral.sh/uv/) · [Typer](https://typer.tiangolo.com/) · [Rich](https://rich.readthedocs.io/) · [FastAPI](https://fastapi.tiangolo.com/)

---

## Features

| Feature | Details |
| --- | --- |
| **rsync mirrors** | Full rsync support with custom options, bandwidth limiting, and progress tracking |
| **HTTP / FTP mirrors** | wget-based mirroring for HTTP and FTP sources |
| **Daemon mode** | Background sync with interval-based or cron-based scheduling |
| **REST API** | FastAPI monitoring API for mirror status and sizes |
| **Notifications** | Alerts via Telegram Bot API and Discord Webhook (start, finish, progress, disk usage) |
| **Health checks** | Validate tools, paths, config, and mirror disk usage |
| **TOML config** | Human-readable `~/.config/xsync/config.toml` |
| **Sync logs** | Per-run log files with automatic rotation |
| **Rich output** | Colour-coded tables and status indicators |
| **Shell completion** | bash / zsh / fish via Typer |

---

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- `rsync` (for rsync mirrors)
- `wget` (for HTTP/FTP mirrors)

---

## Installation

```bash
# Clone the repo
git clone https://github.com/xeon-dot/Xsync.git
cd Xsync

# Install with uv
uv sync

# Run directly
uv run xsync --help

# Or install the entry-point globally
uv tool install .
xsync --help
```

---

## Quick Start

```bash
# 1. Initialise configuration
xsync init

# 2. Add mirrors
xsync mirror add ubuntu  rsync://mirror.kakao.com/ubuntu    /srv/mirrors/ubuntu
xsync mirror add debian  http://ftp.debian.org/debian       /srv/mirrors/debian --type http

# 3. List mirrors
xsync mirror list

# 4. Sync all enabled mirrors
xsync sync

# 5. Check status
xsync status
```

---

## Commands

### `xsync init`

Initialise the Xsync configuration directory (`~/.config/xsync/`).

```shell
xsync init [--config-dir PATH]
```

---

### `xsync mirror`

#### `mirror add`

```shell
xsync mirror add NAME URL LOCAL_PATH [OPTIONS]

Options:
  --type       rsync | http | ftp          (default: rsync)
  --description TEXT
  --bwlimit    Bandwidth limit for rsync   (e.g. "10m" for 10 MB/s)
  --rsync-opts Space-separated rsync options (overrides defaults)
```

#### `mirror remove`

```shell
xsync mirror remove NAME [--yes]
```

#### `mirror list`

List all configured mirrors in a table.

#### `mirror show NAME`

Show detailed information about a single mirror.

#### `mirror enable / disable NAME`

Enable or disable a mirror (disabled mirrors are skipped during sync).

#### `mirror diff NAME`

Show rsync dry-run diff for a mirror (what would change). Only works for rsync mirrors.

---

### `xsync sync`

```shell
xsync sync [NAME ...] [--dry-run] [--verbose]
```

Sync one or all enabled mirrors.

| Option | Short | Description |
| --- | --- | --- |
| `--dry-run` | `-n` | Print the sync command without executing |
| `--verbose` | `-v` | Print subprocess output to console |

---

### `xsync status`

```shell
xsync status [NAME ...]
```

Show the last sync status, timestamp, and size for mirrors.

---

### `xsync health`

```shell
xsync health [NAME ...]
```

Check configuration, required tools, mirror paths, and disk usage thresholds.

---

### `xsync log NAME`

```shell
xsync log NAME [--lines N]
```

Print the latest sync log for a mirror (default: last 50 lines).

---

### `xsync daemon`

Run background sync on a schedule.

#### `daemon start [NAME ...]`

```shell
xsync daemon start [OPTIONS]

Options:
  --interval SECONDS   Sync interval (overrides daemon_interval config)
  --api                Enable API server alongside daemon
  --api-port PORT      API server port (overrides api_port config)
```

Detaches from the terminal (double-fork). PID file at `{config_dir}/xsync-daemon.pid`.

Supports two scheduling modes:
- **Interval-based**: sleeps `daemon_interval` seconds between cycles (default: 3600)
- **Cron-based**: uses `daemon_schedule` cron expression (e.g. `"0 */6 * * *"`)

#### `daemon stop`

```shell
xsync daemon stop [--force]
```

`--force` sends SIGKILL instead of SIGTERM.

#### `daemon status`

Show whether the background sync daemon is running.

#### `daemon restart [NAME ...]`

Restart the daemon. Same options as `daemon start` plus `--force`.

---

### `xsync api`

Run a REST API server for monitoring.

#### `api start`

```shell
xsync api start [--port PORT]
```

Default port: `58080`. PID file at `{config_dir}/xsync-api.pid`.

**Endpoints:**

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/status` | Full status of all mirrors and daemon state |
| `GET` | `/api/mirrors` | List of mirror names |
| `GET` | `/api/mirrors/{name}` | Single mirror status |
| `GET` | `/api/mirrors/{name}/size` | Mirror size info |

#### `api stop`

```shell
xsync api stop [--force]
```

#### `api status`

Show whether the API server is running.

---

### `xsync notify`

#### `notify test`

```shell
xsync notify test [telegram|discord|all]
```

Send a test notification through configured channels.

---

### `xsync config`

#### `config show`

Display current global configuration.

#### `config set KEY VALUE`

Update a global config value. See [Configuration](#configuration) for valid keys.

#### `config validate`

Validate the current configuration and report issues (checks tools, paths, Telegram/Discord config consistency).

---

## Global Option

All commands accept `--config-dir PATH` (or `XSYNC_CONFIG_DIR` env var) to use a non-default configuration directory.

---

## Configuration

Config is stored at `~/.config/xsync/config.toml`:

```toml
version = 1

[global]
default_rsync_options = ["-avz", "--delete"]
log_dir = ""
max_log_files = 30
parallel_jobs = 1
daemon_interval = 3600
daemon_schedule = ""
api_enabled = false
api_port = 58080
disk_usage_warning_percent = 90

[global.telegram]
bot_token = "123456:ABC-DEF"
chat_id = "-100123456"
notify_on_success = true
notify_on_failure = true
notify_on_start = false
notify_on_finish = false
notify_on_progress = false

[global.discord]
webhook_url = "https://discord.com/api/webhooks/123/token"
notify_on_success = true
notify_on_failure = true
notify_on_start = false
notify_on_finish = false
notify_on_progress = false

[mirrors.ubuntu]
url = "rsync://mirror.kakao.com/ubuntu"
local_path = "/srv/mirrors/ubuntu"
mirror_type = "rsync"
enabled = true
description = "Ubuntu LTS mirror"
rsync_options = ["-avz", "--delete"]
http_options = []
bandwidth_limit = "50m"
last_status = "success"
```

### Config Keys

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `default_rsync_options` | list (space-separated) | `["-avz", "--delete"]` | Default rsync flags |
| `log_dir` | string | `""` | Custom log directory |
| `max_log_files` | integer | `30` | Max log files per mirror |
| `parallel_jobs` | integer | `1` | Parallel mirror sync jobs |
| `daemon_interval` | integer | `3600` | Daemon sync interval in seconds |
| `daemon_schedule` | string | `""` | Cron expression for daemon scheduling |
| `api_enabled` | boolean | `false` | Enable API server with daemon |
| `api_port` | integer | `58080` | API server port |
| `disk_usage_warning_percent` | integer | `90` | Disk usage warning threshold (%) |
| `telegram.bot_token` | string | | Telegram Bot API token |
| `telegram.chat_id` | string | | Telegram chat ID |
| `telegram.notify_on_success` | boolean | `true` | Alert on sync success |
| `telegram.notify_on_failure` | boolean | `true` | Alert on sync failure |
| `telegram.notify_on_start` | boolean | `false` | Alert when sync starts |
| `telegram.notify_on_finish` | boolean | `false` | Alert when sync finishes |
| `telegram.notify_on_progress` | boolean | `false` | Alert at 10% progress milestones |
| `discord.webhook_url` | string | | Discord Webhook URL |
| `discord.notify_on_success` | boolean | `true` | Alert on sync success |
| `discord.notify_on_failure` | boolean | `true` | Alert on sync failure |
| `discord.notify_on_start` | boolean | `false` | Alert when sync starts |
| `discord.notify_on_finish` | boolean | `false` | Alert when sync finishes |
| `discord.notify_on_progress` | boolean | `false` | Alert at 10% progress milestones |

---

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_cli.py -v

# Lint
uv run ruff check src/ tests/
```

---

## License

[AGPL-3.0-or-later](LICENSE)
