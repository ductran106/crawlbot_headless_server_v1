# Midnight finalize forensic note — 2026-03-21

## Symptom
At session rollover `20260320_P6 -> 20260321_P1`, logs showed:
- `SAVE_DOCUMENT_RESULT success=true`
- followed immediately by `NameError: build_save_document_notification is not defined`
- user did **not** receive the expected Telegram docx at midnight.

## Evidence
From overnight run `logs/overnight-run-20260320-221144.log`:
- `00:00:19` RET 2 saved `final_20260320_P6_duc-ProBook_ret_2_room_lich_388mess.docx`
- `00:00:52` RETURN saved `final_20260320_P6_duc-ProBook_return_room_lich_586mess.docx`
- immediately after each save: `Lỗi khi lưu tài liệu: name 'build_save_document_notification' is not defined`

## Root cause
`src/crawler/message_crawler.py::save_document()` called:
- `send_notification(build_save_document_notification(...))`
but did not import `build_save_document_notification` from `src/notification/messages.py`.

## Why Telegram docx was missing
The docx-send lane still exists downstream:
- `rotate_session_if_needed()` -> `self.docx_handler.process_docx_format(final_path)`
- `src/storage/docx_handler.py::process_docx_format()` -> `send_document(output_path, ...)`

Because `save_document()` raised before returning `final_path`, downstream format/send never ran.

## Fix
Commit `6fbab3b`:
- add `from ..notification.messages import build_save_document_notification`

## Quick recognition rule for future incidents
If you see this pattern:
- `SAVE_DOCUMENT_RESULT success=true`
- then a `NameError` in `save_document()`
- then no Telegram docx

=> suspect **post-save notification code path** broke, not raw file-save itself and not the downstream Telegram transport.
