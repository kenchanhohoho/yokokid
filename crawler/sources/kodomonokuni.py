"""こどもの国 — list page on kodomonokuni.org. Mixed date formats including
recurring events; we keep only events with a parseable specific date."""
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
    id="kodomonokuni",
    name="こどもの国",
    url="https://www.kodomonokuni.org/event/",
)

LIST_URL = "https://www.kodomonokuni.org/event/"
VENUE_NAME = "こどもの国"
VENUE_ADDRESS = "横浜市青葉区奈良町700"
VENUE_WARD = "青葉区"
VENUE_LAT = 35.5605
VENUE_LON = 139.4863


def fetch_events(client: httpx.Client) -> list[dict]:
    r = client.get(LIST_URL)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    today = datetime.now(JST).date()
    out: list[dict] = []

    for li in soup.select("li.event"):
        a = li.find("a", href=True)
        title_el = li.select_one(".ev_title")
        sub_el = li.select_one(".ev_sub")
        con_el = li.select_one(".ev_con")
        if not (a and title_el and sub_el):
            continue
        title = title_el.get_text(strip=True)
        date_text = sub_el.get_text(" ", strip=True)
        description = con_el.get_text(strip=True) if con_el else f"{VENUE_NAME}のイベント"

        start_d, end_d = _pick_date(date_text, today)
        if start_d is None:
            # Skip recurring-only entries (e.g., "毎週日曜日") for v0.
            continue

        detail_url = urljoin(LIST_URL, a["href"])
        out.append(
            make_event(
                source=META,
                event_id=stable_id(META.id, detail_url, title),
                title=title,
                description=description,
                venue_name=VENUE_NAME,
                venue_address=VENUE_ADDRESS,
                ward=VENUE_WARD,
                start_iso=N.to_iso(start_d, None),
                end_iso=N.to_iso(end_d, None) if end_d else None,
                age_min=0,
                age_max=99,
                age_text="どなたでも",
                price_type="paid",
                price_amount=None,
                price_text="入園料が必要(イベント参加費は別途)",
                indoor=False,
                categories=["外遊び", "自然", "体験"],
                registration_required=None,
                registration_deadline=None,
                detail_url=detail_url,
                lat=VENUE_LAT,
                lon=VENUE_LON,
            )
        )

    log.info("kodomonokuni: %d events", len(out))
    return out


_RANGE = re.compile(
    r"(?:(\d{4})年)?\s*(\d{1,2})[月/](\d{1,2})日?"
    r"(?:\s*[～~〜\-]\s*(?:(\d{1,2})[月/])?(\d{1,2})日?)?"
)


def _pick_date(text: str, today: date) -> tuple[date | None, date | None]:
    # Skip strictly recurring strings without explicit dates.
    if not re.search(r"\d", text):
        return None, None

    candidates: list[tuple[date, date]] = []
    for m in _RANGE.finditer(text):
        try:
            year = int(m.group(1)) if m.group(1) else today.year
            mo1 = int(m.group(2))
            d1 = int(m.group(3))
            start = date(year, mo1, d1)
            if (today - start).days > 90:
                start = date(year + 1, mo1, d1)
            if m.group(5):
                mo2 = int(m.group(4)) if m.group(4) else mo1
                d2 = int(m.group(5))
                try:
                    end = date(start.year, mo2, d2)
                    if end < start:
                        end = date(start.year + 1, mo2, d2)
                except ValueError:
                    end = start
                candidates.append((start, end))
            else:
                candidates.append((start, start))
        except ValueError:
            continue

    candidates.sort()
    for s, e in candidates:
        if e >= today:
            return s, e if e != s else None
    return None, None
