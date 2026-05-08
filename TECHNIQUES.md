# Tài liệu kỹ thuật – Zalo Web Crawler

Mô tả chi tiết các kỹ thuật dùng trong project này để có thể tái sử dụng khi triển khai dự án mới tương tự (crawl web app cần đăng nhập, giữ phiên, crawl theo nhóm/conversation).

---

## 1. Tổng quan kiến trúc

- **Stack:** Python 3.10+, Selenium 4, Chrome/Chromium, python-docx, Telegram Bot API.
- **Luồng chính:** Khởi động Chrome với **user profile riêng** → Mở trang web (Zalo) → Kiểm tra đăng nhập (có ô search = đã đăng nhập, có QR = chưa) → Nếu chưa: gửi QR qua Telegram, đợi quét → Tìm và vào từng nhóm → Crawl tin nhắn (DOM) → Lưu autosave + file cuối → Có thể chạy nhiều nhóm trong một session, luân phiên.
- **Module chính:** `browser/driver` (Chrome), `auth/login` (đăng nhập + QR), `browser/navigation` (tìm nhóm, click), `crawler/message_crawler` (vòng lặp crawl), `crawler/message_processor` (trích xuất từng tin), `storage` (docx, db), `utils` (config, logger, error_logger, decorators).

---

## 2. Cách mở trình duyệt (Chrome)

### 2.1 Công nghệ

- **Selenium WebDriver** với **ChromeDriver** (Chrome for Testing hoặc Chrome/Chromium cài sẵn).
- Dùng **Chrome Options** để:
  - Chỉ định **thư mục profile** (`--user-data-dir`) → **lưu cookie/localStorage/session** để không phải đăng nhập lại.
  - Chỉ định **cổng debug** (`--remote-debugging-port`) để có thể kết nối lại nếu cần.
  - Trên Linux/server: `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu` (headless), v.v.

### 2.2 Code mẫu (ý tưởng)

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

chrome_options = Options()
# QUAN TRỌNG: dùng 1 thư mục cố định để Chrome lưu profile (cookie, session)
chrome_options.add_argument("--user-data-dir=/path/to/chrome_user_data")
chrome_options.add_argument("--remote-debugging-port=9222")
chrome_options.add_argument("--window-size=1920,1080")

# Headless (server không GUI)
# chrome_options.add_argument("--headless=new")
# chrome_options.add_argument("--disable-gpu")

# Linux thường cần
# chrome_options.add_argument("--no-sandbox")
# chrome_options.add_argument("--disable-dev-shm-usage")

# Binary Chrome (nếu không nằm trong PATH)
# chrome_options.binary_location = "/usr/bin/google-chrome"

service = Service(log_path="logs/chromedriver.log")
driver = webdriver.Chrome(service=service, options=chrome_options)

# Tránh timeout 120s mặc định dẫn tới tab crash
driver.set_page_load_timeout(300)
driver.set_script_timeout(300)
```

### 2.3 Lưu ý

- **Một lúc chỉ một process Chrome** dùng cùng `user-data-dir` (và cùng `remote-debugging-port`). Nếu mở hai process cùng profile sẽ conflict.
- Đóng driver: `driver.quit()` và có thể **kill các process Chrome** có cmdline chứa `user_data_dir` hoặc `debug_port` (dùng `psutil`) để dọn sạch.

---

## 3. Lưu phiên đăng nhập (không phải đăng nhập lại)

### 3.1 Cơ chế

- Chrome lưu **cookies, localStorage, sessionStorage** trong thư mục **user-data-dir** (profile).
- Khi mở lại với cùng `--user-data-dir=...`, trang web (vd. Zalo) đọc lại cookie → **vẫn coi là đã đăng nhập** (trừ khi hết hạn phiên hoặc bị logout).
- **Không** dùng cookie export/import trong code; chỉ cần **dùng đúng một thư mục profile** cho môi trường chạy bot.

### 3.2 Thực hành

- Cấu hình một biến (vd. `.env`): `CHROME_USER_DATA_DIR=./chrome_user_data` (hoặc đường dẫn tuyệt đối).
- Lần đầu chạy: mở Zalo → đăng nhập (QR hoặc cách khác) → thoát bình thường (hoặc để script đóng driver). Lần sau chạy lại với cùng `user-data-dir` → thường vẫn đăng nhập.
- Trên server headless: lần đầu có thể cần chạy **không headless** (hoặc dùng QR gửi Telegram) để đăng nhập một lần, sau đó profile đã có session.

---

## 4. Đăng nhập (Zalo Web)

### 4.1 Trang đích

- URL: `https://chat.zalo.me/`
- **Đã đăng nhập:** có ô tìm kiếm (vd. `#contact-search-input`).
- **Chưa đăng nhập:** có khối QR (vd. `.qrcode img`).

