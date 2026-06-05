# Xử lý tín hiệu hệ thống
# src/utils/signals.py
import signal
import sys
from .logger import log, logging

# Biến toàn cục để kiểm soát việc dừng chương trình
is_shutting_down = False
shutdown_reason = None


def init_signal_handlers():
    """Đăng ký các handler xử lý tín hiệu hệ thống"""
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Terminate signal
    log("Đã đăng ký xử lý tín hiệu hệ thống")


def _signal_safe_notice(message):
    try:
        sys.stderr.write(message + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def request_graceful_shutdown(reason=None):
    """Kích hoạt graceful shutdown từ app/UI mà không cần gửi OS signal."""
    global is_shutting_down, shutdown_reason
    if not is_shutting_down:
        is_shutting_down = True
        shutdown_reason = reason or "app-request"
        log(f"Đã nhận yêu cầu dừng an toàn (reason={shutdown_reason})", level=logging.WARNING)
        _signal_safe_notice("Đang dừng chương trình an toàn, vui lòng đợi quá trình hiện tại hoàn thành...")
        return True
    return False


def get_shutdown_reason():
    return shutdown_reason


def signal_handler(sig, frame):
    """Xử lý tín hiệu khi người dùng nhấn Ctrl+C hoặc khi hệ thống gửi tín hiệu terminate"""
    if not is_shutting_down:
        request_graceful_shutdown(reason=f"signal:{sig}")
    else:
        _signal_safe_notice("Đang buộc dừng chương trình...")
        sys.exit(1)


def is_terminating():
    """Kiểm tra xem chương trình có đang trong quá trình dừng không"""
    return is_shutting_down
