"""野毛山動物園 — list page on hama-midorinokyokai.or.jp."""
from __future__ import annotations

import httpx

from ._zoo_common import parse_zoo_list
from .base import SourceMeta

META = SourceMeta(
    id="nogeyama",
    name="野毛山動物園",
    url="https://www.hama-midorinokyokai.or.jp/zoo/nogeyama/event/",
)


def fetch_events(client: httpx.Client) -> list[dict]:
    return parse_zoo_list(
        client=client,
        list_url=META.url,
        source=META,
        venue_name="野毛山動物園",
        venue_address="横浜市西区老松町63-10",
        venue_ward="西区",
        lat=35.4445,
        lon=139.6235,
    )
