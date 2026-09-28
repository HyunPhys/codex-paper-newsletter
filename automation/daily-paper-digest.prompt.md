# Daily Paper Digest automation prompt

Run the paper newsletter scoring and sending pipeline in this workspace without
using an external LLM API. Windows Task Scheduler has already produced
`out/candidates.json`; do not fetch RSS feeds in this automation.

1. Validate that `out/candidates.json` is valid, contains candidates, and has a
   `stats.target_date` matching today in the configured timezone. Stop without
   sending if validation fails.
2. Score every unique candidate against the embedded profile and Zotero context.
   Write `out/scored.json` with exactly one item per candidate key. Each item
   must contain `key`, half-step `score` from 0 to 5, `reason`,
   `detailed_summary`, `one_line_summary`, half-step `broad_interest_score`, and
   `broad_interest_reason`. Profile rules are primary; Zotero papers are positive
   semantic examples. Do not reward journal prestige by itself.
3. Run `python -m paper_newsletter render-scored --config config/settings.toml
   --no-mark-processed`. Stop if it fails.
4. Read `out/latest_email.json` and send it through the connected Gmail account
   as `multipart/alternative`, using `body` as UTF-8 plain text and `body_html`
   as UTF-8 HTML. Use the payload's `to` and `subject` values.
5. Only after Gmail confirms a successful send, run `python -m paper_newsletter
   mark-processed --config config/settings.toml`. If sending fails, optionally
   create a draft, but never mark processed.
6. Write a concise run summary to the automation memory including candidate,
   relevant, broad-pick and feed-error counts, send result, and state result.
