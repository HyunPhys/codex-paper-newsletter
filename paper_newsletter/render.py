from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from .models import ScoredPaper


SourceStats = list[tuple[str, int, int, int]]


DEFAULT_TEMPLATE = """# Daily Paper Digest - {{date}}

**{{summary_line}}**

## At a glance

- **Relevant papers:** {{relevant_count}}
- **Inclusion threshold:** {{threshold}}/5.0
- **Top source mix:** {{source_summary}}
- **Candidates below threshold:** {{skipped_count}}

## Top 5

{{top_papers}}

## All relevant papers

{{all_papers_table}}

## Broad field picks

{{broad_papers}}

## Run details

Generated for the Korean calendar day. Scores are personalized to the research profile and Zotero context.
"""


def render_digest(
    scored: list[ScoredPaper],
    skipped_count: int,
    today: date,
    top_n: int = 5,
    template_path: Path | None = None,
    threshold: float = 3.0,
    broad_picks: list[ScoredPaper] | None = None,
) -> str:
    top = scored[:top_n]
    rest = scored[top_n:]
    template = load_template(template_path)
    # Template replacement is intentionally simple: the template is local and the
    # allowed placeholders are documented in docs/user-manual.md.
    values = {
        "date": today.isoformat(),
        "summary_line": f"Found {len(scored)} relevant papers for today's digest.",
        "relevant_count": str(len(scored)),
        "threshold": f"{threshold:.1f}",
        "source_summary": render_source_summary(scored),
        "skipped_count": str(skipped_count),
        "top_papers": render_top_papers(top),
        "other_papers": render_other_papers(rest),
        "all_papers_table": render_all_papers_table(scored),
        "broad_papers": render_broad_papers_markdown(broad_picks or []),
    }
    body = template
    for key, value in values.items():
        body = body.replace("{{" + key + "}}", value)
    return body.strip() + "\n"


def load_template(template_path: Path | None) -> str:
    if template_path and template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return DEFAULT_TEMPLATE


def render_source_summary(scored: list[ScoredPaper]) -> str:
    if not scored:
        return "none"
    counts = Counter(item.paper.feed_title or "Unknown" for item in scored)
    return ", ".join(f"{feed} ({count})" for feed, count in counts.most_common(4))


