# Class MessageCrawler
# src/crawler/message_crawler.py
import os
import time
import threading
import socket
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from ..utils.logger import log, logging
from ..utils.config import (
    MESSAGE_CRAWL_INTERVAL,
    MAX_MESSAGES,
    DEFAULT_GROUP_NAME,
    AUTOSAVE_INTERVAL,
    COMPUTER_NAME,
    get_session_id,
    DATA_FOLDER,
    DB_NAME,
    get_group_data_folder,
    get_session_suffix,
    slugify,
    build_autosave_docx_name,
    build_final_docx_name,
    MULTI_ROOM_STABLE_WAIT_2ROOM,
    MULTI_ROOM_STABLE_WAIT_3ROOM,
)
from ..notification.telegram import send_notification, send_alert
from ..notification.messages import build_save_document_notification
from ..monitoring.keyword_monitor import KeywordMonitor
from .message_processor import MessageProcessor
from ..storage.docx_handler import DocxHandler
from ..storage.database import DatabaseManager
from ..utils.decorators import retry_on_webdriver_error
from ..utils.error_logger import log_error
from ..utils.browser_errors import is_browser_dead_error
from ..utils.fail_artifacts import FailArtifactMixin, maybe_cleanup_fail_artifacts
from ..utils.observability import build_event_payload, log_event
from ..utils.artifact_paths import build_autosave_temp_path
from ..utils.signals import is_terminating
from ..utils.status_codes import (
    GROUP_MISMATCH,
    GROUP_STATE_UNKNOWN,
    LOGIN_STATE_UNKNOWN,
    QR_VISIBLE,
    READY_IN_TARGET_GROUP,
    STATUS_CHECK_ERROR,
    classify_reason,
)

