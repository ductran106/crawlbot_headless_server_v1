# Xử lý tin nhắn crawl được
# src/crawler/message_processor.py
import re
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from ..utils.logger import log, logging
from ..utils.browser_errors import is_browser_dead_error

class MessageProcessor:
    """Xử lý tin nhắn và trích xuất thông tin"""

    ATTACHMENT_LABELS = {
        "image": "[Hình ảnh]",
        "video": "[Video]",
        "file": "[Tệp đính kèm]",
        "link": "[Liên kết]",
        "sticker": "[Sticker]",
        "contact": "[Danh thiếp]",
        "location": "[Vị trí]",
        "voice": "[Tin nhắn thoại]",
    }
    
# Thêm biến previous_timestamp vào phương thức __init__
    def __init__(self, driver, current_user_name="Tôi"):
        """Khởi tạo MessageProcessor với WebDriver"""
        self.driver = driver
        self.current_user_name = current_user_name
        self.previous_sender = None
        self.previous_timestamp = None  # Thêm biến này để lưu thời gian tin nhắn trước đó
        self.message_sender_cache = {}
        self.last_message_metadata = {}
    
    def extract_with_js(self, chat_item, css_selector, attribute="textContent"):
        """Sử dụng JavaScript để trích xuất thông tin từ phần tử an toàn hơn"""
        try:
            script = f"""
                var element = arguments[0].querySelector('{css_selector}');
                return element ? element.{attribute}.trim() : '';
            """
            return self.driver.execute_script(script, chat_item)
        except Exception:
            return ""
    
    def _normalize_text(self, value):
        return " ".join((value or "").split())

    def _format_meta_block(self, label, value):
        value = self._normalize_text(value)
        return f"[{label}: {value}]" if value else f"[{label}]"

    def extract_reactions(self, chat_item):
        """Cố gắng bắt reaction summary theo nhiều selector/path khác nhau."""
        try:
            reactions = self.driver.execute_script("""
                var root = arguments[0];
                var selectors = [
                    '[data-component="reaction-summary"] [aria-label]',
                    '[class*="reaction"] [aria-label]',
                    '[data-component*="reaction"] [aria-label]',
                    '[class*="emoji"] [aria-label]'
                ];
                var seen = new Set();
                var values = [];
                selectors.forEach(function(selector) {
                    root.querySelectorAll(selector).forEach(function(el) {
                        var raw = (el.getAttribute('aria-label') || el.textContent || '').trim();
                        if (!raw || seen.has(raw)) return;
                        seen.add(raw);
                        values.push(raw);
                    });
                });
                return values;
            """, chat_item)
            if reactions:
                return f" [Reaction: {' | '.join(reactions)}]"
        except Exception:
            pass
        return ""

    def extract_system_markers(self, chat_item):
        """Bắt các marker như edited / recalled / system-state nếu có."""
        markers = []
        try:
            marker_data = self.driver.execute_script("""
                var root = arguments[0];
                var selectors = [
                    '.undo-message',
                    '.edited-message',
                    '.message-edited',
                    '.message-status',
                    '[data-component="message-status"]',
                    '.system-message',
                    '[data-component="system-message"]'
                ];
                var out = [];
                selectors.forEach(function(selector) {
                    root.querySelectorAll(selector).forEach(function(el) {
                        var text = (el.textContent || '').trim();
                        if (text) out.push(text);
                    });
                });
                return out;
            """, chat_item)
            for text in marker_data or []:
                norm = self._normalize_text(text)
                if not norm:
                    continue
                lowered = norm.lower()
                if 'thu hồi' in lowered or 'đã thu hồi' in lowered:
                    markers.append('[Thu hồi]')
                elif 'đã chỉnh sửa' in lowered or 'edited' in lowered or 'chỉnh sửa' in lowered:
                    markers.append('[Đã chỉnh sửa]')
                else:
                    markers.append(self._format_meta_block('System', norm))
        except Exception:
            pass
        deduped = []
        for marker in markers:
            if marker not in deduped:
                deduped.append(marker)
        return ''.join(f" {marker}" for marker in deduped)

    def extract_attachment_metadata(self, chat_item):
        """Cố gắng lấy metadata cho sticker/file/link/video/... ngoài text/image/voice cơ bản."""
        try:
            meta = self.driver.execute_script("""
                var root = arguments[0];
                function firstText(selectors) {
                    for (var i = 0; i < selectors.length; i++) {
                        var el = root.querySelector(selectors[i]);
                        if (el && el.textContent && el.textContent.trim()) return el.textContent.trim();
                    }
                    return '';
                }
                function has(selectors) {
                    return selectors.some(function(selector) { return root.querySelector(selector); });
                }
                return {
                    sticker: has(['.sticker-message', '[data-type="sticker"]', 'img[alt*="sticker" i]']),
                    file_name: firstText(['.file-name', '.attachment-file-name', '[data-component="file-name"]', '.file-message__name']),
                    file_size: firstText(['.file-size', '.attachment-file-size', '.file-message__size']),
                    link_title: firstText(['.link-msg__title', '.link-preview__title', 'a[href] .title']),
                    link_url: (root.querySelector('a[href]') || {}).href || '',
                    video_label: firstText(['.video-msg__desc', '.video-message__title', '[data-component="video-title"]']),
                    image_count: root.querySelectorAll('.img-msg-v2, .photo-message-v2, .image-box__image').length,
                    system_text: firstText(['.system-message', '[data-component="system-message"]'])
                };
            """, chat_item)
        except Exception:
            return ""

        blocks = []
        if meta.get('sticker'):
            blocks.append(self.ATTACHMENT_LABELS['sticker'])
        if meta.get('file_name'):
            label = f"{self.ATTACHMENT_LABELS['file']} {meta['file_name']}"
            if meta.get('file_size'):
                label += f" ({meta['file_size']})"
            blocks.append(label)
        if meta.get('link_title') or meta.get('link_url'):
            detail = meta.get('link_title') or meta.get('link_url')
            if meta.get('link_title') and meta.get('link_url') and meta['link_url'] not in detail:
                detail = f"{meta['link_title']} | {meta['link_url']}"
            blocks.append(f"{self.ATTACHMENT_LABELS['link']} {detail}".strip())
        if meta.get('video_label'):
            blocks.append(f"{self.ATTACHMENT_LABELS['video']} {meta['video_label']}".strip())
        if meta.get('system_text'):
            blocks.append(self._format_meta_block('System', meta['system_text']))

        deduped = []
        for block in blocks:
            normalized = self._normalize_text(block)
            if normalized and normalized not in deduped:
                deduped.append(normalized)
        return ''.join(f" {block}" for block in deduped)

    def get_sender_name(self, chat_item, max_retries=2):
        """Trích xuất tên người gửi từ chat_item với cơ chế thử lại và phòng ngừa"""
        for retry in range(max_retries):
            try:
                # Lấy ID của tin nhắn để phục vụ cache
                msg_id = None
                try:
                    message_div = chat_item.find_elements(By.CSS_SELECTOR, "[data-component='bubble-message']")
                    if message_div and len(message_div) > 0:
                        msg_id = message_div[0].get_attribute("id")
                    
                    # Kiểm tra trong cache trước
                    if msg_id and msg_id in self.message_sender_cache:
                        return self.message_sender_cache[msg_id]
                except Exception as id_error:
                    # Bỏ qua lỗi khi lấy ID, tiếp tục xử lý
                    pass
                
                # Kiểm tra nếu tin nhắn của mình (dựa vào class me)
                try:
                    class_attr = chat_item.get_attribute("class") or ""
                    html_content = chat_item.get_attribute("innerHTML") or ""
                    
                    if "message-wrapper--me" in html_content or "chat-item me" in class_attr or "me" in class_attr:
                        if msg_id:
                            self.message_sender_cache[msg_id] = self.current_user_name
                        return self.current_user_name
                except Exception as me_error:
                    # Bỏ qua lỗi khi kiểm tra tin nhắn của mình
                    pass
                
                # Sử dụng JavaScript để tìm tên người gửi - cách an toàn hơn
                try:
                    sender_name = self.driver.execute_script("""
                        var element = arguments[0].querySelector('.message-sender-name-content .truncate');
                        return element ? element.textContent.trim() : '';
                    """, chat_item)
                    
                    if sender_name:
                        self.previous_sender = sender_name
                        if msg_id:
                            self.message_sender_cache[msg_id] = sender_name
                        return sender_name
                except Exception as js_error:
                    # Bỏ qua lỗi JavaScript
                    pass
                
                # Tìm tên người gửi trong message-sender-name-bubble bằng JavaScript
                try:
                    bubble_name = self.driver.execute_script("""
                        var element = arguments[0].querySelector('.message-sender-name-bubble .truncate');
                        return element ? element.textContent.trim() : '';
                    """, chat_item)
                    
                    if bubble_name:
                        self.previous_sender = bubble_name
                        if msg_id:
                            self.message_sender_cache[msg_id] = bubble_name
                        return bubble_name
                except Exception as bubble_error:
                    # Bỏ qua lỗi JavaScript
                    pass
                
                # Cách truyền thống - thử lại nếu cần
                try:
                    # Tìm tên người gửi trong message-sender-name-content
                    sender_elements = chat_item.find_elements(By.CSS_SELECTOR, ".message-sender-name-content .truncate")
                    if sender_elements and len(sender_elements) > 0 and sender_elements[0].text.strip():
                        sender_name = sender_elements[0].text.strip()
                        self.previous_sender = sender_name
                        if msg_id:
                            self.message_sender_cache[msg_id] = sender_name
                        return sender_name
                    
                    # Tìm tên người gửi trong message-sender-name-bubble
                    bubble_elements = chat_item.find_elements(By.CSS_SELECTOR, ".message-sender-name-bubble .truncate")
                    if bubble_elements and len(bubble_elements) > 0 and bubble_elements[0].text.strip():
                        sender_name = bubble_elements[0].text.strip()
                        self.previous_sender = sender_name
                        if msg_id:
                            self.message_sender_cache[msg_id] = sender_name
                        return sender_name
                except Exception as element_error:
                    # Bỏ qua lỗi khi tìm kiếm phần tử theo cách truyền thống
                    pass
                
                # Kiểm tra class của chat-item để xác định phân nhóm
                try:
                    class_attr = chat_item.get_attribute("class") or ""
                    if "--s2" in class_attr and self.previous_sender:
                        if msg_id:
                            self.message_sender_cache[msg_id] = self.previous_sender
                        return self.previous_sender
                except Exception as class_error:
                    # Bỏ qua lỗi khi lấy thuộc tính class
                    pass
                
                # Nếu không thể xác định người gửi, sử dụng người gửi cuối cùng
                if self.previous_sender:
                    if msg_id:
                        self.message_sender_cache[msg_id] = self.previous_sender
                    return self.previous_sender
                
                # Không có cách nào xác định được, sử dụng tên mặc định có ý nghĩa
                default_name = "Người gửi"
                if msg_id:
                    self.message_sender_cache[msg_id] = default_name
                return default_name
                
            except Exception as e:
                # Nếu là lần thử cuối cùng, ghi log lỗi
                if retry == max_retries - 1:
                    log(f"Lỗi khi trích xuất tên người gửi (sau {max_retries} lần thử): {str(e)}", level=logging.ERROR)
                # Nếu chưa phải lần cuối, thử lại
                else:
                    time.sleep(0.1)
        
        # Trả về tên người gửi trước đó nếu đã có, ngược lại sử dụng giá trị mặc định
        if self.previous_sender:
            return self.previous_sender
        return "Người gửi"
    
    def extract_message_content(self, chat_item, max_retries=2):
        """Trích xuất nội dung tin nhắn từ chat_item - ưu tiên giữ đủ text/mention/emoji/attachments."""
        for retry in range(max_retries):
            try:
                message_view = None
                try:
                    message_views = chat_item.find_elements(By.CSS_SELECTOR, "[data-component='message-content-view']")
                    if message_views and len(message_views) > 0:
                        message_view = message_views[0]
                except Exception:
                    pass

                try:
                    undo_exists = self.driver.execute_script("""
                        return arguments[0].querySelector('.undo-message') !== null;
                    """, chat_item)
                    if undo_exists:
                        return "[Tin nhắn đã thu hồi]", "", ""
                except Exception:
                    pass

                try:
                    voice_exists = self.driver.execute_script("""
                        return arguments[0].querySelector('.voice-message, .voice-message-normal') !== null;
                    """, chat_item)
                    if voice_exists:
                        duration = self.extract_with_js(chat_item, ".voice-message-normal__duration-wrapper") or "00:00"
                        return "", "", f"[Tin nhắn thoại - {duration}]"
                except Exception:
                    pass

                try:
                    image_exists = self.driver.execute_script("""
                        return arguments[0].querySelector('.img-msg-v2, .photo-message-v2, .image-box__image') !== null;
                    """, chat_item)
                    if image_exists:
                        caption = self.driver.execute_script("""
                            var imgCapDiv = arguments[0].querySelector('.img-msg-v2__cap');
                            if (!imgCapDiv) return '';
                            var textContainer = imgCapDiv.querySelector('[data-component="text-container"]');
                            if (!textContainer) return '';
                            var textParts = [];
                            var children = textContainer.childNodes;
                            for (var i = 0; i < children.length; i++) {
                                var node = children[i];
                                if (node.nodeType === 3) textParts.push(node.textContent);
                                else if (node.nodeType === 1) textParts.push(node.textContent || '');
                            }
                            return textParts.join('').trim();
                        """, chat_item)
                        if caption:
                            return caption, "[Hình ảnh]", ""
                        return "", "[Hình ảnh]", ""
                except Exception:
                    pass

                try:
                    text_content = self.driver.execute_script("""
                        var container = arguments[0].querySelector('[data-component="message-text-content"]');
                        if (!container) return '';
                        var textContainer = container.querySelector('[data-component="text-container"]') || container;
                        var walker = document.createTreeWalker(textContainer, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, null);
                        var parts = [];
                        var node;
                        while (node = walker.nextNode()) {
                            if (node.nodeType === 3) {
                                parts.push(node.textContent || '');
                            } else if (node.nodeType === 1) {
                                var tag = (node.tagName || '').toLowerCase();
                                if (tag === 'img' && node.getAttribute('alt')) {
                                    parts.push(node.getAttribute('alt'));
                                }
                            }
                        }
                        return parts.join('').trim();
                    """, chat_item)
                    if text_content:
                        return text_content, "", ""
                except Exception as js_error:
                    log(f"Lỗi khi trích xuất text bằng JS: {str(js_error)}", level=logging.DEBUG)

                if message_view:
                    try:
                        text_container = message_view.find_element(By.CSS_SELECTOR, "[data-component='text-container']")
                        all_elements = text_container.find_elements(By.CSS_SELECTOR, "span.text, a.mention-name, a.text-is-phone-number, span.emoji-sizer")
                        combined_text = ''.join(element.text for element in all_elements if element.text)
                        if combined_text:
                            return combined_text, "", ""
                    except Exception as e:
                        log(f"Lỗi khi trích xuất text bằng Selenium: {str(e)}", level=logging.DEBUG)

                attachment_only = self.extract_attachment_metadata(chat_item)
                if attachment_only:
                    return "", attachment_only.strip(), ""

                try:
                    overflow_text = self.driver.execute_script("""
                        var container = arguments[0].querySelector('.overflow-hidden');
                        if (!container) return '';
                        return container.innerText;
                    """, chat_item)
                    if overflow_text:
                        return overflow_text, "", ""
                except Exception as overflow_error:
                    log(f"Lỗi khi trích xuất text từ overflow-hidden: {str(overflow_error)}", level=logging.DEBUG)
                    try:
                        overflow_containers = chat_item.find_elements(By.CSS_SELECTOR, ".overflow-hidden")
                        if overflow_containers and len(overflow_containers) > 0:
                            return overflow_containers[0].text, "", ""
                    except Exception:
                        pass

                return "[Không xác định]", "", ""
            except Exception as e:
                if retry == max_retries - 1:
                    level = logging.DEBUG if is_browser_dead_error(e) else logging.ERROR
                    log(f"Lỗi khi trích xuất nội dung tin nhắn: {str(e)}", level=level)
                else:
                    time.sleep(0.1)

        return "[Lỗi trích xuất]", "", ""
    
    def extract_quote(self, chat_item, max_retries=2):
        """Trích xuất phần trích dẫn nếu có - Phiên bản cải tiến"""
        for retry in range(max_retries):
            try:
                # Kiểm tra nếu có phần tử trích dẫn bằng JavaScript
                quote_exists = self.driver.execute_script("""
                    return arguments[0].querySelector('.message-quote-fragment__container') !== null;
                """, chat_item)
                
                if not quote_exists:
                    return ""
                
                # Lấy tên người được trích dẫn bằng JavaScript
                quote_name = self.extract_with_js(chat_item, ".quote-name")
                
                # Lấy nội dung trích dẫn bằng JavaScript
                quote_text = self.extract_with_js(chat_item, ".message-quote-fragment__description")
                
                # Tạo chuỗi trích dẫn đầy đủ
                if quote_name and quote_text:
                    return f'|||{quote_name}: {quote_text}|||'
                elif quote_name:
                    return f'|||{quote_name}|||'
                elif quote_text:
                    return f'|||{quote_text}|||'
                else:
                    return f'|||Trích dẫn|||'
                    
            except Exception as e:
                # Nếu là lần thử cuối cùng, ghi log lỗi
                if retry == max_retries - 1:
                    level = logging.DEBUG if is_browser_dead_error(e) else logging.ERROR
                    log(f"Lỗi khi trích xuất trích dẫn: {str(e)}", level=level)
                # Nếu chưa phải lần cuối, thử lại
                else:
                    time.sleep(0.1)
        
        return ""
    
    def _extract_exact_timestamp_from_qid(self, chat_item):
        """Cố gắng lấy timestamp chính xác từ data-qid trên message-content-view."""
        try:
            data_qid = self.driver.execute_script("""
                var root = arguments[0];
                var el = root.querySelector('[data-component="message-content-view"]');
                return el ? (el.getAttribute('data-qid') || '') : '';
            """, chat_item)
        except Exception:
            data_qid = ""

        if not data_qid:
            return {}

        match = re.search(r'@(\d{13})_', data_qid)
        if not match:
            return {}

        try:
            ts_ms = int(match.group(1))
            dt = datetime.fromtimestamp(ts_ms / 1000)
            return {
                "sent_at_exact": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "sent_at_ms": ts_ms,
                "render_time": dt.strftime("%H:%M:%S"),
                "timestamp_source": "exact_from_qid",
            }
        except Exception:
            return {}

    def _build_timestamp_metadata(self, raw_time, *, ingested_at=None):
        raw_time = self._normalize_text(raw_time)
        ingested_at = ingested_at or datetime.now()

        exact_meta = self.last_message_metadata.copy() if self.last_message_metadata else {}
        if exact_meta.get("timestamp_source") == "exact_from_qid":
            exact_meta.setdefault("ingested_at", ingested_at.strftime("%Y-%m-%d %H:%M:%S"))
            return exact_meta

        if raw_time and re.fullmatch(r"\d{2}:\d{2}:\d{2}", raw_time):
            return {
                "sent_at_exact": f"{ingested_at.strftime('%Y-%m-%d')} {raw_time}",
                "sent_at_ms": None,
                "render_time": raw_time,
                "timestamp_source": "exact_from_qid",
            }

        if ingested_at:
            return {
                "sent_at_exact": ingested_at.strftime("%Y-%m-%d %H:%M:%S"),
                "sent_at_ms": int(ingested_at.timestamp() * 1000),
                "render_time": ingested_at.strftime("%H:%M:%S"),
                "timestamp_source": "ingested_fallback",
            }

        if raw_time and re.fullmatch(r"\d{2}:\d{2}", raw_time):
            return {
                "sent_at_exact": None,
                "sent_at_ms": None,
                "render_time": f"{raw_time}:00",
                "timestamp_source": "minute_only_zero_second",
            }

        return {
            "sent_at_exact": None,
            "sent_at_ms": None,
            "render_time": "00:00:00",
            "timestamp_source": "minute_only_zero_second",
        }

    # Sửa phương thức extract_timestamp
    def _format_render_timestamp(self, date_str, raw_time):
        raw_time = self._normalize_text(raw_time)
        if raw_time and raw_time != "hh:mm":
            return f"*[{date_str} {raw_time}]"
        return f"*[{date_str} hh:mm]"

    def extract_timestamp(self, chat_item, max_retries=2):
        """Trích xuất thời gian gửi tin nhắn - Phiên bản cải tiến để xử lý tin nhắn liên tiếp"""
        self.last_message_metadata = {}
        for retry in range(max_retries):
            try:
                # Kiểm tra class của chat-item để xác định kiểu tin nhắn
                class_attr = chat_item.get_attribute("class") or ""
                is_consecutive = "--s2" in class_attr  # Tin nhắn liên tiếp từ cùng người gửi
                
                # Ưu tiên lấy timestamp chính xác từ data-qid nếu có
                exact_meta = self._extract_exact_timestamp_from_qid(chat_item)
                if exact_meta:
                    self.last_message_metadata = exact_meta
                    return exact_meta["render_time"]

                # Thử lấy thời gian bằng các cách thông thường trước
                timestamp = self.extract_with_js(chat_item, ".card-send-time__sendTime")
                if timestamp:
                    return timestamp
                
                timestamp = self.extract_with_js(chat_item, ".bubble-message-time")
                if timestamp:
                    return timestamp
                
                # Kiểm tra thêm các class đặc biệt khác có thể chứa thời gian
                timestamp = self.extract_with_js(chat_item, ".time-text")
                if timestamp:
                    return timestamp
                
                # Thử các cách truyền thống
                time_elements = chat_item.find_elements(By.CSS_SELECTOR, ".card-send-time__sendTime")
                if time_elements and len(time_elements) > 0:
                    return time_elements[0].text.strip()
                
                time_elements = chat_item.find_elements(By.CSS_SELECTOR, ".bubble-message-time")
                if time_elements and len(time_elements) > 0:
                    return time_elements[0].text.strip()
                
                # Nếu là tin nhắn liên tiếp và không tìm thấy thời gian, thử lấy từ người gửi trước đó
                if is_consecutive and self.previous_timestamp:
                    return self.previous_timestamp
                
                # Trường hợp không tìm thấy, sử dụng "hh:mm"
                return "hh:mm"
                
            except Exception as e:
                # Nếu là lần thử cuối cùng, ghi log lỗi
                if retry == max_retries - 1:
                    level = logging.DEBUG if is_browser_dead_error(e) else logging.ERROR
                    log(f"Lỗi khi trích xuất thời gian: {str(e)}", level=level)
                # Nếu chưa phải lần cuối, thử lại
                else:
                    time.sleep(0.1)
        
        # Trường hợp thất bại, sử dụng "hh:mm"
        return "hh:mm"
    
    # Sửa phần process_chat_item để lưu previous_timestamp
    def process_chat_item(self, chat_item):
        """Xử lý một chat-item và trích xuất thông tin - Version cải tiến"""
        try:
            # Sử dụng dict để lưu kết quả trích xuất
            extracted_data = {}
            
            # Trích xuất tên người gửi và lưu vào dict
            try:
                extracted_data['poster'] = self.get_sender_name(chat_item)
            except Exception as sender_error:
                log(f"Lỗi khi trích xuất tên người gửi trong process_chat_item: {str(sender_error)}", level=logging.ERROR)
                extracted_data['poster'] = self.previous_sender or "Người gửi"
            
            # Lưu lại người gửi cho tin nhắn tiếp theo
            self.previous_sender = extracted_data['poster']
            
            # Trích xuất nội dung tin nhắn
            try:
                extracted_data['msg_text'], extracted_data['pic'], extracted_data['voice'] = self.extract_message_content(chat_item)
            except Exception as content_error:
                level = logging.DEBUG if is_browser_dead_error(content_error) else logging.ERROR
                log(f"Lỗi khi trích xuất nội dung tin nhắn trong process_chat_item: {str(content_error)}", level=level)
                extracted_data['msg_text'], extracted_data['pic'], extracted_data['voice'] = "[Nội dung không thể trích xuất]", "", ""
            
            # Trích xuất phần trích dẫn
            try:
                extracted_data['quote_ok'] = self.extract_quote(chat_item)
            except Exception as quote_error:
                level = logging.DEBUG if is_browser_dead_error(quote_error) else logging.ERROR
                log(f"Lỗi khi trích xuất trích dẫn trong process_chat_item: {str(quote_error)}", level=level)
                extracted_data['quote_ok'] = ""
            
            # Trích xuất thời gian
            try:
                extracted_data['thoigian'] = self.extract_timestamp(chat_item)
                extracted_data['timestamp_meta'] = self._build_timestamp_metadata(
                    extracted_data['thoigian'],
                    ingested_at=datetime.now(),
                )
                extracted_data['thoigian'] = extracted_data['timestamp_meta']['render_time']
                self.previous_timestamp = extracted_data['thoigian']
            except Exception as time_error:
                level = logging.DEBUG if is_browser_dead_error(time_error) else logging.ERROR
                log(f"Lỗi khi trích xuất thời gian trong process_chat_item: {str(time_error)}", level=level)
                extracted_data['timestamp_meta'] = self._build_timestamp_metadata("", ingested_at=datetime.now())
                extracted_data['thoigian'] = extracted_data['timestamp_meta']['render_time']
            
            try:
                extracted_data['attachment_meta'] = self.extract_attachment_metadata(chat_item)
            except Exception as attachment_error:
                log(f"Lỗi khi trích xuất attachment metadata: {str(attachment_error)}", level=logging.ERROR)
                extracted_data['attachment_meta'] = ""

            try:
                extracted_data['reaction_meta'] = self.extract_reactions(chat_item)
            except Exception as reaction_error:
                log(f"Lỗi khi trích xuất reaction metadata: {str(reaction_error)}", level=logging.ERROR)
                extracted_data['reaction_meta'] = ""

            try:
                extracted_data['system_markers'] = self.extract_system_markers(chat_item)
            except Exception as marker_error:
                log(f"Lỗi khi trích xuất system markers: {str(marker_error)}", level=logging.ERROR)
                extracted_data['system_markers'] = ""

            # Tạo nội dung tin nhắn đầy đủ
            now = datetime.now()
            prefix = self._format_render_timestamp(now.strftime('%d/%m/%Y'), extracted_data['thoigian'])
            data_ok = (
                f"{prefix} "
                f"{extracted_data['poster']}: "
                f"{extracted_data['msg_text']}"
                f"{extracted_data['quote_ok']}"
                f"{extracted_data['pic']}"
                f"{extracted_data['voice']}"
                f"{extracted_data['attachment_meta']}"
                f"{extracted_data['reaction_meta']}"
                f"{extracted_data['system_markers']}"
            )
            
            return data_ok, extracted_data['msg_text']
            
        except Exception as e:
            log(f"Lỗi tổng thể khi xử lý chat-item: {str(e)}", level=logging.ERROR)
            
            # Tạo tin nhắn với thông tin tối thiểu
            now = datetime.now()
            poster = self.previous_sender or "Người gửi"
            prefix = self._format_render_timestamp(now.strftime('%d/%m/%Y'), "hh:mm")
            data_ok = f"{prefix} {poster}: [Nội dung không thể trích xuất]"
            return data_ok, ""