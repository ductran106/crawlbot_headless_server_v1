# 1-Day Evidence Review Template

Repo:
`/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab`

Mục tiêu: review evidence sau vòng observed long-run ~1 ngày, để quyết định:
- giữ nguyên milestone hiện tại
- hay mở patch tiếp theo (ví dụ Phase 5D vào `message_crawler.py`)

---

## 1. Run metadata

- Date:
- Start time:
- End time:
- Duration:
- Profile: **3-room**
- Repo path:
- Commit / working state note:
- `.env` profile used:
- Log folder / run log:

---

## 2. Crash / recovery review

### Crash count
- Browser crash count:
- Tab crash count:
- Connection refused count:
- Driver restart attempts:
- Driver restart failures:
- Recover session failures:

### Nhận xét
- Recovery có tự đứng dậy sạch không?
- Có loop crash/recover lặp lại không?
- Có time window nào lỗi dồn cụm không?

---

## 3. Room fairness review

### Tracker summary
- Total ROOM_SWITCH_TRACKER events:
- Rooms seen in tracker:
- `max_consecutive` theo từng room:
- `max_starvation_sec` theo từng room:
- `selected_by` distribution theo từng room:

### Nhận xét fairness
- Có room nào bị ghé ít bất thường không?
- Có sticky-room pattern quay lại không?
- Bootstrap-never-visited có chỉ chạy ở đầu vòng rồi trả hệ về fairness ổn định không?

---

## 4. HEY KLUB / room 3 review

### Evidence
- HEY KLUB có xuất hiện trong ROOM_SWITCH_TRACKER không?
- HEY KLUB có được mở room thật không?
- HEY KLUB có crawl ra message thật không?
- HEY KLUB có save final/autosave/docx/send Telegram ổn không?

### Kết luận riêng cho room 3
- [ ] ổn
- [ ] hơi lệch nhưng chấp nhận được
- [ ] còn dấu hiệu bị bỏ quên

Ghi chú:

---

## 5. File / docx / Telegram send review

### Kiểm tra
- Save final file có ổn không?
- Autosave có bị lỗi không?
- Format docx có ổn không?
- Telegram text notify có ổn không?
- Telegram document send có ổn không?

### Bất thường nếu có
-
-
-

---

## 6. Runtime quality review

### Các dấu hiệu tốt
-
-
-

### Các dấu hiệu xấu
-
-
-

### Nhận định tổng thể
- 2-room quality so với trước:
- 3-room quality so với trước:
- Runtime/browser có còn là bottleneck chính không?

---

## 7. Quyết định sau review

Chọn một:

- [ ] Giữ nguyên milestone hiện tại, chưa sửa thêm
- [ ] Mở patch tiếp theo ở `message_crawler.py`
- [ ] Mở patch tiếp theo ở browser/runtime
- [ ] Chạy thêm một vòng long-run nữa trước khi quyết định

### Lý do

---

## 8. Nếu phải sửa tiếp, sửa gì trước?

### Candidate patch area
- [ ] `src/crawler/message_crawler.py`
- [ ] `src/browser/navigation.py`
- [ ] `src/browser/driver.py`
- [ ] `main.py`
- [ ] Khác:

### Evidence nào dẫn tới quyết định đó?
-
-
-

---

## 9. One-line conclusion

> Sau vòng 1-day observed long-run này, kết luận ngắn nhất là: ...
