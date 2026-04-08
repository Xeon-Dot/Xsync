"""Tests for xsync.discord notification module."""

from unittest.mock import MagicMock, patch

from xsync.discord import (
    notify_sync_finish,
    notify_sync_progress,
    notify_sync_result,
    notify_sync_start,
    send_discord_message,
)
from xsync.models import DiscordConfig, SyncStatus


class TestSendDiscordMessage:
    def test_successful_send(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        with patch("xsync.discord.httpx.post", return_value=mock_response) as mock_post:
            result = send_discord_message(
                "https://discord.com/api/webhooks/123/token", "Hello!"
            )
        assert result is True
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["content"] == "Hello!"

    def test_http_error_returns_false(self):
        with patch("xsync.discord.httpx.post", side_effect=Exception("network error")):
            result = send_discord_message(
                "https://discord.com/api/webhooks/123/token", "msg"
            )
        assert result is False

    def test_uses_provided_webhook_url(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        url = "https://discord.com/api/webhooks/999/mytoken"
        with patch("xsync.discord.httpx.post", return_value=mock_response) as mock_post:
            send_discord_message(url, "test")
        called_url = mock_post.call_args[0][0]
        assert called_url == url


class TestNotifySyncResult:
    def _make_cfg(self, **kwargs) -> DiscordConfig:
        defaults = {
            "webhook_url": "https://discord.com/api/webhooks/123/token",
            "notify_on_success": True,
            "notify_on_failure": True,
        }
        defaults.update(kwargs)
        return DiscordConfig(**defaults)  # ty:ignore[invalid-argument-type]

    def test_skips_when_no_webhook_url(self):
        cfg = DiscordConfig(webhook_url=None)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.SUCCESS, 10.0)
        mock_send.assert_not_called()

    def test_skips_success_when_notify_on_success_false(self):
        cfg = self._make_cfg(notify_on_success=False)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.SUCCESS, 10.0)
        mock_send.assert_not_called()

    def test_skips_failure_when_notify_on_failure_false(self):
        cfg = self._make_cfg(notify_on_failure=False)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.FAILED, 5.0, "exit code 1")
        mock_send.assert_not_called()

    def test_sends_success_notification(self):
        cfg = self._make_cfg()
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.SUCCESS, 12.5)
        mock_send.assert_called_once()
        content = mock_send.call_args[0][1]
        assert "ubuntu" in content
        assert "SUCCESS" in content
        assert "12.5s" in content
        assert "✅" in content

    def test_sends_failure_notification_with_error(self):
        cfg = self._make_cfg()
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_result(cfg, "debian", SyncStatus.FAILED, 3.0, "rsync failed")
        mock_send.assert_called_once()
        content = mock_send.call_args[0][1]
        assert "debian" in content
        assert "FAILED" in content
        assert "❌" in content
        assert "rsync failed" in content

    def test_sends_with_correct_webhook_url(self):
        url = "https://discord.com/api/webhooks/123/token"
        cfg = self._make_cfg(webhook_url=url)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.SUCCESS, 5.0)
        mock_send.assert_called_once_with(url, mock_send.call_args[0][1])


class TestNotifySyncStart:
    def _make_cfg(self, **kwargs) -> DiscordConfig:
        defaults = {
            "webhook_url": "https://discord.com/api/webhooks/123/token",
            "notify_on_start": True,
        }
        defaults.update(kwargs)
        return DiscordConfig(**defaults)  # ty:ignore[invalid-argument-type]

    def test_skips_when_no_webhook_url(self):
        cfg = DiscordConfig(webhook_url=None, notify_on_start=True)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_start(cfg, "ubuntu")
        mock_send.assert_not_called()

    def test_skips_when_notify_on_start_false(self):
        cfg = self._make_cfg(notify_on_start=False)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_start(cfg, "ubuntu")
        mock_send.assert_not_called()

    def test_sends_start_notification(self):
        cfg = self._make_cfg()
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_start(cfg, "ubuntu")
        mock_send.assert_called_once()
        content = mock_send.call_args[0][1]
        assert "ubuntu" in content
        assert "STARTED" in content
        assert "🔄" in content


class TestNotifySyncFinish:
    def _make_cfg(self, **kwargs) -> DiscordConfig:
        defaults = {
            "webhook_url": "https://discord.com/api/webhooks/123/token",
            "notify_on_finish": True,
        }
        defaults.update(kwargs)
        return DiscordConfig(**defaults)  # ty:ignore[invalid-argument-type]

    def test_skips_when_no_webhook_url(self):
        cfg = DiscordConfig(webhook_url=None, notify_on_finish=True)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_finish(cfg, "ubuntu", SyncStatus.SUCCESS, 5.0)
        mock_send.assert_not_called()

    def test_skips_when_notify_on_finish_false(self):
        cfg = self._make_cfg(notify_on_finish=False)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_finish(cfg, "ubuntu", SyncStatus.SUCCESS, 5.0)
        mock_send.assert_not_called()

    def test_sends_finish_notification_on_success(self):
        cfg = self._make_cfg()
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_finish(cfg, "ubuntu", SyncStatus.SUCCESS, 12.5)
        mock_send.assert_called_once()
        content = mock_send.call_args[0][1]
        assert "ubuntu" in content
        assert "FINISHED" in content
        assert "SUCCESS" in content
        assert "12.5s" in content
        assert "✅" in content

    def test_sends_finish_notification_on_failure(self):
        cfg = self._make_cfg()
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_finish(cfg, "debian", SyncStatus.FAILED, 3.0, "rsync failed")
        mock_send.assert_called_once()
        content = mock_send.call_args[0][1]
        assert "FAILED" in content
        assert "rsync failed" in content
        assert "❌" in content


class TestNotifySyncProgress:
    def _make_cfg(self, **kwargs) -> DiscordConfig:
        defaults = {
            "webhook_url": "https://discord.com/api/webhooks/123/token",
            "notify_on_progress": True,
        }
        defaults.update(kwargs)
        return DiscordConfig(**defaults)  # ty:ignore[invalid-argument-type]

    def test_skips_when_no_webhook_url(self):
        cfg = DiscordConfig(webhook_url=None, notify_on_progress=True)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_progress(cfg, "ubuntu", 50)
        mock_send.assert_not_called()

    def test_skips_when_notify_on_progress_false(self):
        cfg = self._make_cfg(notify_on_progress=False)
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_progress(cfg, "ubuntu", 50)
        mock_send.assert_not_called()

    def test_sends_progress_notification(self):
        cfg = self._make_cfg()
        with patch("xsync.discord.send_discord_message") as mock_send:
            notify_sync_progress(cfg, "ubuntu", 70)
        mock_send.assert_called_once()
        content = mock_send.call_args[0][1]
        assert "ubuntu" in content
        assert "70%" in content
        assert "📊" in content
