# README-HANDOFF-MINIMAL

## Mục tiêu
Gói này dùng để mang `crawlbot_portable_scheduler_lab` sang **máy Ubuntu khác** và chạy nhanh với mức chuẩn tối thiểu.

## 1) Yêu cầu hệ thống
### Bắt buộc
- Ubuntu/Debian
- `python3`
- `python3-venv`
- `git` (nếu clone bằng git)
- Chrome/Chromium

### Bắt buộc nếu chạy non-headless
- `python3-tk`

> Vì `Crawlbot Control` mini-window dùng `tkinter`.
> Nếu chạy `HEADLESS=true` thì không cần `python3-tk`.

## 2) Cài dependency hệ thống nhanh
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-tk chromium-browser
```

Nếu máy dùng Google Chrome riêng thì thay `chromium-browser` bằng gói Chrome phù hợp.

## 3) Chuẩn bị project
```bash
cd ~/crawlbot_portable_scheduler_lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4) Chuẩn bị config
Dùng file mẫu:
```bash
cp .env.example .env
```

Các biến cần kiểm tra tối thiểu:
- `HEADLESS=false` nếu muốn thấy Chrome + dùng Crawlbot Control
- `HEADLESS=true` nếu muốn chạy headless
- `CHROME_USER_DATA_DIR=./chrome_user_data`
- `CHROME_DEBUG_PORT=9222`
- `GROUP_NAMES` hoặc `DEFAULT_GROUP_NAME`
- `TELEGRAM_TOKEN`
- `ADMIN_CHAT_ID`
- `ALERT_CHAT_ID`

## 5) Login Zalo
- Profile đăng nhập không nên giả định luôn đi kèm máy mới.
- Nếu chưa có session trong `chrome_user_data`, chạy non-headless lần đầu để đăng nhập/quét QR.

## 6) Chạy bot
### Non-headless
```bash
source .venv/bin/activate
python main.py
```

Kỳ vọng:
- mở Chrome thật
- hiện `Crawlbot Control`
- nút `Dừng an toàn & đóng Chrome` hoạt động

### Headless
```bash
HEADLESS=true ./.venv/bin/python main.py
```

## 7) Hành vi quan trọng đã có
- **Preflight cleanup**: trước khi launch driver, bot sẽ đóng các Chrome/Chromium xung đột trực tiếp với lane crawler (cùng `user-data-dir` hoặc `remote-debugging-port`).
- **Crawlbot Control**: ở non-headless mode có mini-window always-on-top để dừng an toàn.
- **Graceful shutdown**: bấm nút stop sẽ đi theo luồng shutdown sạch, không kill cứng.
- **Profile cache cleanup an toàn**: có script chỉ dọn cache/rác trong `chrome_user_data` mà không đụng `Cookies`, `Local Storage`, `IndexedDB`.
- **Maintenance 1-lệnh**: có thể dùng script maintenance để dừng bot an toàn -> cleanup cache -> chạy lại bot.

## 8) Maintenance / cleanup profile
### Cleanup cache-only an toàn
```bash
./scripts/cleanup-chrome-profile-cache.sh ./chrome_user_data ./backups
```

### Maintenance 1-lệnh: stop -> cleanup -> restart
```bash
./scripts/maintenance-restart-with-profile-cleanup.sh
```

Mặc định script sẽ:
1. gửi `SIGTERM` cho `python main.py`
2. chờ bot dừng sạch
3. dọn cache-only trong `chrome_user_data`
4. chạy lại bot bằng `.venv/bin/python main.py`
5. ghi log vào `logs/maintenance-restart.log`

## 9) Log nên xem nhanh
- `logs/chromedriver.log`
- `logs/maintenance-restart.log`
- log console/stdout của `python main.py`
- `data/logs/errors/`
- `data/logs/fail-artifacts/` (nếu có)

## 10) PASS tối thiểu trên máy mới
- boot được
- Telegram startup OK
- mở được Zalo Web
- vào đúng room
- crawl được tin
- non-headless thì thấy `Crawlbot Control`
- bấm nút stop thì đóng sạch
- cleanup cache-only xong vẫn giữ login Zalo

## 11) Nếu lỗi
### Thiếu UI control
- lỗi `No module named 'tkinter'`
- cách xử lý: cài `python3-tk`

### Chrome không lên
- kiểm tra Chrome/Chromium có thật trên máy
- kiểm tra `CHROME_BINARY` nếu cần chỉ rõ path

### Chưa đăng nhập Zalo
- chạy `HEADLESS=false`
- đăng nhập/quét QR trước

### Telegram lỗi
- kiểm tra `TELEGRAM_TOKEN`, `ADMIN_CHAT_ID`, `ALERT_CHAT_ID`

## 12) File nên mang theo
- source code project
- `.env.example`
- `.env.2room.recommended` / `.env.3room.recommended` nếu cần
- tài liệu này: `README-HANDOFF-MINIMAL.md`
- `scripts/cleanup-chrome-profile-cache.sh`
- `scripts/maintenance-restart-with-profile-cleanup.sh`

## 13) Khuyến nghị handoff
Nếu giao cho user kỹ thuật vừa phải:
- gửi **source package sạch**
- kèm `.env.example`
- kèm file này
- không nên gửi cả `chrome_user_data`, `logs`, `runs`, `.venv`, `__pycache__`
