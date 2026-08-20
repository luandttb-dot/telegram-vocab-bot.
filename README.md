# Gửi từ vựng ngẫu nhiên vào Telegram mỗi 2 tiếng

Script này đọc tab **Dictionary** trong Google Sheet của bạn, chọn ngẫu nhiên
50 từ, rồi gửi vào Telegram. Chạy tự động mỗi 2 tiếng bằng GitHub Actions
(miễn phí, không cần giữ máy tính bật).

## Tổng quan các bước

1. Tạo Telegram Bot + lấy Chat ID
2. Tạo Google Service Account + chia sẻ quyền đọc Sheet
3. Đưa code này lên một GitHub repo
4. Khai báo 4 secret trong repo
5. Bật workflow — xong, cứ 2 tiếng bot sẽ tự gửi

---

## 1. Tạo Telegram Bot

1. Mở Telegram, tìm **@BotFather**, bấm Start.
2. Gõ lệnh `/newbot`, đặt tên hiển thị và username (phải kết thúc bằng `bot`,
   ví dụ `vocab_reminder_bot`).
3. BotFather trả về một **token** dạng:
   `123456789:AAExampleTokenPleaseReplaceThis`
   → Lưu lại, đây là `TELEGRAM_BOT_TOKEN`.

## 2. Lấy Chat ID

1. Mở chat với bot vừa tạo, gửi bất kỳ tin nhắn nào (ví dụ "hi").
2. Trên trình duyệt, mở:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   (thay `<TOKEN>` bằng token ở bước 1)
3. Tìm đoạn `"chat":{"id":123456789, ...}` trong JSON trả về.
   → Số đó chính là `TELEGRAM_CHAT_ID`.

   Nếu muốn gửi vào một **group**, thêm bot vào group đó trước, gửi tin nhắn
   trong group rồi lặp lại bước 2 — chat_id của group thường là số âm
   (ví dụ `-1001234567890`).

## 3. Tạo Google Service Account (để đọc Sheet không cần đăng nhập thủ công)

1. Vào [Google Cloud Console](https://console.cloud.google.com/) → tạo project mới
   (hoặc chọn project có sẵn).
2. Vào **APIs & Services → Library**, tìm và bật **Google Sheets API**.
3. Vào **APIs & Services → Credentials → Create Credentials → Service account**.
   Đặt tên tuỳ ý, bấm Done.
4. Mở service account vừa tạo → tab **Keys → Add Key → Create new key → JSON**.
   File JSON sẽ tự tải về máy — **giữ bí mật file này**.
5. Mở file JSON, copy giá trị trường `"client_email"`
   (dạng `xxx@xxx.iam.gserviceaccount.com`).

## 4. Chia sẻ Google Sheet cho Service Account

1. Mở Google Sheet chứa tab Dictionary.
2. Bấm **Share**, dán email service account (bước 3.5) vào, chọn quyền
   **Viewer**, bấm Send.
3. Lấy `SPREADSHEET_ID`: là đoạn nằm giữa `/d/` và `/edit` trong URL của sheet.
   Ví dụ URL:
   `https://docs.google.com/spreadsheets/d/1mwEy0UM8EDIwxRvPMld06nu44IC9eC6nPctGtdNlw0E/edit`
   → `SPREADSHEET_ID = 1mwEy0UM8EDIwxRvPMld06nu44IC9eC6nPctGtdNlw0E`

## 5. Đưa code lên GitHub

1. Tạo repo mới trên GitHub (có thể để **Private**).
2. Upload toàn bộ nội dung thư mục này (`send_vocab.py`, `requirements.txt`,
   thư mục `.github/workflows/vocab.yml`, `README.md`) vào repo.

## 6. Khai báo Secrets

Vào repo → **Settings → Secrets and variables → Actions → New repository secret**,
tạo lần lượt 4 secret:

| Tên secret | Giá trị |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Dán **toàn bộ nội dung** file JSON tải ở bước 3.4 |
| `SPREADSHEET_ID` | ID lấy ở bước 4.3 |
| `TELEGRAM_BOT_TOKEN` | Token lấy ở bước 1.3 |
| `TELEGRAM_CHAT_ID` | Chat ID lấy ở bước 2.3 |

## 7. Chạy thử

Vào tab **Actions** của repo → chọn workflow **"Send Vocabulary to Telegram"**
→ bấm **Run workflow** để chạy thử ngay (không cần đợi lịch).
Nếu chạy thành công, bạn sẽ nhận được tin nhắn trong Telegram ngay sau đó.

Sau khi chạy thử ổn, workflow sẽ tự động chạy theo lịch **mỗi 2 tiếng** (dòng
`cron: "0 */2 * * *"` trong file `.github/workflows/vocab.yml`), không cần
làm gì thêm.

## Tuỳ chỉnh

- Đổi số từ mỗi lần gửi: thêm secret `NUM_WORDS` (ví dụ `30`).
- Đổi tên tab nếu không phải "Dictionary": thêm secret `SHEET_NAME`.
- Đổi giờ chạy: sửa biểu thức cron trong `vocab.yml`
  (lưu ý: giờ cron là **giờ UTC**, Việt Nam là UTC+7,
  ví dụ muốn chạy đúng 8h sáng giờ VN thì đặt cron là phút tương ứng 1h UTC).
- GitHub Actions có thể trễ vài phút so với lịch đặt khi hệ thống đông,
  đây là giới hạn của GitHub chứ không phải lỗi script.

## Lưu ý bảo mật

- File JSON service account và Telegram token đều là thông tin nhạy cảm —
  chỉ nên lưu trong GitHub Secrets, **không** commit trực tiếp vào code.
- Sheet chỉ cấp quyền **Viewer** cho service account là đủ, không cần Editor.
