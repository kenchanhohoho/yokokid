"""横浜市 市民利用施設等イベント情報 — the city-wide aggregator that covers
地区センター, コミュニティハウス, 児童館, 図書館, 公園 across all 18 wards.

Strategy: collect event IDs from per-ward index pages + the new-arrivals RSS,
then fetch each event's detail page (which uses a clean <th>/<td> table) and
keep entries whose 対象者層 includes 乳幼児 or こども・青少年.
"""
from __future__ import annotations

import logging
import re
import time
import warnings
from datetime import date, datetime
from datetime import time as dtime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import httpx

from .. import normalize as N
from .base import JST, SourceMeta, make_event, stable_id

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
log = logging.getLogger(__name__)

META = SourceMeta(
    id="yokohama_city",
    name="横浜市 市民利用施設等イベント情報",
    url="https://cgi.city.yokohama.lg.jp/common/event2/",
)

BASE = "https://cgi.city.yokohama.lg.jp/common/event2/"

WARDS = {
    "nishi": "西区", "naka": "中区", "minami": "南区", "konan": "港南区",
    "hodogaya": "保土ケ谷区", "asahi": "旭区", "tsurumi": "鶴見区",
    "kanagawa": "神奈川区", "isogo": "磯子区", "kanazawa": "金沢区",
    "aoba": "青葉区", "tsuzuki": "都筑区", "midori": "緑区", "kohoku": "港北区",
    "sakae": "栄区", "seya": "瀬谷区", "izumi": "泉区", "totsuka": "戸塚区",
}

KIDS_TARGETS = {"乳幼児", "こども・青少年"}

CATEGORY_KEYWORDS = [
    ("読み聞かせ", ["おはなし会", "読み聞かせ", "絵本"]),
    ("音楽",       ["リトミック", "コンサート", "音楽", "歌"]),
    ("工作",       ["工作", "クラフト", "つくる"]),
    ("外遊び",     ["公園", "外あそび", "外遊び"]),
    ("体験",       ["体験", "教室", "ワーク"]),
    ("自然",       ["自然", "森", "観察会"]),
    ("スポーツ",   ["体操", "スポーツ", "運動"]),
    ("科学",       ["実験", "サイエンス"]),
]


def fetch_events(client: httpx.Client) -> list[dict]:
    today = datetime.now(JST).date()
    id_to_ward: dict[str, str] = {}

    # Per-ward index pages → ward attribution.
    for slug, ward_jp in WARDS.items():
        try:
            r = client.get(BASE + f"{slug}/index.html")
            if r.status_code != 200:
                continue
            for eid in _extract_event_ids(r.text):
                id_to_ward.setdefault(eid, ward_jp)
        except Exception as exc:
            log.warning("yokohama_city ward %s: %s", slug, exc)

    # Top "本日開催中" + 新着 RSS = wider net for events not surfaced in any ward index.
    try:
        r = client.get(BASE + "event_list.html")
        for eid in _extract_event_ids(r.text):
            id_to_ward.setdefault(eid, "")
    except Exception:
        pass
    try:
        r = client.get(BASE + "eventlist.rss")
        for eid in _extract_event_ids(r.text):
            id_to_ward.setdefault(eid, "")
    except Exception:
        pass

    log.info("yokohama_city: %d candidate event IDs collected", len(id_to_ward))

    out: list[dict] = []
    for eid, ward in id_to_ward.items():
        try:
            ev = _parse_detail(client, eid, ward, today)
        except Exception as exc:
            log.warning("yokohama_city event %s parse error: %s", eid, exc)
            continue
        if ev:
            out.append(ev)
        time.sleep(0.25)  # Politeness delay; ~10s overhead for 40 events.

    log.info("yokohama_city: %d kid events kept", len(out))
    return out


_ID_PATTERN = re.compile(r"event_detail\.html\?id=(\d+)")


def _extract_event_ids(html: str) -> list[str]:
    return list(dict.fromkeys(_ID_PATTERN.findall(html)))  # preserve order, dedupe


