"""
Gửi 1 đoạn văn tiếng Anh (do Gemini AI viết) chứa các từ vựng của lần chạy
này vào Telegram, kèm bảng nghĩa/ví dụ để tra cứu.

LOGIC "BAO PHỦ CẢ NGÀY" (không đổi so với bản trước):
- Mỗi ngày (giờ UTC), toàn bộ từ vựng được xáo trộn 1 lần duy nhất (seed =
  ngày hôm đó) rồi chia đều cho các lần chạy trong ngày (mặc định 12 lần,
  mỗi 2 tiếng). Mỗi lần chạy "phụ trách" đúng 1 phần -> sau đúng 1 ngày,
  toàn bộ từ trong sheet đều được gửi ít nhất 1 lần, không sót.

MỚI: ĐOẠN VĂN DO AI VIẾT
- Gọi Gemini API (miễn phí, xem README.md) để viết 1 đoạn văn tiếng Anh
  tự nhiên, lồng ghép toàn bộ các từ của lần chạy này, bôi đậm *từ* khi
  xuất hiện lần đầu.
- Script tự kiểm tra xem từ nào bị AI bỏ sót trong đoạn văn (không đảm bảo
  100% AI dùng đủ mọi từ) -> nếu có, liệt kê bổ sung ở cuối để KHÔNG phá vỡ
  cam kết "bao phủ cả ngày".
- Nếu gọi AI thất bại (hết quota, lỗi mạng...), script tự động chuyển về
  gửi dạng danh sách từ + nghĩa như bản cũ, để bạn vẫn nhận được từ vựng
  hôm đó thay vì không có gì.

Cần các biến môi trường (đặt làm GitHub Actions Secrets, xem README.md):
- GOOGLE_SERVICE_ACCOUNT_JSON : toàn bộ nội dung file JSON service account
- SPREADSHEET_ID              : ID của Google Sheet (nằm giữa /d/ và /edit trên URL)
- TELEGRAM_BOT_TOKEN          : token của bot, lấy từ @BotFather
- TELEGRAM_CHAT_ID            : id của chat/user nhận tin nhắn
- GEMINI_API_KEY              : API key miễn phí từ Google AI Studio (để viết đoạn văn)
- SHEET_NAME                  : (tuỳ chọn) tên tab, mặc định "Dictionary"
- NUM_WORDS                   : (tuỳ chọn) số từ mỗi lần gửi, mặc định 50
- RUN_INTERVAL_HOURS          : (tuỳ chọn) số tiếng giữa 2 lần chạy, mặc định 2
- GEMINI_MODEL                : (tuỳ chọn) model Gemini, mặc định "gemini-2.5-flash"
"""

import json
import math
import os
import random
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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

TELEGRAM_MAX_LEN = 3800  # để dư so với giới hạn 4096 ký tự của Telegram


def get_words():
    """Đọc toàn bộ từ vựng từ tab Dictionary trên Google Sheet."""
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
    - Toàn bộ `words` được bao phủ hết trong 1 ngày (qua các lần chạy khác nhau)
    - Mỗi tin nhắn vẫn có đúng NUM_WORDS từ (nếu đủ dữ liệu)

    Trả về: (final_list, slot_index, runs_per_day, guaranteed_count)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    runs_per_day = max(1, 24 // RUN_INTERVAL_HOURS)
    slot_index = (now.hour // RUN_INTERVAL_HOURS) % runs_per_day
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


def make_header(sample, slot_index, runs_per_day, now):
    return (
        f"📚 Đợt {slot_index + 1}/{runs_per_day} hôm nay — {len(sample)} từ "
        f"— {now.strftime('%H:%M %d/%m/%Y')} (UTC)"
    )


def generate_paragraph(sample):
    """
    Gọi Gemini API để viết 1 đoạn văn tiếng Anh lồng ghép toàn bộ từ trong
    `sample`. Bôi đậm từ bằng *từ* (Markdown legacy của Telegram).
    Trả về (text, missing_words) — missing_words là các từ AI có vẻ không
    dùng tới (kiểm tra bằng cách tìm chuỗi con, không hoàn toàn chính xác
    100% nhưng đủ để cảnh báo).
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("Chưa cấu hình GEMINI_API_KEY.")

    word_list_str = ", ".join(f'"{w["word"]}"' for w in sample)
    prompt = (
        "You are helping a Vietnamese learner study English vocabulary.\n"
        "Write ONE flowing, coherent English paragraph (250-450 words) — a short "
        "story or realistic scenario — that naturally uses EVERY single item in "
        "the following list at least once. Use each item's EXACT wording given "
        "(you may only change verb tense/grammatical form when strictly needed, "
        "but keep the core wording recognizable). The very first time each item "
        "appears, wrap it in single asterisks like *this*. Do not use asterisks "
        "for anything else. Do not add a title, preamble, or explanation — "
        "output ONLY the paragraph itself.\n\n"
        f"Vocabulary items ({len(sample)} total): {word_list_str}"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    resp = requests.post(
        url,
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 1200},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

    text_lower = text.lower()
    missing = [w for w in sample if w["word"].lower() not in text_lower]
    return text, missing


def build_glossary_lines(sample):
    """Tạo danh sách các dòng nghĩa/ví dụ (mỗi từ 1-2 dòng), không kèm header."""
    lines = ["📖 Nghĩa & ví dụ:", ""]
    for i, item in enumerate(sample, 1):
        line = f"{i}. {item['word']}"
        if item["meaning"]:
            line += f" — {item['meaning']}"
        lines.append(line)
        if item["example"]:
            lines.append(f"    → {item['example']}")
    return lines


def chunk_lines(lines, max_len=TELEGRAM_MAX_LEN):
    """Gom các dòng thành từng tin nhắn không vượt quá giới hạn ký tự."""
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
    header = make_header(final_list, slot_index, runs_per_day, now)

    used_ai = False
    try:
        paragraph, missing = generate_paragraph(final_list)
        used_ai = True
        send_telegram(f"{header}\n\n{paragraph}", parse_mode="Markdown")
        if missing:
            missing_text = ", ".join(w["word"] for w in missing)
            send_telegram(
                "⚠️ Vài từ AI chưa lồng được vào đoạn văn trên (vẫn đủ trong "
                f"phần bao phủ hôm nay): {missing_text}"
            )
    except Exception as e:  # noqa: BLE001 - muốn bắt mọi lỗi để có fallback
        print(f"Không tạo được đoạn văn bằng AI ({e}). Chuyển sang gửi danh sách.")
        send_telegram(header)

    glossary_lines = build_glossary_lines(final_list)
    for chunk in chunk_lines(glossary_lines):
        send_telegram(chunk)

    print(
        f"Đã gửi {len(final_list)} từ (đợt {slot_index + 1}/{runs_per_day}, "
        f"trong đó {guaranteed_count} từ thuộc phần bảo đảm bao phủ hôm nay, "
        f"dùng AI: {used_ai}) vào Telegram thành công."
    )


if __name__ == "__main__":
    main()
