# src/notification/telegram.py
import asyncio
import io
import telegram as tg  # Import thư viện với tên khác để tránh circular import
from ..utils.logger import log, logging
from ..utils.config import TELEGRAM_TOKEN, ADMIN_CHAT_ID, ALERT_CHAT_ID, COMPUTER_NAME

_TELEGRAM_CONFIG_WARNED = set()

def _telegram_is_configured(chat_id, *, context="telegram") -> bool:
    """Tránh ném exception liên tục khi thiếu cấu hình Telegram."""
    if not TELEGRAM_TOKEN:
        key = (context, "missing_token")
        if key not in _TELEGRAM_CONFIG_WARNED:
            log(f"Bỏ gửi {context}: thiếu TELEGRAM_TOKEN", level=logging.WARNING)
            _TELEGRAM_CONFIG_WARNED.add(key)
        return False
    if not chat_id:
        key = (context, "missing_chat_id")
        if key not in _TELEGRAM_CONFIG_WARNED:
            log(f"Bỏ gửi {context}: thiếu chat_id (ADMIN_CHAT_ID/ALERT_CHAT_ID)", level=logging.WARNING)
            _TELEGRAM_CONFIG_WARNED.add(key)
        return False
    return True

# Function to send telegram notification
async def send_telegram_notification_async(message, chat_id=None):
    """Gửi thông báo Telegram (async version)"""
    if not chat_id:
        chat_id = ADMIN_CHAT_ID
    
    try:
        if not _telegram_is_configured(chat_id, context="telegram_notification"):
            return False

        log(f"TELEGRAM: Đang gửi tin nhắn đến chat_id {chat_id}: {message}")

        # Thêm tên máy tính vào cuối tin nhắn
        message = f"{message}\n\n[Máy: {COMPUTER_NAME}]"
        
        bot = tg.Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=chat_id, text=message)
        log("Đã gửi thông báo Telegram thành công")
        return True
    except Exception as e:
        log(f"Lỗi kết nối Telegram: {str(e)}", level=logging.ERROR)
        return False

# Send notification wrapper
def send_notification(message, chat_id=None):
    """Wrapper không đồng bộ cho hàm gửi thông báo"""
    try:
        try:
            loop = asyncio.get_running_loop()
            # Nếu đã có loop đang chạy, tạo task mới
            future = asyncio.run_coroutine_threadsafe(
                send_telegram_notification_async(message, chat_id), loop
            )
            return True
        except RuntimeError:
            # Không có loop đang chạy, dùng asyncio.run()
            return asyncio.run(send_telegram_notification_async(message, chat_id))
    except Exception as e:
        log(f"Lỗi khi gửi thông báo: {str(e)}", level=logging.ERROR)
        return False

# Các loại thông báo
async def send_alert_message_async(message, chat_id=None):
    """Gửi thông báo cảnh báo qua Telegram"""
    if not chat_id:
        chat_id = ALERT_CHAT_ID  # Sử dụng ALERT_CHAT_ID thay vì ADMIN_CHAT_ID

    if not _telegram_is_configured(chat_id, context="telegram_alert"):
        return False

    formatted_message = f"⚠️: {message}"
    log(formatted_message, level=logging.WARNING)

    return await send_telegram_notification_async(formatted_message, chat_id)

async def send_error_message_async(message, chat_id=None):
    """Gửi thông báo lỗi qua Telegram"""
    if not chat_id:
        chat_id = ADMIN_CHAT_ID
    
    formatted_message = f"❌ LỖI: {message}"
    log(formatted_message, level=logging.ERROR)
    
    return await send_telegram_notification_async(formatted_message, chat_id)

# Send alert message
def send_alert(message, chat_id=None):
    """Wrapper không đồng bộ cho hàm gửi thông báo cảnh báo.

    Nếu Telegram chưa được cấu hình thì degrade sạch, không giả thành công.
    """
    if not chat_id:
        chat_id = ALERT_CHAT_ID

    if not _telegram_is_configured(chat_id, context="telegram_alert"):
        return False

    log(f"Xếp hàng gửi cảnh báo Telegram đến chat_id {chat_id}", level=logging.INFO)

    try:
        import threading

        def send_message_in_thread():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(send_alert_message_async(message, chat_id))
                log(f"Kết quả gửi cảnh báo trong thread: {result}", level=logging.INFO)
                new_loop.close()
            except Exception as thread_error:
                log(f"Lỗi trong thread gửi cảnh báo: {str(thread_error)}", level=logging.ERROR)

        t = threading.Thread(target=send_message_in_thread)
        t.daemon = True
        t.start()
        return True

    except Exception as e:
        log(f"Lỗi khi gửi thông báo cảnh báo: {str(e)}", level=logging.ERROR)
        return False

# Send error message
def send_error(message, chat_id=None):
    """Wrapper không đồng bộ cho hàm gửi thông báo lỗi"""
    try:
        try:
            loop = asyncio.get_running_loop()
            # Nếu đã có loop đang chạy, tạo task mới
            future = asyncio.run_coroutine_threadsafe(
                send_error_message_async(message, chat_id), loop
            )
            return True
        except RuntimeError:
            # Không có loop đang chạy, dùng asyncio.run()
            return asyncio.run(send_error_message_async(message, chat_id))
    except Exception as e:
        log(f"Lỗi khi gửi thông báo lỗi: {str(e)}", level=logging.ERROR)
        return False

