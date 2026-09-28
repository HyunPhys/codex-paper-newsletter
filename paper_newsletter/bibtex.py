from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .rss import clean_text


FIELD_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*[{\"].*", re.M)


def summarize_bibtex(
    path: Path,
    max_entries: int | None = None,
    max_chars: int = 80_000,
) -> str:
    """Build compact scoring context that represents the whole Zotero library.

    Abstracts are deliberately omitted here. A few long abstracts used to fill
    the context budget after roughly 40 entries, which biased scoring toward the
    beginning of the BibTeX export. Titles, venues, and keywords preserve much
    broader coverage for semantic matching.
    """
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    entries = split_entries(text)
    if max_entries is not None:
        entries = entries[:max_entries]

    records: list[dict[str, str]] = []
    keyword_counts: Counter[str] = Counter()
    for entry in entries:
        fields = parse_fields(entry)
        title = fields.get("title", "")
        if not title:
            continue
        records.append(fields)
        keywords = fields.get("keywords", "") or fields.get("tags", "")
        keyword_counts.update(semantic_keywords(keywords))

    header = [
        "# Zotero Library Overview",
        f"Parsed entries: {len(records)}",
    ]
    if keyword_counts:
        common = ", ".join(
            f"{keyword} ({count})" for keyword, count in keyword_counts.most_common(40)
        )
        header.append(f"Frequent library keywords: {common}")
    header.extend(["", "# Zotero Title Catalog"])

    summaries: list[str] = []
    for fields in records:
        title = fields["title"]
        year = fields.get("year", "") or fields.get("date", "")[:4]
        keywords = ", ".join(
            semantic_keywords(fields.get("keywords", "") or fields.get("tags", ""))
        )
        journal = fields.get("journal", "") or fields.get("booktitle", "")
        line = f"- {title}"
        if year:
            line += f" ({year})"
        if journal:
            line += f", {journal}"
        if keywords:
            line += f". Keywords: {keywords[:240]}"
        clean_line = clean_text(line)
        projected = len("\n".join(header + summaries + [clean_line]))
        if projected > max_chars:
            break
        summaries.append(clean_line)

    if len(summaries) < len(records):
        header.append(
            f"Context limit: included {len(summaries)} of {len(records)} parsed entries."
        )
    return "\n".join(header + summaries)


def semantic_keywords(value: str) -> list[str]:
    """Drop Zotero workflow symbols while retaining topical keywords."""
    keywords: list[str] = []
    for keyword in re.split(r"\s*[,;]\s*", value):
        keyword = clean_text(keyword).strip().lower()
        if keyword and re.search(r"[A-Za-z0-9가-힣]{2,}", keyword):
            keywords.append(keyword)
    return keywords


def split_entries(text: str) -> list[str]:
    starts = [match.start() for match in re.finditer(r"@[A-Za-z]+\s*[{(]", text)]
    entries: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        entries.append(text[start:end])
    return entries


def parse_fields(entry: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = entry.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*(.*)", line)
        if not match:
            i += 1
            continue
        name = match.group(1).lower()
        value = match.group(2).strip()
        if not value:
            i += 1
            continue
        opener = value[0] if value[0] in "{\"'" else ""
        rest = value[1:] if opener else value
        closer = "}" if opener == "{" else opener
        value_parts = [rest]
        balance = rest.count("{") - rest.count("}") if opener == "{" else 0
        while opener and i + 1 < len(lines) and not field_complete(value_parts[-1], closer, balance):
            i += 1
            value_parts.append(lines[i].strip())
            if opener == "{":
                balance += value_parts[-1].count("{") - value_parts[-1].count("}")
        raw = " ".join(value_parts).rstrip(",").strip()
        fields[name] = clean_bib_value(raw, closer) if opener else clean_text(raw)
        i += 1
    return fields


def field_complete(last_part: str, closer: str, balance: int) -> bool:
    if closer == "}":
        return balance <= 0 and last_part.rstrip().endswith(("},", "}"))
    return last_part.rstrip().endswith((f"{closer},", closer))


def clean_bib_value(value: str, closer: str) -> str:
    value = value.rstrip(",").strip()
    if value.startswith(("{", "\"", "'")):
        value = value[1:]
    if value.endswith(closer):
        value = value[:-1]
    value = value.replace("{", "").replace("}", "")
    return clean_text(value)
