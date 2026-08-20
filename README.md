# Gửi đoạn văn từ vựng vào Telegram mỗi 2 tiếng — đảm bảo bao phủ hết cả sheet trong ngày

Script này đọc tab **Dictionary** trong Google Sheet của bạn, chọn 50 từ, nhờ
**Gemini AI (miễn phí)** viết thành 1 đoạn văn tiếng Anh tự nhiên lồng ghép
các từ đó, rồi gửi vào Telegram kèm bảng nghĩa/ví dụ để tra cứu. Chạy tự động
mỗi 2 tiếng bằng GitHub Actions (miễn phí, không cần giữ máy tính bật).

Mỗi lần chạy sẽ gửi (2-3 tin nhắn):
1. **Đoạn văn** do AI viết, các từ vựng được in đậm (`*từ*`) khi xuất hiện lần đầu.
2. *(nếu có)* Cảnh báo ngắn nếu AI vô tình bỏ sót vài từ trong đoạn văn — để
   bạn vẫn biết đủ 50 từ hôm nay là những từ nào (không phá vỡ cam kết bao
   phủ cả ngày ở phần dưới).
3. **Bảng nghĩa & ví dụ** của cả 50 từ, để tra cứu nhanh.

Nếu vì lý do nào đó không gọi được Gemini (hết quota, lỗi mạng...), script tự
động chuyển về gửi dạng danh sách từ + nghĩa (không có đoạn văn) thay vì bỏ
lỡ hoàn toàn — bạn vẫn nhận được từ vựng hôm đó.

## Logic chọn từ (quan trọng)

Thay vì chọn hoàn toàn ngẫu nhiên mỗi lần (dễ bị sót từ, có từ không bao giờ
được ôn), script chia đều toàn bộ từ vựng cho các lần chạy trong ngày:

- Mỗi ngày (theo giờ UTC), toàn bộ danh sách từ được xáo trộn 1 lần duy nhất,
  dùng chính ngày hôm đó làm "seed" — nên mọi lần chạy trong cùng 1 ngày đều
  tính ra cùng 1 thứ tự xáo trộn (không cần lưu trạng thái ở đâu cả).
- Danh sách đó được chia đều thành N phần, N = số lần chạy trong ngày
  (mặc định 24 giờ / 2 tiếng = 12 lần).
- Mỗi lần chạy chỉ "phụ trách" đúng 1 phần, dựa theo giờ UTC hiện tại.
  → Sau 12 lần chạy trong ngày, hợp của các phần = toàn bộ từ trong sheet,
  **không sót từ nào**.
- Nếu phần phụ trách ít hơn 50 từ (ví dụ sheet có 108 từ ÷ 12 lần ≈ 9 từ/lần),
  phần còn thiếu được bù ngẫu nhiên từ toàn bộ danh sách để đủ 50 từ mỗi tin.
- Tin nhắn sẽ có dòng đầu dạng `📚 Đợt 5/12 hôm nay — 50 từ — ...` để bạn biết
  đây là đợt thứ mấy trong ngày.

**Lưu ý**: "ngày" ở đây tính theo giờ UTC (giờ Việt Nam = UTC+7, nên 1 "ngày"
của hệ thống sẽ lệch 7 tiếng so với nửa đêm giờ VN — không ảnh hưởng gì đến
việc bao phủ từ vựng, chỉ là mốc tính ngày khác giờ VN một chút). Nếu bạn đổi
tần suất chạy trong `vocab.yml` (ví dụ mỗi 3 tiếng thay vì 2), nhớ cập nhật
thêm secret `RUN_INTERVAL_HOURS` cho khớp (xem bảng secrets bên dưới).

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

## 4.5. Lấy Gemini API Key (miễn phí — dùng để viết đoạn văn)

1. Vào **https://aistudio.google.com/apikey** (đăng nhập bằng tài khoản Google
   bất kỳ, có thể dùng chung tài khoản đã tạo Service Account ở trên).
2. Bấm **"Create API key"** → chọn hoặc tạo 1 project bất kỳ khi được hỏi.
3. Copy chuỗi API key hiện ra (dạng `AIzaSy...`).
4. Đây là **hoàn toàn miễn phí, không cần thẻ tín dụng** — Google giới hạn số
   request/ngày cho gói free, nhưng script chỉ gọi 12 lần/ngày (mỗi 2 tiếng)
   nên nằm rất xa giới hạn đó, không lo bị tính phí hay hết quota.
5. Giữ bí mật key này giống như token Telegram — sẽ dán vào GitHub Secret ở
   bước sau (`GEMINI_API_KEY`).

## 5. Đưa code lên GitHub

1. Tạo repo mới trên GitHub (có thể để **Private**).
2. Upload toàn bộ nội dung thư mục này (`send_vocab.py`, `requirements.txt`,
   thư mục `.github/workflows/vocab.yml`, `README.md`) vào repo.

## 6. Khai báo Secrets

Vào repo → **Settings → Secrets and variables → Actions → New repository secret**,
tạo lần lượt 5 secret:

| Tên secret | Giá trị |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Dán **toàn bộ nội dung** file JSON tải ở bước 3.4 |
| `SPREADSHEET_ID` | ID lấy ở bước 4.3 |
| `TELEGRAM_BOT_TOKEN` | Token lấy ở bước 1.3 |
| `TELEGRAM_CHAT_ID` | Chat ID lấy ở bước 2.3 |
| `GEMINI_API_KEY` | API key lấy ở bước 4.5 |

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
- Đổi model Gemini (nếu model mặc định bị Google ngừng hỗ trợ): thêm secret
  `GEMINI_MODEL` (ví dụ `gemini-flash-latest`). Xem danh sách model hiện có
  tại https://ai.google.dev/gemini-api/docs/models.
- Đổi giờ chạy: sửa biểu thức cron trong `vocab.yml`
  (lưu ý: giờ cron là **giờ UTC**, Việt Nam là UTC+7,
  ví dụ muốn chạy đúng 8h sáng giờ VN thì đặt cron là phút tương ứng 1h UTC).
  **Nếu đổi từ "mỗi 2 tiếng" sang tần suất khác** (ví dụ mỗi 3 tiếng:
  `"0 */3 * * *"`), phải thêm secret `RUN_INTERVAL_HOURS` = `3` để script tự
  tính lại số lần chạy/ngày cho đúng — nếu không, logic bao phủ cả ngày sẽ
  tính sai.
- GitHub Actions có thể trễ vài phút so với lịch đặt khi hệ thống đông,
  đây là giới hạn của GitHub chứ không phải lỗi script (không ảnh hưởng tới
  việc bao phủ từ vựng, vì script tự khớp theo "khung giờ" 2 tiếng gần nhất
  chứ không cần đúng chính xác từng phút).
- Nếu bạn tự bấm **"Run workflow"** thủ công ngoài giờ lịch (để test), script
  vẫn chạy bình thường và không phá vỡ logic — chỉ là sẽ gửi lại đúng phần
  của khung giờ hiện tại thêm 1 lần (không thiếu, không thừa về mặt bao phủ).

## Lưu ý bảo mật

- File JSON service account và Telegram token đều là thông tin nhạy cảm —
  chỉ nên lưu trong GitHub Secrets, **không** commit trực tiếp vào code.
- Sheet chỉ cấp quyền **Viewer** cho service account là đủ, không cần Editor.
