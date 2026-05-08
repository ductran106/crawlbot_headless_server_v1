# Portable Scheduler Soak-Test Checklist

Repo lab:
`/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab`

Mục tiêu: soak-test fairness-first scheduler sau Phase 1-4 trong điều kiện gần thực tế, trước khi cân nhắc đưa sang runtime riêng hoặc merge ngược.

---

## 1. Mục tiêu soak-test

Soak-test này không nhằm chứng minh "zero miss tuyệt đối".
Nó nhằm trả lời 4 câu hỏi thực tế:

1. Với **2 room**, room còn lại có còn bị bỏ đói quá lâu không?
2. Với **3 room**, room thứ ba có còn bị starve rõ như trước không?
3. Khi room nóng, scheduler có ưu tiên đúng mức mà không độc chiếm lane không?
4. Sau khi giảm dwell time + batch DB write, vòng quay có mượt hơn không?

---

## 2. Chuẩn bị trước khi test

### 2.1 Không dùng live repo
- Chạy từ repo lab, không chạm 2 project live.
- Repo lab đã có fairness scheduler + config knobs + test xanh.

### 2.2 Tạo `.env` riêng cho lab
Từ file:
- `.env.scheduler-tuning.example`

copy sang:
- `.env`

### 2.3 Kiểm tra nhanh cấu hình cần chú ý
- `GROUP_NAMES`
- `MULTI_ROOM_STABLE_WAIT_2ROOM`
- `MULTI_ROOM_STABLE_WAIT_3ROOM`
- `SCHED_MAX_CONSECUTIVE_VISITS`
- `SCHED_STARVATION_SEC_2ROOM`
- `SCHED_STARVATION_SEC_3ROOM`
- `SCHED_HOT_SLEEP_SEC`
- `SCHED_PRESSURE_SLEEP_SEC`

### 2.4 Ghi lại baseline trước khi test
Trước khi chạy, note nhanh:
- test 2 room hay 3 room
- room nào thường nóng
- room nào thường ít tin
- kỳ vọng cụ thể

Ví dụ:
- 2 room: RET 2 ROOM LỊCH + HEY KLUB
- kỳ vọng: không để 1 room bị bỏ >6s quá thường xuyên

---

## 3. Kịch bản test đề xuất

## Kịch bản A — 2 room, cả hai tương đối nóng

### Mục tiêu
- xem room A nóng có làm room B bị đói kéo dài không
- xác nhận không có pattern kiểu `A -> A -> A`

### Cần quan sát
- `selected_by`
- `consecutive_visits`
- `starvation_seconds`
- `sleep_s`
- cadence đổi room

### Pass nếu
- không thấy room nào bị `consecutive_visits > 2`
- room còn lại vẫn được ghé đều
- khi room kia đói quá ngưỡng, có force switch rõ

---

## Kịch bản B — 2 room, một room rất nóng, một room vừa phải

### Mục tiêu
- xem hot room có được ưu tiên vừa đủ mà không bóp chết room còn lại

### Pass nếu
- hot room được ghé dày hơn nhẹ
- room còn lại không bị bỏ đói quá lâu
- cadence tổng thể vẫn ổn định hơn bản Portable cũ

---

## Kịch bản C — 3 room, một room nóng, hai room vừa

### Mục tiêu
- xác nhận room nóng không monopolize lane
- room thứ ba không bị quên quá lâu

### Pass nếu
- không có pattern `A -> A -> A`
- room B/C vẫn được quay lại đủ đều
- scheduler chọn room theo starvation/fairness chứ không chỉ bám room nóng

---

## Kịch bản D — 3 room, hai room nóng cùng lúc

### Mục tiêu
- đây là case dễ lộ fairness bug nhất
- xác nhận room bị đói lâu nhất được kéo lên đúng lúc

### Pass nếu
- room thứ ba không starve quá rõ
- scheduler không dao động kiểu chỉ nhảy qua lại giữa 2 room nóng và bỏ quên room còn lại

---

## 4. Metrics cần nhìn khi soak-test

