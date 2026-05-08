# Crawlbot Control v1 spec

## Mục tiêu
Thêm một lane dừng an toàn cho chế độ **non-headless** mà không thay đổi behavior hiện tại của headless mode.

## Phạm vi v1
- Tên UI: **Crawlbot Control**
- Chỉ bật khi `HEADLESS=false`
- UI là **1 cửa sổ mini always-on-top**
- Có 1 nút chính: **Dừng an toàn & đóng Chrome**
- Nút này **không kill cứng**; nó chỉ kích hoạt graceful shutdown path hiện có

## Nguyên lý hoạt động
1. App khởi động bình thường.
2. Nếu `HEADLESS=false`, app mở thêm một mini control window độc lập.
3. Khi user bấm nút `Dừng an toàn & đóng Chrome`, UI gọi một hàm request shutdown tập trung.
4. Hàm này bật cờ shutdown dùng chung (`is_terminating() == True`).
5. Main loop / crawler loop đang có sẽ tự thoát ở checkpoint sẵn có.
6. `finally` / cleanup path hiện tại tiếp tục chạy để đóng WebDriver/Chrome sạch.

## Không làm ở v1
- Không chèn nút vào trong cửa sổ Chrome.
- Không theo dõi vị trí Chrome theo thời gian thực.
- Không thay đổi behavior của headless mode.
- Không thêm logic đoán user tự đóng Chrome bằng tay.

## Bổ sung preflight trước khi chạy
Trước khi launch Chrome/WebDriver, app sẽ chạy một bước preflight cleanup để đóng các tiến trình Chrome/Chromium có nguy cơ xung đột với lane crawler.

Rule v1 an toàn:
- ưu tiên dọn các tiến trình dùng cùng `user-data-dir`
- hoặc cùng `remote-debugging-port`
- tránh đóng tràn lan mọi cửa sổ Chrome không liên quan

## UI dùng gì
- Ưu tiên `tkinter` chuẩn của Python.
- Lý do:
  - có sẵn trên hầu hết môi trường desktop Python
  - đủ cho 1 mini-window đơn giản
  - không cần dependency ngoài
- Requirement triển khai:
  - non-headless mode cần `tkinter`
  - trên Ubuntu/Debian nên cài `python3-tk`

## File dự kiến sửa

### 1) `src/utils/signals.py`
Thêm API mức app để trigger graceful shutdown ngoài signal hệ thống:
- `request_graceful_shutdown(reason=None)`
- `get_shutdown_reason()`

Mục tiêu:
- button UI có thể dùng chung cùng shutdown flag hiện hữu
- không phải giả lập kill process

### 2) `src/ui/control_window.py` (mới)
Chứa mini control window:
- tạo `Tk()` trong thread riêng
- always-on-top
- nút `Dừng an toàn & đóng Chrome`
- bấm nút -> gọi `request_graceful_shutdown("crawlbot_control_button")`
- có hàm `start_control_window()` / `stop_control_window()`

### 3) `main.py`
- startup: nếu non-headless thì mở control window
- shutdown/finally: đóng control window nếu đang chạy
- không thay đổi luồng headless

### 4) `src/browser/driver.py`
- thêm preflight cleanup trước khi launch driver
- đóng các Chrome/Chromium xung đột trực tiếp với lane crawler

## Luồng nhận stop signal
- Nguồn phát stop signal v1:
  - signal hệ thống (`SIGINT`, `SIGTERM`) như cũ
  - button từ `Crawlbot Control`
- Điểm nhận stop signal:
  - `src/utils/signals.is_shutting_down`
- Điểm tiêu thụ stop signal:
  - `while not is_terminating()` ở main loop
  - `crawler.external_stop_flag = is_terminating`
  - các guard shutdown hiện có trong browser/crawler/navigation

## Hành vi UX v1
- Window nhỏ, nổi trên cùng, title: `Crawlbot Control`
- Có text trạng thái ngắn: `Crawler đang chạy` / `Đang dừng an toàn...`
- Nút stop sau khi bấm sẽ bị disable để tránh bấm lặp
- Đóng app chính thì control window cũng tự đóng

## Tiêu chí hoàn thành v1
- `HEADLESS=false`: xuất hiện mini control window
- bấm nút stop -> app đi vào graceful shutdown
- Chrome được đóng qua cleanup path hiện có
- `HEADLESS=true`: không hiện UI, behavior giữ nguyên
