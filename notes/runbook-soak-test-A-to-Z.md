# Runbook Cực Ngắn — Soak-Test Scheduler Từ A tới Z

Repo:
`/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab`

Mục tiêu: chạy soak-test nhanh cho fairness-first scheduler trong repo lab, theo quy trình ngắn nhất nhưng vẫn đủ sạch để quan sát.

---

## 0. Vào repo

```bash
cd /home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab
```

---

## 1. Chọn profile

### Test 2 room
```bash
./use-2room.sh
```

### Test 3 room
```bash
./use-3room.sh
```

Sau khi chạy, nhớ nhìn lại `GROUP_NAMES` script vừa in ra.

---

## 2. Review nhanh `.env`

```bash
grep -E '^(GROUP_NAMES|DEFAULT_GROUP_NAME|MULTI_ROOM_STABLE_WAIT_2ROOM|MULTI_ROOM_STABLE_WAIT_3ROOM|SCHED_MAX_CONSECUTIVE_VISITS|SCHED_STARVATION_SEC_2ROOM|SCHED_STARVATION_SEC_3ROOM|SCHED_HOT_SLEEP_SEC|SCHED_PRESSURE_SLEEP_SEC|SCHED_NORMAL_SLEEP_MIN_SEC_2ROOM|SCHED_NORMAL_SLEEP_MAX_SEC_2ROOM|SCHED_NORMAL_SLEEP_MIN_SEC_3ROOM|SCHED_NORMAL_SLEEP_MAX_SEC_3ROOM)=' .env
```

Mục tiêu ở bước này:
- xác nhận đang dùng đúng profile
- xác nhận knobs scheduler đúng như mong muốn

---

## 3. Chạy test nhanh trước khi soak

```bash
. .venv/bin/activate
python -m pytest -q tests/test_anti_miss_scheduler_hints.py tests/test_scheduler_fairness_policy.py tests/test_scheduler_config_policy.py
```

Nếu test không xanh thì **không soak**.

---

## 4. Xóa nhiễu log cũ nếu muốn đọc kết quả sạch hơn

Chỉ làm trong repo lab.

```bash
mkdir -p logs
mv logs "logs_backup_$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
mkdir -p logs
```

Nếu không muốn move cả thư mục thì có thể chỉ archive file log cũ theo cách riêng của anh.

---

## 5. Chạy soak-test thật

### Cách thường
```bash
. .venv/bin/activate
python main.py
```

### Nếu muốn lưu console output riêng
```bash
. .venv/bin/activate
python main.py | tee soak-test-$(date +%Y%m%d-%H%M%S).log
```

---

## 6. Trong lúc bot chạy, cần nhìn gì?

Ưu tiên grep các tín hiệu sau:

```bash
if command -v rg >/dev/null 2>&1; then
  rg "ROOM_SWITCH_TRACKER|fairness scheduler|backlog_pressure=true|possible_gap=true|backlog_hot=true" logs -n
else
  grep -RInE "ROOM_SWITCH_TRACKER|fairness scheduler|backlog_pressure=true|possible_gap=true|backlog_hot=true" logs
fi
```

### Điều cần quan sát bằng mắt
- có bị cảm giác bot kẹt ở một room quá lâu không
- room còn lại / room thứ ba có được quay lại đều không
- `selected_by=starvation_guard` có xuất hiện lúc hợp lý không
- `consecutive_visits` có vượt 2 không

---

## 7. Dừng soak-test sau khi đủ thời lượng

Tùy mục tiêu, có thể chạy:
- 15–30 phút để nhìn behavior ban đầu
- 1–2 giờ nếu muốn nhìn giờ cao điểm rõ hơn

Dừng bằng cách bình thường của terminal (`Ctrl+C`) hoặc đúng cách anh vẫn dùng cho repo này.

---

## 8. Summarize nhanh sau khi chạy

```bash
./scripts/summarize-room-switch-tracker.py logs
```

Script sẽ tóm theo room:
- `events`
- `avg_processed`
- `max_starvation_sec`
- `max_consecutive`
- `max_sleep_sec`
- `backlog_pressure_cnt`
- `possible_gap_cnt`
- `backlog_hot_cnt`
- `selected_by`

---

## 9. Cách đọc kết quả nhanh

### Tín hiệu tốt
- `max_consecutive` không vượt 2
- `max_starvation_sec` không phình bất thường ở một room
- room thứ ba không bị đói rõ trong mode 3 room
- `selected_by` không bị lệch hẳn về một room nóng mãi

### Tín hiệu xấu
- vẫn thấy bot ở lì một room
- `max_starvation_sec` cao rõ ở room còn lại
- room thứ ba bị lãng quên khi 2 room khác nóng
- `possible_gap` lặp nhiều nhưng scheduler không cứu room bị đói

---

## 10. Nếu kết quả chưa ổn thì tune theo thứ tự này

### Tune 1 — giảm starvation threshold
- `SCHED_STARVATION_SEC_2ROOM`
- `SCHED_STARVATION_SEC_3ROOM`

### Tune 2 — giảm stable wait
- `MULTI_ROOM_STABLE_WAIT_2ROOM`
- `MULTI_ROOM_STABLE_WAIT_3ROOM`

### Tune 3 — giảm normal sleep max
- `SCHED_NORMAL_SLEEP_MAX_SEC_2ROOM`
- `SCHED_NORMAL_SLEEP_MAX_SEC_3ROOM`

### Tune 4 — chỉ đụng sau cùng
- `SCHED_MAX_CONSECUTIVE_VISITS`

Khuyến nghị hiện tại: **giữ `SCHED_MAX_CONSECUTIVE_VISITS=2`**, đừng nới sớm.

---

## 11. Mẫu quy trình ngắn nhất

### Soak-test 2 room
```bash
cd /home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab
./use-2room.sh
. .venv/bin/activate
python -m pytest -q tests/test_anti_miss_scheduler_hints.py tests/test_scheduler_fairness_policy.py tests/test_scheduler_config_policy.py
python main.py
```

Sau khi dừng:
```bash
./scripts/summarize-room-switch-tracker.py logs
```

### Soak-test 3 room
```bash
cd /home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab
./use-3room.sh
. .venv/bin/activate
python -m pytest -q tests/test_anti_miss_scheduler_hints.py tests/test_scheduler_fairness_policy.py tests/test_scheduler_config_policy.py
python main.py
```

Sau khi dừng:
```bash
./scripts/summarize-room-switch-tracker.py logs
```

---

## 12. Một câu chốt

Runbook này đủ để anh làm đúng 3 việc theo thứ tự:
1. chọn đúng profile
2. soak-test bản lab sạch
3. đọc nhanh kết quả để quyết định có cần tune tiếp không
