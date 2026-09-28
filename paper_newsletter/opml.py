from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .models import Feed


def parse_opml(path: Path) -> list[Feed]:
    tree = ET.parse(path)
    root = tree.getroot()
    feeds: list[Feed] = []
    seen: set[str] = set()

    for outline in root.findall(".//outline"):
        url = outline.attrib.get("xmlUrl") or outline.attrib.get("xmlurl")
        if not url:
            continue
        normalized = url.strip()
        if not normalized or normalized in seen:
            continue
        title = (
            outline.attrib.get("title")
            or outline.attrib.get("text")
            or normalized
        ).strip()
        feeds.append(Feed(title=title, url=normalized))
        seen.add(normalized)

    return feeds
