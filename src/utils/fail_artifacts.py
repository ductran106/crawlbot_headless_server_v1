import json
import os
import time
from datetime import datetime
from pathlib import Path

from .config import (
    DATA_FOLDER,
    ENABLE_FAIL_ARTIFACTS,
    FAIL_ARTIFACT_MAX_BYTES,
    FAIL_ARTIFACT_RETENTION_DAYS,
    FAIL_ARTIFACT_SCREENSHOT_THROTTLE_SECONDS,
    FAIL_ARTIFACT_TARGET_BYTES,
)
from .logger import log, logging
from .artifact_paths import build_fail_artifact_path, get_fail_artifact_dir

_THROTTLE_STATE = {}
_LAST_CLEANUP_AT = 0.0
_CLEANUP_INTERVAL_SECONDS = 5 * 60


def _env_bool(name, default):
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}


def _env_int(name, default):
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def fail_artifacts_enabled():
    return _env_bool("ENABLE_FAIL_ARTIFACTS", ENABLE_FAIL_ARTIFACTS)


def reset_fail_artifact_throttle_state():
    _THROTTLE_STATE.clear()


def _artifact_key(group_name, phase, reason):
    return (str(group_name or "group"), str(phase or "phase"), str(reason or "reason"))


def should_capture_fail_artifact(group_name, phase, reason, *, now=None, throttle_seconds=None):
    """Allow heavy screenshot capture once per group/phase/reason per throttle window."""
    now = time.time() if now is None else float(now)
    throttle_seconds = _env_int(
        "FAIL_ARTIFACT_SCREENSHOT_THROTTLE_SECONDS",
        FAIL_ARTIFACT_SCREENSHOT_THROTTLE_SECONDS if throttle_seconds is None else throttle_seconds,
    )
    key = _artifact_key(group_name, phase, reason)
    last = _THROTTLE_STATE.get(key)
    if last is not None and now - last < throttle_seconds:
        return False
    _THROTTLE_STATE[key] = now
    return True


def _safe_fail_artifact_dir(data_folder=None):
    base_data = Path(data_folder or DATA_FOLDER).resolve()
    fail_dir = Path(get_fail_artifact_dir(data_folder=str(base_data))).resolve()
    expected = (base_data / "logs" / "fail-artifacts").resolve()
    if fail_dir != expected:
        raise RuntimeError(f"Refusing to clean unexpected fail artifact dir: {fail_dir} != {expected}")
    return fail_dir


def _iter_artifact_files(fail_dir):
    if not fail_dir.exists():
        return []
    return [p for p in fail_dir.rglob("*") if p.is_file()]


def _remove_empty_dirs(fail_dir):
    if not fail_dir.exists():
        return 0
    removed = 0
    for p in sorted([x for x in fail_dir.rglob("*") if x.is_dir()], key=lambda x: len(x.parts), reverse=True):
        try:
            p.rmdir()
            removed += 1
        except OSError:
            pass
    return removed


def cleanup_fail_artifacts(*, data_folder=None, max_age_days=None, max_bytes=None, target_bytes=None, logger=log):
    """Clean only data/logs/fail-artifacts with 14-day retention and size cap."""
    max_age_days = _env_int("FAIL_ARTIFACT_RETENTION_DAYS", FAIL_ARTIFACT_RETENTION_DAYS if max_age_days is None else max_age_days)
    max_bytes = _env_int("FAIL_ARTIFACT_MAX_BYTES", FAIL_ARTIFACT_MAX_BYTES if max_bytes is None else max_bytes)
    target_bytes = _env_int("FAIL_ARTIFACT_TARGET_BYTES", FAIL_ARTIFACT_TARGET_BYTES if target_bytes is None else target_bytes)
    if target_bytes > max_bytes:
        target_bytes = max_bytes
    fail_dir = _safe_fail_artifact_dir(data_folder)
    result = {"artifact_dir": str(fail_dir), "exists": fail_dir.exists(), "before_bytes": 0, "after_bytes": 0, "before_count": 0, "after_count": 0, "deleted_old_count": 0, "deleted_old_bytes": 0, "deleted_size_count": 0, "deleted_size_bytes": 0, "removed_empty_dirs": 0}
    if not fail_dir.exists():
        return result
    info = []
    for p in _iter_artifact_files(fail_dir):
        try:
            st = p.stat()
        except OSError:
            continue
        info.append((p, st.st_mtime, st.st_size))
    result["before_count"] = len(info)
    result["before_bytes"] = sum(size for _, _, size in info)
    cutoff = time.time() - max_age_days * 86400
    kept = []
    for p, mtime, size in info:
        if mtime < cutoff:
            try:
                p.unlink()
                result["deleted_old_count"] += 1
                result["deleted_old_bytes"] += size
            except OSError as exc:
                if logger:
                    logger(f"Không thể xóa fail artifact cũ {p}: {exc}", level=logging.WARNING)
                kept.append((p, mtime, size))
        else:
            kept.append((p, mtime, size))
    current_bytes = sum(size for p, _, size in kept if p.exists())
    if current_bytes > max_bytes:
        for p, _, size in sorted(kept, key=lambda item: item[1]):
            if current_bytes <= target_bytes:
                break
            if not p.exists():
                continue
            try:
                p.unlink()
                current_bytes -= size
                result["deleted_size_count"] += 1
                result["deleted_size_bytes"] += size
            except OSError as exc:
                if logger:
                    logger(f"Không thể xóa fail artifact để giảm dung lượng {p}: {exc}", level=logging.WARNING)
    result["removed_empty_dirs"] = _remove_empty_dirs(fail_dir)
    remaining = _iter_artifact_files(fail_dir)
    result["after_count"] = len(remaining)
    total = 0
    for p in remaining:
        try:
            total += p.stat().st_size
        except OSError:
            pass
    result["after_bytes"] = total
    if logger:
        logger(
            "Fail artifact cleanup: "
            f"dir={result['artifact_dir']}, before={result['before_count']} files/{result['before_bytes']} bytes, "
            f"after={result['after_count']} files/{result['after_bytes']} bytes, "
            f"deleted_old={result['deleted_old_count']}, deleted_size={result['deleted_size_count']}",
            level=logging.INFO,
        )
    return result


