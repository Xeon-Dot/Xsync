# xync

> **Linux mirror synchronization and management CLI tool**
> Built with Python · [uv](https://docs.astral.sh/uv/) · [Typer](https://typer.tiangolo.com/) · [Rich](https://rich.readthedocs.io/) · [FastAPI](https://fastapi.tiangolo.com/)

---

## Features

### Sync

| Feature | Details |
| --- | --- |
| **rsync mirrors** | Full rsync support with per-mirror options, bandwidth limiting, and progress tracking |
| **HTTP / FTP mirrors** | wget-based mirroring for HTTP, HTTPS, and FTP sources |
| **Mirror diff** | `xync mirror diff` — preview changes before syncing via `rsync --dry-run --itemize-changes` |
| **Parallel sync** | Concurrent mirror syncing via `ThreadPoolExecutor` (configurable `parallel_jobs`) |
| **Dry-run & verbose** | `--dry-run` prints commands without executing; `--verbose` streams live subprocess output |
| **Per-mirror locking** | Atomic lock files prevent overlapping sync runs of the same mirror |

### Daemon

| Feature | Details |
| --- | --- |
| **Background sync** | Double-fork daemon with PID file management and graceful shutdown on SIGTERM/SIGINT |
| **Scheduling** | Interval-based (seconds) or cron-based (e.g. `"0 */6 * * *"`) scheduling via croniter |
| **Config hot-reload** | Re-reads config between sync cycles — no restart needed after config changes |

### API

| Feature | Details |
| --- | --- |
| **REST endpoints** | `GET /api/status`, `/api/mirrors`, `/api/mirrors/{name}`, `/api/mirrors/{name}/size` |
| **Live sync state** | Real-time tracking of currently syncing mirror and status accessible via API |
| **Standalone or threaded** | Run the API server standalone or embedded in the daemon as a background thread |

### Notifications

| Feature | Details |
| --- | --- |
| **Telegram & Discord** | Alerts via Telegram Bot API and Discord Webhooks with per-channel notification toggles |
| **Trigger events** | Configurable alerts for start, success, failure, finish, and progress milestones (every 10%) |
| **Disk warnings** | Automatic alert when mirror filesystem exceeds configurable threshold |
| **Test command** | `xync notify test` to verify notification channel configuration before relying on them |

### Management

| Feature | Details |
| --- | --- |
| **TOML config** | Human-readable `~/.config/xync/config.toml` with schema versioning for future migrations |
| **CLI config editor** | `xync config set` and `xync config validate` — no need to edit TOML by hand |
| **Health checks** | Validate tools on PATH, URL schemes, directory permissions, and disk usage |
| **Sync logs** | Per-run timestamped log files with automatic rotation and in-CLI viewing (`xync log`) |
| **Size trends** | Track previous vs current mirror size delta in `xync status` |
| **Rich output** | Colour-coded tables, status indicators, and progress bars |
| **Shell completion** | bash / zsh / fish via Typer |
| **Standalone binary** | Single-file executable built with PyInstaller — no Python required at runtime |

---

## Requirements

- `rsync` (for rsync mirrors)
- `wget` (for HTTP/FTP mirrors)

For building from source:
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager

---

## Installation

### Option 1: Pre-built Executable (Recommended)

Download the latest release for your platform:

**Linux AMD64 (x86_64):**
```bash
wget https://github.com/xeon-dot/xync/releases/latest/download/xync-linux-amd64.tar.gz
tar -xzf xync-linux-amd64.tar.gz
sudo mv xync /usr/local/bin/
xync --version
```

**Linux ARM64 (aarch64):**
```bash
wget https://github.com/xeon-dot/xync/releases/latest/download/xync-linux-arm64.tar.gz
tar -xzf xync-linux-arm64.tar.gz
sudo mv xync /usr/local/bin/
xync --version
```

**Verify checksum (optional):**
```bash
wget https://github.com/xeon-dot/xync/releases/latest/download/xync-linux-amd64.tar.gz.sha256
sha256sum -c xync-linux-amd64.tar.gz.sha256
```

> **Note:** The executable is self-contained and doesn't require Python to be installed. However, you still need `rsync` and `wget` installed on your system for mirror synchronization.

### Option 2: Install from Source

```bash
# Clone the repo
git clone https://github.com/xeon-dot/xync.git
cd xync

# Install with uv
uv sync

# Run directly
uv run xync --help

# Or install the entry-point globally
uv tool install .
xync --help
```

---

## Quick Start

```bash
# 1. Initialise configuration
xync init

# 2. Add mirrors
xync mirror add ubuntu  rsync://mirror.kakao.com/ubuntu    /srv/mirrors/ubuntu
xync mirror add debian  http://ftp.debian.org/debian       /srv/mirrors/debian --type http

# 3. List mirrors
xync mirror list

# 4. Sync all enabled mirrors
xync sync

# 5. Check status
xync status
```

---

## Commands

### `xync init`

Initialise the xync configuration directory (`~/.config/xync/`).

```shell
xync init [--config-dir PATH]
```

---

### `xync mirror`

#### `mirror add`

```shell
xync mirror add NAME URL LOCAL_PATH [OPTIONS]

Options:
  --type       rsync | http | ftp          (default: rsync)
  --description TEXT
  --bwlimit    Bandwidth limit for rsync   (e.g. "10m" for 10 MB/s)
  --rsync-opts Space-separated rsync options (overrides defaults)
```

#### `mirror remove`

```shell
xync mirror remove NAME [--yes]
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

### `xync sync`

```shell
xync sync [NAME ...] [--dry-run] [--verbose]
```

Sync one or all enabled mirrors.

| Option | Short | Description |
| --- | --- | --- |
| `--dry-run` | `-n` | Print the sync command without executing |
| `--verbose` | `-v` | Print subprocess output to console |

---

### `xync status`

```shell
xync status [NAME ...]
```

Show the last sync status, timestamp, and size for mirrors.

---

### `xync health`

```shell
xync health [NAME ...]
```

Check configuration, required tools, mirror paths, and disk usage thresholds.

---

### `xync log NAME`

```shell
xync log NAME [--lines N]
```

Print the latest sync log for a mirror (default: last 50 lines).

---

### `xync daemon`

Run background sync on a schedule.

#### `daemon start [NAME ...]`

```shell
xync daemon start [OPTIONS]

Options:
  --interval SECONDS   Sync interval (overrides daemon_interval config)
  --api                Enable API server alongside daemon
  --api-port PORT      API server port (overrides api_port config)
```

Detaches from the terminal (double-fork). PID file at `{config_dir}/xync-daemon.pid`.

Supports two scheduling modes:
- **Interval-based**: sleeps `daemon_interval` seconds between cycles (default: 3600)
- **Cron-based**: uses `daemon_schedule` cron expression (e.g. `"0 */6 * * *"`)

#### `daemon stop`

```shell
xync daemon stop [--force]
```

`--force` sends SIGKILL instead of SIGTERM.

#### `daemon status`

Show whether the background sync daemon is running.

#### `daemon restart [NAME ...]`

Restart the daemon. Same options as `daemon start` plus `--force`.

---

### `xync api`

Run a REST API server for monitoring.

#### `api start`

```shell
xync api start [--port PORT]
```

Default port: `58080`. PID file at `{config_dir}/xync-api.pid`.

**Endpoints:**

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/status` | Full status of all mirrors and daemon state |
| `GET` | `/api/mirrors` | List of mirror names |
| `GET` | `/api/mirrors/{name}` | Single mirror status |
| `GET` | `/api/mirrors/{name}/size` | Mirror size info |

#### `api stop`

```shell
xync api stop [--force]
```

#### `api status`

Show whether the API server is running.

---

### `xync notify`

#### `notify test`

```shell
xync notify test [telegram|discord|all]
```

Send a test notification through configured channels.

---

### `xync config`

#### `config show`

Display current global configuration.

#### `config set KEY VALUE`

Update a global config value. See [Configuration](#configuration) for valid keys.

#### `config validate`

Validate the current configuration and report issues (checks tools, paths, Telegram/Discord config consistency).

---

## Global Option

All commands accept `--config-dir PATH` (or `xync_CONFIG_DIR` env var) to use a non-default configuration directory.

---

## Configuration

Config is stored at `~/.config/xync/config.toml`:

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
