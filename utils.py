import re
from datetime import datetime
import pytz


def decode_latin(text):
    """Decode text with various encodings"""
    try:
        return text.encode().decode('utf-8')
    except Exception as e1:
        try:
            return bytes(text, 'utf-8').decode('unicode_escape')
        except Exception as e2:
            try:
                return text.encode('raw_unicode_escape').decode('utf-8')
            except Exception as e3:
                print(f"Warning: Could not decode text: '{text}'")
                print(f"Errors: {e1}, {e2}, {e3}")
                return text


def is_receipt_by_keywords(text, keywords):
    """Check if text contains receipt keywords"""
    text_lower = text.lower()
    matches = sum(1 for keyword in keywords if keyword in text_lower)
    currency_pattern = r'R?\$?\s*\d+[,.]\d{2}'
    has_currency = bool(re.search(currency_pattern, text))
    return has_currency and matches >= 1


def convert_to_utc(date_str, time_str, timezone='America/Sao_Paulo'):
    """Convert local datetime to UTC"""
    local_tz = pytz.timezone(timezone)
    datetime_str = f"{date_str} {time_str}"
    local_dt = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
    local_dt = local_tz.localize(local_dt)
    return local_dt.astimezone(pytz.UTC)
