from unittest.mock import Mock, patch

from src.crawler.message_crawler import MessageCrawler
from src.utils.status_codes import LOGIN_STATE_UNKNOWN, GROUP_STATE_UNKNOWN


class DummyDriver:
    title = "Zalo - Test User"

    def find_elements(self, *args, **kwargs):
        return []


def _make_crawler():
    with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
         patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
         patch("src.crawler.message_crawler.MessageProcessor"), \
         patch("src.crawler.message_crawler.DocxHandler"), \
         patch("src.crawler.message_crawler.DatabaseManager"):
        mock_keyword_monitor.return_value.start_monitoring.return_value = None
        return MessageCrawler(DummyDriver(), browser_navigation=Mock(), group_name="RETURN ROOM LỊCH")


def test_login_unknown_streak_escalates_to_browser_restart():
    crawler = _make_crawler()
    status = crawler._build_zalo_status_snapshot(
        logged_in=False,
        in_group=False,
        needs_qr=False,
        reason=LOGIN_STATE_UNKNOWN,
    )

    with patch.object(crawler, "refresh_page_safely", return_value=False) as mock_refresh, \
         patch.object(crawler, "_restart_browser_session", return_value=True) as mock_restart:
        first = crawler._recover_from_status(status, notify=False)
        second = crawler._recover_from_status(status, notify=False)

    assert first is False
    assert mock_refresh.called
    assert second is True
    mock_restart.assert_called_once()


def test_group_reconnect_fail_streak_escalates_to_browser_restart():
    crawler = _make_crawler()
    status = crawler._build_zalo_status_snapshot(
        logged_in=True,
        in_group=False,
        needs_qr=False,
        reason=GROUP_STATE_UNKNOWN,
    )

    crawler.browser_navigation.find_and_access_group.return_value = False

    with patch.object(crawler, "_should_run_recovery_action", return_value=True), \
         patch.object(crawler, "_restart_browser_session", return_value=True) as mock_restart:
        first = crawler._recover_from_status(status, notify=False)
        second = crawler._recover_from_status(status, notify=False)

    assert first is False
    assert second is True
    mock_restart.assert_called_once()
