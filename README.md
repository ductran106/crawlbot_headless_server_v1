# Crawlbot

Crawler Zalo Web dùng Selenium để theo dõi/crawl tin nhắn nhóm, autosave ra DOCX và gửi cảnh báo qua Telegram.

## Trạng thái cleanup
- Đã chuẩn hóa dependency runtime cơ bản
- Đã thêm `.gitignore` để tránh commit data/profile/secrets
- Đã thêm `run.sh` để ép chạy đúng `.venv`
- Không thay đổi flow runtime của tiến trình đang chạy

## Chạy đúng cách
```bash
cd /home/duc/crawlbot
python3 -m venv .venv   # nếu chưa có
. .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

## File quan trọng
- `main.py`: entrypoint chính
- `legacy/main1.py`: snapshot cũ để tham chiếu, không dùng để chạy runtime
- `src/`: source chính
- `.env.example`: mẫu cấu hình
- `chrome_user_data/`: profile Chrome runtime (không commit)
- `data/`: output crawl/runtime data (không commit)

## Lưu ý vận hành
- Không chạy bằng `python3 main.py` nếu chưa activate `.venv`
- Không commit `.env`, `chrome_user_data/`, `data/`
- Nếu đang có tiến trình chạy, sửa file source sẽ chỉ có hiệu lực sau lần restart tiếp theo
