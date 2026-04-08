"""Tests for the Typer CLI (xsync.main)."""

from pathlib import Path

from typer.testing import CliRunner

from xsync.main import app

runner = CliRunner()


def make_cfg_opt(tmp_path: Path) -> list[str]:
    return ["--config-dir", str(tmp_path)]


class TestInit:
    def test_init_creates_config(self, tmp_path):
        result = runner.invoke(app, ["init"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0, result.output
        assert (tmp_path / "config.toml").exists()

    def test_init_idempotent(self, tmp_path):
        runner.invoke(app, ["init"] + make_cfg_opt(tmp_path))
        result = runner.invoke(app, ["init"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "already exists" in result.output


class TestMirrorAdd:
    def test_add_rsync_mirror(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "mirror",
                "add",
                "ubuntu",
                "rsync://mirror.example.com/ubuntu",
                "/srv/mirrors/ubuntu",
            ]
            + make_cfg_opt(tmp_path),
        )
        assert result.exit_code == 0, result.output
        assert "ubuntu" in result.output

    def test_add_http_mirror(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "mirror",
                "add",
                "debian",
                "http://ftp.debian.org/debian",
                "/srv/mirrors/debian",
                "--type",
                "http",
            ]
            + make_cfg_opt(tmp_path),
        )
        assert result.exit_code == 0, result.output

    def test_duplicate_mirror_fails(self, tmp_path):
        args = [
            "mirror",
            "add",
            "ubuntu",
            "rsync://mirror.example.com/ubuntu",
            "/srv/mirrors/ubuntu",
        ] + make_cfg_opt(tmp_path)
        runner.invoke(app, args)
        result = runner.invoke(app, args)
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_add_invalid_url_fails(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "mirror",
                "add",
                "bad",
                "noscheme.example.com/path",
                "/srv/mirrors/bad",
            ]
            + make_cfg_opt(tmp_path),
        )
        assert result.exit_code != 0

    def test_add_invalid_name_fails(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "mirror",
                "add",
                "bad name!",
                "rsync://mirror.example.com/path",
                "/srv/mirrors/bad",
            ]
            + make_cfg_opt(tmp_path),
        )
        assert result.exit_code != 0


