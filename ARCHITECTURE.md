# Kiến trúc project – Cấu trúc thư mục và nhiệm vụ module

Mô tả cấu trúc thư mục và vai trò từng module để khi tạo dự án mới bạn biết **sửa file nào** cho URL/selector/nghiệp vụ mới.

---

## 1. Cấu trúc thư mục (gốc project)

```
crawlbot/
├── main.py                 # Entry: signal, Telegram check, chọn single/multi-group, gọi run_app hoặc run_multi_group_single_session
├── legacy/main1.py         # Snapshot cũ để tham chiếu khi cleanup, không phải entrypoint runtime
├── .env                    # Biến môi trường (không commit), xem CONFIG_REFERENCE.md
├── .env.example            # Mẫu biến env
├── requirements.txt        # Python dependencies
├── chrome_user_data/       # Profile Chrome (cookie, session) – không copy sang project mới
├── data/                   # Dữ liệu: logs, errors, docx, DB, keywords – tạo lại hoặc dùng DATA_FOLDER
├── src/
│   ├── auth/               # Đăng nhập
│   ├── browser/            # Chrome driver + điều hướng
│   ├── crawler/            # Crawl tin + xử lý từng tin
│   ├── monitoring/         # Từ khóa, (system monitor)
│   ├── notification/       # Telegram
│   ├── storage/            # Docx, DB, file
│   ├── tools/              # Capture cấu trúc trang
│   └── utils/              # Config, logger, error_logger, decorators, env, signals
```

---

## 2. Module và file – Nhiệm vụ / Khi nào sửa

### 2.1 `main.py`

- **Nhiệm vụ:** Khởi tạo signal, kiểm tra Telegram, đọc GROUP_NAMES; nếu nhiều nhóm thì `run_multi_group_single_session(groups)`, không thì `run_app()`. Xử lý `--capture-structure`. Bắt exception và gọi error_logger; khi “tab crashed” gọi recovery và cập nhật refs.
- **Sửa khi dự án mới:** Có thể đổi tên biến (GROUP_NAMES → ROOM_NAMES); logic recovery và refs giữ nguyên.

---

### 2.2 `src/browser/driver.py`

- **Nhiệm vụ:** Khởi tạo Chrome (Options: user-data-dir, remote-debugging-port, headless, timeout); restart driver; recover_session (mở lại URL); đóng Chrome và kill process liên quan (psutil).
- **Sửa khi dự án mới:** Trong `recover_session()` đổi URL mặc định `https://chat.zalo.me` thành URL trang của bạn.

---

### 2.3 `src/browser/navigation.py`

- **Nhiệm vụ:** Mở trang (open_zalo_web); tìm và vào nhóm (find_and_access_group: search box, conv-item, click, đợi header-title); reconnect_to_group.
- **Sửa khi dự án mới:** Đổi URL trong `open_zalo_web()`. Trong `find_and_access_group()` đổi toàn bộ selector: ô tìm kiếm, danh sách kết quả (vd. `.conv-item`), selector xác nhận đã vào room (vd. `.header-title`). Có thể đổi tên tham số `group_name` → `room_name`.

---

### 2.4 `src/auth/login.py`

- **Nhiệm vụ:** Kiểm tra đăng nhập (check_login_status: có ô search = đã đăng nhập, có QR = chưa); gửi QR qua Telegram (send_qr_to_telegram); đợi đăng nhập (wait_for_login); làm mới QR (refresh_qr_code).
- **Sửa khi dự án mới:** Thay selector “đã đăng nhập” (vd. `#contact-search-input`) và “chưa đăng nhập” (vd. `.qrcode img`). Nếu không dùng QR thì thay bằng flow đăng nhập khác (form, click, đợi redirect).

---

### 2.5 `src/crawler/message_crawler.py`

- **Nhiệm vụ:** Một “nhịp” crawl (crawl_step): kiểm tra đăng nhập và đúng nhóm; lấy danh sách `.chat-item`; với mỗi item gọi message_processor.process_chat_item; loại trùng; append autosave; kiểm tra từ khóa; cuộn (scroll_for_messages). Quản lý autosave, save_document, rotate_session_if_needed.
- **Sửa khi dự án mới:** Selector danh sách item (vd. `.chat-item`) và giới hạn số lượng (vd. 50). Có thể đổi tên biến group → room; logic autosave/rotate giữ nguyên.

---

### 2.6 `src/crawler/message_processor.py`

- **Nhiệm vụ:** Trích xuất từ một “chat item”: người gửi (get_sender_name), nội dung (extract_message_content), thời gian (extract_timestamp), trích dẫn (extract_quote); ghép thành một dòng (process_chat_item).
- **Sửa khi dự án mới:** Thay **toàn bộ selector** cho đúng DOM trang mới: bubble-message, message-sender-name-*, message-content-view, text-container, time, quote. Đây là file cần chỉnh nhiều nhất khi đổi web.

---

### 2.7 `src/storage/` (docx_handler, database, file_manager)

