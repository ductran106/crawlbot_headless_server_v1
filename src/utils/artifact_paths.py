import os
from datetime import datetime

from .config import COMPUTER_NAME, DATA_FOLDER, LOGS_FOLDER, get_session_suffix, slugify


def build_log_filename(now=None, hostname=None):
    now = now or datetime.now()
    hostname = hostname or COMPUTER_NAME
    return f"{now.strftime('%Y-%m-%d')}_{get_session_suffix(now)}_{hostname}.log"


def build_error_log_path(now=None, *, data_folder=None):
    now = now or datetime.now()
    base_data = data_folder or DATA_FOLDER
    return os.path.join(base_data, "logs", "errors", f"error_{now.strftime('%Y-%m-%d')}.log")


def get_fail_artifact_dir(*, data_folder=None):
    base_data = data_folder or DATA_FOLDER
    return os.path.join(base_data, "logs", "fail-artifacts")


def build_fail_artifact_filename(now, group_name, phase, reason, extension):
    ts = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{slugify(group_name)}_{slugify(phase)}_{slugify(reason)}.{extension.lstrip('.')}"


def build_fail_artifact_path(now, group_name, phase, reason, extension, *, data_folder=None):
    return os.path.join(
        get_fail_artifact_dir(data_folder=data_folder),
        build_fail_artifact_filename(now, group_name, phase, reason, extension),
    )


def build_structure_capture_paths(now=None, *, output_dir=None):
    now = now or datetime.now()
    out_dir = output_dir or os.path.join(DATA_FOLDER, "logs")
    ts = now.strftime("%Y-%m-%d_%H-%M-%S")
    return (
        os.path.join(out_dir, f"zalo_structure_{ts}.md"),
        os.path.join(out_dir, f"zalo_structure_{ts}.json"),
    )


def build_autosave_temp_path(autosave_path: str) -> str:
    return f"{autosave_path}.temp"


def build_autosave_backup_path(autosave_path: str) -> str:
    return f"{autosave_path}.backup"
