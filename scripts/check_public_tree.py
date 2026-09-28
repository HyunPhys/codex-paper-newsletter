from __future__ import annotations

import argparse
from pathlib import Path


TEXT_SUFFIXES = {".py", ".ps1", ".md", ".toml", ".yml", ".yaml", ".json", ".opml", ".txt"}
FORBIDDEN = (
    "bhkim133@snu.ac.kr",
    "C:\\Users\\",
    "OPENAI_API_KEY",
    "PAPER_NEWSLETTER_USE_OPENAI_API",
)
FORBIDDEN_NAMES = {"settings.toml", "profile.md", "my_papers.bib", "processed.json"}


def check_tree(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.name in FORBIDDEN_NAMES:
            errors.append(f"private filename: {path.relative_to(root)}")
        if path.name == Path(__file__).name:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in FORBIDDEN:
            if token.lower() in text.lower():
                errors.append(f"forbidden token {token!r}: {path.relative_to(root)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    errors = check_tree(args.root)
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        print(f"Public tree check failed with {len(errors)} issue(s).")
        return 1
    print("Public tree check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
