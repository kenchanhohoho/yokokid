"""アンパンマンこどもミュージアム横浜 — stub for v1.1."""
from __future__ import annotations

import logging

import httpx

from .base import SourceMeta

log = logging.getLogger(__name__)

META = SourceMeta(
    id="anpanman",
    name="アンパンマンこどもミュージアム横浜",
    url="https://www.yokohama-anpanman.jp/",
)


def fetch_events(client: httpx.Client) -> list[dict]:
    log.warning("anpanman: parser not implemented yet (planned for v1.1)")
    return []
