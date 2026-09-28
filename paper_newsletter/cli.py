from __future__ import annotations

import argparse
from collections import Counter
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings, read_text
from .bibtex import summarize_bibtex
from .doi import fill_missing_dois_by_title
from .enrich import enrich_paper
from .files import write_text_atomic
from .models import Paper, ScoredPaper
from .opml import parse_opml
from .relevance import score_paper
from .render import (
    build_source_stats,
    email_payload,
    render_digest,
    render_email_html,
    render_email_text,
)
from .rss import dedupe_papers, fetch_feed, is_retryable_fetch_error
from .state import ProcessedState
from .maintenance import backup_runtime, doctor, restore_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a personalized paper newsletter.")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "collect", "render-scored", "mark-processed", "doctor", "backup", "restore"],
    )
    parser.add_argument("--config", default="config/settings.toml")
    parser.add_argument("--feeds-opml")
    parser.add_argument("--profile")
    parser.add_argument("--my-papers")
    parser.add_argument("--my-papers-bib")
    parser.add_argument("--email-template")
    parser.add_argument("--state-file")
    parser.add_argument("--out-dir")
    parser.add_argument("--since-days", type=int, default=1)
    parser.add_argument("--target-date", default="")
    parser.add_argument("--timezone")
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--collection-attempts", type=int)
    parser.add_argument("--collection-retry-delay-seconds", type=int)
    parser.add_argument("--dated-feed-lookback-days", type=int)
    parser.add_argument("--arxiv-lookback-days", type=int)
    parser.add_argument("--send-payload", default="")
    parser.add_argument("--email-to")
    parser.add_argument("--candidates")
    parser.add_argument("--scores")
    parser.add_argument("--backup-dir", default="backups")
    parser.add_argument("--backup-file", default="")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--no-mark-processed", action="store_true")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    settings = Settings.from_toml(config_path).with_overrides(
        feeds_opml=Path(args.feeds_opml) if args.feeds_opml else None,
        profile_md=Path(args.profile) if args.profile else None,
        my_papers_md=Path(args.my_papers) if args.my_papers else None,
        my_papers_bib=Path(args.my_papers_bib) if args.my_papers_bib else None,
        email_template=Path(args.email_template) if args.email_template else None,
        state_file=Path(args.state_file) if args.state_file else None,
        out_dir=Path(args.out_dir) if args.out_dir else None,
        threshold=args.threshold,
        timezone_name=args.timezone,
        collection_attempts=args.collection_attempts,
        collection_retry_delay_seconds=args.collection_retry_delay_seconds,
        dated_feed_lookback_days=args.dated_feed_lookback_days,
        arxiv_lookback_days=args.arxiv_lookback_days,
        email_to=args.email_to,
    )
    args.email_to = settings.email_to
    args.candidates = args.candidates or str(settings.out_dir / "candidates.json")
    args.scores = args.scores or str(settings.out_dir / "scored.json")

    if args.command == "doctor":
        return doctor(settings, config_path)
    if args.command == "backup":
        backup_runtime(settings, config_path, Path(args.backup_dir))
        return 0
    if args.command == "restore":
        if not args.backup_file:
            raise SystemExit("restore requires --backup-file PATH")
        restore_runtime(Path(args.backup_file), Path.cwd(), confirmed=args.yes)
        return 0

    if args.command in {"run", "collect"} and not settings.feeds_opml.exists():
        raise SystemExit(f"Missing OPML file: {settings.feeds_opml}")

    if args.command == "render-scored":
        return render_scored(args, settings)
    if args.command == "mark-processed":
        return mark_processed(args, settings)

    candidates, fetched_count, errors, target_date = collect_candidates(args, settings)

    if args.command == "collect":
        profile = read_text(settings.profile_md)
        my_papers = read_my_papers(settings)
        payload = {
            "instructions": (
                "Score every candidate for the user's paper newsletter. "
                "Return scores as 0.0, 0.5, ..., 5.0. "
                "Use English for reason and summaries to avoid Windows email encoding issues. "
                "Write a JSON file with top-level key 'items'. Each item must include "
                "key, score, reason, detailed_summary, one_line_summary, "
                "broad_interest_score, and broad_interest_reason."
            ),
            "threshold": settings.threshold,
            "profile": profile,
            "my_papers": my_papers,
            "candidates": [paper.to_dict() for paper in candidates],
            "stats": {
                "fetched": fetched_count,
                "candidates": len(candidates),
                "feed_errors": errors,
                "target_date": target_date.isoformat(),
                "timezone": settings.timezone_name,
                "dated_feed_lookback_days": settings.dated_feed_lookback_days,
                "arxiv_lookback_days": settings.arxiv_lookback_days,
                "scoring_schema_version": 2,
            },
        }
        candidates_path = Path(args.candidates)
        write_text_atomic(candidates_path, json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"Candidates: {candidates_path}")
        print(f"Candidate count: {len(candidates)}")
        return 0

    profile = read_text(settings.profile_md)
    my_papers = read_my_papers(settings)
    scored_all = [score_paper(paper, profile, my_papers) for paper in candidates]
    return write_digest(args, settings, scored_all, fetched_count, len(candidates), errors, target_date)