def _parse_detail(client: httpx.Client, eid: str, ward_hint: str, today: date) -> dict | None:
    url = BASE + f"event_detail.html?id={eid}"
    r = client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "lxml")

    # Title — <title>横浜市 市民利用施設等イベント情報 <title></title>
    title_tag = soup.find("title")
    title = ""
    if title_tag:
        title = title_tag.get_text(strip=True)
        title = re.sub(r"^横浜市\s*市民利用施設等イベント情報\s*", "", title)
    if not title:
        return None

    table = soup.find("table", id="event-detail")
    if not table:
        return None
    fields: dict[str, str] = {}
    for tr in table.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not (th and td):
            continue
        label = th.get_text(strip=True)
        # Preserve line breaks in 日程 by replacing <br> with \n.
        for br in td.find_all("br"):
            br.replace_with("\n")
        value = td.get_text("\n", strip=True)
        fields[label] = value

    target = fields.get("対象者層", "")
    if not any(t in target for t in KIDS_TARGETS):
        return None

    # 日程 — pick the first future occurrence.
    schedule = fields.get("日程", "")
    start_iso, end_iso = _parse_schedule(schedule, fields.get("開催時刻", ""), today)
    if start_iso is None:
        return None

    venue_name = fields.get("場所/窓口", "") or fields.get("主催", "") or "横浜市内施設"
    venue_address_raw = fields.get("場所詳細", "") or venue_name
    ward = ward_hint or N.detect_ward(venue_address_raw) or ""

    description = fields.get("あらまし", "").replace("\n", " ").strip()[:200]
    sub_title = fields.get("サブタイトル", "")
    if sub_title and not description:
        description = sub_title

    age_text = fields.get("参加条件", "") or target
    age_min, age_max = N.parse_age_range(age_text)
    if age_min is None and age_max is None:
        # fall back from 対象者層
        if "乳幼児" in target:
            age_min, age_max = 0, 6
        elif "こども・青少年" in target:
            age_min, age_max = 6, 18

    cost_text = fields.get("費用負担", "") or "無料"
    price_type, price_amount, price_text = N.parse_price(cost_text)

    method = fields.get("応募・選考方法", "")
    if "当日" in method or "自由" in method:
        registration_required = False
    elif "申込" in method or "先着" in method:
        registration_required = True
    else:
        registration_required = None

    indoor = N.parse_indoor(target, venue_name, description)

    cats = _categorize(title, description, venue_name)

    return make_event(
        source=META,
        event_id=stable_id(META.id, eid),
        title=title,
        description=description or f"{venue_name}のイベント",
        venue_name=venue_name,
        venue_address=venue_address_raw,
        ward=ward or None,
        start_iso=start_iso,
        end_iso=end_iso,
        age_min=age_min,
        age_max=age_max,
        age_text=age_text or target,
        price_type=price_type,
        price_amount=price_amount,
        price_text=price_text or cost_text,
        indoor=indoor,
        categories=cats or ["体験"],
        registration_required=registration_required,
        registration_deadline=None,
        detail_url=url,
    )


_DATE_LINE = re.compile(
    r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日"
    r"(?:\s*\([月火水木金土日]\))?"
    r"(?:\s*(\d{1,2})時(?:(\d{2})分)?\s*から\s*(\d{1,2})時(?:(\d{2})分)?\s*まで)?"
)


def _parse_schedule(schedule: str, time_field: str, today: date) -> tuple[str | None, str | None]:
    if not schedule:
        return None, None
    matches: list[tuple[date, dtime | None, dtime | None]] = []
    for line in schedule.split("\n"):
        m = _DATE_LINE.search(line)
        if not m:
            continue
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        st = et = None
        if m.group(4):
            st = dtime(int(m.group(4)), int(m.group(5)) if m.group(5) else 0)
        if m.group(6):
            et = dtime(int(m.group(6)), int(m.group(7)) if m.group(7) else 0)
        matches.append((d, st, et))
    # If no time on the date lines, fall back to 開催時刻 single line.
    if matches and time_field and all(st is None for _, st, _ in matches):
        st, et = N.parse_jp_time_range(time_field)
        matches = [(d, st, et) for d, _, _ in matches]
    matches.sort(key=lambda x: x[0])
    for d, st, et in matches:
        if d >= today:
            return N.to_iso(d, st), (N.to_iso(d, et) if et else None)
    return None, None


def _categorize(*texts: str) -> list[str]:
    blob = " ".join(texts)
    out: list[str] = []
    for cat, keywords in CATEGORY_KEYWORDS:
        if any(k in blob for k in keywords):
            out.append(cat)
    return out
