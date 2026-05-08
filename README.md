# Crawlbot Headless Server v1

Crawler Zalo Web dùng Selenium để theo dõi/crawl tin nhắn nhóm, lưu DOCX và gửi thông báo/tài liệu qua Telegram.

Repo này là bản **dev sạch** của lane `crawlbot_portable_scheduler_headless_server_v1`, tách khỏi runtime copy trên farmbot để có thể quản lý bằng git và đẩy lên GitHub an toàn.

## Mục tiêu
- Chạy Crawlbot theo lane **headless trên Ubuntu server**
- Hỗ trợ 1 hoặc nhiều room bằng fairness scheduler
- Giữ tách biệt giữa **source code** và **runtime state** (`.env`, profile Chrome, data, logs)

## Runtime đã được kiểm thực trên farmbot
- Headless: `true`
- Room đang dùng gần nhất:
  - `HEY KLUB`
  - `RETURN Tái định cư`
- Runtime copy thực tế trên farmbot:
  - `/home/farm4bot/work/crawlbot_portable_scheduler_headless_server_v1`

## Cấu trúc chính
- `main.py` — entrypoint chính
- `src/` — source chính
- `run-headless-server.sh` — launcher headless chuẩn
- `run-crawlbot-with-heartbeat.sh` — launcher có heartbeat file
- `README-HEADLESS-UBUNTU-SERVER.md` — hướng dẫn bring-up Ubuntu server
- `ARCHITECTURE.md` / `TECHNIQUES.md` / `CONFIG_REFERENCE.md` — tài liệu kỹ thuật và config

## Cài đặt nhanh
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.headless.example .env
# sửa .env theo môi trường thật
```

## Chạy
Foreground:
```bash
./run-headless-server.sh
```

Background:
```bash
nohup ./run-headless-server.sh > /tmp/crawlbot-headless.out 2>&1 &
```

## Dừng an toàn
```bash
pkill -TERM -f 'python main.py'
```

## Xem log nhanh
```bash
tail -f /tmp/crawlbot-headless.out
```

Nếu dùng launcher ghi log nội bộ:
```bash
tail -f logs/headless-run.log
```

## Điều không được commit
- `.env`
- `.venv/`
- `chrome_user_data/`
- `data/`
- `logs/`
- file DOCX/DB/runtime artifacts

## Ghi chú repo
- Repo này được làm sạch từ một runtime handoff copy đã chạy thật.
- Không đưa secrets, session đăng nhập, DB, logs, hay crawl outputs lên git.
- Muốn xem hướng dẫn bring-up chi tiết, đọc `README-HEADLESS-UBUNTU-SERVER.md`.
