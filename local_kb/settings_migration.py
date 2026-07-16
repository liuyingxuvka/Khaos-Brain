from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from local_kb.common import utc_now_iso
from local_kb.settings import (
    CURRENT_DESKTOP_SETTINGS_SCHEMA_VERSION,
    CURRENT_DESKTOP_SETTINGS_KEYS,
    CURRENT_ORGANIZATION_SETTING_KEYS,
    DEFAULT_DESKTOP_SETTINGS,
    current_desktop_settings_issues,
    desktop_settings_path,
    load_desktop_settings,
    save_desktop_settings,
)


SETTINGS_MIGRATION_ID = "desktop-settings-direct-to-v1"
OBSOLETE_ORGANIZATION_SETTING_KEYS = frozenset(
    {
        "maintainer_mode_requested",
        "maintainer_validated",
        "maintainer_validation_status",
        "maintainer_validation_message",
    }
)
OBSOLETE_TO_CURRENT = {
    "maintainer_mode_requested": "organization_maintenance_requested",
    "maintainer_validated": "organization_maintenance_validated",
    "maintainer_validation_status": "organization_maintenance_status",
    "maintainer_validation_message": "organization_maintenance_message",
}


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
    return Path(repo_root) / ".local" / "migrations" / SETTINGS_MIGRATION_ID / "current-receipt.json"


def _snapshot_path(repo_root: Path, run_id: str) -> Path:
    return Path(repo_root) / ".local" / "migrations" / SETTINGS_MIGRATION_ID / "snapshots" / f"{run_id}.json"


