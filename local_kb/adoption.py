from __future__ import annotations

import copy
from datetime import date, datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from local_kb.card_ids import new_card_id
from local_kb.model_maintenance import load_current_model_entries, publish_sleep_model_generation
from local_kb.models import Entry
from local_kb.org_sources import utc_timestamp
from local_kb.skill_sharing import (
    consolidate_imported_skill_bundles,
    extract_card_bound_skill_bundle_dependencies,
    install_imported_skill_bundle_version,
    resolve_skill_bundle_source_dir,
)
from local_kb.store import load_organization_entries, load_yaml_file


ADOPTION_KEY = "organization_adoption"
EXCHANGE_LEDGER_RELATIVE_PATH = Path(".local") / "organization_exchange_hashes.json"
MODEL_PROJECTION_METADATA_KEYS = {
    "projection_schema_version",
    "projection_digest",
    "authority_generation_id",
    "authority_scope",
    "logicguard_model_id",
    "logicguard_node_id",
    "logicguard_block_id",
    "logicguard_revision_id",
    "logicguard_mesh_id",
    "logicguard_mesh_revision_id",
    "logicguard_open_role_gaps",
}
EXCHANGE_HASH_IGNORED_KEYS = {
    ADOPTION_KEY,
    "organization_proposal",
    "id",
    "scope",
    "status",
    "confidence",
    "source",
    "updated_at",
    "created_at",
    "i18n",
    "related_cards",
    *MODEL_PROJECTION_METADATA_KEYS,
}
EXCHANGE_HASH_ORDER_INSENSITIVE_KEYS = {
    "cross_index",
    "related_cards",
    "required_skills",
    "tags",
    "trigger_keywords",
}


