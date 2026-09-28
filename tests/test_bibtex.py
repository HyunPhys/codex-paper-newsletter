from pathlib import Path

from paper_newsletter.bibtex import parse_fields, summarize_bibtex


def test_summarize_bibtex(tmp_path: Path) -> None:
    bib = tmp_path / "papers.bib"
    bib.write_text(
        """@article{key,
  title = {My Useful Paper},
  year = {2025},
  journal = {Great Journal},
  keywords = {language models, retrieval},
  abstract = {This paper studies retrieval for language models.}
}
""",
        encoding="utf-8",
    )
    summary = summarize_bibtex(bib)
    assert "My Useful Paper" in summary
    assert "language models" in summary


def test_summarize_bibtex_represents_entries_after_long_abstracts(tmp_path: Path) -> None:
    bib = tmp_path / "papers.bib"
    entries = []
    for index in range(100):
        entries.append(
            f"""@article{{key{index},
  title = {{Paper {index}}},
  year = {2020 + index % 6},
  journal = {{Journal}},
  keywords = {{moire, domain wall}},
  abstract = {{{'long abstract ' * 100}}}
}}
"""
        )
    bib.write_text("\n".join(entries), encoding="utf-8")

    summary = summarize_bibtex(bib)

    assert "Parsed entries: 100" in summary
    assert "Paper 0" in summary
    assert "Paper 99" in summary
    assert "long abstract" not in summary


def test_parse_fields_accepts_unbraced_numeric_year() -> None:
    fields = parse_fields("""@article{key,
  title = {Example},
  year = 2026,
}
""")

    assert fields["year"] == "2026"
