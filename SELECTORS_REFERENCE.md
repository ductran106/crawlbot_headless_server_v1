# Tham chiếu Selectors – Zalo Web (và gợi ý cho web mới)

Bảng selector dùng trong project, kèm **file sử dụng**, để khi chuyển sang web khác bạn biết thay ở đâu và có template để điền selector mới (sau khi chạy capture structure).

---

## 1. Trang đăng nhập / chung

| Mục đích | Selector | File sử dụng |
|----------|----------|----------------|
| Ô tìm kiếm (đã đăng nhập) | `#contact-search-input` | `navigation.py` (find_and_access_group), `login.py` (check_login_status, wait_for_login) |
| QR đăng nhập | `.qrcode img` | `login.py` (check_login_status, send_qr_to_telegram) |
| QR hết hạn | `.qrcode-expired` | `login.py` (is_qr_expired) |
| Nút làm mới QR | `.qrcode-expired .btn` | `login.py` (refresh_qr_code) |

---

## 2. Điều hướng – Tìm và vào nhóm

| Mục đích | Selector | File sử dụng |
|----------|----------|----------------|
| Một item trong danh sách kết quả tìm kiếm | `.conv-item` | `navigation.py` (find_and_access_group, reconnect_to_group) |
| Tiêu đề nhóm (xác nhận đã vào room) | `.header-title` | `navigation.py` (find_and_access_group) |

---

## 3. Khung chat – Danh sách tin nhắn

| Mục đích | Selector | File sử dụng |
|----------|----------|----------------|
| Một tin nhắn (item) | `.chat-item` | `message_crawler.py` (crawl_step, scroll_for_messages) |
| Khung cuộn tin nhắn | `.chat-container`, `.conversation-list` | `message_crawler.py` (scroll_for_messages – JS) |

---

## 4. Trích xuất nội dung từng tin (message_processor.py)

| Mục đích | Selector | Hàm / ghi chú |
|----------|----------|----------------|
| Bubble tin nhắn (lấy id) | `[data-component='bubble-message']` | get_sender_name |
| Tin của mình | class `me`, `message-wrapper--me` | get_sender_name |
| Tên người gửi (content) | `.message-sender-name-content .truncate` | get_sender_name |
| Tên người gửi (bubble) | `.message-sender-name-bubble .truncate` | get_sender_name |
| Tin nhắn liên tiếp cùng người | class `--s2` | get_sender_name, extract_timestamp |
| Nội dung tin | `[data-component='message-content-view']` | extract_message_content |
| Container chữ | `[data-component='text-container']` | extract_message_content |
| Đoạn chữ / mention / SĐT | `span.text, a.mention-name, a.text-is-phone-number` | extract_message_content |
| Fallback nội dung | `.overflow-hidden` | extract_message_content |
| Thời gian (card) | `.card-send-time__sendTime` | extract_timestamp |
| Thời gian (bubble) | `.bubble-message-time` | extract_timestamp |
| Trích dẫn | `.message-quote-fragment__container`, `.quote-name`, `.message-quote-fragment__description` | extract_quote |

---

## 5. Dùng cho dự án mới

1. **Capture cấu trúc trang mới:** Chạy `python main.py --capture-structure` (sau khi đã sửa URL và selector “đã đăng nhập” để vào được trang). File kết quả trong `data/logs/` (zalo_structure_*.md / .json) là bảng selector thực tế của trang đó.
2. **Thay selector:** Trong **navigation.py** thay ô search, `.conv-item`, `.header-title`. Trong **message_processor.py** thay toàn bộ selector sender/content/time/quote. Trong **message_crawler.py** thay selector danh sách item (vd. `.chat-item`).
3. **Cập nhật danh sách tham chiếu:** Nếu dùng `src/tools/zalo_structure_capture.py` cho trang mới, sửa biến `ZALO_SELECTORS_REF` trong file đó thành danh sách selector trang mới để lần sau capture vẫn đúng.

Chi tiết kỹ thuật crawl và format tin xem **TECHNIQUES.md**; bước tạo dự án mới xem **NEW_PROJECT_GUIDE.md**.
