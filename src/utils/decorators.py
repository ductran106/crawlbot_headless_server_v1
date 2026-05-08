# src/utils/decorators.py
import time
import functools
from ..utils.browser_errors import is_browser_dead_error
from ..utils.logger import log, logging
from ..utils.signals import is_terminating

def retry_on_webdriver_error(max_retries=3, delay=1):
    """
    Decorator để tự động thử lại hàm khi có lỗi WebDriver
    
    Args:
        max_retries (int): Số lần thử lại tối đa
        delay (int): Thời gian chờ giữa các lần thử (giây)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from ..browser.driver import browser_manager
            
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    if is_terminating():
                        log(f"Bỏ retry {func.__name__} vì hệ thống đang shutdown.", level=logging.DEBUG)
                        if last_exception:
                            raise last_exception
                        raise RuntimeError(f"shutdown-in-progress:{func.__name__}")

                    # Kiểm tra sức khỏe của WebDriver trước khi thực hiện hàm
                    if attempt > 0 and not browser_manager.check_driver_health():
                        if is_terminating():
                            log(f"Bỏ restart/recover trước retry {func.__name__} vì đang shutdown.", level=logging.DEBUG)
                            raise RuntimeError(f"shutdown-in-progress:{func.__name__}")
                        log(f"WebDriver không khỏe mạnh, đang khởi động lại...", level=logging.WARNING)
                        browser_manager.restart_driver()
                        browser_manager.recover_session()
                    
                    # Thực hiện hàm
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    # Kiểm tra các lỗi liên quan đến WebDriver (bao gồm tab crashed, read timed out)
                    error_msg = str(e).lower()
                    webdriver_errors = [
                        "stale element", "no such element", "timeout", "timed out",
                        "webdriver exception", "not connected", "connection refused",
                        "tab crashed", "crashed", "connectionpool", "read timed out",
                        "remotedisconnected", "connection aborted", "protocolerror"
                    ]

                    # Tab crashed / mất kết nối: re-raise ngay để main loop recover và cập nhật refs (navigator, crawlers)
                    if is_browser_dead_error(e):
                        log(f"Lỗi browser (tab crashed/timeout): {str(e)}. Để main loop khôi phục.", level=logging.WARNING)
                        raise
                    
                    if any(err in error_msg for err in webdriver_errors):
                        if attempt < max_retries:
                            log(f"Lỗi WebDriver: {str(e)}. Thử lại lần {attempt + 1}/{max_retries}", 
                                level=logging.WARNING)
                            time.sleep(delay * (attempt + 1))
                        else:
                            log(f"Đã thử lại {max_retries} lần không thành công: {str(e)}", 
                                level=logging.ERROR)
                            raise
                    else:
                        raise
            
            # Nếu đã thử tất cả các lần và vẫn thất bại
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator