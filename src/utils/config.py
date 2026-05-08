# src/utils/config.py
import os
import re
import socket
import unicodedata
from datetime import datetime
from .env_loader import get_env

# Telegram helpers
def _get_chat_id_env(key: str):
    """
    Đọc chat_id từ env.
    - Nếu là số (vd: 2079... hoặc -100...), trả int
    - Nếu là string khác (vd: @channelusername), trả str
    - Nếu rỗng/thiếu/sai kiểu, trả None
    """
    raw = get_env(key, None)
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    try:
        return int(s)
    except ValueError:
        return s

# Timezone configuration
TIMEZONE_NAME = get_env('TIMEZONE', None)
if TIMEZONE_NAME:
    try:
        import pytz
        TIMEZONE = pytz.timezone(TIMEZONE_NAME)
        log_timezone = TIMEZONE_NAME
    except ImportError:
        # Nếu chưa cài pytz, dùng timezone hệ thống
        TIMEZONE = None
        log_timezone = "system default (pytz not installed)"
    except Exception as e:
        TIMEZONE = None
        log_timezone = f"invalid ({str(e)})"
else:
    TIMEZONE = None
    log_timezone = "system default"

def get_local_now():
    """Lấy thời gian hiện tại với timezone (nếu được cấu hình)"""
    if TIMEZONE:
        return datetime.now(TIMEZONE)
    else:
        return datetime.now()

# Thư mục cài đặt
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cài đặt Chrome
DEFAULT_CHROME_USER_DATA_DIR = os.path.join(BASE_DIR, "chrome_user_data")
CHROME_USER_DATA_DIR = get_env('CHROME_USER_DATA_DIR', DEFAULT_CHROME_USER_DATA_DIR)
CHROME_DEBUG_PORT = get_env('CHROME_DEBUG_PORT', "9222")
HEADLESS = get_env('HEADLESS', False, bool)
CHROME_BINARY = get_env('CHROME_BINARY', None)
CHROME_WINDOW_WIDTH = get_env('CHROME_WINDOW_WIDTH', 1920, int)
CHROME_WINDOW_HEIGHT = get_env('CHROME_WINDOW_HEIGHT', 1080, int)

# Cài đặt thời gian
LOGIN_TIMEOUT = get_env('LOGIN_TIMEOUT', 300, int)  # giây
MESSAGE_CRAWL_INTERVAL = get_env('MESSAGE_CRAWL_INTERVAL', 1, int)   # Thời gian giữa các lần crawl (giây)
KEYWORD_UPDATE_INTERVAL = get_env('KEYWORD_UPDATE_INTERVAL', 60, int)  # Thời gian cập nhật từ khóa (giây)
AUTOSAVE_INTERVAL = get_env('AUTOSAVE_INTERVAL', 30, int)  # Thời gian tự động lưu (giây)
MULTI_ROOM_STABLE_WAIT_2ROOM = get_env('MULTI_ROOM_STABLE_WAIT_2ROOM', 1.5, float)
MULTI_ROOM_STABLE_WAIT_3ROOM = get_env('MULTI_ROOM_STABLE_WAIT_3ROOM', 1.0, float)
SCHED_MAX_CONSECUTIVE_VISITS = get_env('SCHED_MAX_CONSECUTIVE_VISITS', 2, int)
SCHED_STARVATION_SEC_2ROOM = get_env('SCHED_STARVATION_SEC_2ROOM', 6, int)
SCHED_STARVATION_SEC_3ROOM = get_env('SCHED_STARVATION_SEC_3ROOM', 8, int)
SCHED_HOT_SLEEP_SEC = get_env('SCHED_HOT_SLEEP_SEC', 1, int)
SCHED_PRESSURE_SLEEP_SEC = get_env('SCHED_PRESSURE_SLEEP_SEC', 2, int)
SCHED_NORMAL_SLEEP_MIN_SEC_2ROOM = get_env('SCHED_NORMAL_SLEEP_MIN_SEC_2ROOM', 2, int)
SCHED_NORMAL_SLEEP_MAX_SEC_2ROOM = get_env('SCHED_NORMAL_SLEEP_MAX_SEC_2ROOM', 3, int)
SCHED_NORMAL_SLEEP_MIN_SEC_3ROOM = get_env('SCHED_NORMAL_SLEEP_MIN_SEC_3ROOM', 2, int)
SCHED_NORMAL_SLEEP_MAX_SEC_3ROOM = get_env('SCHED_NORMAL_SLEEP_MAX_SEC_3ROOM', 4, int)

