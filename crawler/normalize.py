"""Heuristic parsers for messy Japanese event descriptions.

These helpers convert free-text dates, age ranges, and prices into structured
fields. They are intentionally conservative: when a value cannot be parsed
reliably, we return None so the frontend can show the raw text instead.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

_AGE_KANJI = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def parse_age_range(text: str) -> tuple[int | None, int | None]:
    """Examples: '3歳〜小学生', '0〜3歳', '小学生向け', '未就学児'."""
    if not text:
        return None, None
    t = text.replace("〜", "~").replace("～", "~")
    # explicit numeric "N歳~M歳"
    m = re.search(r"(\d+)\s*歳?\s*~\s*(\d+)\s*歳", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    # "N歳~小学生" or "N歳から小学生"
    m = re.search(r"(\d+)\s*歳\s*(?:~|から).{0,3}小学(?:生|校(高|中|低)?学年)", t)
    if m:
        max_age = 12 if "高学年" in t else (9 if "中学年" in t else (7 if "低学年" in t else 12))
        return int(m.group(1)), max_age
    # "0~3歳" already handled. "未就学児"
    if "未就学" in t:
        return 0, 6
    if "乳児" in t:
        return 0, 1
    if "幼児" in t:
        return 1, 6
    if "小学生向け" in t or "小学生対象" in t or t.strip() == "小学生":
        return 6, 12
    if "小学校低学年" in t:
        return 6, 8
    if "小学校中学年" in t:
        return 8, 10
    if "小学校高学年" in t:
        return 10, 12
    # "N歳以上"
    m = re.search(r"(\d+)\s*歳\s*以上", t)
    if m:
        return int(m.group(1)), None
    # bare "N歳"
    m = re.search(r"(\d+)\s*歳", t)
    if m:
        n = int(m.group(1))
        return n, n
    if "どなたでも" in t or "全年齢" in t or "全ての年齢" in t:
        return 0, 99
    return None, None


def parse_price(text: str) -> tuple[str, int | None, str]:
    """Returns (type, amount, raw_text). type ∈ {free, paid, varies}."""
    if not text:
        return "varies", None, ""
    t = text.replace(",", "")
    if any(k in t for k in ("無料", "free", "Free", "FREE")):
        # Some pages say "無料（材料費別途）" — still treat as free for filter purposes.
        return "free", 0, text.strip()
    m = re.search(r"(\d{2,5})\s*円", t)
    if m:
        return "paid", int(m.group(1)), text.strip()
    return "varies", None, text.strip()


def parse_indoor(category: str, venue: str, description: str) -> bool | None:
    """Heuristic: outdoor markers > indoor markers > None."""
    blob = f"{category} {venue} {description}"
    outdoor_keys = ["公園", "屋外", "野外", "外遊び", "ネイチャー", "森", "海"]
    indoor_keys = ["館内", "室内", "屋内", "ホール", "図書館", "センター", "ミュージアム", "科学館"]
    if any(k in blob for k in outdoor_keys):
        return False
    if any(k in blob for k in indoor_keys):
        return True
    return None


def parse_jp_date(text: str, default_year: int | None = None) -> date | None:
    """Examples: '5月10日', '2026年5月10日', '令和8年5月10日'."""
    if not text:
        return None
    t = text.strip()
    m = re.search(r"(?:令和(\d+)年|(\d{4})年)?\s*(\d{1,2})月\s*(\d{1,2})日", t)
    if m:
        if m.group(1):
            year = 2018 + int(m.group(1))  # 令和元年 = 2019
        elif m.group(2):
            year = int(m.group(2))
        else:
            year = default_year or datetime.now(JST).year
        return date(year, int(m.group(3)), int(m.group(4)))
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def parse_jp_time_range(text: str) -> tuple[time | None, time | None]:
    if not text:
        return None, None
    t = text.replace("〜", "~").replace("～", "~").replace(":", ":")
    m = re.search(r"(\d{1,2}):(\d{2})\s*~\s*(\d{1,2}):(\d{2})", t)
    if m:
        return time(int(m.group(1)), int(m.group(2))), time(int(m.group(3)), int(m.group(4)))
    m = re.search(r"(\d{1,2}):(\d{2})", t)
    if m:
        return time(int(m.group(1)), int(m.group(2))), None
    return None, None


def to_iso(d: date | None, t: time | None) -> str | None:
    if d is None:
        return None
    if t is None:
        return datetime.combine(d, time(0, 0), tzinfo=JST).isoformat(timespec="seconds")
    return datetime.combine(d, t, tzinfo=JST).isoformat(timespec="seconds")


def detect_ward(address: str | None) -> str | None:
    if not address:
        return None
    m = re.search(r"横浜市\s*([^\s、,]+?[区])", address)
    if m:
        return m.group(1)
    return None
