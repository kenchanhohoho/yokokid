"""横浜市 観光・イベントカレンダー — city-wide event calendar curated by the
city's Bureau of Tourism. Each row is one day; events repeat on multi-day
spans, so we collect distinct detail URLs and visit each."""
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
    id="yokohama_kanko",
    name="横浜市 観光・イベントカレンダー",
    url="https://www.city.yokohama.lg.jp/kanko-bunka/kanko-event/eventannai/calendar/list_calendar.html",
)

LIST_URL = META.url

# Kid-relevant target audience markers. Used to filter events; conservative
# (favours recall over precision) since the page is broad.
KID_TARGET_KEYWORDS = ["子ども", "こども", "親子", "乳幼児", "児童", "小学生", "中学生", "高校生", "ファミリー", "家族"]


def fetch_events(client: httpx.Client) -> list[dict]:
    today = datetime.now(JST).date()
    out: list[dict] = []

    r = client.get(LIST_URL)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # Collect distinct detail URLs from the calendar table.
    detail_urls: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/kanko-bunka/kanko-event/eventannai/kyoku-sagasu" in href:
            full = urljoin(LIST_URL, href)
            if full not in seen:
                seen.add(full)
                detail_urls.append(full)

    log.info("yokohama_kanko: %d candidate events", len(detail_urls))

    for url in detail_urls:
        try:
            ev = _parse_detail(client, url, today)
        except Exception as exc:
            log.warning("yokohama_kanko %s parse error: %s", url, exc)
            continue
        if ev:
            out.append(ev)
        time.sleep(0.2)

    log.info("yokohama_kanko: %d kid events kept", len(out))
    return out


def _parse_detail(client: httpx.Client, url: str, today: date) -> dict | None:
    r = client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "lxml")

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s*[-|]\s*横浜市$", "", t.get_text(strip=True))
    if not title:
        return None

    # Heuristic: break the body text into "field" lines and read off labelled
    # sections. The page renders as a series of <h2>/<h3>/text blocks.
    body_text = soup.get_text("\n", strip=True)
    fields = _extract_fields(body_text)

    target_text = fields.get("対象者", "")
    desc = fields.get("概要", "") or fields.get("イベント名", "")
    blob_for_kid_check = f"{title} {target_text} {desc}"
    if not any(k in blob_for_kid_check for k in KID_TARGET_KEYWORDS):
        return None

    schedule = fields.get("日時詳細", "") or fields.get("開催日時", "") or fields.get("日時", "")
    start_iso, end_iso = _parse_schedule(schedule, today)
    if start_iso is None:
        return None

    venue_full = fields.get("開催場所", "")
    venue_name = venue_full.split("（")[0].split("(")[0].strip()
    if not venue_name:
        venue_name = "横浜市内"
    ward = (
        fields.get("開催エリア", "").strip()
        or N.detect_ward(venue_full)
        or None
    )

    age_min, age_max = N.parse_age_range(target_text)
    cost_text = fields.get("費用", "") or fields.get("料金", "") or fields.get("参加費", "") or "詳細は公式ページ"
    price_type, price_amount, price_text = N.parse_price(cost_text)

    method = fields.get("参加方法", "") + " " + fields.get("申込方法", "")
    if "申込" in method or "予約" in method:
        registration_required: bool | None = True
    elif "どなたでも" in method or "自由" in method:
        registration_required = False
    else:
        registration_required = None

    indoor = N.parse_indoor("", venue_name, desc)

    cats = _categorize(title, desc)

    return make_event(
        source=META,
        event_id=stable_id(META.id, url),
        title=title,
        description=desc[:200] if desc else f"{venue_name}のイベント",
        venue_name=venue_name,
        venue_address=venue_full or venue_name,
        ward=ward,
        start_iso=start_iso,
        end_iso=end_iso,
        age_min=age_min,
        age_max=age_max,
        age_text=target_text or "",
        price_type=price_type,
        price_amount=price_amount,
        price_text=price_text,
        indoor=indoor,
        categories=cats,
        registration_required=registration_required,
        registration_deadline=None,
        detail_url=url,
    )


_LABELS = {
    "イベント名", "概要", "日時詳細", "開催日時", "日時",
    "開催場所", "開催エリア", "対象者", "参加方法", "申込方法",
    "費用", "料金", "参加費", "主催", "主催・共催", "問合せ", "申込",
    "最終更新日", "印刷する",
}


def _extract_fields(text: str) -> dict[str, str]:
    """Walk down the body splitting on labelled headings. The page uses
    visible labels like '日時詳細' followed by the value on subsequent lines
    until the next known label."""
    out: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line in _LABELS:
            if current and buf:
                out.setdefault(current, " ".join(buf).strip())
            current = line
            buf = []
            continue
        if current:
            buf.append(line)
    if current and buf:
        out.setdefault(current, " ".join(buf).strip())
    return out


_DATE_PAT = re.compile(
    r"(?:(\d{4})年)?\s*(\d{1,2})月\s*(\d{1,2})日"
    r"(?:\s*\([月火水木金土日]\))?"
    r"(?:\s*[～~〜]\s*(?:(\d{4})年)?\s*(?:(\d{1,2})月)?\s*(\d{1,2})日)?"
)


def _parse_schedule(text: str, today: date) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    candidates: list[tuple[date, date | None]] = []
    for m in _DATE_PAT.finditer(text):
        try:
            year = int(m.group(1)) if m.group(1) else today.year
            mo = int(m.group(2))
            d = int(m.group(3))
            start = date(year, mo, d)
            if (today - start).days > 90:
                start = date(year + 1, mo, d)
            end: date | None = None
            if m.group(6):
                year2 = int(m.group(4)) if m.group(4) else start.year
                mo2 = int(m.group(5)) if m.group(5) else mo
                d2 = int(m.group(6))
                try:
                    end = date(year2, mo2, d2)
                    if end < start:
                        end = date(start.year + 1, mo2, d2)
                except ValueError:
                    end = None
            candidates.append((start, end))
        except ValueError:
            continue
    candidates.sort()
    for s, e in candidates:
        last = e or s
        if last >= today:
            # Find first time in the schedule near this date if any.
            t_start, t_end = N.parse_jp_time_range(text)
            return N.to_iso(s, t_start), (N.to_iso(e, t_end) if e else (N.to_iso(s, t_end) if t_end else None))
    return None, None


def _categorize(title: str, desc: str) -> list[str]:
    blob = f"{title} {desc}"
    cats: list[str] = []
    if any(k in blob for k in ["工作", "クラフト", "つくる", "ワークショップ"]):
        cats.append("工作")
    if any(k in blob for k in ["科学", "実験", "サイエンス"]):
        cats.append("科学")
    if any(k in blob for k in ["音楽", "コンサート", "ライブ"]):
        cats.append("音楽")
    if any(k in blob for k in ["読み聞かせ", "おはなし", "絵本"]):
        cats.append("読み聞かせ")
    if any(k in blob for k in ["スポーツ", "運動", "体操"]):
        cats.append("スポーツ")
    if any(k in blob for k in ["公園", "外遊び", "野外"]):
        cats.append("外遊び")
    if any(k in blob for k in ["自然", "森", "観察"]):
        cats.append("自然")
    return cats or ["体験"]
