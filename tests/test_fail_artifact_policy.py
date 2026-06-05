
import os
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils.fail_artifacts import (
    FailArtifactMixin,
    cleanup_fail_artifacts,
    should_capture_fail_artifact,
    reset_fail_artifact_throttle_state,
)


class DummyDriver:
    current_url = "https://chat.zalo.me/mock"
    title = "Mock Zalo"
    calls = 0

    def save_screenshot(self, path):
        type(self).calls += 1
        Path(path).write_bytes(b"png")
        return True


class Owner(FailArtifactMixin):
    def __init__(self):
        self.driver = DummyDriver()
        self.group_name = "Nhóm Test"


class FailArtifactPolicyTests(unittest.TestCase):
    def setUp(self):
        reset_fail_artifact_throttle_state()
        DummyDriver.calls = 0

    def test_env_disable_skips_screenshot_and_json_but_returns_loggable_artifact(self):
        with tempfile.TemporaryDirectory() as data_dir, patch.dict(os.environ, {"ENABLE_FAIL_ARTIFACTS": "false"}, clear=False):
            artifact = Owner().capture_fail_artifact(phase="auth.check_login_status", reason="login_state_unknown", group_name="Nhóm Test", data_folder=data_dir)
            self.assertFalse((Path(data_dir)/"logs"/"fail-artifacts").exists())
            self.assertIsNone(artifact["screenshot_path"])
            self.assertIsNone(artifact["sidecar_json_path"])
            self.assertEqual(DummyDriver.calls, 0)
            self.assertFalse(artifact["artifacts_enabled"])

    def test_repeated_same_error_saves_only_one_screenshot_per_30_minutes_but_json_keeps_logging_context(self):
        with tempfile.TemporaryDirectory() as data_dir, patch.dict(os.environ, {"ENABLE_FAIL_ARTIFACTS": "true"}, clear=False):
            first = Owner().capture_fail_artifact(phase="navigation.search", reason="group_search_empty", group_name="Nhóm Test", data_folder=data_dir)
            second = Owner().capture_fail_artifact(phase="navigation.search", reason="group_search_empty", group_name="Nhóm Test", data_folder=data_dir)
            self.assertTrue(first["screenshot_path"])
            self.assertIsNone(second["screenshot_path"])
            self.assertEqual(DummyDriver.calls, 1)
            self.assertTrue(second["screenshot_throttled"])
            self.assertTrue(second["sidecar_json_path"])

    def test_throttle_allows_same_error_after_30_minutes(self):
        with tempfile.TemporaryDirectory() as data_dir, patch.dict(os.environ, {"ENABLE_FAIL_ARTIFACTS": "true"}, clear=False):
            self.assertTrue(should_capture_fail_artifact("g", "p", "r", now=1000))
            self.assertFalse(should_capture_fail_artifact("g", "p", "r", now=1000 + 60))
            self.assertTrue(should_capture_fail_artifact("g", "p", "r", now=1000 + 1801))

    def test_cleanup_removes_old_files_and_reduces_size_to_target(self):
        with tempfile.TemporaryDirectory() as data_dir:
            art = Path(data_dir)/"logs"/"fail-artifacts"
            art.mkdir(parents=True)
            old = art/"old.json"
            old.write_bytes(b"x")
            old_ts = time.time() - 15*24*3600
            os.utime(old, (old_ts, old_ts))
            for idx in range(5):
                p = art/f"big{idx}.bin"
                p.write_bytes(b"x" * 1024)
                ts = time.time() - (100 - idx)
                os.utime(p, (ts, ts))
            result = cleanup_fail_artifacts(data_folder=data_dir, max_age_days=14, max_bytes=3*1024, target_bytes=2*1024)
            self.assertGreaterEqual(result["deleted_old_count"], 1)
            self.assertLessEqual(result["after_bytes"], 2*1024)
            self.assertFalse(old.exists())

if __name__ == "__main__":
    unittest.main()
