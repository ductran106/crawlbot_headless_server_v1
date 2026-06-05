import unittest
from unittest.mock import patch

from src.crawler.message_processor import MessageProcessor


class DummyDriver:
    title = "Zalo - Test User"

    def __init__(self):
        self._responses = {}

    def set_response(self, snippet, value):
        self._responses[snippet] = value

    def execute_script(self, script, *_args):
        for snippet, value in self._responses.items():
            if snippet in script:
                return value
        return ""


class DummyChatItem:
    def __init__(self, class_name="chat-item"):
        self.class_name = class_name

    def find_elements(self, *_args, **_kwargs):
        return []

    def get_attribute(self, name):
        if name == "class":
            return self.class_name
        return ""


class MessageProcessorMetadataTests(unittest.TestCase):
    def setUp(self):
        self.driver = DummyDriver()
        self.processor = MessageProcessor(self.driver, current_user_name="Test User")
        self.chat_item = DummyChatItem()

    def test_extract_attachment_metadata_includes_file_and_link(self):
        self.driver.set_response("return {", {
            "sticker": False,
            "file_name": "bao-gia.pdf",
            "file_size": "2 MB",
            "link_title": "OpenClaw Docs",
            "link_url": "https://docs.openclaw.ai",
            "video_label": "",
            "image_count": 0,
            "system_text": "",
        })

        result = self.processor.extract_attachment_metadata(self.chat_item)

        self.assertIn("[Tệp đính kèm] bao-gia.pdf (2 MB)", result)
        self.assertIn("[Liên kết] OpenClaw Docs | https://docs.openclaw.ai", result)

    def test_extract_reactions_summarizes_labels(self):
        self.driver.set_response("return values;", ["👍 2", "❤️ từ Anh"])

        result = self.processor.extract_reactions(self.chat_item)

        self.assertEqual(result, " [Reaction: 👍 2 | ❤️ từ Anh]")

    def test_extract_system_markers_normalizes_edited_and_recalled(self):
        self.driver.set_response("return out;", ["Đã chỉnh sửa", "Tin nhắn đã thu hồi"])

        result = self.processor.extract_system_markers(self.chat_item)

        self.assertIn("[Đã chỉnh sửa]", result)
        self.assertIn("[Thu hồi]", result)

    def test_process_chat_item_appends_metadata_blocks(self):
        with patch.object(self.processor, "get_sender_name", return_value="Alice"), \
             patch.object(self.processor, "extract_message_content", return_value=("Xin chào", "", "")), \
             patch.object(self.processor, "extract_quote", return_value="|||Bob: Hi|||"), \
             patch.object(self.processor, "extract_timestamp", return_value="10:30"), \
             patch.object(self.processor, "extract_attachment_metadata", return_value=" [Tệp đính kèm] bao-gia.pdf"), \
             patch.object(self.processor, "extract_reactions", return_value=" [Reaction: 👍 2]"), \
             patch.object(self.processor, "extract_system_markers", return_value=" [Đã chỉnh sửa]"):
            rendered, plain = self.processor.process_chat_item(self.chat_item)

        self.assertIn("Alice: Xin chào", rendered)
        self.assertIn("|||Bob: Hi|||", rendered)
        self.assertIn("[Tệp đính kèm] bao-gia.pdf", rendered)
        self.assertIn("[Reaction: 👍 2]", rendered)
        self.assertIn("[Đã chỉnh sửa]", rendered)
        self.assertEqual(plain, "Xin chào")


if __name__ == "__main__":
    unittest.main()
