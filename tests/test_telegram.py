"""Tests for xsync.telegram notification module."""

from unittest.mock import MagicMock, patch

from xsync.models import SyncStatus, TelegramConfig
from xsync.telegram import (
    notify_sync_finish,
    notify_sync_progress,
    notify_sync_result,
    notify_sync_start,
    send_telegram_message,
)


class TestSendTelegramMessage:
    def test_successful_send(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        with patch(
            "xsync.telegram.httpx.post", return_value=mock_response
        ) as mock_post:
            result = send_telegram_message("token123", "chat456", "Hello!")
        assert result is True
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["chat_id"] == "chat456"
        assert kwargs["json"]["text"] == "Hello!"

    def test_http_error_returns_false(self):
        with patch("xsync.telegram.httpx.post", side_effect=Exception("network error")):
            result = send_telegram_message("token", "chat", "msg")
        assert result is False

    def test_uses_correct_api_url(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        with patch(
            "xsync.telegram.httpx.post", return_value=mock_response
        ) as mock_post:
            send_telegram_message("mytoken", "mychat", "test")
        url = mock_post.call_args[0][0]
        assert "mytoken" in url
        assert "sendMessage" in url


class TestNotifySyncResult:
    def _make_cfg(self, **kwargs) -> TelegramConfig:
        defaults = {
            "bot_token": "tok123",
            "chat_id": "chat789",
            "notify_on_success": True,
            "notify_on_failure": True,
        }
        defaults.update(kwargs)
        return TelegramConfig(**defaults)  # ty:ignore[invalid-argument-type]

    def test_skips_when_no_token(self):
        cfg = TelegramConfig(bot_token=None, chat_id="chat")
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.SUCCESS, 10.0)
        mock_send.assert_not_called()

    def test_skips_when_no_chat_id(self):
        cfg = TelegramConfig(bot_token="token", chat_id=None)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.SUCCESS, 10.0)
        mock_send.assert_not_called()

    def test_skips_success_when_notify_on_success_false(self):
        cfg = self._make_cfg(notify_on_success=False)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.SUCCESS, 10.0)
        mock_send.assert_not_called()

    def test_skips_failure_when_notify_on_failure_false(self):
        cfg = self._make_cfg(notify_on_failure=False)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.FAILED, 5.0, "exit code 1")
        mock_send.assert_not_called()

    def test_sends_success_notification(self):
        cfg = self._make_cfg()
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.SUCCESS, 12.5)
        mock_send.assert_called_once()
        text = mock_send.call_args[0][2]
        assert "ubuntu" in text
        assert "SUCCESS" in text
        assert "12.5s" in text
        assert "✅" in text

    def test_sends_failure_notification_with_error(self):
        cfg = self._make_cfg()
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_result(cfg, "debian", SyncStatus.FAILED, 3.0, "rsync failed")
        mock_send.assert_called_once()
        text = mock_send.call_args[0][2]
        assert "debian" in text
        assert "FAILED" in text
        assert "❌" in text
        assert "rsync failed" in text

    def test_sends_with_correct_credentials(self):
        cfg = self._make_cfg(bot_token="mytoken", chat_id="mychat")
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_result(cfg, "ubuntu", SyncStatus.SUCCESS, 5.0)
        mock_send.assert_called_once_with(
            "mytoken", "mychat", mock_send.call_args[0][2]
        )


class TestNotifySyncStart:
    def _make_cfg(self, **kwargs) -> TelegramConfig:
        defaults = {
            "bot_token": "tok123",
            "chat_id": "chat789",
            "notify_on_start": True,
        }
        defaults.update(kwargs)
        return TelegramConfig(**defaults)  # ty:ignore[invalid-argument-type]

    def test_skips_when_no_token(self):
        cfg = TelegramConfig(bot_token=None, chat_id="chat", notify_on_start=True)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_start(cfg, "ubuntu")
        mock_send.assert_not_called()

    def test_skips_when_no_chat_id(self):
        cfg = TelegramConfig(bot_token="token", chat_id=None, notify_on_start=True)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_start(cfg, "ubuntu")
        mock_send.assert_not_called()

    def test_skips_when_notify_on_start_false(self):
        cfg = self._make_cfg(notify_on_start=False)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_start(cfg, "ubuntu")
        mock_send.assert_not_called()

    def test_sends_start_notification(self):
        cfg = self._make_cfg()
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_start(cfg, "ubuntu")
        mock_send.assert_called_once()
        text = mock_send.call_args[0][2]
        assert "ubuntu" in text
        assert "STARTED" in text
        assert "🔄" in text


class TestNotifySyncFinish:
    def _make_cfg(self, **kwargs) -> TelegramConfig:
        defaults = {
            "bot_token": "tok123",
            "chat_id": "chat789",
            "notify_on_finish": True,
        }
        defaults.update(kwargs)
        return TelegramConfig(**defaults)  # ty:ignore[invalid-argument-type]

    def test_skips_when_no_token(self):
        cfg = TelegramConfig(bot_token=None, chat_id="chat", notify_on_finish=True)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_finish(cfg, "ubuntu", SyncStatus.SUCCESS, 5.0)
        mock_send.assert_not_called()

    def test_skips_when_notify_on_finish_false(self):
        cfg = self._make_cfg(notify_on_finish=False)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_finish(cfg, "ubuntu", SyncStatus.SUCCESS, 5.0)
        mock_send.assert_not_called()

    def test_sends_finish_notification_on_success(self):
        cfg = self._make_cfg()
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_finish(cfg, "ubuntu", SyncStatus.SUCCESS, 12.5)
        mock_send.assert_called_once()
        text = mock_send.call_args[0][2]
        assert "ubuntu" in text
        assert "FINISHED" in text
        assert "SUCCESS" in text
        assert "12.5s" in text
        assert "✅" in text

    def test_sends_finish_notification_on_failure(self):
        cfg = self._make_cfg()
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_finish(cfg, "debian", SyncStatus.FAILED, 3.0, "rsync failed")
        mock_send.assert_called_once()
        text = mock_send.call_args[0][2]
        assert "FAILED" in text
        assert "rsync failed" in text
        assert "❌" in text


class TestNotifySyncProgress:
    def _make_cfg(self, **kwargs) -> TelegramConfig:
        defaults = {
            "bot_token": "tok123",
            "chat_id": "chat789",
            "notify_on_progress": True,
        }
        defaults.update(kwargs)
        return TelegramConfig(**defaults)  # ty:ignore[invalid-argument-type]

    def test_skips_when_no_token(self):
        cfg = TelegramConfig(bot_token=None, chat_id="chat", notify_on_progress=True)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_progress(cfg, "ubuntu", 50)
        mock_send.assert_not_called()

    def test_skips_when_notify_on_progress_false(self):
        cfg = self._make_cfg(notify_on_progress=False)
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_progress(cfg, "ubuntu", 50)
        mock_send.assert_not_called()

    def test_sends_progress_notification(self):
        cfg = self._make_cfg()
        with patch("xsync.telegram.send_telegram_message") as mock_send:
            notify_sync_progress(cfg, "ubuntu", 50)
        mock_send.assert_called_once()
        text = mock_send.call_args[0][2]
        assert "ubuntu" in text
        assert "50%" in text
        assert "📊" in text
