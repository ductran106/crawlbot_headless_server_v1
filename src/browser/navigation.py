# Điều hướng và tìm kiếm nhóm
# src/browser/navigation.py
import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from ..utils.logger import log, logging
from ..utils.config import DEFAULT_GROUP_NAME
from ..utils.browser_errors import is_browser_dead_error
from ..utils.decorators import retry_on_webdriver_error
from ..utils.error_logger import log_error
from ..utils.fail_artifacts import FailArtifactMixin
from ..utils.signals import is_terminating
from ..utils.status_codes import (
    ALREADY_LOGGED_IN,
    GROUP_OPENED_AT_NAVIGATION,
    GROUP_OPENED_UNVERIFIED,
    GROUP_OPENED_USABLE_UNVERIFIED,
    GROUP_SEARCH_EMPTY,
    LOGIN_STATE_UNKNOWN,
    NAVIGATION_STALL,
    QR_VISIBLE,
    RECONNECT_HEADER_UNVERIFIED,
    RECONNECT_USABLE_UNVERIFIED,
)

class ZaloNavigator(FailArtifactMixin):
    """Quản lý điều hướng trong Zalo Web"""
    
    def __init__(self, driver):
        """Khởi tạo ZaloNavigator với WebDriver đã được khởi tạo"""
        self.driver = driver
        self.last_navigation_result = None

    def _collect_conv_item_labels(self, conv_items, limit=5):
        labels = []
        for item in conv_items[:limit]:
            try:
                text = (item.text or "").strip()
            except Exception:
                text = ""
            if text:
                labels.append(text)
        return labels

    def _should_quiet_shutdown_browser_error(self, error):
        return is_terminating() and is_browser_dead_error(error)

    def _normalize_group_text(self, text):
        text = (text or "").strip().lower()
        text = re.sub(r"[^\w\s]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _strip_noise_tokens(self, text):
        normalized = self._normalize_group_text(text)
        if not normalized:
            return ""
        tokens = []
        for tok in normalized.split():
            if tok.isdigit():
                continue
            if re.fullmatch(r"\d+[a-z]+", tok) or re.fullmatch(r"[a-z]+\d+", tok):
                continue
            if len(tok) == 1 and tok.isalnum():
                continue
            tokens.append(tok)
        return " ".join(tokens).strip()

    def _target_tokens(self, group_name):
        normalized = self._normalize_group_text(group_name)
        return [p for p in normalized.split() if p]

    def _matches_target_group(self, candidate_text, group_name):
        candidate = self._normalize_group_text(candidate_text)
        target = self._normalize_group_text(group_name)
        if not candidate or not target:
            return False
        if target in candidate:
            return True

        candidate_stripped = self._strip_noise_tokens(candidate_text)
        target_stripped = self._strip_noise_tokens(group_name)
        if candidate_stripped and target_stripped:
            if target_stripped in candidate_stripped or candidate_stripped in target_stripped:
                return True

        parts = self._target_tokens(group_name)
        if not parts:
            return False
        return all(p in candidate for p in parts)

    def _clear_search_box(self, search_box):
        """Clear ô search theo hướng nhẹ tay trước, chỉ fallback khi thật sự cần."""
        try:
            current_value = (search_box.get_attribute("value") or "").strip()
        except Exception:
            current_value = ""

        if not current_value:
            return True

        try:
            search_box.click()
            time.sleep(0.05)
        except Exception:
            pass

        # Ưu tiên lane nhẹ: clear() + Ctrl+A/Delete một lần.
        try:
            search_box.clear()
            time.sleep(0.05)
        except Exception:
            pass

        try:
            current_value = (search_box.get_attribute("value") or "").strip()
        except Exception:
            current_value = ""
        if not current_value:
            return True

        try:
            search_box.send_keys(Keys.CONTROL, 'a')
            search_box.send_keys(Keys.DELETE)
            time.sleep(0.08)
        except Exception:
            pass

        try:
            current_value = (search_box.get_attribute("value") or "").strip()
        except Exception:
            current_value = ""
        if not current_value:
            return True

        # JS fallback chỉ dùng 1 lần cuối để giảm số remote/script call khi browser đang lag.
        try:
            self.driver.execute_script(
                "arguments[0].value=''; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
                search_box,
            )
            time.sleep(0.08)
        except Exception:
            pass

        try:
            return not bool((search_box.get_attribute("value") or "").strip())
        except Exception:
            return False

    def _extract_header_title_text(self):
        candidates = [
            ".header-title",
            ".header-title span",
            "header .header-title",
            "header [class*='header-title']",
            "[class*='header'] [class*='title']",
            "main header span",
            "header h1",
            "header h2",
        ]
        for selector in candidates:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                elements = []
            for el in elements:
                try:
                    text = (el.text or "").strip()
                except Exception:
                    text = ""
                if text:
                    return text
        return ""

    def _extract_active_sidebar_title_text(self):
        candidates = [
            ".conv-item.active",
            ".conv-item.selected",
            ".conv-item[aria-selected='true']",
            ".conversation-item.active",
            ".conversation-item.selected",
        ]
        for selector in candidates:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                elements = []
            for el in elements:
                try:
                    text = (el.text or "").strip()
                except Exception:
                    text = ""
                if text:
                    return text
        return ""

    def _extract_composer_target_text(self):
        candidates = [
            ".chat-input__footer",
            ".chat-input-container",
            ".composer-footer",
            ".input-message-container",
            "[class*='composer']",
            "[class*='input']",
            "footer",
        ]
        target_hints = ["tin nhắn tới", "nhắn tới", "gửi tới", "@"]; 
        for selector in candidates:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                elements = []
            for el in elements:
                try:
                    text = (el.text or "").strip()
                except Exception:
                    text = ""
                if not text:
                    continue
                lowered = text.lower()
                if any(hint in lowered for hint in target_hints):
                    return text
        return ""

    def _verify_composer_target(self, group_name):
        composer_text = self._extract_composer_target_text()
        composer_match = self._matches_target_group(composer_text, group_name)
        return composer_match, composer_text

    def _is_search_panel_open(self):
        try:
            search_box = self.driver.find_element(By.ID, "contact-search-input")
            value = (search_box.get_attribute("value") or "").strip()
            return bool(value)
        except Exception:
            return None

    def _build_navigation_result(self, *, ok, verify_mode, status_code, group_name, header_text="", sidebar_text="", composer_target_text="", clicked_item="", header_match=False, sidebar_match=False, composer_match=False, clicked_item_match=False, normalized_header="", normalized_sidebar="", normalized_composer="", normalized_target="", retry_attempt=0, possible_gap=False, gap_risk_reason=None, revisit_boost_hint=False, search_panel_open=None, stable_checks_required=1, stable_checks_reached=0, navigation_stall=False):
        result = {
            "ok": bool(ok),
            "verify_mode": verify_mode,
            "status_code": status_code,
            "group_name": group_name,
            "header_text": header_text or "",
            "sidebar_text": sidebar_text or "",
            "composer_target_text": composer_target_text or "",
            "clicked_item": clicked_item or "",
            "header_match": bool(header_match),
            "sidebar_match": bool(sidebar_match),
            "composer_match": bool(composer_match),
            "clicked_item_match": bool(clicked_item_match),
            "normalized_header": normalized_header or "",
            "normalized_sidebar": normalized_sidebar or "",
            "normalized_composer": normalized_composer or "",
            "normalized_target": normalized_target or "",
            "retry_attempt": int(retry_attempt or 0),
            "possible_gap": bool(possible_gap),
            "gap_risk_reason": gap_risk_reason,
            "revisit_boost_hint": bool(revisit_boost_hint),
            "search_panel_open": search_panel_open,
            "stable_checks_required": int(stable_checks_required or 1),
            "stable_checks_reached": int(stable_checks_reached or 0),
            "navigation_stall": bool(navigation_stall),
        }
        self.last_navigation_result = result
        return result

    def _build_verification_snapshot(self, group_name, clicked_item=None, retry_attempt=0, stable_checks_required=1, stable_checks_reached=0, navigation_stall=False):
        header_text = self._extract_header_title_text()
        sidebar_text = self._extract_active_sidebar_title_text()
        composer_match, composer_target_text = self._verify_composer_target(group_name)
        header_match = self._matches_target_group(header_text, group_name)
        sidebar_match = self._matches_target_group(sidebar_text, group_name)
        clicked_item_match = self._matches_target_group(clicked_item, group_name)
        return {
            "group_name": group_name,
            "header_text": header_text,
            "sidebar_text": sidebar_text,
            "composer_target_text": composer_target_text,
            "clicked_item": clicked_item or "",
            "header_match": header_match,
            "sidebar_match": sidebar_match,
            "composer_match": composer_match,
            "clicked_item_match": clicked_item_match,
            "normalized_header": self._strip_noise_tokens(header_text),
            "normalized_sidebar": self._strip_noise_tokens(sidebar_text),
            "normalized_composer": self._strip_noise_tokens(composer_target_text),
            "normalized_target": self._strip_noise_tokens(group_name),
            "retry_attempt": int(retry_attempt or 0),
            "stable_checks_required": int(stable_checks_required or 1),
            "stable_checks_reached": int(stable_checks_reached or 0),
            "search_panel_open": self._is_search_panel_open(),
            "navigation_stall": bool(navigation_stall),
        }

    def _classify_verification_mode(self, snapshot, strong_matched=False):
        if strong_matched:
            return "strong"
        header_or_sidebar = bool(snapshot.get("header_match") or snapshot.get("sidebar_match"))
        composer_match = bool(snapshot.get("composer_match"))
        clicked_item_match = bool(snapshot.get("clicked_item_match"))
        usable = (
            composer_match and (header_or_sidebar or clicked_item_match)
        ) or (
            header_or_sidebar and clicked_item_match
        )
        return "usable" if usable else "failed"

    def _wait_for_navigation_progress(self, group_name, timeout=12):
        deadline = time.time() + max(1.0, float(timeout or 12))
        while time.time() < deadline:
            try:
                header_text = self._extract_header_title_text()
                sidebar_text = self._extract_active_sidebar_title_text()
                composer_match, composer_text = self._verify_composer_target(group_name)
                if self._matches_target_group(header_text, group_name) or self._matches_target_group(sidebar_text, group_name) or composer_match:
                    return {
                        "progressed": True,
                        "navigation_stall": False,
                        "header_text": header_text,
                        "sidebar_text": sidebar_text,
                        "composer_target_text": composer_text,
                    }
            except Exception:
                pass
            time.sleep(0.2)
        return {
            "progressed": False,
            "navigation_stall": True,
            "header_text": self._extract_header_title_text(),
            "sidebar_text": self._extract_active_sidebar_title_text(),
            "composer_target_text": self._extract_composer_target_text(),
        }

    def _search_click_and_verify_group(self, group_name, search_box, phase_prefix="navigation.find_and_access_group", reconnect=False, retry_attempt=0):
        cleared = self._clear_search_box(search_box)
        if not cleared:
            log(f"Ô search chưa clear sạch trước khi tìm '{group_name}', sẽ tiếp tục theo lane nhẹ", level=logging.WARNING)

        try:
            search_box.send_keys(group_name)
        except Exception:
            self.driver.execute_script("arguments[0].focus();", search_box)
            search_box.send_keys(group_name)
        time.sleep(0.9 if not reconnect else 0.8)

        conv_items = self.driver.find_elements(By.CSS_SELECTOR, ".conv-item")
        labels = self._collect_conv_item_labels(conv_items)
        log(f"{'Reconnect search' if reconnect else 'Tìm thấy'} cho '{group_name}'; top_results={labels}", level=logging.DEBUG if reconnect else logging.INFO)

        for item in conv_items:
            item_text = item.text
            if not item_text:
                continue
            item_text_norm = item_text.strip()
            matched = self._matches_target_group(item_text_norm, group_name)
            if not matched:
                continue

            log(f"Tìm thấy nhóm phù hợp: '{item_text_norm}'")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", item)
            time.sleep(0.35)
            self.driver.execute_script("arguments[0].click();", item)
            log(f"Đã click vào nhóm '{group_name}'")

            try:
                progress = self._wait_for_navigation_progress(group_name, timeout=12)
                wait_result = self._wait_until_header_matches(group_name, timeout=5, stable_checks=1)
                snapshot = self._build_verification_snapshot(
                    group_name,
                    clicked_item=item_text_norm,
                    retry_attempt=retry_attempt,
                    stable_checks_required=wait_result["stable_checks_required"],
                    stable_checks_reached=wait_result["stable_checks_reached"],
                    navigation_stall=bool(progress.get("navigation_stall", False)),
                )
                verify_mode = self._classify_verification_mode(snapshot, strong_matched=wait_result["matched"])

                if verify_mode == "strong":
                    log(
                        f"Đã truy cập nhóm '{group_name}' thành công (reason={GROUP_OPENED_AT_NAVIGATION}; verify_mode=strong; header='{snapshot['header_text']}', sidebar='{snapshot['sidebar_text']}', normalized_header='{snapshot['normalized_header']}', normalized_sidebar='{snapshot['normalized_sidebar']}', normalized_target='{snapshot['normalized_target']}')."
                    )
                    self._warmup_room_after_open(scroll_rounds=1, settle_seconds=0.6 if not reconnect else 0.5)
                    return self._build_navigation_result(
                        ok=True,
                        verify_mode="strong",
                        status_code=GROUP_OPENED_AT_NAVIGATION,
                        group_name=group_name,
                        header_text=snapshot["header_text"],
                        sidebar_text=snapshot["sidebar_text"],
                        composer_target_text=snapshot["composer_target_text"],
                        clicked_item=snapshot["clicked_item"],
                        header_match=snapshot["header_match"],
                        sidebar_match=snapshot["sidebar_match"],
                        composer_match=snapshot["composer_match"],
                        clicked_item_match=snapshot["clicked_item_match"],
                        normalized_header=snapshot["normalized_header"],
                        normalized_sidebar=snapshot["normalized_sidebar"],
                        normalized_composer=snapshot["normalized_composer"],
                        normalized_target=snapshot["normalized_target"],
                        retry_attempt=retry_attempt,
                        stable_checks_required=snapshot["stable_checks_required"],
                        stable_checks_reached=snapshot["stable_checks_reached"],
                    )

                if verify_mode == "usable":
                    status_code = RECONNECT_USABLE_UNVERIFIED if reconnect else GROUP_OPENED_USABLE_UNVERIFIED
                    log(
                        f"Đã truy cập nhóm '{group_name}' ở degraded verify (reason={status_code}; verify_mode=usable; header='{snapshot['header_text']}', sidebar='{snapshot['sidebar_text']}', composer='{snapshot['composer_target_text']}', clicked_item='{snapshot['clicked_item']}')",
                        level=logging.WARNING,
                    )
                    self._warmup_room_after_open(scroll_rounds=1, settle_seconds=0.5)
                    return self._build_navigation_result(
                        ok=True,
                        verify_mode="usable",
                        status_code=status_code,
                        group_name=group_name,
                        header_text=snapshot["header_text"],
                        sidebar_text=snapshot["sidebar_text"],
                        composer_target_text=snapshot["composer_target_text"],
                        clicked_item=snapshot["clicked_item"],
                        header_match=snapshot["header_match"],
                        sidebar_match=snapshot["sidebar_match"],
                        composer_match=snapshot["composer_match"],
                        clicked_item_match=snapshot["clicked_item_match"],
                        normalized_header=snapshot["normalized_header"],
                        normalized_sidebar=snapshot["normalized_sidebar"],
                        normalized_composer=snapshot["normalized_composer"],
                        normalized_target=snapshot["normalized_target"],
                        retry_attempt=retry_attempt,
                        possible_gap=True,
                        gap_risk_reason="unverified_navigation",
                        revisit_boost_hint=True,
                        search_panel_open=snapshot["search_panel_open"],
                        stable_checks_required=snapshot["stable_checks_required"],
                        stable_checks_reached=snapshot["stable_checks_reached"],
                        navigation_stall=snapshot["navigation_stall"],
                    )

                if retry_attempt < 1:
                    log(f"Verify chưa đủ tin cậy cho '{group_name}', sẽ retry same-room 1 lần", level=logging.WARNING)
                    return self._search_click_and_verify_group(group_name, search_box, phase_prefix=phase_prefix, reconnect=reconnect, retry_attempt=retry_attempt + 1)

                reason = NAVIGATION_STALL if snapshot["navigation_stall"] else (RECONNECT_HEADER_UNVERIFIED if reconnect else GROUP_OPENED_UNVERIFIED)
                self.capture_fail_artifact(
                    phase=f"{phase_prefix}.verify",
                    reason=reason,
                    group_name=group_name,
                    extra={
                        "top_results": labels,
                        "header_text": snapshot["header_text"],
                        "sidebar_text": snapshot["sidebar_text"],
                        "composer_target_text": snapshot["composer_target_text"],
                        "clicked_item": snapshot["clicked_item"],
                        "header_match": snapshot["header_match"],
                        "sidebar_match": snapshot["sidebar_match"],
                        "composer_match": snapshot["composer_match"],
                        "clicked_item_match": snapshot["clicked_item_match"],
                        "verify_mode": verify_mode,
                        "stable_checks_required": snapshot["stable_checks_required"],
                        "stable_checks_reached": snapshot["stable_checks_reached"],
                        "search_panel_open": snapshot["search_panel_open"],
                        "retry_attempt": retry_attempt,
                        "navigation_stall": snapshot["navigation_stall"],
                    },
                )
                log(
                    f"Click xong nhưng verify thất bại cho '{group_name}'; header='{snapshot['header_text']}', sidebar='{snapshot['sidebar_text']}', composer='{snapshot['composer_target_text']}', clicked_item='{snapshot['clicked_item']}', retry_attempt={retry_attempt}, navigation_stall={snapshot['navigation_stall']}",
                    level=logging.WARNING,
                )
                return self._build_navigation_result(
                    ok=False,
                    verify_mode="failed",
                    status_code=reason,
                    group_name=group_name,
                    header_text=snapshot["header_text"],
                    sidebar_text=snapshot["sidebar_text"],
                    composer_target_text=snapshot["composer_target_text"],
                    clicked_item=snapshot["clicked_item"],
                    header_match=snapshot["header_match"],
                    sidebar_match=snapshot["sidebar_match"],
                    composer_match=snapshot["composer_match"],
                    clicked_item_match=snapshot["clicked_item_match"],
                    normalized_header=snapshot["normalized_header"],
                    normalized_sidebar=snapshot["normalized_sidebar"],
                    normalized_composer=snapshot["normalized_composer"],
                    normalized_target=snapshot["normalized_target"],
                    retry_attempt=retry_attempt,
                    possible_gap=True,
                    gap_risk_reason="navigation_stall" if snapshot["navigation_stall"] else "unverified_navigation",
                    revisit_boost_hint=True,
                    search_panel_open=snapshot["search_panel_open"],
                    stable_checks_required=snapshot["stable_checks_required"],
                    stable_checks_reached=snapshot["stable_checks_reached"],
                    navigation_stall=snapshot["navigation_stall"],
                )
            except Exception as e:
                if is_browser_dead_error(e):
                    level = logging.DEBUG if self._should_quiet_shutdown_browser_error(e) else logging.ERROR
                    log(f"Lỗi browser khi xác nhận nhóm: {str(e)}", level=level)
                    raise
                self.capture_fail_artifact(
                    phase=f"{phase_prefix}.verify",
                    reason=RECONNECT_HEADER_UNVERIFIED if reconnect else GROUP_OPENED_UNVERIFIED,
                    group_name=group_name,
                    extra={"top_results": labels, "clicked_item": item_text_norm, "retry_attempt": retry_attempt},
                )
                log(f"Không thể xác nhận tiêu đề nhóm: {str(e)}", level=logging.WARNING)
                return self._build_navigation_result(
                    ok=False,
                    verify_mode="failed",
                    status_code=RECONNECT_HEADER_UNVERIFIED if reconnect else GROUP_OPENED_UNVERIFIED,
                    group_name=group_name,
                    clicked_item=item_text_norm,
                    retry_attempt=retry_attempt,
                    possible_gap=True,
                    gap_risk_reason="unverified_navigation",
                    revisit_boost_hint=True,
                )

        self.capture_fail_artifact(
            phase=f"{phase_prefix}.search",
            reason=GROUP_SEARCH_EMPTY,
            group_name=group_name,
            extra={"top_results": labels},
        )
        log(
            f"Không tìm thấy nhóm '{group_name}' trong kết quả tìm kiếm; reason={GROUP_SEARCH_EMPTY}; top_results={labels}",
            level=logging.ERROR,
        )
        return self._build_navigation_result(
            ok=False,
            verify_mode="failed",
            status_code=GROUP_SEARCH_EMPTY,
            group_name=group_name,
            possible_gap=False,
            gap_risk_reason="wrong_room",
            revisit_boost_hint=False,
        )

    def _verify_current_group_title(self, group_name, timeout=5):
        header_selectors = [
            ".header-title",
            "header .header-title",
            "[class*='header'] [class*='title']",
            "main header span",
        ]
        last_error = None
        for selector in header_selectors:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                break
            except Exception as e:
                last_error = e
                continue
        else:
            if last_error:
                raise last_error

        header_text = self._extract_header_title_text()
        active_sidebar_text = self._extract_active_sidebar_title_text()
        header_match = self._matches_target_group(header_text, group_name)
        sidebar_match = self._matches_target_group(active_sidebar_text, group_name)
        return (header_match or sidebar_match), header_text, active_sidebar_text

    def _wait_until_header_matches(self, group_name, timeout=6, stable_checks=2):
        """Chờ room target xuất hiện ổn định; chấp nhận thêm lane verify từ sidebar active."""
        deadline = time.time() + max(0.5, float(timeout or 6))
        stable = 0
        last_header_text = ""
        last_sidebar_text = ""
        normalized_target = self._strip_noise_tokens(group_name)
        required = max(1, int(stable_checks or 1))

        while time.time() < deadline:
            matched, header_text, sidebar_text = self._verify_current_group_title(group_name, timeout=1)
            last_header_text = header_text
            last_sidebar_text = sidebar_text

            normalized_header = self._strip_noise_tokens(header_text)
            normalized_sidebar = self._strip_noise_tokens(sidebar_text)
            fallback_matched = bool(
                normalized_target and (
                    (normalized_header and (normalized_header in normalized_target or normalized_target in normalized_header))
                    or (normalized_sidebar and (normalized_sidebar in normalized_target or normalized_target in normalized_sidebar))
                )
            )

            if matched or fallback_matched:
                stable += 1
                if stable >= required:
                    return {
                        "matched": True,
                        "header_text": header_text,
                        "sidebar_text": sidebar_text,
                        "normalized_header": normalized_header,
                        "normalized_sidebar": normalized_sidebar,
                        "normalized_target": normalized_target,
                        "stable_checks_required": required,
                        "stable_checks_reached": stable,
                    }
            else:
                stable = 0
            time.sleep(0.2)

        return {
            "matched": False,
            "header_text": last_header_text,
            "sidebar_text": last_sidebar_text,
            "normalized_header": self._strip_noise_tokens(last_header_text),
            "normalized_sidebar": self._strip_noise_tokens(last_sidebar_text),
            "normalized_target": normalized_target,
            "stable_checks_required": required,
            "stable_checks_reached": stable,
        }

    def _warmup_room_after_open(self, scroll_rounds=1, settle_seconds=0.6):
        """Warmup nhẹ sau khi mở room để giảm render churn trong multi-room mode."""
        time.sleep(max(0.0, float(settle_seconds or 0.0)))
        for _ in range(max(0, int(scroll_rounds or 0))):
            self.driver.execute_script("""
                var chatContainer = document.querySelector('.chat-container, .conversation-list');
                if (chatContainer) {
                    chatContainer.scrollTop = 0;
                } else {
                    window.scrollTo(0, 0);
                }
            """)
            time.sleep(0.2)
            self.driver.execute_script("""
                var chatContainer = document.querySelector('.chat-container, .conversation-list');
                if (chatContainer) {
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                } else {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            """)
            time.sleep(0.2)
    
    @retry_on_webdriver_error(max_retries=3)
    def open_zalo_web(self):
        """Mở trang Zalo Web và đợi tải xong"""
        try:
            self.driver.get("https://chat.zalo.me/")
            # Đợi cho trang tải xong
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            log("Đã mở trang Zalo Web")
            return True
        except Exception as e:
            log(f"Lỗi khi mở Zalo Web: {str(e)}", level=logging.ERROR)
            return False
    
    @retry_on_webdriver_error(max_retries=2)
    def check_login_status(self):
        """Kiểm tra xem đã đăng nhập vào Zalo Web chưa.

        Giữ semantics đồng bộ với auth/login.py:
        - không nuốt nhầm lỗi browser chết/tab crash
        - phân biệt rõ logged-in / qr-visible / unknown-state trong log
        """
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "contact-search-input"))
            )
            log(f"Đã đăng nhập vào Zalo (reason={ALREADY_LOGGED_IN})")
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
            log(f"Chưa đăng nhập, cần quét mã QR (reason={QR_VISIBLE})")
            return False
        except Exception as e:
            if is_browser_dead_error(e):
                log(f"Lỗi browser khi kiểm tra QR đăng nhập: {str(e)}", level=logging.WARNING)
                raise
            self.capture_fail_artifact(phase="navigation.check_login_status", reason=LOGIN_STATE_UNKNOWN)
            log(f"Không thể xác định trạng thái đăng nhập (reason={LOGIN_STATE_UNKNOWN})", level=logging.WARNING)
            return False
    
    @retry_on_webdriver_error(max_retries=3)
    def find_and_access_group(self, group_name=None):
        """Tìm và truy cập nhóm chat Zalo; trả về status object giàu ngữ nghĩa verify/navigation."""
        if not group_name:
            group_name = DEFAULT_GROUP_NAME

        try:
            matched_current, header_text, sidebar_text = self._verify_current_group_title(group_name, timeout=1)
            if matched_current:
                snapshot = self._build_verification_snapshot(group_name, stable_checks_required=1, stable_checks_reached=1)
                log(
                    f"Đã ở sẵn trong nhóm '{group_name}' (header='{header_text}', sidebar='{sidebar_text}')",
                    level=logging.DEBUG,
                )
                return self._build_navigation_result(
                    ok=True,
                    verify_mode="strong",
                    status_code=GROUP_OPENED_AT_NAVIGATION,
                    group_name=group_name,
                    header_text=snapshot["header_text"],
                    sidebar_text=snapshot["sidebar_text"],
                    composer_target_text=snapshot["composer_target_text"],
                    clicked_item=snapshot["clicked_item"],
                    header_match=snapshot["header_match"],
                    sidebar_match=snapshot["sidebar_match"],
                    composer_match=snapshot["composer_match"],
                    clicked_item_match=snapshot["clicked_item_match"],
                    normalized_header=snapshot["normalized_header"],
                    normalized_sidebar=snapshot["normalized_sidebar"],
                    normalized_composer=snapshot["normalized_composer"],
                    normalized_target=snapshot["normalized_target"],
                    stable_checks_required=1,
                    stable_checks_reached=1,
                )
        except Exception as precheck_error:
            if is_browser_dead_error(precheck_error):
                raise

        try:
            search_box = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.ID, "contact-search-input"))
            )
            return self._search_click_and_verify_group(group_name, search_box, phase_prefix="navigation.find_and_access_group", reconnect=False)
        except Exception as e:
            level = logging.DEBUG if self._should_quiet_shutdown_browser_error(e) else logging.ERROR
            log(f"Lỗi khi tìm kiếm nhóm: {str(e)}", level=level)
            if not self._should_quiet_shutdown_browser_error(e):
                ctx = {"group_name": group_name, "phase": "find_and_access_group"}
                try:
                    ctx["current_url"] = self.driver.current_url
                    ctx["page_title"] = self.driver.title
                except Exception:
                    pass
                log_error(e, context=ctx, extra_message="Lỗi khi tìm kiếm nhóm")
            if is_browser_dead_error(e) or "Read timed out" in str(e) or "HTTPConnectionPool" in str(e):
                raise
            return self._build_navigation_result(
                ok=False,
                verify_mode="failed",
                status_code=GROUP_OPENED_UNVERIFIED,
                group_name=group_name,
                possible_gap=True,
                gap_risk_reason="unverified_navigation",
                revisit_boost_hint=True,
            )
    
    @retry_on_webdriver_error(max_retries=3)
    def reconnect_to_group(self, group_name=None):
        """Kết nối lại với nhóm chat sau khi làm mới trang; trả về status object."""
        if not group_name:
            group_name = DEFAULT_GROUP_NAME

        try:
            matched_current, header_text, sidebar_text = self._verify_current_group_title(group_name, timeout=1)
            if matched_current:
                snapshot = self._build_verification_snapshot(group_name, stable_checks_required=1, stable_checks_reached=1)
                log(
                    f"Reconnect bỏ qua search vì đã ở đúng room '{group_name}' (header='{header_text}', sidebar='{sidebar_text}')",
                    level=logging.DEBUG,
                )
                return self._build_navigation_result(
                    ok=True,
                    verify_mode="strong",
                    status_code=GROUP_OPENED_AT_NAVIGATION,
                    group_name=group_name,
                    header_text=snapshot["header_text"],
                    sidebar_text=snapshot["sidebar_text"],
                    composer_target_text=snapshot["composer_target_text"],
                    clicked_item=snapshot["clicked_item"],
                    header_match=snapshot["header_match"],
                    sidebar_match=snapshot["sidebar_match"],
                    composer_match=snapshot["composer_match"],
                    clicked_item_match=snapshot["clicked_item_match"],
                    normalized_header=snapshot["normalized_header"],
                    normalized_sidebar=snapshot["normalized_sidebar"],
                    normalized_composer=snapshot["normalized_composer"],
                    normalized_target=snapshot["normalized_target"],
                    stable_checks_required=1,
                    stable_checks_reached=1,
                )
        except Exception as precheck_error:
            if is_browser_dead_error(precheck_error):
                raise

        try:
            search_input = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.ID, "contact-search-input"))
            )
            return self._search_click_and_verify_group(group_name, search_input, phase_prefix="navigation.reconnect_to_group", reconnect=True)
        except Exception as e:
            level = logging.DEBUG if self._should_quiet_shutdown_browser_error(e) else logging.ERROR
            log(f"Lỗi khi kết nối lại với nhóm: {str(e)}", level=level)
            if is_browser_dead_error(e):
                raise
            return self._build_navigation_result(
                ok=False,
                verify_mode="failed",
                status_code=RECONNECT_HEADER_UNVERIFIED,
                group_name=group_name,
                possible_gap=True,
                gap_risk_reason="unverified_navigation",
                revisit_boost_hint=True,
            )
