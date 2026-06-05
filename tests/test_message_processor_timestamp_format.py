import unittest
from datetime import datetime
from unittest.mock import patch

from src.crawler.message_processor import MessageProcessor


class DummyDriver:
    title = "Zalo - Test User"

    def __init__(self):
        self.responses = {}

    def set_response(self, snippet, value):
        self.responses[snippet] = value

    def execute_script(self, script, *_args, **_kwargs):
        for snippet, value in self.responses.items():
            if snippet in script:
                return value
        return ""


class DummyChatItem:
    def find_elements(self, *_args, **_kwargs):
        return []

    def get_attribute(self, _name):
        return ""


class MessageProcessorTimestampFormatTests(unittest.TestCase):
    def setUp(self):
        self.processor = MessageProcessor(DummyDriver(), current_user_name="Test User")
        self.chat_item = DummyChatItem()

    def test_format_render_timestamp_keeps_hour_minute_without_fake_seconds(self):
        rendered = self.processor._format_render_timestamp("18/03/2026", "10:56")
        self.assertEqual(rendered, "*[18/03/2026 10:56]")

    def test_extract_timestamp_prefers_exact_qid_time_when_available(self):
        self.processor.driver.set_response("getAttribute('data-qid')", "7633765874436@1773834283675_6457667131780776797_g1332908445374310844")
        extracted = self.processor.extract_timestamp(self.chat_item)
        self.assertEqual(extracted, "18:44:43")

    def test_build_timestamp_metadata_falls_back_to_ingested_at(self):
        fake_now = datetime(2026, 3, 18, 10, 56, 41)
        meta = self.processor._build_timestamp_metadata("10:56", ingested_at=fake_now)
        self.assertEqual(meta["render_time"], "10:56:41")
        self.assertEqual(meta["timestamp_source"], "ingested_fallback")

    def test_process_chat_item_does_not_append_placeholder_seconds(self):
        fake_now = datetime(2026, 3, 18, 10, 56, 0)
        with patch("src.crawler.message_processor.datetime") as mock_datetime, \
             patch.object(self.processor, "get_sender_name", return_value="Alice"), \
             patch.object(self.processor, "extract_message_content", return_value=("Xin chào", "", "")), \
             patch.object(self.processor, "extract_quote", return_value=""), \
             patch.object(self.processor, "extract_timestamp", return_value="10:56"), \
             patch.object(self.processor, "extract_attachment_metadata", return_value=""), \
             patch.object(self.processor, "extract_reactions", return_value=""), \
             patch.object(self.processor, "extract_system_markers", return_value=""):
            mock_datetime.now.return_value = fake_now
            rendered, _ = self.processor.process_chat_item(self.chat_item)

        self.assertIn("*[18/03/2026 10:56:00] Alice: Xin chào", rendered)
        self.assertNotIn(":ss]", rendered)
        self.assertNotIn("hh:mm:ss", rendered)


if __name__ == "__main__":
    unittest.main()
