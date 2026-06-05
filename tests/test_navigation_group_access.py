from unittest.mock import MagicMock, patch

from src.browser.navigation import ZaloNavigator


@patch("src.browser.navigation.time.sleep", return_value=None)
def test_find_and_access_group_returns_false_when_header_does_not_match(_,):
    driver = MagicMock()
    navigator = ZaloNavigator(driver)
    search_box = MagicMock()
    item = MagicMock()
    item.text = "RET 2 ROOM LỊCH"
    driver.find_elements.return_value = [item]

    with patch("src.browser.navigation.WebDriverWait") as wait_cls:
        wait_cls.return_value.until.return_value = search_box
        with patch.object(navigator, "_verify_current_group_title", return_value=(False, "ROOM KHÁC")):
            with patch.object(navigator, "_wait_until_header_matches", return_value=(False, "ROOM KHÁC")):
                result = navigator.find_and_access_group("RET 2 ROOM LỊCH")

    assert result is False


@patch("src.browser.navigation.time.sleep", return_value=None)
def test_find_and_access_group_returns_true_only_after_verified_match(_,):
    driver = MagicMock()
    navigator = ZaloNavigator(driver)
    search_box = MagicMock()
    item = MagicMock()
    item.text = "RET 2 ROOM LỊCH"
    driver.find_elements.return_value = [item]

    with patch("src.browser.navigation.WebDriverWait") as wait_cls:
        wait_cls.return_value.until.return_value = search_box
        with patch.object(navigator, "_verify_current_group_title", side_effect=[(False, "ROOM KHÁC")]):
            with patch.object(navigator, "_wait_until_header_matches", return_value=(True, "RET 2 ROOM LỊCH")):
                with patch.object(navigator, "_warmup_room_after_open") as warmup:
                    result = navigator.find_and_access_group("RET 2 ROOM LỊCH")

    assert result is True
    warmup.assert_called_once()


@patch("src.browser.navigation.time.sleep", return_value=None)
def test_reconnect_to_group_returns_false_when_header_not_verified(_,):
    driver = MagicMock()
    navigator = ZaloNavigator(driver)
    search_box = MagicMock()
    item = MagicMock()
    item.text = "HEY KLUB"
    driver.find_elements.return_value = [item]

    with patch("src.browser.navigation.WebDriverWait") as wait_cls:
        wait_cls.return_value.until.return_value = search_box
        with patch.object(navigator, "_verify_current_group_title", return_value=(False, "ROOM KHÁC")):
            with patch.object(navigator, "_wait_until_header_matches", return_value=(False, "ROOM KHÁC")):
                result = navigator.reconnect_to_group("HEY KLUB")

    assert result is False


def test_matches_target_group_uses_normalized_semantics():
    navigator = ZaloNavigator(MagicMock())
    assert navigator._matches_target_group("Return Room Lịch!!!", "RETURN ROOM LỊCH") is True
    assert navigator._matches_target_group("Hey   Klub", "HEY KLUB") is True
    assert navigator._matches_target_group("Room khac", "HEY KLUB") is False


@patch("src.browser.navigation.time.sleep", return_value=None)
def test_wait_until_header_matches_uses_normalized_fallback(_,):
    navigator = ZaloNavigator(MagicMock())

    with patch.object(
        navigator,
        "_verify_current_group_title",
        side_effect=lambda *args, **kwargs: (False, "[1-1 RETURN] ROOM LỊCH"),
    ):
        matched, header = navigator._wait_until_header_matches("RETURN ROOM LỊCH", timeout=1, stable_checks=2)

    assert matched is True
    assert header == "[1-1 RETURN] ROOM LỊCH"
