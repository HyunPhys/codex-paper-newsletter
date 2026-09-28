# Codex Paper Newsletter

A Windows-first personal research newsletter that collects papers from RSS,
uses a Codex automation to rank them against a research profile and Zotero
library, and sends a readable HTML digest through Gmail.

The collector and renderer do not require an external LLM API key. Codex performs
the semantic scoring, while Windows Task Scheduler handles network-dependent RSS
collection before the automation runs.

## Requirements

- Windows 10 or 11
- Python 3.11 or newer
- Codex Desktop with a connected Gmail account
- An OPML feed export, a research profile, and optionally a Zotero BibTeX export

## Install

```powershell
git clone https://github.com/HyunPhys/codex-paper-newsletter.git
cd codex-paper-newsletter
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

Then edit the files created in `config/`, connect Gmail in Codex, and create a
10:00 daily automation using `automation/daily-paper-digest.prompt.md`.

- [English installation guide](docs/INSTALL.en.md)
- [한국어 설치 매뉴얼](docs/INSTALL.ko.md)
- [Operations and recovery](docs/OPERATIONS.en.md)

## Safety model

`render-scored` never needs to mark papers as processed. The Codex automation
sends the email first and runs `mark-processed` only after Gmail confirms success.
Candidate and score keys must match exactly, preventing stale or partial results
from being sent or committed to state.

Newsletter emails include a small footer crediting Byunghyun Kim, with a contact
address and link to this public repository.

## License

MIT. Developed by [Byunghyun Kim](mailto:bhkim133@gmail.com).
