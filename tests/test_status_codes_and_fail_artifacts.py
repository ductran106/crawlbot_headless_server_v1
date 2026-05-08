import os
import tempfile
import unittest
from unittest.mock import patch

from src.utils.fail_artifacts import FailArtifactMixin
from src.utils.status_codes import (
    GROUP_MISMATCH,
    GROUP_SEARCH_EMPTY,
    LOGIN_STATE_UNKNOWN,
    QR_VISIBLE,
    READY_IN_TARGET_GROUP,
    classify_reason,
)


class DummyDriver:
    current_url = "https://chat.zalo.me/mock"
    title = "Mock Zalo"

    def save_screenshot(self, path):
        with open(path, "wb") as f:
            f.write(b"png")
        return True


class DummyFailArtifactOwner(FailArtifactMixin):
    def __init__(self):
        self.driver = DummyDriver()
        self.group_name = "Nhóm Test"


class StatusCodesAndFailArtifactsTests(unittest.TestCase):
    def test_classify_reason_groups_are_stable(self):
        self.assertEqual(classify_reason(READY_IN_TARGET_GROUP), "ready")
        self.assertEqual(classify_reason(QR_VISIBLE), "login")
        self.assertEqual(classify_reason(LOGIN_STATE_UNKNOWN), "login")
        self.assertEqual(classify_reason(GROUP_MISMATCH), "group")
        self.assertEqual(classify_reason(GROUP_SEARCH_EMPTY), "group")
        self.assertEqual(classify_reason("something-new"), "unknown")

    def test_capture_fail_artifact_collects_minimum_fields(self):
        owner = DummyFailArtifactOwner()
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch.object(owner, "_get_fail_artifact_dir", return_value=tmpdir):
            artifact = owner.capture_fail_artifact(
                phase="regression.group_mismatch",
                reason=GROUP_MISMATCH,
                group_name="Nhóm Test",
            )

            self.assertEqual(artifact["phase"], "regression.group_mismatch")
            self.assertEqual(artifact["reason"], GROUP_MISMATCH)
            self.assertEqual(artifact["current_url"], "https://chat.zalo.me/mock")
            self.assertEqual(artifact["page_title"], "Mock Zalo")
            self.assertTrue(artifact["screenshot_path"].endswith(".png"))
            self.assertTrue(os.path.exists(artifact["screenshot_path"]))
            self.assertTrue(artifact["sidecar_json_path"].endswith(".json"))
            self.assertTrue(os.path.exists(artifact["sidecar_json_path"]))


if __name__ == "__main__":
    unittest.main()
