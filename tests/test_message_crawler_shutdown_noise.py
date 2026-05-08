import unittest
from unittest.mock import Mock, patch

from src.crawler.message_crawler import MessageCrawler


class DummyDriver:
    title = "Zalo - Test User"

    def find_elements(self, *args, **kwargs):
        return []


class MessageCrawlerShutdownNoiseTests(unittest.TestCase):
    def setUp(self):
        with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
             patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
             patch("src.crawler.message_crawler.MessageProcessor"), \
             patch("src.crawler.message_crawler.DocxHandler"), \
             patch("src.crawler.message_crawler.DatabaseManager"):
            mock_keyword_monitor.return_value.start_monitoring.return_value = None
            self.browser_navigation = Mock()
            self.crawler = MessageCrawler(DummyDriver(), browser_navigation=self.browser_navigation, group_name="Nhóm Test")

    def test_expected_shutdown_webdriver_error_detected_from_stop_flag(self):
        self.crawler.external_stop_flag = lambda: True
        error = Exception("HTTPConnectionPool(host='localhost', port=12345): Failed to establish a new connection: [Errno 111] Connection refused")

        self.assertTrue(self.crawler._is_expected_shutdown_webdriver_error(error))

    def test_non_shutdown_error_is_not_suppressed(self):
        self.crawler.external_stop_flag = lambda: False
        error = Exception("some unexpected parser failure")

        self.assertFalse(self.crawler._is_expected_shutdown_webdriver_error(error))


if __name__ == "__main__":
    unittest.main()
