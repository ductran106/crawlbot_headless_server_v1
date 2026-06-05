# Milestone — Scheduler / Runtime v1

Repo:
`/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab`

Ngày chốt mốc: 2026-03-23

Mục tiêu của note này: khóa lại đúng phạm vi những gì đã chốt ở milestone hiện tại, để sau này nhìn lại biết rõ:
- cái gì đã được sửa và có evidence tốt
- cái gì chưa sửa có chủ đích
- vì sao chưa mở tiếp Phase 5D vào `message_crawler.py`

---

## 1. Mốc này chốt cái gì?

Đây là milestone cho nhánh:
- **scheduler fairness**
- **browser/runtime hardening**

Không phải milestone cho toàn bộ crawler.

### Cụ thể, milestone này chốt 2 lớp:
1. **Scheduler layer** trong `main.py`
2. **Browser/runtime layer** trong:
   - `src/browser/navigation.py`
   - `src/browser/driver.py`
   - `main.py`

---

## 2. Những gì đã chốt xong

## 2.1 Scheduler fairness

### Đã làm
- bỏ kiểu sticky-room cũ dựa quá nhiều vào stay-budget
- chuyển sang fairness-first scheduler
- có starvation guard
- có cap consecutive visits
- có policy riêng cho 2-room và 3-room
- đưa knobs scheduler ra config
- thêm test fairness / config policy

### Đã sửa thêm bug logic quan trọng
- fix **never-visited room starvation**
- áp dụng theo hướng:
  - bootstrap visit mỗi room 1 lần
  - room chưa từng được ghé có ưu tiên cao hơn trước khi vào fairness loop bình thường

### Evidence
- bug `HEY KLUB không được ghé` đã được xác nhận là bug thật
- sau fix, soak-test ngắn đã xác nhận `HEY KLUB` được ghé và crawl thật

---

## 2.2 Browser / runtime hardening

### Phase 5A — `src/browser/navigation.py`
Đã chốt:
- thêm import runtime debt bị thiếu (`re`, `Keys`)
- thêm `_wait_until_header_matches()`
- siết `find_and_access_group()` chỉ success khi verify đúng room
- siết `reconnect_to_group()` theo cùng contract
- thêm fast-path nếu đã ở đúng room
- warmup nhẹ hơn cho multi-room mode

### Phase 5B — `src/browser/driver.py`
Đã chốt:
- thêm `check_zalo_surface_ready()`
- phân biệt driver alive với Zalo surface usable
- harden `restart_driver()`
- đổi `recover_session()` từ sleep cứng sang contract surface-ready hơn

### Phase 5C — `main.py`
Đã chốt:
- recovery contract phải reopen lại `target_group`
- nếu navigation chưa verify đúng room thì bỏ `crawl_step()` trong nhịp đó
- recovery path mang theo `target_group` rõ ràng hơn

### Lỗi phụ đã vá
- fix `build_error_log_path is not defined`
- runbook grep có fallback khi máy không có `rg`

---

## 3. Test / evidence hiện có

## Unit / regression side
- fairness/config/navigation/driver/main recovery tests đã được thêm và chạy xanh theo từng phase
- repo lab hiện có test cho:
  - fairness policy
  - scheduler config policy
  - navigation group access
  - browser driver recovery
  - main recovery contract

## Runtime / soak-test side
### 2-room
- pass khá sạch
- không còn sticky-room rõ như bản Portable cũ

### 3-room
- short-soak sau hardening 5A/5B/5C: tốt hơn rõ
- soak 10 phút: tích cực hơn rõ, browser/runtime đỡ vỡ sớm hơn
- fix never-visited starvation: đã xác nhận `HEY KLUB` được ghé/crawl trong run ngắn sau fix

---

## 4. Điều milestone này KHÔNG chốt

### Chưa chốt production-grade tuyệt đối cho 3-room
Vẫn chưa nên nói rằng:
- anti-miss đã hoàn hảo
- runtime đã hoàn toàn đanh cho mọi giờ cao điểm
- có thể chạy production dài hạn mà không cần theo dõi thêm

### Chưa mở Phase 5D vào `message_crawler.py`
Đây là quyết định có chủ đích.

Lý do:
- milestone hiện tại đã đủ lớn và có ý nghĩa riêng
- nếu mở `message_crawler.py` ngay, sẽ trộn crawler-cost concerns với scheduler/runtime concerns
- cần tách rõ từng mốc để khỏi mất khả năng đánh giá nguyên nhân–kết quả

---

## 5. Vì sao dừng ở đây là hợp lý?

Vì hiện tại đã có đủ 3 điều:
1. **patch có ý nghĩa kiến trúc**
2. **test có thật**
3. **runtime evidence có thật**

Đây là một điểm dừng tốt để nói rằng:
> milestone scheduler/runtime v1 đã hình thành

Nếu tiếp tục sửa ngay mà không chốt mốc, rất dễ:
- làm loãng kết quả
- quên mất bug nào đã được xử đúng
- khó phân biệt hiệu quả của Phase 5A/5B/5C với các sửa đổi sau này

---

## 6. Điều còn mở cho vòng sau

Nếu sau này mở tiếp nhánh mới, nên mở bằng câu hỏi rõ ràng như:
- `message_crawler.py` còn bottleneck gì thật sự?
- evidence nào trong log chỉ ra điều đó?
- sửa vào crawler để giảm cost path nào?
- sửa đó có đáng để thành **Phase 5D** riêng hay không?

### Candidate cho vòng sau
- `src/crawler/message_crawler.py`
- nhưng chỉ nên mở khi có evidence rõ từ log / soak-test / missed-message pattern

---

## 7. Một câu chốt milestone

**Milestone scheduler/runtime v1 được xem là đã đạt khi hệ không còn dừng ở mức “ý tưởng fairness”, mà đã có scheduler tốt hơn, recovery tốt hơn, browser/runtime bền hơn, và bug room thứ ba bị bỏ quên đã được sửa có evidence.**
