import unittest
from unittest.mock import Mock, patch

from src.browser.driver import BrowserManager
from src.browser.navigation import ZaloNavigator


class ShutdownRecoveryNoiseTests(unittest.TestCase):
    def test_browser_manager_skips_restart_when_shutting_down(self):
        manager = BrowserManager(user_data_dir="./tmp-test-profile", debug_port=0)
        with patch("src.browser.driver.is_terminating", return_value=True):
            self.assertFalse(manager.restart_driver())

    def test_browser_manager_skips_recover_when_shutting_down(self):
        manager = BrowserManager(user_data_dir="./tmp-test-profile", debug_port=0)
        manager.driver = Mock()
        with patch("src.browser.driver.is_terminating", return_value=True):
            self.assertFalse(manager.recover_session())

    def test_navigation_quiets_shutdown_browser_error_only_while_terminating(self):
        navigator = ZaloNavigator(driver=Mock())
        browser_dead_error = Exception("HTTPConnectionPool(host='localhost', port=123): connection refused")

        with patch("src.browser.navigation.is_terminating", return_value=True):
            self.assertTrue(navigator._should_quiet_shutdown_browser_error(browser_dead_error))

        with patch("src.browser.navigation.is_terminating", return_value=False):
            self.assertFalse(navigator._should_quiet_shutdown_browser_error(browser_dead_error))


if __name__ == "__main__":
    unittest.main()
