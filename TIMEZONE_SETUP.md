# Hướng dẫn đổi Timezone trên Ubuntu Server

## 🕐 Vấn đề

Server đang ở múi giờ UTC (hoặc múi giờ khác) trong khi bạn muốn dùng múi giờ địa phương (UTC+7 - Việt Nam).

**Ví dụ**: Server hiển thị 5:19 nhưng thực tế là 12:19 (chênh lệch 7 giờ)

## ✅ Giải pháp 1: Đổi Timezone hệ thống (Khuyến nghị)

### Bước 1: Kiểm tra timezone hiện tại

```bash
# Xem timezone hiện tại
timedatectl

# Hoặc
date
```

### Bước 2: Xem danh sách timezone có sẵn

```bash
# Xem tất cả timezone
timedatectl list-timezones

# Tìm timezone Việt Nam
timedatectl list-timezones | grep -i "ho_chi_minh\|vietnam\|asia/ho_chi_minh"
```

Timezone Việt Nam thường là: `Asia/Ho_Chi_Minh`

### Bước 3: Đổi timezone

```bash
# Đổi sang timezone Việt Nam (UTC+7)
sudo timedatectl set-timezone Asia/Ho_Chi_Minh

# Xác nhận
timedatectl
date
```

### Bước 4: Kiểm tra lại

```bash
# Kiểm tra thời gian hiện tại
date

# Kiểm tra timezone
timedatectl status
```

**Kết quả mong đợi:**
```
               Local time: Tue 2026-01-28 12:19:00 +07
           Universal time: Tue 2026-01-28 05:19:00 UTC
                 RTC time: Tue 2026-01-28 05:19:00
                Time zone: Asia/Ho_Chi_Minh (+07, +0700)
```

## 🔧 Giải pháp 2: Đổi timezone bằng lệnh cũ (nếu timedatectl không có)

```bash
# Xem timezone hiện tại
cat /etc/timezone

# Đổi timezone
sudo ln -sf /usr/share/zoneinfo/Asia/Ho_Chi_Minh /etc/localtime

# Hoặc
echo "Asia/Ho_Chi_Minh" | sudo tee /etc/timezone
sudo dpkg-reconfigure -f noninteractive tzdata

# Kiểm tra
date
```

## 🐍 Giải pháp 3: Set timezone trong Python code (Nếu không muốn đổi hệ thống)

Nếu bạn không muốn đổi timezone của toàn hệ thống, có thể set trong code Python.

### Thêm vào file `.env`:

```env
# Timezone cho ứng dụng (ví dụ: Asia/Ho_Chi_Minh)
TIMEZONE=Asia/Ho_Chi_Minh
```

### Code sẽ tự động sử dụng timezone này (đã được cập nhật trong config.py)

## 📋 Các timezone phổ biến

| Quốc gia/Vùng | Timezone | UTC Offset |
|---------------|----------|------------|
| Việt Nam | `Asia/Ho_Chi_Minh` | UTC+7 |
| Thái Lan | `Asia/Bangkok` | UTC+7 |
| Singapore | `Asia/Singapore` | UTC+8 |
| Malaysia | `Asia/Kuala_Lumpur` | UTC+8 |
| Indonesia (Jakarta) | `Asia/Jakarta` | UTC+7 |
| Philippines | `Asia/Manila` | UTC+8 |

## ⚠️ Lưu ý quan trọng

1. **Sau khi đổi timezone, cần restart ứng dụng:**
   ```bash
   # Nếu chạy bằng systemd
   sudo systemctl restart zalo-crawler
   
   # Hoặc nếu chạy thủ công, dừng và chạy lại
   python main.py
   ```

2. **Kiểm tra log để xác nhận:**
   ```bash
   # Xem log với timestamp
   tail -f logs/*.log
   ```

3. **Ảnh hưởng đến file name:**
   - Tên file docx sẽ dùng thời gian mới
   - Session (P1-P6) sẽ được tính theo giờ địa phương

## 🧪 Test nhanh

```bash
# Test timezone trong Python
python3 -c "from datetime import datetime; import pytz; tz = pytz.timezone('Asia/Ho_Chi_Minh'); print(datetime.now(tz))"
```

## 📝 Xác nhận sau khi đổi

1. **Kiểm tra thời gian hệ thống:**
   ```bash
   date
   # Phải hiển thị đúng giờ địa phương
   ```

2. **Kiểm tra trong log:**
   ```bash
   # Chạy ứng dụng và xem log
   python main.py
   # Log phải hiển thị đúng giờ địa phương
   ```

3. **Kiểm tra tên file:**
   - File docx được tạo sẽ có timestamp đúng với giờ địa phương
   - Ví dụ: `01-28 1219_P3-hanauda.docx` (thay vì `01-28 0519_...`)
