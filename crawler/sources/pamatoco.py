"""パマトコ（横浜市子育て応援サイト）— stub.

The site uses category and tag pages rather than a single event feed; a robust
parser needs per-page handling. Implemented as v1.1.
"""
from __future__ import annotations

import logging

import httpx

from .base import SourceMeta

log = logging.getLogger(__name__)

META = SourceMeta(
    id="pamatoco",
    name="パマトコ（横浜市子育て応援サイト）",
    url="https://pamatoco.city.yokohama.lg.jp/",
)


def fetch_events(client: httpx.Client) -> list[dict]:
    log.warning("pamatoco: parser not implemented yet (planned for v1.1)")
    return []