def read_my_papers(settings: Settings) -> str:
    parts = []
    md = read_text(settings.my_papers_md)
    if md:
        parts.append("# Manually Curated Papers\n\n" + md)
    bib_summary = summarize_bibtex(settings.my_papers_bib)
    if bib_summary:
        parts.append("# Zotero BibTeX Summary\n\n" + bib_summary)
    return "\n\n".join(parts)


def collect_candidates(args: argparse.Namespace, settings: Settings) -> tuple[list[Paper], int, list[str], date]:
    state = ProcessedState(settings.state_file)
    window_start, window_end, target_date = kst_window(args, settings)
    feeds = parse_opml(settings.feeds_opml)
    fetched: list[Paper] = []
    pending = list(feeds)
    errors_by_url: dict[str, str] = {}
    attempts = max(1, settings.collection_attempts)

    # Successful feeds are retained while only transient failures are retried.
    # This prevents one healthy feed from suppressing retries for another feed.
    for attempt in range(attempts):
        retryable: list = []
        for feed in pending:
            try:
                fetched.extend(
                    fetch_feed(
                        feed,
                        settings.request_timeout_seconds,
                        settings.user_agent,
                        settings.request_retries,
                        settings.max_response_bytes,
                    )
                )
                errors_by_url.pop(feed.url, None)
            except Exception as exc:
                errors_by_url[feed.url] = f"{feed.title}: {exc}"
                if is_retryable_fetch_error(exc) and attempt < attempts - 1:
                    retryable.append(feed)
        pending = retryable
        if not pending:
            break
        delay = max(0, settings.collection_retry_delay_seconds)
        if delay:
            print(
                f"{len(pending)} transient feed failure(s); "
                f"retrying in {delay} seconds ({attempt + 2}/{attempts})..."
            )
            time.sleep(delay)

    errors = list(errors_by_url.values())

    if feeds and not fetched and errors:
        error_preview = "\n".join(f"- {error}" for error in errors[:10])
        raise SystemExit(
            "All feed fetches failed, so no newsletter will be generated.\n"
            f"First errors:\n{error_preview}"
        )

    # First filter uses feed-level metadata only. Enrichment can later add a DOI,
    # so keys may change from url:* to doi:* after this point.
    candidates = [
        paper
        for paper in dedupe_papers(fetched)
        if not state.seen(paper.key)
        and in_collection_window_for_feed(paper, window_start, window_end, settings)
    ]

    enriched = [
        enrich_paper(paper, settings.request_timeout_seconds, settings.user_agent)
        for paper in candidates
    ]
    # Enrichment may discover DOI/authors/abstract from the article page.
    # Re-dedupe afterwards so the same paper from multiple feeds does not survive
    # just because one copy gained a stronger DOI-based key.
    enriched = [
        paper
        for paper in dedupe_papers(enriched)
        if not state.seen(paper.key)
    ]
    print(f"Date window ({settings.timezone_name}): {target_date.isoformat()}")
    return enriched, len(fetched), errors, target_date


