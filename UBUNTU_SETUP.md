# Hướng dẫn chạy Zalo Crawler trên Ubuntu Server 22.04.5

## 📋 Yêu cầu hệ thống

- Ubuntu Server 22.04.5 (hoặc tương đương)
- Python 3.8+
- Quyền sudo để cài đặt packages
- Kết nối Internet

## 🚀 Cài đặt nhanh (Tự động)

```bash
# 1. Clone/copy project vào server
cd ~/crawlbot  # hoặc thư mục bạn muốn

# 2. Chạy script cài đặt tự động
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

Script sẽ tự động:
- ✅ Cài đặt Python3 và venv
- ✅ Cài đặt Google Chrome
- ✅ Cài đặt tất cả thư viện hệ thống cần thiết
- ✅ Tạo virtual environment
- ✅ Cài đặt Python packages từ requirements.txt
- ✅ Kiểm tra Chrome headless hoạt động
- ✅ Tạo các thư mục cần thiết
- ✅ Tạo file .env.example

## ⚙️ Cấu hình thủ công

### 1. Tạo file .env

Sao chép từ `.env.example` và điền thông tin:

```bash
cp .env.example .env
nano .env  # hoặc dùng editor khác
```

**Các biến quan trọng cần điền:**

```env
# Telegram Bot (BẮT BUỘC)
TELEGRAM_TOKEN=your_telegram_bot_token
ADMIN_CHAT_ID=your_personal_chat_id
ALERT_CHAT_ID=your_group_chat_id

# Quan trọng: Bật headless cho server
HEADLESS=true

# Đường dẫn thư mục (có thể dùng đường dẫn tuyệt đối)
DATA_FOLDER=./data
CHROME_USER_DATA_DIR=./chrome_user_data
LOGS_FOLDER=./logs
```

### 2. Kiểm tra Chrome

Chạy lệnh sau để test Chrome headless:

```bash
google-chrome --headless --disable-gpu --no-sandbox --disable-dev-shm-usage --dump-dom https://www.google.com
```

Nếu không có lỗi → Chrome hoạt động tốt.

### 3. Kiểm tra quyền thư mục

Đảm bảo user hiện tại có quyền ghi vào các thư mục:

```bash
chmod -R 755 data logs chrome_user_data
```

## 🐛 Xử lý lỗi "Chrome instance exited"

Nếu gặp lỗi này, thử các bước sau:

### Bước 1: Kiểm tra log chi tiết

```bash
cat logs/chromedriver.log
```

Log sẽ cho biết lỗi cụ thể.

### Bước 2: Kiểm tra Chrome có chạy được không

```bash
# Test Chrome headless
google-chrome --headless --disable-gpu --no-sandbox --disable-dev-shm-usage --dump-dom https://www.google.com

# Kiểm tra version
google-chrome --version
```

### Bước 3: Kiểm tra thiếu dependencies

```bash
# Cài lại các thư viện cần thiết
sudo apt install -y \
  libnss3 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
  libcups2 libxss1 libxrandr2 libxdamage1 libxcomposite1 \
  libxext6 libxfixes3 libxi6 libxkbcommon0 libpangocairo-1.0-0 \
  libx11-6 libx11-xcb1 libxcb1 libgbm1 libgtk-3-0 \
  fonts-liberation ca-certificates fonts-noto-color-emoji libasound2
```

### Bước 4: Kiểm tra quyền thư mục user-data-dir

```bash
# Đảm bảo thư mục có quyền ghi
ls -la chrome_user_data
chmod -R 755 chrome_user_data
```

### Bước 5: Thử chạy Chrome với user khác (nếu cần)

Nếu chạy với user không phải root, đảm bảo:
- User có quyền truy cập `/dev/shm` (thường tự động)
- Không có process Chrome khác đang chạy với cùng user-data-dir

```bash
# Kiểm tra process Chrome đang chạy
ps aux | grep chrome

# Kill nếu cần
pkill -f chrome
```

### Bước 6: Kiểm tra Selenium và ChromeDriver

```bash
source .venv/bin/activate
python -c "from selenium import webdriver; print(webdriver.__version__)"
```

Selenium 4+ tự động quản lý ChromeDriver, nhưng nếu có vấn đề:

```bash
# Cài đặt webdriver-manager (nếu chưa có)
pip install webdriver-manager
```

## 📝 Chạy chương trình

### Chạy thủ công

```bash
cd ~/crawlbot
source .venv/bin/activate
python main.py
```

### Chạy trong background (tmux/screen)

```bash
# Cài tmux nếu chưa có
sudo apt install -y tmux

# Tạo session mới
tmux new -s zalo_crawler

# Trong tmux, chạy:
source .venv/bin/activate
python main.py

# Detach: Ctrl+B, sau đó nhấn D
# Attach lại: tmux attach -t zalo_crawler
```

### Chạy với systemd (Tự động khởi động)

Tạo file `/etc/systemd/system/zalo-crawler.service`:

```ini
[Unit]
Description=Zalo Crawler Bot
After=network.target

[Service]
Type=simple
User=duc
WorkingDirectory=/home/duc/crawlbot
Environment="PATH=/home/duc/crawlbot/.venv/bin"
ExecStart=/home/duc/crawlbot/.venv/bin/python /home/duc/crawlbot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Kích hoạt:

```bash
sudo systemctl daemon-reload
sudo systemctl enable zalo-crawler
sudo systemctl start zalo-crawler

# Xem log
sudo journalctl -u zalo-crawler -f
```

## 🔍 Kiểm tra hoạt động

### 1. Kiểm tra Telegram bot

Khi chạy lần đầu, bot sẽ:
- ✅ Gửi startup notification đến ADMIN_CHAT_ID
- ✅ Gửi alert-ready notification đến ALERT_CHAT_ID

> Wording của các notification core hiện đã được chuẩn hóa qua `src/notification/messages.py`. Nếu wording thay đổi theo code mới, lấy `messages.py` làm source-of-truth thay vì ví dụ cứng trong doc này.

Nếu không nhận được → kiểm tra:
- Token Telegram đúng chưa
- Bot đã được add vào group (nếu ALERT_CHAT_ID là group)
- Server có kết nối Internet không

### 2. Kiểm tra đăng nhập Zalo

Lần chạy đầu tiên:
- Bot sẽ mở Zalo Web
- Nếu chưa đăng nhập, bot sẽ **chụp QR code và gửi qua Telegram**
- Bạn quét QR trên điện thoại → đăng nhập thành công
- Session được lưu trong `chrome_user_data/`

Lần chạy sau:
- Nếu session còn hiệu lực → tự động đăng nhập
- Nếu hết hạn → gửi QR mới qua Telegram

### 3. Kiểm tra log

```bash
# Xem log ứng dụng
tail -f logs/*.log

# Xem log ChromeDriver (nếu có lỗi)
tail -f logs/chromedriver.log
```

## 📞 Hỗ trợ

Nếu vẫn gặp lỗi sau khi thử các bước trên:

1. Kiểm tra log chi tiết: `logs/chromedriver.log` và `logs/*.log`
2. Chạy test Chrome headless: `google-chrome --headless --disable-gpu --no-sandbox --dump-dom https://www.google.com`
3. Kiểm tra version: `python --version`, `google-chrome --version`
4. Gửi thông tin lỗi kèm log để được hỗ trợ
