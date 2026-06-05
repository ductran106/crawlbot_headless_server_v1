import unittest
from unittest.mock import Mock, patch

from src.crawler.message_crawler import MessageCrawler


class DummyDriver:
    title = "Zalo - Test User"


class MessageCrawlerRecoveryActionCooldownTests(unittest.TestCase):
    def setUp(self):
        with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
             patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
             patch("src.crawler.message_crawler.MessageProcessor"), \
             patch("src.crawler.message_crawler.DocxHandler"), \
             patch("src.crawler.message_crawler.DatabaseManager"):
            mock_keyword_monitor.return_value.start_monitoring.return_value = None
            self.crawler = MessageCrawler(DummyDriver(), browser_navigation=Mock(), group_name="Nhóm Test")

    def test_should_run_recovery_action_skips_repeat_within_cooldown(self):
        with patch("src.crawler.message_crawler.time.time", side_effect=[1000, 1060]):
            first = self.crawler._should_run_recovery_action("action.needs_qr", cooldown_seconds=120)
            second = self.crawler._should_run_recovery_action("action.needs_qr", cooldown_seconds=120)

        self.assertTrue(first)
        self.assertFalse(second)

    def test_should_run_recovery_action_allows_after_cooldown(self):
        with patch("src.crawler.message_crawler.time.time", side_effect=[1000, 1121]):
            first = self.crawler._should_run_recovery_action("action.out_of_group", cooldown_seconds=120)
            second = self.crawler._should_run_recovery_action("action.out_of_group", cooldown_seconds=120)

        self.assertTrue(first)
        self.assertTrue(second)


if __name__ == "__main__":
    unittest.main()
