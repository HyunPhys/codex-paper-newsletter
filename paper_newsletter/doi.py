from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path


def fill_missing_dois_by_title(items, cache_path: Path, contact_email: str = "") -> None:
    cache = load_cache(cache_path)
    changed = False
    for item in items:
        paper = item.paper
        if paper.doi or not paper.title:
            continue
        cached = cache.get(normalize_title(paper.title))
        if cached:
            paper.doi = cached
            continue
        doi = lookup_doi_by_title(paper.title, contact_email)
        if doi:
            paper.doi = doi
            cache[normalize_title(paper.title)] = doi
            changed = True
    if changed:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=True, indent=2), encoding="utf-8")


def load_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {str(k): str(v) for k, v in data.items()}


def lookup_doi_by_title(title: str, contact_email: str = "") -> str:
    query = urllib.parse.urlencode({"query.title": title, "rows": "3"})
    identity = f" (mailto:{contact_email})" if contact_email else ""
    request = urllib.request.Request(
        f"https://api.crossref.org/works?{query}",
        headers={"User-Agent": f"paper-newsletter/0.1{identity}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return ""
    target = normalize_title(title)
    best_doi = ""
    best_score = 0.0
    for item in data.get("message", {}).get("items", []):
        candidate_titles = item.get("title") or []
        if not candidate_titles:
            continue
        candidate = normalize_title(str(candidate_titles[0]))
        score = SequenceMatcher(None, target, candidate).ratio()
        if score > best_score:
            best_score = score
            best_doi = str(item.get("DOI", "")).lower()
    return best_doi if best_score >= 0.92 else ""


def normalize_title(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()
