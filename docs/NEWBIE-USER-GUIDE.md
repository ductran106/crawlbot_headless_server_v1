# NEWBIE-USER-GUIDE.md — Hướng dẫn sử dụng repo mới cho người không rành kỹ thuật

Tài liệu này viết để **người mới / không chuyên kỹ thuật** vẫn có thể dùng được lane crawlbot mới trên FarmBot.

---

## 1. Tài liệu này dùng để làm gì?

Repo này là bản chạy mới của crawlbot tại:

- `/home/farm4bot/work/crawlbot_headless_server_v1_dev`

Hiện tại cách chạy chuẩn là:

- dùng **systemd user service**
- service name: `crawlbot-headless-dev.service`

Nói ngắn gọn:
- **Không cần tự chạy `python main.py` bằng tay mỗi lần nữa**
- Sau reboot, service này có thể tự chạy lại
- Khi cần kiểm tra / restart / xem log thì dùng vài lệnh cố định

---

## 2. Khi nào nên mở file này?

Mở file này khi bạn muốn:
- biết repo nào là repo đang dùng thật
- biết service nào là service chuẩn
- biết cách kiểm tra bot còn sống hay không
- biết cách restart bot khi nghi nó bị treo
- biết xem log khi bot có vấn đề
- biết cái gì **không nên đụng vào** để tránh làm mất session/login

---

## 3. Thông tin chuẩn cần nhớ

### Repo chuẩn đang dùng
- `/home/farm4bot/work/crawlbot_headless_server_v1_dev`

### Service chuẩn đang dùng
- `crawlbot-headless-dev.service`

### User chạy service
- `farm4bot`

### File lệnh quan trọng
- `README.md` → đọc mô tả nhanh
- `RUNBOOK.md` → quick runbook ngắn
- `SYSTEMD-RUNBOOK.md` → runbook chuẩn cho service systemd
- `docs/NEWBIE-USER-GUIDE.md` → hướng dẫn đầy đủ dễ hiểu này

---

## 4. Nguyên tắc an toàn cực quan trọng

Nếu bạn không chắc mình đang làm gì, hãy làm đúng 4 nguyên tắc này:

1. **Ưu tiên dùng `systemctl --user ...`** thay vì tự chạy tay.
2. **Không xóa thư mục `chrome_user_data`** nếu chưa hiểu rõ.
3. **Không đăng xuất Zalo trong Chrome** nếu mục tiêu là giữ session đang sống.
4. **Không mở nhiều lane crawlbot cùng lúc** nếu không có lý do rõ ràng.

---

## 5. Cách SSH vào máy FarmBot

Từ máy có quyền SSH, vào bằng user `farm4bot`:

```bash
ssh farm4bot@farmbot
```

Sau khi vào máy, bạn có thể chạy các lệnh bên dưới.

---

## 6. 3 lệnh quan trọng nhất

Nếu chỉ nhớ 3 lệnh, hãy nhớ 3 lệnh này.

### Xem trạng thái bot
```bash
systemctl --user status crawlbot-headless-dev.service
```

### Restart bot
```bash
systemctl --user restart crawlbot-headless-dev.service
```

### Xem log realtime
```bash
journalctl --user -u crawlbot-headless-dev.service -f
```

---

## 7. Cách biết bot đang chạy ổn hay không

### Bước 1 — kiểm tra service có đang chạy không

Chạy:

```bash
systemctl --user status crawlbot-headless-dev.service
```

Nếu thấy các chữ kiểu như sau thì thường là ổn:
- `active (running)`
- có `Main PID`
- không bị restart liên tục quá nhanh

Nếu thấy:
- `inactive (dead)`
- `failed`
- `activating` quá lâu

thì cần xem log.

---

### Bước 2 — xem log gần nhất

```bash
journalctl --user -u crawlbot-headless-dev.service -n 100 --no-pager
```

Hoặc xem realtime:

```bash
journalctl --user -u crawlbot-headless-dev.service -f
```

---

### Bước 3 — dấu hiệu tốt trong log

Các dấu hiệu tốt thường gặp:
- `Login state -> already-logged-in`
- `Navigation ok`
- `ROOM_SWITCH_TRACKER`
- `Đã lưu ... tin nhắn vào database`
- bot qua lại được giữa các room như:
  - `HEY KLUB`
  - `RETURN Tái định cư`

Nếu thấy các dòng kiểu này xuất hiện đều thì thường lane đang hoạt động.

---

## 8. Khi nào nên restart bot?

Nên restart khi:
- service không còn `active (running)`
- log đứng im quá lâu bất thường
- bot không còn chuyển room
- nghi bị treo browser / chromedriver
- có lỗi nhưng không tự hồi phục

Lệnh restart:

```bash
systemctl --user restart crawlbot-headless-dev.service
```

Sau khi restart, kiểm tra lại:

```bash
systemctl --user status crawlbot-headless-dev.service
journalctl --user -u crawlbot-headless-dev.service -n 80 --no-pager
```

---

## 9. Cách stop / start thủ công

### Stop
```bash
systemctl --user stop crawlbot-headless-dev.service
```

### Start
```bash
systemctl --user start crawlbot-headless-dev.service
```

### Restart
```bash
systemctl --user restart crawlbot-headless-dev.service
```

---

## 10. Kiểm tra sau khi reboot máy

