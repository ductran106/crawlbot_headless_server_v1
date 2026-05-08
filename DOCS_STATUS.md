# DOCS_STATUS.md

Tài liệu nào nên đọc trước, tài liệu nào là historical/reference.

## Active / ưu tiên đọc trước
1. `README.md` — entry ngắn cho repo dev sạch
2. `RUNBOOK.md` — chạy/dừng/xem log lane farmbot runtime
3. `REPLACEMENT_CHECKLIST.md` — tiêu chuẩn để repo dev thay runtime copy trên farmbot
4. `README-HEADLESS-UBUNTU-SERVER.md` — bring-up headless trên Ubuntu server
5. `CONFIG_REFERENCE.md` — cấu hình `.env`
6. `ARCHITECTURE.md` — cấu trúc module/source

## Reference / đọc khi cần
- `TECHNIQUES.md` — giải thích kỹ thuật chi tiết hơn
- `FILE_LOCATION_GUIDE.md` — naming/path của docx, db, artifacts
- `SELECTORS_REFERENCE.md` — selector/debug reference
- `docs/` — notes/reference chuyên biệt
- `tests/` — bằng chứng regression/guardrails

## Historical / không nên dùng làm entrypoint chính
- `README-RUN-FIRST.md`
- `README-RUN-ON-NEW-MACHINE.md`
- `SETUP-CHECKLIST-UBUNTU-NEW-MACHINE.md`
- `NEW_PROJECT_GUIDE.md`
- `TIMEZONE_SETUP.md`
- `UBUNTU_SETUP.md`

Lý do: các file này chứa dấu vết của lane cũ, path cũ, hoặc packaging/handoff cũ. Giữ lại để tham khảo, nhưng không nên coi là source-of-truth đầu tiên cho repo dev sạch hiện tại.
