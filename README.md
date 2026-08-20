# Gửi đoạn văn từ vựng vào Telegram, 7h sáng - 9h tối mỗi 2 tiếng — đảm bảo bao phủ hết cả sheet trong ngày

Script này đọc tab **Dictionary** trong Google Sheet của bạn, chọn 50 từ, nhờ
**Gemini AI (miễn phí)** viết thành 1 đoạn văn tiếng Anh tự nhiên lồng ghép
các từ đó, rồi gửi vào Telegram. Chạy tự động bằng GitHub Actions (miễn phí,
không cần giữ máy tính bật), **mỗi 2 tiếng 1 lần, chỉ trong khung giờ 7:00 -
21:00 giờ Việt Nam** (không gửi lúc nửa đêm/sáng sớm).

**Mỗi lần chạy gửi đúng 1 tin nhắn**: đoạn văn do AI viết, các từ vựng được
in đậm khi xuất hiện lần đầu. Nếu tin nhắn quá dài vượt giới hạn 4096 ký tự
của Telegram, nó sẽ tự tách thành nhiều tin liên tiếp — đây là giới hạn kỹ
thuật của Telegram, không phải script cố ý gửi nhiều tin.

Nếu vì lý do nào đó không gọi được Gemini (hết quota, lỗi mạng, server Google
quá tải...), script tự thử lại 3 lần; nếu vẫn thất bại, tin nhắn duy nhất đó
sẽ chuyển sang liệt kê tên 50 từ hôm nay (không có đoạn văn) thay vì bỏ lỡ
hoàn toàn ngày đó.

## Logic chọn từ (quan trọng)

Thay vì chọn hoàn toàn ngẫu nhiên mỗi lần (dễ bị sót từ, có từ không bao giờ
được ôn), script chia đều toàn bộ từ vựng cho các lần chạy trong khung giờ
hoạt động của ngày:

- Mỗi ngày, toàn bộ danh sách từ (lấy **trực tiếp, mới nhất** từ Google Sheet
  ngay tại thời điểm chạy — sheet có thể sửa/thêm/xoá bất cứ lúc nào, lần
  chạy kế tiếp sẽ tự cập nhật theo) được xáo trộn 1 lần duy nhất, dùng chính
  ngày hôm đó làm "seed" — nên mọi lần chạy trong cùng 1 ngày đều tính ra
  cùng 1 thứ tự xáo trộn (không cần lưu trạng thái ở đâu cả).
- Danh sách đó được chia đều thành N phần, N = số lần chạy trong khung giờ
  hoạt động (mặc định 7h-21h VN, cách nhau 2 tiếng = **8 lần/ngày**).
- Mỗi lần chạy chỉ "phụ trách" đúng 1 phần, dựa theo giờ hiện tại.
  → Sau đủ 8 lần chạy trong ngày, hợp của các phần = toàn bộ từ đang có
  trong sheet tại thời điểm đó, **không sót từ nào**.
- Nếu phần phụ trách ít hơn 50 từ (ví dụ sheet có 108 từ ÷ 8 lần ≈ 14 từ/lần),
  phần còn thiếu được bù ngẫu nhiên từ toàn bộ danh sách để đủ 50 từ mỗi tin.
- Tin nhắn sẽ có dòng đầu dạng `📚 Đợt 5/8 hôm nay — 50 từ — ...` để bạn biết
  đây là đợt thứ mấy trong ngày.

**Lưu ý**: vì sheet có thể đổi bất cứ lúc nào, cam kết "không sót từ" áp dụng
cho danh sách từ **tại thời điểm mỗi lần chạy**, không phải danh sách cố định
từ đầu ngày — đây là đánh đổi cần thiết để luôn phản ánh đúng sheet mới nhất
mà không cần lưu trạng thái ở đâu khác (ví dụ database riêng).

Nếu bạn đổi khung giờ hoạt động hoặc tần suất chạy trong `vocab.yml`, nhớ cập
nhật thêm các secret tương ứng cho khớp (xem bảng secrets bên dưới):
`RUN_INTERVAL_HOURS`, `ACTIVE_START_HOUR_UTC`, `ACTIVE_END_HOUR_UTC`.

