"""横浜市西区役所 子育てイベント — stub for v1.1."""
from __future__ import annotations

import logging

import httpx

from .base import SourceMeta

log = logging.getLogger(__name__)

META = SourceMeta(
    id="nishi",
    name="横浜市西区役所",
    url="https://www.city.yokohama.lg.jp/nishi/",
)


def fetch_events(client: httpx.Client) -> list[dict]:
    log.warning("nishi: parser not implemented yet (planned for v1.1)")
    return []
