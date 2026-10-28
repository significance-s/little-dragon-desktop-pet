"""Remove retired shipped presets without altering user-created reminders."""
from __future__ import annotations

import hashlib


# Fingerprints avoid redistributing the retired private event's name or date.
RETIRED_TITLE_HASHES = frozenset({
    "ea91784f73395c26a7656207531908af33be3089e515564bbdbab33811d8cf67",
    "4619a4ce55b3f36f36b5fa03dd99a752937fc5600f4354f49c7f57ee9fcb2dbf",
})


def clean_retired_countdown(config: dict) -> dict:
    result = dict(config)
    event = result.get("event_countdown")
    if isinstance(event, dict) and isinstance(event.get("title"), str):
        title = "".join(event["title"].split())
        if hashlib.sha256(title.encode("utf-8")).hexdigest() in RETIRED_TITLE_HASHES:
            result["event_countdown"] = {"enabled": False}
    return result
