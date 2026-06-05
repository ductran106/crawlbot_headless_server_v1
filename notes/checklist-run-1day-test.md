# Checklist cực ngắn — Run 1-day observed long-run test

Repo:
`/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab`

Mục tiêu: chạy runtime riêng cho repo lab trong khoảng 1 ngày để lấy evidence dài hạn, không đụng lane live của 2 project cũ.

---

## Trước khi chạy

- [ ] Xác nhận chạy trên **repo lab**, không phải repo live
- [ ] Chọn profile cố định: **3-room**
- [ ] Không tune thêm config ngay trước khi chạy
- [ ] Dùng log riêng, không lẫn với run cũ
- [ ] Không sửa code giữa chừng trong suốt vòng 1 ngày

### Lệnh gợi ý
```bash
cd /home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab
./use-3room.sh
. .venv/bin/activate
python -m pytest -q tests/test_navigation_group_access.py tests/test_browser_driver_recovery.py tests/test_main_recovery_contract.py tests/test_message_crawler_recovery.py
```

---

## Khi bắt đầu run

- [ ] Ghi lại thời điểm bắt đầu
- [ ] Archive / tách log cũ ra chỗ khác
- [ ] Tạo log folder sạch cho vòng này
- [ ] Chạy bot ở runtime riêng cho repo lab

### Nguyên tắc
- Không đổi `.env`
- Không sửa code
- Không chèn patch nóng giữa chừng
- Nếu có lỗi, để nó log lại; không chữa tay ngay trừ khi buộc phải dừng hẳn

---

## Trong lúc chạy

Không cần ngồi nhìn liên tục, chỉ cần thỉnh thoảng check:

- [ ] Có crash browser không?
- [ ] Có recovery được không?
- [ ] Có room nào bị bỏ quên quá lâu không?
- [ ] HEY KLUB có được ghé/crawl không?
- [ ] File/docx/Telegram send có còn đều không?

---

## Sau khi chạy xong

- [ ] Ghi lại thời điểm kết thúc
- [ ] Chạy summarize `ROOM_SWITCH_TRACKER`
- [ ] Gom evidence review theo template `notes/1-day-evidence-review-template.md`
- [ ] Chưa sửa gì ngay; đọc evidence trước

### Tiêu chí review sau 1 ngày
- [ ] crash count
- [ ] recovery count
- [ ] room fairness
- [ ] HEY KLUB / room 3 có bị bỏ quên nữa không
- [ ] file/docx/Telegram send có ổn định không

---

## Một câu chốt

Vòng 1-day này là để lấy **evidence sạch**. Mục tiêu không phải chữa lỗi giữa chừng, mà là quan sát đủ lâu để lần sửa sau đúng chỗ và đáng tiền.
