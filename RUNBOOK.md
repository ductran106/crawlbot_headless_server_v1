# RUNBOOK.md — Farmbot runtime quick runbook

Mục tiêu: đủ ngắn để mở ra là chạy, xem log, dừng, và kiểm tra trạng thái lane headless trên farmbot.

## Runtime path đang dùng trên farmbot
```bash
/home/farm4bot/work/crawlbot_portable_scheduler_headless_server_v1
```

## 1) Vào đúng thư mục
```bash
cd /home/farm4bot/work/crawlbot_portable_scheduler_headless_server_v1
```

## 2) Chạy bot
Foreground:
```bash
./run-headless-server.sh
```

Background:
```bash
nohup ./run-headless-server.sh > /tmp/crawlbot-headless.out 2>&1 & echo $!
```

Nếu muốn có heartbeat file:
```bash
nohup ./run-crawlbot-with-heartbeat.sh > /tmp/crawlbot-heartbeat.out 2>&1 & echo $!
```

## 3) Xem log
Log ngoài nhanh nhất:
```bash
tail -f /tmp/crawlbot-headless.out
```

Nếu launcher/flow đang ghi vào logs nội bộ:
```bash
tail -f logs/headless-run.log
```

Xem log session mới nhất:
```bash
ls -1t logs/*.log | head -n 1 | xargs -r tail -n 80
```

## 4) Kiểm tra process
```bash
pgrep -af 'python.*main.py|run-headless-server|chromedriver|chrome.*chrome_user_data'
```

## 5) Dừng an toàn
Ưu tiên:
```bash
pkill -TERM -f 'python main.py'
```

Nếu cần dọn rộng hơn:
```bash
pkill -f 'python.*zalo|python.*crawler|chromedriver|chrome.*chrome_user_data'
```

Chỉ dùng khi process lì:
```bash
pkill -9 -f 'python.*zalo|python.*crawler|chromedriver|chrome.*chrome_user_data'
```

## 6) PASS tối thiểu
Khi lane chạy ổn, log nên có:
- `verify_mode=strong` hoặc `verify_mode=usable`
- `ROOM_SWITCH_TRACKER`
- `fairness scheduler:`
- vào room thành công
- save docx thành công
- gửi Telegram thành công

## 7) Dấu hiệu cần soi kỹ
- `group-opened-unverified`
- `navigation-stall`
- `HTTPConnectionPool(`
- `Read timed out`
- `tab crashed`

## 8) Runtime config đã kiểm thực gần nhất
- `HEADLESS=true`
- `GROUP_NAMES=HEY KLUB, RETURN Tái định cư`
- `CHROME_USER_DATA_DIR=./chrome_user_data`
- `CHROME_DEBUG_PORT=9222`

## 9) Lưu ý vận hành
- Không commit `.env`, `chrome_user_data/`, `data/`, `logs/`
- Runtime copy trên farmbot là lane chạy thật; repo GitHub là bản dev sạch để quản lý source
- Nếu cần session Zalo còn sống, đừng xóa `chrome_user_data/`
