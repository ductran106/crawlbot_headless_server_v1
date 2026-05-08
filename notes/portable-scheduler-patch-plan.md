# Portable Scheduler Patch Plan

Repo làm việc an toàn: `/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab`

Mục tiêu: chuyển design scheduler 2-room / 3-room thành patch plan cụ thể cho repo Portable, theo hướng:
- không chạm live run của 2 project hiện tại
- giảm miss khi nhiều room cùng nóng
- giữ các cải tiến tốt của Portable (observability, fail artifacts, tests, structured state)
- sửa đúng chỗ đang làm fairness vỡ: dwell quá lâu ở 1 room

---

## 1. Root cause cần sửa

Portable hiện miss nhiều hơn repo cũ chủ yếu vì:
- dùng `stay_on_group_budget` để ở lại room nóng quá lâu
- `possible_gap` và `backlog_hot` có thể kéo scheduler thành sticky-room policy
- fairness giữa các room bị giảm
- room không được ghé lâu dễ trôi DOM window
- `crawl_step()` còn khá nặng trong room nóng

Kết luận:
- không cần bỏ Portable
- cần sửa scheduler thành **fair adaptive scheduler**

---

## 2. Patch objective

### Objective 1
Khôi phục **round-robin fairness** làm backbone.

### Objective 2
Giữ adaptive behavior nhưng giới hạn:
- hot room chỉ được bonus hữu hạn
- không room nào được độc chiếm lane

### Objective 3
Thêm starvation guard để đảm bảo room bị đói sẽ được kéo lên đúng lúc.

### Objective 4
Giảm per-cycle cost trong multi-room mode.

---

## 3. Files cần sửa

## 3.1 `main.py`
Đây là file patch chính.

### Cần thay đổi
- bỏ logic `stay_on_group_budget` hiện tại hoặc giảm nó thành lớp bonus rất mỏng
- thay `_compute_group_scheduling_decision()` thành policy fairness-first
- thêm `last_visited_at` / `consecutive_visits` / `starvation_seconds`
- thêm rule khác nhau theo số room (`len(groups) == 2` / `== 3` / `> 3`)
- đổi logic chọn room kế tiếp từ “ở lại hay không” sang “chọn room kế tiếp theo score + starvation guard”

### Mục tiêu code-level
Từ logic kiểu:
- crawl room hiện tại
- nếu room này nóng thì ở lại

sang logic kiểu:
- crawl room hiện tại
- update state tất cả room
- chọn room kế tiếp theo fairness-first rules

---

## 3.2 `src/crawler/message_crawler.py`
Patch phụ nhưng quan trọng.

### Cần thay đổi
- cho phép `wait_for_messages_stable()` dùng timeout ngắn hơn trong multi-room mode
- batch DB write theo mỗi `crawl_step()` thay vì save per-message
- giữ nguyên backlog signals (`backlog_pressure`, `possible_gap`, `backlog_hot`) nhưng để scheduler dùng như signal ưu tiên chứ không phải signal khóa lane

### Mục tiêu code-level
- giảm thời gian 1 room chiếm lane
- giảm dwell time thực tế mỗi vòng crawl

---

## 3.3 `src/utils/config.py`
Thêm config knobs mới cho scheduler.

### Cần thêm env/config gợi ý
- `MULTI_ROOM_MODE=true`
- `MULTI_ROOM_STABLE_WAIT_2ROOM=1.5`
- `MULTI_ROOM_STABLE_WAIT_3ROOM=1.0`
- `SCHED_MAX_CONSECUTIVE_VISITS=2`
- `SCHED_STARVATION_SEC_2ROOM=6`
- `SCHED_STARVATION_SEC_3ROOM=8`
- `SCHED_HOT_SLEEP_SEC=1`
- `SCHED_PRESSURE_SLEEP_SEC=2`
- `SCHED_NORMAL_SLEEP_MIN_SEC=2`
- `SCHED_NORMAL_SLEEP_MAX_SEC=4`

### Mục tiêu
- tránh hardcode magic numbers rải trong `main.py`
- dễ tune ngoài code sau này

---

## 3.4 Tests cần thêm/sửa

### Test file nên thêm mới
- `tests/test_scheduler_fairness_policy.py`
- `tests/test_scheduler_starvation_guard.py`
- `tests/test_scheduler_two_room_bonus_cap.py`
- `tests/test_scheduler_three_room_priority.py`

### Test cũ nên cập nhật nếu cần
- `tests/test_anti_miss_scheduler_hints.py`

### Mục tiêu test
- với 2 room: không room nào bị bonus stay quá 1 lần liên tiếp
- với 3 room: không room nào bị ghé >2 lần liên tiếp
- starvation breach sẽ force switch đúng room
- `possible_gap` tăng ưu tiên nhưng không override starvation guard

---

## 4. Patch design cụ thể

## Phase 1 — Scheduler state model

### Thêm state cho mỗi room
Dạng tối thiểu:

```python
room_state = {
  room_name: {
    "last_visited_at": float,
    "consecutive_visits": int,
    "backlog_pressure": bool,
    "possible_gap": bool,
    "backlog_hot": bool,
    "last_processed_count": int,
    "last_visible_count": int,
  }
}
```

