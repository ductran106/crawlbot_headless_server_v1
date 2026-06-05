"""Canonical message builders for Crawlbot notifications.

Giữ layer này nhỏ, pure, và không phụ thuộc transport để:
- gom wording/source-of-truth
- giảm string literal rải rác
- dễ test semantics
"""


def build_startup_notification() -> str:
    return "🚀 Hệ thống Zalo Crawler đã khởi động"


def build_alert_ready_notification() -> str:
    return "🔄 Bot cảnh báo đã sẵn sàng"


def build_webdriver_restart_notification() -> str:
    return "⚠️ Phát hiện lỗi WebDriver, đang khởi động lại toàn bộ..."


def build_login_qr_required_notification() -> str:
    return "🔐 Cần quét mã QR để đăng nhập Zalo (Mã QR có hiệu lực trong 60 giây)"


def build_login_success_notification() -> str:
    return "✅ Đăng nhập Zalo thành công!"


def build_login_timeout_notification() -> str:
    return "❌ Hết thời gian chờ đăng nhập Zalo"


def build_save_document_notification(group_name: str, message_count: int, file_name: str) -> str:
    return f"✅ ({group_name}) Đã lưu {int(message_count)} tin nhắn vào file {file_name}"


def build_docx_processed_notification() -> str:
    return "✅ Đã xử lý xong file Word, chuẩn bị gửi file"
