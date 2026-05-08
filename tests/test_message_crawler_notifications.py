import unittest
from unittest.mock import Mock, patch

from src.crawler.message_crawler import MessageCrawler


class DummyDriver:
    title = "Zalo - Test User"


class MessageCrawlerNotificationTests(unittest.TestCase):
    def setUp(self):
        with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
             patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
             patch("src.crawler.message_crawler.MessageProcessor"), \
             patch("src.crawler.message_crawler.DocxHandler"), \
             patch("src.crawler.message_crawler.DatabaseManager"):
            mock_keyword_monitor.return_value.start_monitoring.return_value = None
            self.crawler = MessageCrawler(DummyDriver(), browser_navigation=Mock(), group_name="Nhóm Test")

    def test_send_notification_throttled_skips_repeat_within_cooldown(self):
        with patch("src.crawler.message_crawler.send_notification") as mock_notify, \
             patch("src.crawler.message_crawler.time.time", side_effect=[1000, 1060]):
            first = self.crawler._send_notification_throttled("recovery.needs_qr", "msg", cooldown_seconds=120)
            second = self.crawler._send_notification_throttled("recovery.needs_qr", "msg", cooldown_seconds=120)

        self.assertTrue(first)
        self.assertFalse(second)
        mock_notify.assert_called_once_with("msg")

    def test_send_notification_throttled_allows_after_cooldown(self):
        with patch("src.crawler.message_crawler.send_notification") as mock_notify, \
             patch("src.crawler.message_crawler.time.time", side_effect=[1000, 1201]):
            first = self.crawler._send_notification_throttled("recovery.no_new_data", "msg", cooldown_seconds=120)
            second = self.crawler._send_notification_throttled("recovery.no_new_data", "msg", cooldown_seconds=120)

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(mock_notify.call_count, 2)


if __name__ == "__main__":
    unittest.main()