def maybe_cleanup_fail_artifacts(*, data_folder=None, force=False):
    global _LAST_CLEANUP_AT
    now = time.time()
    if force or now - _LAST_CLEANUP_AT >= _CLEANUP_INTERVAL_SECONDS:
        _LAST_CLEANUP_AT = now
        return cleanup_fail_artifacts(data_folder=data_folder)
    return None


class FailArtifactMixin:
    """Capture minimal fail diagnostics without allowing unlimited artifact growth."""

    def _get_fail_artifact_dir(self, data_folder=None):
        base = get_fail_artifact_dir(data_folder=data_folder or DATA_FOLDER)
        os.makedirs(base, exist_ok=True)
        return base

    def capture_fail_artifact(self, *, phase, reason, group_name=None, extra=None, data_folder=None):
        group_name = group_name or getattr(self, "group_name", None) or "group"
        artifact = {"phase": phase, "reason": reason, "group_name": group_name, "timestamp": datetime.now().isoformat(), "current_url": None, "page_title": None, "screenshot_path": None, "sidecar_json_path": None, "artifacts_enabled": fail_artifacts_enabled(), "screenshot_throttled": False}
        artifact.update(extra or {})
        driver = getattr(self, "driver", None)
        if driver is not None:
            try:
                artifact["current_url"] = driver.current_url
            except Exception:
                pass
            try:
                artifact["page_title"] = driver.title
            except Exception:
                pass
        if not artifact["artifacts_enabled"]:
            log(f"Fail artifact skipped (disabled): phase={artifact['phase']}, reason={artifact['reason']}, url={artifact['current_url']}, title={artifact['page_title']}", level=logging.WARNING)
            return artifact
        try:
            maybe_cleanup_fail_artifacts(data_folder=data_folder or DATA_FOLDER)
        except Exception as exc:
            log(f"Không thể cleanup fail artifacts trước khi capture: {exc}", level=logging.WARNING)
        if driver is not None:
            if should_capture_fail_artifact(group_name, phase, reason):
                try:
                    path = build_fail_artifact_path(datetime.now(), group_name, phase, reason, "png", data_folder=data_folder or DATA_FOLDER)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    if hasattr(driver, "save_screenshot") and driver.save_screenshot(path):
                        artifact["screenshot_path"] = path
                except Exception as e:
                    log(f"Không thể chụp fail artifact screenshot: {e}", level=logging.WARNING)
            else:
                artifact["screenshot_throttled"] = True
        try:
            json_path = build_fail_artifact_path(datetime.now(), group_name, phase, reason, "json", data_folder=data_folder or DATA_FOLDER)
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(artifact, f, ensure_ascii=False, indent=2)
            artifact["sidecar_json_path"] = json_path
        except Exception as e:
            log(f"Không thể ghi fail artifact sidecar json: {e}", level=logging.WARNING)
        log(f"Fail artifact captured: phase={artifact['phase']}, reason={artifact['reason']}, url={artifact['current_url']}, title={artifact['page_title']}, screenshot={artifact['screenshot_path']}, sidecar={artifact['sidecar_json_path']}, screenshot_throttled={artifact['screenshot_throttled']}", level=logging.WARNING)
        return artifact
