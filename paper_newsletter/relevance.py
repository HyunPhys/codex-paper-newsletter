from __future__ import annotations

import re

from .models import Paper, ScoredPaper
from .rss import clean_text


def score_paper(paper: Paper, profile: str, my_papers: str) -> ScoredPaper:
    """Provide an offline fallback; daily LLM scoring belongs to Codex automation."""
    include = _section_terms(profile, "include keywords")
    exclude = _section_terms(profile, "exclude keywords")
    text = clean_text(f"{paper.title} {paper.summary}").lower()
    positive = sum(1 for term in include if term in text)
    negative = sum(1 for term in exclude if term in text)
    library_matches = sum(1 for term in _top_terms(my_papers) if term in text)
    score = clamp_half_step(
        1.0 + min(3.0, positive) + min(1.0, library_matches * 0.25) - negative * 1.5
    )
    reason = (
        f"Offline keyword fallback: {positive} profile match(es), "
        f"{library_matches} library-context match(es), {negative} exclusion match(es)."
    )
    summary = clean_text(paper.summary) or "No abstract was supplied by the source feed."
    return ScoredPaper(paper, score, reason, summary, clean_text(paper.title))


def _section_terms(profile: str, heading: str) -> list[str]:
    active = False
    terms: list[str] = []
    for line in profile.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            active = heading in stripped.lower()
        elif active and stripped.startswith(("-", "*")):
            term = stripped[1:].strip().lower()
            if term:
                terms.append(term)
    return terms


def _top_terms(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{3,}", text.lower())
    ignored = {"this", "that", "with", "from", "paper", "journal", "title", "year"}
    counts: dict[str, int] = {}
    for word in words:
        if word not in ignored:
            counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)[:100]]


def clamp_half_step(value: float) -> float:
    return max(0.0, min(5.0, round(value * 2) / 2))
