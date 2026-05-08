# Hướng dẫn về vị trí lưu file

## 📁 Nơi lưu file DOCX

### Thư mục gốc
File docx được lưu vào thư mục được cấu hình trong `.env`:
- **Biến**: `DATA_FOLDER`
- **Mặc định** (nếu không set): `./data` (thư mục `data` trong project)

### Ví dụ trên Ubuntu:
```env
# Nếu dùng đường dẫn tương đối
DATA_FOLDER=./data

# Hoặc đường dẫn tuyệt đối
DATA_FOLDER=/opt/zalo/data
```

## 📄 Các loại file được tạo

> Hiện tại canonical repo dùng naming chuẩn theo `session_id + hostname + group_slug`.
> Với multi-room, file thường nằm trong thư mục riêng của từng room dưới `DATA_FOLDER/`.

### 1. File Autosave (tự động lưu định kỳ)
- **Tên file**: `autosave_{session_id}_{hostname}_{group_slug}.docx`
- **Ví dụ**: `autosave_20260319_P1_duc-ProBook_return_room_lich.docx`
- **Mục đích**: File tạm được lưu tự động mỗi `AUTOSAVE_INTERVAL` giây (mặc định 30s)
- **Vị trí**: `DATA_FOLDER/{group_slug}/`

### 2. File cuối cùng (raw, sau khi crawl xong)
- **Tên file**: `final_{session_id}_{hostname}_{group_slug}_{message_count}mess.docx`
- **Ví dụ**: `final_20260319_P1_duc-ProBook_return_room_lich_19mess.docx`
- **Mục đích**: File chính thức sau khi hoàn thành crawl cho room đó
- **Vị trí**: `DATA_FOLDER/{group_slug}/`

### 3. File đã xử lý (định dạng chuẩn / deliverable)
- **Tên file**: `Lich_{session_id}_{hostname}_{group_slug}_{message_count}mess_crawl.docx`
- **Ví dụ**: `Lich_20260319_P1_duc-ProBook_return_room_lich_19mess_crawl.docx`
- **Mục đích**: File đã được xử lý định dạng (thay `-` và `+` thành `_`, format lại...)
- **Vị trí**: `DATA_FOLDER/{group_slug}/` (cùng thư mục với file gốc)
- **Đặc biệt**: File này được **tự động gửi qua Telegram** sau khi xử lý xong

## 🔍 Cách kiểm tra file đã được tạo

### Trên Ubuntu Server:

```bash
# Xem tất cả file docx theo từng room
find data -type f -name '*.docx' | sort

# Xem file mới nhất
find data -type f -name '*.docx' -printf '%T@ %p\n' | sort -nr | head -5

# Xem chi tiết một file
file data/return_room_lich/final_20260319_P1_duc-ProBook_return_room_lich_19mess.docx
```

### Trong log:

Khi chạy, bạn sẽ thấy log như:
```
Đã tạo file autosave ban đầu: data/return_room_lich/autosave_20260319_P1_duc-ProBook_return_room_lich.docx
Đã lưu tài liệu cuối cùng: data/return_room_lich/final_20260319_P1_duc-ProBook_return_room_lich_19mess.docx với 19 tin nhắn
Đã hoàn thành xử lý định dạng file: data/return_room_lich/Lich_20260319_P1_duc-ProBook_return_room_lich_19mess_crawl.docx
```

## 📊 Cấu trúc thư mục DATA_FOLDER

