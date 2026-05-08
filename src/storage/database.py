# Xử lý database
# src/storage/database.py
import os
import re
import sqlite3
from datetime import datetime

from ..utils.logger import log, logging
from ..utils.config import DATA_FOLDER, DB_NAME

class DatabaseManager:
    """Quản lý cơ sở dữ liệu SQLite"""

    def _normalize_timestamp_metadata(self, timestamp_text, metadata=None):
        metadata = dict(metadata or {})
        timestamp_text = (timestamp_text or "").strip()
        ingested_at = metadata.get("ingested_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if metadata.get("sent_at_exact"):
            return {
                "sent_at_exact": metadata.get("sent_at_exact"),
                "sent_at_ms": metadata.get("sent_at_ms"),
                "ingested_at": ingested_at,
                "timestamp_source": metadata.get("timestamp_source") or "exact_from_qid",
            }

        match_exact = re.match(r"(\d{2}/\d{2}/\d{4}) (\d{2}:\d{2}:\d{2})", timestamp_text)
        if match_exact:
            day, time_part = match_exact.groups()
            sent_at_exact = datetime.strptime(f"{day} {time_part}", "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
            return {
                "sent_at_exact": sent_at_exact,
                "sent_at_ms": metadata.get("sent_at_ms"),
                "ingested_at": ingested_at,
                "timestamp_source": metadata.get("timestamp_source") or "exact_from_qid",
            }

        match_minute = re.match(r"(\d{2}/\d{2}/\d{4}) (\d{2}:\d{2})", timestamp_text)
        if match_minute:
            day, time_part = match_minute.groups()
            if metadata.get("timestamp_source") == "minute_only_zero_second":
                sent_at_exact = datetime.strptime(f"{day} {time_part}:00", "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                return {
                    "sent_at_exact": sent_at_exact,
                    "sent_at_ms": None,
                    "ingested_at": ingested_at,
                    "timestamp_source": "minute_only_zero_second",
                }

        return {
            "sent_at_exact": None,
            "sent_at_ms": None,
            "ingested_at": ingested_at,
            "timestamp_source": metadata.get("timestamp_source") or "ingested_fallback",
        }
    
    def __init__(self, db_path=None):
        """Khởi tạo DatabaseManager với đường dẫn database tùy chọn"""
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = os.path.join(DATA_FOLDER, DB_NAME)
        
        # Đảm bảo thư mục tồn tại
        if not os.path.exists(os.path.dirname(self.db_path)):
            os.makedirs(os.path.dirname(self.db_path))
        
        # Khởi tạo database
        self.init_database()
    
    def init_database(self):
        """Khởi tạo database và tạo các bảng cần thiết"""
        try:
            # Kết nối đến database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tạo bảng messages nếu chưa tồn tại
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                sender TEXT,
                content TEXT,
                message_type TEXT,
                group_name TEXT,
                has_image INTEGER,
                has_voice INTEGER,
                has_quote INTEGER,
                raw_message TEXT,
                created_at TEXT,
                sent_at_exact TEXT,
                sent_at_ms INTEGER,
                ingested_at TEXT,
                timestamp_source TEXT
            )
            ''')

            # Safe migrations for older DBs
            existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(messages)")}
            migrations = {
                "sent_at_exact": "ALTER TABLE messages ADD COLUMN sent_at_exact TEXT",
                "sent_at_ms": "ALTER TABLE messages ADD COLUMN sent_at_ms INTEGER",
                "ingested_at": "ALTER TABLE messages ADD COLUMN ingested_at TEXT",
                "timestamp_source": "ALTER TABLE messages ADD COLUMN timestamp_source TEXT",
            }
            for column, sql in migrations.items():
                if column not in existing_columns:
                    cursor.execute(sql)
            
            # Tạo bảng keywords nếu chưa tồn tại
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE,
                created_at TEXT
            )
            ''')
            
            # Tạo bảng keyword_matches nếu chưa tồn tại
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyword_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                keyword_id INTEGER,
                created_at TEXT,
                FOREIGN KEY (message_id) REFERENCES messages (id),
                FOREIGN KEY (keyword_id) REFERENCES keywords (id)
            )
            ''')
            
            # Tạo bảng sessions nếu chưa tồn tại
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                start_time TEXT,
                end_time TEXT,
                computer_name TEXT,
                message_count INTEGER,
                status TEXT
            )
            ''')
            
            # Commit thay đổi và đóng kết nối
            conn.commit()
            conn.close()
            
            log("Đã khởi tạo database thành công")
            return True
        except Exception as e:
            log(f"Lỗi khi khởi tạo database: {str(e)}", level=logging.ERROR)
            return False
    
    def save_messages(self, messages, group_name):
        """
        Lưu tin nhắn vào database
        
        Args:
            messages (list): Danh sách tin nhắn cần lưu
            group_name (str): Tên nhóm chat
            
        Returns:
            int: Số tin nhắn đã lưu thành công
        """
        try:
            # Kết nối đến database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Đếm số tin nhắn đã lưu
            saved_count = 0
            
            # Lưu tin nhắn vào database
            for message in messages:
                try:
                    record = message if isinstance(message, dict) else {"raw_message": message}
                    raw_message = record.get("raw_message", "")

                    # Phân tích tin nhắn để trích xuất thông tin
                    # Format: *[16/03/2025 20:58:42] Người gửi: Nội dung
                    parts = raw_message.split("] ", 1)
                    if len(parts) >= 2:
                        timestamp_part = parts[0].replace("*[", "")
                        rest_part = parts[1]
                        
                        # Tách người gửi và nội dung
                        sender_content = rest_part.split(": ", 1)
                        if len(sender_content) >= 2:
                            sender = record.get("sender") or sender_content[0]
                            content = record.get("content") or sender_content[1]
                        else:
                            sender = record.get("sender") or "Unknown"
                            content = record.get("content") or rest_part
                        
                        # Xác định loại tin nhắn
                        message_type = record.get("message_type") or "text"
                        has_image = record.get("has_image", 1 if "[Hình ảnh]" in content else 0)
                        has_voice = record.get("has_voice", 1 if "[Tin nhắn thoại" in content else 0)
                        has_quote = record.get("has_quote", 1 if "|||" in content else 0)
                        
                        if message_type == "text":
                            if has_image:
                                message_type = "image"
                            if has_voice:
                                message_type = "voice"
                            if has_quote:
                                message_type = "quote"

                        timestamp_meta = self._normalize_timestamp_metadata(timestamp_part, {
                            "sent_at_exact": record.get("sent_at_exact"),
                            "sent_at_ms": record.get("sent_at_ms"),
                            "ingested_at": record.get("ingested_at"),
                            "timestamp_source": record.get("timestamp_source"),
                        })
                        
                        # Thêm vào database
                        cursor.execute('''
                        INSERT INTO messages 
                        (timestamp, sender, content, message_type, group_name, has_image, has_voice, has_quote, raw_message, created_at, sent_at_exact, sent_at_ms, ingested_at, timestamp_source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            timestamp_part,
                            sender,
                            content,
                            message_type,
                            group_name,
                            has_image,
                            has_voice,
                            has_quote,
                            raw_message,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            timestamp_meta["sent_at_exact"],
                            timestamp_meta["sent_at_ms"],
                            timestamp_meta["ingested_at"],
                            timestamp_meta["timestamp_source"],
                        ))
                        
                        saved_count += 1
                except Exception as item_error:
                    log(f"Lỗi khi lưu tin nhắn vào database: {str(item_error)}", level=logging.ERROR)
                    continue
            
            # Commit thay đổi và đóng kết nối
            conn.commit()
            conn.close()
            
            log(f"Đã lưu {saved_count}/{len(messages)} tin nhắn vào database")
            return saved_count
        except Exception as e:
            log(f"Lỗi khi lưu vào database: {str(e)}", level=logging.ERROR)
            return 0