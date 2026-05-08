import unittest
from unittest.mock import Mock, patch

from src.crawler.message_crawler import MessageCrawler
from src.utils.observability import format_event_log


class DummyDriver:
    title = "Zalo - Test User"

    def find_elements(self, *args, **kwargs):
        raise Exception("HTTPConnectionPool(host='localhost', port=123): Failed to establish a new connection: [Errno 111] Connection refused")


class CrawlbotShutdownFinalNoiseTests(unittest.TestCase):
    def setUp(self):
        with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
             patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
             patch("src.crawler.message_crawler.MessageProcessor"), \
             patch("src.crawler.message_crawler.DocxHandler"), \
             patch("src.crawler.message_crawler.DatabaseManager"):
            mock_keyword_monitor.return_value.start_monitoring.return_value = None
            self.browser_navigation = Mock()
            self.crawler = MessageCrawler(DummyDriver(), browser_navigation=self.browser_navigation, group_name="Nhóm Test")

    def test_save_document_missing_autosave_is_quiet_on_shutdown(self):
        with patch("src.crawler.message_crawler.is_terminating", return_value=True), \
             patch("src.crawler.message_crawler.log") as mock_log:
            result = self.crawler.save_document(__import__("datetime").datetime(2026, 3, 18, 11, 20, 0))

        self.assertIsNone(result)
        self.assertTrue(any(call.kwargs.get("level") for call in mock_log.call_args_list))

    def test_wait_for_messages_stable_returns_false_for_shutdown_browser_error(self):
        self.crawler.external_stop_flag = lambda: True
        with patch("src.crawler.message_crawler.log"):
            result = self.crawler.wait_for_messages_stable(timeout=0.1)
        self.assertFalse(result)

    def test_format_event_log_keeps_fixed_prefix_for_save_document(self):
        line = format_event_log(
            "save_document_result",
            payload={"success": True, "message_count": 12},
            prefix="SAVE_DOCUMENT_RESULT",
        )
        self.assertEqual(
            line,
            'SAVE_DOCUMENT_RESULT {"event":"save_document_result","message_count":12,"success":true}',
        )


if __name__ == "__main__":
    unittest.main()
