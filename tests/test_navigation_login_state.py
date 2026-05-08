import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException, WebDriverException

from src.browser.navigation import ZaloNavigator


class DummyDriver:
    title = "Zalo - Test User"


class NavigationLoginStateTests(unittest.TestCase):
    def setUp(self):
        self.navigator = ZaloNavigator(DummyDriver())

    def test_check_login_status_returns_true_when_search_visible(self):
        wait_mock = Mock()
        wait_mock.until.return_value = object()

        with patch("src.browser.navigation.WebDriverWait", return_value=wait_mock):
            result = self.navigator.check_login_status()

        self.assertTrue(result)

    def test_check_login_status_returns_false_when_qr_visible(self):
        search_wait = Mock()
        search_wait.until.side_effect = TimeoutException("search not ready")
        qr_wait = Mock()
        qr_wait.until.return_value = object()

        with patch("src.browser.navigation.WebDriverWait", side_effect=[search_wait, qr_wait]):
            result = self.navigator.check_login_status()

        self.assertFalse(result)

    def test_check_login_status_reraises_browser_dead_error(self):
        search_wait = Mock()
        search_wait.until.side_effect = WebDriverException("tab crashed")

        with patch("src.browser.navigation.WebDriverWait", return_value=search_wait):
            with self.assertRaises(WebDriverException):
                self.navigator.check_login_status()


if __name__ == "__main__":
    unittest.main()
