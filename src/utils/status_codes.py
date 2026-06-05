"""Reason-code taxonomy dùng chung cho crawlbot lane.

Mục tiêu:
- tránh hardcode string reason rải rác
- gom semantics login/group/navigation/status vào một chỗ
- giữ compatibility: caller vẫn có thể đọc chuỗi `reason`
"""

READY_IN_TARGET_GROUP = "ready-in-target-group"
ALREADY_LOGGED_IN = "already-logged-in"
QR_VISIBLE = "qr-visible"
LOGIN_STATE_UNKNOWN = "login-state-unknown"
GROUP_MISMATCH = "group-mismatch"
GROUP_STATE_UNKNOWN = "group-state-unknown"
STATUS_CHECK_ERROR = "status-check-error"
GROUP_SEARCH_EMPTY = "group-search-empty"
GROUP_OPENED_UNVERIFIED = "group-opened-unverified"
GROUP_OPENED_USABLE_UNVERIFIED = "group-opened-usable-unverified"
GROUP_OPENED_AT_NAVIGATION = "group-opened-at-navigation"
NAVIGATION_STALL = "navigation-stall"
RECONNECT_HEADER_UNVERIFIED = "reconnect-header-unverified"
RECONNECT_USABLE_UNVERIFIED = "reconnect-usable-unverified"
LOGIN_DETECTED = "login-detected"
QR_EXPIRED = "qr-expired"
QR_SEND_ATTEMPT = "qr-send-attempt"
QR_SENT = "qr-sent"
WAITING_FOR_LOGIN = "waiting-for-login"
LOGIN_TIMEOUT = "login-timeout"

REASON_GROUPS = {
    "ready": {READY_IN_TARGET_GROUP, ALREADY_LOGGED_IN, GROUP_OPENED_AT_NAVIGATION, LOGIN_DETECTED},
    "login": {QR_VISIBLE, LOGIN_STATE_UNKNOWN, QR_EXPIRED, QR_SEND_ATTEMPT, QR_SENT, WAITING_FOR_LOGIN, LOGIN_TIMEOUT},
    "group": {
        GROUP_MISMATCH,
        GROUP_STATE_UNKNOWN,
        GROUP_SEARCH_EMPTY,
        GROUP_OPENED_UNVERIFIED,
        GROUP_OPENED_USABLE_UNVERIFIED,
        NAVIGATION_STALL,
        RECONNECT_HEADER_UNVERIFIED,
        RECONNECT_USABLE_UNVERIFIED,
    },
    "error": {STATUS_CHECK_ERROR},
}


def classify_reason(reason: str) -> str:
    reason = str(reason or "").strip()
    for group_name, reasons in REASON_GROUPS.items():
        if reason in reasons:
            return group_name
    return "unknown"
