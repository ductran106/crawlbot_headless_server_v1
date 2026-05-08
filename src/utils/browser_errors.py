"""Các helper nhận diện lỗi browser/WebDriver để dùng chung.

Phase 1 cleanup:
- gom các browser-crash signatures về một chỗ
- không đổi flow recover hiện có
"""

BROWSER_DEAD_ERROR_SIGNATURES = (
    "tab crashed",
    "crashed",
    "read timed out",
    "connectionpool",
    "connection refused",
    "not connected",
    "target window already closed",
    "remotedisconnected",
    "connection aborted",
    "protocolerror",
    "timed out",
)


def is_browser_dead_error(exc) -> bool:
    """True nếu lỗi do tab crash / timeout / mất kết nối Chrome/WebDriver."""
    if exc is None:
        return False
    message = str(exc).lower()
    return any(signature in message for signature in BROWSER_DEAD_ERROR_SIGNATURES)
