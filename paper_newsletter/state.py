from __future__ import annotations

import json
from pathlib import Path

from .files import write_text_atomic


class ProcessedState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.keys: set[str] = set()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # Keep the broken file for manual recovery, but do not let one
                # corrupt write block future collections forever.
                backup = path.with_suffix(path.suffix + ".corrupt")
                path.replace(backup)
                data = {}
            self.keys = set(data.get("processed", []))

    def seen(self, key: str) -> bool:
        return key in self.keys

    def add_many(self, keys: list[str]) -> None:
        self.keys.update(keys)

    def save(self) -> None:
        data = {"processed": sorted(self.keys)}
        write_text_atomic(self.path, json.dumps(data, indent=2, ensure_ascii=False))
