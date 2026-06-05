from unittest.mock import MagicMock, patch

from src.browser.driver import BrowserManager


def test_check_zalo_surface_ready_detects_search_ready():
    manager = BrowserManager(user_data_dir="/tmp/test-profile", debug_port=9333)
    manager.driver = MagicMock()

    def fake_find_elements(by, selector):
        if selector == "contact-search-input":
            return [MagicMock()]
        if selector == ".qrcode img":
            return []
        if selector == "body":
            return [MagicMock()]
        return []

    manager.driver.find_elements.side_effect = fake_find_elements

    with patch("src.browser.driver.WebDriverWait") as wait_cls:
        wait_cls.return_value.until.return_value = True
        ready, reason = manager.check_zalo_surface_ready(timeout=3)

    assert ready is True
    assert reason == "search_ready"


def test_check_zalo_surface_ready_detects_qr_ready():
    manager = BrowserManager(user_data_dir="/tmp/test-profile", debug_port=9333)
    manager.driver = MagicMock()

    def fake_find_elements(by, selector):
        if selector == "contact-search-input":
            return []
        if selector == ".qrcode img":
            return [MagicMock()]
        if selector == "body":
            return [MagicMock()]
        return []

    manager.driver.find_elements.side_effect = fake_find_elements

    with patch("src.browser.driver.WebDriverWait") as wait_cls:
        wait_cls.return_value.until.return_value = True
        ready, reason = manager.check_zalo_surface_ready(timeout=3)

    assert ready is True
    assert reason == "qr_ready"


def test_recover_session_returns_false_when_surface_not_ready():
    manager = BrowserManager(user_data_dir="/tmp/test-profile", debug_port=9333)
    manager.driver = MagicMock()

    with patch("src.browser.driver.WebDriverWait") as wait_cls, \
         patch.object(manager, "check_zalo_surface_ready", side_effect=[(False, "surface_unknown"), (False, "surface_unknown")]):
        wait_cls.return_value.until.return_value = True
        assert manager.recover_session(url="https://chat.zalo.me", timeout=2) is False


def test_recover_session_returns_true_when_surface_ready():
    manager = BrowserManager(user_data_dir="/tmp/test-profile", debug_port=9333)
    manager.driver = MagicMock()

    with patch("src.browser.driver.WebDriverWait") as wait_cls, \
         patch.object(manager, "check_zalo_surface_ready", return_value=(True, "search_ready")):
        wait_cls.return_value.until.return_value = True
        assert manager.recover_session(url="https://chat.zalo.me", timeout=2) is True


def test_should_proactively_recycle_by_uptime():
    manager = BrowserManager(user_data_dir="/tmp/test-profile", debug_port=9333)
    manager.driver_started_at = 100.0

    with patch("src.browser.driver.DRIVER_PROACTIVE_RECYCLE_MINUTES", 180), \
         patch("src.browser.driver.DRIVER_PROACTIVE_RECYCLE_ROOM_CYCLES", 900), \
         patch("src.browser.driver.time.time", return_value=100.0 + 180 * 60 + 5):
        should_recycle, reason = manager.should_proactively_recycle(room_cycle=10)

    assert should_recycle is True
    assert reason == "uptime>=180m"


def test_should_proactively_recycle_by_room_cycle():
    manager = BrowserManager(user_data_dir="/tmp/test-profile", debug_port=9333)
    manager.driver_started_at = 100.0

    with patch("src.browser.driver.DRIVER_PROACTIVE_RECYCLE_MINUTES", 180), \
         patch("src.browser.driver.DRIVER_PROACTIVE_RECYCLE_ROOM_CYCLES", 900), \
         patch("src.browser.driver.time.time", return_value=100.0 + 60):
        should_recycle, reason = manager.should_proactively_recycle(room_cycle=905)

    assert should_recycle is True
    assert reason == "room_cycle>=900"


def test_should_not_proactively_recycle_when_below_thresholds():
    manager = BrowserManager(user_data_dir="/tmp/test-profile", debug_port=9333)
    manager.driver_started_at = 100.0

    with patch("src.browser.driver.DRIVER_PROACTIVE_RECYCLE_MINUTES", 180), \
         patch("src.browser.driver.DRIVER_PROACTIVE_RECYCLE_ROOM_CYCLES", 900), \
         patch("src.browser.driver.time.time", return_value=100.0 + 120):
        should_recycle, reason = manager.should_proactively_recycle(room_cycle=100)

    assert should_recycle is False
    assert reason is None
