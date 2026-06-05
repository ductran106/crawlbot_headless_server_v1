import json
import os
from datetime import datetime

from .config import DATA_FOLDER
from .logger import log, logging
from .artifact_paths import build_fail_artifact_path, get_fail_artifact_dir


class FailArtifactMixin:
    """Thu thập artifact tối thiểu khi fail để lane đỡ mù.

    Artifact mặc định:
    - screenshot (nếu chụp được)
    - current_url
    - page_title
    - reason
    - phase/group_name/timestamp
    """

    def _get_fail_artifact_dir(self):
        base = os.path.join(DATA_FOLDER, "logs", "fail-artifacts")
        os.makedirs(base, exist_ok=True)
        return base

    def capture_fail_artifact(self, *, phase, reason, group_name=None, extra=None):
        group_name = group_name or getattr(self, "group_name", None) or "group"
        artifact = {
            "phase": phase,
            "reason": reason,
            "group_name": group_name,
            "timestamp": datetime.now().isoformat(),
            "current_url": None,
            "page_title": None,
            "screenshot_path": None,
            "sidecar_json_path": None,
        }
        artifact.update(extra or {})

        fail_dir = get_fail_artifact_dir(data_folder=DATA_FOLDER)
        os.makedirs(fail_dir, exist_ok=True)

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
            try:
                path = build_fail_artifact_path(
                    datetime.now(),
                    group_name,
                    phase,
                    reason,
                    "png",
                    data_folder=DATA_FOLDER,
                )
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if hasattr(driver, "save_screenshot") and driver.save_screenshot(path):
                    artifact["screenshot_path"] = path
            except Exception as e:
                log(f"Không thể chụp fail artifact screenshot: {e}", level=logging.WARNING)

        try:
            json_path = build_fail_artifact_path(
                datetime.now(),
                group_name,
                phase,
                reason,
                "json",
                data_folder=DATA_FOLDER,
            )
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(artifact, f, ensure_ascii=False, indent=2)
            artifact["sidecar_json_path"] = json_path
        except Exception as e:
            log(f"Không thể ghi fail artifact sidecar json: {e}", level=logging.WARNING)

        log(
            f"Fail artifact captured: phase={artifact['phase']}, reason={artifact['reason']}, "
            f"url={artifact['current_url']}, title={artifact['page_title']}, screenshot={artifact['screenshot_path']}, "
            f"sidecar={artifact['sidecar_json_path']}",
            level=logging.WARNING,
        )
        return artifact