### 4.2 Kiểm tra trạng thái đăng nhập

```python
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Đã đăng nhập: có ô search
search = WebDriverWait(driver, 5).until(
    EC.presence_of_element_located((By.ID, "contact-search-input"))
)
# → return True

# Chưa đăng nhập: có QR
qr = WebDriverWait(driver, 3).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, ".qrcode img"))
)
# → return False
```

- Nếu không thấy ô search cũng không thấy QR trong thời gian chờ → coi là “không xác định” (trang lỗi / đang load).

### 4.3 Đăng nhập bằng QR (từ xa)

- Tìm phần tử QR: `.qrcode img`.
- Chụp ảnh: `qr_element.screenshot(path)` hoặc `driver.save_screenshot(path)`.
- Gửi ảnh qua Telegram (Bot API) để user quét trên điện thoại.
- Vòng lặp: mỗi vài giây kiểm tra lại xem đã có `#contact-search-input` chưa; nếu QR hết hạn thì tìm nút làm mới (vd. `.qrcode-expired .btn`) hoặc `driver.refresh()` rồi chụp QR mới và gửi lại.
- Timeout tổng (vd. 300s hoặc 90s khi “recovery”) để tránh chờ vô hạn.

### 4.4 Làm mới QR khi hết hạn

- Kiểm tra có class/block “QR hết hạn”: vd. `.qrcode-expired`.
- Click nút làm mới: vd. `.qrcode-expired .btn`, hoặc `driver.refresh()` rồi đợi trang load và chụp QR mới.

---

## 5. Điều hướng: tìm và vào nhóm (conversation)

### 5.1 Tìm nhóm theo tên

- Dùng ô tìm kiếm: `#contact-search-input` (clear, send_keys tên nhóm).
- Đợi vài giây để kết quả render.
- Danh sách kết quả: các phần tử hội thoại (vd. `.conv-item`). Duyệt từng item, lấy `item.text` (hoặc text con), **chuẩn hóa chữ thường** rồi so khớp với tên nhóm (chứa chuỗi hoặc chứa tất cả từ).

### 5.2 Click vào nhóm

- Scroll vào view: `driver.execute_script("arguments[0].scrollIntoView(true);", item)`.
- Click bằng JS để tránh bị che: `driver.execute_script("arguments[0].click();", item)`.
- Đợi vào màn hình chat: vd. xuất hiện `.header-title` (tiêu đề nhóm) trong vài giây.

### 5.3 Xác nhận đúng nhóm

- Chỉ coi là “đã vào nhóm” khi có element đặc trưng của màn chat (vd. `.header-title`). Tránh đọc tin nhắn khi vẫn đang ở màn search hoặc nhóm khác.

---

## 6. Crawl dữ liệu (tin nhắn)

### 6.1 Xác định danh sách tin nhắn trên DOM

- Mỗi tin nhắn thường là một block (vd. `.chat-item`).  
  `items = driver.find_elements(By.CSS_SELECTOR, ".chat-item")`
- Có thể giới hạn số lượng (vd. 50 tin gần nhất) để tránh xử lý quá nhiều: `items = items[-50:]`.

### 6.2 Trích xuất từng tin (sender, nội dung, thời gian)

- **Người gửi:**  
  - Tin của mình: class chứa `me` hoặc `message-wrapper--me`.  
  - Tin người khác: vd. `.message-sender-name-content .truncate` hoặc `.message-sender-name-bubble .truncate` (textContent).  
  - Tin nhắn liên tiếp (cùng người): class có `--s2` → dùng lại “người gửi” của tin trước.
