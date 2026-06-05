from datetime import datetime

from src.utils.config import (
    get_next_session_boundary,
    get_session_id,
    get_session_run_seconds,
    get_session_suffix,
    has_session_changed,
)


def test_session_suffix_mapping_is_human_readable_and_ordered():
    assert get_session_suffix(datetime(2026, 3, 18, 0, 0, 0)) == "P1"
    assert get_session_suffix(datetime(2026, 3, 18, 9, 0, 0)) == "P2"
    assert get_session_suffix(datetime(2026, 3, 18, 12, 0, 0)) == "P3"
    assert get_session_suffix(datetime(2026, 3, 18, 15, 0, 0)) == "P4"
    assert get_session_suffix(datetime(2026, 3, 18, 18, 0, 0)) == "P5"
    assert get_session_suffix(datetime(2026, 3, 18, 21, 0, 0)) == "P6"


def test_session_id_uses_same_standardized_suffix():
    assert get_session_id(datetime(2026, 3, 18, 11, 59, 59)) == "20260318_P2"
    assert get_session_id(datetime(2026, 3, 18, 12, 0, 0)) == "20260318_P3"


def test_next_session_boundary_follows_canonical_windows():
    assert get_next_session_boundary(datetime(2026, 3, 18, 6, 30, 0)) == datetime(2026, 3, 18, 9, 0, 0)
    assert get_next_session_boundary(datetime(2026, 3, 18, 10, 15, 0)) == datetime(2026, 3, 18, 12, 0, 0)
    assert get_next_session_boundary(datetime(2026, 3, 18, 22, 10, 0)) == datetime(2026, 3, 18, 23, 59, 59)


def test_session_run_seconds_matches_next_boundary():
    assert get_session_run_seconds(datetime(2026, 3, 18, 8, 59, 30)) == 30.0
    assert get_session_run_seconds(datetime(2026, 3, 18, 11, 59, 0)) == 60.0


def test_has_session_changed_tracks_business_window_rollover():
    assert has_session_changed("20260318_P1", datetime(2026, 3, 18, 9, 0, 0)) is True
    assert has_session_changed("20260318_P2", datetime(2026, 3, 18, 11, 30, 0)) is False
