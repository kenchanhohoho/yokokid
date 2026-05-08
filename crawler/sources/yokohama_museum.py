"""横浜美術館 — child program filter."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import httpx

from .. import normalize as N
from .base import JST, SourceMeta, make_event, stable_id

log = logging.getLogger(__name__)

META = SourceMeta(
    id="yokohama_museum",
    name="横浜美術館",
    url="https://yokohama.art.museum/",
)

LIST_URL = "https://yokohama.art.museum/event/?conditions%5B%5D=children"

VENUE_NAME = "横浜美術館"
VENUE_ADDRESS = "横浜市西区みなとみらい3-4-1"
VENUE_WARD = "西区"
VENUE_LAT = 35.4587
VENUE_LON = 139.6322

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def fetch_events(client: httpx.Client) -> list[dict]:
    r = client.get(LIST_URL, headers={"User-Agent": UA})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    today = datetime.now(JST).date()
    out: list[dict] = []

    for box in soup.select("div.itemBox"):
        a = box.find("a", href=True)
        h3 = box.find("h3")
        if not (a and h3):
            continue
        info_tags = [p.get_text(strip=True) for p in box.select(".infoBox p")]
        if not any("子ども" in t for t in info_tags):
            continue

        title = h3.get_text(strip=True)
        date_lines = [p.get_text(" ", strip=True) for p in box.select("p.dateTxt")]
        date_text = date_lines[0] if date_lines else ""
        target_text = date_lines[1] if len(date_lines) > 1 else ""

        start_d, end_d = _parse_dates(date_text, today)
        if start_d is None:
            continue

        is_free = any("無料" in t for t in info_tags)
        is_workshop = any("ワークショップ" in t for t in info_tags)
        is_lecture = any(t in ("講演会・トーク",) for t in info_tags)

        cats: list[str] = ["体験"]
        if is_workshop:
            cats = ["工作", "体験"]
        if is_lecture:
            cats = ["体験"]

        age_min, age_max = N.parse_age_range(target_text)
        if age_min is None and age_max is None:
            age_min, age_max = 0, 12  # 子ども（小学生以下）

        detail_url = urljoin(LIST_URL, a["href"])
        out.append(
            make_event(
                source=META,
                event_id=stable_id(META.id, detail_url),
                title=title,
                description=target_text or f"{VENUE_NAME}のプログラム",
                venue_name=VENUE_NAME,
                venue_address=VENUE_ADDRESS,
                ward=VENUE_WARD,
                start_iso=N.to_iso(start_d, None),
                end_iso=N.to_iso(end_d, None) if end_d else None,
                age_min=age_min,
                age_max=age_max,
                age_text=target_text or "子ども（小学生以下）",
                price_type="free" if is_free else "paid",
                price_amount=0 if is_free else None,
                price_text="無料" if is_free else "観覧料が必要(詳細は公式ページ)",
                indoor=True,
                categories=cats,
                registration_required=None,
                registration_deadline=None,
                detail_url=detail_url,
                lat=VENUE_LAT,
                lon=VENUE_LON,
            )
        )

    log.info("yokohama_museum: %d events", len(out))
    return out


_DATE = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")


def _parse_dates(text: str, today: date) -> tuple[date | None, date | None]:
    matches = list(_DATE.finditer(text))
    if not matches:
        return None, None
    try:
        m1 = matches[0]
        start = date(int(m1.group(1)), int(m1.group(2)), int(m1.group(3)))
    except ValueError:
        return None, None
    end: date | None = None
    if len(matches) >= 2:
        try:
            m2 = matches[1]
            end = date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        except ValueError:
            end = None
    # Skip events whose entire range is in the past.
    last = end or start
    if last < today:
        return None, None
    return start, end
