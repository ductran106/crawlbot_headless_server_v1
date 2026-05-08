# SYSTEMD-RUNBOOK.md — crawlbot-headless-dev trên farmbot

Mục tiêu: mở file này ra là biết service nào đang chạy, kiểm tra thế nào, restart ra sao, và rollback về chạy tay nếu cần.

## 1) Service chuẩn hiện tại
- Service name: `crawlbot-headless-dev.service`
- Host/user: `farm4bot@farmbot`
- App path: `/home/farm4bot/work/crawlbot_headless_server_v1_dev`
- systemd unit path: `~/.config/systemd/user/crawlbot-headless-dev.service`

Entry hiện tại:
- `WorkingDirectory=/home/farm4bot/work/crawlbot_headless_server_v1_dev`
- `ExecStart=/bin/bash /home/farm4bot/work/crawlbot_headless_server_v1_dev/run-headless-server.sh`

Thiết kế vận hành:
- dùng **user systemd service**
- `Restart=always`
- `RestartSec=5`
- `WantedBy=default.target`
- user đã bật `linger`, nên service có thể tự lên sau reboot mà không cần đăng nhập GUI thủ công

---

## 2) Lệnh nhanh hằng ngày

### Xem trạng thái
```bash
systemctl --user status crawlbot-headless-dev.service
```

### Xem log live
```bash
journalctl --user -u crawlbot-headless-dev.service -f
```

### Restart service
```bash
systemctl --user restart crawlbot-headless-dev.service
```

### Stop service
```bash
systemctl --user stop crawlbot-headless-dev.service
```

### Start lại service
```bash
systemctl --user start crawlbot-headless-dev.service
```

### Xem có auto-start không
```bash
systemctl --user is-enabled crawlbot-headless-dev.service
```

### Xem có đang chạy không
```bash
systemctl --user is-active crawlbot-headless-dev.service
```

---

## 3) Kiểm tra sau reboot / sau sự cố

### Check 1 — service state
```bash
systemctl --user is-active crawlbot-headless-dev.service
```
Kỳ vọng:
- `active`

### Check 2 — journal gần nhất
```bash
journalctl --user -u crawlbot-headless-dev.service -n 80 --no-pager
```
Kỳ vọng thường thấy:
- `Kết nối Telegram thành công`
- `Login state -> already-logged-in`
- `Chạy chế độ multi-group: [HEY KLUB, RETURN Tái định cư]`
- `verify_mode=strong`
- `ROOM_SWITCH_TRACKER`

### Check 3 — process thật
```bash
pgrep -af python main.py