class TestMirrorList:
    def test_list_empty(self, tmp_path):
        result = runner.invoke(app, ["mirror", "list"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "No mirrors" in result.output

    def test_list_shows_mirror(self, tmp_path):
        runner.invoke(
            app,
            [
                "mirror",
                "add",
                "ubuntu",
                "rsync://mirror.example.com/ubuntu",
                "/srv/mirrors/ubuntu",
            ]
            + make_cfg_opt(tmp_path),
        )
        result = runner.invoke(app, ["mirror", "list"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "ubuntu" in result.output


class TestMirrorRemove:
    def test_remove_existing(self, tmp_path):
        runner.invoke(
            app,
            [
                "mirror",
                "add",
                "ubuntu",
                "rsync://mirror.example.com/ubuntu",
                "/srv/mirrors/ubuntu",
            ]
            + make_cfg_opt(tmp_path),
        )
        result = runner.invoke(
            app, ["mirror", "remove", "ubuntu", "--yes"] + make_cfg_opt(tmp_path)
        )
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_remove_missing_fails(self, tmp_path):
        result = runner.invoke(
            app, ["mirror", "remove", "nonexistent", "--yes"] + make_cfg_opt(tmp_path)
        )
        assert result.exit_code != 0


class TestMirrorShow:
    def test_show_existing(self, tmp_path):
        runner.invoke(
            app,
            [
                "mirror",
                "add",
                "ubuntu",
                "rsync://mirror.example.com/ubuntu",
                "/srv/mirrors/ubuntu",
                "--description",
                "Ubuntu LTS mirror",
            ]
            + make_cfg_opt(tmp_path),
        )
        result = runner.invoke(
            app, ["mirror", "show", "ubuntu"] + make_cfg_opt(tmp_path)
        )
        assert result.exit_code == 0
        assert "ubuntu" in result.output
        assert "Ubuntu LTS mirror" in result.output

    def test_show_missing_fails(self, tmp_path):
        result = runner.invoke(
            app, ["mirror", "show", "nonexistent"] + make_cfg_opt(tmp_path)
        )
        assert result.exit_code != 0


class TestMirrorEnableDisable:
    def _add_mirror(self, tmp_path):
        runner.invoke(
            app,
            [
                "mirror",
                "add",
                "ubuntu",
                "rsync://mirror.example.com/ubuntu",
                "/srv/mirrors/ubuntu",
            ]
            + make_cfg_opt(tmp_path),
        )

    def test_disable_mirror(self, tmp_path):
        self._add_mirror(tmp_path)
        result = runner.invoke(
            app, ["mirror", "disable", "ubuntu"] + make_cfg_opt(tmp_path)
        )
        assert result.exit_code == 0
        assert "disabled" in result.output

    def test_enable_mirror(self, tmp_path):
        self._add_mirror(tmp_path)
        runner.invoke(app, ["mirror", "disable", "ubuntu"] + make_cfg_opt(tmp_path))
        result = runner.invoke(
            app, ["mirror", "enable", "ubuntu"] + make_cfg_opt(tmp_path)
        )
        assert result.exit_code == 0
        assert "enabled" in result.output


class TestStatus:
    def test_status_no_mirrors(self, tmp_path):
        result = runner.invoke(app, ["status"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "No mirrors" in result.output

    def test_status_shows_mirror(self, tmp_path):
        runner.invoke(
            app,
            [
                "mirror",
                "add",
                "ubuntu",
                "rsync://mirror.example.com/ubuntu",
                "/srv/mirrors/ubuntu",
            ]
            + make_cfg_opt(tmp_path),
        )
        result = runner.invoke(app, ["status"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "ubuntu" in result.output


class TestConfigCommands:
    def test_config_show(self, tmp_path):
        result = runner.invoke(app, ["config", "show"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "max_log_files" in result.output

    def test_config_show_includes_telegram(self, tmp_path):
        result = runner.invoke(app, ["config", "show"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "telegram" in result.output

    def test_config_set_max_log_files(self, tmp_path):
        result = runner.invoke(
            app, ["config", "set", "max_log_files", "20"] + make_cfg_opt(tmp_path)
        )
        assert result.exit_code == 0
        assert "max_log_files" in result.output

    def test_config_set_invalid_key(self, tmp_path):
        result = runner.invoke(
            app, ["config", "set", "nonexistent_key", "value"] + make_cfg_opt(tmp_path)
        )
        assert result.exit_code != 0

    def test_config_set_invalid_int(self, tmp_path):
        result = runner.invoke(
            app,
            ["config", "set", "max_log_files", "not_a_number"] + make_cfg_opt(tmp_path),
        )
        assert result.exit_code != 0

    def test_config_set_telegram_bot_token(self, tmp_path):
        result = runner.invoke(
            app,
            ["config", "set", "telegram.bot_token", "123456:ABC-DEF"]
            + make_cfg_opt(tmp_path),
        )
        assert result.exit_code == 0
        assert "telegram.bot_token" in result.output

    def test_config_set_telegram_chat_id(self, tmp_path):
        result = runner.invoke(
            app,
            ["config", "set", "telegram.chat_id", "100123456"] + make_cfg_opt(tmp_path),
        )
        assert result.exit_code == 0
        assert "telegram.chat_id" in result.output

    def test_config_set_telegram_notify_on_success(self, tmp_path):
        result = runner.invoke(
            app,
            ["config", "set", "telegram.notify_on_success", "false"]
            + make_cfg_opt(tmp_path),
        )
        assert result.exit_code == 0

    def test_config_set_telegram_notify_on_failure(self, tmp_path):
        result = runner.invoke(
            app,
            ["config", "set", "telegram.notify_on_failure", "true"]
            + make_cfg_opt(tmp_path),
        )
        assert result.exit_code == 0

    def test_config_set_telegram_bool_invalid(self, tmp_path):
        result = runner.invoke(
            app,
            ["config", "set", "telegram.notify_on_success", "maybe"]
            + make_cfg_opt(tmp_path),
        )
        assert result.exit_code != 0


class TestSync:
    def test_sync_no_mirrors(self, tmp_path):
        result = runner.invoke(app, ["sync"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "No mirrors" in result.output

    def test_sync_dry_run(self, tmp_path):
        runner.invoke(
            app,
            [
                "mirror",
                "add",
                "ubuntu",
                "rsync://mirror.example.com/ubuntu",
                "/srv/mirrors/ubuntu",
            ]
            + make_cfg_opt(tmp_path),
        )
        result = runner.invoke(app, ["sync", "--dry-run"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0

    def test_sync_missing_mirror_fails(self, tmp_path):
        result = runner.invoke(app, ["sync", "nonexistent"] + make_cfg_opt(tmp_path))
        assert result.exit_code != 0


class TestDaemonCommands:
    """Tests for xsync daemon start / stop / status."""

    def test_daemon_status_not_running(self, tmp_path):
        result = runner.invoke(app, ["daemon", "status"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "not running" in result.output

    def test_daemon_stop_not_running(self, tmp_path):
        result = runner.invoke(app, ["daemon", "stop"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "not running" in result.output

    def test_daemon_status_running(self, tmp_path, mocker):
        mocker.patch("xsync.daemon.is_running", return_value=True)
        mocker.patch("xsync.daemon.read_pid", return_value=12345)
        result = runner.invoke(app, ["daemon", "status"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "12345" in result.output

    def test_daemon_stop_sends_sigterm(self, tmp_path, mocker):
        mocker.patch("xsync.daemon.is_running", return_value=True)
        mocker.patch("xsync.daemon.read_pid", return_value=12345)
        mock_stop = mocker.patch("xsync.daemon.stop_daemon", return_value=True)
        result = runner.invoke(app, ["daemon", "stop"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        assert "12345" in result.output
        mock_stop.assert_called_once()

    def test_daemon_start_already_running(self, tmp_path, mocker):
        mocker.patch("xsync.daemon.is_running", return_value=True)
        mocker.patch("xsync.daemon.read_pid", return_value=12345)
        result = runner.invoke(app, ["daemon", "start"] + make_cfg_opt(tmp_path))
        assert result.exit_code != 0
        assert "already running" in result.output

    def test_daemon_start_forks(self, tmp_path, mocker):
        mocker.patch("xsync.daemon.is_running", return_value=False)
        mock_daemonize = mocker.patch("xsync.daemon.daemonize")
        mock_loop = mocker.patch("xsync.daemon.run_daemon_loop")
        result = runner.invoke(app, ["daemon", "start"] + make_cfg_opt(tmp_path))
        assert result.exit_code == 0
        mock_daemonize.assert_called_once()
        mock_loop.assert_called_once()

    def test_daemon_start_custom_interval(self, tmp_path, mocker):
        mocker.patch("xsync.daemon.is_running", return_value=False)
        mock_daemonize = mocker.patch("xsync.daemon.daemonize")
        mock_loop = mocker.patch("xsync.daemon.run_daemon_loop")
        result = runner.invoke(
            app,
            ["daemon", "start", "--interval", "1800"] + make_cfg_opt(tmp_path),
        )
        assert result.exit_code == 0
        _cfg_dir, _names, interval, _api_enabled, _api_port = mock_loop.call_args[0]
        assert interval == 1800

    def test_daemon_start_uses_config_interval(self, tmp_path, mocker):
        runner.invoke(
            app,
            ["config", "set", "daemon_interval", "7200"] + make_cfg_opt(tmp_path),
        )
        mocker.patch("xsync.daemon.is_running", return_value=False)
        mocker.patch("xsync.daemon.daemonize")
        mock_loop = mocker.patch("xsync.daemon.run_daemon_loop")
        runner.invoke(app, ["daemon", "start"] + make_cfg_opt(tmp_path))
        _cfg_dir, _names, interval, _api_enabled, _api_port = mock_loop.call_args[0]
        assert interval == 7200

    def test_daemon_stop_sends_sigkill_with_force(self, tmp_path, mocker):
        mocker.patch("xsync.daemon.is_running", return_value=True)
        mocker.patch("xsync.daemon.read_pid", return_value=12345)
        mock_stop = mocker.patch("xsync.daemon.stop_daemon", return_value=True)
        result = runner.invoke(
            app, ["daemon", "stop", "--force"] + make_cfg_opt(tmp_path)
        )
        assert result.exit_code == 0
        assert "SIGKILL" in result.output
        mock_stop.assert_called_once_with(mocker.ANY, True)