def kst_window(args: argparse.Namespace, settings: Settings) -> tuple[datetime, datetime, date]:
    tz = ZoneInfo(settings.timezone_name)
    if args.target_date:
        target_date = date.fromisoformat(args.target_date)
    else:
        target_date = datetime.now(tz).date()
    days = max(1, int(args.since_days))
    start_date = target_date - timedelta(days=days - 1)
    window_start = datetime.combine(start_date, datetime.min.time(), tzinfo=tz)
    window_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    return window_start, window_end, target_date


def in_collection_window(paper: Paper, window_start: datetime, window_end: datetime) -> bool:
    if paper.published is None:
        return True
    published = paper.published
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    local_published = published.astimezone(window_start.tzinfo)
    return window_start <= local_published < window_end


def in_collection_window_for_feed(
    paper: Paper,
    window_start: datetime,
    window_end: datetime,
    settings: Settings,
) -> bool:
    if not is_arxiv_paper(paper):
        lookback_days = max(1, settings.dated_feed_lookback_days)
        dated_window_start = window_start - timedelta(days=lookback_days - 1)
        return in_collection_window(paper, dated_window_start, window_end)
    lookback_days = max(1, settings.arxiv_lookback_days)
    arxiv_window_start = window_start - timedelta(days=lookback_days - 1)
    return in_collection_window(paper, arxiv_window_start, window_end)


def is_arxiv_paper(paper: Paper) -> bool:
    haystack = " ".join([paper.feed_title, paper.url]).lower()
    return "arxiv.org" in haystack


def render_scored(args: argparse.Namespace, settings: Settings) -> int:
    scores_path = Path(args.scores)
    if not scores_path.exists():
        raise SystemExit(f"Missing scores file: {scores_path}")
    data = json.loads(scores_path.read_text(encoding="utf-8"))
    candidates_path = Path(args.candidates)
    candidate_data, stats = load_candidate_data(candidates_path)
    # This is the main stale-file guard: never render yesterday's scores against
    # today's candidates, and never render partial Codex output.
    validate_score_coverage(
        data,
        candidate_data,
        require_broad_interest=int(stats.get("scoring_schema_version", 1)) >= 2,
    )
    fetched_count = int(stats.get("fetched", 0))
    candidate_count = int(stats.get("candidates", len(candidate_data)))
    errors = list(stats.get("feed_errors", []))
    digest_date = date.today()
    if stats.get("target_date"):
        digest_date = date.fromisoformat(str(stats["target_date"]))

    scored: list[ScoredPaper] = []
    for item in data.get("items", []):
        key = item.get("key", "")
        paper_data = dict(candidate_data.get(key, {}))
        paper_data.update(item.get("paper", {}))
        if not paper_data:
            continue
        paper = Paper.from_dict(paper_data)
        scored.append(
            ScoredPaper(
                paper=paper,
                score=float(item.get("score", 0.0)),
                reason=item.get("reason", ""),
                detailed_summary=item.get("detailed_summary", ""),
                one_line_summary=item.get("one_line_summary", ""),
                broad_interest_score=float(item.get("broad_interest_score", 0.0)),
                broad_interest_reason=item.get("broad_interest_reason", ""),
            )
        )
    return write_digest(args, settings, scored, fetched_count, candidate_count, errors, digest_date)


