from __future__ import annotations

import email.utils
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from typing import Iterable

from .models import Feed, Paper

ATOM = "{http://www.w3.org/2005/Atom}"
RSS1 = "{http://purl.org/rss/1.0/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"
PRISM = "{http://prismstandard.org/namespaces/basic/2.0/}"
PRISM12 = "{http://prismstandard.org/namespaces/basic/1.2/}"


def fetch_url(url: str, timeout: int, user_agent: str, retries: int = 2, max_bytes: int = 10_000_000) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
            "Accept-Language": "en-US,en;q=0.8",
        },
    )
    last_error: Exception | None = None
    attempts = max(1, retries)
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                # Read one extra byte so oversized feeds fail before they can
                # consume unbounded memory in the scheduled collector.
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise ValueError(f"Response exceeded {max_bytes} bytes: {url}")
                return raw
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1 and is_retryable_fetch_error(exc):
                time.sleep(2 * (attempt + 1))
            else:
                break
    assert last_error is not None
    raise last_error


def is_retryable_fetch_error(exc: Exception) -> bool:
    """Return whether another request could reasonably recover this failure."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 408 or exc.code == 429 or 500 <= exc.code < 600
    if isinstance(exc, (ET.ParseError, ValueError)):
        return False
    return True


def fetch_feed(
    feed: Feed,
    timeout: int,
    user_agent: str,
    retries: int = 2,
    max_bytes: int = 10_000_000,
) -> list[Paper]:
    raw = fetch_url(feed.url, timeout=timeout, user_agent=user_agent, retries=retries, max_bytes=max_bytes)
    return parse_feed(raw, feed)


def parse_feed(raw: bytes, feed: Feed) -> list[Paper]:
    root = ET.fromstring(raw)
    # Feedly exports a mix of RSS 2.0, Atom, and RDF/RSS 1.0 feeds. The parser
    # dispatch stays explicit so journal-specific namespace bugs are easier to see.
    if root.tag == f"{ATOM}feed":
        return list(_parse_atom(root, feed))
    if root.tag.endswith("RDF"):
        return list(_parse_rdf(root, feed))
    return list(_parse_rss(root, feed))


def _parse_rss(root: ET.Element, feed: Feed) -> Iterable[Paper]:
    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link") or _text(item, "guid")
        summary = _first_text(item, ["description", f"{CONTENT}encoded"])
        authors = _authors_from_text(_first_text(item, ["author", f"{DC}creator"]))
        if not authors:
            authors = extract_authors_from_summary(summary)
        doi = _extract_doi(" ".join([title, link, summary]))
        published = _parse_datetime(_first_text(item, ["pubDate", f"{DC}date"]))
        if title or link:
            yield Paper(
                title=clean_text(title) or link,
                url=link.strip(),
                feed_title=feed.title,
                authors=authors,
                summary=clean_text(summary),
                doi=doi,
                published=published,
            )


def _parse_rdf(root: ET.Element, feed: Feed) -> Iterable[Paper]:
    for item in root.findall(f"{RSS1}item"):
        title = _first_text(item, [f"{RSS1}title", f"{DC}title"])
        link = _text(item, f"{RSS1}link")
        summary = _first_text(item, [f"{RSS1}description", f"{CONTENT}encoded"])
        authors = _all_text(item, f"{DC}creator")
        if not authors:
            authors = extract_authors_from_summary(summary)
        doi = normalize_identifier(
            _first_text(
                item,
                [
                    f"{PRISM}doi",
                    f"{PRISM12}doi",
                    f"{DC}identifier",
                ],
            )
        )
        doi = doi or _extract_doi(" ".join([title, link, summary]))
        published = _parse_datetime(
            _first_text(
                item,
                [
                    f"{DC}date",
                    f"{PRISM}publicationDate",
                    f"{PRISM12}publicationDate",
                    f"{PRISM}coverDate",
                    f"{PRISM12}coverDate",
                    f"{PRISM}coverDisplayDate",
                    f"{PRISM12}coverDisplayDate",
                ],
            )
        )
        if title or link:
            yield Paper(
                title=clean_text(title) or link,
                url=link.strip(),
                feed_title=feed.title,
                authors=authors,
                summary=clean_text(summary),
                doi=doi,
                published=published,
            )


def _parse_atom(root: ET.Element, feed: Feed) -> Iterable[Paper]:
    for entry in root.findall(f"{ATOM}entry"):
        title = _text(entry, f"{ATOM}title")
        link = _atom_link(entry)
        summary = _first_text(entry, [f"{ATOM}summary", f"{ATOM}content"])
        authors = [clean_text(a.findtext(f"{ATOM}name") or "") for a in entry.findall(f"{ATOM}author")]
        authors = [a for a in authors if a]
        doi = _extract_doi(" ".join([title, link, summary]))
        published = _parse_datetime(_first_text(entry, [f"{ATOM}published", f"{ATOM}updated"]))
        if title or link:
            yield Paper(
                title=clean_text(title) or link,
                url=link.strip(),
                feed_title=feed.title,
                authors=authors,
                summary=clean_text(summary),
                doi=doi,
                published=published,
            )


def dedupe_papers(papers: Iterable[Paper]) -> list[Paper]:
    seen: set[str] = set()
    unique: list[Paper] = []
    for paper in papers:
        key = paper.key
        if key in seen:
            continue
        seen.add(key)
        unique.append(paper)
    return unique


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _text(node: ET.Element, tag: str) -> str:
    found = node.find(tag)
    return "" if found is None or found.text is None else found.text.strip()


def _first_text(node: ET.Element, tags: list[str]) -> str:
    for tag in tags:
        value = _text(node, tag)
        if value:
            return value
    return ""


def _all_text(node: ET.Element, tag: str) -> list[str]:
    values = [clean_text(found.text or "") for found in node.findall(tag)]
    return [value for value in values if value]


def _atom_link(entry: ET.Element) -> str:
    fallback = ""
    for link in entry.findall(f"{ATOM}link"):
        href = link.attrib.get("href", "").strip()
        if not href:
            continue
        if link.attrib.get("rel", "alternate") == "alternate":
            return href
        fallback = fallback or href
    return fallback


def _authors_from_text(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*(?:,|;|\band\b)\s*", clean_text(value))
    return [part for part in parts if part]


def extract_authors_from_summary(value: str) -> list[str]:
    text = clean_text(value)
    match = re.search(
        r"Author\(s\):\s*(.+?)(?:\s+(?:DOI|Source|Publication date|The content of this RSS Feed)\b|$)",
        text,
        flags=re.I,
    )
    if not match:
        return []
    authors_text = match.group(1).strip()
    authors_text = re.sub(r"\s+and\s+", ", ", authors_text)
    return [author.strip() for author in authors_text.split(",") if author.strip()]


def _extract_doi(value: str) -> str:
    match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", value, flags=re.I)
    return match.group(0).rstrip(".").lower() if match else ""


def normalize_identifier(value: str) -> str:
    value = clean_text(value)
    doi = _extract_doi(value)
    if doi:
        return doi
    return ""


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
