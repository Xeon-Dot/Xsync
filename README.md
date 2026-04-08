# Xsync

> **Linux mirror synchronization and management CLI tool**
> Built with Python · [uv](https://docs.astral.sh/uv/) · [Typer](https://typer.tiangolo.com/) · [Rich](https://rich.readthedocs.io/)

---

## Features

| Feature                | Details                                                      |
| ---------------------- | ------------------------------------------------------------ |
| **rsync mirrors**      | Full rsync support with custom options & bandwidth limiting  |
| **HTTP / FTP mirrors** | wget-based mirroring for HTTP and FTP sources                |
| **Notifications**      | Alerts via Telegram bot and Discord Webhook for sync results |
| **TOML config**        | Human-readable `~/.config/xsync/config.toml`                 |
| **Sync logs**          | Per-run log files with automatic rotation                    |
| **Rich output**        | Colour-coded tables and status indicators                    |
| **Shell completion**   | bash / zsh / fish via Typer                                  |

---

## Requirements

- Python ≥ 3.11
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

```
xsync init [--config-dir PATH]
```

---

### `xsync mirror`

#### `mirror add`

```
xsync mirror add NAME URL LOCAL_PATH [OPTIONS]

Options:
  --type       rsync | http | ftp          (default: rsync)
  --description TEXT
  --bwlimit    Bandwidth limit for rsync   (e.g. "10m" for 10 MB/s)
  --rsync-opts Space-separated rsync options (overrides defaults)
```

#### `mirror remove`

```
xsync mirror remove NAME [--yes]
```

#### `mirror list`

List all configured mirrors in a table.

#### `mirror show NAME`

Show detailed information about a single mirror.

#### `mirror enable / disable NAME`

Enable or disable a mirror (disabled mirrors are skipped during sync).

---

### `xsync sync`

```
xsync sync [NAME ...] [--dry-run]
```

Sync one or all enabled mirrors. `--dry-run` prints the command without executing it.

---

### `xsync status`

```
xsync status [NAME ...]
```

Show the last sync status and timestamp for mirrors.

---

### `xsync log NAME`

```
xsync log NAME [--lines N]
```

Print the latest sync log for a mirror (default: last 50 lines).

---

### `xsync config`

#### `config show`

Display current global configuration.

#### `config set KEY VALUE`

Update a global config value.

| Key                          | Type                     | Description                                         |
| ---------------------------- | ------------------------ | --------------------------------------------------- |
| `default_rsync_options`      | string (space-separated) | Default rsync flags                                 |
| `log_dir`                    | string                   | Custom log directory                                |
| `max_log_files`              | integer                  | Max log files per mirror                            |
| `parallel_jobs`              | integer                  | Parallel mirror sync jobs                           |
| `telegram.bot_token`         | string                   | Telegram Bot API token                              |
| `telegram.chat_id`           | string                   | Telegram chat ID for notifications                  |
| `telegram.notify_on_success` | boolean                  | Send Telegram alert on sync success (default: true) |
| `telegram.notify_on_failure` | boolean                  | Send Telegram alert on sync failure (default: true) |
| `discord.webhook_url`        | string                   | Discord Webhook URL for notifications               |
| `discord.notify_on_success`  | boolean                  | Send Discord alert on sync success (default: true)  |
| `discord.notify_on_failure`  | boolean                  | Send Discord alert on sync failure (default: true)  |

---

## Global Option

All commands accept `--config-dir PATH` (or `XSYNC_CONFIG_DIR` env var) to use a non-default configuration directory.

---

## Configuration File

Config is stored at `~/.config/xsync/config.toml`:

```toml
version = 1

[global]
default_rsync_options = ["-avz", "--delete"]
log_dir = ""
max_log_files = 30
parallel_jobs = 1

[global.telegram]
bot_token = "123456:ABC-DEF"
chat_id = "-100123456"
notify_on_success = true
notify_on_failure = true

[global.discord]
webhook_url = "https://discord.com/api/webhooks/123/token"
notify_on_success = true
notify_on_failure = true

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

---

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_cli.py -v
```

---

## License

[AGPL-3.0-or-latest](LICENSE)
