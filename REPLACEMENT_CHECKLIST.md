# REPLACEMENT_CHECKLIST.md — Khi nào repo dev đủ điều kiện thay runtime copy trên farmbot

Mục tiêu: chỉ thay lane runtime copy hiện tại khi có đủ bằng chứng vận hành, không thay chỉ vì repo nhìn sạch hơn.

## Runtime copy hiện tại
- Path: `/home/farm4bot/work/crawlbot_portable_scheduler_headless_server_v1`
- Đây là lane đã có bằng chứng chạy thật trên farmbot
- Repo GitHub dev sạch hiện tại: `ductran106/crawlbot_headless_server_v1`

## Điều kiện tối thiểu trước khi thay

### 1) Source parity rõ ràng
- [ ] Repo dev có đầy đủ source, scripts, docs cần thiết để chạy headless
- [ ] `.gitignore` chặn đúng secrets/runtime artifacts
- [ ] Có `README.md`, `RUNBOOK.md`, `CONFIG_REFERENCE.md`
- [ ] Không còn mơ hồ file nào là entrypoint chính

### 2) Bring-up sạch trên một working copy mới
- [ ] Clone repo dev sạch sang một thư mục test mới trên farmbot
- [ ] Tạo `.venv` mới
- [ ] Tạo `.env` từ file example
- [ ] Reuse hoặc mount đúng `chrome_user_data` nếu cần giữ session Zalo
- [ ] Chạy được bằng `./run-headless-server.sh`

### 3) Smoke test pass
- [ ] Boot process thành công
- [ ] Telegram startup pass
- [ ] Vào được room thật
- [ ] Có `verify_mode=strong` hoặc `verify_mode=usable`
- [ ] Có `ROOM_SWITCH_TRACKER`
- [ ] Có `fairness scheduler:`

### 4) Boundary/output pass
- [ ] Save docx pass
- [ ] Format docx pass
- [ ] Gửi Telegram document pass
- [ ] Không có dấu hiệu mất boundary artifacts

### 5) Soak test đủ lâu
- [ ] 1-room soak pass
- [ ] 2-room soak pass
- [ ] Không crash bất thường trong khoảng soak đã chọn
- [ ] Không có bằng chứng miss tin rõ ràng trong cửa sổ test
- [ ] Recovery behavior chấp nhận được nếu browser rung

### 6) Vận hành/rollback rõ ràng
- [ ] Có lệnh chạy/dừng/xem log rõ ràng trong `RUNBOOK.md`
- [ ] Có backup path hoặc có thể quay lại runtime copy cũ nhanh
- [ ] Có kế hoạch rollback nếu repo dev lane mới fail sau cutover

## Tiêu chuẩn quyết định thay
Chỉ nên thay runtime copy hiện tại khi đồng thời đúng cả 3 điều:
1. repo dev chạy được trên working copy mới,
2. smoke + boundary pass,
3. soak đủ để tin rằng không kém lane runtime cũ.

## Cách rollout an toàn
1. Không đụng runtime copy cũ ngay
2. Clone repo dev sang path mới trên farmbot
3. Gắn `.env` và `chrome_user_data` phù hợp
4. Chạy soak trên path mới
5. Nếu pass ổn định, mới đổi path chuẩn vận hành
6. Giữ khả năng rollback về path cũ trong giai đoạn đầu

## Không nên làm
- Không cutover chỉ vì repo GitHub đã sạch
- Không xóa `chrome_user_data` nếu còn cần session Zalo đang sống
- Không assume headless lane mới sẽ ổn bằng lane cũ nếu chưa có soak evidence
