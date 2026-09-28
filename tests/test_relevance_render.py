from datetime import date

from paper_newsletter.models import Paper, ScoredPaper
from paper_newsletter.cli import select_broad_interest
from paper_newsletter.models import normalize_url_key
from paper_newsletter.relevance import clamp_half_step, score_paper
from paper_newsletter.render import (
    build_source_stats,
    email_payload,
    render_digest,
    render_email_html,
    render_email_text,
)


def test_half_step_clamp() -> None:
    assert clamp_half_step(3.24) == 3.0
    assert clamp_half_step(3.26) == 3.5
    assert clamp_half_step(99) == 5.0


def test_keyword_scoring_and_rendering() -> None:
    profile = """# Research Profile
## Include Keywords
- language model
## Exclude Keywords
- erratum
"""
    my_papers = "Topics: retrieval augmented generation, biomedical text mining"
    paper = Paper(
        title="A language model for biomedical retrieval",
        url="https://example.org/paper",
        summary="We study retrieval augmented generation for biomedical text mining.",
    )
    scored = score_paper(paper, profile, my_papers)
    assert scored.score >= 3.0
    body = render_digest([scored], skipped_count=2, today=date(2026, 5, 5))
    assert "Top 5" in body
    assert "**Score:" in body
    assert "**Abstract:** We study retrieval augmented generation for biomedical text mining." in body
    assert "**Relevant papers:**" in body
    assert "| number | score | journal name | paper title |" in body
    assert "| **1** |" in body
    assert "Candidates below threshold" in body


def test_paper_key_normalizes_doi_and_url_tracking() -> None:
    doi_paper = Paper(title="A", url="", doi="https://doi.org/10.1234/ABC. ")
    assert doi_paper.key == "doi:10.1234/abc"

    assert normalize_url_key("HTTPS://Example.org/Paper/?utm_source=x&b=2#section") == (
        "https://example.org/Paper?b=2"
    )


def test_email_payload_contains_html_and_readable_plain_text() -> None:
    paper = Paper(
        title=r"Moir\'e bilayer MoTe$_2$",
        url="https://example.org/paper?x=1&y=2",
        feed_title="Example Journal",
        authors=["Ada Lovelace", "Grace Hopper"],
        summary="This is the source abstract.",
        doi="10.1234/example",
    )
    scored = ScoredPaper(
        paper=paper,
        score=4.5,
        reason="Directly relevant.",
        detailed_summary="Detailed summary.",
        one_line_summary="One line.",
    )
    broad = ScoredPaper(
        paper=Paper(
            title="Broad semiconductor methods paper",
            url="https://example.org/broad",
            feed_title="Adjacent Journal",
        ),
        score=2.5,
        reason="Adjacent field.",
        detailed_summary="Broad detailed summary.",
        one_line_summary="Broad one-line summary.",
        broad_interest_score=4.5,
        broad_interest_reason="A field-shaping microscopy method.",
    )

    source_stats = build_source_stats([scored], 3.0)
    plain = render_email_text(
        [scored], 3, date(2026, 9, 22), 3.0,
        feed_errors=["A Journal: timeout"], source_stats=source_stats,
        broad_picks=[broad],
    )
    html = render_email_html(
        [scored], 3, date(2026, 9, 22), 3.0,
        feed_errors=["A Journal: timeout"], source_stats=source_stats,
        broad_picks=[broad],
        project_url="https://github.com/example/codex-paper-newsletter",
    )
    payload = email_payload("Subject", plain, html, "reader@example.org")

    assert "##" not in plain
    assert "**" not in plain
    assert "Moiré bilayer MoTe2" in plain
    assert "Ada Lovelace; Grace Hopper" in plain
    assert "Feed collection warning" in html
    assert "<table" in html
    assert "Journal / feed screening summary" in html
    assert html.rfind("Journal / feed screening summary") > html.rfind("All relevant papers")
    assert html.rfind("Broad field picks") > html.rfind("All relevant papers")
    assert html.rfind("Broad field picks") < html.rfind("Journal / feed screening summary")
    assert "A field-shaping microscopy method." in html
    assert "<strong>Abstract:</strong> This is the source abstract." in html
    assert "Abstract: This is the source abstract." in plain
    assert "Example Journal | 1 | 1 | 0" in plain
    assert "TOTAL | 1 | 1 | 0" in plain
    assert plain.rfind("JOURNAL / FEED SCREENING SUMMARY") > plain.rfind("ALL RELEVANT PAPERS")
    assert plain.rfind("BROAD FIELD PICKS") < plain.rfind("JOURNAL / FEED SCREENING SUMMARY")
    assert "https://example.org/paper?x=1&amp;y=2" in html
    assert '"body_html"' in payload
    assert "Developed by Byunghyun Kim" in plain
    assert "bhkim133@gmail.com" in plain
    assert "Developed by Byunghyun Kim" in html
    assert "Public repository" in html


def test_source_stats_balance_received_passed_and_failed() -> None:
    items = [
        ScoredPaper(Paper("A", "https://example.org/a", feed_title="Journal A"), 4.0, "", "", ""),
        ScoredPaper(Paper("B", "https://example.org/b", feed_title="Journal A"), 2.5, "", "", ""),
        ScoredPaper(Paper("C", "https://example.org/c", feed_title="Journal B"), 3.0, "", "", ""),
    ]

    rows = build_source_stats(items, 3.0, all_sources=["Journal A", "Journal B", "Journal C"])

    assert rows == [
        ("Journal A", 2, 1, 1),
        ("Journal B", 1, 1, 0),
        ("Journal C", 0, 0, 0),
    ]


def test_select_broad_interest_excludes_core_and_limits_to_three() -> None:
    items = [
        ScoredPaper(
            Paper(str(index), f"https://example.org/{index}"),
            3.5 if index == 0 else 2.5,
            "", "", "",
            broad_interest_score=5.0 - index * 0.5,
            broad_interest_reason="Broad value.",
        )
        for index in range(5)
    ]

    selected = select_broad_interest(items, threshold=3.0, limit=3)

    assert [item.paper.title for item in selected] == ["1", "2", "3"]
    assert all(item.score < 3.0 for item in selected)