class MessageCrawler(FailArtifactMixin):
    """Class quản lý việc crawl tin nhắn từ Zalo"""
    
    def __init__(self, driver, browser_navigation, group_name=None, data_folder=None, room_count=1):
        """Khởi tạo MessageCrawler với WebDriver và ZaloNavigator"""
        self.driver = driver
        self.browser_navigation = browser_navigation
        self.group_name = group_name or DEFAULT_GROUP_NAME
        self.group_slug = slugify(self.group_name)
        self.room_count = max(1, int(room_count or 1))
        base_data_folder = data_folder or DATA_FOLDER
        self.data_folder = self._resolve_group_data_folder(base_data_folder)
        self.processed_messages = set()  # Lưu ID của tin nhắn đã xử lý
        self.unique_messages = []        # Danh sách tin nhắn đã lọc trùng
        self.running = True              # Cờ điều khiển tiến trình
        self.last_reload_time = time.time()
        self.last_collected_time = time.time()
        self.max_messages = MAX_MESSAGES
        self.external_stop_flag = lambda: False  # Hàm trả về cờ dừng từ bên ngoài
        self.console_logs = []
        self.notification_cooldowns = {}
        self.recovery_action_cooldowns = {}
        self.last_status_reason = None
        self.login_unknown_streak = 0
        self.group_reconnect_fail_streak = 0
        self.last_processed_count = 0
        self.last_visible_count = 0
        self.backlog_pressure = False
        self.possible_gap = False
        self.backlog_pressure_streak = 0
        self.possible_gap_streak = 0
        self.backlog_hot = False
        
        # Khởi tạo các thành phần phụ thuộc
        self.current_user_name = self._get_current_user_name()
        self.message_processor = MessageProcessor(driver, self.current_user_name)
        self.keyword_monitor = KeywordMonitor()
        self.docx_handler = DocxHandler(data_folder=self.data_folder)
        self.db_manager = DatabaseManager(db_path=os.path.join(self.data_folder, DB_NAME))
        
        # Thuộc tính cho việc lưu tự động
        self.last_save_time = time.time()
        self.autosave_interval = AUTOSAVE_INTERVAL
        self.save_lock = threading.Lock()
        
        # Biến quản lý phiên
        now = datetime.now()
        self.session_id = get_session_id(now)
        self.configure_autosave_filename(now)
        self.autosave_thread = None
        
        # Thêm các thuộc tính theo dõi sức khỏe
        self.last_health_check = time.time()
        self.consecutive_errors = 0
        #self.max_consecutive_errors = 5  # Khởi động lại sau 5 lỗi liên tiếp
        # Thêm biến theo dõi trạng thái Zalo
        self.last_status_check = time.time()
        
        log(f"Tên Zalo hiện tại: {self.current_user_name}")
        log(f"File autosave cho phiên này: {self.autosave_file_name}")
        log(f"Bắt đầu phiên: {self.session_id}")
        try:
            maybe_cleanup_fail_artifacts(data_folder=DATA_FOLDER, force=True)
        except Exception as e:
            log(f"Không thể cleanup fail artifacts khi khởi động crawler: {e}", level=logging.WARNING)
        
        # Khởi động giám sát từ khóa
        self.keyword_monitor.start_monitoring()

    def _cleanup_fail_artifacts_after_job(self):
        try:
            maybe_cleanup_fail_artifacts(data_folder=DATA_FOLDER, force=True)
        except Exception as e:
            log(f"Không thể cleanup fail artifacts sau job crawler: {e}", level=logging.WARNING)

    def _resolve_group_data_folder(self, base_folder):
        """Mỗi room có một thư mục dữ liệu riêng; tránh lồng thư mục nếu caller đã trỏ sẵn tới room folder."""
        normalized_base = os.path.normpath(base_folder)
        if os.path.basename(normalized_base) == self.group_slug:
            return normalized_base
        return get_group_data_folder(self.group_name, normalized_base)

    def _build_observability_payload(self, event_name, **fields):
        now = fields.pop("now", None) or datetime.now()
        return build_event_payload(event_name, now=now, group=self.group_name, **fields)

    def _log_observability_event(self, event_name, *, prefix=None, level=logging.INFO, **fields):
        payload = self._build_observability_payload(event_name, **fields)
        log_event(event_name, payload, prefix=prefix, level=level)
        return payload

    def _compute_backlog_state(self, visible_count, processed_count):
        """Heuristic nhẹ để biết room có đang nóng/backlog dày không."""
        visible_count = max(0, int(visible_count or 0))
        processed_count = max(0, int(processed_count or 0))
        # Nếu cửa sổ hiện tại rất dày hoặc vừa ingest được nhiều tin mới, coi như có áp lực backlog.
        self.backlog_pressure = visible_count >= 80 or processed_count >= 12
        # Nếu cửa sổ rất dày nhưng nhịp này ingest được rất ít, có khả năng đang bỏ sót/cần drain sâu hơn.
        self.possible_gap = visible_count >= 80 and processed_count <= 2

        if self.backlog_pressure:
            self.backlog_pressure_streak += 1
        else:
            self.backlog_pressure_streak = 0

        if self.possible_gap:
            self.possible_gap_streak += 1
        else:
            self.possible_gap_streak = 0

        self.backlog_hot = self.backlog_pressure_streak >= 2 or self.possible_gap_streak >= 2
        self.last_visible_count = visible_count
        self.last_processed_count = processed_count
        return {
            "group": self.group_name,
            "processed_count": processed_count,
            "visible_count": visible_count,
            "backlog_pressure": self.backlog_pressure,
            "possible_gap": self.possible_gap,
            "backlog_pressure_streak": self.backlog_pressure_streak,
            "possible_gap_streak": self.possible_gap_streak,
            "backlog_hot": self.backlog_hot,
        }

    def _is_expected_shutdown_webdriver_error(self, error):
        """Nhận diện lỗi WebDriver có thể bỏ qua khi đang shutdown/browser đã chết."""
        if not error:
            return False
        error_text = str(error)
        if self.external_stop_flag() and is_browser_dead_error(error):
            return True
        lowered = error_text.lower()
        if self.external_stop_flag() and (
            "connection refused" in lowered
            or "failed to establish a new connection" in lowered
            or "invalid session id" in lowered
            or "target window already closed" in lowered
        ):
            return True
        return False

    def _log_shutdown_webdriver_noise(self, context, error):
        log(
            f"({self.group_name}) Bỏ qua lỗi WebDriver lúc shutdown ở {context}: {str(error)}",
            level=logging.DEBUG,
        )

    def _should_quiet_shutdown_file_noise(self):
        return is_terminating()
    
    def _get_current_user_name(self):
        """Lấy tên người dùng từ tiêu đề trang Zalo"""
        try:
            page_title = self.driver.title
            if " - " in page_title and page_title.startswith("Zalo"):
                return page_title.split(" - ", 1)[1]
            return "Tôi"
        except Exception as e:
            log(f"Lỗi khi lấy tên người dùng từ tiêu đề: {str(e)}", level=logging.WARNING)
            return "Tôi"
    
    def configure_autosave_filename(self, now):
        """Tạo tên file autosave chuẩn dựa trên session hiện tại."""
        session_id = get_session_id(now)
        self.autosave_file_name = build_autosave_docx_name(session_id, COMPUTER_NAME, self.group_slug)
        self.autosave_log_file_name = now.strftime("%m-%d_%H-%M") + f'_{get_session_suffix(now)}-{COMPUTER_NAME}_{self.group_slug}_log.docx'

    def _get_multi_room_stable_wait_timeout(self):
        """Timeout chờ ổn định ngắn hơn trong multi-room mode để giảm dwell time mỗi room."""
        if self.room_count >= 3:
            return float(MULTI_ROOM_STABLE_WAIT_3ROOM)
        if self.room_count == 2:
            return float(MULTI_ROOM_STABLE_WAIT_2ROOM)
        return 3.0
    
    @retry_on_webdriver_error(max_retries=2)
    def scroll_for_messages(self):
        """Cuộn trang để tải thêm tin nhắn cũ và mới"""
        try:
            # Lưu lại số lượng tin nhắn trước khi cuộn
            initial_message_count = len(self.driver.find_elements(By.CSS_SELECTOR, ".chat-item"))
            
            # Cuộn lên đầu trước để lấy tin nhắn mới
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Cuộn xuống cuối để lấy tin nhắn cũ
            chat_container_script = """
                var chatContainer = document.querySelector(".chat-container, .conversation-list");
                if (chatContainer) {
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                    return true;
                }
                return false;
            """
            
            container_scrolled = self.driver.execute_script(chat_container_script)
            
            if not container_scrolled:
                # Thử cách khác nếu không tìm thấy chat container
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            time.sleep(1)
            
            # Kiểm tra xem có tin nhắn mới không
            new_message_count = len(self.driver.find_elements(By.CSS_SELECTOR, ".chat-item"))
            if new_message_count > initial_message_count:
                log(f"Đã tải thêm {new_message_count - initial_message_count} tin nhắn mới")
            
            return True
        except Exception as e:
            if self._is_expected_shutdown_webdriver_error(e):
                self._log_shutdown_webdriver_noise("scroll_for_messages", e)
                return False
            log(f"Lỗi khi cuộn trang: {str(e)}", level=logging.ERROR)
            return False

    @retry_on_webdriver_error(max_retries=2)
    def wait_for_messages_stable(self, timeout=5):
        """
        Đợi cho đến khi số lượng tin nhắn ổn định (không tăng thêm).
        Điều này giúp đảm bảo tin nhắn đã load đủ trước khi crawl.
        """
        try:
            start_time = time.time()
            last_count = 0
            stable_count = 0
            required_stable_checks = 2  # Phải ổn định 2 lần liên tiếp
            
            while time.time() - start_time < timeout:
                current_count = len(self.driver.find_elements(By.CSS_SELECTOR, ".chat-item"))
                
                if current_count == last_count:
                    stable_count += 1
                    if stable_count >= required_stable_checks:
                        log(f"({self.group_name}) Tin nhắn ổn định tại {current_count} item", level=logging.DEBUG)
                        return True
                else:
                    stable_count = 0
                    log(f"({self.group_name}) Đã tải {current_count} tin nhắn", level=logging.DEBUG)
                
                last_count = current_count
                time.sleep(0.5)
            
            log(f"({self.group_name}) Hết timeout chờ tin nhắn ổn định, tiếp tục với {last_count} item", level=logging.DEBUG)
            return True
        except Exception as e:
            if self._is_expected_shutdown_webdriver_error(e):
                self._log_shutdown_webdriver_noise("wait_for_messages_stable", e)
                return False
            log(f"({self.group_name}) Lỗi khi chờ tin nhắn ổn định: {str(e)}", level=logging.ERROR)
            return False

    @retry_on_webdriver_error(max_retries=2)
    def load_more_messages_buffer(self, scroll_count=3):
        """
        Scroll nhiều lần để chắc chắn load đủ tin nhắn.
        Tránh tình trạng tin nhắn vừa vào không kịp render.
        """
        try:
            for i in range(scroll_count):
                # Scroll lên để tải tin nhắn cũ
                self.driver.execute_script("""
                    var chatContainer = document.querySelector(".chat-container, .conversation-list");
                    if (chatContainer) {
                        chatContainer.scrollTop = 0;
                    } else {
                        window.scrollTo(0, 0);
                    }
                """)
                time.sleep(0.5)
                
                # Scroll xuống để tải tin nhắn mới
                self.driver.execute_script("""
                    var chatContainer = document.querySelector(".chat-container, .conversation-list");
                    if (chatContainer) {
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    } else {
                        window.scrollTo(0, document.body.scrollHeight);
                    }
                """)
                time.sleep(0.5)
            
            log(f"({self.group_name}) Đã scroll buffer {scroll_count} lần", level=logging.DEBUG)
            return True
        except Exception as e:
            log(f"({self.group_name}) Lỗi khi scroll buffer: {str(e)}", level=logging.ERROR)
            return False

    @retry_on_webdriver_error(max_retries=2)
    def refresh_page_safely(self):
        """Làm mới trang một cách an toàn với cơ chế thử lại"""
        log("Đang làm mới trang...")
        self.driver.refresh()
        time.sleep(5)  # Đợi trang tải lại
        
        # Truy cập lại nhóm chat
        return self.reconnect_to_group()

    def _send_notification_throttled(self, key, message, cooldown_seconds=120):
        """Gửi notification có cooldown để tránh spam khi lane chập chờn."""
        now = time.time()
        last_sent = self.notification_cooldowns.get(key, 0)
        if now - last_sent < cooldown_seconds:
            log(
                f"Bỏ qua notification '{key}' do còn trong cooldown {cooldown_seconds}s",
                level=logging.DEBUG,
            )
            return False
        send_notification(message)
        self.notification_cooldowns[key] = now
        return True

    def _should_run_recovery_action(self, key, cooldown_seconds):
        """Chặn recovery action lặp quá sát để tránh lane tự quẫy."""
        now = time.time()
        last_run = self.recovery_action_cooldowns.get(key, 0)
        if now - last_run < cooldown_seconds:
            log(
                f"Bỏ qua recovery action '{key}' do còn trong cooldown {cooldown_seconds}s",
                level=logging.DEBUG,
            )
            return False
        self.recovery_action_cooldowns[key] = now
        return True

    def _build_recovery_notification(self, status):
        """Reason-aware notify policy để alert đúng mức độ/context."""
        status = status or {}
        reason = status.get("reason", "unknown")
        page_state = status.get("page_state") or {}
        group_title = page_state.get("group_title", "")
        target_group = page_state.get("target_group") or self.group_name

        if reason == QR_VISIBLE:
            return {
                "key": "recovery.needs_qr",
                "message": f"🔐 Zalo đang hiện QR/login lại ({reason}). Cần khôi phục phiên trước khi crawl tiếp.",
                "cooldown": 180,
            }
        if reason == LOGIN_STATE_UNKNOWN:
            return {
                "key": "recovery.login_state_unknown",
                "message": f"🟡 Trạng thái login chưa rõ ({reason}). Đang thử refresh để phân loại lại.",
                "cooldown": 180,
            }
        if reason == GROUP_MISMATCH:
            current_group = f"'{group_title}'" if group_title else "group khác/không rõ"
            return {
                "key": "recovery.group_mismatch",
                "message": f"🧭 Đang lệch group: hiện ở {current_group}, cần về '{target_group}'.",
                "cooldown": 180,
            }
        if reason == GROUP_STATE_UNKNOWN:
            return {
                "key": "recovery.group_state_unknown",
                "message": f"🟠 Login vẫn còn nhưng chưa xác định được group hiện tại. Đang thử reconnect vào '{target_group}'.",
                "cooldown": 180,
            }
        return {
            "key": f"recovery.{reason}",
            "message": f"⚠️ Crawlbot gặp trạng thái cần recovery: {reason}.",
            "cooldown": 180,
        }

    def _format_status_context(self, status):
        """Chuẩn hóa breadcrumb ngắn cho log/debug khi lane đổi trạng thái."""
        status = status or {}
        page_state = status.get("page_state") or {}
        reason = status.get('reason', 'unknown')
        parts = [
            f"reason={reason}",
            f"reason_group={classify_reason(reason)}",
            f"logged_in={bool(status.get('logged_in'))}",
            f"in_group={bool(status.get('in_group'))}",
            f"needs_qr={bool(status.get('needs_qr'))}",
        ]
        if page_state.get("group_title"):
            parts.append(f"group_title='{page_state.get('group_title')}'")
        if page_state.get("target_group"):
            parts.append(f"target_group='{page_state.get('target_group')}'")
        return ", ".join(parts)

    def _log_status_transition(self, status, *, force=False, level=logging.INFO, prefix="Zalo status"):
        """Chỉ log khi reason đổi hoặc khi được force để tránh spam nhưng vẫn có breadcrumb."""
        reason = (status or {}).get("reason", "unknown")
        if (not force) and reason == self.last_status_reason:
            return
        self.last_status_reason = reason
        log(f"{prefix} -> {self._format_status_context(status)}", level=level)
        self._log_observability_event(
            "zalo_status_transition",
            prefix="ZALO_STATUS_TRANSITION",
            level=level,
            status_reason=reason,
            reason_group=classify_reason(reason),
            logged_in=bool((status or {}).get("logged_in")),
            in_group=bool((status or {}).get("in_group")),
            needs_qr=bool((status or {}).get("needs_qr")),
            group_title=((status or {}).get("page_state") or {}).get("group_title", ""),
            target_group=((status or {}).get("page_state") or {}).get("target_group", self.group_name),
            status_prefix=prefix,
        )

    def _sync_driver_references(self, new_driver):
        """Sau restart driver, đồng bộ lại mọi reference phụ thuộc để tránh stale handle."""
        if not new_driver:
            return False
        self.driver = new_driver
        self.browser_navigation.driver = new_driver
        self.message_processor.driver = new_driver
        return True

    def _restart_browser_session(self, *, reason, reopen_group=True):
        """Circuit breaker: restart browser sạch thay vì refresh/reconnect mù quá lâu."""
        from ..browser.driver import browser_manager

        log(f"({self.group_name}) Kích hoạt browser session restart: reason={reason}", level=logging.WARNING)
        self._log_observability_event(
            "browser_restart_requested",
            prefix="BROWSER_RESTART_REQUESTED",
            level=logging.WARNING,
            reason=reason,
            reopen_group=bool(reopen_group),
        )
        restarted = browser_manager.restart_driver()
        if not restarted:
            self._log_observability_event(
                "browser_restart_result",
                prefix="BROWSER_RESTART_RESULT",
                level=logging.ERROR,
                reason=reason,
                success=False,
                step="restart_driver",
            )
            return False
        self._sync_driver_references(browser_manager.get_driver())

        recovered = browser_manager.recover_session()
        if not recovered:
            self._log_observability_event(
                "browser_restart_result",
                prefix="BROWSER_RESTART_RESULT",
                level=logging.ERROR,
                reason=reason,
                success=False,
                step="recover_session",
            )
            return False

        self._sync_driver_references(browser_manager.get_driver())
        self.last_reload_time = time.time()
        self.last_health_check = time.time()

        reopen_ok = True
        if reopen_group:
            reopen_ok = bool(self.browser_navigation.find_and_access_group(self.group_name))
        self._log_observability_event(
            "browser_restart_result",
            prefix="BROWSER_RESTART_RESULT",
            level=logging.INFO if reopen_ok else logging.ERROR,
            reason=reason,
            success=bool(reopen_ok),
            step="reopen_group" if reopen_group else "recover_session",
        )
        return reopen_ok

    def _recover_from_status(self, status, notify=True):
        """Thực hiện recovery theo trạng thái đã phân loại, tránh chữa chung chung."""
        current_time = time.time()
        reason = status.get("reason", "unknown")
        page_state = status.get("page_state") or {}
        group_title = page_state.get("group_title", "")
        target_group = page_state.get("target_group") or self.group_name

        if not status.get("logged_in"):
            if status.get("needs_qr"):
                self.login_unknown_streak = 0
                if not self._should_run_recovery_action("action.needs_qr", cooldown_seconds=180):
                    return False
                log(f"Zalo cần QR/login lại (reason={reason}), đang thử đăng nhập lại...", level=logging.WARNING)
                if notify:
                    note = self._build_recovery_notification(status)
                    self._send_notification_throttled(
                        note["key"],
                        note["message"],
                        cooldown_seconds=note["cooldown"],
                    )

                from ..auth.login import ZaloAuthManager
                auth_manager = ZaloAuthManager(self.driver)
                login_success = auth_manager.wait_for_login()

                if login_success:
                    log("Đăng nhập lại thành công!")
                    find_success = self.browser_navigation.find_and_access_group(self.group_name)
                    if not find_success:
                        log("Không thể tìm nhóm chat sau khi đăng nhập lại", level=logging.ERROR)
                else:
                    log("Không thể đăng nhập lại", level=logging.ERROR)

                self.last_reload_time = current_time
                self.last_collected_time = current_time
                return login_success

            self.login_unknown_streak += 1
            if self.login_unknown_streak >= 2:
                self.capture_fail_artifact(
                    phase="recover_from_status.login_unknown",
                    reason=f"{reason}.streak_{self.login_unknown_streak}",
                    group_name=self.group_name,
                )
                log(
                    f"Trạng thái đăng nhập không xác định lặp {self.login_unknown_streak} lần, chuyển sang restart browser thay vì refresh mù.",
                    level=logging.WARNING,
                )
                return self._restart_browser_session(reason=f"login_unknown_streak_{self.login_unknown_streak}")

            if not self._should_run_recovery_action("action.unknown_state_refresh", cooldown_seconds=90):
                return False
            self.capture_fail_artifact(
                phase="recover_from_status.login_unknown",
                reason=reason,
                group_name=self.group_name,
            )
            log(f"Trạng thái đăng nhập không xác định (reason={reason}), làm mới trang để khôi phục...", level=logging.WARNING)
            if notify:
                note = self._build_recovery_notification(status)
                self._send_notification_throttled(
                    note["key"],
                    note["message"],
                    cooldown_seconds=note["cooldown"],
                )
            return self.refresh_page_safely()

        if not status.get("in_group"):
            self.login_unknown_streak = 0
            action_key = "action.out_of_group"
            notify_key = "recovery.out_of_group"
            notify_message = "🔍 Đã mất kết nối với nhóm chat, đang kết nối lại..."
            log_message = "Đã đăng nhập nhưng không ở trong nhóm chat, đang kết nối lại..."

            if reason == GROUP_MISMATCH:
                action_key = "action.group_mismatch"
                notify_key = "recovery.group_mismatch"
                notify_message = (
                    f"🔍 Đang ở sai nhóm ('{group_title}' -> cần '{target_group}'), đang chuyển lại..."
                    if group_title else f"🔍 Đang ở sai nhóm, đang chuyển lại '{target_group}'..."
                )
                log_message = (
                    f"Đã đăng nhập nhưng đang ở sai nhóm ('{group_title}' != '{target_group}'), đang chuyển lại..."
                    if group_title else f"Đã đăng nhập nhưng chưa ở đúng nhóm '{target_group}', đang chuyển lại..."
                )
            elif reason == GROUP_STATE_UNKNOWN:
                action_key = "action.group_state_unknown"
                notify_key = "recovery.group_state_unknown"
                notify_message = "🟡 Không xác định được group hiện tại, đang thử kết nối lại nhóm mục tiêu..."
                log_message = "Đã đăng nhập nhưng không xác định được group hiện tại, đang kết nối lại..."

            if not self._should_run_recovery_action(action_key, cooldown_seconds=120):
                return False
            self.capture_fail_artifact(
                phase=f"recover_from_status.{reason}",
                reason=reason,
                group_name=self.group_name,
                extra={"current_group_title": group_title, "target_group": target_group},
            )
            log(
                f"{log_message} ({self._format_status_context(status)})",
                level=logging.WARNING,
            )
            if notify:
                note = self._build_recovery_notification(status)
                self._send_notification_throttled(
                    note["key"],
                    note["message"],
                    cooldown_seconds=note["cooldown"],
                )
            find_success = self.browser_navigation.find_and_access_group(self.group_name)
            if find_success:
                self.group_reconnect_fail_streak = 0
                log("Đã kết nối lại với nhóm chat thành công")
                self._log_observability_event(
                    "group_reconnect_result",
                    prefix="GROUP_RECONNECT_RESULT",
                    level=logging.INFO,
                    reason=reason,
                    success=True,
                    current_group_title=group_title,
                    target_group=target_group,
                    fail_streak=self.group_reconnect_fail_streak,
                )
            else:
                self.group_reconnect_fail_streak += 1
                log("Không thể kết nối lại với nhóm chat", level=logging.ERROR)
                self._log_observability_event(
                    "group_reconnect_result",
                    prefix="GROUP_RECONNECT_RESULT",
                    level=logging.ERROR,
                    reason=reason,
                    success=False,
                    current_group_title=group_title,
                    target_group=target_group,
                    fail_streak=self.group_reconnect_fail_streak,
                )
                if self.group_reconnect_fail_streak >= 2:
                    log(
                        f"Reconnect/group recovery fail {self.group_reconnect_fail_streak} lần liên tiếp, chuyển sang restart browser sạch.",
                        level=logging.WARNING,
                    )
                    return self._restart_browser_session(reason=f"group_reconnect_fail_streak_{self.group_reconnect_fail_streak}")
            return find_success

        self.login_unknown_streak = 0
        self.group_reconnect_fail_streak = 0
        return True

    def create_initial_autosave_file(self):
        """Tạo file autosave ban đầu với header"""
        try:
            from docx import Document
            
            # Đảm bảo thư mục tồn tại
            if not os.path.exists(self.data_folder):
                os.makedirs(self.data_folder)
            
            # Đường dẫn file autosave - Một file duy nhất cho mỗi phiên/host/room
            self.autosave_file_name = build_autosave_docx_name(self.session_id, COMPUTER_NAME, self.group_slug)
            self.autosave_path = os.path.join(self.data_folder, self.autosave_file_name)
            
            # Tạo document mới với header
            doc = Document()
            
            # Thêm tiêu đề và thông tin
            now = datetime.now()
            doc.add_heading(f'Tin nhắn nhóm "{self.group_name}" - Phiên {self.session_id}', 0)
            doc.add_paragraph(f'Thời gian bắt đầu: {now.strftime("%d/%m/%Y %H:%M:%S")}')
            doc.add_paragraph(f'Máy tính: {socket.gethostname()}')
            doc.add_paragraph('_______________________________________________')
            
            # Lưu document
            doc.save(self.autosave_path)
            
            log(f"Đã tạo file autosave ban đầu: {self.autosave_path}")
            return True
        except Exception as e:
            log(f"Lỗi khi tạo file autosave ban đầu: {str(e)}", level=logging.ERROR)
            return False

    def append_single_message_to_autosave(self, message):
        """Thêm một tin nhắn duy nhất vào file autosave"""
        try:
            from docx import Document
            import os
            import shutil
            from datetime import datetime
            
            # Kiểm tra file tồn tại, nếu không tạo mới
            if not hasattr(self, 'autosave_path') or not os.path.exists(self.autosave_path):
                self.create_initial_autosave_file()
            
            # Tạo file tạm để ghi
            temp_path = build_autosave_temp_path(self.autosave_path)
            
            try:
                # Thử mở file hiện có
                doc = Document(self.autosave_path)
            except Exception as e:
                log(f"Lỗi khi mở file autosave: {str(e)}, đang tạo file mới...", level=logging.WARNING)
                # Nếu không mở được, tạo file mới
                doc = Document()
                # Thêm header cho file mới
                now = datetime.now()
                doc.add_heading(f'Tin nhắn nhóm "{self.group_name}" - Phiên {self.session_id}', 0)
                doc.add_paragraph(f'Thời gian bắt đầu: {now.strftime("%d/%m/%Y %H:%M:%S")}')
                doc.add_paragraph(f'Máy tính: {socket.gethostname()}')
                doc.add_paragraph('_______________________________________________')
            
            # Thêm tin nhắn mới vào document
            doc.add_paragraph(message)
            
            # Lưu vào file tạm trước
            doc.save(temp_path)
            
            # Nếu lưu file tạm thành công, thay thế file cũ
            if os.path.exists(temp_path):
                # Sao lưu file cũ nếu cần
                backup_path = self.autosave_path + ".backup"
                if os.path.exists(self.autosave_path):
                    shutil.copy2(self.autosave_path, backup_path)
                
                # Thay thế file cũ bằng file tạm
                shutil.move(temp_path, self.autosave_path)
                
                # Xóa file backup nếu không cần thiết
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                
                return True
            else:
                log("Không thể tạo file tạm", level=logging.ERROR)
                return False
                
        except Exception as e:
            log(f"Lỗi khi thêm tin nhắn vào file autosave: {str(e)}", level=logging.ERROR)
            # Nếu có lỗi, thử tạo file mới
            try:
                self.create_initial_autosave_file()
                return self.append_single_message_to_autosave(message)
            except:
                return False

    def append_to_autosave_file(self, messages):
        """Thêm danh sách tin nhắn vào file autosave"""
        try:
            from docx import Document
            
            # Kiểm tra file tồn tại, nếu không tạo mới
            import os
            if not hasattr(self, 'autosave_path') or not os.path.exists(self.autosave_path):
                self.create_initial_autosave_file()
                
            # Mở file hiện có
            doc = Document(self.autosave_path)
            
            # Thêm tin nhắn mới vào document
            for message in messages:
                doc.add_paragraph(message)
            
            # Lưu document
            doc.save(self.autosave_path)
            return True
        except Exception as e:
            log(f"Lỗi khi thêm tin nhắn vào file autosave: {str(e)}", level=logging.ERROR)
            return False

    def autosave_worker(self):
        """Thread worker để theo dõi việc lưu tự động định kỳ"""
        session_id = self.session_id  # Lưu ID phiên khi thread bắt đầu
        log(f"Bắt đầu luồng autosave cho phiên {session_id}")
        
        # Đảm bảo file autosave được tạo ban đầu
        if not hasattr(self, 'autosave_path'):
            self.create_initial_autosave_file()
        
        while self.running:
            try:
                # Kiểm tra xem phiên hiện tại có còn khớp với phiên khi luồng được tạo không
                current_time = datetime.now()
                current_session_id = get_session_id(current_time)
                
                if current_session_id != session_id:
                    log(f"Phiên đã thay đổi từ {session_id} sang {current_session_id}, dừng autosave")
                    break
                
                # Mỗi 3 phút, ghi log báo cáo là autosave vẫn đang hoạt động
                time.sleep(180)  # 3 phút
                log(f"Autosave vẫn đang hoạt động cho phiên {session_id} - lúc {datetime.now().strftime('%H:%M:%S')}")
                
            except Exception as e:
                log(f"Lỗi trong autosave_worker: {str(e)}", level=logging.ERROR)
                time.sleep(30)  # Nếu lỗi, đợi 30 giây trước khi thử lại
        
        log(f"Kết thúc luồng autosave cho phiên {session_id}")
    
    def save_current_data(self):
        """Lưu dữ liệu hiện tại vào file Word, ghi đè lên file autosave của phiên"""
        try:
            # Lưu tin nhắn vào file autosave
            if len(self.unique_messages) > 0:
                self.append_to_autosave_file(self.unique_messages)
                
                # Sau khi lưu, chỉ giữ lại 50 tin nhắn gần nhất
                self.unique_messages = self.unique_messages[-50:]
                
            log(f"Đã cập nhật dữ liệu autosave cho phiên {self.session_id} lúc {datetime.now().strftime('%H:%M:%S')}")
            return self.autosave_path, None
        except Exception as e:
            log(f"Lỗi khi lưu tự động: {str(e)}", level=logging.ERROR)
            return None, None
    
    def start_crawling(self):
        """Bắt đầu crawl tin nhắn"""
        try:
            # Khởi động autosave thread
            if hasattr(self, 'autosave_thread') and self.autosave_thread and self.autosave_thread.is_alive():
                log("Dừng luồng autosave cũ...")
                old_session_id = self.session_id
                self.session_id = f"STOPPING_{old_session_id}"
                self.autosave_thread.join(timeout=2)
            
            # Cập nhật ID phiên hiện tại
            now = datetime.now()
            self.session_id = get_session_id(now)
            log(f"Bắt đầu phiên mới: {self.session_id}")
            
            # Khởi động thread lưu tự động
            self.autosave_thread = threading.Thread(target=self.autosave_worker, daemon=True)
            self.autosave_thread.start()
            
            # Tính toán thời gian kết thúc dựa vào session window hiện tại
            now_tinh = datetime.now()
            target_time = get_next_session_boundary(now_tinh)
            run_time = get_session_run_seconds(now_tinh)
            log(f"Thời gian chạy code là trong (giây): {run_time}")
            
            # Lưu thời gian bắt đầu và kết thúc
            end_time = time.time() + run_time
            now_save = datetime.now()
            
            # Thêm biến theo dõi việc làm mới trang
            refresh_success = True
            
            # Vòng lặp chính để thu thập tin nhắn
            while time.time() < end_time and self.running:
                try:
                    # Kiểm tra cờ dừng từ bên ngoài
                    if self.external_stop_flag():
                        log("Nhận tín hiệu dừng, đang hoàn tất quá trình thu thập hiện tại...")
                        break
                    
                    current_time = time.time()
                    
                    # Kiểm tra trạng thái Zalo định kỳ
                    if current_time - self.last_status_check > 60:  # Kiểm tra mỗi phút
                        log("Kiểm tra trạng thái Zalo...", level=logging.DEBUG)
                        status = self.check_zalo_status()
                        self.last_status_check = current_time
                        if status.get("logged_in") and status.get("in_group"):
                            self._log_status_transition(status, level=logging.DEBUG)
                        else:
                            self._log_status_transition(status, level=logging.WARNING)
                            refresh_success = self._recover_from_status(status, notify=True)
                    
                    # Kiểm tra sức khỏe WebDriver sau lần làm mới trang trước đó không thành công
                    if not refresh_success:
                        from ..browser.driver import browser_manager
                        if not browser_manager.check_driver_health():
                            log("WebDriver không khỏe mạnh sau khi làm mới trang, đang khởi động lại...", level=logging.WARNING)
                            self._restart_browser_session(reason="post_refresh_unhealthy")
                        refresh_success = True
                    
                    # Kiểm tra sức khỏe WebDriver định kỳ
                    if current_time - self.last_health_check > 300:  # mỗi 5 phút
                        from ..browser.driver import browser_manager
                        if not browser_manager.check_driver_health():
                            log("Phát hiện WebDriver không khỏe mạnh, đang khởi động lại...", level=logging.WARNING)
                            self._restart_browser_session(reason="periodic_healthcheck_unhealthy")
                        self.last_health_check = time.time()
                    
                    # Kiểm tra nếu cần reload trang định kỳ
                    if current_time - self.last_reload_time > 300:  # 5 phút reload trang 1 lần
                        log("Định kỳ làm mới trang...")
                        try:
                            refresh_success = self.refresh_page_safely()
                            self.last_reload_time = current_time
                        except Exception as refresh_error:
                            log(f"Lỗi khi làm mới trang định kỳ: {str(refresh_error)}", level=logging.ERROR)
                            refresh_success = False
                    
                    # Kiểm tra nếu quá 60 giây không có dữ liệu mới
                    if current_time - self.last_collected_time > 60:
                        log("Không có dữ liệu mới trong 1 phút, làm mới trang...")
                        self._send_notification_throttled(
                            "recovery.no_new_data",
                            "Không có dữ liệu mới trong 1 phút, làm mới trang...",
                            cooldown_seconds=300,
                        )
                        try:
                            refresh_success = self.refresh_page_safely()
                            self.last_collected_time = current_time
                        except Exception as refresh_error:
                            log(f"Lỗi khi làm mới trang do không có dữ liệu mới: {str(refresh_error)}", level=logging.ERROR)
                            refresh_success = False
                    
                    # Thu thập tin nhắn với số lượng giới hạn
                    chat_items = self.driver.find_elements(By.CSS_SELECTOR, ".chat-item")
                    
                    # Giới hạn số lượng tin nhắn để xử lý
                    if len(chat_items) > 50:
                        chat_items = chat_items[-50:]  # Lấy 50 tin nhắn mới nhất
                    
                    # Xử lý từng tin nhắn
                    processed_count = 0
                    for chat_item in chat_items:
                        if self.external_stop_flag():
                            log(f"({self.group_name}) Nhận stop flag giữa vòng xử lý tin nhắn, thoát sớm để tránh log nhiễu.", level=logging.DEBUG)
                            break
                        try:
                            # Kiểm tra xem phần tử còn hợp lệ không
                            is_valid = self.driver.execute_script("""
                                try {
                                    // Thử truy cập một thuộc tính bất kỳ
                                    arguments[0].getAttribute('class');
                                    return true;
                                } catch (e) {
                                    return false;
                                }
                            """, chat_item)
                            
                            if not is_valid:
                                continue
                            
                            data_ok, msg_text = self.message_processor.process_chat_item(chat_item)
                            
                            if data_ok and data_ok not in self.unique_messages:
                                self.unique_messages.append(data_ok)
                                processed_count += 1
                                
                                # Giới hạn số lượng tin nhắn lưu trữ
                                if len(self.unique_messages) > self.max_messages:
                                    self.unique_messages = self.unique_messages[-self.max_messages:]
                                
                                log(data_ok)
                                self.append_single_message_to_autosave(data_ok)
                                self.db_manager.save_messages([{
                                    "raw_message": data_ok,
                                    "content": msg_text,
                                    "sender": self.message_processor.previous_sender,
                                    "group_name": self.group_name,
                                    "sent_at_exact": self.message_processor.last_message_metadata.get("sent_at_exact"),
                                    "sent_at_ms": self.message_processor.last_message_metadata.get("sent_at_ms"),
                                    "ingested_at": self.message_processor.last_message_metadata.get("ingested_at"),
                                    "timestamp_source": self.message_processor.last_message_metadata.get("timestamp_source"),
                                }], self.group_name)

                                # Kiểm tra từ khóa trong tin nhắn
                                if msg_text:
                                    matching_keywords = self.keyword_monitor.check_keywords(msg_text)
                                    if matching_keywords:
                                        keyword_alert = f"🔍 Có: {', '.join(matching_keywords)} trong: {msg_text}"
                                        log(keyword_alert, level=logging.WARNING)
                                        try:
                                            from ..notification.telegram import send_alert, ALERT_CHAT_ID
                                            send_alert(keyword_alert, chat_id=ALERT_CHAT_ID)
                                        except Exception as alert_error:
                                            log(f"Lỗi khi gửi cảnh báo từ crawler: {str(alert_error)}", level=logging.ERROR)   

                                # Cập nhật thời gian thu thập cuối cùng
                                self.last_collected_time = time.time()
                        except Exception as item_error:
                            if self._is_expected_shutdown_webdriver_error(item_error):
                                self._log_shutdown_webdriver_noise("process_chat_item", item_error)
                                break

                            log(f"Lỗi khi xử lý tin nhắn cụ thể: {str(item_error)}", level=logging.ERROR)
                            error_str = str(item_error).lower()
                            if "connection" in error_str or "webdriver" in error_str or "timeout" in error_str:
                                log("Phát hiện lỗi kết nối WebDriver, tăng biến đếm lỗi", level=logging.WARNING)
                                self.consecutive_errors += 1
                                
                                # Nếu đạt đến 5 lỗi liên tiếp, thực hiện các bước phục hồi
                                if self.consecutive_errors >= 5:
                                    log(f"Đã xảy ra {self.consecutive_errors} lỗi liên tiếp, đang thực hiện phục hồi...", level=logging.WARNING)
                                    self.refresh_page_safely()
                                    status = self.check_zalo_status()
                                    self._log_status_transition(status, force=True, level=logging.WARNING, prefix="Zalo status after consecutive webdriver errors")

                                    if status.get("logged_in") and status.get("in_group"):
                                        log("Đã đăng nhập và ở trong nhóm chat, đang làm mới trang...", level=logging.WARNING)
                                        self.refresh_page_safely()
                                    else:
                                        self._recover_from_status(status, notify=False)

                                    self.consecutive_errors = 0
                            
                            continue  # Bỏ qua tin nhắn này và tiếp tục
                    
                    if processed_count > 0:
                        log(f"Đã xử lý {processed_count} tin nhắn mới")
                        # Reset biến đếm lỗi liên tiếp khi xử lý thành công
                        self.consecutive_errors = 0
                    
                    # Cuộn trang để tải thêm tin nhắn
                    self.scroll_for_messages()
                    
                    time.sleep(MESSAGE_CRAWL_INTERVAL)
                
                except Exception as crawl_error:
                    if self._is_expected_shutdown_webdriver_error(crawl_error):
                        self._log_shutdown_webdriver_noise("crawl_loop", crawl_error)
                        break

                    # Cải thiện xử lý lỗi
                    log(f"Lỗi trong quá trình crawl: {str(crawl_error)}", level=logging.ERROR)
                    
                    # Tăng biến đếm lỗi liên tiếp
                    #self.consecutive_errors += 1
                    
                    # Kiểm tra loại lỗi
                    ##error_str = str(crawl_error).lower()
                    ##if "connection" in error_str or "timeout" in error_str or "webdriver" in error_str:
                        # Kiểm tra nếu vượt quá số lỗi cho phép
                        ##if self.consecutive_errors >= self.max_consecutive_errors:
                        ##    log(f"Đã xảy ra {self.consecutive_errors} lỗi liên tiếp, khởi động lại WebDriver...", level=logging.WARNING)
                        ##    from ..browser.driver import browser_manager
                        ##    browser_manager.restart_driver()
                        ##    browser_manager.recover_session()
                        ##    self.reconnect_to_group()
                        ##    self.consecutive_errors = 0
                    
                    # Trường hợp lỗi thông thường, thử phục hồi bằng cách làm mới trang
                    ##try:
                    ##    refresh_success = self.refresh_page_safely()
                    ##except Exception as recovery_error:
                    ##    log(f"Không thể phục hồi sau lỗi: {str(recovery_error)}", level=logging.ERROR)
                    ##    refresh_success = False
                    
                    # Đợi một chút trước khi tiếp tục
                    ##time.sleep(5)
            
            # Khi kết thúc, lưu file cuối cùng
            with self.save_lock:
                log("Đang lưu dữ liệu cuối cùng...")
                final_file = self.save_document(now_save)
            
            return final_file
            
        except Exception as e:
            log(f"Lỗi không xác định: {str(e)}", level=logging.ERROR)
            self._send_notification_throttled(
                "crawler.unhandled_error",
                f"Lỗi không xác định: {str(e)}",
                cooldown_seconds=300,
            )
            return None
        finally:
            # Đảm bảo lưu dữ liệu lần cuối khi kết thúc
            try:
                with self.save_lock:
                    log("Đang lưu dữ liệu trước khi kết thúc...")
                    self.save_current_data()
            except Exception as save_error:
                log(f"Lỗi khi lưu dữ liệu cuối cùng: {str(save_error)}", level=logging.ERROR)
            self._cleanup_fail_artifacts_after_job()
                
    def reconnect_to_group(self):
        """Kết nối lại với nhóm chat sau khi làm mới trang.

        Hardening note:
        - không coi reconnect là thành công chỉ vì navigation trả True
        - verify lại đúng target group qua `check_zalo_status()`
        - log rõ mismatch/unknown sau reconnect để main loop đỡ mù
        """
        reconnect_ok = self.browser_navigation.reconnect_to_group(self.group_name)
        if not reconnect_ok:
            log(
                f"Reconnect tới nhóm '{self.group_name}' thất bại ở navigation layer; step=navigation",
                level=logging.WARNING,
            )
            return False

        status = self.check_zalo_status()
        if status.get("logged_in") and status.get("in_group"):
            self._log_status_transition(status, force=True, level=logging.INFO, prefix="Reconnect verified")
            log(f"Reconnect tới nhóm '{self.group_name}' đã được verify thành công")
            return True

        reason = status.get("reason", "unknown")
        page_state = status.get("page_state") or {}
        current_group = page_state.get("group_title", "")
        breadcrumb = self._format_status_context(status)
        if reason == GROUP_MISMATCH:
            self.capture_fail_artifact(
                phase="reconnect_to_group.verify",
                reason=reason,
                group_name=self.group_name,
                extra={"current_group_title": current_group, "target_group": self.group_name},
            )
            log(
                f"Reconnect xong nhưng vẫn đang ở sai nhóm ('{current_group}' != '{self.group_name}'); step=verify, {breadcrumb}",
                level=logging.WARNING,
            )
        elif reason == GROUP_STATE_UNKNOWN:
            self.capture_fail_artifact(
                phase="reconnect_to_group.verify",
                reason=reason,
                group_name=self.group_name,
                extra={"current_group_title": current_group, "target_group": self.group_name},
            )
            log(
                f"Reconnect xong nhưng chưa xác định được group hiện tại; step=verify, {breadcrumb}",
                level=logging.WARNING,
            )
        elif not status.get("logged_in"):
            self.capture_fail_artifact(
                phase="reconnect_to_group.verify",
                reason=reason,
                group_name=self.group_name,
            )
            log(
                f"Reconnect xong nhưng trạng thái đăng nhập chưa ổn; step=verify, {breadcrumb}",
                level=logging.WARNING,
            )
        else:
            self.capture_fail_artifact(
                phase="reconnect_to_group.verify",
                reason=reason,
                group_name=self.group_name,
                extra={"current_group_title": current_group, "target_group": self.group_name},
            )
            log(
                f"Reconnect xong nhưng verify không pass; step=verify, {breadcrumb}",
                level=logging.WARNING,
            )
        return False
    
    def save_document(self, now_save):
        """Lưu tài liệu Word với các tin nhắn đã thu thập"""
        try:
            # Mở file autosave để thêm thông tin kết thúc
            from docx import Document
            import os
            import shutil
            
            if not hasattr(self, 'autosave_path') or not os.path.exists(self.autosave_path):
                level = logging.DEBUG if self._should_quiet_shutdown_file_noise() else logging.ERROR
                log("Không tìm thấy file autosave để tạo file cuối cùng", level=level)
                return None
                
            # Mở file autosave để thêm thông tin kết thúc
            doc = Document(self.autosave_path)
            
            # Thêm thông tin kết thúc
            doc.add_paragraph('_______________________________________________')
            doc.add_paragraph(f'Thời gian kết thúc: {now_save.strftime("%d/%m/%Y %H:%M:%S")}')
            
            # Đếm số đoạn văn (tương đương số tin nhắn + header)
            message_count = len(doc.paragraphs) - 5  # Trừ đi các dòng header và footer
            doc.add_paragraph(f'Tổng số tin nhắn: {message_count}')
            
            # Lưu lại file autosave với thông tin kết thúc
            doc.save(self.autosave_path)
            
            # Tên file cuối: canonical final naming theo session/host/room/message_count
            file_name = build_final_docx_name(self.session_id, COMPUTER_NAME, self.group_slug, message_count)
            final_path = os.path.join(os.path.dirname(self.autosave_path), file_name)
            
            # Sao chép file autosave thành file cuối cùng
            shutil.copy2(self.autosave_path, final_path)
            
            log(f"Đã lưu tài liệu cuối cùng: {final_path} với {message_count} tin nhắn")
            self._log_observability_event(
                "save_document_result",
                prefix="SAVE_DOCUMENT_RESULT",
                level=logging.INFO,
                success=True,
                file_name=file_name,
                final_path=final_path,
                message_count=message_count,
            )
            send_notification(build_save_document_notification(self.group_name, message_count, file_name))
            
            return final_path
        except Exception as e:
            log(f"Lỗi khi lưu tài liệu: {str(e)}", level=logging.ERROR)
            self._log_observability_event(
                "save_document_result",
                prefix="SAVE_DOCUMENT_RESULT",
                level=logging.ERROR,
                success=False,
                error=str(e),
            )
            return None
    def _build_zalo_status_snapshot(self, *, logged_in=False, in_group=False, needs_qr=False, reason="unknown", group_title=""):
        return {
            "logged_in": bool(logged_in),
            "in_group": bool(in_group),
            "needs_qr": bool(needs_qr),
            "reason": reason,
            "page_state": {
                "group_title": group_title or "",
                "target_group": str(self.group_name or ""),
            },
        }

    def check_zalo_status(self):
        """Kiểm tra trạng thái hiện tại của Zalo: đăng nhập, trong nhóm chat.

        Hardening note:
        - không nuốt nhầm browser-dead thành trạng thái "logged_out"
        - phân biệt rõ hơn giữa needs_qr / logged_in / group-mismatch / unknown-state
        - giữ backward compatibility cho các call sites đang đọc `logged_in`, `in_group`, `needs_qr`
        - thêm `reason` và `page_state` để dev lane debug/recovery dễ hơn
        """
        try:
            is_logged_in = False
            try:
                WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.ID, "contact-search-input"))
                )
                is_logged_in = True
            except TimeoutException:
                pass
            except Exception as e:
                if is_browser_dead_error(e):
                    log(f"Lỗi browser khi kiểm tra trạng thái đăng nhập: {str(e)}", level=logging.WARNING)
                    raise
                log(f"Không thấy marker đăng nhập, sẽ kiểm tra QR: {str(e)}", level=logging.WARNING)

            if not is_logged_in:
                try:
                    WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".qrcode img"))
                    )
                    status = self._build_zalo_status_snapshot(
                        logged_in=False,
                        in_group=False,
                        needs_qr=True,
                        reason=QR_VISIBLE,
                    )
                    log("Phát hiện Zalo đã đăng xuất, hiển thị QR code", level=logging.WARNING)
                    return status
                except TimeoutException:
                    status = self._build_zalo_status_snapshot(
                        logged_in=False,
                        in_group=False,
                        needs_qr=False,
                        reason=LOGIN_STATE_UNKNOWN,
                    )
                    log("Không xác định được trạng thái đăng nhập", level=logging.WARNING)
                    self._log_observability_event(
                        "login_state_unknown",
                        prefix="LOGIN_STATE_UNKNOWN",
                        level=logging.WARNING,
                        reason=LOGIN_STATE_UNKNOWN,
                        trigger="qr_timeout",
                    )
                    return status
                except Exception as e:
                    if is_browser_dead_error(e):
                        log(f"Lỗi browser khi kiểm tra QR/login state: {str(e)}", level=logging.WARNING)
                        raise
                    status = self._build_zalo_status_snapshot(
                        logged_in=False,
                        in_group=False,
                        needs_qr=False,
                        reason=LOGIN_STATE_UNKNOWN,
                    )
                    log(f"Không xác định được trạng thái đăng nhập: {str(e)}", level=logging.WARNING)
                    self._log_observability_event(
                        "login_state_unknown",
                        prefix="LOGIN_STATE_UNKNOWN",
                        level=logging.WARNING,
                        reason=LOGIN_STATE_UNKNOWN,
                        trigger="qr_check_exception",
                        error=str(e),
                    )
                    return status

            is_in_group = False
            title_text = ""
            try:
                group_title = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".header-title.flx.flx-al-c.flex-1"))
                )
                title_text = group_title.text
                title_lower = (title_text or "").strip().lower()
                target = str(self.group_name).strip().lower()
                matched = target and (target in title_lower)
                if not matched and target:
                    parts = [p for p in target.split() if p]
                    matched = all(p in title_lower for p in parts) if parts else False

                if matched:
                    is_in_group = True
                    log(f"Đang ở trong nhóm chat: '{title_text}'")
                else:
                    log(
                        f"Không phải trong nhóm chat mục tiêu ('{self.group_name}'). Tiêu đề hiện tại: '{title_text}'",
                        level=logging.WARNING,
                    )
            except TimeoutException:
                log("Không tìm thấy tiêu đề nhóm chat", level=logging.WARNING)
            except Exception as e:
                if is_browser_dead_error(e):
                    log(f"Lỗi browser khi kiểm tra tiêu đề nhóm chat: {str(e)}", level=logging.WARNING)
                    raise
                log(f"Không thể xác định tiêu đề nhóm chat: {str(e)}", level=logging.WARNING)

            if is_in_group:
                return self._build_zalo_status_snapshot(
                    logged_in=True,
                    in_group=True,
                    needs_qr=False,
                    reason=READY_IN_TARGET_GROUP,
                    group_title=title_text,
                )

            reason = GROUP_MISMATCH if title_text else GROUP_STATE_UNKNOWN
            return self._build_zalo_status_snapshot(
                logged_in=True,
                in_group=False,
                needs_qr=False,
                reason=reason,
                group_title=title_text,
            )
        except Exception as e:
            if is_browser_dead_error(e):
                log(f"Browser chết trong check_zalo_status: {str(e)}", level=logging.WARNING)
                raise
            log(f"Lỗi khi kiểm tra trạng thái Zalo: {str(e)}", level=logging.ERROR)
            self._log_observability_event(
                "zalo_status_check_error",
                prefix="ZALO_STATUS_CHECK_ERROR",
                level=logging.ERROR,
                reason=STATUS_CHECK_ERROR,
                error=str(e),
            )
            return self._build_zalo_status_snapshot(
                logged_in=False,
                in_group=False,
                needs_qr=False,
                reason=STATUS_CHECK_ERROR,
            )

    def rotate_session_if_needed(self):
        """Nếu đổi phiên (P1-P6), chốt file cũ và tạo autosave mới."""
        try:
            now = datetime.now()
            current_session_id = get_session_id(now)
            if current_session_id == self.session_id:
                return None

            log(f"({self.group_name}) Đổi phiên: {self.session_id} -> {current_session_id}", level=logging.INFO)

            final_path = None
            try:
                with self.save_lock:
                    final_path = self.save_document(now)
            except Exception as e:
                log(f"({self.group_name}) Lỗi khi chốt file phiên cũ: {str(e)}", level=logging.ERROR)

            if final_path:
                try:
                    self.docx_handler.process_docx_format(final_path)
                except Exception as e:
                    log(f"({self.group_name}) Lỗi khi xử lý format file: {str(e)}", level=logging.ERROR)

            # Reset trạng thái cho phiên mới
            self.session_id = current_session_id
            self.processed_messages = set()
            self.unique_messages = []
            self.message_processor = MessageProcessor(self.driver, self.current_user_name)
            self.configure_autosave_filename(now)
            try:
                self.create_initial_autosave_file()
            except Exception:
                pass

            return final_path
        except Exception as e:
            log(f"({self.group_name}) Lỗi rotate_session_if_needed: {str(e)}", level=logging.ERROR)
            return None

    def crawl_step(self):
        """
        Crawl 1 nhịp cho group hiện tại.
        QUAN TRỌNG: Chỉ đọc tin nhắn khi xác nhận đang ở đúng group để tránh lẫn dữ liệu.
        """
        try:
            status = self.check_zalo_status()
            if not status.get("logged_in"):
                self._log_status_transition(status, level=logging.WARNING, prefix=f"crawl_step[{self.group_name}] blocked")
                return 0

            if not status.get("in_group"):
                self._log_status_transition(status, level=logging.WARNING, prefix=f"crawl_step[{self.group_name}] needs_reconnect")
                ok = self.browser_navigation.find_and_access_group(self.group_name)
                if not ok:
                    return 0
                status2 = self.check_zalo_status()
                if not status2.get("in_group"):
                    self._log_status_transition(status2, force=True, level=logging.WARNING, prefix=f"crawl_step[{self.group_name}] reconnect_verify_failed")
                    return 0
                self._log_status_transition(status2, force=True, level=logging.INFO, prefix=f"crawl_step[{self.group_name}] reconnect_verified")

            # Multi-room mode: giảm timeout chờ ổn định để giảm dwell time mỗi room.
            self.wait_for_messages_stable(timeout=self._get_multi_room_stable_wait_timeout())
            
            processed_count = 0
            db_batch = []

            chat_items = self.driver.find_elements(By.CSS_SELECTOR, ".chat-item")
            visible_count = len(chat_items)
            if len(chat_items) > 100:
                chat_items = chat_items[-100:]

            for chat_item in chat_items:
                try:
                    is_valid = self.driver.execute_script(
                        """
                        try {
                            arguments[0].getAttribute('class');
                            return true;
                        } catch (e) {
                            return false;
                        }
                        """,
                        chat_item,
                    )
                    if not is_valid:
                        continue

                    data_ok, msg_text = self.message_processor.process_chat_item(chat_item)
                    if data_ok and data_ok not in self.unique_messages:
                        self.unique_messages.append(data_ok)
                        processed_count += 1

                        if len(self.unique_messages) > self.max_messages:
                            self.unique_messages = self.unique_messages[-self.max_messages:]

                        log(f"({self.group_name}) {data_ok}")
                        self.append_single_message_to_autosave(data_ok)
                        db_batch.append({
                            "raw_message": data_ok,
                            "content": msg_text,
                            "sender": self.message_processor.previous_sender,
                            "group_name": self.group_name,
                            "sent_at_exact": self.message_processor.last_message_metadata.get("sent_at_exact"),
                            "sent_at_ms": self.message_processor.last_message_metadata.get("sent_at_ms"),
                            "ingested_at": self.message_processor.last_message_metadata.get("ingested_at"),
                            "timestamp_source": self.message_processor.last_message_metadata.get("timestamp_source"),
                        })

                        if msg_text:
                            matching_keywords = self.keyword_monitor.check_keywords(msg_text)
                            if matching_keywords:
                                keyword_alert = f"🔍 ({self.group_name}) Có: {', '.join(matching_keywords)} trong: {msg_text}"
                                log(keyword_alert, level=logging.WARNING)
                                try:
                                    from ..notification.telegram import ALERT_CHAT_ID
                                    send_alert(keyword_alert, chat_id=ALERT_CHAT_ID)
                                except Exception as alert_error:
                                    log(f"Lỗi khi gửi cảnh báo: {str(alert_error)}", level=logging.ERROR)

                        self.last_collected_time = time.time()
                except Exception as item_error:
                    if self._is_expected_shutdown_webdriver_error(item_error):
                        self._log_shutdown_webdriver_noise("crawl_step.process_chat_item", item_error)
                        break
                    log(f"({self.group_name}) Lỗi khi xử lý tin nhắn: {str(item_error)}", level=logging.ERROR)
                    continue

            if db_batch:
                self.db_manager.save_messages(db_batch, self.group_name)

            try:
                self.scroll_for_messages()
            except Exception:
                pass

            backlog_state = self._compute_backlog_state(visible_count, processed_count)
            if backlog_state["backlog_pressure"]:
                log(
                    f"({self.group_name}) backlog_pressure=true processed={processed_count} visible={visible_count}",
                    level=logging.INFO,
                )
            if backlog_state["possible_gap"]:
                log(
                    f"({self.group_name}) possible_gap=true processed={processed_count} visible={visible_count}",
                    level=logging.WARNING,
                )
            if backlog_state["backlog_hot"]:
                log(
                    f"({self.group_name}) backlog_hot=true pressure_streak={backlog_state['backlog_pressure_streak']} gap_streak={backlog_state['possible_gap_streak']}",
                    level=logging.INFO,
                )

            return processed_count
        except Exception as e:
            if self._is_expected_shutdown_webdriver_error(e):
                self._log_shutdown_webdriver_noise("crawl_step", e)
                return 0
            log(f"({self.group_name}) Lỗi crawl_step: {str(e)}", level=logging.ERROR)
            ctx = {"group_name": self.group_name, "phase": "crawl_step"}
            try:
                ctx["current_url"] = self.driver.current_url
                ctx["page_title"] = self.driver.title
            except Exception:
                pass
            log_error(e, context=ctx, extra_message="Lỗi trong crawl_step")
            return 0
