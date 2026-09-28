# Operations and Recovery

Run `paper-newsletter doctor` first. A healthy daily run has a successful 09:40
`PaperNewsletterCollect` task, a current `out/candidates.json`, a successful 10:00
Codex automation, a Gmail message ID, and only then an updated processed state.

Collection logs are stored under `logs/`. Codex run summaries are stored in its
automation memory. If Gmail fails, reconnect it and resend the existing payload;
do not run `mark-processed`. Use `paper-newsletter backup` before moving machines
or replacing configuration, and verify a restore with `doctor` before enabling
scheduled sends.
