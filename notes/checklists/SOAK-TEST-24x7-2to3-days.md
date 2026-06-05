# SOAK-TEST-24x7-2to3-days

## Mục tiêu
Chạy 24/7 trong 2-3 ngày trên máy mới để bắt lỗi production-like.

## Mỗi ngày nhìn 4 lane

### 1) Process health
- [ ] Process còn sống
- [ ] Log vẫn tăng
- [ ] Không crash loop / restart loop

Check nhanh:
```bash
pgrep -af "python.*main.py"
tail -n 100 logs/portable-run.log
```

### 2) Session rollover / docx lane
Ở mỗi boundary phiên (P1..P6), kiểm tra:
- [ ] Có `Đổi phiên:`
- [ ] Có `Đã lưu tài liệu cuối cùng:`
- [ ] Có `SAVE_DOCUMENT_RESULT success=true`
- [ ] Có `Đã hoàn thành xử lý định dạng file:`
- [ ] Có `Đã gửi file Telegram thành công`
- [ ] Có file `final_...docx`
- [ ] Có file `Lich_...docx`

Fail signatures:
- [ ] `build_save_document_notification is not defined`
- [ ] `Lỗi khi lưu tài liệu`
- [ ] `Lỗi khi gửi file Telegram`

### 3) Navigation / reconnect lane
- [ ] Có `group-search-empty` không?
- [ ] Có `group-mismatch` lặp lại không?
- [ ] Có `reconnect_verify_failed` thành chuỗi dài không?
- [ ] Có room nào bị camp / không quay lại lâu không?

Check nhanh:
```bash
rg -n "group-search-empty|group-mismatch|reconnect_verify_failed|ROOM_SWITCH_TRACKER" logs/portable-run.log | tail -n 200
```

### 4) Browser / login lane
- [ ] Có mất login không?
- [ ] Có QR yêu cầu lại không?
- [ ] Có browser restart/recovery bất thường không?

Check nhanh:
```bash
rg -n "QR|logged_out|LOGIN_STATE_UNKNOWN|BROWSER_RESTART|BROWSER_RECOVERY|WebDriver|Chrome" logs/portable-run.log | tail -n 200
```

## Evidence nên lưu mỗi ngày
- [ ] tên log file chính
- [ ] mốc boundary đã pass/fail
- [ ] số lần Telegram docx send thành công
- [ ] 1-2 fail artifact đáng chú ý nếu có
- [ ] commit / HEAD đang chạy

## Điều kiện PASS sau 2-3 ngày
- [ ] process sống ổn định
- [ ] rollover docx pass liên tục
- [ ] Telegram send ổn định ở boundary
- [ ] không có bug mới nghiêm trọng ngoài lane navigation đã biết

## Điều kiện FAIL đáng escalte ngay
- [ ] mất docx ở boundary
- [ ] mất Telegram send lặp lại
- [ ] login rớt thường xuyên
- [ ] process chết im / log đứng
- [ ] room switching hỏng đến mức bỏ lỡ crawl kéo dài
