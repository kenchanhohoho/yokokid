"""はまぎん こども宇宙科学館 — list page is clean HTML."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import httpx

from .. import normalize as N
from .base import JST, SourceMeta, make_event, stable_id

log = logging.getLogger(__name__)

META = SourceMeta(
    id="kagakukan",
    name="はまぎん こども宇宙科学館",
    url="https://www.yokohama-kagakukan.jp/event/",
)

LIST_URL = "https://www.yokohama-kagakukan.jp/event/"

CATEGORY_MAP = {
    "プラネタリウム": ["科学"],
    "サイエンス・ショウなど": ["科学", "体験"],
    "サイエンスショウなど": ["科学", "体験"],
    "工作": ["工作"],
    "読み聞かせ": ["読み聞かせ"],
    "トークイベント": ["科学"],
    "企画展": ["科学"],
    "オンライン": ["科学"],
    "星空観察会": ["科学", "自然"],
}

VENUE_NAME = "はまぎん こども宇宙科学館"
VENUE_ADDRESS = "横浜市磯子区洋光台5-2-1"
VENUE_WARD = "磯子区"
VENUE_LAT = 35.3601
VENUE_LON = 139.6125


def fetch_events(client: httpx.Client) -> list[dict]:
    r = client.get(LIST_URL)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    today = datetime.now(JST).date()
    events: list[dict] = []

    for art in soup.select("article.event"):
        a = art.find("a", href=True)
        if not a:
            continue
        detail_url = urljoin(LIST_URL, a["href"])
        title_el = art.select_one(".event_tit")
        date_el = art.select_one(".event_date")
        cat_el = art.select_one(".event_cat")
        join_el = art.select_one(".event_join")
        target_el = art.select_one(".event_target")
        if not (title_el and date_el):
            continue

        title = title_el.get_text(strip=True)
        date_text = date_el.get_text(" ", strip=True)
        category_text = cat_el.get_text(strip=True) if cat_el else ""
        join_text = join_el.get_text(strip=True) if join_el else ""
        target_text = target_el.get_text(strip=True) if target_el else ""

        start_d, end_d = _pick_first_future_range(date_text, today)
        if start_d is None:
            continue

        age_min, age_max = N.parse_age_range(target_text)
        cats = CATEGORY_MAP.get(category_text, ["体験"])
        registration_required = "チケット" in join_text and "当日" not in join_text

        events.append(
            make_event(
                source=META,
                event_id=stable_id(META.id, detail_url),
                title=title,
                description=f"{category_text}のイベント。{target_text}".strip("。"),
                venue_name=VENUE_NAME,
                venue_address=VENUE_ADDRESS,
                ward=VENUE_WARD,
                start_iso=N.to_iso(start_d, None),
                end_iso=N.to_iso(end_d, None) if end_d else None,
                age_min=age_min,
                age_max=age_max,
                age_text=target_text,
                price_type="paid",
                price_amount=None,
                price_text="入館料が必要(詳細は公式ページ)",
                indoor=True,
                categories=cats,
                registration_required=registration_required,
                registration_deadline=None,
                detail_url=detail_url,
                lat=VENUE_LAT,
                lon=VENUE_LON,
            )
        )

    log.info("kagakukan: %d events", len(events))
    return events


_RANGE = re.compile(
    r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日(?:（[月火水木金土日]）)?"
    r"(?:\s*[～~〜]\s*(?:(\d{4})年)?\s*(?:(\d{1,2})月)?\s*(\d{1,2})日)?"
)


def _pick_first_future_range(text: str, today: date) -> tuple[date | None, date | None]:
    """Walk through all date specifications and return the first range that
    overlaps today or is in the future."""
    candidates: list[tuple[date, date]] = []
    base_year: int | None = None
    base_month: int | None = None
    for m in _RANGE.finditer(text):
        y1 = int(m.group(1))
        mo1 = int(m.group(2))
        d1 = int(m.group(3))
        base_year, base_month = y1, mo1
        if m.group(6):
            y2 = int(m.group(4)) if m.group(4) else y1
            mo2 = int(m.group(5)) if m.group(5) else mo1
            d2 = int(m.group(6))
            try:
                start = date(y1, mo1, d1)
                end = date(y2, mo2, d2)
            except ValueError:
                continue
            candidates.append((start, end))
        else:
            try:
                d = date(y1, mo1, d1)
            except ValueError:
                continue
            candidates.append((d, d))

    # Also handle short-form continuations like "、12日（日）" reusing base_year/month.
    short = re.compile(r"、\s*(\d{1,2})日")
    if base_year and base_month:
        # Avoid double-counting positions matched by _RANGE.
        for sm in short.finditer(text):
            try:
                d = date(base_year, base_month, int(sm.group(1)))
            except ValueError:
                continue
            if not any(s == d for s, _ in candidates):
                candidates.append((d, d))

    candidates.sort()
    for s, e in candidates:
        if e >= today:
            return s, e if e != s else None
    return None, None
