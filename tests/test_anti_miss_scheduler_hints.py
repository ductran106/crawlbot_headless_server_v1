from datetime import datetime
from unittest.mock import Mock, patch

from main import (
    _build_scheduler_policy,
    _compute_room_priority,
    _format_room_switch_tracker_log,
    _select_next_group,
    _select_sleep_seconds,
    _update_group_backlog_tracker,
)
from src.crawler.message_crawler import MessageCrawler
from src.utils.config import COMPUTER_NAME
from src.utils.observability import build_event_payload, build_room_switch_tracker_snapshot, format_event_log


class DummyDriver:
    title = "Zalo - Test User"

    def find_elements(self, *args, **kwargs):
        return []


def _make_crawler():
    with patch.object(MessageCrawler, "_get_current_user_name", return_value="Test User"), \
         patch("src.crawler.message_crawler.KeywordMonitor") as mock_keyword_monitor, \
         patch("src.crawler.message_crawler.MessageProcessor"), \
         patch("src.crawler.message_crawler.DocxHandler"), \
         patch("src.crawler.message_crawler.DatabaseManager"):
        mock_keyword_monitor.return_value.start_monitoring.return_value = None
        return MessageCrawler(DummyDriver(), browser_navigation=Mock(), group_name="RETURN ROOM LỊCH")


def test_backlog_pressure_turns_on_for_dense_visible_window():
    crawler = _make_crawler()
    state = crawler._compute_backlog_state(visible_count=85, processed_count=3)
    assert state["backlog_pressure"] is True
    assert crawler.backlog_pressure is True


def test_possible_gap_turns_on_when_visible_dense_but_processed_low():
    crawler = _make_crawler()
    state = crawler._compute_backlog_state(visible_count=90, processed_count=1)
    assert state["possible_gap"] is True
    assert crawler.possible_gap is True


def test_backlog_pressure_turns_off_for_light_room():
    crawler = _make_crawler()
    state = crawler._compute_backlog_state(visible_count=12, processed_count=2)
    assert state["backlog_pressure"] is False
    assert state["possible_gap"] is False


def test_backlog_hot_turns_on_after_repeated_pressure():
    crawler = _make_crawler()
    first = crawler._compute_backlog_state(visible_count=85, processed_count=3)
    second = crawler._compute_backlog_state(visible_count=88, processed_count=4)
    assert first["backlog_hot"] is False
    assert second["backlog_hot"] is True
    assert second["backlog_pressure_streak"] == 2


def test_gap_streak_turns_on_backlog_hot():
    crawler = _make_crawler()
    crawler._compute_backlog_state(visible_count=90, processed_count=1)
    second = crawler._compute_backlog_state(visible_count=92, processed_count=2)
    assert second["possible_gap"] is True
    assert second["possible_gap_streak"] == 2
    assert second["backlog_hot"] is True


def test_pressure_streak_resets_after_light_cycle():
    crawler = _make_crawler()
    crawler._compute_backlog_state(visible_count=85, processed_count=3)
    crawler._compute_backlog_state(visible_count=88, processed_count=4)
    cooled = crawler._compute_backlog_state(visible_count=10, processed_count=1)
    assert cooled["backlog_pressure"] is False
    assert cooled["backlog_pressure_streak"] == 0
    assert cooled["backlog_hot"] is False


def test_scheduler_policy_for_two_rooms_has_tighter_starvation_cap():
    policy = _build_scheduler_policy(2)
    assert policy["room_count"] == 2
    assert policy["max_consecutive_visits"] == 2
    assert policy["starvation_threshold_seconds"] == 6


def test_scheduler_policy_for_three_rooms_still_caps_consecutive_visits():
    policy = _build_scheduler_policy(3)
    assert policy["room_count"] == 3
    assert policy["max_consecutive_visits"] == 2
    assert policy["starvation_threshold_seconds"] == 8


def test_compute_room_priority_prefers_starving_room_over_recent_hot_room():
    policy = _build_scheduler_policy(3)
    room_state = {
        "A": {"starvation_seconds": 2, "possible_gap": False, "backlog_hot": True, "backlog_pressure": True, "consecutive_visits": 1},
        "B": {"starvation_seconds": 9, "possible_gap": False, "backlog_hot": False, "backlog_pressure": False, "consecutive_visits": 0},
    }
    assert _compute_room_priority("B", room_state["B"], policy) > _compute_room_priority("A", room_state["A"], policy)


def test_select_next_group_forces_starving_room_in_two_room_mode():
    groups = ["A", "B"]
    room_state = {
        "A": {"starvation_seconds": 1, "possible_gap": False, "backlog_hot": True, "backlog_pressure": True, "consecutive_visits": 1},
        "B": {"starvation_seconds": 7, "possible_gap": False, "backlog_hot": False, "backlog_pressure": False, "consecutive_visits": 0},
    }
    selected, reason, score = _select_next_group(groups, room_state, current_group="A")
    assert selected == "B"
    assert reason == "starvation_guard"
    assert score is None


