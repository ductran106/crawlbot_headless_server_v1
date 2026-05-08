# Xử lý biến môi trường
# src/utils/env_loader.py
import os
from dotenv import load_dotenv
from pathlib import Path

def load_env():
    """Load biến môi trường từ file .env hoặc file override qua ENV_FILE."""
    project_root = Path(__file__).parents[2]
    env_file = os.getenv('ENV_FILE', '.env').strip() or '.env'
    env_path = Path(env_file)
    if not env_path.is_absolute():
        env_path = project_root / env_file
    load_dotenv(env_path)

def get_env(key, default=None, type=str):
    """Lấy giá trị biến môi trường với kiểu dữ liệu tương ứng"""
    # Lấy raw string từ env; nếu không có thì trả default (có thể là bool/int/...)
    raw = os.getenv(key)
    # Treat missing/empty values as unset
    if raw is None:
        return default
    if isinstance(raw, str) and raw.strip() == "":
        return default
        
    # Chuyển đổi kiểu dữ liệu
    if type == bool:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ('true', '1', 'yes', 'y', 'on')
    elif type == int:
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            return default
    elif type == float:
        try:
            return float(str(raw).strip())
        except (TypeError, ValueError):
            return default
    elif type == list:
        return [item.strip() for item in str(raw).split(',')]
    else:
        return str(raw)

# Load biến môi trường khi import module
load_env() 