# Gửi hình ảnh qua Telegram
async def send_image_notification_async(image_data, caption=None, chat_id=None):
    """Gửi hình ảnh qua Telegram"""
    if not chat_id:
        chat_id = ADMIN_CHAT_ID
    
    if caption:
        log(f"TELEGRAM IMAGE: {caption}")
    else:
        log("TELEGRAM IMAGE: [Không có chú thích]")
    
    try:
        if not _telegram_is_configured(chat_id, context="telegram_image"):
            return False

        bot = tg.Bot(token=TELEGRAM_TOKEN)
        
        if isinstance(image_data, io.BytesIO):
            # Đảm bảo con trỏ đang ở đầu file
            image_data.seek(0)
            await bot.send_photo(chat_id=chat_id, photo=image_data, caption=caption)
        elif isinstance(image_data, str) and (image_data.startswith('http://') or image_data.startswith('https://')):
            await bot.send_photo(chat_id=chat_id, photo=image_data, caption=caption)
        else:
            log(f"Không hỗ trợ định dạng hình ảnh: {type(image_data)}", level=logging.ERROR)
            return False
        
        log("Đã gửi hình ảnh Telegram thành công")
        return True
    except Exception as e:
        log(f"Lỗi khi gửi hình ảnh qua Telegram: {str(e)}", level=logging.ERROR)
        return False

def send_image_notification(image_data, caption=None, chat_id=None):
    """Wrapper cho hàm gửi hình ảnh"""
    try:
        try:
            loop = asyncio.get_running_loop()
            # Nếu đã có loop đang chạy, tạo task mới
            future = asyncio.run_coroutine_threadsafe(
                send_image_notification_async(image_data, caption, chat_id), loop
            )
            return True
        except RuntimeError:
            # Không có loop đang chạy, dùng asyncio.run()
            return asyncio.run(send_image_notification_async(image_data, caption, chat_id))
    except Exception as e:
        log(f"Lỗi khi gửi hình ảnh: {str(e)}", level=logging.ERROR)
        return False

# Hàm tiện ích để kiểm tra kết nối
async def test_telegram_connection_async():
    """Kiểm tra kết nối đến Telegram API"""
    try:
        if not TELEGRAM_TOKEN:
            log("Không thể kiểm tra Telegram: thiếu TELEGRAM_TOKEN", level=logging.WARNING)
            return False

        bot = tg.Bot(token=TELEGRAM_TOKEN)
        bot_info = await bot.get_me()
        log(f"Kết nối Telegram thành công! Bot: @{bot_info.username}")
        return True
    except Exception as e:
        log(f"Lỗi khi kiểm tra kết nối Telegram: {str(e)}", level=logging.ERROR)
        return False

# Wrapper cho hàm test kết nối
def check_telegram_connection():
    """Wrapper cho hàm kiểm tra kết nối Telegram"""
    try:
        try:
            loop = asyncio.get_running_loop()
            future = asyncio.run_coroutine_threadsafe(
                test_telegram_connection_async(), loop
            )
            return future.result(timeout=10)  # Đợi kết quả với timeout 10 giây
        except RuntimeError:
            return asyncio.run(test_telegram_connection_async())
    except Exception as e:
        log(f"Lỗi khi kiểm tra kết nối: {str(e)}", level=logging.ERROR)
        return False

# Hàm tương thích ngược với phiên bản cũ
def send_telegram_notification(message, chat_id=None):
    """Hàm tương thích với phiên bản cũ - chuyển tiếp đến send_notification"""
    return send_notification(message, chat_id)

# Thêm vào file src/notification/telegram.py
async def send_document_async(file_path, caption=None, chat_id=None):
    """Gửi file tài liệu qua Telegram"""
    import telegram as tg
    from ..utils.config import TELEGRAM_TOKEN
    
    if not chat_id:
        from ..utils.config import ADMIN_CHAT_ID
        chat_id = ADMIN_CHAT_ID
    
    if caption:
        log(f"TELEGRAM DOCUMENT: {caption} - File: {file_path}")
    else:
        log(f"TELEGRAM DOCUMENT: Đang gửi file {file_path}")
    
    try:
        if not _telegram_is_configured(chat_id, context="telegram_document"):
            return False

        bot = tg.Bot(token=TELEGRAM_TOKEN)
        
        # Mở file để gửi
        with open(file_path, 'rb') as document:
            # Lấy tên file từ đường dẫn
            import os
            file_name = os.path.basename(file_path)
            
            # Gửi file
            message = await bot.send_document(
                chat_id=chat_id,
                document=document,
                filename=file_name,
                caption=caption
            )
            
        log(f"Đã gửi file {file_path} qua Telegram thành công")
        return True
    except Exception as e:
        log(f"Lỗi khi gửi file qua Telegram: {str(e)}", level=logging.ERROR)
        return False

def send_document(file_path, caption=None, chat_id=None):
    """Wrapper cho hàm gửi file tài liệu"""
    try:
        try:
            loop = asyncio.get_running_loop()
            # Nếu đã có loop đang chạy, tạo task mới
            future = asyncio.run_coroutine_threadsafe(
                send_document_async(file_path, caption, chat_id), loop
            )
            return True
        except RuntimeError:
            # Không có loop đang chạy, dùng asyncio.run()
            return asyncio.run(send_document_async(file_path, caption, chat_id))
    except Exception as e:
        log(f"Lỗi khi gửi file: {str(e)}", level=logging.ERROR)
        return False