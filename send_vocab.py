"""
Gửi từ vựng vào Telegram: mỗi lần chạy gửi 2 tin nhắn liên tiếp — TIẾNG VIỆT
trước (bản dịch đoạn văn), rồi đến TIẾNG ANH (đoạn văn gốc, từ vựng in đậm).

LOGIC "BAO PHỦ CẢ NGÀY" (trong khung giờ hoạt động):
- Chỉ chạy trong khung giờ hoạt động mỗi ngày (mặc định 7:00 - 22:00 giờ
  Việt Nam = 00:00 - 15:00 UTC), cách nhau RUN_INTERVAL_HOURS tiếng.
- Trong khung giờ đó, toàn bộ từ vựng (lấy TRỰC TIẾP, MỚI NHẤT từ Google
  Sheet mỗi lần chạy — nếu bạn thêm/sửa/xoá từ trong sheet, lần chạy kế
  tiếp sẽ tự cập nhật theo) được xáo trộn 1 lần duy nhất mỗi ngày (seed =
  ngày hôm đó), rồi chia đều cho các lần chạy trong khung giờ đó. Mỗi lần
  chạy "phụ trách" đúng 1 phần -> sau khi hết khung giờ hoạt động trong
  ngày, toàn bộ từ hiện có trong sheet đều đã được gửi ít nhất 1 lần.
- Vì sheet có thể thay đổi bất cứ lúc nào, cam kết "không sót từ" áp dụng
  cho danh sách từ TẠI THỜI ĐIỂM mỗi lần chạy, không phải danh sách cố định
  từ đầu ngày.

MỖI LẦN CHẠY GỬI 2 TIN NHẮN (không header/emoji, không ghi chú gì thêm):
1. Bản dịch tiếng Việt của đoạn văn (văn xuôi thuần Việt, không bôi đậm).
2. Đoạn văn tiếng Anh gốc, các từ vựng được bôi đậm *từ* khi xuất hiện lần đầu.
- Gọi Gemini API (miễn phí, xem README.md) 1 lần duy nhất để lấy cả 2 bản,
  yêu cầu trả về dạng JSON để tách chính xác từng phần.
- Nếu gọi AI thất bại hoàn toàn (hết quota, lỗi mạng, JSON không đọc được
  sau khi đã thử lại...), CHỈ gửi đúng 1 tin nhắn duy nhất là chữ "AI False"
  — KHÔNG BAO GIỜ gửi kèm danh sách 50 từ thay thế. Chi tiết lỗi cụ thể chỉ
  in trong log của GitHub Actions để debug, không gửi vào Telegram.
- Tin nhắn dài hơn giới hạn 4096 ký tự của Telegram sẽ tự tách làm nhiều
  tin liên tiếp — đây là yêu cầu kỹ thuật bắt buộc của Telegram.

Cần các biến môi trường (đặt làm GitHub Actions Secrets, xem README.md):
- GOOGLE_SERVICE_ACCOUNT_JSON : toàn bộ nội dung file JSON service account
- SPREADSHEET_ID              : ID của Google Sheet (nằm giữa /d/ và /edit trên URL)
- TELEGRAM_BOT_TOKEN          : token của bot, lấy từ @BotFather
- TELEGRAM_CHAT_ID            : id của chat/user nhận tin nhắn
- GEMINI_API_KEY              : API key miễn phí từ Google AI Studio (để viết đoạn văn)
- SHEET_NAME                  : (tuỳ chọn) tên tab, mặc định "Dictionary"
- NUM_WORDS                   : (tuỳ chọn) số từ mỗi lần gửi, mặc định 50
- RUN_INTERVAL_HOURS          : (tuỳ chọn) số tiếng giữa 2 lần chạy, mặc định 2
- ACTIVE_START_HOUR_UTC       : (tuỳ chọn) giờ UTC bắt đầu gửi, mặc định 0 (=7h sáng giờ VN)
- ACTIVE_END_HOUR_UTC         : (tuỳ chọn) giờ UTC kết thúc gửi (không tính), mặc định 15 (=22h tối giờ VN)
- GEMINI_MODEL                : (tuỳ chọn) model Gemini, mặc định "gemini-3.5-flash-lite"
"""

import json
import math
import os
import random
import time
from datetime import datetime, timezone

import requests
from google.oauth2.service_account import Credentials
import gspread

GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEET_NAME = os.environ.get("SHEET_NAME", "Dictionary")
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
NUM_WORDS = int(os.environ.get("NUM_WORDS", "50"))
RUN_INTERVAL_HOURS = int(os.environ.get("RUN_INTERVAL_HOURS", "2"))
ACTIVE_START_HOUR_UTC = int(os.environ.get("ACTIVE_START_HOUR_UTC", "0"))   # 7:00 giờ VN
ACTIVE_END_HOUR_UTC = int(os.environ.get("ACTIVE_END_HOUR_UTC", "15"))     # 22:00 giờ VN
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

TELEGRAM_MAX_LEN = 3800  # để dư so với giới hạn 4096 ký tự của Telegram


def get_words():
    """Đọc toàn bộ từ vựng từ tab Dictionary trên Google Sheet (luôn mới nhất)."""
    creds_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(SHEET_NAME)
    records = ws.get_all_records()  # dùng hàng đầu tiên làm header

    words = []
    for row in records:
        word = str(row.get("Word", "")).strip()
        if not word:
            continue
        words.append(
            {
                "word": word,
                "meaning": str(row.get("Meaning", "")).strip(),
                "example": str(row.get("Example", "")).strip(),
            }
        )
    return words


def pick_words_for_this_run(words, now=None):
    """
    Chọn danh sách từ để gửi trong lần chạy này, đảm bảo:
    - Toàn bộ `words` (tại thời điểm gọi) được bao phủ hết trong khung giờ
      hoạt động của 1 ngày (qua các lần chạy khác nhau)
    - Mỗi tin nhắn vẫn có đúng NUM_WORDS từ (nếu đủ dữ liệu)

    Trả về: (final_list, slot_index, runs_per_day, guaranteed_count)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    window_hours = max(RUN_INTERVAL_HOURS, ACTIVE_END_HOUR_UTC - ACTIVE_START_HOUR_UTC)
    runs_per_day = max(1, math.ceil(window_hours / RUN_INTERVAL_HOURS))
    slot_index = ((now.hour - ACTIVE_START_HOUR_UTC) // RUN_INTERVAL_HOURS) % runs_per_day
    today_str = now.strftime("%Y-%m-%d")

    sorted_words = sorted(words, key=lambda w: w["word"].lower())

    daily_shuffled = sorted_words[:]
    random.Random(today_str).shuffle(daily_shuffled)

    n = len(daily_shuffled)
    chunk_size = math.ceil(n / runs_per_day) if n else 0
    start = slot_index * chunk_size
    end = start + chunk_size
    guaranteed = daily_shuffled[start:end]
    guaranteed_ids = {id(w) for w in guaranteed}

    if len(guaranteed) >= NUM_WORDS:
        final_list = guaranteed[:]
    else:
        remaining_pool = [w for w in words if id(w) not in guaranteed_ids]
        need = min(NUM_WORDS - len(guaranteed), len(remaining_pool))
        filler = random.sample(remaining_pool, need) if need > 0 else []
        final_list = guaranteed + filler

    random.shuffle(final_list)
    return final_list, slot_index, runs_per_day, len(guaranteed)


def _extract_json_object(text):
    """Cắt phần JSON object ra khỏi text (phòng khi AI lỡ thêm ```json fences
    hoặc chữ thừa trước/sau)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Không tìm thấy JSON object hợp lệ trong phản hồi.")
    return text[start : end + 1]


def generate_bilingual_paragraph(sample, max_retries=3):
    """
    Gọi Gemini API 1 lần để lấy đồng thời:
    - Đoạn văn tiếng Anh lồng ghép toàn bộ từ trong `sample`, bôi đậm *từ*
      khi xuất hiện lần đầu.
    - Bản dịch tiếng Việt tự nhiên của chính đoạn văn đó (không bôi đậm).
    Tự động thử lại tối đa `max_retries` lần nếu gặp lỗi tạm thời từ server
    Google (503 quá tải, 429 quá nhiều request, lỗi mạng, hoặc JSON trả về
    không hợp lệ), có chờ tăng dần giữa các lần thử (1s, 2s, 4s...).
    Trả về (english_text, vietnamese_text).
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("Chưa cấu hình GEMINI_API_KEY.")

    word_list_str = ", ".join(f'"{w["word"]}"' for w in sample)
    prompt = (
        "You are helping a Vietnamese learner study English vocabulary.\n"
        "Step 1: Write ONE flowing, coherent English paragraph (250-450 words) — "
        "a short story or realistic scenario — that naturally uses EVERY single "
        "item in the following vocabulary list at least once. Use each item's "
        "EXACT wording given (you may only change verb tense/grammatical form "
        "when strictly needed, but keep the core wording recognizable). The "
        "very first time each item appears, wrap it in single asterisks like "
        "*this*. Do not use asterisks for anything else.\n"
        "Step 2: Translate that exact English paragraph into natural, fluent "
        "Vietnamese (translate the meaning naturally, not word-by-word). Do NOT "
        "use asterisks or any special formatting in the Vietnamese translation.\n\n"
        "Respond with ONLY a single valid JSON object (no markdown code fences, "
        "no extra commentary before or after), in exactly this shape:\n"
        '{"english": "...", "vietnamese": "..."}\n\n'
        f"Vocabulary items ({len(sample)} total): {word_list_str}"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                url,
                headers={
                    "x-goog-api-key": GEMINI_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.9, "maxOutputTokens": 2000},
                },
                timeout=60,
            )
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait_s = 2 ** (attempt - 1)
                print(
                    f"Gemini trả về {resp.status_code} (lần thử {attempt}/{max_retries}), "
                    f"chờ {wait_s}s rồi thử lại..."
                )
                time.sleep(wait_s)
                continue

            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            json_str = _extract_json_object(raw_text)
            parsed = json.loads(json_str)
            english = str(parsed.get("english", "")).strip()
            vietnamese = str(parsed.get("vietnamese", "")).strip()
            if not english:
                raise ValueError("JSON trả về thiếu trường 'english'.")
            return english, vietnamese

        except (
            requests.exceptions.RequestException,
            KeyError,
            IndexError,
            ValueError,
            json.JSONDecodeError,
        ) as e:
            last_error = e
            if attempt < max_retries:
                wait_s = 2 ** (attempt - 1)
                print(
                    f"Lỗi khi gọi/đọc kết quả Gemini (lần thử {attempt}/{max_retries}): "
                    f"{e}. Chờ {wait_s}s rồi thử lại..."
                )
                time.sleep(wait_s)
                continue
            raise

    raise RuntimeError(f"Gemini vẫn lỗi sau {max_retries} lần thử: {last_error}")


def chunk_text(text, max_len=TELEGRAM_MAX_LEN):
    """Tách 1 đoạn text dài thành nhiều phần không vượt giới hạn ký tự Telegram."""
    lines = text.split("\n")
    chunks = []
    current = []
    current_len = 0
    for line in lines:
        added_len = len(line) + 1
        if current and current_len + added_len > max_len:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += added_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def send_telegram(text, parse_mode=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    resp = requests.post(url, data=payload, timeout=30)
    if parse_mode and resp.status_code == 400:
        # Có thể do Markdown bị lỗi cú pháp (dấu * không khớp cặp...) ->
        # gửi lại dạng chữ thường, không format, để không mất tin nhắn.
        resp = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=30,
        )
    resp.raise_for_status()


def main():
    words = get_words()
    if not words:
        raise SystemExit(f"Sheet '{SHEET_NAME}' không có từ nào.")

    now = datetime.now(timezone.utc)
    final_list, slot_index, runs_per_day, guaranteed_count = pick_words_for_this_run(
        words, now
    )

    used_ai = False
    try:
        english, vietnamese = generate_bilingual_paragraph(final_list)
        used_ai = True
        # Gửi tiếng Việt TRƯỚC, tiếng Anh SAU — đúng thứ tự yêu cầu.
        messages = []
        if vietnamese:
            messages.append((vietnamese, None))
        messages.append((english, "Markdown"))
    except Exception as e:  # noqa: BLE001 - muốn bắt mọi lỗi để có fallback
        print(f"Không tạo được đoạn văn bằng AI ({e}).")
        messages = [("AI False", None)]

    for text, parse_mode in messages:
        for chunk in chunk_text(text):
            send_telegram(chunk, parse_mode=parse_mode)

    print(
        f"Đã gửi {len(final_list)} từ (đợt {slot_index + 1}/{runs_per_day}, "
        f"trong đó {guaranteed_count} từ thuộc phần bảo đảm bao phủ hôm nay, "
        f"dùng AI: {used_ai}) vào Telegram thành công."
    )


if __name__ == "__main__":
    main()