# Cài đặt Telegram
TELEGRAM_TOKEN = get_env('TELEGRAM_TOKEN')
ADMIN_CHAT_ID = _get_chat_id_env('ADMIN_CHAT_ID')
ALERT_CHAT_ID = _get_chat_id_env('ALERT_CHAT_ID')

# Cài đặt nhóm Zalo
DEFAULT_GROUP_NAME = get_env('DEFAULT_GROUP_NAME', "RETURN ROOM LỊCH")
# Cho phép cấu hình nhiều nhóm, ví dụ:
# GROUP_NAMES=RETURN ROOM LỊCH,RET 2 ROOM LỊCH
_GROUP_NAMES_RAW = get_env('GROUP_NAMES', None, list)
if _GROUP_NAMES_RAW:
    GROUP_NAMES = [x.strip() for x in _GROUP_NAMES_RAW if str(x).strip()]
else:
    GROUP_NAMES = [DEFAULT_GROUP_NAME]

# Thời gian chuyển group (random) để giảm hành vi bot
GROUP_SWITCH_MIN_SEC = get_env('GROUP_SWITCH_MIN_SEC', 5, int)
GROUP_SWITCH_MAX_SEC = get_env('GROUP_SWITCH_MAX_SEC', 15, int)

# Cài đặt lưu trữ
DEFAULT_DATA_FOLDER = os.path.join(BASE_DIR, "data")
DEFAULT_LOGS_FOLDER = os.path.join(BASE_DIR, "logs")
DATA_FOLDER = get_env('DATA_FOLDER', DEFAULT_DATA_FOLDER)
LOGS_FOLDER = get_env('LOGS_FOLDER', DEFAULT_LOGS_FOLDER)
MAX_MESSAGES = get_env('MAX_MESSAGES', 200, int)          # Số lượng tin nhắn tối đa lưu trữ trong bộ nhớ
DB_NAME = "zalo_messages.db"
KEYWORDS_FILE = "keywords.txt"

def slugify(text: str) -> str:
    """Tạo slug an toàn cho tên file/thư mục."""
    if text is None:
        return "group"
    s = str(text).strip()
    if not s:
        return "group"
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:64] or "group"

def get_group_data_folder(group_name: str, base_folder: str = None) -> str:
    """Thư mục dữ liệu riêng theo từng group (tránh đụng file/db giữa các group)."""
    base = base_folder or DATA_FOLDER
    return os.path.join(base, slugify(group_name))

# Cài đặt giám sát hệ thống
SYSTEM_CHECK_INTERVAL = get_env('SYSTEM_CHECK_INTERVAL', 60, int)
CPU_THRESHOLD = get_env('CPU_THRESHOLD', 80, int)
MEMORY_THRESHOLD = get_env('MEMORY_THRESHOLD', 80, int)
DISK_THRESHOLD = get_env('DISK_THRESHOLD', 90, int)

# Cài đặt retry và timeout
MAX_RETRIES = get_env('MAX_RETRIES', 3, int)
RETRY_DELAY = get_env('RETRY_DELAY', 5, int)
REQUEST_TIMEOUT = get_env('REQUEST_TIMEOUT', 30, int)
# Timeout cho Selenium/Chrome (tránh Read timed out 120s dẫn tới tab crash)
DRIVER_PAGE_LOAD_TIMEOUT = get_env('DRIVER_PAGE_LOAD_TIMEOUT', 300, int)   # giây
DRIVER_SCRIPT_TIMEOUT = get_env('DRIVER_SCRIPT_TIMEOUT', 300, int)         # giây
DRIVER_PROACTIVE_RECYCLE_MINUTES = get_env('DRIVER_PROACTIVE_RECYCLE_MINUTES', 180, int)
DRIVER_PROACTIVE_RECYCLE_ROOM_CYCLES = get_env('DRIVER_PROACTIVE_RECYCLE_ROOM_CYCLES', 900, int)