def test_select_next_group_caps_consecutive_visits_in_three_room_mode():
    groups = ["A", "B", "C"]
    room_state = {
        "A": {"starvation_seconds": 1, "possible_gap": True, "backlog_hot": True, "backlog_pressure": True, "consecutive_visits": 2},
        "B": {"starvation_seconds": 5, "possible_gap": False, "backlog_hot": False, "backlog_pressure": False, "consecutive_visits": 0},
        "C": {"starvation_seconds": 4, "possible_gap": False, "backlog_hot": False, "backlog_pressure": False, "consecutive_visits": 0},
    }
    selected, reason, score = _select_next_group(groups, room_state, current_group="A")
    assert selected in {"B", "C"}
    assert selected != "A"
    assert reason in {"priority_score", "starvation_guard", "round_robin"}
    assert score is None or isinstance(score, (int, float))


def test_select_sleep_seconds_prefers_fast_loop_for_hot_room():
    policy = _build_scheduler_policy(2)
    room_snapshot = {"possible_gap": False, "backlog_hot": True, "backlog_pressure": True}
    assert _select_sleep_seconds(room_snapshot, policy) == 1


def test_select_sleep_seconds_uses_pressure_mode_before_normal_mode():
    policy = _build_scheduler_policy(3)
    room_snapshot = {"possible_gap": False, "backlog_hot": False, "backlog_pressure": True}
    assert _select_sleep_seconds(room_snapshot, policy) == 2


def test_room_switch_tracker_snapshot_reflects_scheduler_state():
    tracker = {"pressure_streak": 2, "gap_streak": 1, "backlog_hot": True}
    now = datetime(2026, 3, 19, 4, 46, 0)
    snapshot = build_room_switch_tracker_snapshot(
        "RETURN ROOM LỊCH",
        tracker,
        processed_count=7,
        backlog_pressure=True,
        possible_gap=False,
        stay_budget=2,
        next_idx=3,
        sleep_s=1,
        room_cycle=5,
        now=now,
    )
    assert snapshot == {
        "event": "room_switch_tracker",
        "ts": "2026-03-19T04:46:00",
        "session_id": "20260319_P1",
        "host": COMPUTER_NAME,
        "room_cycle": 5,
        "group": "RETURN ROOM LỊCH",
        "processed_count": 7,
        "backlog_pressure": True,
        "possible_gap": False,
        "pressure_streak": 2,
        "gap_streak": 1,
        "backlog_hot": True,
        "stay_budget": 2,
        "next_group_index": 3,
        "sleep_s": 1,
    }


def test_room_switch_tracker_log_is_stable_json_line():
    snapshot = {
        "event": "room_switch_tracker",
        "ts": "2026-03-19T04:46:00",
        "session_id": "20260319_P1",
        "host": "duc-ProBook",
        "room_cycle": 5,
        "group": "RETURN ROOM LỊCH",
        "processed_count": 7,
        "backlog_pressure": True,
        "possible_gap": False,
        "pressure_streak": 2,
        "gap_streak": 1,
        "backlog_hot": True,
        "stay_budget": 2,
        "next_group_index": 3,
        "sleep_s": 1,
    }
    line = _format_room_switch_tracker_log(snapshot)
    assert line == (
        'ROOM_SWITCH_TRACKER '
        '{"backlog_hot":true,"backlog_pressure":true,"event":"room_switch_tracker",'
        '"gap_streak":1,"group":"RETURN ROOM LỊCH","host":"duc-ProBook",'
        '"next_group_index":3,"possible_gap":false,"pressure_streak":2,'
        '"processed_count":7,"room_cycle":5,"session_id":"20260319_P1",'
        '"sleep_s":1,"stay_budget":2,"ts":"2026-03-19T04:46:00"}'
    )


def test_format_event_log_supports_generic_observability_events():
    line = format_event_log(
        "sample_event",
        payload={"value": 42, "status": "ok"},
        prefix="SAMPLE_EVENT",
    )
    assert line == 'SAMPLE_EVENT {"event":"sample_event","status":"ok","value":42}'


def test_build_event_payload_adds_common_metadata():
    payload = build_event_payload(
        "sample_event",
        now=datetime(2026, 3, 19, 4, 55, 0),
        group="RETURN ROOM LỊCH",
        status="ok",
    )
    assert payload == {
        "event": "sample_event",
        "ts": "2026-03-19T04:55:00",
        "session_id": "20260319_P1",
        "host": COMPUTER_NAME,
        "group": "RETURN ROOM LỊCH",
        "status": "ok",
    }