### Ghi chú
Hiện Portable đã có một phần tín hiệu trong crawler, chỉ cần nâng về scheduler-level state rõ hơn.

---

## Phase 2 — Replace stay-budget policy

### Hiện tại
Portable dùng:
- `stay_on_group_budget`
- `_update_group_backlog_tracker()`
- `_compute_group_scheduling_decision()`

### Sửa thành
Tạo hàm mới kiểu:
- `_build_scheduler_policy(room_count)`
- `_compute_starvation_seconds(state, now)`
- `_select_next_room(groups, room_state, current_room, now)`
- `_select_sleep_seconds(last_room_state, room_count)`

### Ý đồ
Không còn suy nghĩ “ở lại room này bao nhiêu lần nữa”, mà chuyển thành:
- “sau room này, room nào đáng được ghé tiếp theo nhất?”

---

## Phase 3 — 2-room policy

### Rules implement
- backbone alternating
- max consecutive visits = 2
- starvation threshold = 6s
- hot room được 1 bonus visit tối đa
- `possible_gap` chỉ tăng score, không bypass starvation guard

### Kỳ vọng hành vi
- A/B quay lại đủ nhanh
- room nóng có lợi thế nhẹ
- không còn hiện tượng A/A/A kéo dài

---

## Phase 4 — 3-room policy

### Rules implement
- backbone round-robin
- max consecutive visits = 2
- starvation threshold = 8s
- nếu nhiều room cùng nóng, ưu tiên room bị đói lâu nhất
- room nóng không được độc chiếm lane

### Kỳ vọng hành vi
- giảm starve room thứ ba
- revisit latency của cả 3 room có trần rõ hơn

---

## Phase 5 — Multi-room crawl-step cost reduction

### Patch 5.1 — stable wait timeout
Trong `MessageCrawler.crawl_step()`:
- cho timeout phụ thuộc `room_count` hoặc mode
- 2 room: khoảng 1.5s
- 3 room: khoảng 1.0s

### Patch 5.2 — batch DB writes
Hiện tại save DB theo từng tin:

```python
self.db_manager.save_messages([{...}], self.group_name)
```

Cần đổi thành:
- gom danh sách message trong một vòng
- cuối vòng save một lần

### Lợi ích
- giảm IO overhead
- giảm thời gian room hiện tại chiếm lane

---

## 5. Observability patch

Cần log thêm các field sau trong `room_switch_tracker` hoặc event tương đương:
- `starvation_seconds`
- `consecutive_visits`
- `selected_by`
  - `starvation_guard`
  - `priority_score`
  - `round_robin`
- `priority_score`
- `room_count`
- `policy_mode` (`2room` / `3room` / `nroom`)

### Mục tiêu
- lần sau có evidence thật để tune scheduler
- không phải chỉ nhìn cảm giác “ở room này lâu quá”

---

## 6. Patch order đề xuất

## Step 1
Tạo repo lab riêng (đã xong)
- `/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab`

## Step 2
Patch scheduler core trong `main.py`
- thêm state model
- thay room selection logic
- bỏ sticky stay-budget

## Step 3
Patch `message_crawler.py`
- multi-room stable wait ngắn hơn
- batch DB writes

## Step 4
Patch `config.py`
- thêm scheduler knobs

## Step 5
Viết test policy mới

## Step 6
Chạy smoke test / dry simulation
- mô phỏng state transitions 2-room và 3-room
- chưa cần chạy live Zalo thật

## Step 7
Nếu smoke ổn mới mới tính deploy sang runtime riêng để soak test

---

## 7. Thành công được định nghĩa như nào?

Patch được coi là thành công khi:

### Với 2 room
- không room nào bị ở liên tiếp > 2 lần
- room không active không bị đói quá threshold
- cadence quay lại room còn lại ngắn hơn Portable hiện tại

### Với 3 room
- room thứ ba không còn bị starve dài
- revisit latency phân bố đều hơn
- room nóng vẫn được ưu tiên nhưng không độc chiếm lane

### Về codebase
- Portable vẫn giữ được observability / fail artifacts / structured logging
- không phải quay về bản cũ hoàn toàn

---

## 8. Điều tuyệt đối không làm trong patch này

- không patch trực tiếp vào 2 repo live đang chạy
- không đụng dữ liệu runtime thật
- không copy `chrome_user_data`, `data`, `logs` vào repo lab để tránh nhiễu
- không tối ưu quá tay theo lý thuyết trước khi có simulation/test

---

## 9. Output cuối của nhánh patch này

Repo lab sau patch nên có:
- scheduler fairness-first chạy cho 2 room và 3 room
- config knobs rõ ràng
- tests cho scheduler policy
- note giải thích rule để sau này maintain không bị quên ý đồ

---

## 10. Câu chốt

Patch này không nhằm “làm room nóng mạnh hơn”, mà nhằm **khôi phục fairness đủ mạnh để room nóng không giết room còn lại**. Trong bài toán crawl từ DOM/UI, đó mới là con đường anti-miss đúng.
