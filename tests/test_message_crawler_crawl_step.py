import unittest
from unittest.mock import Mock, patch

from src.crawler.message_crawler import MessageCrawler


class DummyDriver:
    title = "Zalo - Test User"

    def find_elements(self, *args, **kwargs):
        return []


class MessageCrawlerCrawlStepTests(unittest.TestCase):
    def setUp(self):
        with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
             patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
             patch("src.crawler.message_crawler.MessageProcessor"), \
             patch("src.crawler.message_crawler.DocxHandler"), \
             patch("src.crawler.message_crawler.DatabaseManager"):
            mock_keyword_monitor.return_value.start_monitoring.return_value = None
            self.browser_navigation = Mock()
            self.browser_navigation.find_and_access_group.return_value = True
            self.crawler = MessageCrawler(DummyDriver(), browser_navigation=self.browser_navigation, group_name="Nhóm Test")

    def test_crawl_step_returns_zero_and_logs_when_logged_out(self):
        with patch.object(self.crawler, "check_zalo_status", return_value={
            "logged_in": False,
            "in_group": False,
            "needs_qr": True,
            "reason": "qr-visible",
            "page_state": {"group_title": "", "target_group": "Nhóm Test"},
        }), patch.object(self.crawler, "_log_status_transition") as log_transition:
            result = self.crawler.crawl_step()

        self.assertEqual(result, 0)
        self.browser_navigation.find_and_access_group.assert_not_called()
        log_transition.assert_called_once()

    def test_crawl_step_verifies_reconnect_result_before_processing(self):
        statuses = [
            {
                "logged_in": True,
                "in_group": False,
                "needs_qr": False,
                "reason": "group-mismatch",
                "page_state": {"group_title": "Nhóm Khác", "target_group": "Nhóm Test"},
            },
            {
                "logged_in": True,
                "in_group": True,
                "needs_qr": False,
                "reason": "ready-in-target-group",
                "page_state": {"group_title": "Nhóm Test", "target_group": "Nhóm Test"},
            },
        ]
        with patch.object(self.crawler, "check_zalo_status", side_effect=statuses), \
             patch.object(self.crawler, "_log_status_transition") as log_transition, \
             patch.object(self.crawler, "wait_for_messages_stable", return_value=True), \
             patch.object(self.crawler, "scroll_for_messages", return_value=True):
            result = self.crawler.crawl_step()

        self.assertEqual(result, 0)
        self.browser_navigation.find_and_access_group.assert_called_once_with("Nhóm Test")
        self.assertEqual(log_transition.call_count, 2)


if __name__ == "__main__":
    unittest.main()
