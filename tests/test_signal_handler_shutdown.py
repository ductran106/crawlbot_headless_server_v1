import unittest
from unittest.mock import patch

import src.utils.signals as signals


class SignalHandlerShutdownTests(unittest.TestCase):
    def setUp(self):
        signals.is_shutting_down = False

    def tearDown(self):
        signals.is_shutting_down = False

    def test_first_signal_uses_stderr_notice_instead_of_logger(self):
        with patch("src.utils.signals._signal_safe_notice") as mock_notice, \
             patch("src.utils.signals.log") as mock_log:
            signals.signal_handler(None, None)

        self.assertTrue(signals.is_shutting_down)
        mock_notice.assert_called_once()
        mock_log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
