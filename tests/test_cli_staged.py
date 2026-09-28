import json
import pytest
from pathlib import Path
from argparse import Namespace
from datetime import datetime
from zoneinfo import ZoneInfo

from paper_newsletter.cli import (
    collect_candidates,
    in_collection_window,
    in_collection_window_for_feed,
    kst_window,
    main,
    validate_score_coverage,
)
from paper_newsletter.config import Settings
from paper_newsletter.models import Feed, Paper


def test_render_scored_marks_processed(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    scores = tmp_path / "scored.json"
    out_dir = tmp_path / "out"
    state = tmp_path / "state.json"
    payload = tmp_path / "email.json"

    candidates.write_text(
        json.dumps(
            {
                "stats": {"fetched": 1, "candidates": 1, "feed_errors": []},
                "candidates": [
                    {
                        "key": "url:https://example.org/paper",
                        "title": "Codex scored paper",
                        "url": "https://example.org/paper",
                        "feed_title": "Journal",
                        "authors": ["A. Author"],
                        "summary": "Abstract",
                        "doi": "",
                        "published": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    scores.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "key": "url:https://example.org/paper",
                        "score": 4.5,
                        "reason": "사용자 관심사와 직접 관련됩니다.",
                        "detailed_summary": "상세 요약",
                        "one_line_summary": "한 줄 요약",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = main(
        [
            "render-scored",
            "--feeds-opml",
            "config/feeds.opml",
            "--candidates",
            str(candidates),
            "--scores",
            str(scores),
            "--out-dir",
            str(out_dir),
            "--state-file",
            str(state),
            "--send-payload",
            str(payload),
        ]
    )

    assert result == 0
    assert "Codex scored paper" in payload.read_text(encoding="utf-8")
    assert "url:https://example.org/paper" in state.read_text(encoding="utf-8")


def test_render_scored_marks_original_and_enriched_keys(monkeypatch, tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    scores = tmp_path / "scored.json"
    out_dir = tmp_path / "out"
    state = tmp_path / "state.json"
    payload = tmp_path / "email.json"

    candidates.write_text(
        json.dumps(
            {
                "stats": {"fetched": 1, "candidates": 1, "feed_errors": [], "target_date": "2026-05-18"},
                "candidates": [
                    {
                        "key": "url:https://example.org/paper",
                        "title": "DOI enriched paper",
                        "url": "https://example.org/paper",
                        "feed_title": "Journal",
                        "authors": ["A. Author"],
                        "summary": "Abstract",
                        "doi": "",
                        "published": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    scores.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "key": "url:https://example.org/paper",
                        "score": 4.0,
                        "reason": "Relevant.",
                        "detailed_summary": "Detailed.",
                        "one_line_summary": "One line.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "paper_newsletter.cli.fill_missing_dois_by_title",
        lambda relevant, _cache_path, *_args: setattr(relevant[0].paper, "doi", "10.1234/example"),
    )

    result = main(
        [
            "render-scored",
            "--feeds-opml",
            "config/feeds.opml",
            "--candidates",
            str(candidates),
            "--scores",
            str(scores),
            "--out-dir",
            str(out_dir),
            "--state-file",
            str(state),
            "--send-payload",
            str(payload),
        ]
    )

    assert result == 0
    state_text = state.read_text(encoding="utf-8")
    assert "url:https://example.org/paper" in state_text
    assert "doi:10.1234/example" in state_text


def test_render_scored_no_mark_then_mark_processed(monkeypatch, tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    scores = tmp_path / "scored.json"
    out_dir = tmp_path / "out"
    state = tmp_path / "state.json"
    payload = tmp_path / "email.json"

    candidates.write_text(
        json.dumps(
            {
                "stats": {"fetched": 1, "candidates": 1, "feed_errors": [], "target_date": "2026-05-18"},
                "candidates": [
                    {
                        "key": "url:https://example.org/paper",
                        "title": "Deferred mark paper",
                        "url": "https://example.org/paper",
                        "feed_title": "Journal",
                        "authors": ["A. Author"],
                        "summary": "Abstract",
                        "doi": "",
                        "published": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    scores.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "key": "url:https://example.org/paper",
                        "score": 4.0,
                        "reason": "Relevant.",
                        "detailed_summary": "Detailed.",
                        "one_line_summary": "One line.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "paper_newsletter.cli.fill_missing_dois_by_title",
        lambda relevant, _cache_path, *_args: setattr(relevant[0].paper, "doi", "10.1234/deferred"),
    )

    render_result = main(
        [
            "render-scored",
            "--feeds-opml",
            "config/feeds.opml",
            "--candidates",
            str(candidates),
            "--scores",
            str(scores),
            "--out-dir",
            str(out_dir),
            "--state-file",
            str(state),
            "--send-payload",
            str(payload),
            "--no-mark-processed",
        ]
    )

    assert render_result == 0
    assert not state.exists()

    mark_result = main(
        [
            "mark-processed",
            "--feeds-opml",
            "config/feeds.opml",
            "--candidates",
            str(candidates),
            "--scores",
            str(scores),
            "--out-dir",
            str(out_dir),
            "--state-file",
            str(state),
        ]
    )

    assert mark_result == 0
    state_text = state.read_text(encoding="utf-8")
    assert "url:https://example.org/paper" in state_text
    assert "doi:10.1234/deferred" in state_text


def test_render_scored_rejects_stale_scores_without_overwriting_payload(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    scores = tmp_path / "scored.json"
    out_dir = tmp_path / "out"
    state = tmp_path / "state.json"
    payload = tmp_path / "email.json"
    payload.write_text("keep me", encoding="utf-8")

    candidates.write_text(
        json.dumps(
            {
                "stats": {"fetched": 1, "candidates": 1, "feed_errors": [], "target_date": "2026-05-27"},
                "candidates": [
                    {
                        "key": "url:https://example.org/today",
                        "title": "Today paper",
                        "url": "https://example.org/today",
                        "feed_title": "Journal",
                        "authors": [],
                        "summary": "",
                        "doi": "",
                        "published": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    scores.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "key": "url:https://example.org/old",
                        "score": 4.0,
                        "reason": "Old.",
                        "detailed_summary": "Old.",
                        "one_line_summary": "Old.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="does not match candidates"):
        main(
            [
                "render-scored",
                "--feeds-opml",
                "config/feeds.opml",
                "--candidates",
                str(candidates),
                "--scores",
                str(scores),
                "--out-dir",
                str(out_dir),
                "--state-file",
                str(state),
                "--send-payload",
                str(payload),
            ]
        )

    assert payload.read_text(encoding="utf-8") == "keep me"
    assert not state.exists()


def test_mark_processed_rejects_incomplete_scores(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    scores = tmp_path / "scored.json"
    state = tmp_path / "state.json"

    candidates.write_text(
        json.dumps(
            {
                "stats": {"fetched": 2, "candidates": 2, "feed_errors": []},
                "candidates": [
                    {
                        "key": "url:https://example.org/one",
                        "title": "One",
                        "url": "https://example.org/one",
                        "feed_title": "Journal",
                        "authors": [],
                        "summary": "",
                        "doi": "",
                        "published": None,
                    },
                    {
                        "key": "url:https://example.org/two",
                        "title": "Two",
                        "url": "https://example.org/two",
                        "feed_title": "Journal",
                        "authors": [],
                        "summary": "",
                        "doi": "",
                        "published": None,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    scores.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "key": "url:https://example.org/one",
                        "score": 4.0,
                        "reason": "Relevant.",
                        "detailed_summary": "Detailed.",
                        "one_line_summary": "One line.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Missing scores"):
        main(
            [
                "mark-processed",
                "--feeds-opml",
                "config/feeds.opml",
                "--candidates",
                str(candidates),
                "--scores",
                str(scores),
                "--state-file",
                str(state),
            ]
        )

    assert not state.exists()


def test_render_scored_rejects_non_half_step_score(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    scores = tmp_path / "scored.json"
    candidates.write_text(
        json.dumps(
            {
                "stats": {"fetched": 1, "candidates": 1, "feed_errors": []},
                "candidates": [
                    {
                        "key": "url:https://example.org/paper",
                        "title": "Paper",
                        "url": "https://example.org/paper",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    scores.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "key": "url:https://example.org/paper",
                        "score": 3.7,
                        "reason": "Relevant.",
                        "detailed_summary": "Detailed.",
                        "one_line_summary": "Summary.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="half steps"):
        main(
            [
                "render-scored",
                "--feeds-opml",
                "config/feeds.opml",
                "--candidates",
                str(candidates),
                "--scores",
                str(scores),
                "--out-dir",
                str(tmp_path / "out"),
            ]
        )


def test_scoring_schema_v2_requires_broad_interest_fields() -> None:
    candidates = {"url:https://example.org/paper": {"title": "Paper"}}
    scores = {
        "items": [
            {
                "key": "url:https://example.org/paper",
                "score": 3.0,
                "reason": "Relevant.",
                "detailed_summary": "Detailed.",
                "one_line_summary": "Summary.",
            }
        ]
    }

    with pytest.raises(SystemExit, match="missing broad-interest fields"):
        validate_score_coverage(scores, candidates, require_broad_interest=True)


def test_kst_date_window_includes_only_target_date() -> None:
    args = Namespace(target_date="2026-05-06", since_days=1)
    start, end, target = kst_window(args, Settings())
    assert target.isoformat() == "2026-05-06"

    may_5_kst = Paper(
        title="Old",
        url="https://example.org/old",
        published=datetime(2026, 5, 5, 14, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )
    may_6_kst = Paper(
        title="Today",
        url="https://example.org/today",
        published=datetime(2026, 5, 6, 1, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )
    undated = Paper(title="Undated", url="https://example.org/undated")

    assert not in_collection_window(may_5_kst, start, end)
    assert in_collection_window(may_6_kst, start, end)
    assert in_collection_window(undated, start, end)


def test_arxiv_feed_uses_lookback_window() -> None:
    args = Namespace(target_date="2026-05-07", since_days=1)
    settings = Settings(arxiv_lookback_days=2, dated_feed_lookback_days=1)
    start, end, _ = kst_window(args, settings)
    late_arxiv = Paper(
        title="Late arXiv paper",
        url="https://arxiv.org/abs/2605.00001",
        feed_title="cond-mat.mes-hall updates on arXiv.org",
        published=datetime(2026, 5, 6, 12, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )
    regular_journal = Paper(
        title="Old journal paper",
        url="https://example.org/paper",
        feed_title="Journal",
        published=datetime(2026, 5, 6, 12, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert in_collection_window_for_feed(late_arxiv, start, end, settings)
    assert not in_collection_window_for_feed(regular_journal, start, end, settings)


def test_dated_journal_feed_uses_lookback_window() -> None:
    args = Namespace(target_date="2026-05-18", since_days=1)
    settings = Settings(dated_feed_lookback_days=4)
    start, end, _ = kst_window(args, settings)
    friday_paper = Paper(
        title="Friday journal paper",
        url="https://example.org/friday",
        feed_title="ACS Nano",
        published=datetime(2026, 5, 15, 12, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )
    old_paper = Paper(
        title="Old journal paper",
        url="https://example.org/old",
        feed_title="ACS Nano",
        published=datetime(2026, 5, 14, 12, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert in_collection_window_for_feed(friday_paper, start, end, settings)
    assert not in_collection_window_for_feed(old_paper, start, end, settings)


def test_collect_retries_when_all_feeds_fail(monkeypatch, tmp_path: Path) -> None:
    args = Namespace(target_date="2026-05-07", since_days=1)
    settings = Settings(
        state_file=tmp_path / "state.json",
        collection_attempts=2,
        collection_retry_delay_seconds=0,
    )
    calls = {"count": 0}

    monkeypatch.setattr("paper_newsletter.cli.parse_opml", lambda _: [Feed("Journal", "https://example.org/rss")])
    monkeypatch.setattr("paper_newsletter.cli.enrich_paper", lambda paper, *_: paper)

    def fake_fetch_feed(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("connection refused")
        return [Paper(title="Recovered paper", url="https://example.org/paper")]

    monkeypatch.setattr("paper_newsletter.cli.fetch_feed", fake_fetch_feed)

    candidates, fetched_count, errors, target_date = collect_candidates(args, settings)

    assert target_date.isoformat() == "2026-05-07"
    assert fetched_count == 1
    assert errors == []
    assert [paper.title for paper in candidates] == ["Recovered paper"]


def test_collect_retries_only_failed_feeds(monkeypatch, tmp_path: Path) -> None:
    args = Namespace(target_date="2026-05-07", since_days=1)
    settings = Settings(
        state_file=tmp_path / "state.json",
        collection_attempts=2,
        collection_retry_delay_seconds=0,
    )
    calls = {"Healthy": 0, "Flaky": 0}
    feeds = [
        Feed("Healthy", "https://example.org/healthy.xml"),
        Feed("Flaky", "https://example.org/flaky.xml"),
    ]
    monkeypatch.setattr("paper_newsletter.cli.parse_opml", lambda _: feeds)
    monkeypatch.setattr("paper_newsletter.cli.enrich_paper", lambda paper, *_: paper)

    def fake_fetch_feed(feed, *_args, **_kwargs):
        calls[feed.title] += 1
        if feed.title == "Flaky" and calls[feed.title] == 1:
            raise OSError("temporary connection failure")
        return [Paper(title=f"{feed.title} paper", url=f"https://example.org/{feed.title}")]

    monkeypatch.setattr("paper_newsletter.cli.fetch_feed", fake_fetch_feed)

    candidates, fetched_count, errors, _target_date = collect_candidates(args, settings)

    assert fetched_count == 2
    assert errors == []
    assert calls == {"Healthy": 1, "Flaky": 2}
    assert {paper.title for paper in candidates} == {"Healthy paper", "Flaky paper"}


def test_collect_dedupes_after_enrichment_changes_key(monkeypatch, tmp_path: Path) -> None:
    args = Namespace(target_date="2026-05-07", since_days=1)
    settings = Settings(state_file=tmp_path / "state.json")

    monkeypatch.setattr(
        "paper_newsletter.cli.parse_opml",
        lambda _: [
            Feed("Journal A", "https://a.example/rss"),
            Feed("Journal B", "https://b.example/rss"),
        ],
    )
    monkeypatch.setattr(
        "paper_newsletter.cli.fetch_feed",
        lambda feed, *_: [
            Paper(
                title=f"Shared paper from {feed.title}",
                url=f"https://example.org/{feed.title}",
            )
        ],
    )

    def fake_enrich(paper: Paper, *_args):
        paper.doi = "10.1234/shared"
        return paper

    monkeypatch.setattr("paper_newsletter.cli.enrich_paper", fake_enrich)

    candidates, fetched_count, errors, _target_date = collect_candidates(args, settings)

    assert fetched_count == 2
    assert errors == []
    assert len(candidates) == 1
    assert candidates[0].key == "doi:10.1234/shared"
