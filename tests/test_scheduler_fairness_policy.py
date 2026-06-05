from main import _build_scheduler_policy, _select_next_group


def test_two_room_policy_forces_switch_when_other_room_starves():
    groups = ["A", "B"]
    room_state = {
        "A": {
            "starvation_seconds": 0,
            "possible_gap": True,
            "backlog_hot": True,
            "backlog_pressure": True,
            "consecutive_visits": 1,
        },
        "B": {
            "starvation_seconds": 6,
            "possible_gap": False,
            "backlog_hot": False,
            "backlog_pressure": False,
            "consecutive_visits": 0,
        },
    }
    selected, reason, score = _select_next_group(groups, room_state, current_group="A")
    assert _build_scheduler_policy(2)["starvation_threshold_seconds"] == 6
    assert selected == "B"
    assert reason == "starvation_guard"
    assert score is None


def test_two_room_policy_never_allows_third_consecutive_visit():
    groups = ["A", "B"]
    room_state = {
        "A": {
            "starvation_seconds": 1,
            "possible_gap": True,
            "backlog_hot": True,
            "backlog_pressure": True,
            "consecutive_visits": 2,
        },
        "B": {
            "starvation_seconds": 3,
            "possible_gap": False,
            "backlog_hot": False,
            "backlog_pressure": False,
            "consecutive_visits": 0,
        },
    }
    selected, reason, score = _select_next_group(groups, room_state, current_group="A")
    assert selected == "B"
    assert reason in {"priority_score", "starvation_guard", "round_robin"}
    assert score is None or isinstance(score, (int, float))


def test_three_room_policy_prefers_most_starved_room_when_multiple_rooms_wait():
    groups = ["A", "B", "C"]
    room_state = {
        "A": {
            "starvation_seconds": 0,
            "possible_gap": True,
            "backlog_hot": True,
            "backlog_pressure": True,
            "consecutive_visits": 1,
        },
        "B": {
            "starvation_seconds": 8,
            "possible_gap": False,
            "backlog_hot": False,
            "backlog_pressure": False,
            "consecutive_visits": 0,
        },
        "C": {
            "starvation_seconds": 10,
            "possible_gap": False,
            "backlog_hot": False,
            "backlog_pressure": False,
            "consecutive_visits": 0,
        },
    }
    selected, reason, score = _select_next_group(groups, room_state, current_group="A")
    assert _build_scheduler_policy(3)["starvation_threshold_seconds"] == 8
    assert selected == "C"
    assert reason == "starvation_guard"
    assert score is None


def test_three_room_policy_does_not_let_hot_room_monopolize_lane():
    groups = ["A", "B", "C"]
    room_state = {
        "A": {
            "starvation_seconds": 1,
            "possible_gap": True,
            "backlog_hot": True,
            "backlog_pressure": True,
            "consecutive_visits": 2,
        },
        "B": {
            "starvation_seconds": 4,
            "possible_gap": False,
            "backlog_hot": False,
            "backlog_pressure": False,
            "consecutive_visits": 0,
        },
        "C": {
            "starvation_seconds": 5,
            "possible_gap": False,
            "backlog_hot": False,
            "backlog_pressure": False,
            "consecutive_visits": 0,
        },
    }
    selected, reason, score = _select_next_group(groups, room_state, current_group="A")
    assert selected in {"B", "C"}
    assert selected != "A"
    assert reason in {"priority_score", "starvation_guard", "round_robin", "bootstrap_never_visited"}
    assert score is None or isinstance(score, (int, float))


def test_three_room_policy_bootstraps_never_visited_room_before_normal_fairness():
    groups = ["A", "B", "C"]
    room_state = {
        "A": {
            "last_visited_at": 100.0,
            "never_visited": False,
            "starvation_seconds": 1,
            "possible_gap": False,
            "backlog_hot": False,
            "backlog_pressure": False,
            "consecutive_visits": 1,
        },
        "B": {
            "last_visited_at": 110.0,
            "never_visited": False,
            "starvation_seconds": 2,
            "possible_gap": False,
            "backlog_hot": False,
            "backlog_pressure": False,
            "consecutive_visits": 0,
        },
        "C": {
            "last_visited_at": 0.0,
            "never_visited": True,
            "starvation_seconds": 8,
            "possible_gap": False,
            "backlog_hot": False,
            "backlog_pressure": False,
            "consecutive_visits": 0,
        },
    }
    selected, reason, score = _select_next_group(groups, room_state, current_group="A")
    assert selected == "C"
    assert reason == "bootstrap_never_visited"
    assert score is None