def render_top_papers(top: list[ScoredPaper]) -> str:
    lines: list[str] = [
    ]
    if not top:
        return "No papers met today's inclusion criteria."
    for index, item in enumerate(top, 1):
        paper = item.paper
        lines.extend(
            [
                f"### {index}. {paper.title}",
                "",
                f"**Score: {item.score:.1f}/5.0**",
                "",
                f"**Why it matters:** {item.reason}",
                "",
                f"**Codex summary:** {item.detailed_summary}",
                "",
                f"**Abstract:** {paper.summary or 'Abstract not available from the feed or article page.'}",
                "",
                f"- **Authors:** {', '.join(paper.authors[:8]) if paper.authors else 'Unknown'}",
                f"- **Source:** {paper.feed_title or 'Unknown'}",
                f"- **Link:** {paper.url}",
                f"- **DOI:** {paper.doi or 'Unknown'}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def render_other_papers(rest: list[ScoredPaper]) -> str:
    if not rest:
        return "No additional relevant papers beyond the Top 5."
    lines: list[str] = []
    for item in rest:
        paper = item.paper
        lines.append(f"- **{item.score:.1f}/5.0** [{paper.title}]({paper.url}) - {item.one_line_summary}")
    return "\n".join(lines)


def render_all_papers_table(scored: list[ScoredPaper]) -> str:
    if not scored:
        return "No relevant papers."
    lines = [
        "| number | score | journal name | paper title |",
        "| ---: | ---: | --- | --- |",
    ]
    ordered = sorted(
        scored,
        key=lambda item: (item.score, item.paper.published_or_min()),
        reverse=True,
    )
    for index, item in enumerate(ordered, 1):
        paper = item.paper
        title = escape_table_cell(paper.title)
        journal = escape_table_cell(paper.feed_title or "Unknown")
        if paper.url:
            title = f"[{title}]({paper.url})"
        lines.append(f"| **{index}** | **{item.score:.1f}** | {journal} | {title} |")
    return "\n".join(lines)


def escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def render_broad_papers_markdown(items: list[ScoredPaper]) -> str:
    if not items:
        return "No additional broad-field pick today."
    lines: list[str] = []
    for index, item in enumerate(items, 1):
        paper = item.paper
        title = f"[{paper.title}]({paper.url})" if paper.url else paper.title
        lines.extend(
            [
                f"### {index}. {title}",
                "",
                f"**Why broaden out:** {item.broad_interest_reason}",
                "",
                f"- **Source:** {paper.feed_title or 'Unknown'}",
                f"- **Broad-interest score:** {item.broad_interest_score:.1f}/5.0",
                "",
                item.one_line_summary or item.detailed_summary,
                "",
            ]
        )
    return "\n".join(lines).strip()


def render_email_text(
    scored: list[ScoredPaper],
    skipped_count: int,
    today: date,
    threshold: float,
    top_n: int = 5,
    feed_errors: list[str] | None = None,
    source_stats: SourceStats | None = None,
    broad_picks: list[ScoredPaper] | None = None,
    developer_name: str = "Byunghyun Kim",
    developer_email: str = "bhkim133@gmail.com",
    project_url: str = "",
) -> str:
    """Render a clean plain-text fallback without Markdown syntax."""
    lines = [
        f"Daily Paper Digest - {today.isoformat()}",
        "",
        f"Relevant papers: {len(scored)}",
        f"Broad field picks: {len(broad_picks or [])}",
        f"Inclusion threshold: {threshold:.1f}/5.0",
        f"Candidates below threshold: {skipped_count}",
        f"Top source mix: {render_source_summary(scored)}",
    ]
    if feed_errors:
        lines.extend(["", "FEED COLLECTION WARNING"])
        lines.extend(f"- {display_text(error)}" for error in feed_errors)

    lines.extend(["", f"TOP {min(top_n, len(scored))}", ""])
    if not scored:
        lines.append("No papers met today's inclusion criteria.")
    for index, item in enumerate(scored[:top_n], 1):
        paper = item.paper
        lines.extend(
            [
                f"{index}. {display_text(paper.title)}",
                f"Score: {item.score:.1f}/5.0",
                f"Why it matters: {display_text(item.reason)}",
                f"Codex summary: {display_text(item.detailed_summary)}",
                f"Abstract: {display_text(paper.summary) if paper.summary else 'Abstract not available from the feed or article page.'}",
                f"Authors: {'; '.join(display_text(author) for author in paper.authors[:8]) if paper.authors else 'Unknown'}",
                f"Source: {display_text(paper.feed_title or 'Unknown')}",
                f"Link: {paper.url}",
                f"DOI: {paper.doi or 'Unknown'}",
                "",
            ]
        )

    lines.extend(["ALL RELEVANT PAPERS", ""])
    for index, item in enumerate(scored, 1):
        lines.append(
            f"{index}. [{item.score:.1f}] {display_text(item.paper.title)} "
            f"- {display_text(item.paper.feed_title or 'Unknown')}"
        )
        lines.append(f"   {item.paper.url}")

    lines.extend(["", "BROAD FIELD PICKS", ""])
    if not broad_picks:
        lines.append("No additional broad-field pick today.")
    for index, item in enumerate(broad_picks or [], 1):
        paper = item.paper
        lines.extend(
            [
                f"{index}. {display_text(paper.title)}",
                f"Why broaden out: {display_text(item.broad_interest_reason)}",
                f"Source: {display_text(paper.feed_title or 'Unknown')}",
                f"Link: {paper.url}",
                f"Summary: {display_text(item.one_line_summary or item.detailed_summary)}",
                "",
            ]
        )

    lines.extend(["", "JOURNAL / FEED SCREENING SUMMARY", ""])
    lines.append("Journal / feed | Received candidates | Passed | Below threshold")
    lines.append("-" * 72)
    for source, received, passed, failed in source_stats or []:
        lines.append(f"{display_text(source)} | {received} | {passed} | {failed}")
    total_received = sum(row[1] for row in source_stats or [])
    total_passed = sum(row[2] for row in source_stats or [])
    total_failed = sum(row[3] for row in source_stats or [])
    lines.append(f"TOTAL | {total_received} | {total_passed} | {total_failed}")
    lines.append(
        "Received candidates are papers evaluated after date, deduplication, "
        "and processed-state filters."
    )
    lines.extend(["", f"Developed by {developer_name}"])
    if developer_email:
        lines.append(f"Contact: {developer_email}")
    if project_url:
        lines.append(f"Project: {project_url}")
    return "\n".join(lines).strip() + "\n"


def render_email_html(
    scored: list[ScoredPaper],
    skipped_count: int,
    today: date,
    threshold: float,
    top_n: int = 5,
    feed_errors: list[str] | None = None,
    source_stats: SourceStats | None = None,
    broad_picks: list[ScoredPaper] | None = None,
    developer_name: str = "Byunghyun Kim",
    developer_email: str = "bhkim133@gmail.com",
    project_url: str = "",
) -> str:
    """Render email-safe HTML with inline styles for Gmail and mobile clients."""
    warning = ""
    if feed_errors:
        warning_items = "".join(f"<li>{html_text(error)}</li>" for error in feed_errors)
        warning = (
            '<div style="margin:20px 0;padding:12px 14px;border-left:4px solid #b45309;'
            'background:#fff7ed;color:#7c2d12;">'
            '<strong>Feed collection warning</strong>'
            f'<ul style="margin:8px 0 0;padding-left:20px;">{warning_items}</ul></div>'
        )

    stats_rows: list[str] = []
    for index, (source, received, passed, failed) in enumerate(source_stats or []):
        background = "#f9fafb" if index % 2 else "#ffffff"
        stats_rows.append(
            f'<tr style="background:{background};">'
            f'<td style="padding:8px;border-bottom:1px solid #e5e7eb;">{html_text(source)}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center;">{received}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center;color:#166534;font-weight:700;">{passed}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center;color:#6b7280;">{failed}</td>'
            '</tr>'
        )
    total_received = sum(row[1] for row in source_stats or [])
    total_passed = sum(row[2] for row in source_stats or [])
    total_failed = sum(row[3] for row in source_stats or [])
    stats_rows.append(
        '<tr style="background:#e5e7eb;font-weight:700;">'
        '<td style="padding:9px 8px;">Total</td>'
        f'<td style="padding:9px 8px;text-align:center;">{total_received}</td>'
        f'<td style="padding:9px 8px;text-align:center;color:#166534;">{total_passed}</td>'
        f'<td style="padding:9px 8px;text-align:center;">{total_failed}</td>'
        '</tr>'
    )
    screening_table = (
        '<h2 style="margin:28px 0 12px;font-size:20px;">Journal / feed screening summary</h2>'
        '<div style="overflow-x:auto;">'
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        '<thead><tr style="background:#e5e7eb;">'
        '<th style="padding:8px;text-align:left;">Journal / feed</th>'
        '<th style="padding:8px;text-align:center;">Received</th>'
        '<th style="padding:8px;text-align:center;">Passed</th>'
        '<th style="padding:8px;text-align:center;">Below</th>'
        f'</tr></thead><tbody>{"".join(stats_rows)}</tbody></table></div>'
        '<p style="margin:8px 0 0;color:#6b7280;font-size:12px;line-height:1.5;">'
        'Received means candidates evaluated after date, deduplication, and processed-state filters. '
        f'Passed means score at or above {threshold:.1f}/5.0.</p>'
    )

    top_sections: list[str] = []
    for index, item in enumerate(scored[:top_n], 1):
        paper = item.paper
        title = html_text(paper.title)
        title_html = html_link(paper.url, title) if paper.url else title
        authors = "; ".join(html_text(author) for author in paper.authors[:8]) or "Unknown"
        doi = html_text(paper.doi or "Unknown")
        if paper.doi:
            doi = html_link(f"https://doi.org/{paper.doi}", doi)
        top_sections.append(
            '<div style="padding:20px 0;border-bottom:1px solid #d1d5db;">'
            f'<div style="margin-bottom:6px;color:#374151;font-size:13px;font-weight:700;">'
            f'#{index} &nbsp; {item.score:.1f}/5.0</div>'
            f'<h2 style="margin:0 0 10px;font-size:19px;line-height:1.35;color:#111827;">{title_html}</h2>'
            f'<p style="margin:0 0 12px;line-height:1.55;"><strong>Why it matters:</strong> {html_text(item.reason)}</p>'
            f'<p style="margin:0 0 12px;line-height:1.6;color:#1f2937;"><strong>Codex summary:</strong> '
            f'{html_text(item.detailed_summary)}</p>'
            '<div style="margin:0 0 14px;padding:12px 14px;background:#f9fafb;border-left:3px solid #64748b;'
            'line-height:1.6;color:#374151;">'
            f'<strong>Abstract:</strong> {html_text(paper.summary) if paper.summary else "Abstract not available from the feed or article page."}'
            '</div>'
            '<div style="font-size:13px;line-height:1.6;color:#4b5563;">'
            f'<div><strong>Authors:</strong> {authors}</div>'
            f'<div><strong>Source:</strong> {html_text(paper.feed_title or "Unknown")}</div>'
            f'<div><strong>DOI:</strong> {doi}</div>'
            '</div></div>'
        )
    if not top_sections:
        top_sections.append("<p>No papers met today's inclusion criteria.</p>")

    broad_sections: list[str] = []
    for index, item in enumerate(broad_picks or [], 1):
        paper = item.paper
        title = html_text(paper.title)
        title_html = html_link(paper.url, title) if paper.url else title
        broad_sections.append(
            '<div style="padding:16px 0;border-bottom:1px solid #d1d5db;">'
            f'<div style="margin-bottom:5px;color:#475569;font-size:12px;font-weight:700;">'
            f'#{index} &nbsp; Broad-interest {item.broad_interest_score:.1f}/5.0</div>'
            f'<h3 style="margin:0 0 8px;font-size:17px;line-height:1.4;color:#111827;">{title_html}</h3>'
            f'<p style="margin:0 0 8px;line-height:1.55;"><strong>Why broaden out:</strong> '
            f'{html_text(item.broad_interest_reason)}</p>'
            f'<p style="margin:0 0 8px;line-height:1.55;color:#374151;">'
            f'{html_text(item.one_line_summary or item.detailed_summary)}</p>'
            f'<div style="font-size:13px;color:#6b7280;"><strong>Source:</strong> '
            f'{html_text(paper.feed_title or "Unknown")}</div></div>'
        )
    if not broad_sections:
        broad_sections.append(
            '<p style="color:#6b7280;">No additional broad-field pick today.</p>'
        )
    broad_section = (
        '<h2 style="margin:28px 0 4px;font-size:20px;">Broad field picks</h2>'
        '<p style="margin:0 0 4px;color:#6b7280;font-size:13px;line-height:1.5;">'
        'High-impact work from adjacent areas of TEM, solid-state physics, and semiconductors.</p>'
        + "".join(broad_sections)
    )
    footer_links: list[str] = []
    if developer_email:
        footer_links.append(html_link(f"mailto:{developer_email}", html_text(developer_email)))
    if project_url:
        footer_links.append(html_link(project_url, "Public repository"))
    footer = (
        '<div style="margin:32px 0 0;padding:18px 0 4px;border-top:1px solid #d1d5db;'
        'text-align:center;color:#6b7280;font-size:12px;line-height:1.7;">'
        f'Developed by {html_text(developer_name)}'
        + (f'<br>{" &nbsp;|&nbsp; ".join(footer_links)}' if footer_links else "")
        + '</div>'
    )

    rows: list[str] = []
    for index, item in enumerate(scored, 1):
        paper = item.paper
        title = html_text(paper.title)
        title_html = html_link(paper.url, title) if paper.url else title
        background = "#f9fafb" if index % 2 == 0 else "#ffffff"
        rows.append(
            f'<tr style="background:{background};">'
            f'<td style="padding:9px 8px;border-bottom:1px solid #e5e7eb;text-align:center;">{index}</td>'
            f'<td style="padding:9px 8px;border-bottom:1px solid #e5e7eb;text-align:center;font-weight:700;">{item.score:.1f}</td>'
            f'<td style="padding:9px 8px;border-bottom:1px solid #e5e7eb;">{html_text(paper.feed_title or "Unknown")}</td>'
            f'<td style="padding:9px 8px;border-bottom:1px solid #e5e7eb;line-height:1.4;">{title_html}</td>'
            '</tr>'
        )

    return (
        '<!doctype html><html><body style="margin:0;background:#f3f4f6;">'
        '<div style="display:none;max-height:0;overflow:hidden;">'
        f'{len(scored)} relevant papers selected for {today.isoformat()}.</div>'
        '<div style="max-width:760px;margin:0 auto;padding:24px 18px;background:#ffffff;'
        'font-family:Arial,Helvetica,sans-serif;color:#111827;font-size:15px;">'
        f'<h1 style="margin:0 0 6px;font-size:26px;line-height:1.25;">Daily Paper Digest</h1>'
        f'<div style="color:#6b7280;margin-bottom:20px;">{today.isoformat()}</div>'
        '<table role="presentation" style="width:100%;border-collapse:collapse;background:#eef2ff;">'
        '<tr>'
        f'<td style="padding:12px;text-align:center;"><strong>{len(scored)}</strong><br><span style="font-size:12px;color:#4b5563;">Relevant</span></td>'
        f'<td style="padding:12px;text-align:center;"><strong>{len(broad_picks or [])}</strong><br><span style="font-size:12px;color:#4b5563;">Broad picks</span></td>'
        f'<td style="padding:12px;text-align:center;"><strong>{threshold:.1f}</strong><br><span style="font-size:12px;color:#4b5563;">Threshold</span></td>'
        f'<td style="padding:12px;text-align:center;"><strong>{skipped_count}</strong><br><span style="font-size:12px;color:#4b5563;">Below threshold</span></td>'
        '</tr></table>'
        f'{warning}'
        f'<h2 style="margin:26px 0 0;font-size:20px;">Top {min(top_n, len(scored))}</h2>'
        f'{"".join(top_sections)}'
        '<h2 style="margin:28px 0 12px;font-size:20px;">All relevant papers</h2>'
        '<div style="overflow-x:auto;">'
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        '<thead><tr style="background:#e5e7eb;">'
        '<th style="padding:9px 8px;text-align:center;">#</th>'
        '<th style="padding:9px 8px;text-align:center;">Score</th>'
        '<th style="padding:9px 8px;text-align:left;">Source</th>'
        '<th style="padding:9px 8px;text-align:left;">Paper</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        '<p style="margin:26px 0 0;color:#6b7280;font-size:12px;line-height:1.5;">'
        'Scores are personalized to the research profile and Zotero context.</p>'
        f'{broad_section}'
        f'{screening_table}'
        f'{footer}'
        '</div></body></html>'
    )


def display_text(value: str) -> str:
    """Make common LaTeX fragments from scholarly feeds readable in email."""
    text = value or ""
    accents = {
        r"\'e": "é",
        r"\'E": "É",
        r'\"o': "ö",
        r'\"u': "ü",
        r"\`a": "à",
    }
    for source, replacement in accents.items():
        text = text.replace(source, replacement)
    text = re.sub(r"\\(?:mathrm|text)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\$_\{?([^{}$]+)\}?\$", r"\1", text)
    text = text.replace("$", "").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def html_text(value: str) -> str:
    return escape(display_text(value), quote=True)


def html_link(url: str, label_html: str) -> str:
    return f'<a href="{escape(url, quote=True)}" style="color:#1d4ed8;text-decoration:underline;">{label_html}</a>'


def build_source_stats(
    scored: list[ScoredPaper],
    threshold: float,
    all_sources: list[str] | None = None,
) -> SourceStats:
    """Return source totals where received always equals passed plus failed."""
    received = Counter({source: 0 for source in all_sources or []})
    received.update(item.paper.feed_title or "Unknown" for item in scored)
    passed = Counter(
        item.paper.feed_title or "Unknown"
        for item in scored
        if item.score >= threshold
    )
    rows = [
        (source, total, passed[source], total - passed[source])
        for source, total in received.items()
    ]
    return sorted(rows, key=lambda row: (-row[1], row[0].lower()))


def email_payload(subject: str, body: str, body_html: str, to: str) -> str:
    return json.dumps(
        {"subject": subject, "body": body, "body_html": body_html, "to": to},
        ensure_ascii=True,
        indent=2,
    )
