from unittest.mock import patch

from src.notification import telegram as telegram_mod


def test_send_alert_returns_false_when_telegram_not_configured():
    telegram_mod._TELEGRAM_CONFIG_WARNED.clear()
    with patch.object(telegram_mod, "TELEGRAM_TOKEN", ""), \
         patch.object(telegram_mod, "ALERT_CHAT_ID", None):
        assert telegram_mod.send_alert("hello") is False


def test_send_alert_config_warning_is_throttled_per_context():
    telegram_mod._TELEGRAM_CONFIG_WARNED.clear()
    with patch.object(telegram_mod, "TELEGRAM_TOKEN", ""), \
         patch.object(telegram_mod, "ALERT_CHAT_ID", None), \
         patch.object(telegram_mod, "log") as mock_log:
        telegram_mod.send_alert("hello")
        telegram_mod.send_alert("hello again")

    warning_messages = [call.args[0] for call in mock_log.call_args_list if call.kwargs.get("level")]
    assert sum("Bỏ gửi telegram_alert: thiếu TELEGRAM_TOKEN" in msg for msg in warning_messages) == 1
