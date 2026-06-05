from unittest.mock import MagicMock, patch

from main import _recover_browser_and_update_refs


@patch("main.log_event")
def test_recover_browser_returns_none_when_target_group_reopen_fails(_mock_log_event):
    browser_manager = MagicMock()
    browser_manager.restart_driver.return_value = True
    browser_manager.get_driver.return_value = MagicMock()
    browser_manager.recover_session.return_value = True

    zalo_navigator = MagicMock()
    zalo_navigator.find_and_access_group.return_value = False

    zalo_auth = MagicMock()
    zalo_auth.check_login_status.return_value = True

    crawler = MagicMock()
    crawler.browser_navigation = MagicMock()
    crawler.message_processor = MagicMock()
    crawlers = {"ROOM A": crawler}

    result = _recover_browser_and_update_refs(
        browser_manager,
        zalo_navigator,
        crawlers,
        ["ROOM A"],
        zalo_auth,
        target_group="ROOM A",
    )

    assert result is None
    zalo_navigator.find_and_access_group.assert_called_once_with(group_name="ROOM A")


@patch("main.log_event")
def test_recover_browser_returns_driver_when_target_group_reopens(_mock_log_event):
    new_driver = MagicMock()
    browser_manager = MagicMock()
    browser_manager.restart_driver.return_value = True
    browser_manager.get_driver.return_value = new_driver
    browser_manager.recover_session.return_value = True

    zalo_navigator = MagicMock()
    zalo_navigator.find_and_access_group.return_value = True

    zalo_auth = MagicMock()
    zalo_auth.check_login_status.return_value = True

    crawler = MagicMock()
    crawler.browser_navigation = MagicMock()
    crawler.message_processor = MagicMock()
    crawlers = {"ROOM A": crawler}

    result = _recover_browser_and_update_refs(
        browser_manager,
        zalo_navigator,
        crawlers,
        ["ROOM A"],
        zalo_auth,
        target_group="ROOM A",
    )

    assert result is new_driver
    zalo_navigator.find_and_access_group.assert_called_once_with(group_name="ROOM A")


def test_recover_browser_passes_reason_to_restart_driver():
    new_driver = MagicMock()
    browser_manager = MagicMock()
    browser_manager.restart_driver.return_value = True
    browser_manager.get_driver.return_value = new_driver
    browser_manager.recover_session.return_value = True

    zalo_navigator = MagicMock()
    zalo_navigator.find_and_access_group.return_value = True

    zalo_auth = MagicMock()
    zalo_auth.check_login_status.return_value = True

    crawler = MagicMock()
    crawler.browser_navigation = MagicMock()
    crawler.message_processor = MagicMock()
    crawlers = {"ROOM A": crawler}

    with patch("main.log_event"):
        result = _recover_browser_and_update_refs(
            browser_manager,
            zalo_navigator,
            crawlers,
            ["ROOM A"],
            zalo_auth,
            target_group="ROOM A",
            recovery_reason="proactive_recycle:uptime>=180m",
        )

    assert result is new_driver
    browser_manager.restart_driver.assert_called_once_with(reason="proactive_recycle:uptime>=180m")
