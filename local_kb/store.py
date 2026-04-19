from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from local_kb.models import Entry

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: PyYAML. Install it with: pip install pyyaml"
    ) from exc


DEFAULT_SCOPES = ("public", "private", "candidates")


def resolve_repo_root(value: str | os.PathLike[str]) -> Path:
    return Path(value).resolve()


def load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_entries(repo_root: Path, scopes: Iterable[str] = DEFAULT_SCOPES) -> list[Entry]:
    entries: list[Entry] = []
    kb_root = repo_root / "kb"
    for scope in scopes:
        target = kb_root / scope
        if not target.exists():
            continue
        for path in sorted(target.rglob("*.yaml")):
            entries.append(Entry(path=path, data=load_yaml_file(path)))
    return entries


def write_yaml_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def history_events_path(repo_root: Path) -> Path:
    return repo_root / "kb" / "history" / "events.jsonl"


def append_timeline_event(repo_root: Path, payload: dict[str, Any]) -> Path:
    path = history_events_path(repo_root)
    append_jsonl(path, payload)
    return path


def candidate_dir(repo_root: Path) -> Path:
    path = repo_root / "kb" / "candidates"
    path.mkdir(parents=True, exist_ok=True)
    return path

