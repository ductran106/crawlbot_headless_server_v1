# Crawlbot Lane Reason Codes

Tài liệu ngắn để team nhìn phát hiểu taxonomy hiện tại của crawlbot lane.

## Mục tiêu
- gom toàn bộ `reason` codes về một ngôn ngữ chung
- giúp log / fail artifact / notify policy / recovery logic nói cùng một thứ tiếng
- giúp test/regression dễ khóa behavior hơn

Source-of-truth trong code:
- `src/utils/status_codes.py`

## Nhóm reason chính

### 1) ready
Dùng khi lane đang ở trạng thái sẵn sàng hoặc vừa xác nhận ổn.

- `ready-in-target-group`
  - đã login
  - đang ở đúng target group
- `already-logged-in`
  - login marker hiện diện
- `group-opened-at-navigation`
  - navigation layer vừa mở được group
- `login-detected`
  - auth flow phát hiện login đã thành công

### 2) login
Dùng khi lane đang ở vấn đề liên quan login / QR / auth uncertainty.

- `qr-visible`
  - đang thấy QR/login screen
- `login-state-unknown`
  - chưa phân loại rõ là login ok hay QR state
- `qr-expired`
  - QR đã hết hạn
- `qr-send-attempt`
  - đang thử gửi QR
- `qr-sent`
  - QR đã được gửi đi
- `waiting-for-login`
  - đang chờ user login
- `login-timeout`
  - hết thời gian chờ login

### 3) group
Dùng khi lane còn login nhưng group context chưa đúng hoặc chưa xác định.

- `group-mismatch`
  - đang ở sai group
- `group-state-unknown`
  - chưa xác định được group hiện tại
- `group-search-empty`
  - search không ra candidate phù hợp
- `group-opened-unverified`
  - click/mở group rồi nhưng chưa verify được header/context
- `reconnect-header-unverified`
  - reconnect click xong nhưng chưa verify được header

### 4) error
Dùng cho lỗi hệ thống/check tổng quát.

- `status-check-error`
  - check status nổ lỗi ngoài các case phân loại ở trên

## Cách dùng trong code

### Recovery logic
- `qr-visible` -> login/QR recovery path
- `login-state-unknown` -> refresh/reclassify path
- `group-mismatch` -> reconnect về target group
- `group-state-unknown` -> reconnect + verify path

### Notify policy
Reason-aware notify nên khác nhau theo class:
- `qr-visible` -> alert kiểu cần khôi phục phiên/login
- `group-mismatch` -> alert kiểu lệch group/context
- `login-state-unknown` -> alert kiểu đang refresh để phân loại lại
- `group-state-unknown` -> alert kiểu reconnect vì context chưa rõ

### Fail artifacts
Khi fail path quan trọng xảy ra, artifact tối thiểu nên có:
- screenshot
- sidecar JSON
- current_url
- page_title
- phase
- reason
- group_name
- timestamp

## Quy ước đặt tên
- dùng kebab-case
- reason nên mô tả **state** hoặc **classification**, không phải cảm xúc/log text
- log message có thể tiếng Việt, nhưng `reason` nên ổn định và machine-friendly

## Ví dụ
### Ví dụ 1 — cần login lại
```json
{
  "logged_in": false,
  "in_group": false,
  "needs_qr": true,
  "reason": "qr-visible"
}
```

### Ví dụ 2 — login vẫn còn nhưng lệch group
```json
{
  "logged_in": true,
  "in_group": false,
  "needs_qr": false,
  "reason": "group-mismatch",
  "page_state": {
    "group_title": "Nhóm Khác",
    "target_group": "Nhóm Test"
  }
}
```

### Ví dụ 3 — trạng thái tốt
```json
{
  "logged_in": true,
  "in_group": true,
  "needs_qr": false,
  "reason": "ready-in-target-group"
}
```

## Rule thực dụng cho team
Nếu thêm reason mới, nên làm cùng lúc 4 việc:
1. thêm vào `src/utils/status_codes.py`
2. gắn vào recovery/notify path nếu liên quan
3. thêm regression test tương ứng
4. update file docs này nếu reason có ý nghĩa vận hành
