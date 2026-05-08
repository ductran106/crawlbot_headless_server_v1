# LEGACY SNAPSHOT: file này được giữ lại để tham chiếu khi cleanup.
# Không dùng file này để chạy runtime; entrypoint hiện tại là ./run.sh -> main.py
# main.py - đặt ở thư mục gốc CrawlZalo_tonghop
import sys
import os
import time
import asyncio
import random

from src.utils.logger import log, logging
from src.utils.error_logger import log_error
from src.utils.signals import init_signal_handlers, is_terminating
from src.utils.config import (
    ensure_data_folder,
    GROUP_NAMES,
    get_group_data_folder,
    GROUP_SWITCH_MIN_SEC,
    GROUP_SWITCH_MAX_SEC,
)
from src.browser.driver import browser_manager
from src.browser.navigation import ZaloNavigator
from src.auth.login import ZaloAuthManager
from src.crawler.message_crawler import MessageCrawler
from src.notification.telegram import send_notification, send_error, send_alert, check_telegram_connection
from src.storage.docx_handler import DocxHandler

def countdown(seconds):
    """Đếm ngược trong console"""
    for i in range(seconds, 0, -1):
        sys.stdout.write(f"\rĐang đợi {i} giây...")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\rHoàn thành đợi!            \n")
    sys.stdout.flush()

async def crawl_messages():
    """Hàm chính crawler tin nhắn Zalo"""
    driver = None
    try:
        # Đảm bảo thư mục dữ liệu tồn tại
        ensure_data_folder()
        
        # Khởi động Chrome
        driver = browser_manager.get_chrome_driver()
        
        # Khởi tạo các module
        zalo_navigator = ZaloNavigator(driver)
        zalo_auth = ZaloAuthManager(driver)
        
        # Mở trang Zalo Web
        zalo_navigator.open_zalo_web()
        
        # Kiểm tra đăng nhập
        if not zalo_auth.check_login_status():
            # Đợi đăng nhập
            login_success = zalo_auth.wait_for_login()
            if not login_success:
                return False
        
        # Tìm và truy cập nhóm chat
        group_access = zalo_navigator.find_and_access_group()
        if not group_access:
            return False
        
        # Khởi tạo và bắt đầu crawler
        crawler = MessageCrawler(driver, zalo_navigator)
        
        # Chuyển biến is_terminating vào crawler
        crawler.external_stop_flag = is_terminating
        
        # Chạy crawler và chờ kết quả
        file_path = crawler.start_crawling()
        
        return file_path
        
    except Exception as e:
        error_message = f"❌ Lỗi hệ thống: {str(e)}"
        log(error_message, level=logging.ERROR)
        log_error(e, context={"phase": "crawl_messages"}, extra_message="Lỗi trong crawl_messages")
        send_error(error_message)
        return False
    finally:
        # Dọn dẹp
        if driver:
            try:
                driver.quit()
            except:
                pass

def _is_browser_dead_error(e):
    """True nếu lỗi do tab crash / timeout / mất kết nối Chrome."""
    if e is None:
        return False
    s = str(e).lower()
    return any(x in s for x in [
        "tab crashed", "crashed", "read timed out", "connectionpool",
        "connection refused", "not connected", "target window already closed",
        "remotedisconnected", "connection aborted", "protocolerror"
    ])


