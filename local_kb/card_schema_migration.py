from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from local_kb.common import utc_now_iso
from local_kb.store import load_yaml_file, write_yaml_file


SKILL_GUIDANCE_MIGRATION_ID = "skill-guidance-direct-to-v1"
CURRENT_SKILL_GUIDANCE_FIELD = "unavailable_skill_guidance"
OBSOLETE_SKILL_GUIDANCE_FIELDS = (
    "skill_fallback",
    "fallback",
    "without_skill",
    "fallback_guidance",
)


def _entry_paths(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    for scope in ("public", "private", "candidates"):
        root = Path(repo_root) / "kb" / scope
        if root.is_dir():
            paths.extend(sorted(root.rglob("*.yaml")))
    return paths


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _receipt_path(repo_root: Path) -> Path:
    return Path(repo_root) / ".local" / "migrations" / SKILL_GUIDANCE_MIGRATION_ID / "current-receipt.json"


def migrate_skill_guidance_fields_to_current(repo_root: Path) -> dict[str, Any]:
    """Rewrite old Skill-guidance field aliases outside normal card readers."""

    root = Path(repo_root)
    changes: list[tuple[Path, dict[str, Any], list[str]]] = []
    conflicts: list[str] = []
    for path in _entry_paths(root):
        data = load_yaml_file(path)
        if not isinstance(data, dict):
            continue
        use = data.get("use")
        if not isinstance(use, dict):
            continue
        present = [field for field in OBSOLETE_SKILL_GUIDANCE_FIELDS if field in use]
        if not present:
            continue
        values = {str(use.get(field) or "").strip() for field in present}
        values.discard("")
        current_value = str(use.get(CURRENT_SKILL_GUIDANCE_FIELD) or "").strip()
        if len(values) > 1 or (current_value and values and current_value not in values):
            conflicts.append(path.relative_to(root).as_posix())
            continue
        next_data = dict(data)
        next_use = dict(use)
        if not current_value and values:
            next_use[CURRENT_SKILL_GUIDANCE_FIELD] = next(iter(values))
        for field in present:
            next_use.pop(field, None)
        next_data["use"] = next_use
        changes.append((path, next_data, present))
    if conflicts:
        return {
            "ok": False,
            "status": "blocked",
            "migration_id": SKILL_GUIDANCE_MIGRATION_ID,
            "error": "Skill guidance migration has conflicting old and current fields",
            "conflicts": conflicts,
        }
    if not changes:
        return {
            "ok": True,
            "status": "no_delta",
            "migration_id": SKILL_GUIDANCE_MIGRATION_ID,
            "migrated_file_count": 0,
            "residual_obsolete_field_count": 0,
        }

    run_id = f"{utc_now_iso().replace(':', '').replace('-', '')}-{uuid4().hex[:8]}"
    snapshot_root = root / ".local" / "migrations" / SKILL_GUIDANCE_MIGRATION_ID / "snapshots" / run_id
    backups: list[tuple[Path, Path]] = []
    try:
        for path, next_data, _present in changes:
            relative = path.relative_to(root)
            snapshot = snapshot_root / relative
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, snapshot)
            backups.append((path, snapshot))
            write_yaml_file(path, next_data)
        residuals: list[str] = []
        for path in _entry_paths(root):
            data = load_yaml_file(path)
            use = data.get("use") if isinstance(data, dict) else None
            if isinstance(use, dict) and any(field in use for field in OBSOLETE_SKILL_GUIDANCE_FIELDS):
                residuals.append(path.relative_to(root).as_posix())
        if residuals:
            raise RuntimeError("obsolete Skill guidance fields remain: " + ", ".join(residuals))
        receipt = {
            "schema_version": 1,
            "migration_id": SKILL_GUIDANCE_MIGRATION_ID,
            "status": "committed",
            "migrated_at": utc_now_iso(),
            "migrated_file_count": len(changes),
            "migrated_fields": sorted({field for _path, _data, fields in changes for field in fields}),
            "residual_obsolete_field_count": 0,
            "rollback_snapshot": str(snapshot_root),
        }
        _atomic_write_json(_receipt_path(root), receipt)
        return {"ok": True, "status": "committed", "migration_id": SKILL_GUIDANCE_MIGRATION_ID, "receipt": receipt}
    except Exception as exc:
        for path, snapshot in reversed(backups):
            shutil.copy2(snapshot, path)
        return {
            "ok": False,
            "status": "rolled_back",
            "migration_id": SKILL_GUIDANCE_MIGRATION_ID,
            "error": str(exc),
            "rollback_snapshot": str(snapshot_root),
        }
