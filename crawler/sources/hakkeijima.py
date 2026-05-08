"""横浜・八景島シーパラダイス — events live under /ps/event/ as a list of links."""
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
    id="hakkeijima",
    name="横浜・八景島シーパラダイス",
    url="https://www.seaparadise.co.jp/",
)

LIST_URLS = [
    "https://www.seaparadise.co.jp/ps/event/index.html",
    "https://www.seaparadise.co.jp/aquaresorts/event/",
]

VENUE_NAME = "横浜・八景島シーパラダイス"
VENUE_ADDRESS = "横浜市金沢区八景島"
VENUE_WARD = "金沢区"
VENUE_LAT = 35.3414
VENUE_LON = 139.6378

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def fetch_events(client: httpx.Client) -> list[dict]:
    today = datetime.now(JST).date()
    seen: set[str] = set()
    out: list[dict] = []

    for list_url in LIST_URLS:
        try:
            r = client.get(list_url, headers={"User-Agent": UA})
            r.raise_for_status()
        except Exception as exc:
            log.warning("hakkeijima %s: %s", list_url, exc)
            continue
        soup = BeautifulSoup(r.text, "lxml")

        for a in soup.find_all("a", href=True):
            txt = a.get_text(" ", strip=True)
            if len(txt) < 10 or len(txt) > 400:
                continue
            if not _DATE_PATTERN.search(txt):
                continue
            href = a["href"]
            detail_url = urljoin(list_url, href)
            if detail_url in seen:
                continue
            seen.add(detail_url)

            title = _extract_title(txt)
            start_d, end_d = _parse_dates(txt, today)
            if start_d is None:
                continue

            description = _trim_description(txt, title)
            cats = _categorize(title, description)

            out.append(
                make_event(
                    source=META,
                    event_id=stable_id(META.id, detail_url),
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
                    price_text="入園料が必要(詳細は公式ページ)",
                    indoor=None,
                    categories=cats,
                    registration_required=None,
                    registration_deadline=None,
                    detail_url=detail_url,
                    lat=VENUE_LAT,
                    lon=VENUE_LON,
                )
            )

    log.info("hakkeijima: %d events", len(out))
    return out


_DATE_PATTERN = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})日")
_RANGE = re.compile(
    r"(\d{1,2})\s*月\s*(\d{1,2})\s*日"
    r"(?:\s*\([月火水木金土日]\))?"
    r"(?:\s*[～~〜]\s*(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日)?"
)


def _parse_dates(text: str, today: date) -> tuple[date | None, date | None]:
    m = _RANGE.search(text)
    if not m:
        return None, None
    try:
        year = today.year
        mo1 = int(m.group(1))
        d1 = int(m.group(2))
        start = date(year, mo1, d1)
        if (today - start).days > 90:
            start = date(year + 1, mo1, d1)
        if m.group(4):
            mo2 = int(m.group(3)) if m.group(3) else mo1
            d2 = int(m.group(4))
            end = date(start.year, mo2, d2)
            if end < start:
                end = date(start.year + 1, mo2, d2)
            if end < today:
                return None, None
            return start, end if end != start else None
        if start < today:
            return None, None
        return start, None
    except ValueError:
        return None, None


def _extract_title(text: str) -> str:
    parts = re.split(r"[【\[]|[ 　]{2,}|\s\d{1,2}月", text, maxsplit=1)
    head = parts[0].strip()
    if not head:
        head = text.strip()[:40]
    return head[:60]


def _trim_description(full: str, title: str) -> str:
    rest = full
    if title and title in full:
        rest = full.replace(title, "", 1)
    rest = rest.strip(" 　\n")
    return rest[:160] or f"{VENUE_NAME}のイベント"


def _categorize(title: str, description: str) -> list[str]:
    blob = f"{title} {description}"
    cats: list[str] = ["体験"]
    if "ワークショップ" in blob or "工作" in blob or "セルフ" in blob:
        cats = ["工作", "体験"]
    if "コンサート" in blob or "ライブ" in blob or "ステージ" in blob:
        cats.append("音楽")
    if "ヨガ" in blob or "ランニング" in blob:
        cats.append("スポーツ")
    if "バラ" in blob or "花" in blob or "フラワー" in blob:
        cats.append("自然")
    return cats