Sau khi máy reboot, đăng nhập lại và chạy:

```bash
systemctl --user status crawlbot-headless-dev.service
```

Nếu vẫn thấy `active (running)` thì auto-start đang hoạt động đúng.

---

## 11. Muốn xem process thật bên dưới đang chạy gì

Nếu cần soi sâu hơn, dùng:

```bash
ps -ef | egrep "python(3)? .*main\\.py|chromedriver|chrome .*chrome_user_data" | egrep -v "egrep|grep"
```

Mục tiêu là nhìn thấy:
- Python chạy `main.py`
- `chromedriver`
- tiến trình `chrome`

---

## 12. Những file/thư mục quan trọng

### Repo chính
- `/home/farm4bot/work/crawlbot_headless_server_v1_dev`

### Docs / runbook
- `/home/farm4bot/work/crawlbot_headless_server_v1_dev/README.md`
- `/home/farm4bot/work/crawlbot_headless_server_v1_dev/RUNBOOK.md`
- `/home/farm4bot/work/crawlbot_headless_server_v1_dev/SYSTEMD-RUNBOOK.md`
- `/home/farm4bot/work/crawlbot_headless_server_v1_dev/docs/NEWBIE-USER-GUIDE.md`

### Script quan trọng
- `/home/farm4bot/work/crawlbot_headless_server_v1_dev/run-headless-server.sh`
- `/home/farm4bot/work/crawlbot_headless_server_v1_dev/scripts/hourly-status-report.sh`
- `/home/farm4bot/work/crawlbot_headless_server_v1_dev/scripts/check-forensic-markers-once.sh`

### User systemd unit
- `/home/farm4bot/.config/systemd/user/crawlbot-headless-dev.service`

---

## 13. Những điều KHÔNG nên làm nếu chưa hiểu

### Không nên làm 1: tự xóa profile Chrome
Không xóa:
- `chrome_user_data`
- `chrome_user_data.devcopy`

Vì đây có thể là nơi giữ session/login và trạng thái browser.

### Không nên làm 2: chạy nhiều bot trùng nhau
Không nên vừa:
- `systemctl --user start ...`
- vừa `python main.py`
- vừa mở thêm lane test khác

Điều này có thể làm đụng session, log, profile hoặc browser.

### Không nên làm 3: giết process bừa bằng `pkill` quá rộng
Ví dụ không nên dùng pattern quá rộng vì có thể giết nhầm process khác hoặc làm rơi session SSH.

---

## 14. Nếu bot lỗi thì đọc theo thứ tự nào?

Nếu có sự cố, hãy làm theo đúng thứ tự này:

### Mức 1 — kiểm tra trạng thái service
```bash
systemctl --user status crawlbot-headless-dev.service
```

### Mức 2 — xem 100 dòng log gần nhất
```bash
journalctl --user -u crawlbot-headless-dev.service -n 100 --no-pager
```

### Mức 3 — restart service
```bash
systemctl --user restart crawlbot-headless-dev.service
```

### Mức 4 — xem log realtime
```bash
journalctl --user -u crawlbot-headless-dev.service -f
```

### Mức 5 — nếu vẫn chưa rõ, mới kiểm tra process tree
```bash
ps -ef | egrep "python(3)? .*main\\.py|chromedriver|chrome .*chrome_user_data" | egrep -v "egrep|grep"
```

---

## 15. Dấu hiệu “ổn” và “chưa ổn”

### Dấu hiệu ổn
- service là `active (running)`
- có `Main PID`
- log có `already-logged-in`
- log có `Navigation ok`
- log có `ROOM_SWITCH_TRACKER`
- log vẫn sinh ra dữ liệu mới

### Dấu hiệu chưa ổn
- service `failed`
- restart liên tục
- log đứng lâu bất thường
- không còn chuyển room
- browser/chromedriver mất nhưng Python vẫn treo
- login bị văng ra ngoài

---

## 16. Nếu chỉ muốn “làm cho bot chạy lại” thật nhanh

Dùng đúng 3 lệnh này:

```bash
systemctl --user restart crawlbot-headless-dev.service
sleep 3
systemctl --user status crawlbot-headless-dev.service
```

Sau đó nếu cần soi tiếp:

```bash
journalctl --user -u crawlbot-headless-dev.service -n 80 --no-pager
```

---

## 17. Nếu không phải người kỹ thuật, câu thần chú nên nhớ

Nếu không chắc:
- đừng xóa gì cả
- đừng chạy tay `python main.py`
- đừng đụng `chrome_user_data`
- chỉ dùng:
  - `status`
  - `restart`
  - `journalctl`

---

## 18. File nào nên đọc tiếp theo?

Nếu bạn muốn đọc thêm:

1. `README.md` → giới thiệu nhanh repo
2. `RUNBOOK.md` → thao tác nhanh
3. `SYSTEMD-RUNBOOK.md` → thao tác systemd chuẩn
4. `docs/NEWBIE-USER-GUIDE.md` → hướng dẫn chi tiết dễ hiểu

---

## 19. Kết luận ngắn

Cho repo mới này, cách dùng chuẩn hiện tại là:
- dùng service `crawlbot-headless-dev.service`
- ưu tiên `systemctl --user ...`
- không chạy tay trừ khi thật cần
- không đụng profile Chrome nếu chưa hiểu rõ

