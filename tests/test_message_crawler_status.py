import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException, WebDriverException

from src.crawler.message_crawler import MessageCrawler


class DummyDriver:
    title = "Zalo - Test User"


class MessageCrawlerStatusTests(unittest.TestCase):
    def setUp(self):
        with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
             patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
             patch("src.crawler.message_crawler.MessageProcessor"), \
             patch("src.crawler.message_crawler.DocxHandler"), \
             patch("src.crawler.message_crawler.DatabaseManager"):
            mock_keyword_monitor.return_value.start_monitoring.return_value = None
            self.crawler = MessageCrawler(DummyDriver(), browser_navigation=Mock(), group_name="Nhóm Test")

    def test_check_zalo_status_detects_needs_qr(self):
        search_wait = Mock()
        search_wait.until.side_effect = TimeoutException("search not ready")
        qr_wait = Mock()
        qr_wait.until.return_value = object()

        with patch("src.crawler.message_crawler.WebDriverWait", side_effect=[search_wait, qr_wait]):
            status = self.crawler.check_zalo_status()

        self.assertEqual(status["logged_in"], False)
        self.assertEqual(status["in_group"], False)
        self.assertEqual(status["needs_qr"], True)
        self.assertEqual(status["reason"], "qr-visible")

    def test_check_zalo_status_detects_logged_in_and_in_group(self):
        search_wait = Mock()
        search_wait.until.return_value = object()
        group_el = Mock()
        group_el.text = "Nhóm Test Chính"
        group_wait = Mock()
        group_wait.until.return_value = group_el

        with patch("src.crawler.message_crawler.WebDriverWait", side_effect=[search_wait, group_wait]):
            status = self.crawler.check_zalo_status()

        self.assertEqual(status["logged_in"], True)
        self.assertEqual(status["in_group"], True)
        self.assertEqual(status["needs_qr"], False)
        self.assertEqual(status["reason"], "ready-in-target-group")
        self.assertEqual(status["page_state"]["group_title"], "Nhóm Test Chính")

    def test_check_zalo_status_detects_group_mismatch(self):
        search_wait = Mock()
        search_wait.until.return_value = object()
        group_el = Mock()
        group_el.text = "Nhóm Khác"
        group_wait = Mock()
        group_wait.until.return_value = group_el

        with patch("src.crawler.message_crawler.WebDriverWait", side_effect=[search_wait, group_wait]):
            status = self.crawler.check_zalo_status()

        self.assertEqual(status["logged_in"], True)
        self.assertEqual(status["in_group"], False)
        self.assertEqual(status["needs_qr"], False)
        self.assertEqual(status["reason"], "group-mismatch")
        self.assertEqual(status["page_state"]["group_title"], "Nhóm Khác")

    def test_check_zalo_status_detects_unknown_login_state(self):
        search_wait = Mock()
        search_wait.until.side_effect = TimeoutException("search not ready")
        qr_wait = Mock()
        qr_wait.until.side_effect = TimeoutException("qr not visible")

        with patch("src.crawler.message_crawler.WebDriverWait", side_effect=[search_wait, qr_wait]):
            status = self.crawler.check_zalo_status()

        self.assertEqual(status["logged_in"], False)
        self.assertEqual(status["in_group"], False)
        self.assertEqual(status["needs_qr"], False)
        self.assertEqual(status["reason"], "login-state-unknown")

    def test_check_zalo_status_reraises_browser_dead_error(self):
        search_wait = Mock()
        search_wait.until.side_effect = WebDriverException("tab crashed")

        with patch("src.crawler.message_crawler.WebDriverWait", return_value=search_wait):
            with self.assertRaises(WebDriverException):
                self.crawler.check_zalo_status()


if __name__ == "__main__":
    unittest.main()