def mark_processed(args: argparse.Namespace, settings: Settings) -> int:
    candidates_path = Path(args.candidates)
    scores_path = Path(args.scores)
    if not scores_path.exists():
        raise SystemExit(f"Missing scores file: {scores_path}")

    candidate_data, stats = load_candidate_data(candidates_path)
    scores_payload = json.loads(scores_path.read_text(encoding="utf-8"))
    # Repeat the coverage check here because this command is the only one that
    # mutates processed state. It must stay safe even when called manually.
    validate_score_coverage(
        scores_payload,
        candidate_data,
        require_broad_interest=int(stats.get("scoring_schema_version", 1)) >= 2,
    )
    keys = set(candidate_data)
    scored: list[ScoredPaper] = []
    for item in scores_payload.get("items", []):
        key = item.get("key", "")
        paper_data = dict(candidate_data.get(key, {}))
        paper_data.update(item.get("paper", {}))
        if not paper_data:
            continue
        paper = Paper.from_dict(paper_data)
        scored.append(
            ScoredPaper(
                paper=paper,
                score=float(item.get("score", 0.0)),
                reason=item.get("reason", ""),
                detailed_summary=item.get("detailed_summary", ""),
                one_line_summary=item.get("one_line_summary", ""),
                broad_interest_score=float(item.get("broad_interest_score", 0.0)),
                broad_interest_reason=item.get("broad_interest_reason", ""),
            )
        )
        keys.add(paper.key)

    relevant = [item for item in scored if item.score >= settings.threshold]
    fill_missing_dois_by_title(
        relevant, settings.out_dir / "doi_cache.json", settings.crossref_email
    )
    keys.update(item.paper.key for item in scored)

    state = ProcessedState(settings.state_file)
    state.add_many(sorted(keys))
    state.save()
    print(f"Marked processed: {len(keys)}")
    print(f"State: {settings.state_file}")
    return 0


def load_candidate_data(candidates_path: Path) -> tuple[dict[str, dict], dict]:
    if not candidates_path.exists():
        raise SystemExit(f"Missing candidates file: {candidates_path}")
    candidates_payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    candidates = candidates_payload.get("candidates", [])
    if not candidates:
        raise SystemExit(f"No candidates found in: {candidates_path}")
    candidate_data = {
        item["key"]: item
        for item in candidates
        if item.get("key")
    }
    if not candidate_data:
        raise SystemExit(f"No keyed candidates found in: {candidates_path}")
    return candidate_data, dict(candidates_payload.get("stats", {}))


def validate_score_coverage(
    scores_payload: dict,
    candidate_data: dict[str, dict],
    require_broad_interest: bool = False,
) -> None:
    """Require a one-to-one mapping between current candidates and score items."""
    items = scores_payload.get("items", [])
    if not items:
        raise SystemExit("Scores file has no items.")
    score_keys = [str(item.get("key", "")) for item in items if item.get("key")]
    duplicate_score_keys = [key for key, count in Counter(score_keys).items() if count > 1]
    if duplicate_score_keys:
        preview = ", ".join(sorted(duplicate_score_keys)[:5])
        raise SystemExit(f"Scores file contains duplicate keys: {preview}")
    invalid_scores: list[str] = []
    for item in items:
        key = str(item.get("key", "<missing key>"))
        if require_broad_interest and (
            "broad_interest_score" not in item or "broad_interest_reason" not in item
        ):
            invalid_scores.append(f"{key}=missing broad-interest fields")
            continue
        try:
            score = float(item.get("score"))
        except (TypeError, ValueError):
            invalid_scores.append(f"{key}=non-numeric")
            continue
        if not 0.0 <= score <= 5.0 or abs(score * 2 - round(score * 2)) > 1e-9:
            invalid_scores.append(f"{key}={score}")
        if "broad_interest_score" in item:
            try:
                broad_score = float(item.get("broad_interest_score"))
            except (TypeError, ValueError):
                invalid_scores.append(f"{key}.broad_interest_score=non-numeric")
                continue
            if not 0.0 <= broad_score <= 5.0 or abs(broad_score * 2 - round(broad_score * 2)) > 1e-9:
                invalid_scores.append(f"{key}.broad_interest_score={broad_score}")
            elif broad_score > 0.0 and not str(item.get("broad_interest_reason", "")).strip():
                invalid_scores.append(f"{key}=missing broad-interest reason")
    if invalid_scores:
        raise SystemExit(
            "Scores must be half steps from 0.0 through 5.0; invalid values: "
            + ", ".join(invalid_scores[:5])
        )
    candidate_keys = set(candidate_data)
    scored_keys = set(score_keys)
    missing = sorted(candidate_keys - scored_keys)
    extra = sorted(scored_keys - candidate_keys)
    if missing or extra:
        parts = ["Scores file does not match candidates file."]
        if missing:
            parts.append(f"Missing scores for {len(missing)} candidates; first keys: {', '.join(missing[:5])}")
        if extra:
            parts.append(f"Scores include {len(extra)} non-candidate keys; first keys: {', '.join(extra[:5])}")
        raise SystemExit("\n".join(parts))


