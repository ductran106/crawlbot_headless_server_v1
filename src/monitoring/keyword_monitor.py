# Giám sát từ khóa
# src/monitoring/keyword_monitor.py
import threading
import time

from ..utils.logger import log, logging
from ..utils.config import KEYWORD_UPDATE_INTERVAL
from ..storage.file_manager import load_keywords
from ..notification.telegram import send_alert

class KeywordMonitor:
    """Giám sát từ khóa trong tin nhắn"""
    
    def __init__(self):
        """Khởi tạo KeywordMonitor"""
        self.keywords = load_keywords()
        self.running = False
        self.update_thread = None
    
    def start_monitoring(self):
        """Bắt đầu giám sát từ khóa"""
        if not self.running:
            self.running = True
            self.update_thread = threading.Thread(target=self.update_keywords_periodically, daemon=True)
            self.update_thread.start()
            log("Đã bắt đầu giám sát từ khóa")
            return True
        return False
    
    def stop_monitoring(self):
        """Dừng giám sát từ khóa"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=1)
        log("Đã dừng giám sát từ khóa")
        return True
    
    def update_keywords_periodically(self):
        """Cập nhật từ khóa định kỳ"""
        while self.running:
            try:
                updated_keywords = load_keywords()
                
                # Kiểm tra xem có thay đổi không
                if set(updated_keywords) != set(self.keywords):
                    old_count = len(self.keywords)
                    new_count = len(updated_keywords)
                    self.keywords = updated_keywords
                    log(f"Đã cập nhật danh sách từ khóa: {old_count} → {new_count}")
                    
                time.sleep(KEYWORD_UPDATE_INTERVAL)
            except Exception as e:
                log(f"Lỗi khi cập nhật từ khóa: {str(e)}", level=logging.ERROR)
                time.sleep(60)  # Nếu lỗi, đợi 1 phút trước khi thử lại
    ###
    def check_keywords(self, msg_text):
        """Kiểm tra tin nhắn có chứa từ khóa nào không với độ chính xác cao hơn"""
        if not msg_text or not self.keywords:
            return []
        
        # Chuẩn hóa tin nhắn: chuyển thành chữ thường và thêm khoảng trắng ở đầu/cuối
        # để dễ dàng kiểm tra ranh giới từ
        msg_text_lower = " " + msg_text.lower() + " "
        
        # Loại bỏ các dấu câu phổ biến và thay thế bằng khoảng trắng
        # để tránh các từ dính liền với dấu câu
        for punct in ['.', ',', '!', '?', ':', ';', '-', '(', ')', '[', ']', '{', '}', '"', "'"]:
            msg_text_lower = msg_text_lower.replace(punct, ' ')
        
        # Đảm bảo chỉ có một khoảng trắng giữa các từ
        while '  ' in msg_text_lower:
            msg_text_lower = msg_text_lower.replace('  ', ' ')
        
        matching_keywords = []
        
        for keyword in self.keywords:
            keyword_lower = keyword.lower()
            
            # Kiểm tra từ khóa đơn (một từ)
            if ' ' not in keyword_lower:
                # Thêm khoảng trắng vào đầu và cuối để tạo ranh giới từ
                padded_keyword = " " + keyword_lower + " "
                if padded_keyword in msg_text_lower:
                    matching_keywords.append(keyword)
            
            # Kiểm tra từ khóa phức (nhiều từ)
            else:
                # Kiểm tra theo cụm từ chính xác
                padded_keyword = " " + keyword_lower + " "
                if padded_keyword in msg_text_lower:
                    matching_keywords.append(keyword)
                
                # Kiểm tra các từ tách rời (tất cả các từ phải xuất hiện)
                else:
                    keyword_parts = keyword_lower.split()
                    # Kiểm tra từng từ có ranh giới từ
                    all_parts_found = True
                    for part in keyword_parts:
                        padded_part = " " + part + " "
                        if padded_part not in msg_text_lower:
                            all_parts_found = False
                            break
                    
                    if all_parts_found:
                        matching_keywords.append(keyword)
        
        # Ghi log chi tiết khi tìm thấy từ khóa
        if matching_keywords:
            log(f"Tìm thấy từ khóa trong tin nhắn: '{msg_text}'. Từ khóa: {matching_keywords}", 
                level=logging.DEBUG)
        
        return matching_keywords
    
    def process_message(self, msg_text):
        """Xử lý tin nhắn và kiểm tra từ khóa"""
        if not msg_text:
            return []
        
        matching_keywords = self.check_keywords(msg_text)
        if matching_keywords:
            keyword_alert = f"🔍 Phát hiện từ khóa: {', '.join(matching_keywords)} trong: {msg_text}"
            log(keyword_alert, level=logging.WARNING)
            send_alert(keyword_alert)
        
        return matching_keywords