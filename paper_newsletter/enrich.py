from __future__ import annotations

import re
from html.parser import HTMLParser

from .models import Paper
from .rss import clean_text, fetch_url


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.citation_authors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attr = {k.lower(): (v or "") for k, v in attrs}
        name = (attr.get("name") or attr.get("property") or "").lower()
        content = attr.get("content", "").strip()
        if name == "citation_author" and content:
            self.citation_authors.append(content)
        if name and content and name not in self.meta:
            self.meta[name] = content


def enrich_paper(paper: Paper, timeout: int, user_agent: str) -> Paper:
    if len(paper.summary) >= 240 and paper.doi:
        return paper
    if not paper.url.startswith(("http://", "https://")):
        return paper
    try:
        raw = fetch_url(paper.url, timeout=timeout, user_agent=user_agent, retries=1, max_bytes=1_000_000)
    except Exception:
        return paper
    html = raw[:1_000_000].decode("utf-8", errors="ignore")
    parser = MetadataParser()
    parser.feed(html)
    meta = parser.meta

    title = first_meta(meta, ["citation_title", "dc.title", "og:title"]) or paper.title
    abstract = first_meta(
        meta,
        ["citation_abstract", "description", "dc.description", "og:description"],
    )
    doi = (
        first_meta(meta, ["citation_doi", "dc.identifier"])
        or extract_doi_from_html(html)
        or paper.doi
    )
    authors = list(paper.authors)
    if parser.citation_authors:
        authors = parser.citation_authors

    paper.title = clean_text(title)
    if abstract and len(abstract) > len(paper.summary):
        paper.summary = clean_text(abstract)
    paper.doi = normalize_doi(doi)
    paper.authors = [clean_text(author) for author in authors if clean_text(author)]
    return paper


def first_meta(meta: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        if meta.get(key):
            return meta[key]
    return ""


def extract_doi_from_html(html: str) -> str:
    match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", html, flags=re.I)
    return match.group(0) if match else ""


def normalize_doi(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^(doi:|https?://(?:dx\.)?doi\.org/)", "", value, flags=re.I)
    return value.rstrip(".").lower()
