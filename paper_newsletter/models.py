from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_NAMES = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid"}


@dataclass(frozen=True)
class Feed:
    title: str
    url: str


@dataclass
class Paper:
    title: str
    url: str
    feed_title: str = ""
    authors: list[str] = field(default_factory=list)
    summary: str = ""
    doi: str = ""
    published: datetime | None = None

    @property
    def key(self) -> str:
        # Processed-state correctness depends on stable keys. Prefer DOI because
        # journal URLs often change through tracking parameters or redirects.
        if self.doi:
            return f"doi:{normalize_doi_key(self.doi)}"
        if self.url:
            return f"url:{normalize_url_key(self.url)}"
        return f"title:{self.title.strip().lower()}"

    def published_or_min(self) -> datetime:
        return self.published or datetime(1970, 1, 1, tzinfo=timezone.utc)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "url": self.url,
            "feed_title": self.feed_title,
            "authors": self.authors,
            "summary": self.summary,
            "doi": self.doi,
            "published": self.published.isoformat() if self.published else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        published = data.get("published")
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            feed_title=data.get("feed_title", ""),
            authors=list(data.get("authors", [])),
            summary=data.get("summary", ""),
            doi=data.get("doi", ""),
            published=datetime.fromisoformat(published) if published else None,
        )


@dataclass
class ScoredPaper:
    paper: Paper
    score: float
    reason: str
    detailed_summary: str
    one_line_summary: str
    broad_interest_score: float = 0.0
    broad_interest_reason: str = ""


def normalize_doi_key(value: str) -> str:
    value = value.strip().lower()
    for prefix in ("doi:", "https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    return value.rstrip(" .")


def normalize_url_key(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or parsed.path
    kept_query = []
    for name, query_value in parse_qsl(parsed.query, keep_blank_values=True):
        lower_name = name.lower()
        # Keep meaningful query parameters, but drop common campaign/click IDs
        # that would create duplicate keys for the same article.
        if lower_name in TRACKING_QUERY_NAMES or lower_name.startswith(TRACKING_QUERY_PREFIXES):
            continue
        kept_query.append((name, query_value))
    query = urlencode(kept_query, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))
