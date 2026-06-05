# Tham chiếu cấu hình – Biến môi trường và config

Liệt kê toàn bộ biến môi trường (.env) và giá trị đọc trong `src/utils/config.py` để setup dự án mới hoặc chỉnh hành vi mà không cần sửa code.

---

## 1. Cách đọc biến môi trường

- File `.env` đặt ở **thư mục gốc project** (cùng cấp với `main.py`).
- Module `src/utils/env_loader.py` dùng `python-dotenv` để `load_dotenv(.env)`; `config.py` gọi `get_env(key, default, type)`.
- Kiểu: `str` (mặc định), `bool`, `int`, `float`, `list` (tách theo dấu phẩy).

---

## 2. Chrome / trình duyệt

| Biến | Kiểu | Mặc định | Mô tả |
|------|------|----------|--------|
| `CHROME_USER_DATA_DIR` | str | `./chrome_user_data` | Thư mục profile Chrome (cookie, session). **Dùng cố định để không phải đăng nhập lại.** |
| `CHROME_DEBUG_PORT` | str | `9222` | Cổng remote-debugging. Tránh trùng với Chrome khác. |
| `HEADLESS` | bool | false | true = chạy Chrome không giao diện (server). |
| `CHROME_BINARY` | str | (none) | Đường dẫn chrome/chromium (vd. `/usr/bin/google-chrome`). Trên Linux có thể để trống để code tự tìm. |
| `CHROME_WINDOW_WIDTH` | int | 1920 | Chiều rộng cửa sổ. |
| `CHROME_WINDOW_HEIGHT` | int | 1080 | Chiều cao cửa sổ. |

---

## 3. Timeout driver (Selenium / Chrome)

| Biến | Kiểu | Mặc định | Mô tả |
|------|------|----------|--------|
| `DRIVER_PAGE_LOAD_TIMEOUT` | int | 300 | Timeout tải trang (giây). Tránh mặc định 120s dễ gây “Read timed out” rồi tab crash. |
| `DRIVER_SCRIPT_TIMEOUT` | int | 300 | Timeout chạy script (giây). |

---

## 4. Thời gian / interval

| Biến | Kiểu | Mặc định | Mô tả |
|------|------|----------|--------|
| `LOGIN_TIMEOUT` | int | 300 | Thời gian chờ đăng nhập (giây), dùng trong wait_for_login. |
| `MESSAGE_CRAWL_INTERVAL` | int | 1 | Khoảng thời gian giữa các lần crawl (giây) – tham khảo, logic thực tế dùng GROUP_SWITCH_* khi multi-group. |
| `KEYWORD_UPDATE_INTERVAL` | int | 60 | Chu kỳ đọc lại file keywords (giây). |
| `AUTOSAVE_INTERVAL` | int | 30 | Chu kỳ autosave (giây). |
| `GROUP_SWITCH_MIN_SEC` | int | 3 | Số giây tối thiểu nghỉ giữa hai lần chuyển nhóm (random min). |
| `GROUP_SWITCH_MAX_SEC` | int | 7 | Số giây tối đa nghỉ giữa hai lần chuyển nhóm (random max). |

---

## 5. Telegram

| Biến | Kiểu | Mặc định | Mô tả |
|------|------|----------|--------|
| `TELEGRAM_TOKEN` | str | (bắt buộc) | Token bot Telegram. |
| `ADMIN_CHAT_ID` | str/int | (none) | Chat ID nhận thông báo chính (số hoặc @username). |
| `ALERT_CHAT_ID` | str/int | (none) | Chat ID nhận cảnh báo từ khóa (và QR nếu dùng). |

---

## 6. Nhóm / room cần crawl

