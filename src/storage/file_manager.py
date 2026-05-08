# Quản lý file và thư mục
# src/storage/file_manager.py
import os

from ..utils.logger import log, logging
from ..utils.config import DATA_FOLDER, KEYWORDS_FILE

def load_keywords():
    """Đọc danh sách từ khóa từ file"""
    # Tạo một vài từ khóa mặc định
    default_keywords = ["hạ long", "bãi cháy", "tuần châu", "ha long", "halong"]
    
    # Kiểm tra và tạo file keywords.txt nếu chưa tồn tại
    keywords_path = os.path.join(DATA_FOLDER, KEYWORDS_FILE)
    if not os.path.exists(keywords_path):
        os.makedirs(os.path.dirname(keywords_path), exist_ok=True)
        with open(keywords_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(default_keywords))
    
    # Đọc từ khóa từ file
    try:
        with open(keywords_path, 'r', encoding='utf-8') as f:
            return [line.strip().lower() for line in f if line.strip()]
    except Exception as e:
        log(f"Lỗi khi đọc file từ khóa: {str(e)}", level=logging.ERROR)
        return default_keywords

def create_directory_if_not_exists(directory):
    """Tạo thư mục nếu chưa tồn tại"""
    if not os.path.exists(directory):
        os.makedirs(directory)
        log(f"Đã tạo thư mục: {directory}")
        return True
    return False

def get_full_path(filename, subfolder=None):
    """Trả về đường dẫn đầy đủ cho file"""
    base_dir = DATA_FOLDER
    if subfolder:
        base_dir = os.path.join(base_dir, subfolder)
        create_directory_if_not_exists(base_dir)
    
    return os.path.join(base_dir, filename)

def save_text_to_file(text, filename, subfolder=None):
    """Lưu văn bản vào file"""
    try:
        full_path = get_full_path(filename, subfolder)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(text)
        log(f"Đã lưu văn bản vào file: {full_path}")
        return full_path
    except Exception as e:
        log(f"Lỗi khi lưu văn bản vào file: {str(e)}", level=logging.ERROR)
        return None            