def _recover_browser_and_update_refs(browser_manager, zalo_navigator, crawlers, groups, zalo_auth):
    """
    Khởi động lại Chrome, cập nhật driver cho navigator và mọi crawler, mở lại Zalo.
    Trả về driver mới nếu thành công, None nếu thất bại.
    """
    try:
        log("Phát hiện browser/tab lỗi, đang khởi động lại Chrome...", level=logging.WARNING)
        if not browser_manager.restart_driver():
            return None
        driver = browser_manager.get_driver()
        zalo_navigator.driver = driver
        zalo_auth.driver = driver
        for g in groups:
            if g in crawlers:
                crawlers[g].driver = driver
                crawlers[g].browser_navigation.driver = driver
                crawlers[g].message_processor.driver = driver
        browser_manager.recover_session()
        # Retry check_login_status vài lần (trang Zalo có thể chưa kịp render)
        for attempt in range(3):
            if zalo_auth.check_login_status():
                break
            if attempt < 2:
                time.sleep(5)
        if not zalo_auth.check_login_status():
            # Timeout ngắn khi recovery (90s) để không chặn lâu; sau đó vòng lặp chính có thể retry
            if not zalo_auth.wait_for_login(timeout_seconds=90):
                log("Không thể đăng nhập lại sau khi khôi phục (đã thử 90s)", level=logging.ERROR)
                return None
        log("Khôi phục browser thành công, tiếp tục crawl.", level=logging.INFO)
        return driver
    except Exception as ex:
        log(f"Lỗi khi khôi phục browser: {str(ex)}", level=logging.ERROR)
        return None


def run_multi_group_single_session(groups):
    """
    Chạy nhiều group trong 1 process / 1 session Zalo Web.
    Luân phiên round-robin, random 3-7s để giảm hành vi bot.
    Tuyệt đối không đọc tin nhắn nếu chưa xác nhận đúng group.
    Khi gặp tab crashed / timeout sẽ tự khởi động lại Chrome và tiếp tục.
    """
    driver = None
    crawlers = {}
    try:
        ensure_data_folder()

        # Chuẩn bị folder dữ liệu riêng cho từng group
        for g in groups:
            ensure_data_folder(get_group_data_folder(g))

        driver = browser_manager.get_chrome_driver()
        zalo_navigator = ZaloNavigator(driver)
        zalo_auth = ZaloAuthManager(driver)

        zalo_navigator.open_zalo_web()
        if not zalo_auth.check_login_status():
            if not zalo_auth.wait_for_login():
                return False

        # Tạo crawler riêng cho từng group (trạng thái + autosave tách biệt)
        for g in groups:
            crawlers[g] = MessageCrawler(
                driver,
                zalo_navigator,
                group_name=g,
                data_folder=get_group_data_folder(g),
            )
            crawlers[g].external_stop_flag = is_terminating

        idx = 0
        min_s = max(1, int(GROUP_SWITCH_MIN_SEC or 3))
        max_s = max(min_s, int(GROUP_SWITCH_MAX_SEC or 7))
        consecutive_recover_failures = 0
        max_recover_failures = 3  # Dừng recover sau 3 lần thất bại liên tiếp để tránh loop

        while not is_terminating():
            g = groups[idx % len(groups)]
            idx += 1

            # Điều hướng sang group và chỉ crawl khi xác nhận đúng group
            try:
                zalo_navigator.find_and_access_group(group_name=g)
                consecutive_recover_failures = 0
            except Exception as e:
                ctx = {"phase": "find_and_access_group", "group": g}
                try:
                    ctx["current_url"] = driver.current_url
                    ctx["page_title"] = driver.title
                except Exception:
                    pass
                log_error(e, context=ctx, extra_message="Lỗi khi tìm nhóm")
                if _is_browser_dead_error(e):
                    log(f"Lỗi browser khi tìm nhóm: {str(e)}", level=logging.ERROR)
                    if consecutive_recover_failures < max_recover_failures:
                        new_driver = _recover_browser_and_update_refs(
                            browser_manager, zalo_navigator, crawlers, groups, zalo_auth
                        )
                        if new_driver is not None:
                            driver = new_driver
                            consecutive_recover_failures = 0
                        else:
                            consecutive_recover_failures += 1
                else:
                    consecutive_recover_failures = 0

            crawler = crawlers[g]
            crawler.rotate_session_if_needed()
            try:
                crawler.crawl_step()
                consecutive_recover_failures = 0
            except Exception as e:
                ctx = {"phase": "crawl_step", "group": g}
                try:
                    ctx["current_url"] = driver.current_url
                    ctx["page_title"] = driver.title
                except Exception:
                    pass
                log_error(e, context=ctx, extra_message="Lỗi trong crawl_step")
                if _is_browser_dead_error(e):
                    log(f"Lỗi browser trong crawl_step: {str(e)}", level=logging.ERROR)
                    if consecutive_recover_failures < max_recover_failures:
                        new_driver = _recover_browser_and_update_refs(
                            browser_manager, zalo_navigator, crawlers, groups, zalo_auth
                        )
                        if new_driver is not None:
                            driver = new_driver
                            consecutive_recover_failures = 0
                        else:
                            consecutive_recover_failures += 1
                else:
                    log(f"({g}) Lỗi crawl_step: {str(e)}", level=logging.ERROR)
                    consecutive_recover_failures = 0

            sleep_s = random.randint(min_s, max_s)
            time.sleep(sleep_s)

        # Khi dừng: chốt file cho từng group
        from datetime import datetime
        now = datetime.now()
        for g, crawler in crawlers.items():
            try:
                with crawler.save_lock:
                    final_path = crawler.save_document(now)
                if final_path:
                    crawler.docx_handler.process_docx_format(final_path)
            except Exception:
                pass

        return True
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