# Cài đặt logging
LOG_LEVEL = get_env('LOG_LEVEL', 'INFO')
LOG_FORMAT = get_env('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Lấy tên máy tính
COMPUTER_NAME = socket.gethostname()

def get_session_suffix(now=None):
    """Xác định suffix phiên theo giờ địa phương.

    Mapping chuẩn hóa:
    - 00:00:00 - 08:59:59 -> P1
    - 09:00:00 - 11:59:59 -> P2
    - 12:00:00 - 14:59:59 -> P3
    - 15:00:00 - 17:59:59 -> P4
    - 18:00:00 - 20:59:59 -> P5
    - 21:00:00 - 23:59:59 -> P6
    """
    if now is None:
        now = get_local_now()

    total_seconds = now.hour * 3600 + now.minute * 60 + now.second

    if total_seconds < 9 * 3600:
        return "P1"
    elif total_seconds < 12 * 3600:
        return "P2"
    elif total_seconds < 15 * 3600:
        return "P3"
    elif total_seconds < 18 * 3600:
        return "P4"
    elif total_seconds < 21 * 3600:
        return "P5"
    else:
        return "P6"

# Hàm tiện ích để xác định phiên làm việc dựa trên thời gian
def get_session_id(time=None):
    """Lấy ID phiên dựa trên thời gian (chính xác đến giây)."""
    if time is None:
        time = get_local_now()
    suffix = get_session_suffix(time)
    return f"{time.strftime('%Y%m%d')}_{suffix}"


def get_next_session_boundary(now=None):
    """Trả về mốc thời gian kết thúc của phiên hiện tại theo giờ địa phương."""
    if now is None:
        now = get_local_now()

    boundaries = [
        (9, 0, 0),
        (12, 0, 0),
        (15, 0, 0),
        (18, 0, 0),
        (21, 0, 0),
    ]
    for hour, minute, second in boundaries:
        candidate = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if now < candidate:
            return candidate
    return now.replace(hour=23, minute=59, second=59, microsecond=0)


def get_session_run_seconds(now=None):
    """Số giây còn lại đến mốc kết thúc phiên hiện tại."""
    if now is None:
        now = get_local_now()
    boundary = get_next_session_boundary(now)
    return max(0.0, (boundary - now).total_seconds())


def has_session_changed(previous_session_id: str, now=None) -> bool:
    """Kiểm tra xem thời điểm hiện tại đã sang session business mới hay chưa."""
    if not previous_session_id:
        return False
    return get_session_id(now) != previous_session_id


def build_autosave_docx_name(session_id: str, hostname: str, group_slug: str) -> str:
    """Tên file autosave chuẩn cho một room/session."""
    return f"autosave_{session_id}_{hostname}_{group_slug}.docx"


def build_final_docx_name(session_id: str, hostname: str, group_slug: str, message_count: int) -> str:
    """Tên file raw final chuẩn cho một room/session."""
    message_count = max(0, int(message_count or 0))
    return f"final_{session_id}_{hostname}_{group_slug}_{message_count}mess.docx"


def build_formatted_docx_name(session_id: str, hostname: str, group_slug: str, message_count: int) -> str:
    """Tên file deliverable đã format chuẩn cho một room/session."""
    message_count = max(0, int(message_count or 0))
    return f"Lich_{session_id}_{hostname}_{group_slug}_{message_count}mess_crawl.docx"


# Hàm tiện ích để tạo tên file dựa trên thời gian
def get_file_name(now=None, prefix="", suffix=""):
    """Tạo tên file dựa trên thời gian hiện tại"""
    if now is None:
        now = get_local_now()

    # Xác định suffix dựa vào thời gian
    time_suffix = get_session_suffix(now)

    # Tên file: thời gian 24h, dùng - thay : (tránh ký tự không hợp lệ trên Windows)
    file_name = now.strftime("%m-%d_%H-%M") + f'_{time_suffix}-{COMPUTER_NAME}{suffix}'
    return file_name

# Đảm bảo thư mục dữ liệu tồn tại
def ensure_data_folder(folder=None):
    """Đảm bảo thư mục dữ liệu tồn tại"""
    if folder is None:
        folder = DATA_FOLDER
    
    if not os.path.exists(folder):
        os.makedirs(folder)
        return True
    return False

# Log timezone sẽ được gọi sau khi logger được khởi tạo
# (tránh circular import)