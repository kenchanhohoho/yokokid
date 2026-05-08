"""Crawler entry point.

Runs every source module, merges the results, and writes
public/data/events.json. If every source fails, the existing JSON file is
left untouched so the site does not go blank after a transient failure.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from crawler.sources import ALL_SOURCES
from crawler.sources.base import JST, make_client

log = logging.getLogger("crawl")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "public" / "data" / "events.json"


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    all_events: list[dict] = []
    successes: list[str] = []
    failures: list[str] = []

    with make_client() as client:
        for mod in ALL_SOURCES:
            name = getattr(mod, "META").name
            try:
                events = mod.fetch_events(client)
                all_events.extend(events)
                if events:
                    successes.append(f"{name}({len(events)})")
                else:
                    successes.append(f"{name}(0)")
            except Exception as exc:
                log.exception("%s failed: %s", name, exc)
                failures.append(name)

    # Dedupe by id, keep first occurrence.
    seen: set[str] = set()
    unique: list[dict] = []
    for e in all_events:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        unique.append(e)

    if not unique:
        log.warning("no events collected; leaving existing file untouched")
        if failures:
            return 1
        return 0

    payload = {
        "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
        "events": unique,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUTPUT)
    log.info("wrote %d events to %s", len(unique), OUTPUT)
    log.info("sources: success=%s failures=%s", successes, failures)
    return 0


if __name__ == "__main__":
    sys.exit(run())