```text
DATA_FOLDER/
├── return_room_lich/
│   ├── autosave_20260319_P1_duc-ProBook_return_room_lich.docx
│   ├── autosave_20260319_P1_duc-ProBook_return_room_lich.docx.backup
│   ├── autosave_20260319_P1_duc-ProBook_return_room_lich.docx.temp
│   ├── final_20260319_P1_duc-ProBook_return_room_lich_19mess.docx
│   └── Lich_20260319_P1_duc-ProBook_return_room_lich_19mess_crawl.docx
├── ret_2_room_lich/
│   └── ...
├── logs/                     # Log chạy + log lỗi + cấu trúc Zalo
│   ├── *.log                 # Log phiên (theo ngày/phiên/máy)
│   ├── errors/               # Log lỗi chi tiết (gửi cho dev khi cần sửa)
│   │   └── error_YYYY-MM-DD.log
│   ├── zalo_structure_*.md   # Cấu trúc trang Zalo (selectors, elements)
│   └── zalo_structure_*.json
├── ZaloQR/                   # Thư mục chứa QR code
│   ├── zalo_qr_*.png
│   └── zalo_qr_fullscreen_*.png
├── keywords.txt              # File từ khóa
└── zalo_messages.db          # Database SQLite
```

### Log lỗi (để gửi cho dev khi có lỗi)
- **Vị trí**: `DATA_FOLDER/logs/errors/error_YYYY-MM-DD.log`
- **Nội dung**: Mỗi lần có exception, full traceback + context (phase, group_name, ...) được ghi vào file theo ngày.
- **Cách dùng**: Khi gặp lỗi, gửi file `error_YYYY-MM-DD.log` (hoặc nội dung liên quan) cho dev để dễ sửa.

### Cấu trúc Zalo Web (để phát triển thêm tính năng)
- **Tạo file**: Chạy `python main.py --capture-structure` (mở Zalo, đăng nhập nếu cần, lưu cấu trúc rồi thoát).
- **Vị trí**: `DATA_FOLDER/logs/zalo_structure_YYYY-MM-DD_HH-MM-SS.md` và `.json`
- **Nội dung**: Bảng selectors đang dùng, số lượng element, mẫu thuộc tính; danh sách class có trên trang; thông tin body. Dùng khi muốn thêm tính năng mới (dev cần biết cấu trúc DOM Zalo Web).

## ✅ Xác nhận code chạy chuẩn

### Code đã được kiểm tra:
- ✅ Dùng `os.path.join()` → hoạt động tốt trên cả Windows và Linux
- ✅ Tự động tạo thư mục room nếu chưa tồn tại
- ✅ Tên file có session/host/room rõ ràng → dễ correlate với log
- ✅ File được gửi qua Telegram sau khi xử lý xong

### Kiểm tra nhanh:

1. **Kiểm tra thư mục tồn tại:**
```bash
find data -maxdepth 2 -type d | sort
```

2. **Kiểm tra quyền ghi:**
```bash
touch data/test.txt && rm data/test.txt
# Nếu không lỗi → có quyền ghi
```

3. **Kiểm tra file mới nhất:**
```bash
find data -type f -name '*.docx' -printf '%T@ %p\n' | sort -nr | head -1
```

## 🐛 Xử lý lỗi

### Nếu không thấy file:

1. **Kiểm tra log:**
```bash
tail -f logs/*.log | grep -E "autosave|Đã lưu tài liệu cuối cùng|Đã hoàn thành xử lý định dạng"
```

2. **Kiểm tra quyền thư mục:**
```bash
ls -ld data/
# Phải có quyền ghi (drwxrwxr-x hoặc tương tự)
```

3. **Kiểm tra cấu hình .env:**
```bash
grep DATA_FOLDER .env
```

4. **Tạo thư mục thủ công nếu cần:**
```bash
mkdir -p data
chmod 755 data
```

## 📱 File được gửi qua Telegram

Sau khi xử lý xong, file `Lich_*_crawl.docx` sẽ được **tự động gửi qua Telegram** đến:
- `ADMIN_CHAT_ID` (chat cá nhân)
- Kèm caption: `File Word đã xử lý xong - Phiên {final_file_name_without_ext}`

Nếu không nhận được file qua Telegram, kiểm tra:
- Token Telegram đúng chưa
- Bot có quyền gửi file không
- Xem log để biết lỗi cụ thể