def run_app(times=1):
    """Chạy ứng dụng một số lần nhất định"""
    for i in range(times):
        if is_terminating():
            log(f"Dừng thực thi sau {i}/{times} lượt chạy", level=logging.WARNING)
            break
            
        log(f"Lần chạy thứ {i+1}/{times}")
        
        try:
            # Khởi động chuỗi quy trình
            file_path = asyncio.run(crawl_messages())
            
            if file_path:
                countdown(3)
                browser_manager.close_chrome()
                countdown(3)
                docx_handler = DocxHandler()
                processed_file = docx_handler.process_docx_format(file_path)
                # File đã được gửi trong process_docx_format
        
        except Exception as run_error:
            log(f"Lỗi khi chạy crawler: {str(run_error)}", level=logging.ERROR)
            log_error(run_error, context={"phase": "run_app"}, extra_message="Lỗi khi chạy crawler (run_app)")
            
            # Kiểm tra xem có phải lỗi liên quan đến WebDriver không
            error_str = str(run_error).lower()
            if any(err in error_str for err in ["webdriver", "chrome", "connection", "timeout"]):
                log("Phát hiện lỗi WebDriver, đang khởi động lại toàn bộ...", level=logging.WARNING)
                
                # Gửi thông báo lỗi qua Telegram
                send_notification("⚠️ Phát hiện lỗi WebDriver, đang khởi động lại toàn bộ...")
            
            # Đảm bảo Chrome được đóng
            try:
                browser_manager.close_chrome()
            except:
                pass
            
            # Đợi một chút trước khi thử lại
            countdown(30)
        
        if is_terminating():
            break
            
        countdown(3)
        

def run_capture_structure():
    """
    Chạy Chrome, mở Zalo Web, đăng nhập (nếu cần), lấy cấu trúc trang (selectors, elements)
    và lưu ra file .md + .json trong data/logs/ để sau phát triển thêm tính năng.
    """
    from src.tools.zalo_structure_capture import capture_zalo_structure
    ensure_data_folder()
    driver = None
    try:
        log("Chế độ --capture-structure: khởi động Chrome, mở Zalo Web...", level=logging.INFO)
        driver = browser_manager.get_chrome_driver()
        zalo_navigator = ZaloNavigator(driver)
        zalo_auth = ZaloAuthManager(driver)
        zalo_navigator.open_zalo_web()
        if not zalo_auth.check_login_status():
            log("Chưa đăng nhập. Vui lòng quét QR (hoặc đăng nhập) trong vài phút...", level=logging.WARNING)
            if not zalo_auth.wait_for_login():
                log("Hết thời gian đăng nhập. Thoát.", level=logging.ERROR)
                return
        groups = [g for g in (GROUP_NAMES or []) if str(g).strip()]
        if groups:
            zalo_navigator.find_and_access_group(group_name=groups[0])
        path_md, path_json = capture_zalo_structure(driver)
        log(f"Đã lưu cấu trúc Zalo. Gửi file sau cho dev khi cần phát triển thêm:", level=logging.INFO)
        if path_md:
            log(f"  MD:  {path_md}", level=logging.INFO)
        if path_json:
            log(f"  JSON: {path_json}", level=logging.INFO)
    except Exception as e:
        log(f"Lỗi khi capture cấu trúc: {str(e)}", level=logging.ERROR)
        log_error(e, context={"phase": "run_capture_structure"}, extra_message="Lỗi trong --capture-structure")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        browser_manager.close_chrome()


