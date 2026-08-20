"""
Gửi ngẫu nhiên N từ vựng từ Google Sheet "Dictionary" vào Telegram.

Cần các biến môi trường (đặt làm GitHub Actions Secrets, xem README.md):
- GOOGLE_SERVICE_ACCOUNT_JSON : toàn bộ nội dung file JSON service account
- SPREADSHEET_ID              : ID của Google Sheet (nằm giữa /d/ và /edit trên URL)
- TELEGRAM_BOT_TOKEN          : token của bot, lấy từ @BotFather
- TELEGRAM_CHAT_ID            : id của chat/user nhận tin nhắn
- SHEET_NAME                  : (tuỳ chọn) tên tab, mặc định "Dictionary"
- NUM_WORDS                   : (tuỳ chọn) số từ mỗi lần gửi, mặc định 50
"""

import json
import os
import random
from datetime import datetime

import requests
from google.oauth2.service_account import Credentials
import gspread

GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEET_NAME = os.environ.get("SHEET_NAME", "Dictionary")
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
NUM_WORDS = int(os.environ.get("NUM_WORDS", "50"))

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


def build_lines(sample):
    """Tạo danh sách các dòng tin nhắn (mỗi từ 1-2 dòng)."""
    header = f"📚 {len(sample)} từ vựng ngẫu nhiên — {datetime.now().strftime('%H:%M %d/%m/%Y')}"
    lines = [header, ""]
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
        added_len = len(line) + 1  # +1 cho ký tự xuống dòng
        if current and current_len + added_len > max_len:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += added_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=30,
    )
    resp.raise_for_status()


def main():
    words = get_words()
    if len(words) < NUM_WORDS:
        raise SystemExit(
            f"Sheet '{SHEET_NAME}' chỉ có {len(words)} từ, không đủ {NUM_WORDS} từ yêu cầu."
        )

    sample = random.sample(words, NUM_WORDS)
    lines = build_lines(sample)
    for chunk in chunk_lines(lines):
        send_telegram(chunk)

    print(f"Đã gửi {NUM_WORDS} từ vựng vào Telegram thành công.")


if __name__ == "__main__":
    main()
