# P1 rollover PASS after fix — 2026-03-21

## Context
Follow-up verification after fixing the missing import for:
- `build_save_document_notification`
- fix commit: `6fbab3b`

Live run restarted on the patched code:
- log: `logs/restart-live-20260321-051454.log`

## Result
P1 -> P2 rollover passed for both rooms.

### RET 2 ROOM LỊCH
- `09:00:01` rollover detected: `20260321_P1 -> 20260321_P2`
- raw final saved:
  - `data/ret_2_room_lich/final_20260321_P1_duc-ProBook_ret_2_room_lich_326mess.docx`
- formatted output created:
  - `data/ret_2_room_lich/Lich_20260321_P1_duc-ProBook_ret_2_room_lich_326mess_crawl.docx`
- Telegram file send succeeded

### RETURN ROOM LỊCH
- `09:00:44` rollover detected: `20260321_P1 -> 20260321_P2`
- raw final saved:
  - `data/return_room_lich/final_20260321_P1_duc-ProBook_return_room_lich_940mess.docx`
- formatted output created:
  - `data/return_room_lich/Lich_20260321_P1_duc-ProBook_return_room_lich_940mess_crawl.docx`
- Telegram file send succeeded

## Key takeaway
The midnight regression was fixed as expected:
- `SAVE_DOCUMENT_RESULT success=true` still appears
- no `build_save_document_notification is not defined`
- downstream `process_docx_format(final_path)` and Telegram docx delivery resumed normally

## Remaining issue
This verification does **not** close the navigation/reconnect lane.
After rollover, the live run still shows repeated:
- `group-search-empty`
- `group-mismatch`
- `reconnect_verify_failed`
