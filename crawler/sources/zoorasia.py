"""よこはま動物園ズーラシア — list page on hama-midorinokyokai.or.jp."""
from __future__ import annotations

import httpx

from ._zoo_common import parse_zoo_list
from .base import SourceMeta

META = SourceMeta(
    id="zoorasia",
    name="よこはま動物園ズーラシア",
    url="https://www.hama-midorinokyokai.or.jp/zoo/zoorasia/event/",
)


def fetch_events(client: httpx.Client) -> list[dict]:
    return parse_zoo_list(
        client=client,
        list_url=META.url,
        source=META,
        venue_name="よこはま動物園ズーラシア",
        venue_address="横浜市旭区上白根町1175-1",
        venue_ward="旭区",
        lat=35.5046,
        lon=139.5188,
    )