def write_digest(
    args: argparse.Namespace,
    settings: Settings,
    scored_all: list[ScoredPaper],
    fetched_count: int,
    candidate_count: int,
    errors: list[str],
    digest_date: date,
) -> int:
    relevant = sorted(
        [item for item in scored_all if item.score >= settings.threshold],
        key=lambda item: (item.score, item.paper.published_or_min()),
        reverse=True,
    )
    broad_picks = select_broad_interest(scored_all, settings.threshold, limit=3)
    if not relevant and not broad_picks and not args.dry_run and not args.allow_empty:
        raise SystemExit(
            "No relevant or broad-interest papers were selected; skipping email payload generation."
        )
    skipped_count = max(0, candidate_count - len(relevant))
    pre_enrichment_keys = [item.paper.key for item in scored_all]
    # DOI lookup can strengthen keys for relevant papers. Keep both old and new
    # keys when marking so future collections recognize either representation.
    fill_missing_dois_by_title(
        relevant, settings.out_dir / "doi_cache.json", settings.crossref_email
    )

    subject = f"Daily Paper Digest - {digest_date.isoformat()}"
    body = render_digest(
        relevant,
        skipped_count=skipped_count,
        today=digest_date,
        top_n=settings.top_n,
        template_path=settings.email_template,
        threshold=settings.threshold,
        broad_picks=broad_picks,
    )
    all_sources = (
        [feed.title for feed in parse_opml(settings.feeds_opml)]
        if settings.feeds_opml.exists()
        else []
    )
    email_text = render_email_text(
        relevant,
        skipped_count=skipped_count,
        today=digest_date,
        threshold=settings.threshold,
        top_n=settings.top_n,
        feed_errors=errors,
        source_stats=build_source_stats(
            scored_all,
            settings.threshold,
            all_sources=all_sources,
        ),
        broad_picks=broad_picks,
        developer_name=settings.developer_name,
        developer_email=settings.developer_email,
        project_url=settings.project_url,
    )
    email_html = render_email_html(
        relevant,
        skipped_count=skipped_count,
        today=digest_date,
        threshold=settings.threshold,
        top_n=settings.top_n,
        feed_errors=errors,
        source_stats=build_source_stats(
            scored_all,
            settings.threshold,
            all_sources=all_sources,
        ),
        broad_picks=broad_picks,
        developer_name=settings.developer_name,
        developer_email=settings.developer_email,
        project_url=settings.project_url,
    )

    settings.out_dir.mkdir(parents=True, exist_ok=True)
    digest_path = settings.out_dir / f"digest-{digest_date.isoformat()}.md"
    write_text_atomic(digest_path, body)
    payload_path = Path(args.send_payload) if args.send_payload else settings.out_dir / "latest_email.json"
    write_text_atomic(
        payload_path,
        email_payload(subject, email_text, email_html, to=settings.email_to),
    )

    if not args.no_mark_processed and not args.dry_run:
        state = ProcessedState(settings.state_file)
        post_enrichment_keys = [item.paper.key for item in scored_all]
        state.add_many(pre_enrichment_keys + post_enrichment_keys)
        state.save()

    print(f"Fetched: {fetched_count}")
    print(f"Candidates: {candidate_count}")
    print(f"Relevant: {len(relevant)}")
    print(f"Digest: {digest_path}")
    print(f"Email payload: {payload_path}")
    if errors:
        print("Feed errors:")
        for error in errors[:20]:
            print(f"- {error}")
    return 0


def select_broad_interest(
    scored: list[ScoredPaper],
    threshold: float,
    limit: int = 3,
) -> list[ScoredPaper]:
    """Choose impactful adjacent-field papers without duplicating core picks."""
    eligible = [
        item
        for item in scored
        if item.score < threshold and item.broad_interest_score > 0.0
    ]
    return sorted(
        eligible,
        key=lambda item: (
            item.broad_interest_score,
            item.score,
            item.paper.published_or_min(),
        ),
        reverse=True,
    )[: max(0, limit)]
