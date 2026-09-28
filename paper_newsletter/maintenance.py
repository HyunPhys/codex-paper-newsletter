from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile
from zoneinfo import ZoneInfo

from .config import Settings
from .opml import parse_opml


def doctor(settings: Settings, config_path: Path) -> int:
    """Print deployment-oriented health checks without changing runtime data."""
    failures: list[str] = []
    warnings: list[str] = []

    def require(label: str, path: Path) -> None:
        if path.exists():
            print(f"[OK] {label}: {path}")
        else:
            failures.append(f"{label} is missing: {path}")

    print(f"[OK] Python: {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        failures.append("Python 3.11 or newer is required")
    require("Settings", config_path)
    require("Feeds OPML", settings.feeds_opml)
    require("Research profile", settings.profile_md)
    require("Email template", settings.email_template)
    if settings.my_papers_bib.exists() or settings.my_papers_md.exists():
        print("[OK] Research library context is available")
    else:
        warnings.append("No Zotero BibTeX or curated paper list is configured")
    if not settings.email_to:
        failures.append("newsletter.email_to is empty")
    try:
        ZoneInfo(settings.timezone_name)
    except Exception:
        failures.append(f"Invalid timezone: {settings.timezone_name}")
    if settings.feeds_opml.exists():
        try:
            count = len(parse_opml(settings.feeds_opml))
            print(f"[OK] Feed count: {count}")
            if count == 0:
                failures.append("Feeds OPML contains no feed URLs")
        except Exception as exc:
            failures.append(f"Feeds OPML cannot be parsed: {exc}")
    try:
        settings.out_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.out_dir / ".doctor-write-test"
        probe.write_text("ok", encoding="ascii")
        probe.unlink()
        print(f"[OK] Output directory is writable: {settings.out_dir}")
    except OSError as exc:
        failures.append(f"Output directory is not writable: {exc}")

    candidates = settings.out_dir / "candidates.json"
    if candidates.exists():
        try:
            payload = json.loads(candidates.read_text(encoding="utf-8"))
            target = str(payload.get("stats", {}).get("target_date", ""))
            today = datetime.now(ZoneInfo(settings.timezone_name)).date().isoformat()
            if target == today:
                print(f"[OK] Candidates are current for {today}")
            else:
                warnings.append(f"Candidates target_date is {target or 'missing'}; today is {today}")
        except Exception as exc:
            failures.append(f"Candidates JSON is invalid: {exc}")
    else:
        warnings.append("Candidates file does not exist yet")

    _check_scheduled_task(warnings)
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    memory = codex_home / "automations" / "daily-paper-digest" / "memory.md"
    if memory.exists():
        print(f"[OK] Codex automation memory: {memory}")
    else:
        warnings.append("Codex automation memory was not found; create the automation manually")

    for item in warnings:
        print(f"[WARN] {item}")
    for item in failures:
        print(f"[FAIL] {item}")
    print(f"Doctor result: {len(failures)} failure(s), {len(warnings)} warning(s)")
    return 1 if failures else 0


def _check_scheduled_task(warnings: list[str]) -> None:
    if os.name != "nt":
        warnings.append("Windows Task Scheduler check skipped on this operating system")
        return
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", "PaperNewsletterCollect"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0:
        print("[OK] Scheduled task: PaperNewsletterCollect")
    else:
        warnings.append("Scheduled task PaperNewsletterCollect was not found or could not be read")


def backup_runtime(settings: Settings, config_path: Path, backup_dir: Path) -> Path:
    """Back up private configuration and processed state, excluding logs and output."""
    root = Path.cwd().resolve()
    sources = [
        config_path,
        settings.profile_md,
        settings.my_papers_md,
        settings.my_papers_bib,
        settings.email_template,
        settings.feeds_opml,
        settings.state_file,
    ]
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = backup_dir / f"paper-newsletter-backup-{stamp}.zip"
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sources:
            if not source.exists():
                continue
            resolved = source.resolve()
            try:
                relative = resolved.relative_to(root)
            except ValueError as exc:
                raise SystemExit(f"Refusing to back up a path outside the project: {source}") from exc
            arcname = relative.as_posix()
            archive.write(resolved, arcname)
            manifest[arcname] = arcname
        archive.writestr("backup-manifest.json", json.dumps(manifest, indent=2))
    print(f"Backup: {destination}")
    return destination


def restore_runtime(backup_file: Path, project_root: Path, confirmed: bool = False) -> None:
    """Restore only config and state files from a trusted project backup."""
    if not confirmed:
        raise SystemExit("Restore overwrites configuration/state; rerun with --yes to confirm.")
    if not backup_file.exists():
        raise SystemExit(f"Backup does not exist: {backup_file}")
    allowed_roots = {"config", "state"}
    with zipfile.ZipFile(backup_file) as archive:
        for member in archive.infolist():
            if member.filename == "backup-manifest.json" or member.is_dir():
                continue
            relative = PurePosixPath(member.filename)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise SystemExit(f"Unsafe backup member: {member.filename}")
            if relative.parts[0] not in allowed_roots:
                raise SystemExit(f"Unexpected backup member: {member.filename}")
            destination = project_root.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))
            print(f"Restored: {destination}")
