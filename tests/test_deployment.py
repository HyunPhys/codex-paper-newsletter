from __future__ import annotations

from pathlib import Path

import pytest

from paper_newsletter.config import Settings
from paper_newsletter.maintenance import backup_runtime, restore_runtime
from scripts.check_public_tree import check_tree


def test_settings_file_and_cli_style_overrides(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(
        """
[newsletter]
email_to = "reader@example.com"
threshold = 4.0
developer_email = "developer@example.com"
[collection]
schedule_time = "08:30"
attempts = 7
""",
        encoding="utf-8",
    )

    loaded = Settings.from_toml(config)
    overridden = loaded.with_overrides(threshold=3.5, email_to=None)

    assert loaded.email_to == "reader@example.com"
    assert loaded.collection_time == "08:30"
    assert loaded.collection_attempts == 7
    assert overridden.threshold == 3.5
    assert overridden.email_to == "reader@example.com"


def test_backup_and_confirmed_restore(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()
    settings_path = config_dir / "settings.toml"
    profile_path = config_dir / "profile.md"
    state_path = state_dir / "processed.json"
    settings_path.write_text("[newsletter]\nemail_to='reader@example.com'\n", encoding="utf-8")
    profile_path.write_text("original profile", encoding="utf-8")
    state_path.write_text('{"processed":["paper:1"]}', encoding="utf-8")
    settings = Settings(
        profile_md=Path("config/profile.md"),
        state_file=Path("state/processed.json"),
    )

    backup = backup_runtime(settings, Path("config/settings.toml"), Path("backups"))
    profile_path.write_text("changed", encoding="utf-8")
    state_path.write_text('{"processed":[]}', encoding="utf-8")
    restore_runtime(backup, tmp_path, confirmed=True)

    assert profile_path.read_text(encoding="utf-8") == "original profile"
    assert "paper:1" in state_path.read_text(encoding="utf-8")


def test_restore_requires_confirmation(tmp_path: Path) -> None:
    backup = tmp_path / "backup.zip"
    backup.write_bytes(b"not used")
    with pytest.raises(SystemExit, match="--yes"):
        restore_runtime(backup, tmp_path, confirmed=False)


def test_public_tree_checker_rejects_private_files(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.toml").write_text("private", encoding="utf-8")
    assert any("private filename" in error for error in check_tree(tmp_path))


def test_runtime_has_no_external_llm_api_path() -> None:
    source = (Path(__file__).parents[1] / "paper_newsletter" / "relevance.py").read_text(
        encoding="utf-8"
    )
    assert "api.openai.com" not in source
    assert "OPENAI" + "_API_KEY" not in source


def test_install_scripts_do_not_hardcode_a_user_profile() -> None:
    root = Path(__file__).parents[1]
    scripts = (root / "scripts" / "collect_daily.ps1").read_text(encoding="utf-8")
    scripts += (root / "scripts" / "install.ps1").read_text(encoding="utf-8")
    assert "C:" + "\\Users\\" not in scripts
    assert "$PSScriptRoot" in scripts