## 4.1 Quan trọng nhất
- `starvation_seconds`
- `consecutive_visits`
- `selected_by`
- `sleep_s`
- `processed_count`
- `backlog_pressure`
- `possible_gap`
- `backlog_hot`

## 4.2 Diễn giải nhanh

### `starvation_seconds`
- càng thấp/càng có trần ổn thì càng tốt
- nếu thường xuyên phình to ở 1 room, fairness chưa ổn

### `consecutive_visits`
- nếu thấy >2 thì bug policy
- nếu toàn =1 nhưng miss vẫn cao, có thể scheduler quá cứng hoặc crawl_step còn đắt

### `selected_by`
- `starvation_guard` xuất hiện đúng lúc là dấu hiệu tốt
- nếu toàn `priority_score` cho cùng một room liên tục thì có mùi monopolize

### `processed_count` vs `backlog_pressure`
- nếu processed thấp mà backlog cứ nóng liên tục, có thể room đó cần tune thêm

---

## 5. Log nên grep khi test

Ưu tiên nhìn các dòng:
- `ROOM_SWITCH_TRACKER`
- `fairness scheduler:`
- `backlog_pressure=true`
- `possible_gap=true`
- `backlog_hot=true`

### Gợi ý grep
```bash
rg "ROOM_SWITCH_TRACKER|fairness scheduler|backlog_pressure=true|possible_gap=true|backlog_hot=true" logs -n
```

---

## 6. Dấu hiệu pass / fail

## Pass signals
- room chuyển đều hơn bản Portable cũ
- không room nào bị ở quá 2 lượt liên tiếp
- room đói lâu được kéo lên đúng lúc
- không thấy cảm giác "bot kẹt lâu trong một room"

## Fail signals
- vẫn thấy pattern một room chiếm lane quá lâu
- room thứ ba thường xuyên bị đói rõ
- `possible_gap` tăng nhưng scheduler không cứu room bị đói
- log cho thấy `selected_by=priority_score` lặp đi lặp lại cho cùng một room quá nhiều

---

## 7. Thứ tự tuning nếu soak-test chưa ổn

Không tune lung tung. Tune theo thứ tự:

### Ưu tiên 1
Giảm:
- `SCHED_STARVATION_SEC_2ROOM`
- hoặc `SCHED_STARVATION_SEC_3ROOM`

Nếu room bị đói quá lâu.

### Ưu tiên 2
Giảm:
- `MULTI_ROOM_STABLE_WAIT_2ROOM`
- `MULTI_ROOM_STABLE_WAIT_3ROOM`

Nếu cảm giác dwell time từng room vẫn còn nặng.

### Ưu tiên 3
Giảm:
- `SCHED_NORMAL_SLEEP_MAX_SEC_2ROOM`
- `SCHED_NORMAL_SLEEP_MAX_SEC_3ROOM`

Nếu cadence đổi room còn chậm.

### Ưu tiên 4
Chỉ cân nhắc tăng/giảm:
- `SCHED_MAX_CONSECUTIVE_VISITS`

Mặc định nên giữ `2`. Không nên nới lên sớm.

---

## 8. Form ghi kết quả soak-test

## Run metadata
- Date/time:
- Mode: 2-room / 3-room
- Groups:
- Config profile:
- Duration:

## Quan sát nhanh
- Room nào nóng nhất:
- Có room nào bị starve rõ không:
- Có thấy pattern ở lì một room không:
- `selected_by` chủ yếu là gì:

## Kết luận
- Pass / soft pass / fail:
- Knob cần tune tiếp:
- Đề xuất thay đổi:

---

## 9. Tiêu chí trước khi tính chuyện merge / deploy

Chỉ nên cân nhắc đi xa hơn khi:
- test local vẫn xanh
- soak-test 2-room ổn
- soak-test 3-room không còn lộ starvation rõ
- log cho thấy fairness policy hoạt động như thiết kế

---

## Một câu chốt

Nếu sau soak-test anh thấy bot **quay lại mọi room đều hơn**, ít cảm giác “kẹt” trong một room hơn, và room thứ ba không còn bị quên rõ rệt, thì patch đang đi đúng hướng.
