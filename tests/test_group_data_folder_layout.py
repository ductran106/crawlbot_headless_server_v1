import os
from unittest.mock import Mock, patch

from src.crawler.message_crawler import MessageCrawler


class DummyDriver:
    title = "Zalo - Test User"

    def find_elements(self, *args, **kwargs):
        return []


def _make_crawler(group_name="RETURN ROOM LỊCH", data_folder="/tmp/crawlbot-data"):
    with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
         patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
         patch("src.crawler.message_crawler.MessageProcessor"), \
         patch("src.crawler.message_crawler.DocxHandler"), \
         patch("src.crawler.message_crawler.DatabaseManager"):
        mock_keyword_monitor.return_value.start_monitoring.return_value = None
        return MessageCrawler(DummyDriver(), browser_navigation=Mock(), group_name=group_name, data_folder=data_folder)


def test_group_data_folder_is_nested_per_room_under_base_folder():
    crawler = _make_crawler(data_folder="/tmp/crawlbot-data")
    assert crawler.group_slug == "return_room_lich"
    assert crawler.data_folder == "/tmp/crawlbot-data/return_room_lich"


def test_group_data_folder_is_not_double_nested_if_already_room_specific():
    crawler = _make_crawler(data_folder="/tmp/crawlbot-data/return_room_lich")
    assert crawler.data_folder == os.path.normpath("/tmp/crawlbot-data/return_room_lich")