def _safe_segment(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or "card"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _exchange_hash_payload(value: Any, *, key: str = "", top_level: bool = True) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for item_key, item_value in value.items():
            text_key = str(item_key)
            if top_level and text_key in EXCHANGE_HASH_IGNORED_KEYS:
                continue
            normalized_value = _exchange_hash_payload(item_value, key=text_key, top_level=False)
            if normalized_value in ({}, [], "", None):
                continue
            normalized[text_key] = normalized_value
        return normalized
    if isinstance(value, list):
        items = [_exchange_hash_payload(item, key=key, top_level=False) for item in value]
        if key in EXCHANGE_HASH_ORDER_INSENSITIVE_KEYS:
            return sorted(items, key=lambda item: json.dumps(_json_safe(item), ensure_ascii=False, sort_keys=True))
        return items
    if isinstance(value, tuple):
        return [_exchange_hash_payload(item, key=key, top_level=False) for item in value]
    return _json_safe(value)


def card_exchange_hash(data: dict[str, Any]) -> str:
    payload = _exchange_hash_payload(copy.deepcopy(data))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def exchange_ledger_path(repo_root: Path) -> Path:
    return Path(repo_root) / EXCHANGE_LEDGER_RELATIVE_PATH


def load_exchange_ledger(repo_root: Path) -> dict[str, Any]:
    path = exchange_ledger_path(repo_root)
    if not path.exists():
        return {"hashes": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"hashes": {}}
    if not isinstance(payload, dict):
        return {"hashes": {}}
    hashes = payload.get("hashes")
    if not isinstance(hashes, dict):
        payload["hashes"] = {}
    return payload


def write_exchange_ledger(repo_root: Path, payload: dict[str, Any]) -> Path:
    path = exchange_ledger_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def record_exchange_hash(
    repo_root: Path,
    content_hash: str,
    *,
    direction: str,
    organization_id: str = "",
    source_repo: str = "",
    source_path: str = "",
    local_path: str = "",
    entry_id: str = "",
) -> None:
    content_hash = str(content_hash or "").strip()
    if not content_hash:
        return
    ledger = load_exchange_ledger(repo_root)
    hashes = ledger.setdefault("hashes", {})
    if not isinstance(hashes, dict):
        hashes = {}
        ledger["hashes"] = hashes
    now = utc_timestamp()
    item = hashes.get(content_hash)
    if not isinstance(item, dict):
        item = {"first_seen_at": now, "events": []}
    item["last_seen_at"] = now
    events = item.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        item["events"] = events
    events.append(
        {
            "direction": str(direction or "").strip(),
            "organization_id": str(organization_id or "").strip(),
            "source_repo": str(source_repo or "").strip(),
            "source_path": str(source_path or "").strip(),
            "local_path": str(local_path or "").strip(),
            "entry_id": str(entry_id or "").strip(),
            "created_at": now,
        }
    )
    hashes[content_hash] = item
    write_exchange_ledger(repo_root, ledger)


def recorded_exchange_hashes(repo_root: Path, directions: set[str] | None = None) -> set[str]:
    ledger = load_exchange_ledger(repo_root)
    hashes = ledger.get("hashes") if isinstance(ledger.get("hashes"), dict) else {}
    if not directions:
        return {str(content_hash) for content_hash in hashes}
    selected: set[str] = set()
    for content_hash, item in hashes.items():
        events = item.get("events") if isinstance(item, dict) else []
        if not isinstance(events, list):
            continue
        if any(str(event.get("direction") or "") in directions for event in events if isinstance(event, dict)):
            selected.add(str(content_hash))
    return selected


def adoption_content_hash(data: dict[str, Any]) -> str:
    payload = copy.deepcopy(data)
    payload.pop(ADOPTION_KEY, None)
    payload.pop("id", None)
    payload.pop("related_cards", None)
    for field in MODEL_PROJECTION_METADATA_KEYS:
        payload.pop(field, None)
    payload = _exchange_hash_payload(payload, top_level=False)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def adoption_state(data: dict[str, Any]) -> str:
    metadata = data.get(ADOPTION_KEY) if isinstance(data.get(ADOPTION_KEY), dict) else {}
    explicit = str(metadata.get("state") or "").strip()
    if explicit in {"feedback_ready", "locally_rejected"}:
        return explicit
    source_hash = str(metadata.get("source_content_hash") or "").strip()
    if source_hash and source_hash == adoption_content_hash(data):
        return "clean"
    return "diverged"


def adoption_key_from_data(data: dict[str, Any]) -> tuple[str, str, str]:
    metadata = data.get(ADOPTION_KEY) if isinstance(data.get(ADOPTION_KEY), dict) else {}
    return (
        str(metadata.get("organization_id") or "").strip(),
        str(metadata.get("source_entry_id") or "").strip(),
        str(metadata.get("source_repo") or "").strip(),
    )


def organization_key_from_entry(entry: Entry) -> tuple[str, str, str]:
    source = entry.source
    return (
        str(source.get("organization_id") or source.get("source_id") or "").strip(),
        str(entry.data.get("id") or "").strip(),
        str(source.get("source_repo") or "").strip(),
    )


def adopted_organization_keys(repo_root: Path) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for entry in load_current_model_entries(repo_root)[0]:
        key = adoption_key_from_data(entry.data)
        if key[0] and key[1]:
            keys.add(key)
            keys.add((key[0], key[1], ""))
    return keys


def local_exchange_hashes(repo_root: Path) -> set[str]:
    hashes: set[str] = set()
    for entry in load_current_model_entries(repo_root)[0]:
        hashes.add(card_exchange_hash(entry.data))
    return hashes


def blocked_organization_download_hashes(repo_root: Path) -> set[str]:
    return local_exchange_hashes(repo_root) | recorded_exchange_hashes(
        repo_root,
        {"downloaded", "used", "absorbed", "exported", "uploaded"},
    )


def _local_preference_rank(entry: Entry) -> tuple[int, int, int, str]:
    data = entry.data
    has_adoption = isinstance(data.get(ADOPTION_KEY), dict)
    source_scope = str(entry.source.get("scope") or "").strip().lower()
    status = str(data.get("status") or "").strip().lower()
    scope_rank = {"public": 0, "private": 1, "candidate": 2}.get(source_scope, 3)
    status_rank = {"trusted": 0, "approved": 0, "candidate": 1, "deprecated": 3}.get(status, 2)
    return (1 if has_adoption else 0, scope_rank, status_rank, str(entry.path))


def dedupe_local_entries_by_exchange_hash(entries: list[Entry]) -> list[Entry]:
    by_hash: dict[str, Entry] = {}
    for entry in entries:
        content_hash = card_exchange_hash(entry.data)
        existing = by_hash.get(content_hash)
        if existing is None or _local_preference_rank(entry) < _local_preference_rank(existing):
            by_hash[content_hash] = entry
    preferred_paths = {entry.path for entry in by_hash.values()}
    return [entry for entry in entries if entry.path in preferred_paths]


def find_local_entry_by_exchange_hash(repo_root: Path, content_hash: str) -> Entry | None:
    matches = [
        entry
        for entry in load_current_model_entries(repo_root)[0]
        if card_exchange_hash(entry.data) == content_hash
    ]
    if not matches:
        return None
    return sorted(matches, key=_local_preference_rank)[0]


def adopted_card_path(repo_root: Path, organization_id: str, entry_id: str) -> Path:
    return repo_root / "kb" / "candidates" / "adopted" / _safe_segment(organization_id) / f"{_safe_segment(entry_id)}.yaml"


def find_adopted_entry_by_source(
    repo_root: Path,
    *,
    organization_id: str,
    source_entry_id: str,
    source_repo: str = "",
    source_exchange_hash: str = "",
) -> Entry | None:
    matches: list[Entry] = []
    for entry in load_current_model_entries(repo_root)[0]:
        metadata = entry.data.get(ADOPTION_KEY) if isinstance(entry.data.get(ADOPTION_KEY), dict) else {}
        if str(metadata.get("organization_id") or "").strip() != str(organization_id or "").strip():
            continue
        if str(metadata.get("source_entry_id") or "").strip() != str(source_entry_id or "").strip():
            continue
        if source_repo and str(metadata.get("source_repo") or "").strip() != str(source_repo or "").strip():
            continue
        if source_exchange_hash and str(metadata.get("source_exchange_hash") or "").strip() != source_exchange_hash:
            continue
        matches.append(entry)
    if not matches:
        return None
    return sorted(matches, key=_local_preference_rank)[0]


def find_organization_entry(
    entry_id: str,
    organization_sources: list[dict[str, Any]],
    source_info: dict[str, Any] | None = None,
) -> Entry | None:
    source_info = source_info if isinstance(source_info, dict) else {}
    for source in organization_sources:
        org_root = Path(str(source.get("path") or source.get("local_path") or ""))
        organization_id = str(source.get("organization_id") or source.get("id") or "").strip()
        if not org_root.exists() or not organization_id:
            continue
        entries = load_organization_entries(
            org_root,
            organization_id,
            source_repo=str(source.get("source_repo") or source.get("repo_url") or ""),
            source_commit=str(source.get("source_commit") or ""),
        )
        for entry in entries:
            if str(entry.data.get("id") or "").strip() != str(entry_id or "").strip():
                continue
            if source_info:
                expected_path = str(source_info.get("path") or "").strip()
                if expected_path and str(entry.source.get("path") or "").strip() != expected_path:
                    continue
                expected_org = str(source_info.get("organization_id") or "").strip()
                if expected_org and str(entry.source.get("organization_id") or "").strip() != expected_org:
                    continue
            return entry
    return None


def adopt_organization_entry(repo_root: Path, entry: Entry) -> dict[str, Any]:
    if entry.source.get("kind") != "organization":
        return {"ok": False, "error": "entry is not from an organization source"}
    entry_id = str(entry.data.get("id") or entry.path.stem).strip()
    organization_id = str(entry.source.get("organization_id") or entry.source.get("source_id") or "org").strip()
    now = utc_timestamp()
    source_hash = adoption_content_hash(entry.data)
    source_exchange_hash = card_exchange_hash(entry.data)
    existing_adoption = find_adopted_entry_by_source(
        repo_root,
        organization_id=organization_id,
        source_entry_id=entry_id,
        source_repo=str(entry.source.get("source_repo") or ""),
        source_exchange_hash=source_exchange_hash,
    )
    if existing_adoption is not None:
        target_path = existing_adoption.path
        installed_skill_bundles = adopt_entry_skill_bundles(
            repo_root,
            entry,
            source_card_id=str(existing_adoption.data.get("id") or target_path.stem),
        )
        existing = copy.deepcopy(existing_adoption.data)
        metadata = existing.get(ADOPTION_KEY) if isinstance(existing.get(ADOPTION_KEY), dict) else {}
        hit_count = int(metadata.get("hit_count") or 0) if str(metadata.get("hit_count") or "").isdigit() else 0
        metadata.update(
            {
                "last_used_at": now,
                "hit_count": hit_count + 1,
                "source_exchange_hash": metadata.get("source_exchange_hash") or source_exchange_hash,
            }
        )
        existing[ADOPTION_KEY] = metadata
        publication = publish_sleep_model_generation(
            repo_root,
            reason="organization-adoption-metadata-update",
            card_upserts={target_path.relative_to(repo_root).as_posix(): existing},
        )
        if not publication.get("ok"):
            return {
                "ok": False,
                "error": str(publication.get("error") or publication.get("status")),
                "model_generation": publication,
            }
        record_exchange_hash(
            repo_root,
            source_exchange_hash,
            direction="used",
            organization_id=organization_id,
            source_repo=str(entry.source.get("source_repo") or ""),
            source_path=str(entry.source.get("path") or ""),
            local_path=str(target_path),
            entry_id=str(existing.get("id") or target_path.stem),
        )
        active_index_receipt = (
            publication.get("receipt", {}).get("index_receipt", {})
            if publication.get("status") == "committed"
            else publication.get("index_receipt", {})
        )
        return {
            "ok": True,
            "created": False,
            "path": str(target_path),
            "entry_id": str(existing.get("id") or entry_id),
            "state": adoption_state(existing),
            "hit_count": metadata["hit_count"],
            "installed_skill_bundles": installed_skill_bundles,
            "active_index_receipt": active_index_receipt,
        }

    existing_local = find_local_entry_by_exchange_hash(repo_root, source_exchange_hash)
    if existing_local is not None:
        installed_skill_bundles = adopt_entry_skill_bundles(
            repo_root,
            entry,
            source_card_id=str(existing_local.data.get("id") or existing_local.path.stem),
        )
        record_exchange_hash(
            repo_root,
            source_exchange_hash,
            direction="absorbed",
            organization_id=organization_id,
            source_repo=str(entry.source.get("source_repo") or ""),
            source_path=str(entry.source.get("path") or ""),
            local_path=str(existing_local.path),
            entry_id=str(existing_local.data.get("id") or existing_local.path.stem),
        )
        return {
            "ok": True,
            "created": False,
            "matched_existing": True,
            "path": str(existing_local.path),
            "entry_id": str(existing_local.data.get("id") or existing_local.path.stem),
            "state": "already_local",
            "hit_count": 1,
            "source_exchange_hash": source_exchange_hash,
            "installed_skill_bundles": installed_skill_bundles,
        }

    payload = copy.deepcopy(entry.data)
    payload["id"] = new_card_id(repo_root, prefix="cand", generated_at=now)
    payload[ADOPTION_KEY] = {
        "organization_id": organization_id,
        "source_entry_id": entry_id,
        "source_repo": str(entry.source.get("source_repo") or ""),
        "source_commit": str(entry.source.get("source_commit") or ""),
        "source_path": str(entry.source.get("path") or ""),
        "adopted_at": now,
        "last_used_at": now,
        "hit_count": 1,
        "source_content_hash": source_hash,
        "source_exchange_hash": source_exchange_hash,
        "state": "clean",
    }
    target_path = adopted_card_path(repo_root, organization_id, str(payload["id"]))
    publication = publish_sleep_model_generation(
        repo_root,
        reason="organization-adoption-created",
        card_upserts={target_path.relative_to(repo_root).as_posix(): payload},
    )
    if not publication.get("ok"):
        return {
            "ok": False,
            "error": str(publication.get("error") or publication.get("status")),
            "model_generation": publication,
        }
    installed_skill_bundles = adopt_entry_skill_bundles(repo_root, entry, source_card_id=str(payload["id"]))
    record_exchange_hash(
        repo_root,
        source_exchange_hash,
        direction="downloaded",
        organization_id=organization_id,
        source_repo=str(entry.source.get("source_repo") or ""),
        source_path=str(entry.source.get("path") or ""),
        local_path=str(target_path),
        entry_id=str(payload["id"]),
    )
    active_index_receipt = (
        publication.get("receipt", {}).get("index_receipt", {})
        if publication.get("status") == "committed"
        else publication.get("index_receipt", {})
    )
    return {
        "ok": True,
        "created": True,
        "path": str(target_path),
        "entry_id": str(payload["id"]),
        "state": "clean",
        "hit_count": 1,
        "source_exchange_hash": source_exchange_hash,
        "installed_skill_bundles": installed_skill_bundles,
        "active_index_receipt": active_index_receipt,
    }


def adopt_organization_entry_by_source_info(
    repo_root: Path,
    entry_id: str,
    organization_sources: list[dict[str, Any]],
    source_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = find_organization_entry(entry_id, organization_sources, source_info=source_info)
    if entry is None:
        return {"ok": False, "error": "organization entry not found"}
    return adopt_organization_entry(repo_root, entry)


def _organization_root_for_entry(entry: Entry) -> Path:
    relative = Path(str(entry.source.get("path") or ""))
    if relative.parts:
        try:
            return entry.path.parents[len(relative.parts) - 1]
        except IndexError:
            pass
    return entry.path.parents[2] if len(entry.path.parents) > 2 else entry.path.parent


def adopt_entry_skill_bundles(repo_root: Path, entry: Entry, *, source_card_id: str = "") -> dict[str, Any]:
    if entry.source.get("kind") != "organization":
        return {"ok": True, "installed": [], "errors": [], "consolidation": {"ok": True, "bundle_count": 0}}

    installed: list[dict[str, Any]] = []
    errors: list[str] = []
    org_root = _organization_root_for_entry(entry)
    for dependency in extract_card_bound_skill_bundle_dependencies(entry.data):
        source_dir = resolve_skill_bundle_source_dir(org_root, entry.source, dependency)
        if source_dir is None:
            errors.append(f"missing Skill bundle source for {dependency.get('bundle_id') or dependency.get('id')}")
            continue
        result = install_imported_skill_bundle_version(
            repo_root,
            dependency,
            source_dir,
            source_card_id=source_card_id or str(entry.data.get("id") or entry.path.stem),
            status="approved" if str(entry.data.get("status") or "").strip() in {"trusted", "approved"} else "candidate",
        )
        if result.get("ok"):
            installed.append(result)
        else:
            errors.extend(str(error) for error in result.get("errors") or [])

    consolidation = consolidate_imported_skill_bundles(repo_root)
    return {
        "ok": not errors and bool(consolidation.get("ok")),
        "installed": installed,
        "errors": errors,
        "consolidation": consolidation,
    }