| Biến | Kiểu | Mặc định | Mô tả |
|------|------|----------|--------|
| `DEFAULT_GROUP_NAME` | str | (vd. RETURN ROOM LỊCH) | Tên nhóm mặc định khi chỉ có một nhóm. |
| `GROUP_NAMES` | list | (none) | Nhiều nhóm, phân cách bằng dấu phẩy. Nếu có thì dùng thay DEFAULT_GROUP_NAME. Ví dụ: `GROUP_NAMES=Room A,Room B,Room C`. Multi-room runtime hiện dùng thư mục dữ liệu riêng theo `group_slug` và artifact naming/path chuẩn hóa theo room/session/host. |

---

## 7. Thư mục và file

| Biến | Kiểu | Mặc định | Mô tả |
|------|------|----------|--------|
| `DATA_FOLDER` | str | `./data` | Thư mục gốc chứa data: logs, errors, docx, DB, keywords. |
| `LOGS_FOLDER` | str | `./logs` | Thư mục log (chromedriver.log, v.v.); có thể trùng hoặc khác DATA_FOLDER tùy code. |
| `MAX_MESSAGES` | int | 200 | Số tin tối đa lưu trong bộ nhớ (list unique) mỗi nhóm. |

Tên file DB và keywords cố định trong code: `DB_NAME = "zalo_messages.db"`, `KEYWORDS_FILE = "keywords.txt"` (thường nằm trong DATA_FOLDER hoặc path tương đối).

---

## 8. Timezone (tùy chọn)

| Biến | Kiểu | Mặc định | Mô tả |
|------|------|----------|--------|
| `TIMEZONE` | str | (none) | Tên timezone (vd. `Asia/Ho_Chi_Minh`). Cần `pytz`. Dùng cho get_local_now(), session_id, tên file. |

---

## 9. Giám sát hệ thống (tùy chọn)

| Biến | Kiểu | Mặc định | Mô tả |
|------|------|----------|--------|
| `SYSTEM_CHECK_INTERVAL` | int | 60 | Chu kỳ kiểm tra hệ thống (giây). |
| `CPU_THRESHOLD` | int | 80 | Ngưỡng CPU (%) cảnh báo. |
| `MEMORY_THRESHOLD` | int | 80 | Ngưỡng RAM (%) cảnh báo. |
| `DISK_THRESHOLD` | int | 90 | Ngưỡng disk (%) cảnh báo. |

---

## 10. Retry / logging

| Biến | Kiểu | Mặc định | Mô tả |
|------|------|----------|--------|
| `MAX_RETRIES` | int | 3 | Số lần thử lại tối đa (trong decorator retry). |
| `RETRY_DELAY` | int | 5 | Delay cơ bản giữa các lần retry (giây). |
| `REQUEST_TIMEOUT` | int | 30 | Timeout request (dùng ở chỗ gọi HTTP nếu có). |
| `LOG_LEVEL` | str | INFO | Mức log (DEBUG, INFO, WARNING, ERROR). |
| `LOG_FORMAT` | str | (format mặc định) | Chuỗi format log. |

---

## 11. Ví dụ .env tối thiểu cho dự án mới

```env
# Chrome – dùng profile riêng để giữ đăng nhập
CHROME_USER_DATA_DIR=./chrome_user_data
CHROME_DEBUG_PORT=9222
HEADLESS=false  # non-headless + Crawlbot Control cần tkinter/python3-tk trên máy đích

# Trang và nhóm (tên hiển thị đúng như trên web)
DEFAULT_GROUP_NAME=My Room Name
# Hoặc nhiều nhóm:
# GROUP_NAMES=Room A,Room B

# Telegram
TELEGRAM_TOKEN=123456:ABC...
ADMIN_CHAT_ID=2079315704
ALERT_CHAT_ID=-1002246274184

# Thư mục
DATA_FOLDER=./data
```

Các biến không set sẽ dùng giá trị mặc định trong `config.py`. Chi tiết kỹ thuật (profile Chrome, đăng nhập, crawl, recovery) xem **TECHNIQUES.md**; bước tạo dự án mới xem **NEW_PROJECT_GUIDE.md**; cấu trúc module xem **ARCHITECTURE.md**.
