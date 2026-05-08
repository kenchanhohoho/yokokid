"""Shared helpers and base interface for source modules."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

JST = ZoneInfo("Asia/Tokyo")

USER_AGENT = (
    "YokoKidBot/0.1 (+https://yokokid.vercel.app; aggregates public Yokohama "
    "kids-events info; contact via GitHub Issues)"
)

DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)

log = logging.getLogger(__name__)


@dataclass
class SourceMeta:
    id: str
    name: str
    url: str


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.5"},
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    )


def stable_id(source_id: str, *parts: str) -> str:
    h = hashlib.sha1("|".join([source_id, *parts]).encode("utf-8")).hexdigest()[:12]
    return f"{source_id}-{h}"


def now_jst_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def make_event(
    *,
    source: SourceMeta,
    event_id: str,
    title: str,
    description: str,
    venue_name: str,
    venue_address: str,
    ward: str | None,
    start_iso: str,
    end_iso: str | None,
    age_min: int | None,
    age_max: int | None,
    age_text: str,
    price_type: str,
    price_amount: int | None,
    price_text: str,
    indoor: bool | None,
    categories: list[str],
    registration_required: bool | None,
    registration_deadline: str | None,
    detail_url: str,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "title": title,
        "description": description,
        "source": {"id": source.id, "name": source.name, "url": source.url},
        "venue": {
            "name": venue_name,
            "address": venue_address,
            "ward": ward,
            "lat": lat,
            "lon": lon,
        },
        "dates": [{"start": start_iso, "end": end_iso}],
        "ageMin": age_min,
        "ageMax": age_max,
        "ageText": age_text,
        "price": {"type": price_type, "amount": price_amount, "text": price_text},
        "indoor": indoor,
        "categories": categories,
        "registrationRequired": registration_required,
        "registrationDeadline": registration_deadline,
        "url": detail_url,
        "fetchedAt": now_jst_iso(),
    }
