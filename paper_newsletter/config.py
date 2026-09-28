from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
import tomllib
from typing import Any


@dataclass(frozen=True)
class Settings:
    feeds_opml: Path = Path("config/feeds.opml")
    profile_md: Path = Path("config/profile.md")
    my_papers_md: Path = Path("config/my_papers.md")
    my_papers_bib: Path = Path("config/my_papers.bib")
    email_template: Path = Path("config/email_template.md")
    state_file: Path = Path("state/processed.json")
    out_dir: Path = Path("out")
    email_to: str = ""
    developer_name: str = "Byunghyun Kim"
    developer_email: str = "bhkim133@gmail.com"
    project_url: str = ""
    crossref_email: str = ""
    threshold: float = 3.0
    top_n: int = 5
    request_timeout_seconds: int = 8
    request_retries: int = 2
    max_response_bytes: int = 10_000_000
    collection_attempts: int = 6
    collection_retry_delay_seconds: int = 180
    dated_feed_lookback_days: int = 4
    arxiv_lookback_days: int = 2
    collection_time: str = "09:40"
    digest_time: str = "10:00"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 "
        "paper-newsletter/0.1"
    )
    timezone_name: str = "Asia/Seoul"

    @classmethod
    def from_toml(cls, path: Path) -> "Settings":
        """Load TOML values while retaining defaults for omitted settings."""
        if not path.exists():
            return cls()
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        flattened = {
            "feeds_opml": raw.get("paths", {}).get("feeds_opml"),
            "profile_md": raw.get("paths", {}).get("profile_md"),
            "my_papers_md": raw.get("paths", {}).get("my_papers_md"),
            "my_papers_bib": raw.get("paths", {}).get("my_papers_bib"),
            "email_template": raw.get("paths", {}).get("email_template"),
            "state_file": raw.get("paths", {}).get("state_file"),
            "out_dir": raw.get("paths", {}).get("out_dir"),
            "email_to": raw.get("newsletter", {}).get("email_to"),
            "developer_name": raw.get("newsletter", {}).get("developer_name"),
            "developer_email": raw.get("newsletter", {}).get("developer_email"),
            "project_url": raw.get("newsletter", {}).get("project_url"),
            "threshold": raw.get("newsletter", {}).get("threshold"),
            "top_n": raw.get("newsletter", {}).get("top_n"),
            "timezone_name": raw.get("newsletter", {}).get("timezone"),
            "collection_attempts": raw.get("collection", {}).get("attempts"),
            "collection_retry_delay_seconds": raw.get("collection", {}).get("retry_delay_seconds"),
            "dated_feed_lookback_days": raw.get("collection", {}).get("dated_feed_lookback_days"),
            "arxiv_lookback_days": raw.get("collection", {}).get("arxiv_lookback_days"),
            "collection_time": raw.get("collection", {}).get("schedule_time"),
            "digest_time": raw.get("digest", {}).get("schedule_time"),
            "crossref_email": raw.get("network", {}).get("crossref_email"),
            "request_timeout_seconds": raw.get("network", {}).get("request_timeout_seconds"),
            "request_retries": raw.get("network", {}).get("request_retries"),
            "max_response_bytes": raw.get("network", {}).get("max_response_bytes"),
        }
        path_fields = {
            "feeds_opml", "profile_md", "my_papers_md", "my_papers_bib",
            "email_template", "state_file", "out_dir",
        }
        valid_names = {item.name for item in fields(cls)}
        values: dict[str, Any] = {}
        for key, value in flattened.items():
            if value is None or key not in valid_names:
                continue
            values[key] = Path(value) if key in path_fields else value
        return cls(**values)

    def with_overrides(self, **overrides: Any) -> "Settings":
        return replace(self, **{key: value for key, value in overrides.items() if value is not None})


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
