# Hướng dẫn tạo dự án mới từ project crawlbot

Checklist từng bước để nhân bản project này và triển khai cho web/ứng dụng khác (cùng mô hình: đăng nhập web, crawl theo room/nhóm, lưu docx).

---

## Bước 1: Copy project

- Copy toàn bộ thư mục `crawlbot` thành tên mới (vd. `my_chat_crawler`).
- **Không copy** (hoặc xóa sau): `chrome_user_data/`, `data/`, `.venv/`, `*.log`, `zalo_cookies.pkl` (nếu có). Giữ `.env.example`, sửa thành `.env` và điền giá trị mới.

---

## Bước 2: Đổi tên / branding (tùy chọn)

- Đổi tên hiển thị trong log/Telegram: tìm chuỗi "Zalo", "zalo_crawler" trong code và thay bằng tên dự án (vd. "Chat Crawler"). Có thể giữ nguyên logger name `zalo_crawler` nếu không cần.
- `README.md`: cập nhật mô tả dự án mới.

---

## Bước 3: Xác định URL và trang đăng nhập

- **URL trang chính** (sau khi đăng nhập): vd. `https://chat.example.com`.
- **Selector “đã đăng nhập”**: phần tử chỉ có khi đã login (vd. ô tìm kiếm: `#contact-search-input`).
- **Selector “chưa đăng nhập”**: phần tử chỉ có khi chưa login (vd. form login hoặc `.qrcode img`).

Cập nhật trong code:

- `src/browser/navigation.py`: `open_zalo_web()` → đổi URL thành trang của bạn; giữ hoặc đổi tên hàm.
- `src/auth/login.py`: trong `check_login_status()` thay `#contact-search-input` và `.qrcode img` bằng selector thực tế của trang mới.
- `src/browser/driver.py`: trong `recover_session()` thay `https://chat.zalo.me` bằng URL trang của bạn.

---

## Bước 4: Selectors cho “room” / nhóm và tin nhắn

- **Tìm room/nhóm**: ô tìm kiếm (id/selector), danh sách kết quả (vd. `.conv-item`), cách match tên (chuỗi hoặc từ khóa).
- **Click vào room**: click bằng JS lên item đã match; đợi element chứng tỏ đã vào room (vd. `.header-title`).
- **Một “tin nhắn” / item cần crawl**: selector chung (vd. `.chat-item`).
- **Trong mỗi item**: sender, nội dung, thời gian (vd. `.message-sender-name-content .truncate`, `[data-component='message-content-view']`, `.bubble-message-time`).

Cập nhật trong code:

- `src/browser/navigation.py`: `find_and_access_group()` – thay selector ô search, selector danh sách (`.conv-item`), selector xác nhận vào room (`.header-title`). Có thể đổi tên tham số `group_name` thành `room_name` nếu muốn.
- `src/crawler/message_crawler.py`: `crawl_step()` – selector danh sách item (vd. `.chat-item`), giới hạn số lượng (vd. 50).
- `src/crawler/message_processor.py`: toàn bộ selector bên trong `get_sender_name()`, `extract_message_content()`, `extract_timestamp()`, `extract_quote()` – thay bằng selector đúng với DOM trang mới.

Tham khảo bảng selector trong **TECHNIQUES.md** (mục 10) và **SELECTORS_REFERENCE.md** (nếu tạo); với trang mới nên chạy **capture structure** (bước 7) để có bảng selector thực tế.

---

## Bước 5: Cấu hình (.env và config)

- Copy `.env.example` thành `.env`.
- Điền/sửa theo **CONFIG_REFERENCE.md**:
  - Chrome: `CHROME_USER_DATA_DIR`, `CHROME_DEBUG_PORT`, `HEADLESS`, `CHROME_BINARY` (nếu cần).
  - Timeout: `DRIVER_PAGE_LOAD_TIMEOUT`, `DRIVER_SCRIPT_TIMEOUT`, `LOGIN_TIMEOUT`.
  - Ứng dụng: `DATA_FOLDER`, `GROUP_NAMES` hoặc `DEFAULT_GROUP_NAME` (có thể đổi thành ROOM_NAMES / ROOM_NAME cho dự án mới).
  - Telegram: `TELEGRAM_TOKEN`, `ADMIN_CHAT_ID`, `ALERT_CHAT_ID`.

Nếu đổi tên biến (vd. `GROUP_NAMES` → `ROOM_NAMES`): sửa trong `src/utils/config.py` và mọi chỗ import (main, crawler, …).

---

## Bước 6: Đăng nhập (QR / form)

