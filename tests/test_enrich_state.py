import json
from pathlib import Path

from paper_newsletter.enrich import enrich_paper
from paper_newsletter.models import Paper
from paper_newsletter.state import ProcessedState


def test_enrich_preserves_multiple_citation_authors(monkeypatch) -> None:
    html = b"""
<html><head>
  <meta name="citation_title" content="Better title">
  <meta name="citation_author" content="Ada Lovelace">
  <meta name="citation_author" content="Grace Hopper">
  <meta name="citation_doi" content="10.1234/example">
</head></html>
"""
    monkeypatch.setattr("paper_newsletter.enrich.fetch_url", lambda *_args, **_kwargs: html)

    paper = enrich_paper(Paper(title="Title", url="https://example.org/paper"), 1, "agent")

    assert paper.title == "Better title"
    assert paper.authors == ["Ada Lovelace", "Grace Hopper"]
    assert paper.doi == "10.1234/example"


def test_processed_state_backs_up_corrupt_json(tmp_path: Path) -> None:
    state_path = tmp_path / "processed.json"
    state_path.write_text("{not json", encoding="utf-8")

    state = ProcessedState(state_path)
    state.add_many(["url:https://example.org/paper"])
    state.save()

    assert (tmp_path / "processed.json.corrupt").exists()
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "processed": ["url:https://example.org/paper"]
    }
