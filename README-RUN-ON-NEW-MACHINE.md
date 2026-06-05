# README-RUN-ON-NEW-MACHINE

## Mục tiêu
Bản này để mang sang máy Ubuntu khác chạy soak test 24/7 vài ngày.

## 1) Chuẩn bị máy mới
- Cài `git`, `python3`, `python3-venv`
- Cài Google Chrome
- Đảm bảo máy có desktop/GUI hoặc môi trường chạy Chrome phù hợp

## 2) Chuẩn bị project
```bash
cd ~/crawlbot_OK_portable_20260321
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Nếu repo này đã có `.venv` riêng ở máy mới thì dùng `.venv/bin/python main.py`.

## 3) Chuẩn bị config/login
- Copy hoặc tạo lại file `.env` nếu project đang dùng
- Kiểm tra Telegram bot token / chat id
- Zalo login state không đi kèm bản portable này
- Chạy lần đầu sẽ cần đăng nhập lại Zalo nếu chưa có session

## 4) Chạy bot
```bash
cd ~/crawlbot_OK_portable_20260321
source .venv/bin/activate
python main.py
```

Chạy nền:
```bash
nohup ./.venv/bin/python main.py > logs/portable-run.log 2>&1 &
```

## 5) Log cần nhìn nhanh
- `logs/portable-run.log`
- `logs/chromedriver.log`
- `data/logs/fail-artifacts/`

## 6) PASS tối thiểu
- Bot boot được
- Telegram startup OK
- Vào được room
- Đến boundary phiên thì tạo:
  - `final_...docx`
  - `Lich_...docx`
- Có log `Đã gửi file Telegram thành công`

## 7) Nếu lỗi
Nhìn các pattern sau:
- `group-search-empty`
- `group-mismatch`
- `reconnect_verify_failed`
- `Lỗi khi lưu tài liệu`
- `Lỗi khi gửi file Telegram`
- `ModuleNotFoundError`

## 8) Mục tiêu soak test 2-3 ngày
- không crash process
- không mất rollover docx
- không mất Telegram send ở boundary
- ghi nhận lane navigation/reconnect có ổn định hay không
