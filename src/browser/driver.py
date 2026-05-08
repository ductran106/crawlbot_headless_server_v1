# Khởi tạo và quản lý WebDriver
# src/browser/driver.py
import os
import time
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from ..utils.logger import log, logging
from ..utils.browser_errors import is_browser_dead_error
from ..utils.signals import is_terminating
from ..utils.config import (
    CHROME_USER_DATA_DIR,
    CHROME_DEBUG_PORT,
    COMPUTER_NAME,
    HEADLESS,
    CHROME_BINARY,
    CHROME_WINDOW_WIDTH,
    CHROME_WINDOW_HEIGHT,
    LOGS_FOLDER,
    DRIVER_PAGE_LOAD_TIMEOUT,
    DRIVER_SCRIPT_TIMEOUT,
    DRIVER_PROACTIVE_RECYCLE_MINUTES,
    DRIVER_PROACTIVE_RECYCLE_ROOM_CYCLES,
)


class BrowserManager:
    """Quản lý trình duyệt Chrome với Selenium WebDriver"""

    def __init__(self, user_data_dir=None, debug_port=None):
        """Khởi tạo BrowserManager với thư mục dữ liệu và cổng debug tùy chọn"""
        self.user_data_dir = user_data_dir or CHROME_USER_DATA_DIR
        self.debug_port = debug_port or CHROME_DEBUG_PORT
        self.driver = None
        self.driver_started_at = None
        self.driver_restart_count = 0
        self.last_recycle_reason = None
        self.last_proactive_recycle_at = 0.0
        self.last_proactive_recycle_room_cycle = None

    def preflight_close_conflicting_chrome_processes(self, timeout_seconds=5):
        """
        Preflight trước khi launch driver:
        đóng các tiến trình Chrome/Chromium có nguy cơ đụng lane crawler.

        Rule v1 an toàn:
        - cùng user-data-dir
        - hoặc cùng remote-debugging-port
        - tránh đóng tràn lan mọi cửa sổ Chrome không liên quan
        """
        try:
            user_data_dir = str(self.user_data_dir or "").lower()
            debug_port = str(self.debug_port or "").strip()
            candidates = []

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    cmdline = proc.info.get("cmdline") or []
                    cmd = " ".join(cmdline)
                    cmd_lower = cmd.lower()

                    if not name:
                        continue
                    if not any(x in name for x in ["chrome", "chromium"]):
                        continue

                    same_profile = bool(user_data_dir and user_data_dir in cmd_lower)
                    same_debug_port = bool(debug_port and f"--remote-debugging-port={debug_port}" in cmd_lower)

                    if same_profile or same_debug_port:
                        candidates.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if not candidates:
                log("Preflight Chrome cleanup: không thấy tiến trình xung đột cần đóng", level=logging.INFO)
                return 0

            for proc in candidates:
                try:
                    proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            _, alive = psutil.wait_procs(candidates, timeout=timeout_seconds)
            for proc in alive:
                try:
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            log(f"Preflight Chrome cleanup: đã đóng {len(candidates)} tiến trình xung đột trước khi chạy crawler")
            return len(candidates)
        except Exception as e:
            log(f"Lỗi preflight khi đóng Chrome xung đột: {str(e)}", level=logging.WARNING)
            return 0

    def _terminate_related_chrome_processes(self, timeout_seconds=5):
        """
        Cố gắng đóng các tiến trình Chrome/Chromium liên quan đến profile/port của tool này.
        An toàn hơn so với kill toàn bộ chrome trên máy.
        """
        try:
            user_data_dir = str(self.user_data_dir)
            debug_port = str(self.debug_port)
            candidates = []

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    cmdline = proc.info.get("cmdline") or []
                    cmd = " ".join(cmdline).lower()

                    if not name:
                        continue

                    if not any(x in name for x in ["chrome", "chromium"]):
                        continue

                    if (user_data_dir and user_data_dir.lower() in cmd) or (debug_port and debug_port in cmd):
                        candidates.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            for proc in candidates:
                try:
                    proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            _, alive = psutil.wait_procs(candidates, timeout=timeout_seconds)
            for proc in alive:
                try:
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if candidates:
                log(f"Đã đóng {len(candidates)} tiến trình Chrome/Chromium liên quan")
        except Exception as e:
            log(f"Lỗi khi đóng tiến trình Chrome/Chromium: {str(e)}", level=logging.WARNING)

    def get_chrome_driver(self, max_retries=3):
        """Khởi động Chrome WebDriver với profile cá nhân để giữ phiên đăng nhập"""
        retries = 0
        while retries < max_retries:
            try:
                self.preflight_close_conflicting_chrome_processes()

                os.makedirs(self.user_data_dir, exist_ok=True)
                log(f"Sử dụng Chrome user-data-dir: {self.user_data_dir}")

                chrome_options = Options()
                if CHROME_BINARY:
                    chrome_options.binary_location = CHROME_BINARY
                    log(f"Sử dụng Chrome binary: {CHROME_BINARY}")
                else:
                    import shutil
                    chrome_paths = [
                        '/usr/bin/google-chrome',
                        '/usr/bin/google-chrome-stable',
                        '/usr/bin/chromium-browser',
                        '/usr/bin/chromium',
                    ]
                    for path in chrome_paths:
                        if shutil.which(path) or os.path.exists(path):
                            chrome_options.binary_location = path
                            log(f"Tự động phát hiện Chrome tại: {path}")
                            break

                chrome_options.add_argument(f"--user-data-dir={self.user_data_dir}")
                chrome_options.add_argument(f"--remote-debugging-port={self.debug_port}")
                chrome_options.add_argument(f"--window-size={CHROME_WINDOW_WIDTH},{CHROME_WINDOW_HEIGHT}")

                if HEADLESS:
                    chrome_options.add_argument("--headless=new")
                    chrome_options.add_argument("--disable-gpu")
                    log("Chế độ headless đã được bật")

                if os.name != "nt":
                    chrome_options.add_argument("--no-sandbox")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                    chrome_options.add_argument("--disable-software-rasterizer")
                    chrome_options.add_argument("--disable-extensions")
                    chrome_options.add_argument("--disable-background-networking")
                    chrome_options.add_argument("--disable-background-timer-throttling")
                    chrome_options.add_argument("--disable-renderer-backgrounding")
                    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
                    chrome_options.add_argument("--disable-breakpad")
                    chrome_options.add_argument("--disable-component-update")
                    chrome_options.add_argument("--disable-default-apps")
                    chrome_options.add_argument("--disable-domain-reliability")
                    chrome_options.add_argument("--disable-features=TranslateUI")
                    chrome_options.add_argument("--disable-ipc-flooding-protection")
                    chrome_options.add_argument("--disable-notifications")
                    chrome_options.add_argument("--disable-sync")
                    chrome_options.add_argument("--metrics-recording-only")
                    chrome_options.add_argument("--mute-audio")
                    chrome_options.add_argument("--no-first-run")
                    chrome_options.add_argument("--safebrowsing-disable-auto-update")
                    chrome_options.add_argument("--enable-automation")
                    chrome_options.add_argument("--password-store=basic")
                    chrome_options.add_argument("--use-mock-keychain")
                    log("Đã thêm các flags cần thiết cho Linux server")

                chrome_options.add_argument("--log-level=3")
                chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

                log_file = os.path.join(LOGS_FOLDER, "chromedriver.log")
                os.makedirs(LOGS_FOLDER, exist_ok=True)
                service = Service(log_path=log_file)
                log(f"ChromeDriver log sẽ được lưu tại: {log_file}")

                log("Đang khởi tạo Chrome WebDriver...")
                self.driver = webdriver.Chrome(service=service, options=chrome_options)

                self.driver.set_page_load_timeout(DRIVER_PAGE_LOAD_TIMEOUT)
                self.driver.set_script_timeout(DRIVER_SCRIPT_TIMEOUT)
                log(f"Đã đặt page_load_timeout={DRIVER_PAGE_LOAD_TIMEOUT}s, script_timeout={DRIVER_SCRIPT_TIMEOUT}s")

                if not HEADLESS:
                    try:
                        screen_width = self.driver.execute_script("return window.screen.width")
                        screen_height = self.driver.execute_script("return window.screen.height")
                        window_width = int(screen_width * 2 / 3)
                        window_height = screen_height
                        window_x = screen_width - window_width
                        window_y = 0
                        self.driver.set_window_rect(x=window_x, y=window_y, width=window_width, height=window_height)
                    except Exception:
                        pass

                self.driver_started_at = time.time()
                self.last_recycle_reason = None
                log("Đã khởi tạo Chrome WebDriver thành công")
                return self.driver
            except Exception as e:
                retries += 1
                log(f"Lỗi khi khởi động Chrome (lần {retries}): {str(e)}", level=logging.ERROR)
                time.sleep(2)

        raise Exception("Không thể khởi động Chrome sau nhiều lần thử")

    def close_chrome(self):
        """Đóng tất cả các cửa sổ Chrome đang mở"""
        try:
            if self.driver:
                self.driver.quit()
                log("Đã đóng trình duyệt Chrome qua WebDriver")

            self._terminate_related_chrome_processes()
            return True
        except Exception as e:
            log(f"Lỗi khi đóng Chrome: {str(e)}", level=logging.ERROR)
            return False

    def get_driver(self):
        """Trả về WebDriver hiện tại hoặc tạo mới nếu chưa có"""
        if not self.driver:
            return self.get_chrome_driver()
        return self.driver

    def check_driver_health(self):
        """Kiểm tra trạng thái hoạt động mức transport/WebDriver."""
        try:
            if not self.driver:
                log("WebDriver không tồn tại, cần khởi tạo mới", level=logging.WARNING)
                return False

            self.driver.execute_script("return document.readyState")
            return True
        except Exception as e:
            level = logging.DEBUG if is_terminating() and is_browser_dead_error(e) else logging.ERROR
            log(f"WebDriver không phản hồi: {str(e)}", level=level)
            return False

    def get_driver_uptime_seconds(self):
        if not self.driver_started_at:
            return 0.0
        return max(0.0, time.time() - float(self.driver_started_at))

    def should_proactively_recycle(self, *, room_cycle=None):
        """Quyết định có nên recycle browser chủ động trước khi tab crash hay không.

        Guard quan trọng: không được recycle lặp vô hạn sau khi đã vượt ngưỡng.
        - uptime-based recycle: chỉ cho phép lại sau khi đã qua thêm một chu kỳ recycle_minutes
        - room-cycle recycle: chỉ cho phép lại khi room_cycle tăng thêm ít nhất một block recycle_cycles
        """
        uptime_seconds = self.get_driver_uptime_seconds()
        recycle_minutes = max(0, int(DRIVER_PROACTIVE_RECYCLE_MINUTES or 0))
        recycle_cycles = max(0, int(DRIVER_PROACTIVE_RECYCLE_ROOM_CYCLES or 0))
        now = time.time()

        if recycle_minutes and uptime_seconds >= recycle_minutes * 60:
            if not self.last_proactive_recycle_at or (now - float(self.last_proactive_recycle_at)) >= recycle_minutes * 60:
                self.last_proactive_recycle_at = now
                return True, f"uptime>={recycle_minutes}m"

        if recycle_cycles and room_cycle is not None and int(room_cycle) >= recycle_cycles:
            current_room_cycle = int(room_cycle)
            if self.last_proactive_recycle_room_cycle is None or (current_room_cycle - int(self.last_proactive_recycle_room_cycle)) >= recycle_cycles:
                self.last_proactive_recycle_room_cycle = current_room_cycle
                self.last_proactive_recycle_at = now
                return True, f"room_cycle>={recycle_cycles}"

        return False, None

    def check_zalo_surface_ready(self, timeout=8):
        """Kiểm tra browser không chỉ alive mà còn đã sẵn sàng ở bề mặt Zalo/search hoặc QR."""
        try:
            if not self.driver:
                return False, "no_driver"

            WebDriverWait(self.driver, max(1, int(timeout or 8))).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            search_ready = bool(self.driver.find_elements(By.ID, "contact-search-input"))
            if search_ready:
                return True, "search_ready"

            qr_ready = bool(self.driver.find_elements(By.CSS_SELECTOR, ".qrcode img"))
            if qr_ready:
                return True, "qr_ready"

            body_ready = bool(self.driver.find_elements(By.TAG_NAME, "body"))
            if body_ready:
                return True, "body_only"

            return False, "surface_unknown"
        except Exception as e:
            level = logging.DEBUG if is_terminating() and is_browser_dead_error(e) else logging.ERROR
            log(f"Bề mặt Zalo chưa sẵn sàng: {str(e)}", level=level)
            return False, "surface_error"

    def restart_driver(self, max_retries=3, reason=None):
        """Khởi động lại WebDriver khi gặp lỗi, có cleanup/wait rõ hơn để giảm restart fail."""
        if is_terminating():
            log("Bỏ restart WebDriver vì hệ thống đang shutdown.", level=logging.DEBUG)
            return False
        if reason:
            self.last_recycle_reason = reason
            log(f"Đang khởi động lại WebDriver... (reason={reason})", level=logging.WARNING)
        else:
            log("Đang khởi động lại WebDriver...", level=logging.WARNING)

        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            log("Không thể đóng WebDriver hiện tại", level=logging.WARNING)

        self.driver = None
        self._terminate_related_chrome_processes()
        time.sleep(1.0)

        for attempt in range(max_retries):
            try:
                if is_terminating():
                    log("Dừng vòng restart WebDriver vì hệ thống đang shutdown.", level=logging.DEBUG)
                    return False
                log(f"Nỗ lực khởi động lại WebDriver lần {attempt + 1}/{max_retries}")
                self.driver = self.get_chrome_driver()

                if self.check_driver_health():
                    self.driver_restart_count += 1
                    log("Khởi động lại WebDriver thành công")
                    return True
            except Exception as e:
                log(f"Lỗi khi khởi động lại WebDriver (lần {attempt + 1}): {str(e)}", level=logging.ERROR)

            time.sleep(2 * (attempt + 1))

        log("Không thể khởi động lại WebDriver sau nhiều lần thử", level=logging.CRITICAL)
        return False

    def recover_session(self, url=None, timeout=12):
        """
        Khôi phục phiên làm việc sau restart và chỉ pass khi bề mặt Zalo đã usable ở mức tối thiểu.
        """
        if is_terminating():
            log("Bỏ recover_session vì hệ thống đang shutdown.", level=logging.DEBUG)
            return False
        if not self.driver:
            log("Không có WebDriver để khôi phục phiên", level=logging.ERROR)
            return False

        try:
            target_url = url if url else "https://chat.zalo.me"
            log(f"Đang mở lại trang: {target_url}")
            self.driver.get(target_url)

            WebDriverWait(self.driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            ready, reason = self.check_zalo_surface_ready(timeout=timeout)
            if ready:
                log(f"Đã khôi phục phiên làm việc (surface={reason})")
                return True

            log(f"Khôi phục phiên nhưng bề mặt Zalo chưa sẵn sàng (surface={reason})", level=logging.WARNING)
            time.sleep(1.5)
            ready, reason = self.check_zalo_surface_ready(timeout=4)
            if ready:
                log(f"Đã khôi phục phiên làm việc sau retry ngắn (surface={reason})")
                return True

            log(f"Lỗi khi khôi phục phiên: Zalo surface not ready (surface={reason})", level=logging.ERROR)
            return False
        except Exception as e:
            log(f"Lỗi khi khôi phục phiên: {str(e)}", level=logging.ERROR)
            return False


# Tạo instance mặc định để sử dụng trong toàn bộ ứng dụng
browser_manager = BrowserManager()