- Nếu trang mới **không dùng QR**: bỏ hoặc thay logic trong `src/auth/login.py` (send_qr_to_telegram, wait_for_login) bằng flow đăng nhập của bạn (điền form, click nút, đợi redirect).
- Nếu vẫn dùng QR nhưng selector khác: đổi selector `.qrcode img`, `.qrcode-expired`, `.qrcode-expired .btn` trong `login.py` cho đúng trang.

---

## Bước 7: Capture cấu trúc trang mới (khuyến nghị)

- Chạy: `python main.py --capture-structure` (sau khi đã sửa URL và selector “đã đăng nhập” để vào được trang).
- Hoặc tạm sửa `run_capture_structure()` trong `main.py`: mở URL trang mới, đăng nhập (thủ công hoặc script), rồi gọi `capture_zalo_structure(driver)` (có thể đổi tên hàm trong `src/tools/zalo_structure_capture.py` thành `capture_page_structure` và sửa danh sách selector trong file đó cho trang mới).
- Kết quả: file `.md` và `.json` trong `data/logs/` – dùng làm bảng selector tham chiếu khi sửa `navigation.py` và `message_processor.py`.

---

## Bước 8: Format dữ liệu (tin nhắn / item)

- Trong `src/crawler/message_processor.py`, hàm `process_chat_item()` trả về chuỗi một dòng (vd. `*[dd/mm/yyyy hh:mm:ss] Sender: Nội dung...`). Có thể đổi format cho phù hợp dự án (vd. CSV, JSON, hoặc cấu trúc khác).
- Định dạng file xuất (docx): `src/storage/docx_handler.py`, `message_crawler.py` (autosave, save_document) – đổi tên file, heading, paragraph nếu cần. Naming hiện tại đã có helper canonical trong `src/utils/config.py`; nếu đổi schema tên file, ưu tiên sửa helper thay vì format string rải rác.

---

## Bước 9: Từ khóa / cảnh báo (tùy chọn)

- File từ khóa: `data/keywords.txt` (mỗi dòng một từ). Module `src/monitoring/keyword_monitor.py` đọc file này và so với nội dung tin; nếu trùng thì gửi cảnh báo Telegram. Giữ nguyên hoặc đổi đường dẫn trong config.
- Nếu không cần: có thể tắt gọi `keyword_monitor.check_keywords()` trong `message_crawler.py`.

---

## Bước 10: Test

> Lưu ý cho chế độ non-headless: nếu dùng `Crawlbot Control` mini-window, máy đích cần có `tkinter`.
> - Ubuntu/Debian: cài `python3-tk`

1. Chạy Chrome không headless: `HEADLESS=false` (hoặc `HEADLESS=False` trong .env), chạy `python main.py` – kiểm tra mở đúng URL, đăng nhập, vào đúng room, crawl được tin.
2. Nếu dùng non-headless + `Crawlbot Control`, xác nhận mini control window xuất hiện và nút `Dừng an toàn & đóng Chrome` hoạt động.
3. Kiểm tra autosave: có file trong `DATA_FOLDER` (hoặc thư mục từng room), nội dung đúng format.
4. Bật headless (nếu chạy server): `HEADLESS=true`, test lại đăng nhập (QR gửi Telegram hoặc session đã lưu trong profile).
5. Test recovery: tạm dừng Chrome hoặc kill tab, xem log có phát hiện “tab crashed” và restart + recover session đúng không.

---

## Tóm tắt file cần sửa khi đổi web/ứng dụng

| File | Nội dung cần đổi |
|------|-------------------|
| `src/browser/navigation.py` | URL mở trang; selector ô search, danh sách room, xác nhận vào room |
| `src/browser/driver.py` | URL trong `recover_session()` |
| `src/auth/login.py` | Selector đã đăng nhập / chưa đăng nhập; logic QR hoặc form login |
| `src/crawler/message_crawler.py` | Selector danh sách item (vd. `.chat-item`); có thể đổi tên group → room |
| `src/crawler/message_processor.py` | Toàn bộ selector: sender, nội dung, thời gian, trích dẫn |
| `src/utils/config.py` | Tên biến GROUP_NAMES / DEFAULT_GROUP_NAME (nếu đổi); có thể thêm ROOM_* |
| `.env` | Giá trị thực tế (path Chrome, Telegram, DATA_FOLDER, ROOM/GROUP names) |
| `src/tools/zalo_structure_capture.py` | Danh sách selector tham chiếu (ZALO_SELECTORS_REF) cho trang mới khi dùng capture |

Sau khi làm xong các bước trên, bạn có một bản “nhân bản” chạy cho web/ứng dụng mới; chi tiết kỹ thuật vẫn tham khảo **TECHNIQUES.md**, cấu trúc module **ARCHITECTURE.md**, biến môi trường **CONFIG_REFERENCE.md**.
