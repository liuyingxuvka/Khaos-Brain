from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from local_kb.i18n import DEFAULT_LANGUAGE, normalize_language


PERSONAL_MODE = "personal"
ORGANIZATION_MODE = "organization"
VALID_DESKTOP_MODES = {PERSONAL_MODE, ORGANIZATION_MODE}
VALID_ORG_VALIDATION_STATUSES = {"not_configured", "pending", "valid", "invalid"}

DEFAULT_DESKTOP_SETTINGS = {
    "language": DEFAULT_LANGUAGE,
    "mode": PERSONAL_MODE,
    "organization": {
        "repo_url": "",
        "local_mirror_path": "",
        "organization_id": "",
        "validated": False,
        "validation_status": "not_configured",
        "validation_message": "",
        "last_validated_at": "",
        "last_sync_commit": "",
        "last_sync_at": "",
        "organization_maintenance_requested": False,
        "organization_maintenance_validated": False,
        "organization_maintenance_status": "not_configured",
        "organization_maintenance_message": "",
        "maintainer_mode_requested": False,
        "maintainer_validated": False,
        "maintainer_validation_status": "not_configured",
        "maintainer_validation_message": "",
    },
}


def desktop_settings_path(repo_root: Path) -> Path:
    return repo_root / ".local" / "khaos_brain_desktop_settings.json"


def normalize_desktop_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in VALID_DESKTOP_MODES:
        return mode
    return PERSONAL_MODE


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_validation_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in VALID_ORG_VALIDATION_STATUSES:
        return status
    return "not_configured"


def _normalize_organization_maintenance_message(payload: dict[str, Any], maintenance_status: str) -> str:
    if maintenance_status == "valid":
        return ""
    return _normalize_text(payload.get("organization_maintenance_message", payload.get("maintainer_validation_message")))


def _normalize_organization_settings(value: Any) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    validation_status = _normalize_validation_status(payload.get("validation_status"))
    validated = bool(payload.get("validated")) and validation_status == "valid"
    if validated:
        validation_status = "valid"
    maintainer_validation_status = _normalize_validation_status(payload.get("maintainer_validation_status"))
    maintainer_validated = bool(payload.get("maintainer_validated")) and validated and maintainer_validation_status == "valid"
    maintenance_requested = bool(payload.get("organization_maintenance_requested", payload.get("maintainer_mode_requested")))
    maintenance_status = _normalize_validation_status(payload.get("organization_maintenance_status", payload.get("maintainer_validation_status")))
    maintenance_validated = maintenance_requested and validated
    if maintenance_validated:
        maintenance_status = "valid"

    return {
        "repo_url": _normalize_text(payload.get("repo_url")),
        "local_mirror_path": _normalize_text(payload.get("local_mirror_path")),
        "organization_id": _normalize_text(payload.get("organization_id")),
        "validated": validated,
        "validation_status": validation_status,
        "validation_message": _normalize_text(payload.get("validation_message")),
        "last_validated_at": _normalize_text(payload.get("last_validated_at")),
        "last_sync_commit": _normalize_text(payload.get("last_sync_commit")),
        "last_sync_at": _normalize_text(payload.get("last_sync_at")),
        "organization_maintenance_requested": maintenance_requested,
        "organization_maintenance_validated": maintenance_validated,
        "organization_maintenance_status": maintenance_status,
        "organization_maintenance_message": _normalize_organization_maintenance_message(payload, maintenance_status),
        "maintainer_mode_requested": maintenance_requested,
        "maintainer_validated": maintainer_validated,
        "maintainer_validation_status": "valid" if maintainer_validated else maintainer_validation_status,
        "maintainer_validation_message": _normalize_text(payload.get("maintainer_validation_message")),
    }


def load_desktop_settings(repo_root: Path) -> dict[str, Any]:
    path = desktop_settings_path(repo_root)
    if not path.exists():
        return deepcopy(DEFAULT_DESKTOP_SETTINGS)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_DESKTOP_SETTINGS)
    if not isinstance(payload, dict):
        return deepcopy(DEFAULT_DESKTOP_SETTINGS)
    settings = deepcopy(DEFAULT_DESKTOP_SETTINGS)
    settings["language"] = normalize_language(payload.get("language"))
    settings["mode"] = normalize_desktop_mode(payload.get("mode"))
    settings["organization"] = _normalize_organization_settings(payload.get("organization"))
    if settings["mode"] == ORGANIZATION_MODE and not settings["organization"]["validated"]:
        settings["mode"] = PERSONAL_MODE
    return settings


def save_desktop_settings(repo_root: Path, settings: dict[str, Any]) -> Path:
    payload = deepcopy(DEFAULT_DESKTOP_SETTINGS)
    payload["language"] = normalize_language(settings.get("language"))
    payload["mode"] = normalize_desktop_mode(settings.get("mode"))
    payload["organization"] = _normalize_organization_settings(settings.get("organization"))
    if payload["mode"] == ORGANIZATION_MODE and not payload["organization"]["validated"]:
        payload["mode"] = PERSONAL_MODE
    path = desktop_settings_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def organization_sources_from_settings(settings: dict[str, Any]) -> list[dict[str, Any]]:
    if normalize_desktop_mode(settings.get("mode")) != ORGANIZATION_MODE:
        return []
    organization = _normalize_organization_settings(settings.get("organization"))
    if not organization["validated"] or organization["validation_status"] != "valid":
        return []
    if not organization["local_mirror_path"] or not organization["organization_id"]:
        return []
    return [
        {
            "path": organization["local_mirror_path"],
            "organization_id": organization["organization_id"],
            "repo_url": organization["repo_url"],
            "source_commit": organization["last_sync_commit"],
        }
    ]


def maintainer_status_from_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return maintenance_participation_status_from_settings(settings)


def maintenance_participation_status_from_settings(settings: dict[str, Any]) -> dict[str, Any]:
    organization = _normalize_organization_settings(settings.get("organization"))
    source_ready = normalize_desktop_mode(settings.get("mode")) == ORGANIZATION_MODE and organization["validated"]
    requested = bool(organization.get("organization_maintenance_requested"))
    available = requested and source_ready
    if available:
        reason = "organization maintenance participation is enabled"
    elif not source_ready:
        reason = "organization mode is not connected to a validated repository"
    elif not requested:
        reason = "organization maintenance participation is not requested"
    else:
        reason = organization.get("organization_maintenance_message") or "organization maintenance participation is not available"
    return {
        "requested": requested,
        "available": available,
        "validation_status": organization.get("organization_maintenance_status"),
        "reason": reason,
    }
