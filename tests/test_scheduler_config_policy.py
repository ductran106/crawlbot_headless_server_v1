from main import _build_scheduler_policy
from src.utils.config import (
    SCHED_HOT_SLEEP_SEC,
    SCHED_MAX_CONSECUTIVE_VISITS,
    SCHED_NORMAL_SLEEP_MAX_SEC_2ROOM,
    SCHED_NORMAL_SLEEP_MAX_SEC_3ROOM,
    SCHED_NORMAL_SLEEP_MIN_SEC_2ROOM,
    SCHED_NORMAL_SLEEP_MIN_SEC_3ROOM,
    SCHED_PRESSURE_SLEEP_SEC,
    SCHED_STARVATION_SEC_2ROOM,
    SCHED_STARVATION_SEC_3ROOM,
)


def test_two_room_policy_reads_scheduler_knobs_from_config():
    policy = _build_scheduler_policy(2)
    assert policy == {
        "room_count": 2,
        "max_consecutive_visits": max(1, int(SCHED_MAX_CONSECUTIVE_VISITS or 2)),
        "starvation_threshold_seconds": max(1, int(SCHED_STARVATION_SEC_2ROOM or 6)),
        "hot_sleep_seconds": max(1, int(SCHED_HOT_SLEEP_SEC or 1)),
        "pressure_sleep_seconds": max(1, int(SCHED_PRESSURE_SLEEP_SEC or 2)),
        "normal_sleep_min_seconds": max(1, int(SCHED_NORMAL_SLEEP_MIN_SEC_2ROOM or 2)),
        "normal_sleep_max_seconds": max(1, int(SCHED_NORMAL_SLEEP_MAX_SEC_2ROOM or 3)),
    }


def test_three_room_policy_reads_scheduler_knobs_from_config():
    policy = _build_scheduler_policy(3)
    assert policy == {
        "room_count": 3,
        "max_consecutive_visits": max(1, int(SCHED_MAX_CONSECUTIVE_VISITS or 2)),
        "starvation_threshold_seconds": max(1, int(SCHED_STARVATION_SEC_3ROOM or 8)),
        "hot_sleep_seconds": max(1, int(SCHED_HOT_SLEEP_SEC or 1)),
        "pressure_sleep_seconds": max(1, int(SCHED_PRESSURE_SLEEP_SEC or 2)),
        "normal_sleep_min_seconds": max(1, int(SCHED_NORMAL_SLEEP_MIN_SEC_3ROOM or 2)),
        "normal_sleep_max_seconds": max(1, int(SCHED_NORMAL_SLEEP_MAX_SEC_3ROOM or 4)),
    }
