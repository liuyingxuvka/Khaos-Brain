from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Mapping
from uuid import uuid4

from local_kb.common import utc_now_iso
from local_kb.lifecycle import (
    entry_is_retrieval_eligible,
    effective_entry_status,
    load_lifecycle_state,
)
from local_kb.logicguard_models import (
    AUTHORITY_GENERATION_WRITERS,
    ExactBindingError,
    load_authority_generation,
    validate_authority_generation_payload,
)
from local_kb.model_projection import (
    ProjectionValidationError,
    active_index_binding_record,
    validate_card_projections,
    validate_projection_path_scope,
)
from local_kb.models import Entry
from local_kb.store import build_local_entry_source, load_yaml_file


ACTIVE_INDEX_SCHEMA_VERSION = 4
ACTIVE_INDEX_POINTER_SCHEMA_VERSION = 1
ACTIVE_INDEX_DENY_SCHEMA_VERSION = 1
ACTIVE_INDEX_CORRUPTION_SCHEMA_VERSION = 1
ACTIVE_INDEX_PATH = Path("kb") / "indexes" / "active.json"
ACTIVE_INDEX_GENERATION_DIR = Path("kb") / "indexes" / "generations"
ACTIVE_INDEX_DENY_DIR = Path("kb") / "indexes" / "denies"
ACTIVE_INDEX_CORRUPTION_PATH = Path("kb") / "indexes" / "active-corruption.json"
# Retired v3 authorities. Upgrade/Sleep publication removes these files; normal
# reads never consult them.
RETIRED_ACTIVE_INDEX_AUTHORITY_PATH = Path("kb") / "indexes" / "active-authority.json"
RETIRED_ACTIVE_INDEX_INVALIDATION_PATH = Path("kb") / "indexes" / "active-invalidated.json"
INDEX_SCOPES = ("public", "private", "candidates")
TERMINAL_STATUSES = {
    "merged", "rejected", "superseded", "parked", "retired", "deprecated", "history_only"
}
ACTIVE_INDEX_PUBLISHERS = frozenset(AUTHORITY_GENERATION_WRITERS)
ACTIVE_INDEX_IMPACTS = frozenset(
    {"none", "additive_pending", "entry_revoke", "entry_replace", "global_current_corruption"}
)


def active_index_path(repo_root: Path) -> Path:
    """Return the sole current active-index pointer path."""

    return Path(repo_root) / ACTIVE_INDEX_PATH


def active_index_generation_dir(repo_root: Path) -> Path:
    return Path(repo_root) / ACTIVE_INDEX_GENERATION_DIR


def active_index_deny_dir(repo_root: Path) -> Path:
    return Path(repo_root) / ACTIVE_INDEX_DENY_DIR


def active_index_corruption_path(repo_root: Path) -> Path:
    return Path(repo_root) / ACTIVE_INDEX_CORRUPTION_PATH


def active_index_authority_path(repo_root: Path) -> Path:
    """Return the retired v3 authority path for migration/residual checks only."""

    return Path(repo_root) / RETIRED_ACTIVE_INDEX_AUTHORITY_PATH


def active_index_invalidation_path(repo_root: Path) -> Path:
    """Return the retired unscoped invalidation path for residual checks only."""

    return Path(repo_root) / RETIRED_ACTIVE_INDEX_INVALIDATION_PATH


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(f"Unsupported active-index value: {type(value).__name__}")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default
    )


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=_json_default))


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_digest_name(value: str) -> str:
    normalized = str(value).removeprefix("sha256:")
    if not normalized or any(character not in "0123456789abcdef" for character in normalized.lower()):
        raise ValueError("A canonical sha256 digest is required")
    return normalized.lower()


