import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException, WebDriverException

from src.auth.login import ZaloAuthManager


class DummyDriver:
    title = "Zalo - Test User"

    def find_elements(self, *args, **kwargs):
        return []

    def refresh(self):
        return None


class LoginStateObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.manager = ZaloAuthManager(DummyDriver())

    def test_check_login_status_records_logged_in_reason(self):
        wait_mock = Mock()
        wait_mock.until.return_value = object()

        with patch("src.auth.login.WebDriverWait", return_value=wait_mock):
            result = self.manager.check_login_status()

        self.assertTrue(result)
        self.assertEqual(self.manager.last_login_state_reason, "already-logged-in")
        self.assertTrue(self.manager.last_login_state["logged_in"])

    def test_check_login_status_records_qr_visible_reason(self):
        search_wait = Mock()
        search_wait.until.side_effect = TimeoutException("search not ready")
        qr_wait = Mock()
        qr_wait.until.return_value = object()

        with patch("src.auth.login.WebDriverWait", side_effect=[search_wait, qr_wait]):
            result = self.manager.check_login_status()

        self.assertFalse(result)
        self.assertEqual(self.manager.last_login_state_reason, "qr-visible")
        self.assertFalse(self.manager.last_login_state["logged_in"])

    def test_check_login_status_reraises_browser_dead_error(self):
        search_wait = Mock()
        search_wait.until.side_effect = WebDriverException("tab crashed")

        with patch("src.auth.login.WebDriverWait", return_value=search_wait):
            with self.assertRaises(WebDriverException):
                self.manager.check_login_status()

    def test_get_login_debug_state_exposes_last_reason(self):
        self.manager.last_login_state_reason = "qr-sent"

        state = self.manager.get_login_debug_state(qr_sent=True)

        self.assertEqual(state["last_reason"], "qr-sent")
        self.assertTrue(state["qr_sent"])
        self.assertIn("last_qr_refresh_age_s", state)
        self.assertIn("qr_expired", state)

    def test_log_transition_dedupes_same_state_and_reason_only(self):
        state = {
            "logged_in": False,
            "qr_sent": True,
            "qr_expired": False,
            "last_qr_refresh_age_s": 1,
        }

        with patch("src.auth.login.log") as mock_log:
            self.manager._log_login_state_transition(state, reason="qr-sent")
            self.manager._log_login_state_transition(dict(state), reason="qr-sent")
            self.manager._log_login_state_transition(dict(state), reason="waiting-for-login")

        self.assertEqual(mock_log.call_count, 2)
        self.assertEqual(self.manager.last_login_state_reason, "waiting-for-login")

    def test_wait_for_login_timeout_emits_final_state_snapshot(self):
        captured = []

        def capture_transition(state, reason, level=None, force=False):
            captured.append({
                "state": dict(state),
                "reason": reason,
                "force": force,
            })
            self.manager.last_login_state = dict(state)
            self.manager.last_login_state_reason = reason

        with patch("src.auth.login.send_notification") as mock_notify:
            self.manager._log_login_state_transition = capture_transition
            result = self.manager.wait_for_login(timeout_seconds=0)

        self.assertFalse(result)
        self.assertTrue(captured)
        self.assertEqual(captured[-1]["reason"], "login-timeout")
        self.assertTrue(captured[-1]["force"])
        self.assertEqual(captured[-1]["state"]["last_reason"], self.manager.last_login_state_reason)
        mock_notify.assert_called_once_with("❌ Hết thời gian chờ đăng nhập Zalo")


if __name__ == "__main__":
    unittest.main()
