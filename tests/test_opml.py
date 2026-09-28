from pathlib import Path

from paper_newsletter.opml import parse_opml


def test_parse_nested_opml(tmp_path: Path) -> None:
    opml = tmp_path / "feeds.opml"
    opml.write_text(
        """<?xml version="1.0"?>
<opml><body>
  <outline text="Folder">
    <outline text="Journal A" xmlUrl="https://a.example/rss"/>
    <outline title="Journal B" xmlUrl="https://b.example/rss"/>
  </outline>
</body></opml>""",
        encoding="utf-8",
    )
    feeds = parse_opml(opml)
    assert [feed.title for feed in feeds] == ["Journal A", "Journal B"]
    assert [feed.url for feed in feeds] == ["https://a.example/rss", "https://b.example/rss"]
