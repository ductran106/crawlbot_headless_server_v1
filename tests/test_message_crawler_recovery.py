import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from src.crawler.message_crawler import MessageCrawler
from src.utils.config import COMPUTER_NAME


class DummyDriver:
    title = "Zalo - Test User"


class MessageCrawlerRecoveryTests(unittest.TestCase):
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

    def test_recover_from_status_group_mismatch_uses_specific_action_and_navigation(self):
        status = {
            "logged_in": True,
            "in_group": False,
            "needs_qr": False,
            "reason": "group-mismatch",
            "page_state": {"group_title": "Nhóm Khác", "target_group": "Nhóm Test"},
        }

        with patch.object(self.crawler, "_should_run_recovery_action", return_value=True) as should_run, \
             patch.object(self.crawler, "_send_notification_throttled") as send_note:
            result = self.crawler._recover_from_status(status, notify=True)

        self.assertTrue(result)
        should_run.assert_called_once_with("action.group_mismatch", cooldown_seconds=120)
        self.browser_navigation.find_and_access_group.assert_called_once_with("Nhóm Test")
        send_note.assert_called_once()
        self.assertEqual(send_note.call_args[0][0], "recovery.group_mismatch")

    def test_recover_from_status_unknown_login_state_refreshes(self):
        status = {
            "logged_in": False,
            "in_group": False,
            "needs_qr": False,
            "reason": "login-state-unknown",
            "page_state": {"group_title": "", "target_group": "Nhóm Test"},
        }

        with patch.object(self.crawler, "_should_run_recovery_action", return_value=True) as should_run, \
             patch.object(self.crawler, "_send_notification_throttled") as send_note, \
             patch.object(self.crawler, "refresh_page_safely", return_value=True) as refresh:
            result = self.crawler._recover_from_status(status, notify=True)

        self.assertTrue(result)
        should_run.assert_called_once_with("action.unknown_state_refresh", cooldown_seconds=90)
        refresh.assert_called_once_with()
        send_note.assert_called_once()
        self.assertEqual(send_note.call_args[0][0], "recovery.login_state_unknown")

    def test_reconnect_to_group_requires_verified_target_group(self):
        with patch.object(self.crawler, "check_zalo_status", return_value={
            "logged_in": True,
            "in_group": True,
            "needs_qr": False,
            "reason": "ready-in-target-group",
            "page_state": {"group_title": "Nhóm Test", "target_group": "Nhóm Test"},
        }):
            result = self.crawler.reconnect_to_group()

        self.assertTrue(result)
        self.browser_navigation.reconnect_to_group.assert_called_once_with("Nhóm Test")

    def test_reconnect_to_group_fails_on_group_mismatch_after_navigation_success(self):
        with patch.object(self.crawler, "check_zalo_status", return_value={
            "logged_in": True,
            "in_group": False,
            "needs_qr": False,
            "reason": "group-mismatch",
            "page_state": {"group_title": "Nhóm Khác", "target_group": "Nhóm Test"},
        }):
            result = self.crawler.reconnect_to_group()

        self.assertFalse(result)
        self.browser_navigation.reconnect_to_group.assert_called_with("Nhóm Test")

    def test_format_status_context_exposes_reason_and_group_details(self):
        ctx = self.crawler._format_status_context({
            "logged_in": True,
            "in_group": False,
            "needs_qr": False,
            "reason": "group-mismatch",
            "page_state": {"group_title": "Nhóm Khác", "target_group": "Nhóm Test"},
        })

        self.assertIn("reason=group-mismatch", ctx)
        self.assertIn("group_title='Nhóm Khác'", ctx)
        self.assertIn("target_group='Nhóm Test'", ctx)

    def test_build_observability_payload_contains_common_fields(self):
        payload = self.crawler._build_observability_payload(
            "group_reconnect_result",
            now=datetime(2026, 3, 19, 4, 49, 0),
            success=True,
            fail_streak=0,
        )

        self.assertEqual(payload["event"], "group_reconnect_result")
        self.assertEqual(payload["ts"], "2026-03-19T04:49:00")
        self.assertEqual(payload["session_id"], "20260319_P1")
        self.assertEqual(payload["host"], COMPUTER_NAME)
        self.assertEqual(payload["group"], "Nhóm Test")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["fail_streak"], 0)

    def test_log_status_transition_emits_observability_event(self):
        status = {
            "logged_in": True,
            "in_group": False,
            "needs_qr": False,
            "reason": "group-mismatch",
            "page_state": {"group_title": "Nhóm Khác", "target_group": "Nhóm Test"},
        }
        with patch("src.crawler.message_crawler.log_event") as mock_log_event:
            self.crawler._log_status_transition(status, force=True, prefix="test-status")

        mock_log_event.assert_called_once()
        event_name, payload = mock_log_event.call_args.args[:2]
        self.assertEqual(event_name, "zalo_status_transition")
        self.assertEqual(payload["event"], "zalo_status_transition")
        self.assertEqual(payload["status_reason"], "group-mismatch")
        self.assertEqual(payload["group_title"], "Nhóm Khác")
        self.assertEqual(payload["target_group"], "Nhóm Test")
        self.assertEqual(mock_log_event.call_args.kwargs["prefix"], "ZALO_STATUS_TRANSITION")


if __name__ == "__main__":
    unittest.main()
