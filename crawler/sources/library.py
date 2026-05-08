"""横浜市立図書館 — stub for v1.1.

The library system distributes per-branch event PDFs and HTML pages; merging
them into a single feed requires per-branch parsers. Implemented as v1.1.
"""
from __future__ import annotations

import logging

import httpx

from .base import SourceMeta

log = logging.getLogger(__name__)

META = SourceMeta(
    id="library",
    name="横浜市立図書館",
    url="https://www.library.city.yokohama.lg.jp/",
)


def fetch_events(client: httpx.Client) -> list[dict]:
    log.warning("library: parser not implemented yet (planned for v1.1)")
    return []
