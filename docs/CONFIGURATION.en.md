# User Configuration Guide

This guide explains every user-owned file under `config/`. Never place a Gmail
password or API key in these files. Gmail authorization is managed by the Codex
connection.

## Configuration order

1. Copy `settings.example.toml` to `settings.toml`.
2. Copy `feeds.example.opml` to `feeds.opml`, or replace it with a Feedly export.
3. Copy `profile.example.md` to `profile.md` and write your research criteria.
4. Export your Zotero library to `my_papers.bib`.
5. Run `paper-newsletter doctor`.
6. Test collection, Codex scoring, and Gmail sending before enabling the schedule.

The automatic installer creates missing files from examples but never overwrites
existing personal configuration.

## `settings.toml`

This file controls paths, newsletter behavior, schedules, and network limits.

### `[paths]`

| Key | Purpose | Default |
| --- | --- | --- |
| `feeds_opml` | RSS subscriptions | `config/feeds.opml` |
| `profile_md` | Explicit interests and exclusions | `config/profile.md` |
| `my_papers_md` | Optional curated research notes | `config/my_papers.md` |
| `my_papers_bib` | Zotero BibTeX export | `config/my_papers.bib` |
| `email_template` | Archived Markdown digest template | `config/email_template.md` |
| `state_file` | Keys of papers already handled | `state/processed.json` |
| `out_dir` | Candidates, scores, and email payloads | `out` |

The defaults are suitable for normal installations. Relative paths are resolved
from the project root.

### `[newsletter]`

```toml
[newsletter]
email_to = "your-address@example.com"
timezone = "Asia/Seoul"
threshold = 3.0
top_n = 5
developer_name = "Byunghyun Kim"
developer_email = "bhkim133@gmail.com"
project_url = "https://github.com/HyunPhys/codex-paper-newsletter"
```

- `email_to` is the newsletter recipient and may differ from the connected Gmail account.
- `timezone` defines publication-date boundaries and freshness checks.
- `threshold` is the minimum direct-relevance score for the relevant-paper list.
- `top_n` controls how many papers receive full summaries and abstracts.
- Developer fields and `project_url` produce the footer at the bottom of each email.

Scores use half steps from 0.0 through 5.0. A low threshold creates a longer
newsletter; a high threshold may leave only broad-field recommendations.

### Collection, digest, and network sections

- `schedule_time` records the intended RSS and Codex times. The installer registers
  the collection time; set the Codex automation time separately in Codex.
- Retry values control recovery from temporary feed failures.
- General-journal and arXiv lookback windows are separate because publication
  timestamps and update patterns differ.
- `crossref_email` identifies DOI metadata requests. It is a contact address, not
  a password or authentication token.
- Timeout, retry, and response-size values bound slow or abnormal HTTP responses.

## `feeds.opml`: journals and RSS feeds

This is a Feedly-compatible OPML export. Each outline's `xmlUrl` is the RSS, Atom,
or RDF endpoint. `title` or `text` becomes the journal/feed name in the newsletter.

```xml
<outline type="rss"
         title="Nature Materials"
         text="Nature Materials"
         xmlUrl="https://www.nature.com/nmat.rss" />
```

- Export subscriptions from Feedly and save the result as `feeds.opml`.
- Escape `&` as `&amp;` when editing XML manually.
- Duplicate `xmlUrl` values are collected only once.
- A feed with zero papers on a given day is normal and appears as zero in the table.
- Use a real RSS/Atom endpoint, not an ordinary journal web page.
- Publisher feeds may omit dates or abstracts; article metadata enrichment can fill
  some missing fields.

After adding feeds, run a short collection test and inspect `feed_errors`:

```powershell
paper-newsletter collect --collection-attempts 1 --collection-retry-delay-seconds 0
```

## `profile.md`: the primary scoring rubric

The profile is the most stable and authoritative ranking input. Free-form prose is
allowed, but keep the English `Include Keywords` and `Exclude Keywords` headings
for the offline fallback scorer.

```markdown
# Research Profile

## Research interests
Twisted two-dimensional materials, reconstructed domains, and TEM.

## Include Keywords
- moire reconstruction
- domain wall
- 4D-STEM

## Exclude Keywords
- battery-only
- correction

## Scoring guidance
5.0 means a direct match to the current research program.
```

Describe materials, structures, mechanisms, methods, and research questions rather
than listing materials alone. When papers are repeatedly mis-ranked, add the general
reason to the profile instead of hard-coding a paper-specific override.

## `my_papers.bib`: Zotero research context

Select your own papers and important references in Zotero, export them with Better
BibTeX, and save the UTF-8 file as `config/my_papers.bib`. Every useful entry needs
a `title`; `year`, `journal` or `booktitle`, and `keywords` improve the context.

```bibtex
@article{researcher2026,
  title = {Domain reconstruction in twisted layered materials},
  author = {Researcher, Example},
  journal = {Example Journal},
  year = {2026},
  keywords = {moire, domain wall, electron microscopy}
}
```

The program summarizes titles, years, venues, and keywords across the library.
Long abstracts are deliberately omitted so early entries cannot consume the context
budget. The library supplies positive semantic examples; it does not silently
replace exclusions or the scoring scale defined by `profile.md`.

Replace the file whenever you refresh the Zotero export. The next collection embeds
the new context. This is private research data and must not be committed publicly.

## `my_papers.md` and `email_template.md`

- `my_papers.md` is an optional free-form list of especially important papers or
  directions that are not convenient to express in BibTeX.
- `email_template.md` controls the archived Markdown digest. Gmail HTML and plain
  text are rendered separately for email-client compatibility, so editing this
  template alone does not redesign the Gmail message.

## Gmail and the Codex automation

1. Authorize the Gmail connection in Codex; do not store credentials in the project.
2. Create the daily task from `automation/daily-paper-digest.prompt.md`.
3. The automation sends `latest_email.json` using its `to`, `subject`, `body`, and
   `body_html` fields.
4. It runs `mark-processed` only after Gmail confirms a successful send.

To change recipients, edit only `newsletter.email_to` and run `doctor`. If Gmail is
disconnected, reconnect and resend the existing payload before updating state.

## Privacy and validation

Never publish `settings.toml`, `profile.md`, `my_papers.bib`, `state/`, `out/`,
`logs/`, or `backups/`. The public `.gitignore` excludes them, but review `git status`
before every commit.

```powershell
paper-newsletter doctor
paper-newsletter backup
python -m pytest
```

Resolve every doctor failure before enabling scheduled sends.