def main():
    """Hàm chính điều khiển toàn bộ ứng dụng"""
    try:
        # Chế độ lấy cấu trúc Zalo Web (để phát triển thêm tính năng)
        if "--capture-structure" in sys.argv:
            init_signal_handlers()
            ensure_data_folder()
            run_capture_structure()
            return
        
        # Khởi tạo xử lý tín hiệu
        init_signal_handlers()
        
        # Log timezone đang sử dụng
        from src.utils.config import TIMEZONE, TIMEZONE_NAME
        if TIMEZONE:
            log(f"Timezone được cấu hình: {TIMEZONE_NAME}", level=logging.INFO)
        else:
            import time
            offset = time.timezone if (time.daylight == 0) else time.altzone
            offset_hours = offset / -3600
            log(f"Timezone: Hệ thống (UTC{offset_hours:+.0f})", level=logging.INFO)
        
        # Đảm bảo thư mục dữ liệu tồn tại
        ensure_data_folder()
        
        # Kiểm tra kết nối Telegram
        telegram_connected = check_telegram_connection()

        # Thêm vào sau phần kiểm tra kết nối Telegram thành công
        if telegram_connected:
            log("Kết nối Telegram thành công!")
            # Gửi thông báo khởi động về các kênh
            send_notification("🚀 Hệ thống Zalo Crawler đã khởi động")
            
            # Thử gửi cảnh báo với chat_id cụ thể
            try:
                log("Đang gửi tin nhắn cảnh báo test...", level=logging.INFO)
                from src.notification.telegram import ALERT_CHAT_ID
                send_alert("🔄 Bot cảnh báo đã sẵn sàng", chat_id=ALERT_CHAT_ID)
                log(f"Đã gửi tin nhắn test đến {ALERT_CHAT_ID}", level=logging.INFO)

            except Exception as e:
                log(f"Lỗi khi gửi tin nhắn test: {str(e)}", level=logging.ERROR)

        else:
            log("Không thể kết nối đến Telegram, thông báo sẽ chỉ ghi vào log", level=logging.WARNING)
        
        # Nếu cấu hình nhiều nhóm, chạy song song theo nhóm
        groups = [g for g in (GROUP_NAMES or []) if str(g).strip()]
        if len(groups) > 1:
            log(f"Chạy chế độ multi-group: {groups}", level=logging.INFO)
            run_multi_group_single_session(groups)
        else:
            # Single-group (giữ nguyên hành vi cũ)
            times_to_run = 1  # Mặc định chạy 1 lần
            run_app(times_to_run)
        
    except KeyboardInterrupt:
        # KeyboardInterrupt sẽ được xử lý bởi signal_handler
        pass
    except Exception as e:
        error_message = f"❌ Lỗi không xử lý được: {str(e)}"
        log(error_message, level=logging.CRITICAL)
        log_error(e, context={"phase": "main"}, extra_message="Lỗi không xử lý được trong main")
        send_error(error_message)
    finally:
        # Dừng browser
        try:
            browser_manager.close_chrome()
        except:
            pass
        
        log("Hệ thống đã dừng hoàn toàn.")

if __name__ == "__main__":
    main()