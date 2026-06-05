# Xử lý đăng nhập và QR code
# src/auth/login.py
import time
import os
import threading
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from ..utils.logger import log, logging
from ..utils.config import LOGIN_TIMEOUT as LOGIN_TIMEOUT_SECONDS, DATA_FOLDER
from ..notification.telegram import send_notification, send_document
from ..notification.messages import (
    build_login_qr_required_notification,
    build_login_success_notification,
    build_login_timeout_notification,
)
from ..utils.decorators import retry_on_webdriver_error
from ..utils.signals import is_terminating
from ..utils.browser_errors import is_browser_dead_error
from ..utils.fail_artifacts import FailArtifactMixin
from ..utils.status_codes import (
    ALREADY_LOGGED_IN,
    LOGIN_DETECTED,
    LOGIN_STATE_UNKNOWN,
    LOGIN_TIMEOUT,
    QR_EXPIRED,
    QR_SEND_ATTEMPT,
    QR_SENT,
    QR_VISIBLE,
    WAITING_FOR_LOGIN,
)

class ZaloAuthManager(FailArtifactMixin):
    """Quản lý xác thực và đăng nhập Zalo"""
    
    def __init__(self, driver):
        """Khởi tạo ZaloAuthManager với WebDriver đã được khởi tạo"""
        self.driver = driver
        self.last_qr_refresh_time = 0
        self.last_login_state = None
        self.last_login_state_reason = None

    def _build_login_state_snapshot(self, qr_sent=False):
        """Tạo snapshot ngắn gọn cho lane dev/test khi debug trạng thái đăng nhập/QR."""
        now = time.time()
        last_refresh_age = None
        if self.last_qr_refresh_time:
            last_refresh_age = max(0, int(now - self.last_qr_refresh_time))
        return {
            "logged_in": False,
            "qr_sent": bool(qr_sent),
            "qr_expired": self.is_qr_expired(),
            "last_qr_refresh_age_s": last_refresh_age,
        }

    def _log_login_state_transition(self, state, reason, level=logging.INFO, force=False):
        """Chỉ log khi state hoặc lý do đổi trạng thái thay đổi để tăng observability mà không spam log."""
        if (not force) and state == self.last_login_state and reason == self.last_login_state_reason:
            return
        self.last_login_state = dict(state)
        self.last_login_state_reason = reason
        log(f"Login state -> {reason}: {state}", level=level)

    def get_login_debug_state(self, qr_sent=False):
        """Expose state nhỏ gọn cho lane dev/test mà không cần chạm luồng đăng nhập thật."""
        state = self._build_login_state_snapshot(qr_sent=qr_sent)
        state["last_reason"] = self.last_login_state_reason
        return state
    
    @retry_on_webdriver_error(max_retries=2)
    def check_login_status(self):
        """Kiểm tra xem đã đăng nhập vào Zalo Web chưa.

        Hardening follow-up:
        - phân biệt rõ logged-in / qr-visible / unknown-state
        - không nuốt nhầm lỗi browser chết thành trạng thái "chưa đăng nhập"
        - cập nhật login-state reason để dev lane debug dễ hơn
        """
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "contact-search-input"))
            )
            state = {
                "logged_in": True,
                "qr_sent": False,
                "qr_expired": False,
                "last_qr_refresh_age_s": 0,
            }
            self._log_login_state_transition(state, reason=ALREADY_LOGGED_IN)
            log("Đã đăng nhập vào Zalo")
            return True
        except TimeoutException:
            pass
        except Exception as e:
            if is_browser_dead_error(e):
                log(f"Lỗi browser khi kiểm tra trạng thái đăng nhập: {str(e)}", level=logging.WARNING)
                raise
            log(f"Không thấy marker đăng nhập, sẽ kiểm tra QR: {str(e)}", level=logging.WARNING)

        try:
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".qrcode img"))
            )
            state = self._build_login_state_snapshot(qr_sent=False)
            self._log_login_state_transition(state, reason=QR_VISIBLE)
            log("Chưa đăng nhập, cần quét mã QR")
            return False
        except TimeoutException:
            state = self._build_login_state_snapshot(qr_sent=False)
            self._log_login_state_transition(
                state,
                reason=LOGIN_STATE_UNKNOWN,
                level=logging.WARNING,
            )
            self.capture_fail_artifact(phase="auth.check_login_status", reason=LOGIN_STATE_UNKNOWN)
            log(f"Không thể xác định trạng thái đăng nhập (reason={LOGIN_STATE_UNKNOWN})", level=logging.WARNING)
            return False
        except Exception as e:
            if is_browser_dead_error(e):
                log(f"Lỗi browser khi kiểm tra QR đăng nhập: {str(e)}", level=logging.WARNING)
                raise
            state = self._build_login_state_snapshot(qr_sent=False)
            self._log_login_state_transition(
                state,
                reason=LOGIN_STATE_UNKNOWN,
                level=logging.WARNING,
            )
            self.capture_fail_artifact(phase="auth.check_login_status", reason=LOGIN_STATE_UNKNOWN)
            log(f"Không thể xác định trạng thái đăng nhập: reason={LOGIN_STATE_UNKNOWN}; {str(e)}", level=logging.WARNING)
            return False

    @retry_on_webdriver_error(max_retries=2)
    def is_qr_expired(self):
        """Kiểm tra xem QR code đã hết hạn chưa"""
        try:
            expired_elements = self.driver.find_elements(By.CSS_SELECTOR, ".qrcode-expired")
            if expired_elements and len(expired_elements) > 0:
                try:
                    return expired_elements[0].is_displayed()
                except:
                    return False
            return False
        except Exception as e:
            log(f"Lỗi khi kiểm tra QR hết hạn: {str(e)}", level=logging.ERROR)
            return False
    
    @retry_on_webdriver_error(max_retries=2)
    def refresh_qr_code(self):
        """Làm mới mã QR code khi hết hạn"""
        try:
            refresh_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".qrcode-expired .btn")
            if refresh_buttons and len(refresh_buttons) > 0:
                refresh_buttons[0].click()
                log("Đã nhấn nút làm mới QR code")
                time.sleep(1)  # Đợi QR mới xuất hiện
                return True
            else:
                # Nếu không tìm thấy nút, làm mới toàn bộ trang
                log("Không tìm thấy nút làm mới, làm mới toàn bộ trang")
                self.driver.refresh()
                time.sleep(3)  # Đợi trang tải lại
                return True
        except Exception as e:
            log(f"Lỗi khi làm mới QR code: {str(e)}", level=logging.ERROR)
            # Trong trường hợp lỗi, làm mới toàn bộ trang
            try:
                self.driver.refresh()
                time.sleep(3)
            except:
                pass
            return False
    
    def send_qr_to_telegram(self, admin_chat_id=None):
        """Gửi QR code đến Telegram để đăng nhập từ xa"""
        try:
            # Import các module cần thiết
            import os
            import threading
            from ..utils.config import DATA_FOLDER, ADMIN_CHAT_ID, ALERT_CHAT_ID
            
            # Sử dụng cả ADMIN_CHAT_ID và ALERT_CHAT_ID
            chat_ids = []
            if admin_chat_id:
                chat_ids.append(admin_chat_id)
            else:
                for cid in (ADMIN_CHAT_ID, ALERT_CHAT_ID):
                    if cid and cid not in chat_ids:
                        chat_ids.append(cid)

            if not chat_ids:
                log("Không có chat_id Telegram hợp lệ để gửi QR code (kiểm tra ADMIN_CHAT_ID/ALERT_CHAT_ID)", level=logging.WARNING)
                return False
                
            log(f"Sẽ gửi QR code đến các chat_id: {chat_ids}", level=logging.INFO)
            
            # Tìm phần tử QR code (bắt timeout/tab crash để không tràn log traceback)
            try:
                qr_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".qrcode img"))
                )
            except (TimeoutException, WebDriverException) as e:
                log(f"Không tìm thấy QR code (trang đang tải hoặc tab lỗi): {type(e).__name__}", level=logging.WARNING)
                return False
            
            # Tạo thư mục lưu QR code
            qr_folder = os.path.join(DATA_FOLDER, "ZaloQR")
            if not os.path.exists(qr_folder):
                os.makedirs(qr_folder)
            
            timestamp = int(time.time())
            qr_path = os.path.join(qr_folder, f"zalo_qr_{timestamp}.png")
            fullscreen_path = os.path.join(qr_folder, f"zalo_qr_fullscreen_{timestamp}.png")
            
            # Chụp QR code element (phương án 1: QR code riêng)
            try:
                # Cuộn đến QR code để đảm bảo nó hiển thị đầy đủ
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", qr_element)
                time.sleep(0.5)  # Đợi scroll xong
                
                # Chụp QR code với chất lượng tốt hơn
                qr_element.screenshot(qr_path)
                log(f"Đã chụp QR code element và lưu tại {qr_path}")
                
                # Kiểm tra file tồn tại và có kích thước hợp lý
                if os.path.exists(qr_path):
                    file_size = os.path.getsize(qr_path)
                    log(f"Kích thước file QR element: {file_size} bytes", level=logging.INFO)
                    
                    # Nếu file quá nhỏ (< 1KB), có thể QR không render đúng
                    if file_size < 1024:
                        log("File QR quá nhỏ, có thể chất lượng không tốt", level=logging.WARNING)
                else:
                    log("Không thể chụp QR element, sẽ dùng fullscreen", level=logging.WARNING)
                    qr_path = None
            except Exception as e:
                log(f"Lỗi khi chụp QR element: {str(e)}, sẽ dùng fullscreen", level=logging.WARNING)
                qr_path = None
            
            # Chụp toàn màn hình (phương án 2: backup - luôn chụp để đảm bảo)
            try:
                # Đợi một chút để trang render xong
                time.sleep(1)
                
                # Chụp toàn màn hình
                self.driver.save_screenshot(fullscreen_path)
                log(f"Đã chụp toàn màn hình và lưu tại {fullscreen_path}")
                
                if os.path.exists(fullscreen_path):
                    file_size = os.path.getsize(fullscreen_path)
                    log(f"Kích thước file fullscreen: {file_size} bytes", level=logging.INFO)
                else:
                    log("Không thể chụp fullscreen", level=logging.ERROR)
                    fullscreen_path = None
            except Exception as e:
                log(f"Lỗi khi chụp fullscreen: {str(e)}", level=logging.ERROR)
                fullscreen_path = None
            
            # Kiểm tra có ít nhất 1 file ảnh không
            if not qr_path and not fullscreen_path:
                log("Không thể chụp được ảnh QR code nào", level=logging.ERROR)
                return False
            
            # Thực hiện gửi QR code trong một thread riêng
            success_event = threading.Event()
            
            def send_qr_in_thread():
                try:
                    from ..notification.telegram import send_notification, send_document
                    
                    # Gửi thông báo
                    send_notification(build_login_qr_required_notification())
                    
                    # Thử gửi QR code đến từng chat_id
                    success = False
                    for chat_id in chat_ids:
                        try:
                            # Gửi cả 2 ảnh: QR element (nếu có) và fullscreen
                            # Ưu tiên gửi QR element trước (nhỏ gọn hơn)
                            if qr_path and os.path.exists(qr_path):
                                result1 = send_document(
                                    qr_path,
                                    caption="📱 QR Code để đăng nhập Zalo (Mã QR có hiệu lực trong 60 giây)\n\nNếu không quét được, xem ảnh fullscreen bên dưới",
                                    chat_id=chat_id
                                )
                                if result1:
                                    log(f"Đã gửi QR element đến chat_id: {chat_id}")
                                    success = True
                            
                            # Gửi ảnh fullscreen (backup - luôn gửi để đảm bảo)
                            if fullscreen_path and os.path.exists(fullscreen_path):
                                # Đợi một chút giữa các lần gửi
                                time.sleep(0.5)
                                
                                result2 = send_document(
                                    fullscreen_path,
                                    caption="🖼️ Ảnh toàn màn hình Zalo Web\n\nQuét QR code trong ảnh này nếu ảnh QR riêng không quét được",
                                    chat_id=chat_id
                                )
                                if result2:
                                    log(f"Đã gửi ảnh fullscreen đến chat_id: {chat_id}")
                                    success = True
                            
                        except Exception as chat_error:
                            log(f"Lỗi khi gửi QR đến chat_id {chat_id}: {str(chat_error)}", level=logging.WARNING)
                    
                    if success:
                        success_event.set()
                except Exception as e:
                    log(f"Lỗi trong thread gửi QR: {str(e)}", level=logging.ERROR)
                    import traceback
                    log(traceback.format_exc(), level=logging.ERROR)
            
            # Khởi động thread gửi QR code
            thread = threading.Thread(target=send_qr_in_thread)
            thread.daemon = True  # Thread sẽ kết thúc khi chương trình chính kết thúc
            thread.start()
            
            # Đợi thread hoàn thành trong thời gian cho phép
            if success_event.wait(timeout=5):  # Chỉ đợi tối đa 5 giây
                log("Đã gửi QR code qua Telegram thành công")
                self.last_qr_refresh_time = time.time()
                return True
            else:
                # Không đợi thread hoàn thành, vẫn trả về True để tiếp tục luồng chính
                log("Gửi QR code vẫn đang xử lý, tiếp tục luồng chính", level=logging.WARNING)
                self.last_qr_refresh_time = time.time()
                return True  # Vẫn trả về True để không ảnh hưởng đến luồng chính
                
        except (TimeoutException, WebDriverException) as e:
            log(f"Lỗi khi gửi QR code (timeout/tab): {type(e).__name__}", level=logging.WARNING)
            return False
        except Exception as e:
            log(f"Lỗi khi gửi QR code: {str(e)}", level=logging.ERROR)
            return False
    
    def wait_for_login(self, admin_chat_id=None, timeout_seconds=None):
        """Đợi người dùng quét mã QR và đăng nhập Zalo. timeout_seconds: None = dùng LOGIN_TIMEOUT (vd 90 khi recovery)."""
        timeout = timeout_seconds if timeout_seconds is not None else LOGIN_TIMEOUT_SECONDS
        start_time = time.time()
        self.last_qr_refresh_time = 0
        qr_sent = False

        while time.time() - start_time < timeout:
            if is_terminating():
                log("Đang dừng chương trình, thoát vòng chờ đăng nhập.", level=logging.WARNING)
                return False
            try:
                # Kiểm tra nếu đã đăng nhập thành công
                WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.ID, "contact-search-input"))
                )
                self._log_login_state_transition(
                    {
                        "logged_in": True,
                        "qr_sent": bool(qr_sent),
                        "qr_expired": False,
                        "last_qr_refresh_age_s": 0,
                    },
                    reason=LOGIN_DETECTED
                )
                log("Đăng nhập thành công!")

                # Gửi thông báo đăng nhập thành công
                send_notification(build_login_success_notification())

                return True
            except Exception as e:
                if is_browser_dead_error(e):
                    log(f"WebDriver/browser đã chết trong lúc chờ đăng nhập: {str(e)}", level=logging.WARNING)
                    return False

                # Nếu chưa đăng nhập, xử lý QR code
                current_time = time.time()
                qr_expired = self.is_qr_expired()

                # Kiểm tra nếu QR đã hết hạn
                if qr_expired:
                    self._log_login_state_transition(
                        self._build_login_state_snapshot(qr_sent=qr_sent),
                        reason=QR_EXPIRED,
                        level=logging.WARNING,
                    )
                    log("QR code đã hết hạn, làm mới...")
                    if self.refresh_qr_code():
                        # Sau khi làm mới, gửi lại QR code
                        qr_sent = False
                        time.sleep(1)  # Đợi QR mới xuất hiện

                if is_terminating():
                    log("Đang dừng chương trình, bỏ qua gửi/refresh QR và thoát.", level=logging.WARNING)
                    return False

                should_send_qr = (not qr_sent) or (current_time - self.last_qr_refresh_time >= 50)
                if should_send_qr:
                    self._log_login_state_transition(
                        self._build_login_state_snapshot(qr_sent=qr_sent),
                        reason=QR_SEND_ATTEMPT
                    )
                    # Gửi QR code qua Telegram
                    if self.send_qr_to_telegram(admin_chat_id):
                        qr_sent = True
                        self._log_login_state_transition(
                            self._build_login_state_snapshot(qr_sent=qr_sent),
                            reason=QR_SENT
                        )
                else:
                    self._log_login_state_transition(
                        self._build_login_state_snapshot(qr_sent=qr_sent),
                        reason=WAITING_FOR_LOGIN
                    )

                # Đợi 3 giây trước khi kiểm tra lại
                time.sleep(3)

        final_state = self.get_login_debug_state(qr_sent=qr_sent)
        final_state["last_reason"] = LOGIN_TIMEOUT
        self._log_login_state_transition(
            final_state,
            reason=LOGIN_TIMEOUT,
            level=logging.ERROR,
            force=True,
        )
        log(f"Hết thời gian chờ đăng nhập ({timeout} giây)", level=logging.ERROR)

        # Gửi thông báo hết thời gian chờ đăng nhập
        send_notification(build_login_timeout_notification())

        return False
    
    def get_current_user_name(self):
        """Lấy tên người dùng từ tiêu đề trang Zalo"""
        try:
            page_title = self.driver.title
            if " - " in page_title and page_title.startswith("Zalo"):
                return page_title.split(" - ", 1)[1]
            return "Tôi"
        except Exception as e:
            log(f"Lỗi khi lấy tên người dùng từ tiêu đề: {str(e)}", level=logging.WARNING)
            return "Tôi"