def migrate_desktop_settings_to_current(
    repo_root: Path,
    *,
    conflict_resolution: Mapping[str, Any] | None = None,
    resolution_reason: str = "",
) -> dict[str, Any]:
    """Directly rewrite the exact retired desktop-settings shape once.

    Daily settings readers do not call this module and reject every non-current
    persisted shape.
    """

    root = Path(repo_root)
    path = desktop_settings_path(root)
    if not path.exists():
        return {
            "ok": True,
            "status": "no_delta",
            "migration_id": SETTINGS_MIGRATION_ID,
            "settings_present": False,
            "residual_obsolete_field_count": 0,
        }
    try:
        raw_text = path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "status": "blocked",
            "migration_id": SETTINGS_MIGRATION_ID,
            "error": f"desktop settings are unreadable: {exc}",
        }
    if not isinstance(raw, dict):
        return {
            "ok": False,
            "status": "blocked",
            "migration_id": SETTINGS_MIGRATION_ID,
            "error": "desktop settings are neither the exact retired mapping nor the current mapping",
        }
    if not current_desktop_settings_issues(raw):
        prior_receipt: dict[str, Any] = {}
        receipt_path = _receipt_path(root)
        if receipt_path.is_file():
            try:
                candidate = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                candidate = {}
            current_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            if (
                isinstance(candidate, dict)
                and candidate.get("migration_id") == SETTINGS_MIGRATION_ID
                and candidate.get("status") == "committed"
                and candidate.get("current_settings_sha256") == current_sha256
                and int(candidate.get("residual_obsolete_field_count") or 0) == 0
            ):
                prior_receipt = candidate
        return {
            "ok": True,
            "status": "no_delta",
            "migration_id": SETTINGS_MIGRATION_ID,
            "settings_present": True,
            "residual_obsolete_field_count": 0,
            **({"receipt": prior_receipt} if prior_receipt else {}),
        }

    allowed_top = set(CURRENT_DESKTOP_SETTINGS_KEYS)
    allowed_top.discard("schema_version")
    unknown_top = sorted(set(raw) - allowed_top - {"schema_version"})
    organization = raw.get("organization", {})
    if not isinstance(organization, dict):
        return {
            "ok": False,
            "status": "blocked",
            "migration_id": SETTINGS_MIGRATION_ID,
            "error": "retired desktop settings organization must be a mapping",
        }
    allowed_organization = set(CURRENT_ORGANIZATION_SETTING_KEYS) | set(OBSOLETE_ORGANIZATION_SETTING_KEYS)
    unknown_organization = sorted(set(organization) - allowed_organization)
    schema = raw.get("schema_version")
    if unknown_top or unknown_organization or schema not in (None, CURRENT_DESKTOP_SETTINGS_SCHEMA_VERSION):
        return {
            "ok": False,
            "status": "blocked",
            "migration_id": SETTINGS_MIGRATION_ID,
            "error": "desktop settings contain an unknown retired format",
            "unknown_top_level_keys": unknown_top,
            "unknown_organization_keys": unknown_organization,
        }

    migrated_organization = dict(organization)
    conflicts: list[str] = []
    conflict_details: dict[str, dict[str, Any]] = {}
    migrated_fields: list[str] = []
    for obsolete, current in OBSOLETE_TO_CURRENT.items():
        if obsolete not in migrated_organization:
            continue
        if current in migrated_organization and migrated_organization[current] != migrated_organization[obsolete]:
            conflicts.append(f"{obsolete}->{current}")
            conflict_details[current] = {
                "obsolete_field": obsolete,
                "obsolete_value": migrated_organization[obsolete],
                "current_value": migrated_organization[current],
            }
            continue
        migrated_organization[current] = migrated_organization[obsolete]
        migrated_organization.pop(obsolete, None)
        migrated_fields.append(obsolete)
    if conflicts:
        resolution = dict(conflict_resolution or {})
        expected = set(conflict_details)
        if set(resolution) != expected or not str(resolution_reason or "").strip():
            return {
                "ok": False,
                "status": "blocked",
                "migration_id": SETTINGS_MIGRATION_ID,
                "error": "desktop settings migration has conflicting old and current values",
                "conflicts": conflicts,
                "required_resolution_fields": sorted(expected),
            }
        for current, detail in conflict_details.items():
            selected = resolution[current]
            allowed = (detail["obsolete_value"], detail["current_value"])
            if selected not in allowed:
                return {
                    "ok": False,
                    "status": "blocked",
                    "migration_id": SETTINGS_MIGRATION_ID,
                    "error": "AI conflict resolution selected a value absent from the exact old/current inputs",
                    "field": current,
                }
            migrated_organization[current] = selected
            migrated_organization.pop(str(detail["obsolete_field"]), None)
            migrated_fields.append(str(detail["obsolete_field"]))
            detail["selected_value"] = selected

    current_input = deepcopy(DEFAULT_DESKTOP_SETTINGS)
    current_input.update({key: value for key, value in raw.items() if key in {"language", "mode"}})
    current_input["schema_version"] = CURRENT_DESKTOP_SETTINGS_SCHEMA_VERSION
    current_input["organization"].update(migrated_organization)
    run_id = f"{utc_now_iso().replace(':', '').replace('-', '')}-{uuid4().hex[:8]}"
    snapshot = _snapshot_path(root, run_id)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(raw_text, encoding="utf-8")
    try:
        save_desktop_settings(root, current_input)
        current = load_desktop_settings(root)
        residuals = sorted(OBSOLETE_ORGANIZATION_SETTING_KEYS.intersection(current["organization"]))
        if residuals:
            raise RuntimeError("obsolete desktop settings fields remain: " + ", ".join(residuals))
        receipt = {
            "schema_version": 1,
            "migration_id": SETTINGS_MIGRATION_ID,
            "status": "committed",
            "migrated_at": utc_now_iso(),
            "migrated_fields": migrated_fields,
            "residual_obsolete_field_count": 0,
            "rollback_snapshot": str(snapshot),
            "source_settings_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "current_settings_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "ai_conflict_resolution": (
                {
                    "resolver": "ai-upgrade-owner",
                    "reason": str(resolution_reason).strip(),
                    "fields": conflict_details,
                }
                if conflict_details
                else {}
            ),
        }
        _atomic_write_json(_receipt_path(root), receipt)
        return {"ok": True, "status": "committed", "migration_id": SETTINGS_MIGRATION_ID, "receipt": receipt}
    except Exception as exc:
        path.write_text(raw_text, encoding="utf-8")
        return {
            "ok": False,
            "status": "rolled_back",
            "migration_id": SETTINGS_MIGRATION_ID,
            "error": str(exc),
            "rollback_snapshot": str(snapshot),
        }
