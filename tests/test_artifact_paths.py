from datetime import datetime

from src.utils.artifact_paths import (
    build_autosave_backup_path,
    build_autosave_temp_path,
    build_error_log_path,
    build_fail_artifact_filename,
    build_log_filename,
    build_structure_capture_paths,
)


def test_build_log_filename_uses_session_suffix_and_host():
    assert build_log_filename(datetime(2026, 3, 19, 6, 10, 0), "duc-ProBook") == "2026-03-19_P1_duc-ProBook.log"


def test_build_error_log_path_uses_daily_error_log_location():
    assert build_error_log_path(datetime(2026, 3, 19, 6, 10, 0), data_folder="/tmp/data") == "/tmp/data/logs/errors/error_2026-03-19.log"


def test_build_fail_artifact_filename_is_slugged_and_stable():
    assert (
        build_fail_artifact_filename(
            datetime(2026, 3, 19, 6, 10, 5),
            "RETURN ROOM LỊCH",
            "navigation.check_login_status",
            "login-state-unknown",
            "png",
        )
        == "20260319_061005_return_room_lich_navigation_check_login_status_login_state_unknown.png"
    )


def test_build_structure_capture_paths_are_timestamped_pair():
    md_path, json_path = build_structure_capture_paths(datetime(2026, 3, 19, 6, 10, 5), output_dir="/tmp/data/logs")
    assert md_path == "/tmp/data/logs/zalo_structure_2026-03-19_06-10-05.md"
    assert json_path == "/tmp/data/logs/zalo_structure_2026-03-19_06-10-05.json"


def test_build_autosave_temp_and_backup_paths_append_suffixes():
    base = "/tmp/data/return_room_lich/autosave_20260319_P1_duc-ProBook_return_room_lich.docx"
    assert build_autosave_temp_path(base) == base + ".temp"
    assert build_autosave_backup_path(base) == base + ".backup"