def lifecycle_entry_digest(lifecycle_state: Mapping[str, Any]) -> str:
    """Digest only lifecycle fields that can change retrieval eligibility."""

    entries = lifecycle_state.get("entries", {})
    if not isinstance(entries, Mapping):
        return _digest({})
    projection: dict[str, dict[str, Any]] = {}
    for entry_id, raw_state in sorted(entries.items(), key=lambda item: str(item[0])):
        if not isinstance(raw_state, Mapping):
            continue
        row: dict[str, Any] = {"status": str(raw_state.get("status") or "")}
        if "retrieval_eligible" in raw_state:
            row["retrieval_eligible"] = bool(raw_state.get("retrieval_eligible"))
        if "suspended" in raw_state:
            row["suspended"] = bool(raw_state.get("suspended"))
        projection[str(entry_id)] = row
    return _digest(projection)


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _write_immutable(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        existing = _read_json_object(path)
        if existing != dict(payload):
            raise RuntimeError(f"Immutable active-index artifact cannot be rebound: {path}")
        return
    _atomic_write(path, payload)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _relative_managed_path(repo_root: Path, path: Path, *, parent: Path) -> str:
    root = Path(repo_root).resolve()
    resolved = path.resolve(strict=False)
    resolved.relative_to((root / parent).resolve(strict=False))
    return resolved.relative_to(root).as_posix()


def _resolve_managed_path(repo_root: Path, relative: str, *, parent: Path) -> Path:
    root = Path(repo_root).resolve()
    path = (root / str(relative)).resolve(strict=True)
    path.relative_to((root / parent).resolve(strict=False))
    return path


def source_manifest(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scope in INDEX_SCOPES:
        scope_root = Path(repo_root) / "kb" / scope
        if not scope_root.exists():
            continue
        for path in sorted(scope_root.rglob("*.yaml")):
            stat = path.stat()
            rows.append(
                {
                    "scope": scope,
                    "path": path.relative_to(repo_root).as_posix(),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
            )
    return rows


def source_manifest_digest(repo_root: Path) -> str:
    return _digest(source_manifest(repo_root))


def classify_active_index_impact(
    *,
    was_retrieval_eligible: bool,
    is_retrieval_eligible: bool,
    content_changed: bool = False,
    current_corruption: bool = False,
) -> str:
    """Classify a mutation without converting harmless work into an outage."""

    if current_corruption:
        return "global_current_corruption"
    if was_retrieval_eligible and not is_retrieval_eligible:
        return "entry_revoke"
    if was_retrieval_eligible and is_retrieval_eligible and content_changed:
        return "entry_replace"
    if not was_retrieval_eligible and is_retrieval_eligible:
        return "additive_pending"
    return "none"


def _empty_deny_payload(artifact: Mapping[str, Any], artifact_path: str) -> dict[str, Any]:
    unsigned = {
        "schema_version": ACTIVE_INDEX_DENY_SCHEMA_VERSION,
        "index_generation": int(artifact.get("generation") or 0),
        "index_artifact_path": artifact_path,
        "index_artifact_digest": _digest(artifact),
        "authority_generation_id": str(artifact.get("authority_generation_id") or ""),
        "denied_records": [],
    }
    return {**unsigned, "deny_digest": _digest(unsigned)}


def _pointer_payload(
    *, artifact: Mapping[str, Any], artifact_path: str, deny: Mapping[str, Any], deny_path: str
) -> dict[str, Any]:
    unsigned = {
        "schema_version": ACTIVE_INDEX_POINTER_SCHEMA_VERSION,
        "activated_at": utc_now_iso(),
        "generation": int(artifact.get("generation") or 0),
        "artifact_path": artifact_path,
        "artifact_digest": _digest(artifact),
        "content_digest": str(artifact.get("content_digest") or ""),
        "indexed_record_count": int(artifact.get("indexed_record_count") or 0),
        "authority_generation_id": str(artifact.get("authority_generation_id") or ""),
        "authority_generation_digest": str(artifact.get("authority_generation_digest") or ""),
        "deny_path": deny_path,
        "deny_digest": str(deny.get("deny_digest") or ""),
    }
    digest_source = {key: value for key, value in unsigned.items() if key != "activated_at"}
    return {**unsigned, "pointer_digest": _digest(digest_source)}


def _pointer_issues(pointer: Mapping[str, Any]) -> list[str]:
    if int(pointer.get("schema_version") or 0) != ACTIVE_INDEX_POINTER_SCHEMA_VERSION:
        return ["active index current pointer is missing or unsupported"]
    digest_source = {
        key: value for key, value in pointer.items() if key not in {"activated_at", "pointer_digest"}
    }
    issues: list[str] = []
    if _digest(digest_source) != str(pointer.get("pointer_digest") or ""):
        issues.append("active index current pointer digest mismatch")
    for field in (
        "artifact_path", "artifact_digest", "content_digest", "authority_generation_id",
        "authority_generation_digest", "deny_path", "deny_digest",
    ):
        if not str(pointer.get(field) or ""):
            issues.append(f"active index current pointer does not bind {field}")
    return issues


def _artifact_issues(artifact: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if int(artifact.get("schema_version") or 0) != ACTIVE_INDEX_SCHEMA_VERSION:
        issues.append("active index artifact schema version is unsupported")
    records = artifact.get("records", []) if isinstance(artifact.get("records"), list) else []
    identities: set[str] = set()
    generation_id = str(artifact.get("authority_generation_id") or "")
    for record in records:
        if not isinstance(record, Mapping):
            issues.append("active index artifact contains a non-object record")
            continue
        entry_id = str(record.get("entry_id") or "")
        if not entry_id or entry_id in identities:
            issues.append(f"active index artifact has a missing or duplicate entry id: {entry_id}")
        identities.add(entry_id)
        status = str(record.get("status") or "").lower()
        if status in TERMINAL_STATUSES or status not in {"trusted", "candidate"}:
            issues.append(f"ineligible status {status} indexed for {entry_id}")
        data = record.get("data", {}) if isinstance(record.get("data"), Mapping) else {}
        if _digest(data) != str(record.get("content_digest") or ""):
            issues.append(f"content digest mismatch for {entry_id}")
        if str(record.get("authority_generation_id") or "") != generation_id:
            issues.append(f"authority generation mismatch for {entry_id}")
        if str(record.get("projection_digest") or "") != str(data.get("projection_digest") or ""):
            issues.append(f"projection digest binding mismatch for {entry_id}")
        for field in (
            "authority_scope", "logicguard_model_id", "logicguard_node_id", "logicguard_block_id",
            "logicguard_revision_id", "logicguard_mesh_id", "logicguard_mesh_revision_id", "projection_digest",
        ):
            if not str(record.get(field) or ""):
                issues.append(f"exact LogicGuard binding field {field} is missing for {entry_id}")
    if len(records) != int(artifact.get("indexed_record_count") or 0):
        issues.append("indexed_record_count does not match records")
    generation_source = {
        "schema_version": ACTIVE_INDEX_SCHEMA_VERSION,
        "source_manifest": artifact.get("source_manifest", []),
        "lifecycle_entry_digest": artifact.get("lifecycle_entry_digest", ""),
        "authority_generation_id": artifact.get("authority_generation_id", ""),
        "authority_generation_digest": artifact.get("authority_generation_digest", ""),
        "records": [
            _json_safe(dict(record))
            for record in records if isinstance(record, Mapping)
        ],
        "excluded_status_counts": artifact.get("excluded_status_counts", {}),
    }
    if _digest(generation_source) != str(artifact.get("content_digest") or ""):
        issues.append("active index artifact content digest is not reproducible")
    return issues


def _deny_issues(deny: Mapping[str, Any], artifact: Mapping[str, Any], artifact_path: str) -> list[str]:
    issues: list[str] = []
    if int(deny.get("schema_version") or 0) != ACTIVE_INDEX_DENY_SCHEMA_VERSION:
        return ["active index deny projection is missing or unsupported"]
    unsigned = {key: value for key, value in deny.items() if key != "deny_digest"}
    if _digest(unsigned) != str(deny.get("deny_digest") or ""):
        issues.append("active index deny projection digest mismatch")
    bindings = {
        "index_generation": int(artifact.get("generation") or 0),
        "index_artifact_path": artifact_path,
        "index_artifact_digest": _digest(artifact),
        "authority_generation_id": str(artifact.get("authority_generation_id") or ""),
    }
    for field, expected in bindings.items():
        actual = int(deny.get(field) or 0) if isinstance(expected, int) else str(deny.get(field) or "")
        if actual != expected:
            issues.append(f"active index deny projection does not bind {field}")
    records = artifact.get("records", []) if isinstance(artifact.get("records"), list) else []
    exact_records = {
        (str(row.get("entry_id") or ""), str(row.get("content_digest") or ""))
        for row in records if isinstance(row, Mapping)
    }
    seen: set[tuple[str, str]] = set()
    denied = deny.get("denied_records", []) if isinstance(deny.get("denied_records"), list) else []
    for row in denied:
        if not isinstance(row, Mapping):
            issues.append("active index deny projection contains a non-object row")
            continue
        identity = (str(row.get("entry_id") or ""), str(row.get("content_digest") or ""))
        if identity in seen or identity not in exact_records:
            issues.append(f"active index deny projection has a non-exact row for {identity[0]}")
        seen.add(identity)
    return issues


def _load_snapshot(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    pointer = _read_json_object(active_index_path(repo_root))
    issues = _pointer_issues(pointer)
    artifact: dict[str, Any] = {}
    deny: dict[str, Any] = {}
    if issues:
        return pointer, artifact, deny, issues
    try:
        artifact_path = _resolve_managed_path(
            repo_root, str(pointer["artifact_path"]), parent=ACTIVE_INDEX_GENERATION_DIR
        )
        artifact = _read_json_object(artifact_path)
    except (OSError, ValueError, KeyError):
        issues.append("active index immutable artifact is missing or outside its managed directory")
        return pointer, artifact, deny, issues
    if _digest(artifact) != str(pointer.get("artifact_digest") or ""):
        issues.append("active index immutable artifact digest mismatch")
    issues.extend(_artifact_issues(artifact))
    if str(artifact.get("content_digest") or "") != str(pointer.get("content_digest") or ""):
        issues.append("active index pointer content binding mismatch")
    try:
        deny_path = _resolve_managed_path(repo_root, str(pointer["deny_path"]), parent=ACTIVE_INDEX_DENY_DIR)
        deny = _read_json_object(deny_path)
    except (OSError, ValueError, KeyError):
        issues.append("active index immutable deny projection is missing or outside its managed directory")
        return pointer, artifact, deny, issues
    if _digest({key: value for key, value in deny.items() if key != "deny_digest"}) != str(
        pointer.get("deny_digest") or ""
    ):
        issues.append("active index pointer deny binding mismatch")
    issues.extend(_deny_issues(deny, artifact, str(pointer.get("artifact_path") or "")))
    return pointer, artifact, deny, issues


def _current_corruption_issue(repo_root: Path, pointer: Mapping[str, Any]) -> str | None:
    marker_path = active_index_corruption_path(repo_root)
    if not marker_path.exists():
        return None
    marker = _read_json_object(marker_path)
    if int(marker.get("schema_version") or 0) != ACTIVE_INDEX_CORRUPTION_SCHEMA_VERSION:
        return None
    unsigned = {key: value for key, value in marker.items() if key != "marker_digest"}
    if _digest(unsigned) != str(marker.get("marker_digest") or ""):
        return None
    if (
        str(marker.get("pointer_digest") or "") == str(pointer.get("pointer_digest") or "")
        and str(marker.get("artifact_digest") or "") == str(pointer.get("artifact_digest") or "")
    ):
        return "active index current immutable generation is explicitly marked corrupt"
    return None


def current_active_record_identity(repo_root: Path, entry_id: str) -> dict[str, Any] | None:
    """Return the exact current record identity used to authorize a subtractive deny."""

    pointer, artifact, _deny, issues = _load_snapshot(repo_root)
    if issues:
        raise RuntimeError("Active index authority is unavailable: " + "; ".join(issues))
    for row in artifact.get("records", []):
        if isinstance(row, Mapping) and str(row.get("entry_id") or "") == str(entry_id):
            return {
                "entry_id": str(entry_id),
                "content_digest": str(row.get("content_digest") or ""),
                "pointer_digest": str(pointer.get("pointer_digest") or ""),
                "generation": int(pointer.get("generation") or 0),
            }
    return None


def _publish_active_index_deny_locked(
    repo_root: Path,
    *,
    entry_id: str,
    expected_content_digest: str,
    expected_pointer_digest: str,
    reason: str,
    event_type: str = "",
    item_id: str = "",
) -> dict[str, Any]:
    """Atomically subtract one exact record while preserving every other current record."""

    pointer, artifact, deny, issues = _load_snapshot(repo_root)
    if issues:
        raise RuntimeError("Active index authority is unavailable: " + "; ".join(issues))
    if str(pointer.get("pointer_digest") or "") != str(expected_pointer_digest):
        raise RuntimeError("Active index current pointer changed before exact deny publication")
    identity = (str(entry_id), str(expected_content_digest))
    exact_records = {
        (str(row.get("entry_id") or ""), str(row.get("content_digest") or ""))
        for row in artifact.get("records", []) if isinstance(row, Mapping)
    }
    if identity not in exact_records:
        raise ValueError("Exact active-index record digest is not present in the current immutable generation")
    denied = [dict(row) for row in deny.get("denied_records", []) if isinstance(row, Mapping)]
    if identity not in {
        (str(row.get("entry_id") or ""), str(row.get("content_digest") or "")) for row in denied
    }:
        denied.append(
            {
                "entry_id": identity[0],
                "content_digest": identity[1],
                "denied_at": utc_now_iso(),
                "reason": str(reason),
                "event_type": str(event_type),
                "item_id": str(item_id),
            }
        )
    denied.sort(key=lambda row: (str(row.get("entry_id") or ""), str(row.get("content_digest") or "")))
    artifact_relative = str(pointer.get("artifact_path") or "")
    unsigned = {
        "schema_version": ACTIVE_INDEX_DENY_SCHEMA_VERSION,
        "index_generation": int(artifact.get("generation") or 0),
        "index_artifact_path": artifact_relative,
        "index_artifact_digest": _digest(artifact),
        "authority_generation_id": str(artifact.get("authority_generation_id") or ""),
        "denied_records": denied,
    }
    next_deny = {**unsigned, "deny_digest": _digest(unsigned)}
    deny_path = active_index_deny_dir(repo_root) / f"{_safe_digest_name(next_deny['deny_digest'])}.json"
    _write_immutable(deny_path, next_deny)
    deny_relative = _relative_managed_path(repo_root, deny_path, parent=ACTIVE_INDEX_DENY_DIR)
    next_pointer = _pointer_payload(
        artifact=artifact, artifact_path=artifact_relative, deny=next_deny, deny_path=deny_relative
    )
    # The exact record identity and pointer CAS are checked by the caller's
    # lifecycle writer lock; this atomic replacement is the final publication.
    current = _read_json_object(active_index_path(repo_root))
    if str(current.get("pointer_digest") or "") != str(expected_pointer_digest):
        raise RuntimeError("Active index current pointer changed during exact deny publication")
    _atomic_write(active_index_path(repo_root), next_pointer)
    return {
        "ok": True,
        "impact": "entry_revoke",
        "entry_id": identity[0],
        "content_digest": identity[1],
        "pointer_digest": next_pointer["pointer_digest"],
        "artifact_digest": next_pointer["artifact_digest"],
        "deny_digest": next_pointer["deny_digest"],
        "denied_record_count": len(denied),
    }


def publish_active_index_deny(
    repo_root: Path,
    *,
    entry_id: str,
    expected_content_digest: str,
    expected_pointer_digest: str,
    reason: str,
    event_type: str = "",
    item_id: str = "",
) -> dict[str, Any]:
    """Publish one exact deny under the canonical lifecycle writer lock."""

    from local_kb.lifecycle import _lifecycle_lock

    with _lifecycle_lock(repo_root):
        return _publish_active_index_deny_locked(
            repo_root,
            entry_id=entry_id,
            expected_content_digest=expected_content_digest,
            expected_pointer_digest=expected_pointer_digest,
            reason=reason,
            event_type=event_type,
            item_id=item_id,
        )


def _mark_active_index_corruption_locked(
    repo_root: Path,
    *,
    expected_pointer_digest: str,
    reason: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed only for a proven corruption of the exact current pointer."""

    pointer = _read_json_object(active_index_path(repo_root))
    if _pointer_issues(pointer):
        raise RuntimeError("Cannot bind corruption evidence to an invalid current pointer")
    if str(pointer.get("pointer_digest") or "") != str(expected_pointer_digest):
        raise RuntimeError("Active index current pointer changed before corruption marking")
    unsigned = {
        "schema_version": ACTIVE_INDEX_CORRUPTION_SCHEMA_VERSION,
        "marked_at": utc_now_iso(),
        "pointer_digest": str(pointer.get("pointer_digest") or ""),
        "artifact_digest": str(pointer.get("artifact_digest") or ""),
        "reason": str(reason),
        "evidence": _json_safe(dict(evidence or {})),
    }
    marker = {**unsigned, "marker_digest": _digest(unsigned)}
    _atomic_write(active_index_corruption_path(repo_root), marker)
    return marker


def mark_active_index_corruption(
    repo_root: Path,
    *,
    expected_pointer_digest: str,
    reason: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind corruption evidence while holding the canonical lifecycle lock."""

    from local_kb.lifecycle import _lifecycle_lock

    with _lifecycle_lock(repo_root):
        return _mark_active_index_corruption_locked(
            repo_root,
            expected_pointer_digest=expected_pointer_digest,
            reason=reason,
            evidence=evidence,
        )


def clear_active_index_corruption(
    repo_root: Path, *, expected_pointer_digest: str, publisher_id: str
) -> bool:
    if publisher_id not in ACTIVE_INDEX_PUBLISHERS:
        raise PermissionError(f"Unauthorized active-index publisher: {publisher_id or '<missing>'}")
    from local_kb.lifecycle import _lifecycle_lock

    with _lifecycle_lock(repo_root):
        marker = _read_json_object(active_index_corruption_path(repo_root))
        if not marker:
            return False
        if str(marker.get("pointer_digest") or "") != str(expected_pointer_digest):
            return False
        active_index_corruption_path(repo_root).unlink(missing_ok=True)
        return True


def apply_active_index_impact(
    repo_root: Path,
    *,
    impact: str,
    reason: str,
    entry_id: str = "",
    expected_content_digest: str = "",
    expected_pointer_digest: str = "",
    event_type: str = "",
    item_id: str = "",
    corruption_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if impact not in ACTIVE_INDEX_IMPACTS:
        raise ValueError(f"Unsupported active-index impact: {impact}")
    if impact in {"none", "additive_pending"}:
        return {"ok": True, "impact": impact, "changed": False}
    if impact in {"entry_revoke", "entry_replace"}:
        result = publish_active_index_deny(
            repo_root,
            entry_id=entry_id,
            expected_content_digest=expected_content_digest,
            expected_pointer_digest=expected_pointer_digest,
            reason=reason,
            event_type=event_type,
            item_id=item_id,
        )
        result["impact"] = impact
        result["changed"] = True
        return result
    marker = mark_active_index_corruption(
        repo_root,
        expected_pointer_digest=expected_pointer_digest,
        reason=reason,
        evidence=corruption_evidence,
    )
    return {"ok": True, "impact": impact, "changed": True, "marker_digest": marker["marker_digest"]}


def _artifact_generation_source(
    *, manifest: list[dict[str, Any]], entry_digest: str, generation_id: str,
    generation_digest: str, records: list[dict[str, Any]], excluded: Mapping[str, int]
) -> dict[str, Any]:
    return {
        "schema_version": ACTIVE_INDEX_SCHEMA_VERSION,
        "source_manifest": manifest,
        "lifecycle_entry_digest": entry_digest,
        "authority_generation_id": generation_id,
        "authority_generation_digest": generation_digest,
        # Foreground serving reads the immutable embedded records, so their
        # complete payload is part of the generation identity.
        "records": [_json_safe(dict(row)) for row in records],
        "excluded_status_counts": dict(excluded),
    }


def rebuild_active_index(
    repo_root: Path,
    *,
    reason: str = "manual",
    authority_generation: Mapping[str, Any] | None = None,
    publisher_id: str,
) -> dict[str, Any]:
    if publisher_id not in ACTIVE_INDEX_PUBLISHERS:
        raise PermissionError(f"Unauthorized active-index publisher: {publisher_id or '<missing>'}")
    started = perf_counter()
    candidate_generation = (
        validate_authority_generation_payload(authority_generation)
        if authority_generation is not None else load_authority_generation(repo_root)
    )
    generation_id = str(candidate_generation.get("generation_id") or "")
    generation_digest = str(candidate_generation.get("pointer_digest") or "")
    captured_pointer = _read_json_object(active_index_path(repo_root))
    captured_pointer_digest = str(captured_pointer.get("pointer_digest") or "")
    manifest = source_manifest(repo_root)
    lifecycle_state = load_lifecycle_state(repo_root)
    entry_digest = lifecycle_entry_digest(lifecycle_state)
    records: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    source_rows: list[tuple[dict[str, Any], Path, dict[str, Any], str]] = []
    for item in manifest:
        path = Path(repo_root) / str(item["path"])
        data = load_yaml_file(path)
        scope = str(item["scope"])
        validate_projection_path_scope(repo_root, path, data)
        if str(data.get("authority_generation_id") or "") != generation_id:
            raise ValueError(f"Card projection {data.get('id') or item['path']} does not bind candidate authority generation")
        source_rows.append((item, path, data, scope))
    validate_card_projections(repo_root, [data for _item, _path, data, _scope in source_rows])
    for item, _path, data, scope in source_rows:
        status = effective_entry_status(repo_root, data, lifecycle_state=lifecycle_state)
        if not entry_is_retrieval_eligible(repo_root, data, scope=scope, lifecycle_state=lifecycle_state):
            excluded[status or "unknown"] = excluded.get(status or "unknown", 0) + 1
            continue
        normalized = _json_safe(dict(data))
        normalized["status"] = status
        if status == "candidate":
            normalized["retrieval_eligible"] = True
        lifecycle_entry = lifecycle_state.get("entries", {}).get(str(normalized.get("id") or ""), {})
        if isinstance(lifecycle_entry, Mapping):
            receipt = lifecycle_entry.get("decision_receipt", {})
            if isinstance(receipt, Mapping) and receipt.get("new_confidence") is not None:
                normalized["confidence"] = float(receipt["new_confidence"])
        records.append(
            {
                "entry_id": str(normalized.get("id") or ""), "scope": scope, "path": str(item["path"]),
                "status": status, "source_content_digest": _digest(_json_safe(dict(data))),
                "content_digest": _digest(normalized), **active_index_binding_record(normalized), "data": normalized,
            }
        )
    records.sort(key=lambda row: (str(row["entry_id"]), str(row["path"])))
    generation_source = _artifact_generation_source(
        manifest=manifest, entry_digest=entry_digest, generation_id=generation_id,
        generation_digest=generation_digest, records=records, excluded=dict(sorted(excluded.items())),
    )
    content_digest = _digest(generation_source)
    generation_number = int(captured_pointer.get("generation") or 0) + 1
    artifact = {
        "schema_version": ACTIVE_INDEX_SCHEMA_VERSION,
        "generation": generation_number,
        "built_at": utc_now_iso(),
        "reason": str(reason),
        "source_manifest": manifest,
        "source_manifest_digest": _digest(manifest),
        "lifecycle_entry_digest": entry_digest,
        "authority_generation_id": generation_id,
        "authority_generation_digest": generation_digest,
        "lifecycle_event_digest_at_build": str(lifecycle_state.get("event_digest") or ""),
        "indexed_record_count": len(records),
        "excluded_status_counts": dict(sorted(excluded.items())),
        "records": records,
        "content_digest": content_digest,
        "build_duration_ms": round((perf_counter() - started) * 1000, 3),
        "receipt_id": f"active-index:{content_digest.removeprefix('sha256:')[:24]}",
    }
    issues = _artifact_issues(artifact)
    if issues:
        raise ValueError("Active index pre-publication validation failed: " + "; ".join(issues))
    artifact_name = f"{generation_number:020d}-{_safe_digest_name(content_digest)}.json"
    artifact_path = active_index_generation_dir(repo_root) / artifact_name
    _write_immutable(artifact_path, artifact)
    artifact_relative = _relative_managed_path(repo_root, artifact_path, parent=ACTIVE_INDEX_GENERATION_DIR)
    deny = _empty_deny_payload(artifact, artifact_relative)
    deny_path = active_index_deny_dir(repo_root) / f"{_safe_digest_name(deny['deny_digest'])}.json"
    _write_immutable(deny_path, deny)
    deny_relative = _relative_managed_path(repo_root, deny_path, parent=ACTIVE_INDEX_DENY_DIR)
    pointer = _pointer_payload(
        artifact=artifact, artifact_path=artifact_relative, deny=deny, deny_path=deny_relative
    )
    from local_kb.lifecycle import _lifecycle_lock

    with _lifecycle_lock(repo_root):
        current = _read_json_object(active_index_path(repo_root))
        if str(current.get("pointer_digest") or "") != captured_pointer_digest:
            raise RuntimeError("Active-index current pointer changed during rebuild")
        _atomic_write(active_index_path(repo_root), pointer)
        active_index_authority_path(repo_root).unlink(missing_ok=True)
        active_index_invalidation_path(repo_root).unlink(missing_ok=True)
        # A marker bound to the prior pointer is no longer current. Removing it
        # is cleanup, not a fallback or authority transition.
        active_index_corruption_path(repo_root).unlink(missing_ok=True)
    current_generation = None
    try:
        current_generation = load_authority_generation(repo_root)
    except ExactBindingError:
        current_generation = None
    fast_validation: dict[str, Any] = {"ok": True, "deferred": True, "duration_ms": None}
    if current_generation and str(current_generation.get("pointer_digest") or "") == generation_digest:
        fast_validation = validate_active_index_fast(repo_root)
        if not fast_validation.get("ok"):
            raise ValueError("Active index fast validation failed: " + "; ".join(fast_validation.get("issues", [])))
    return {
        "ok": True,
        "receipt_id": artifact["receipt_id"],
        "path": str(active_index_path(repo_root)),
        "pointer_path": str(active_index_path(repo_root)),
        "pointer_digest": pointer["pointer_digest"],
        "artifact_path": str(artifact_path),
        "artifact_digest": pointer["artifact_digest"],
        "deny_path": str(deny_path),
        "deny_digest": pointer["deny_digest"],
        "generation": generation_number,
        "content_digest": content_digest,
        "indexed_record_count": len(records),
        "excluded_status_counts": artifact["excluded_status_counts"],
        "build_duration_ms": artifact["build_duration_ms"],
        "fast_validation_duration_ms": fast_validation.get("duration_ms"),
        "publisher_id": publisher_id,
    }


def _validate_active_index_fast_snapshot(repo_root: Path) -> dict[str, Any]:
    started = perf_counter()
    initial_pointer = _read_json_object(active_index_path(repo_root))
    pointer, artifact, deny, issues = _load_snapshot(repo_root)
    # The active-index pointer is the sole serving-generation authority.  A
    # staged canonical LogicGuard generation may be published before this
    # pointer switches; comparing another mutable current pointer here would
    # create a fail-closed gap and defeat atomic last-pointer activation.
    corruption = _current_corruption_issue(repo_root, pointer)
    if corruption:
        issues.append(corruption)
    final_pointer = _read_json_object(active_index_path(repo_root))
    if str(final_pointer.get("pointer_digest") or "") != str(initial_pointer.get("pointer_digest") or ""):
        issues.append("active index current pointer changed during the query snapshot")
    denied_count = len(deny.get("denied_records", [])) if isinstance(deny.get("denied_records"), list) else 0
    record_count = len(artifact.get("records", [])) if isinstance(artifact.get("records"), list) else 0
    return {
        "ok": not issues,
        "mode": "immutable-pointer",
        "generation": int(pointer.get("generation") or 0),
        "content_digest": str(pointer.get("content_digest") or ""),
        "pointer_digest": str(pointer.get("pointer_digest") or ""),
        "artifact_digest": str(pointer.get("artifact_digest") or ""),
        "deny_digest": str(pointer.get("deny_digest") or ""),
        "indexed_record_count": record_count,
        "denied_record_count": denied_count,
        "effective_record_count": max(0, record_count - denied_count),
        "issues": issues,
        "duration_ms": round((perf_counter() - started) * 1000, 3),
    }


def validate_active_index_fast(repo_root: Path) -> dict[str, Any]:
    return {"path": str(active_index_path(repo_root)), **_validate_active_index_fast_snapshot(repo_root)}


def load_active_index(repo_root: Path) -> dict[str, Any]:
    pointer, artifact, deny, _issues = _load_snapshot(repo_root)
    validation = _validate_active_index_fast_snapshot(repo_root)
    payload = dict(artifact)
    payload.update(
        {
            "current_pointer": pointer,
            "pointer_digest": str(pointer.get("pointer_digest") or ""),
            "artifact_path": str(pointer.get("artifact_path") or ""),
            "artifact_digest": str(pointer.get("artifact_digest") or ""),
            "deny_path": str(pointer.get("deny_path") or ""),
            "deny_digest": str(pointer.get("deny_digest") or ""),
            "denied_records": list(deny.get("denied_records", [])) if isinstance(deny.get("denied_records"), list) else [],
            "stale": not bool(validation.get("ok")),
            "validation_mode": "immutable-pointer",
            "validation_issues": list(validation.get("issues", [])),
            "validation_duration_ms": validation.get("duration_ms"),
        }
    )
    return payload


def _validate_indexed_sources_full(repo_root: Path, artifact: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    projection_rows: list[dict[str, Any]] = []
    root = Path(repo_root).resolve()
    for record in artifact.get("records", []):
        if not isinstance(record, Mapping):
            continue
        entry_id = str(record.get("entry_id") or "")
        scope = str(record.get("scope") or "")
        if scope not in INDEX_SCOPES:
            issues.append(f"indexed source has unsupported scope for {entry_id}")
            continue
        try:
            path = (root / str(record.get("path") or "")).resolve(strict=True)
            path.relative_to((root / "kb" / scope).resolve(strict=False))
            data = load_yaml_file(path)
        except (OSError, ValueError, TypeError):
            issues.append(f"indexed source is missing or unreadable for {entry_id}")
            continue
        if _digest(_json_safe(dict(data))) != str(record.get("source_content_digest") or ""):
            issues.append(f"indexed source content changed for {entry_id}")
        try:
            validate_projection_path_scope(repo_root, path, data)
        except (ProjectionValidationError, ExactBindingError, ValueError) as exc:
            issues.append(f"indexed source has invalid LogicGuard authority for {entry_id}: {exc}")
            continue
        projection_rows.append(data)
    if projection_rows:
        try:
            validate_card_projections(repo_root, projection_rows)
        except (ProjectionValidationError, ExactBindingError, ValueError) as exc:
            issues.append(f"indexed sources have invalid LogicGuard authority: {exc}")
    return issues


def validate_active_index(repo_root: Path) -> dict[str, Any]:
    started = perf_counter()
    pointer, artifact, deny, issues = _load_snapshot(repo_root)
    try:
        generation = load_authority_generation(repo_root)
    except ExactBindingError as exc:
        generation = {}
        issues.append(str(exc))
    if generation:
        if str(generation.get("generation_id") or "") != str(artifact.get("authority_generation_id") or ""):
            issues.append("active index does not bind the current LogicGuard authority generation")
        if str(generation.get("pointer_digest") or "") != str(artifact.get("authority_generation_digest") or ""):
            issues.append("active index authority-generation digest is stale")
    manifest = source_manifest(repo_root)
    if str(artifact.get("source_manifest_digest") or "") != _digest(manifest):
        issues.append("active index source manifest is stale")
    lifecycle_state = load_lifecycle_state(repo_root)
    if str(artifact.get("lifecycle_entry_digest") or "") != lifecycle_entry_digest(lifecycle_state):
        issues.append("active index entry-authority generation is stale")
    issues.extend(_validate_indexed_sources_full(repo_root, artifact))
    corruption = _current_corruption_issue(repo_root, pointer)
    if corruption:
        issues.append(corruption)
    records = artifact.get("records", []) if isinstance(artifact.get("records"), list) else []
    denied = deny.get("denied_records", []) if isinstance(deny.get("denied_records"), list) else []
    return {
        "ok": not issues,
        "mode": "full",
        "path": str(active_index_path(repo_root)),
        "generation": int(pointer.get("generation") or 0),
        "content_digest": str(pointer.get("content_digest") or ""),
        "pointer_digest": str(pointer.get("pointer_digest") or ""),
        "artifact_digest": str(pointer.get("artifact_digest") or ""),
        "deny_digest": str(pointer.get("deny_digest") or ""),
        "indexed_record_count": len(records),
        "denied_record_count": len(denied),
        "issues": issues,
        "duration_ms": round((perf_counter() - started) * 1000, 3),
    }


def load_active_entries(repo_root: Path) -> tuple[list[Entry], dict[str, Any]]:
    payload = load_active_index(repo_root)
    if payload.get("stale"):
        raise RuntimeError(
            "Active index is unavailable or stale: "
            + "; ".join(str(item) for item in payload.get("validation_issues", []))
        )
    denied = {
        (str(row.get("entry_id") or ""), str(row.get("content_digest") or ""))
        for row in payload.get("denied_records", []) if isinstance(row, Mapping)
    }
    entries: list[Entry] = []
    for record in payload.get("records", []):
        if not isinstance(record, Mapping):
            continue
        identity = (str(record.get("entry_id") or ""), str(record.get("content_digest") or ""))
        if identity in denied:
            continue
        path = Path(repo_root) / str(record.get("path") or "")
        scope = str(record.get("scope") or "")
        entries.append(
            Entry(
                path=path,
                data=dict(record.get("data") or {}),
                source=build_local_entry_source(Path(repo_root), scope, path),
            )
        )
    payload["effective_record_count"] = len(entries)
    return entries, payload
