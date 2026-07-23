from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


CURRENT_MAINTENANCE_STANDARD_VERSION = 6
CURRENT_HISTORY_SCHEMA_VERSION = 1
MAINTENANCE_STATE_PATH = Path("kb") / "history" / "migrations" / "maintenance_state.json"


def maintenance_state_path(repo_root: Path) -> Path:
    return Path(repo_root) / MAINTENANCE_STATE_PATH


def load_maintenance_state(repo_root: Path) -> dict[str, Any]:
    path = maintenance_state_path(repo_root)
    if not path.exists():
        return {
            "maintenance_standard_version": 0,
            "history_schema_version": 0,
            "phase": "legacy",
            "committed": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "maintenance_standard_version": 0,
            "history_schema_version": 0,
            "phase": "invalid",
            "committed": False,
            "read_error": True,
        }
    return payload if isinstance(payload, dict) else {}


def maintenance_standard_is_active(repo_root: Path) -> bool:
    state = load_maintenance_state(repo_root)
    return bool(
        state.get("committed")
        and str(state.get("phase") or "") == "committed"
        and int(state.get("maintenance_standard_version") or 0)
        >= CURRENT_MAINTENANCE_STANDARD_VERSION
        and int(state.get("history_schema_version") or 0)
        >= CURRENT_HISTORY_SCHEMA_VERSION
    )


def write_maintenance_state(repo_root: Path, payload: Mapping[str, Any]) -> Path:
    path = maintenance_state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return path
