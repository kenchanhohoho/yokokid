"""Shared parser for Yokohama Green Association zoo sites
(zoorasia.jp, nogeyama, kanazawa). Identical HTML structure across them."""
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


def parse_zoo_list(
    *,
    client: httpx.Client,
    list_url: str,
    source: SourceMeta,
    venue_name: str,
    venue_address: str,
    venue_ward: str,
    lat: float | None = None,
    lon: float | None = None,
) -> list[dict]:
    r = client.get(list_url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    today = datetime.now(JST).date()
    today_year = today.year
    out: list[dict] = []

    for li in soup.select("main li"):
        a = li.find("a", href=True)
        if not a:
            continue
        img = li.find("img")
        title = (img.get("alt") if img else "") or ""
        title = title.strip()
        if not title:
            continue
        dd = li.select_one("dl.term dd")
        date_text = dd.get_text(" ", strip=True) if dd else ""
        if not date_text:
            continue

        start_d, end_d = _parse_zoo_date(date_text, today_year, today)
        if start_d is None:
            continue

        detail_url = urljoin(list_url, a["href"])
        out.append(
            make_event(
                source=source,
                event_id=stable_id(source.id, detail_url),
                title=title,
                description=f"{venue_name}のイベント。",
                venue_name=venue_name,
                venue_address=venue_address,
                ward=venue_ward,
                start_iso=N.to_iso(start_d, None),
                end_iso=N.to_iso(end_d, None) if end_d else None,
                age_min=0,
                age_max=99,
                age_text="どなたでも",
                price_type="paid",
                price_amount=None,
                price_text="入園料が必要(詳細は公式ページ)",
                indoor=False,
                categories=["自然", "体験"],
                registration_required=None,
                registration_deadline=None,
                detail_url=detail_url,
                lat=lat,
                lon=lon,
            )
        )

    log.info("%s: %d events", source.id, len(out))
    return out


_RANGE_NO_YEAR = re.compile(
    r"(\d{1,2})月\s*(\d{1,2})日"
    r"(?:\s*[～~〜]\s*(?:(\d{1,2})月\s*)?(\d{1,2})日)?"
)


def _parse_zoo_date(text: str, default_year: int, today: date) -> tuple[date | None, date | None]:
    m = _RANGE_NO_YEAR.search(text)
    if not m:
        return None, None
    mo1 = int(m.group(1))
    d1 = int(m.group(2))
    mo2 = int(m.group(3)) if m.group(3) else mo1
    d2 = int(m.group(4)) if m.group(4) else None

    year = default_year
    try:
        start = date(year, mo1, d1)
    except ValueError:
        return None, None
    # If start is more than 90 days in the past, assume next year (e.g., page lists Jan event in Dec).
    if (today - start).days > 90:
        year += 1
        start = date(year, mo1, d1)

    if d2 is not None:
        try:
            end = date(year, mo2, d2)
            # If end < start, the range crosses a year boundary.
            if end < start:
                end = date(year + 1, mo2, d2)
        except ValueError:
            end = None
        return start, end if end != start else None
    return start, None
