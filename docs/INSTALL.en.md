# Installation Guide (English)

## 1. Prerequisites

Install Python 3.11 or newer and Codex Desktop on Windows 10/11. Sign in to Codex
and connect Gmail before enabling the daily send automation. The computer and
Windows user session must be active at the scheduled times.

## 2. Automatic installation

Open PowerShell in the repository and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

The installer creates `.venv`, installs the package, copies missing example
configuration files, registers `PaperNewsletterCollect` at the configured time,
and runs the health check. It never overwrites existing configuration or state.

Edit these files after the first run:

- `config/settings.toml`: recipient, timezone, Crossref contact and public URL
- `config/feeds.opml`: your Feedly or other OPML export
- `config/profile.md`: interests, inclusion rules and exclusions
- `config/my_papers.bib`: your Zotero Better BibTeX export

Run `paper-newsletter doctor` until there are no failures.

## 3. Manual installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item config\settings.example.toml config\settings.toml
Copy-Item config\feeds.example.opml config\feeds.opml
Copy-Item config\profile.example.md config\profile.md
Copy-Item config\my_papers.example.bib config\my_papers.bib
.\.venv\Scripts\paper-newsletter.exe doctor
```

Register `scripts/collect_daily.ps1` in Windows Task Scheduler as a daily task.
Use `powershell.exe` with arguments similar to:

```text
-NoProfile -ExecutionPolicy Bypass -File "<PROJECT>\scripts\collect_daily.ps1"
```

Select **Run only when the user is logged on**. The default collection time is
09:40 in `config/settings.toml`.

## 4. Codex and Gmail

Connect Gmail in Codex. Create a daily automation at 10:00 with this repository
as its workspace and paste `automation/daily-paper-digest.prompt.md` as the task.
The 20-minute gap lets RSS retries finish before scoring starts.

Test with `paper-newsletter collect`, then let Codex score and render the current
candidates. A test send must use `--no-mark-processed`; only a confirmed real send
may be followed by `paper-newsletter mark-processed`.

## 5. Backup and removal

```powershell
paper-newsletter backup
paper-newsletter restore --backup-file backups\paper-newsletter-backup-YYYYMMDD-HHMMSS.zip --yes
powershell -ExecutionPolicy Bypass -File scripts/uninstall.ps1
```

Uninstall preserves configuration, runtime state, output, logs and backups.