- **Nhiệm vụ:** Ghi docx (autosave, file cuối), chuẩn hóa format; DB (nếu dùng); quản lý đường dẫn file.
- **Sửa khi dự án mới:** Thường chỉ đổi tên file/heading/paragraph (vd. “Tin nhắn nhóm” → “Tin room X”). Cấu trúc thư mục theo room/group đã có (get_group_data_folder).

---

### 2.8 `src/monitoring/keyword_monitor.py`

- **Nhiệm vụ:** Đọc file keywords (vd. `data/keywords.txt`), so với nội dung tin, nếu trùng thì trả về từ khóa (để main/crawler gửi Telegram).
- **Sửa khi dự án mới:** Có thể đổi đường dẫn file keywords trong config; hoặc tắt nếu không cần.

---

### 2.9 `src/notification/` (telegram, alert)

- **Nhiệm vụ:** Gửi tin nhắn / file qua Telegram Bot API.
- **Sửa khi dự án mới:** Chỉ cần cấu hình đúng TELEGRAM_TOKEN, ADMIN_CHAT_ID, ALERT_CHAT_ID trong .env.

---

### 2.10 `src/utils/config.py`

- **Nhiệm vụ:** Đọc env (get_env), định nghĩa hằng (Chrome, Telegram, DATA_FOLDER, GROUP_NAMES, timeout, v.v.), slugify, get_group_data_folder, ensure_data_folder.
- **Sửa khi dự án mới:** Đổi tên biến (vd. GROUP_NAMES → ROOM_NAMES) nếu muốn; thêm biến mới cho nghiệp vụ đặc thù.

---

### 2.11 `src/utils/logger.py`, `error_logger.py`, `decorators.py`, `signals.py`

- **Nhiệm vụ:** Logger (file + console); error log (traceback + context + crash diagnostics); decorator retry khi lỗi WebDriver; xử lý signal (Ctrl+C) và cờ dừng.
- **Chuẩn hóa hiện tại:** artifact/log path builders ngoài Word naming đã được gom vào `src/utils/artifact_paths.py` (log file, error log, fail artifact, structure capture, autosave temp/backup).
- **Sửa khi dự án mới:** Thường không cần; chỉ khi đổi tên log/error file hoặc thêm loại lỗi đặc biệt. Nếu đổi naming/path, ưu tiên sửa builder trong `artifact_paths.py`.

---

### 2.12 `src/tools/zalo_structure_capture.py`

- **Nhiệm vụ:** Với driver đang mở trang, kiểm tra từng selector trong danh sách (ZALO_SELECTORS_REF), ghi số lượng và mẫu thuộc tính; thu thập mẫu class trên trang; ghi ra .md và .json.
- **Sửa khi dự án mới:** Thay danh sách selector (ZALO_SELECTORS_REF) bằng selector của trang mới; có thể đổi tên hàm/ file thành “page_structure_capture” cho dễ hiểu.

---

## 3. Luồng dữ liệu (tóm tắt)

1. **main.py** → khởi tạo driver (driver.py), navigator (navigation.py), auth (login.py).
2. Mở URL (navigation), kiểm tra đăng nhập (login); nếu chưa thì QR hoặc form (login).
3. Vòng lặp (main): với mỗi nhóm → find_and_access_group (navigation) → crawl_step (message_crawler).
4. **crawl_step:** lấy danh sách item (selector .chat-item), với mỗi item gọi **message_processor.process_chat_item** → chuỗi một dòng; loại trùng; append autosave (storage); kiểm tra từ khóa (monitoring); gửi cảnh báo (notification); cuộn (scroll).
5. Khi lỗi “tab crashed”/timeout: main gọi recovery (restart driver, cập nhật refs, recover_session, check_login lại); error_logger ghi traceback + context + crash diagnostics.

---

## 4. File nên sửa trước khi chạy cho web mới (ưu tiên)

| Thứ tự | File | Mục đích |
|--------|------|----------|
| 1 | `.env` | URL không đổi trong env nhưng DATA_FOLDER, GROUP/ROOM names, Telegram, Chrome path |
| 2 | `src/browser/navigation.py` | URL + selector tìm room và xác nhận vào room |
| 3 | `src/browser/driver.py` | URL trong recover_session |
| 4 | `src/auth/login.py` | Selector đã đăng nhập / chưa đăng nhập; flow QR hoặc form |
| 5 | `src/crawler/message_processor.py` | Toàn bộ selector sender, nội dung, thời gian, quote |
| 6 | `src/crawler/message_crawler.py` | Selector danh sách item (vd. .chat-item) |
| 7 | `src/utils/config.py` | (Tùy chọn) Đổi tên GROUP_NAMES → ROOM_NAMES hoặc thêm biến mới |

Các file còn lại (storage, notification, utils logger/error/decorators, tools capture) giữ nguyên hoặc chỉnh nhẹ (tên, đường dẫn). Chi tiết từng bước thao tác xem **NEW_PROJECT_GUIDE.md**.
