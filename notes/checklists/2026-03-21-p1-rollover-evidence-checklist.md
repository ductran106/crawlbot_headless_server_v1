# P1 rollover evidence checklist — 2026-03-21

Log target:
- `logs/restart-live-20260321-051454.log`

Expected boundary:
- around end of `20260321_P1` (~09:00 local)

## PASS checklist
- [ ] Có log đổi phiên: `Đổi phiên: 20260321_P1 -> ...`
- [ ] Có log save final raw: `Đã lưu tài liệu cuối cùng: ...final_20260321_P1_...docx`
- [ ] Có `SAVE_DOCUMENT_RESULT` với `success=true`
- [ ] Không có `build_save_document_notification is not defined`
- [ ] Có log format xong: `Đã hoàn thành xử lý định dạng file: ...Lich_...docx`
- [ ] Có log gửi Telegram file thành công: `Đã gửi file Telegram thành công: ...`

## FAIL signatures to watch
- [ ] `NameError` / `build_save_document_notification is not defined`
- [ ] `Lỗi khi lưu tài liệu`
- [ ] Có final raw nhưng không có `process_docx_format`
- [ ] Có format xong nhưng `Lỗi khi gửi file Telegram`
- [ ] Không tạo được `Lich_...docx`

## Artifact paths to check
- Raw final:
  - `data/return_room_lich/final_20260321_P1_...docx`
  - `data/ret_2_room_lich/final_20260321_P1_...docx`
- Formatted output:
  - `data/return_room_lich/Lich_20260321_P1_..._crawl.docx`
  - `data/ret_2_room_lich/Lich_20260321_P1_..._crawl.docx`