## Tổng quan các bước

1. Tạo Telegram Bot + lấy Chat ID
2. Tạo Google Service Account + chia sẻ quyền đọc Sheet
3. Lấy Gemini API Key (miễn phí)
4. Đưa code này lên một GitHub repo
5. Khai báo 5 secret trong repo
6. Bật workflow — xong, cứ 2 tiếng bot sẽ tự gửi

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
3. Copy chuỗi API key hiện ra. **Lưu ý**: Google đang chuyển đổi định dạng
   key (key mới có thể bắt đầu bằng `AQ.Ab...` thay vì `AIzaSy...` như trước
   — cả hai đều là key hợp lệ, cứ copy dùng bình thường, không phải bạn tạo
   sai.
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
- Đổi model Gemini (nếu model mặc định bị Google ngừng hỗ trợ, sẽ báo lỗi
  `404 Not Found`; nếu model quá tải sẽ báo `503 Service Unavailable` trong
  log Actions — script tự thử lại 3 lần trước khi bỏ cuộc): thêm secret
  `GEMINI_MODEL`. Cách lấy tên model đang hoạt động thật: dán link sau vào
  trình duyệt (thay `YOUR_KEY` bằng Gemini API key của bạn):
  `https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY`
  Tìm các model có `"generateContent"` trong `supportedGenerationMethods`,
  copy phần tên sau `models/` (ví dụ `gemini-3.5-flash-lite`). Google đổi
  tên/rút model khá thường xuyên, nên đây là cách đáng tin cậy hơn đoán tên.
  Mặc định code hiện đang dùng `gemini-3.5-flash-lite` (đã thử lần lượt
  `gemini-2.5-flash` → lỗi 404 do đã ngừng hỗ trợ, `gemini-3.7-flash` → lỗi
  503 do model quá mới/quá tải; `gemini-3.5-flash-lite` là bản ổn định hơn).
- Đổi giờ chạy hoặc khung giờ hoạt động: sửa biểu thức cron trong `vocab.yml`
  (lưu ý: giờ cron là **giờ UTC**, Việt Nam là UTC+7 — trừ 7 tiếng để quy đổi
  giờ VN sang UTC). Ví dụ khung mặc định 7h-21h VN = 0h-14h UTC, cron là
  `"0 0,2,4,6,8,10,12,14 * * *"`. **Bắt buộc** thêm 3 secret sau cho khớp
  với cron mới, nếu không logic bao phủ cả ngày sẽ tính sai:
  - `RUN_INTERVAL_HOURS`: số tiếng giữa 2 lần chạy (mặc định `2`)
  - `ACTIVE_START_HOUR_UTC`: giờ UTC bắt đầu gửi (mặc định `0`)
  - `ACTIVE_END_HOUR_UTC`: giờ UTC kết thúc gửi, không tính giờ này
    (mặc định `15` — vì lần chạy cuối là 14h UTC, lần tiếp theo lẽ ra là 16h
    UTC nhưng bị loại vì `>= 15`)
- GitHub Actions có thể trễ vài phút so với lịch đặt khi hệ thống đông,
  đây là giới hạn của GitHub chứ không phải lỗi script (không ảnh hưởng tới
  việc bao phủ từ vựng, vì script tự khớp theo "khung giờ" 2 tiếng gần nhất
  chứ không cần đúng chính xác từng phút).
- Nếu bạn tự bấm **"Run workflow"** thủ công ngoài khung giờ đã đặt (để test
  lúc nửa đêm chẳng hạn), script vẫn chạy bình thường và không phá vỡ logic
  — chỉ là sẽ tính vào đúng 1 trong các phần đã chia của khung giờ đó thêm
  1 lần (không thiếu, không thừa về mặt bao phủ).

## Lưu ý bảo mật

- File JSON service account, Telegram token, và Gemini API key đều là thông
  tin nhạy cảm — chỉ nên lưu trong GitHub Secrets, **không** commit trực tiếp
  vào code, và **không** dán vào bất kỳ đâu khác (kể cả khi hỏi người khác
  cách sửa lỗi).
- Sheet chỉ cấp quyền **Viewer** cho service account là đủ, không cần Editor.