- **Nội dung chữ:**  
  - Container: `[data-component='message-content-view']` → bên trong `[data-component='text-container']`.  
  - Đoạn chữ / mention / SĐT: `span.text, a.mention-name, a.text-is-phone-number` (ghép theo thứ tự).  
  - Có thể dùng `execute_script` với `querySelector` + `textContent`/`innerText` để lấy chuỗi an toàn hơn khi DOM phức tạp.
- **Thời gian:**  
  - Vd. `.card-send-time__sendTime` hoặc `.bubble-message-time`. Tin liên tiếp có thể không có time riêng → dùng time tin trước.
- **Trích dẫn (reply):** vd. `.message-quote-fragment__container`, `.quote-name`, `.message-quote-fragment__description`.
- **Thu hồi:** kiểm tra có class/block “undo” hoặc “đã thu hồi” → bỏ qua hoặc ghi nhận “[Đã thu hồi]”.

### 6.3 Định dạng một dòng tin (để lưu / log)

- Ví dụ: `*[dd/mm/yyyy hh:mm:ss] TênNgườiGửi: Nội dung tin|||Trích dẫn|||[Ảnh][Voice]`
- Dùng một chuỗi “signature” (vd. nội dung đã chuẩn hóa + thời gian + sender) để **loại trùng** (set hoặc list kiểm tra đã xử lý).

### 6.4 Cuộn để tải thêm tin

- Khung chat thường nằm trong container (vd. `.chat-container` hoặc `.conversation-list`).  
  `driver.execute_script("var c = document.querySelector('.chat-container'); if(c) c.scrollTop = c.scrollHeight;")`  
  để cuộn xuống cuối (tin cũ). Có thể cuộn lên đầu (scrollTop = 0) để kích hoạt load tin mới (tùy SPA).
- Sau khi cuộn, đợi 1–2 giây rồi lấy lại danh sách `.chat-item`.

### 6.5 Tránh đọc nhầm nhóm

- Mỗi lần bắt đầu bước crawl (vd. mỗi “nhịp”): kiểm tra đang ở đúng nhóm (vd. có `.header-title` và/hoặc so sánh tên nhóm). Chỉ khi “in_group” = True mới `find_elements(".chat-item")` và xử lý.

---

## 7. Lưu dữ liệu

### 7.1 Autosave (định kỳ)

- Mỗi khi có tin mới: append vào file (vd. docx) hoặc buffer. Định kỳ (vd. 30s) hoặc khi số tin mới > ngưỡng: ghi ra file “autosave” (tên có thể kèm session, nhóm, máy).
- File autosave: dùng **copy-read-append-write** hoặc mở docx hiện có, thêm paragraph, save (có lock nếu đa luồng).

### 7.2 File cuối (chốt phiên)

- Khi đổi phiên (vd. đổi ngày/giờ) hoặc khi dừng: lưu toàn bộ tin đã crawl thành file chính theo naming chuẩn hiện tại. Với canonical repo hiện nay:
  - autosave: `autosave_{session_id}_{hostname}_{group_slug}.docx`
  - final raw: `final_{session_id}_{hostname}_{group_slug}_{message_count}mess.docx`
  - final formatted: `Lich_{session_id}_{hostname}_{group_slug}_{message_count}mess_crawl.docx`
- Có thể tạo file cuối từ autosave hoặc từ in-memory list.
- Source-of-truth cho artifact naming/path hiện tại: `FILE_LOCATION_GUIDE.md` + helper builders trong `src/utils/config.py` và `src/utils/artifact_paths.py`.

### 7.3 Định dạng docx

- Dùng `python-docx`: Document, add_heading, add_paragraph. Mỗi tin một paragraph (hoặc một dòng). Có thể chuẩn hóa (thay ký tự đặc biệt, format ngày giờ) trước khi ghi.

### 7.4 Nhiều nhóm

- Mỗi nhóm: thư mục riêng (vd. `data/slug_nhom_1/`, `data/slug_nhom_2/`) và file autosave/final riêng, tránh trộn dữ liệu.

---

## 8. Xử lý lỗi và phục hồi

### 8.1 Tab / browser crash

