# Crawlbot headless for Ubuntu server

Tên gói: `crawlbot_portable_scheduler_headless_server_v1`

## Mục tiêu
Bản này tách riêng lane chạy **headless trên Ubuntu server** từ code stable hiện tại.
Nó giữ logic crawl/scheduler/navigation đã ổn định hơn trên FarmBot, nhưng launcher và config được tối ưu theo hướng server/headless.

## Lưu ý quan trọng
- Zalo Web trong headless mode có thể **kém ổn định hơn** headed/GUI ở một số case UI hoặc anti-bot.
- Vì vậy bản này nên được coi là **lane riêng để soak test**, không assume chắc chắn ổn ngang GUI lane.
- Dùng khi anh cần:
  - chạy trên Ubuntu server không có desktop
  - đóng gói gọn để mang sang máy khác
  - test lane headless độc lập

## 1) Chuẩn bị máy Ubuntu server
```bash
sudo apt update
sudo apt install -y python3 python3-venv unzip wget curl ca-certificates fonts-liberation libnss3 libatk-bridge2.0-0 libgtk-3-0 libxss1 libasound2t64 libgbm1 libu2f-udev xdg-utils
```

Cài Google Chrome (nếu chưa có):
```bash
wget -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y /tmp/google-chrome.deb
```

Kiểm tra:
```bash
which google-chrome || which google-chrome-stable || which chromium || which chromium-browser
```

## 2) Chuẩn bị project
```bash
unzip crawlbot_portable_scheduler_headless_server_v1.zip
cd crawlbot_portable_scheduler_headless_server_v1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Chuẩn bị config
```bash
cp .env.headless.example .env
nano .env
```

Điền tối thiểu:
- `TELEGRAM_TOKEN`
- `ADMIN_CHAT_ID`
- `ALERT_CHAT_ID`
- `GROUP_NAMES`
- nếu Chrome không nằm đúng PATH thì thêm `CHROME_BINARY=/usr/bin/google-chrome-stable`

## 4) Chạy headless
Foreground:
```bash
./run-headless-server.sh
```

Chạy nền:
```bash
nohup ./run-headless-server.sh > logs/headless-run.log 2>&1 &
```

## 5) Log cần xem nhanh
- `logs/headless-run.log`
- `logs/chromedriver.log`
- `data/logs/errors/`
- `data/logs/fail-artifacts/`

## 6) Dấu hiệu pass ban đầu
- process boot được
- Telegram startup OK
- vào được room
- thấy log:
  - `verify_mode=strong` hoặc `verify_mode=usable`
  - `ROOM_SWITCH_TRACKER`
  - `fairness scheduler:`
- boundary/session save được docx và gửi Telegram OK

## 7) Dấu hiệu cần soi kỹ
- `group-opened-unverified`
- `navigation-stall`
- `HTTPConnectionPool(`
- `Read timed out`
- `tab crashed`

## 8) Khuyến nghị rollout
- test 1 room trước
- sau đó 2 room
- nếu ổn mới soak dài hơn
- nếu headless rung hơn GUI, giữ lane này cho server-only cases thay vì thay thế bản GUI stable
