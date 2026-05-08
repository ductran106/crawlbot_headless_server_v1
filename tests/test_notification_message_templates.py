from src.notification.messages import (
    build_alert_ready_notification,
    build_docx_processed_notification,
    build_login_qr_required_notification,
    build_login_success_notification,
    build_login_timeout_notification,
    build_save_document_notification,
    build_startup_notification,
    build_webdriver_restart_notification,
)


def test_core_notification_templates_are_stable():
    assert build_startup_notification() == "🚀 Hệ thống Zalo Crawler đã khởi động"
    assert build_alert_ready_notification() == "🔄 Bot cảnh báo đã sẵn sàng"
    assert build_webdriver_restart_notification() == "⚠️ Phát hiện lỗi WebDriver, đang khởi động lại toàn bộ..."
    assert build_login_qr_required_notification() == "🔐 Cần quét mã QR để đăng nhập Zalo (Mã QR có hiệu lực trong 60 giây)"
    assert build_login_success_notification() == "✅ Đăng nhập Zalo thành công!"
    assert build_login_timeout_notification() == "❌ Hết thời gian chờ đăng nhập Zalo"
    assert build_docx_processed_notification() == "✅ Đã xử lý xong file Word, chuẩn bị gửi file"


def test_save_document_notification_includes_group_count_and_filename():
    assert (
        build_save_document_notification("RETURN ROOM LỊCH", 19, "final_20260319_P1_duc-ProBook_return_room_lich_19mess.docx")
        == "✅ (RETURN ROOM LỊCH) Đã lưu 19 tin nhắn vào file final_20260319_P1_duc-ProBook_return_room_lich_19mess.docx"
    )