- Selenium ném exception (vd. “tab crashed”, “target window already closed”). Bắt ở nơi gọi driver (navigation, crawl_step, main loop).
- Khi phát hiện “tab crashed” / “read timed out” / “connectionpool”:
  - **Không** retry ngay với cùng driver (đã chết). Gọi **restart driver**: `driver.quit()`, tạo lại `webdriver.Chrome(...)` với cùng `user-data-dir`, set lại timeout.
  - **Cập nhật reference** driver ở mọi nơi đang giữ (navigator, auth, crawler, message_processor) để lần sau dùng driver mới.
  - **Khôi phục phiên:** `driver.get("https://chat.zalo.me")`, đợi `document.readyState == "complete"`, có thể sleep thêm vài giây cho SPA render, rồi kiểm tra đăng nhập lại (retry vài lần). Nếu chưa đăng nhập thì gọi wait_for_login với timeout ngắn (vd. 90s).

### 8.2 Timeout

- Tăng `set_page_load_timeout` và `set_script_timeout` (vd. 300s) để giảm “Read timed out” 120s mặc định có thể dẫn tới tab crash.
- Khi gọi `wait_for_login` sau recovery, dùng timeout ngắn (vd. 90s) để không chặn lâu; nếu fail thì coi recovery thất bại và có thể retry ở vòng lặp ngoài.

### 8.3 Log lỗi chi tiết (error log)

- Mỗi exception: ghi vào file riêng (vd. `data/logs/errors/error_YYYY-MM-DD.log`) với **full traceback** và **context** (phase, group_name, current_url, page_title nếu lấy được).
- Khi exception là **tab/browser crash**: thêm block **CRASH DIAGNOSTICS**: đọc ~80 dòng cuối `chromedriver.log` và thông tin bộ nhớ (psutil: total/available, process RSS) để sau này suy lý nguyên nhân (OOM, GPU, v.v.).

### 8.4 Decorator retry

- Các hàm gọi driver (find_and_access_group, check_login_status, scroll_for_messages, …) có thể được bọc bởi decorator: khi gặp lỗi “webdriver” (timeout, stale element) thì retry vài lần. Riêng lỗi “tab crashed”/“connection” thì **không** retry trong decorator mà **re-raise** để main loop xử lý restart + recovery và cập nhật refs.

---

## 9. Cấu hình và công cụ

### 9.1 Biến môi trường (.env)

- Chrome: `CHROME_USER_DATA_DIR`, `CHROME_DEBUG_PORT`, `HEADLESS`, `CHROME_BINARY`, `CHROME_WINDOW_WIDTH`, `CHROME_WINDOW_HEIGHT`.
- Timeout driver: `DRIVER_PAGE_LOAD_TIMEOUT`, `DRIVER_SCRIPT_TIMEOUT`.
- Ứng dụng: `DATA_FOLDER`, `LOGS_FOLDER`, `GROUP_NAMES` (hoặc `DEFAULT_GROUP_NAME`), `GROUP_SWITCH_MIN_SEC`, `GROUP_SWITCH_MAX_SEC`, `AUTOSAVE_INTERVAL`, `LOGIN_TIMEOUT`, `MAX_MESSAGES`.
- Telegram: `TELEGRAM_TOKEN`, `ADMIN_CHAT_ID`, `ALERT_CHAT_ID`.

### 9.2 Capture cấu trúc trang (cho dự án mới)

- Chạy một lần (vd. `python main.py --capture-structure`): mở Zalo, đăng nhập nếu cần, vào một nhóm, gọi hàm “capture structure”.
- Hàm này: với driver hiện tại, kiểm tra từng selector đã biết (ô search, QR, conv-item, header-title, chat-item, bubble-message, message-content-view, …), ghi số lượng và mẫu thuộc tính (tag, id, class, text preview); có thể thu thập danh sách class có trên trang; ghi ra file .md và .json. Dùng khi triển khai dự án mới trên web khác: thay URL và danh sách selector tương ứng.

---

## 10. Selectors tham chiếu (Zalo Web)

