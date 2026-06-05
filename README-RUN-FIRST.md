# README-RUN-FIRST.md

Mở thư mục này và chạy theo thứ tự dưới đây. Đừng đọc cả đống file khác trước.

## Thư mục chuẩn của crawlbot
```bash
cd /home/duc/ai-workspace/repos/crawlbot_OK
```

## Mục tiêu file này
Giúp anh **run thử nhanh** dự án crawlbot trên đúng thư mục chính, không phải đoán entrypoint.

---

## 1) Cách chạy nên ưu tiên

### Nếu muốn chạy như user bình thường
```bash
bash run.sh
```

Đây là đường chạy nên ưu tiên từ bây giờ vì script này:
- kiểm tra có `.venv` chưa
- kiểm tra có `.env` chưa
- tạo `data`, `logs`, `chrome_user_data`
- set `ENV_FILE=.env`
- rồi chạy `python main.py`

### Nếu muốn chạy dev/local thử riêng
```bash
bash dev-run.sh
```

Script này giữ lại cho lane debug/dev:
- kiểm tra có `.venv` chưa
- kiểm tra có `.env.dev` chưa
- tạo `dev-data`, `dev-logs`, `dev-chrome-profile`
- set `ENV_FILE=.env.dev`
- rồi chạy `python main.py`

### Nếu muốn gọi trực tiếp
```bash
python3 main.py
```
Chỉ dùng cách này khi anh **biết chắc** môi trường Python hiện tại đã đúng. Nếu không, ưu tiên `dev-run.sh` hoặc `run.sh`.

---

## 2) Chạy nhanh nhất từ đầu

### Bước 1 — vào thư mục
```bash
cd /home/duc/ai-workspace/repos/crawlbot_OK
```

### Bước 2 — nếu chưa có virtualenv
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### Nếu muốn chạy test/dev luôn
```bash
pip install -r requirements-dev.txt
```

### Bước 3 — chuẩn bị env normal mode
```bash
cp .env.example .env
```

Sau đó sửa `.env` nếu cần.

- Nếu chưa dùng Telegram thật, cứ để các biến Telegram trống.
- Chỉ điền `TELEGRAM_TOKEN` / `ADMIN_CHAT_ID` / `ALERT_CHAT_ID` khi đã có config thật.

### Bước 4 — chạy thử như user bình thường
```bash
bash run.sh
```

### Nếu muốn lane dev/debug riêng
```bash
cp .env.dev.example .env.dev
bash dev-run.sh
```

---

## 3) Nếu script báo lỗi thì hiểu thế nào

### Lỗi thiếu `.venv`
Nó sẽ báo kiểu:
- `Missing .venv`

Cách xử lý:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### Lỗi thiếu `.env`
Nó sẽ báo kiểu:
- `Missing .env. Start from .env.example`

Cách xử lý:
```bash
cp .env.example .env
```

### Lỗi thiếu `.env.dev`
Nó sẽ báo kiểu:
- `Missing .env.dev. Start from .env.dev.example`

Cách xử lý:
```bash
cp .env.dev.example .env.dev
```

---

## 4) File nào là quan trọng nhất

### Entry points
- `run.sh` → entrypoint normal mode / user mode
- `dev-run.sh` → lane debug/dev
- `main.py` → entrypoint chính

### Source code chính
- `src/`

### Test
- `tests/`

### Debug nhanh observability
- `./scripts/event-timeline.sh logs/*.log`
- Filter nhanh: `./scripts/event-timeline.sh --event room_switch_tracker --tail 20`
- Theo room + mốc thời gian: `./scripts/event-timeline.sh --group "RETURN ROOM LỊCH" --since 2026-03-19T04:45:00 logs/*.log`
- Chỉ xem event xấu/fail: `./scripts/event-timeline.sh --latest --fail-only`
- Xem file log mới nhất: `./scripts/event-timeline.sh --latest --tail 30`
- Xem đẹp cho người: `./scripts/event-timeline.sh --latest --pretty`
- Xem summary nhanh: `./scripts/event-timeline.sh --latest --summary --pretty`

### Tài liệu phụ
- `README.md`
- `FILE_LOCATION_GUIDE.md`
- `CONFIG_REFERENCE.md`
- `ARCHITECTURE.md`

---

## 5) Em khuyên anh dùng lệnh nào trước

Nếu mục tiêu là: **“anh muốn chạy như user bình thường”**
thì dùng đúng lệnh này:

```bash
cd /home/duc/ai-workspace/repos/crawlbot_OK && cp .env.example .env && bash run.sh
```

---

## 6) Ghi chú thực dụng

- `run.sh` là entrypoint normal mode nên ưu tiên khi chạy như user bình thường
- `dev-run.sh` chỉ nên dùng khi debug/dev lane riêng
- đừng nhảy sang thư mục bridge/runner v1.1 nếu mục tiêu là chạy **project crawlbot**
- nếu cần debug sâu hơn sau khi chạy, lúc đó mới mở tiếp:
  - `src/`
  - `tests/`
  - `README.md`

---

## 7) One-liner

```bash
cd /home/duc/ai-workspace/repos/crawlbot_OK && cp .env.example .env && bash run.sh
```
