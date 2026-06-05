import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import WebDriverException

from src.crawler.message_crawler import MessageCrawler
from src.browser.navigation import ZaloNavigator
from src.utils.status_codes import (
    GROUP_MISMATCH,
    GROUP_STATE_UNKNOWN,
    LOGIN_STATE_UNKNOWN,
    QR_VISIBLE,
    READY_IN_TARGET_GROUP,
)


class DummyDriver:
    title = "Zalo - Test User"
    current_url = "https://chat.zalo.me/mock"

    def find_elements(self, *args, **kwargs):
        return []

    def save_screenshot(self, path):
        with open(path, "wb") as f:
            f.write(b"png")
        return True


class RegressionScenarioTests(unittest.TestCase):
    def setUp(self):
        with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
             patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
             patch("src.crawler.message_crawler.MessageProcessor"), \
             patch("src.crawler.message_crawler.DocxHandler"), \
             patch("src.crawler.message_crawler.DatabaseManager"):
            mock_keyword_monitor.return_value.start_monitoring.return_value = None
            self.browser_navigation = Mock()
            self.browser_navigation.find_and_access_group.return_value = True
            self.browser_navigation.reconnect_to_group.return_value = True
            self.crawler = MessageCrawler(DummyDriver(), browser_navigation=self.browser_navigation, group_name="Nhóm Test")

    def test_regression_qr_visible_blocks_crawl_step(self):
        with patch.object(self.crawler, "check_zalo_status", return_value={
            "logged_in": False,
            "in_group": False,
            "needs_qr": True,
            "reason": QR_VISIBLE,
            "page_state": {"group_title": "", "target_group": "Nhóm Test"},
        }):
            self.assertEqual(self.crawler.crawl_step(), 0)

    def test_regression_group_mismatch_recovers_via_navigation(self):
        status = {
            "logged_in": True,
            "in_group": False,
            "needs_qr": False,
            "reason": GROUP_MISMATCH,
            "page_state": {"group_title": "Nhóm Khác", "target_group": "Nhóm Test"},
        }
        with patch.object(self.crawler, "_should_run_recovery_action", return_value=True), \
             patch.object(self.crawler, "_send_notification_throttled"), \
             patch.object(self.crawler, "capture_fail_artifact") as capture_artifact:
            result = self.crawler._recover_from_status(status, notify=True)

        self.assertTrue(result)
        self.browser_navigation.find_and_access_group.assert_called_once_with("Nhóm Test")
        capture_artifact.assert_called_once()

    def test_regression_group_state_unknown_captures_artifact(self):
        with patch.object(self.crawler, "check_zalo_status", return_value={
            "logged_in": True,
            "in_group": False,
            "needs_qr": False,
            "reason": GROUP_STATE_UNKNOWN,
            "page_state": {"group_title": "", "target_group": "Nhóm Test"},
        }), patch.object(self.crawler, "capture_fail_artifact") as capture_artifact:
            self.assertFalse(self.crawler.reconnect_to_group())

        capture_artifact.assert_called_once()

    def test_regression_login_unknown_refreshes_and_captures_artifact(self):
        status = {
            "logged_in": False,
            "in_group": False,
            "needs_qr": False,
            "reason": LOGIN_STATE_UNKNOWN,
            "page_state": {"group_title": "", "target_group": "Nhóm Test"},
        }
        with patch.object(self.crawler, "_should_run_recovery_action", return_value=True), \
             patch.object(self.crawler, "refresh_page_safely", return_value=True), \
             patch.object(self.crawler, "capture_fail_artifact") as capture_artifact:
            self.assertTrue(self.crawler._recover_from_status(status, notify=False))

        capture_artifact.assert_called_once()

    def test_regression_ready_in_target_group_passes_verify(self):
        with patch.object(self.crawler, "check_zalo_status", return_value={
            "logged_in": True,
            "in_group": True,
            "needs_qr": False,
            "reason": READY_IN_TARGET_GROUP,
            "page_state": {"group_title": "Nhóm Test", "target_group": "Nhóm Test"},
        }):
            self.assertTrue(self.crawler.reconnect_to_group())

    def test_reason_aware_notify_policy_differs_between_qr_and_group_mismatch(self):
        qr_note = self.crawler._build_recovery_notification({
            "reason": QR_VISIBLE,
            "page_state": {"group_title": "", "target_group": "Nhóm Test"},
        })
        mismatch_note = self.crawler._build_recovery_notification({
            "reason": GROUP_MISMATCH,
            "page_state": {"group_title": "Nhóm Khác", "target_group": "Nhóm Test"},
        })

        self.assertNotEqual(qr_note["key"], mismatch_note["key"])
        self.assertIn("QR", qr_note["message"])
        self.assertIn("lệch group", mismatch_note["message"])

    def test_browser_dead_recovery_artifact_path_exists_for_mismatch_verify(self):
        with patch.object(self.crawler, "check_zalo_status", return_value={
            "logged_in": True,
            "in_group": False,
            "needs_qr": False,
            "reason": GROUP_MISMATCH,
            "page_state": {"group_title": "Nhóm Khác", "target_group": "Nhóm Test"},
        }):
            self.assertFalse(self.crawler.reconnect_to_group())

    def test_navigation_search_top_results_empty_captures_artifact(self):
        navigator = ZaloNavigator(DummyDriver())
        wait_mock = Mock()
        wait_mock.until.return_value = Mock(clear=Mock(), send_keys=Mock())

        with patch("src.browser.navigation.WebDriverWait", return_value=wait_mock), \
             patch.object(navigator.driver, "find_elements", return_value=[]), \
             patch.object(navigator, "capture_fail_artifact") as capture_artifact:
            result = navigator.find_and_access_group("Nhóm Test")

        self.assertFalse(result)
        capture_artifact.assert_called_once()

    def test_navigation_browser_dead_exception_bubbles_for_recovery(self):
        navigator = ZaloNavigator(DummyDriver())
        wait_mock = Mock()
        wait_mock.until.side_effect = WebDriverException("tab crashed")

        with patch("src.browser.navigation.WebDriverWait", return_value=wait_mock):
            with self.assertRaises(WebDriverException):
                navigator.check_login_status()


if __name__ == "__main__":
    unittest.main()