| Mục đích | Selector |
|----------|----------|
| Ô tìm kiếm (đã đăng nhập) | `#contact-search-input` |
| QR đăng nhập | `.qrcode img` |
| QR hết hạn / nút làm mới | `.qrcode-expired`, `.qrcode-expired .btn` |
| Một item trong danh sách hội thoại | `.conv-item` |
| Tiêu đề nhóm (trong chat) | `.header-title` |
| Một tin nhắn trong khung chat | `.chat-item` |
| Khung chứa tin nhắn (cuộn) | `.chat-container`, `.conversation-list` |
| Bubble tin nhắn | `[data-component='bubble-message']` |
| Tên người gửi | `.message-sender-name-content .truncate`, `.message-sender-name-bubble .truncate` |
| Nội dung tin | `[data-component='message-content-view']`, `[data-component='text-container']`, `span.text, a.mention-name, a.text-is-phone-number` |
| Thời gian | `.card-send-time__sendTime`, `.bubble-message-time` |
| Trích dẫn | `.message-quote-fragment__container`, `.quote-name`, `.message-quote-fragment__description` |

- Trang khác (web app khác): dùng DevTools hoặc “capture structure” tương tự để lập bảng selector tương ứng.

---

## 11. Luồng chạy nhiều nhóm (multi-group)

- Một driver, một lần đăng nhập. Danh sách nhóm: `GROUP_NAMES`.
- Vòng lặp: chọn nhóm tiếp theo (round-robin), gọi `find_and_access_group(group_name)`, gọi `crawl_step()` của crawler tương ứng với nhóm đó (mỗi nhóm một instance MessageCrawler với `data_folder` riêng), sleep random (vd. 3–7s), lặp lại.
- Khi `find_and_access_group` hoặc `crawl_step` ném “tab crashed”/timeout: gọi recovery (restart driver, cập nhật refs, recover_session, check_login, wait_for_login 90s nếu cần), rồi tiếp tục vòng lặp. Giới hạn số lần recovery thất bại liên tiếp (vd. 3) để tránh loop.

---

## 12. Checklist triển khai dự án mới tương tự

1. **Chrome + profile**
   - Cài Chrome/Chromium và ChromeDriver (hoặc dùng Selenium 4 managed driver).
   - Chọn một `user-data-dir` cố định; khởi tạo driver với `--user-data-dir` và `--remote-debugging-port`; set `page_load_timeout` và `script_timeout`.

2. **Trang đích và đăng nhập**
   - Xác định URL và cách biết “đã đăng nhập” (selector: ô search, menu user, …) và “chưa đăng nhập” (form login, QR, …).
   - Nếu có QR: chụp element hoặc fullscreen, gửi Telegram (hoặc lưu file), vòng lặp đợi xuất hiện selector “đã đăng nhập”.

3. **Điều hướng tới “room” cần crawl**
   - Tìm ô search hoặc menu, nhập tên room/nhóm, đợi danh sách, match tên (chuẩn hóa, chứa từ), click bằng JS, đợi element đặc trưng của room (header, title).

4. **Crawl nội dung**
   - Xác định selector “một item” (vd. tin nhắn, bài viết). `find_elements`, giới hạn số lượng. Với mỗi item: trích sender, nội dung, thời gian (và trích dẫn nếu có) bằng CSS/JS, tạo chuỗi signature để loại trùng.

5. **Lưu dữ liệu**
   - Autosave (append theo tin hoặc theo thời gian), file cuối khi đổi phiên/dừng; mỗi room/nhóm một thư mục hoặc prefix file.

6. **Lỗi và recovery**
   - Bắt exception “tab crashed”/timeout; restart driver, cập nhật refs, mở lại URL, kiểm tra đăng nhập (retry + timeout ngắn). Ghi error log kèm context và (khi crash) chromedriver tail + memory.

7. **Cấu hình**
   - Đưa đường dẫn, timeout, danh sách room, interval vào config/env. Có thể thêm chế độ “capture structure” để dump selectors cho trang mới.

---

Tài liệu này mô tả đúng các kỹ thuật trong project Zalo Web Crawler hiện tại; khi triển khai dự án mới (web khác), thay URL, selectors và logic nghiệp vụ (format tin, từ khóa, …), giữ nguyên ý tưởng: profile Chrome, kiểm tra đăng nhập, điều hướng theo tên, crawl DOM, autosave + file cuối, xử lý crash và recovery.
