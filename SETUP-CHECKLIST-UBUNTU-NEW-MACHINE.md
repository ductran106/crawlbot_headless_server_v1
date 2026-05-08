# Setup Checklist - Ubuntu New Machine (for `run-gui-session.sh`)

Mục tiêu: copy project này sang **máy Ubuntu mới có desktop GUI**, làm đúng checklist dưới đây là chạy được bằng `./run-gui-session.sh`.

## Project path chuẩn trong máy hiện tại

```bash
/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab-handoff-20260325-192029/crawlbot_portable_scheduler_lab
```

> Khi mang sang máy khác, có thể giải nén ở path khác. Chỉ cần `cd` đúng vào thư mục project sau giải nén.

---

## 1) Cài package hệ thống + Google Chrome

```bash
sudo apt update && sudo apt install -y \
  git curl wget unzip python3 python3-venv python3-pip python3-tk \
  ca-certificates fonts-liberation fonts-noto-color-emoji \
  libnss3 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 \
  libxss1 libxrandr2 libxdamage1 libxcomposite1 libxext6 libxfixes3 \
  libxi6 libxkbcommon0 libpangocairo-1.0-0 libx11-6 libx11-xcb1 \
  libxcb1 libgbm1 libgtk-3-0 libasound2

cd /tmp
wget -O google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb

google-chrome --version
```

---

## 2) Giải nén project và vào đúng thư mục

Ví dụ nếu anh copy file zip sang `~/Downloads`:

```bash
mkdir -p ~/ai-workspace/repos
cd ~/ai-workspace/repos
unzip ~/Downloads/crawlbot_portable_scheduler_Final_v1.zip
cd crawlbot_portable_scheduler_lab
pwd
ls -la
```

Phải thấy các file chính như:
- `run-gui-session.sh`
- `requirements.txt`
- `main.py`
- `README.md`

---

## 3) Tạo virtualenv + cài Python packages

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Kiểm tra:

```bash
./.venv/bin/python --version
```

---

## 4) Tạo file `.env`

```bash
cp .env.example .env
nano .env
```

### Tối thiểu cần điền / kiểm tra

```env
DATA_FOLDER=./data
CHROME_USER_DATA_DIR=./chrome_user_data
LOGS_FOLDER=./logs

TELEGRAM_TOKEN=...
ADMIN_CHAT_ID=...
ALERT_CHAT_ID=...

HEADLESS=false
```

Gợi ý:
- Nếu chạy bằng `run-gui-session.sh` với Chrome hiện giao diện thật, giữ `HEADLESS=false`.
- Nếu chưa có session Zalo, bot có thể yêu cầu đăng nhập lại / gửi QR tùy flow runtime.

---

## 5) Tạo thư mục runtime cần thiết

```bash
mkdir -p logs data chrome_user_data
chmod -R 755 logs data chrome_user_data
chmod +x run-gui-session.sh
```

---

## 6) Kiểm tra đang ở desktop GUI thật

```bash
echo "$DISPLAY"
echo "$XDG_SESSION_TYPE"
who
```

Kỳ vọng:
- `DISPLAY` có giá trị như `:0`
- session là `x11` hoặc `wayland`

Nếu `DISPLAY` trống thì thường là đang SSH/text-only, chưa nên chạy `run-gui-session.sh`.

---

## 7) Test Chrome GUI

```bash
google-chrome
```

Nếu Chrome mở bình thường, đóng lại rồi chạy bot.

---

## 8) Chạy bot bằng `run-gui-session.sh`

```bash
./run-gui-session.sh
```

---

## 9) Nếu muốn chạy nền

```bash
nohup ./run-gui-session.sh > logs/run-gui-session.log 2>&1 &
tail -f logs/run-gui-session.log
```

---

## 10) PASS nhanh sau khi chạy

Checklist quan sát nhanh:
- script không văng ngay
- Chrome mở được
- bot gửi startup/QR Telegram nếu cần
- vào được room
- tại boundary có file `final_...docx`
- có file `Lich_...docx`
- có log `Đã gửi file Telegram thành công`

---

## 11) 3 lỗi hay gặp

### A. `DISPLAY` trống / GUI env lỗi
Chạy lại từ terminal trong desktop session thật, không phải terminal SSH text-only.

### B. Chrome không mở được
Test riêng:

```bash
google-chrome
```

Sửa Chrome trước, rồi mới chạy bot.

### C. Telegram/QR không hoạt động
Kiểm tra lại `.env`:
- `TELEGRAM_TOKEN`
- `ADMIN_CHAT_ID`
- `ALERT_CHAT_ID`

---

## 12) Ghi chú đóng gói của file zip này

File `crawlbot_portable_scheduler_Final_v1.zip` được đóng theo hướng **portable sạch**:
- có source code
- có docs / notes / script chạy
- có `.env.example`
- **không** kèm `.venv`
- **không** kèm `.env`
- **không** kèm `logs/`, `data/`, `chrome_user_data/`

Lý do:
- giảm dung lượng
- tránh mang theo token / session / runtime state máy cũ
- cài mới trên máy đích sạch và ổn định hơn

---

## One-shot gần như full copy-paste

```bash
sudo apt update && sudo apt install -y \
  git curl wget unzip python3 python3-venv python3-pip python3-tk \
  ca-certificates fonts-liberation fonts-noto-color-emoji \
  libnss3 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 \
  libxss1 libxrandr2 libxdamage1 libxcomposite1 libxext6 libxfixes3 \
  libxi6 libxkbcommon0 libpangocairo-1.0-0 libx11-6 libx11-xcb1 \
  libxcb1 libgbm1 libgtk-3-0 libasound2 && \
cd /tmp && \
wget -O google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
sudo apt install -y ./google-chrome-stable_current_amd64.deb && \
mkdir -p ~/ai-workspace/repos && \
cd ~/ai-workspace/repos && \
unzip ~/Downloads/crawlbot_portable_scheduler_Final_v1.zip && \
cd crawlbot_portable_scheduler_lab && \
python3 -m venv .venv && \
source .venv/bin/activate && \
pip install --upgrade pip setuptools wheel && \
pip install -r requirements.txt && \
mkdir -p logs data chrome_user_data && \
chmod -R 755 logs data chrome_user_data && \
chmod +x run-gui-session.sh && \
cp .env.example .env && \
nano .env
```

Sau khi sửa `.env`:

```bash
cd ~/ai-workspace/repos/crawlbot_portable_scheduler_lab
./run-gui-session.sh
```
