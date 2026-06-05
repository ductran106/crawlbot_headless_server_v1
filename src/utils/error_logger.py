# Module lưu log lỗi chi tiết (traceback + context) để dễ cung cấp khi debug
# Khi tab/browser crash sẽ ghi thêm CRASH DIAGNOSTICS (chromedriver log + bộ nhớ) để suy lý nguyên nhân
# src/utils/error_logger.py
import os
import traceback
from datetime import datetime
from .config import DATA_FOLDER, COMPUTER_NAME, LOGS_FOLDER
from .artifact_paths import build_error_log_path

ERROR_LOGS_DIR = os.path.join(DATA_FOLDER, "logs", "errors")
SEPARATOR = "=" * 80
CHROMEDRIVER_LOG_TAIL_LINES = 80


def _ensure_error_log_dir():
    os.makedirs(ERROR_LOGS_DIR, exist_ok=True)


def _get_error_log_path():
    """File log lỗi theo ngày: data/logs/errors/error_YYYY-MM-DD.log"""
    _ensure_error_log_dir()
    return build_error_log_path()


def _is_crash_error(exc: BaseException) -> bool:
    """True nếu lỗi liên quan tab/browser crash hoặc mất kết nối (để ghi thêm diagnostics)."""
    if exc is None:
        return False
    s = str(exc).lower()
    return any(x in s for x in [
        "tab crashed", "crashed", "renderer", "target window already closed",
        "remotedisconnected", "connection aborted", "protocolerror"
    ])


def _get_crash_diagnostics() -> list:
    """
    Thu thập thông tin giúp suy lý nguyên nhân crash:
    - Vài chục dòng cuối chromedriver.log (thường có lý do crash / OOM / GPU)
    - Bộ nhớ hệ thống và process hiện tại (nghi ngờ OOM)
    """
    lines = []
    # Đuôi file chromedriver.log
    try:
        chromedriver_log = os.path.join(LOGS_FOLDER, "chromedriver.log")
        if os.path.isfile(chromedriver_log):
            with open(chromedriver_log, "r", encoding="utf-8", errors="replace") as f:
                tail = f.readlines()
            tail = tail[-CHROMEDRIVER_LOG_TAIL_LINES:] if len(tail) > CHROMEDRIVER_LOG_TAIL_LINES else tail
            lines.append("CHROMEDRIVER LOG (last lines):")
            lines.append("-" * 40)
            lines.extend(t.rstrip() for t in tail)
            lines.append("")
        else:
            lines.append("CHROMEDRIVER LOG: file not found")
    except Exception as e:
        lines.append(f"CHROMEDRIVER LOG: error reading: {e}")
    # Bộ nhớ hệ thống
    try:
        import psutil
        vm = psutil.virtual_memory()
        lines.append("MEMORY:")
        lines.append(f"  total={vm.total // (1024*1024)}MB available={vm.available // (1024*1024)}MB "
                     f"used={vm.percent}%")
        p = psutil.Process()
        pm = p.memory_info()
        lines.append(f"  current_process RSS={pm.rss // (1024*1024)}MB")
    except Exception as e:
        lines.append(f"MEMORY: error: {e}")
    return lines


def log_error(exc: BaseException, context: dict = None, extra_message: str = None):
    """
    Ghi lỗi ra file riêng với full traceback và context.
    Khi lỗi là tab/browser crash sẽ ghi thêm CRASH DIAGNOSTICS (chromedriver log + bộ nhớ) để suy lý nguyên nhân.

    Args:
        exc: Exception vừa bắt được
        context: Dict thông tin bổ sung (vd: group_name, current_url, page_title, phase, ...)
        extra_message: Chuỗi mô tả ngắn thêm (vd: "Trong crawl_step")
    """
    try:
        path = _get_error_log_path()
        lines = [
            SEPARATOR,
            f"TIME: {datetime.now().isoformat()}",
            f"HOST: {COMPUTER_NAME}",
        ]
        if extra_message:
            lines.append(f"NOTE: {extra_message}")
        if context:
            lines.append("CONTEXT:")
            for k, v in (context or {}).items():
                lines.append(f"  {k}: {v}")
        lines.extend([
            f"EXCEPTION: {type(exc).__name__}: {exc}",
            "",
            "TRACEBACK:",
            traceback.format_exc(),
        ])
        # Khi là lỗi crash: thêm phần CRASH DIAGNOSTICS để dễ tìm nguyên nhân
        if _is_crash_error(exc):
            lines.append("")
            lines.append("CRASH DIAGNOSTICS (lý do crash có thể nằm trong chromedriver log / memory):")
            lines.append("-" * 40)
            lines.extend(_get_crash_diagnostics())
        lines.extend([SEPARATOR, ""])
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
        # Ghi cả vào logger thường để console/file log chính cũng thấy
        from .logger import log
        import logging
        log(f"[Error log đã lưu] {type(exc).__name__}: {exc} -> {path}", level=logging.ERROR)
    except Exception as e:
        # Tránh crash khi ghi log lỗi thất bại
        import logging
        logging.getLogger("zalo_crawler").error(f"Không thể ghi error log: {e}")


def get_error_log_path_for_today():
    """Trả về đường dẫn file error log của hôm nay (để user biết file nào gửi)."""
    _ensure_error_log_dir()
    return _get_error_log_path()
