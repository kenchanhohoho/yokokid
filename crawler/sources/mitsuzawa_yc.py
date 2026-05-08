"""三ツ沢公園青少年野外活動センター（横浜市スポーツ協会）.

野外炊事・キャンプ・流しそうめんなど親子向け体験イベントが豊富。
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from datetime import time as dtime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import httpx

from .. import normalize as N
from .base import JST, SourceMeta, make_event, stable_id

log = logging.getLogger(__name__)

META = SourceMeta(
    id="mitsuzawa_yc",
    name="三ツ沢公園青少年野外活動センター",
    url="https://yokohama-sport.jp/mitsuzawa-yc-ysa/",
)

LIST_URL = "https://yokohama-sport.jp/mitsuzawa-yc-ysa/category/family/"

VENUE_NAME = "三ツ沢公園青少年野外活動センター"
VENUE_ADDRESS = "横浜市神奈川区三ツ沢西町3-1"
VENUE_WARD = "神奈川区"
VENUE_LAT = 35.4791
VENUE_LON = 139.6122

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def fetch_events(client: httpx.Client) -> list[dict]:
    today = datetime.now(JST).date()
    out: list[dict] = []

    r = client.get(LIST_URL, headers={"User-Agent": UA})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    detail_urls: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"/mitsuzawa-yc-ysa/information/(\d+)/?$", a["href"])
        if not m:
            continue
        full = urljoin(LIST_URL, a["href"])
        if full in seen:
            continue
        seen.add(full)
        detail_urls.append(full)

    log.info("mitsuzawa_yc: %d candidate event detail URLs", len(detail_urls))

    for url in detail_urls:
        try:
            ev = _parse_detail(client, url, today)
        except Exception as exc:
            log.warning("mitsuzawa_yc %s parse error: %s", url, exc)
            continue
        if ev:
            out.append(ev)
        time.sleep(0.2)

    log.info("mitsuzawa_yc: %d events kept", len(out))
    return out


def _parse_detail(client: httpx.Client, url: str, today: date) -> dict | None:
    r = client.get(url, headers={"User-Agent": UA})
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "lxml")

    h1 = soup.find("h1")
    if not h1:
        return None
    raw_title = h1.get_text(" ", strip=True)
    title = _clean_title(raw_title)

    table = soup.find("table")
    if not table:
        return None
    fields = _parse_table(table)

    schedule = fields.get("日時", "") or fields.get("日　時", "")
    target = fields.get("対象", "") or fields.get("対　象", "")
    cost = fields.get("参加費", "") or fields.get("費用", "")
    content = fields.get("内容", "") or fields.get("内　容", "")
    method = fields.get("申込方法", "")

    start_iso, end_iso = _parse_schedule(schedule, today)
    if start_iso is None:
        return None

    age_min, age_max = N.parse_age_range(target)
    # Family events at this venue are typically 小学生親子. Use a sensible default.
    if age_min is None and age_max is None:
        if "小学生" in target:
            age_min, age_max = 6, 12
        elif "親子" in target or "家族" in target:
            age_min, age_max = 0, 12

    price_type, price_amount, price_text = N.parse_price(cost)

    description = (content or target).replace("\n", " ").strip()[:200]

    cats = _categorize(title, content)

    return make_event(
        source=META,
        event_id=stable_id(META.id, url),
        title=title,
        description=description or f"{VENUE_NAME}の親子向けイベント",
        venue_name=VENUE_NAME,
        venue_address=VENUE_ADDRESS,
        ward=VENUE_WARD,
        start_iso=start_iso,
        end_iso=end_iso,
        age_min=age_min,
        age_max=age_max,
        age_text=target or "親子",
        price_type=price_type,
        price_amount=price_amount,
        price_text=price_text or cost,
        indoor=False,  # 野外活動センター — outdoor by design
        categories=cats,
        registration_required=True if method else None,
        registration_deadline=None,
        detail_url=url,
        lat=VENUE_LAT,
        lon=VENUE_LON,
    )


def _clean_title(raw: str) -> str:
    # Strip leading category words like "親子・家族で楽しむイベント".
    raw = re.sub(r"^(親子・家族で楽しむイベント|大人が楽しむ教室・イベント|お知らせ)\s*", "", raw)
    # Drop trailing date repetitions like "2026年4月29日".
    raw = re.sub(r"\s*20\d{2}年\d{1,2}月\d{1,2}日.*$", "", raw)
    # Drop trailing scheduling tail "予定" if alone.
    raw = re.sub(r"\s+予定\s*$", "", raw)
    return raw.strip()


def _parse_table(table) -> dict[str, str]:
    out: dict[str, str] = {}
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        label = tds[0].get_text(" ", strip=True).replace("　", "").replace(" ", "")
        for br in tds[1].find_all("br"):
            br.replace_with("\n")
        value = tds[1].get_text("\n", strip=True)
        if label:
            out[label] = value
    return out


_DATE_PAT = re.compile(
    r"(?:令和(\d+)年|(\d{4})年)?\s*"
    r"(\d{1,2})月\s*(\d{1,2})日"
    r"(?:\s*\([月火水木金土日]\))?"
    r"(?:\s*[～~〜から]\s*(?:(\d{1,2})月\s*)?(\d{1,2})日)?"
)


def _parse_schedule(text: str, today: date) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    candidates: list[tuple[date, date | None]] = []
    for m in _DATE_PAT.finditer(text):
        try:
            if m.group(1):
                year = 2018 + int(m.group(1))
            elif m.group(2):
                year = int(m.group(2))
            else:
                year = today.year
            mo = int(m.group(3))
            d = int(m.group(4))
            start = date(year, mo, d)
            if (today - start).days > 90:
                start = date(year + 1, mo, d)
            end: date | None = None
            if m.group(6):
                mo2 = int(m.group(5)) if m.group(5) else mo
                d2 = int(m.group(6))
                try:
                    end = date(start.year, mo2, d2)
                    if end < start:
                        end = date(start.year + 1, mo2, d2)
                except ValueError:
                    end = None
            candidates.append((start, end))
        except ValueError:
            continue
    candidates.sort()
    t_start, t_end = N.parse_jp_time_range(text)
    for s, e in candidates:
        last = e or s
        if last >= today:
            return N.to_iso(s, t_start), (N.to_iso(e, t_end) if e else (N.to_iso(s, t_end) if t_end else None))
    return None, None


def _categorize(title: str, content: str) -> list[str]:
    blob = f"{title} {content}"
    cats: list[str] = []
    if any(k in blob for k in ["キャンプ", "野外", "外遊び", "デイ"]):
        cats.append("外遊び")
    if any(k in blob for k in ["自然", "森", "観察"]):
        cats.append("自然")
    if any(k in blob for k in ["料理", "BBQ", "炊事", "そうめん"]):
        cats.append("体験")
    if any(k in blob for k in ["工作"]):
        cats.append("工作")
    return cats or ["体験", "外遊び"]
