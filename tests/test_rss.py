from paper_newsletter.models import Feed
import pytest
import urllib.error

from paper_newsletter.rss import dedupe_papers, fetch_url, is_retryable_fetch_error, parse_feed


def test_parse_rss_and_dedupe() -> None:
    raw = b"""<?xml version="1.0"?>
<rss><channel>
  <item>
    <title>Relevant Paper</title>
    <link>https://example.org/paper</link>
    <description>Abstract with DOI 10.1234/ABC.1</description>
    <pubDate>Mon, 04 May 2026 00:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Duplicate Paper</title>
    <link>https://example.org/other</link>
    <description>Same DOI 10.1234/ABC.1</description>
  </item>
</channel></rss>"""
    papers = parse_feed(raw, Feed(title="Journal", url="https://feed.example"))
    unique = dedupe_papers(papers)
    assert len(unique) == 1
    assert unique[0].doi == "10.1234/abc.1"


def test_parse_atom() -> None:
    raw = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Atom Paper</title>
    <link href="https://example.org/atom-paper"/>
    <summary>Atom abstract</summary>
    <updated>2026-05-04T00:00:00Z</updated>
  </entry>
</feed>"""
    papers = parse_feed(raw, Feed(title="Atom Journal", url="https://feed.example"))
    assert len(papers) == 1
    assert papers[0].title == "Atom Paper"
    assert papers[0].url == "https://example.org/atom-paper"


def test_parse_rdf_rss1_feed() -> None:
    raw = b"""<?xml version="1.0"?>
<rdf:RDF
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns="http://purl.org/rss/1.0/"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/">
  <item rdf:about="https://example.org/rdf-paper">
    <title>RDF Paper</title>
    <link>https://example.org/rdf-paper</link>
    <description>RDF abstract</description>
    <dc:creator>A. Author</dc:creator>
    <dc:date>2026-05-06T00:00:00Z</dc:date>
    <prism:doi>10.5555/rdf.1</prism:doi>
  </item>
</rdf:RDF>"""
    papers = parse_feed(raw, Feed(title="RDF Journal", url="https://feed.example"))
    assert len(papers) == 1
    assert papers[0].title == "RDF Paper"
    assert papers[0].doi == "10.5555/rdf.1"
    assert papers[0].authors == ["A. Author"]


def test_parse_authors_and_doi_from_description() -> None:
    raw = b"""<?xml version="1.0"?>
<rss><channel>
  <item>
    <title>Metadata Paper</title>
    <link>https://example.org/metadata</link>
    <description>Publication date: July 2026 Source: Journal Author(s): Ada Lovelace, Grace Hopper DOI : 10.9999/meta.1</description>
  </item>
</channel></rss>"""
    papers = parse_feed(raw, Feed(title="Journal", url="https://feed.example"))
    assert papers[0].authors == ["Ada Lovelace", "Grace Hopper"]
    assert papers[0].doi == "10.9999/meta.1"


def test_fetch_url_rejects_oversized_response(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size):
            return b"abcdef"

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse())

    with pytest.raises(ValueError, match="exceeded"):
        fetch_url("https://example.org/feed", timeout=1, user_agent="agent", retries=1, max_bytes=5)


def test_permanent_http_errors_are_not_retryable() -> None:
    forbidden = urllib.error.HTTPError("https://example.org", 403, "Forbidden", {}, None)
    throttled = urllib.error.HTTPError("https://example.org", 429, "Slow down", {}, None)

    assert not is_retryable_fetch_error(forbidden)
    assert is_retryable_fetch_error(throttled)
