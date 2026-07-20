from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any, Iterable, Mapping
from uuid import uuid4

from local_kb.common import utc_now_iso
from local_kb.lifecycle import (
    entry_is_retrieval_eligible,
    effective_entry_status,
    load_lifecycle_state,
)
from local_kb.models import Entry
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
from local_kb.store import build_local_entry_source, load_yaml_file


ACTIVE_INDEX_SCHEMA_VERSION = 3
ACTIVE_INDEX_AUTHORITY_SCHEMA_VERSION = 2
ACTIVE_INDEX_PATH = Path("kb") / "indexes" / "active.json"
ACTIVE_INDEX_AUTHORITY_PATH = Path("kb") / "indexes" / "active-authority.json"
ACTIVE_INDEX_INVALIDATION_PATH = Path("kb") / "indexes" / "active-invalidated.json"
INDEX_SCOPES = ("public", "private", "candidates")
TERMINAL_STATUSES = {"merged", "rejected", "superseded", "parked", "retired", "deprecated", "history_only"}
ACTIVE_INDEX_PUBLISHERS = frozenset(AUTHORITY_GENERATION_WRITERS)
_INDEXED_SOURCE_VALIDATION_CACHE_LIMIT = 32
_INDEXED_SOURCE_VALIDATION_CACHE: dict[tuple[Any, ...], tuple[str, ...]] = {}
_INDEXED_SOURCE_VALIDATION_CACHE_LOCK = RLock()


def active_index_path(repo_root: Path) -> Path:
    return Path(repo_root) / ACTIVE_INDEX_PATH


def active_index_authority_path(repo_root: Path) -> Path:
    return Path(repo_root) / ACTIVE_INDEX_AUTHORITY_PATH


def active_index_invalidation_path(repo_root: Path) -> Path:
    return Path(repo_root) / ACTIVE_INDEX_INVALIDATION_PATH


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
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=_json_default))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def lifecycle_entry_digest(lifecycle_state: Mapping[str, Any]) -> str:
    """Digest only lifecycle state that can change retrieval eligibility.

    Observation admission/disposition events are intentionally excluded. They
    must not make every foreground query replay the complete lifecycle merely
    because another AI recorded a new experience.
    """

    entries = lifecycle_state.get("entries", {})
    if not isinstance(entries, Mapping):
        return _digest({})
    retrieval_projection: dict[str, dict[str, Any]] = {}
    for entry_id, raw_state in sorted(entries.items(), key=lambda item: str(item[0])):
        if not isinstance(raw_state, Mapping):
            continue
        projected = {
            "status": str(raw_state.get("status") or ""),
        }
        if "retrieval_eligible" in raw_state:
            projected["retrieval_eligible"] = bool(raw_state.get("retrieval_eligible"))
        if "suspended" in raw_state:
            projected["suspended"] = bool(raw_state.get("suspended"))
        retrieval_projection[str(entry_id)] = projected
    return _digest(retrieval_projection)


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            dict(payload),
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=_json_default,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _invalidation_token(repo_root: Path) -> str | None:
    path = active_index_invalidation_path(repo_root)
    if not path.exists():
        return None
    payload = _read_json_object(path)
    token = str(payload.get("token") or "").strip()
    return token or "invalid-invalidation-marker"


def _clear_active_index_validation_cache() -> None:
    with _INDEXED_SOURCE_VALIDATION_CACHE_LOCK:
        _INDEXED_SOURCE_VALIDATION_CACHE.clear()


def _indexed_source_content_signature(
    repo_root: Path,
    payload: Mapping[str, Any],
) -> tuple[tuple[str, str, str, str], ...]:
    """Hash only indexed source bytes to bind a process-local validation reuse.

    The expensive LogicGuard projection check may be reused only while every
    returnable source, the active index, the invalidation marker, and the sole
    authority pointer remain identical. Raw source hashing is intentionally
    repeated before and after the query snapshot so a source write cannot hide
    behind filesystem timestamp granularity.
    """

    root = Path(repo_root).resolve()
    rows: list[tuple[str, str, str, str]] = []
    records = payload.get("records", []) if isinstance(payload.get("records"), list) else []
    for record in records:
        if not isinstance(record, Mapping):
            rows.append(("", "", "", "invalid-record"))
            continue
        entry_id = str(record.get("entry_id") or "")
        scope = str(record.get("scope") or "")
        relative = str(record.get("path") or "")
        if scope not in INDEX_SCOPES:
            rows.append((entry_id, scope, relative, "unsupported-scope"))
            continue
        try:
            path = (root / relative).resolve(strict=True)
            path.relative_to((root / "kb" / scope).resolve(strict=False))
            content_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError):
            content_digest = "missing-or-outside-scope"
        rows.append((entry_id, scope, relative, content_digest))
    return tuple(sorted(rows))


def _validate_indexed_sources_cached(
    repo_root: Path,
    payload: Mapping[str, Any],
    *,
    invalidation_token: str | None,
    authority: Mapping[str, Any],
    authority_generation: Mapping[str, Any],
    source_signature: tuple[tuple[str, str, str, str], ...],
) -> list[str]:
    key: tuple[Any, ...] = (
        str(Path(repo_root).resolve()),
        int(payload.get("generation") or 0),
        str(payload.get("content_digest") or ""),
        str(invalidation_token or ""),
        str(authority.get("authority_digest") or ""),
        str(authority_generation.get("pointer_digest") or ""),
        source_signature,
    )
    with _INDEXED_SOURCE_VALIDATION_CACHE_LOCK:
        cached = _INDEXED_SOURCE_VALIDATION_CACHE.get(key)
    if cached is not None:
        return list(cached)

    issues = _validate_indexed_sources_fast(repo_root, payload)
    if issues:
        return issues
    with _INDEXED_SOURCE_VALIDATION_CACHE_LOCK:
        if len(_INDEXED_SOURCE_VALIDATION_CACHE) >= _INDEXED_SOURCE_VALIDATION_CACHE_LIMIT:
            _INDEXED_SOURCE_VALIDATION_CACHE.clear()
        _INDEXED_SOURCE_VALIDATION_CACHE[key] = ()
    return issues


def invalidate_active_index(
    repo_root: Path,
    *,
    reason: str,
    event_type: str = "",
    item_id: str = "",
) -> dict[str, Any]:
    """Durably block indexed reads before an entry-authority mutation.

    Lifecycle writers call this while holding their writer lock and before the
    event-log mutation. A crash therefore leaves a visible fail-closed marker;
    only a fully validated rebuild may remove it.
    """

    payload = {
        "schema_version": 1,
        "token": uuid4().hex,
        "invalidated_at": utc_now_iso(),
        "reason": str(reason),
        "event_type": str(event_type),
        "item_id": str(item_id),
    }
    payload["marker_digest"] = _digest(payload)
    _atomic_write(active_index_invalidation_path(repo_root), payload)
    _clear_active_index_validation_cache()
    return payload


def _authority_payload(index: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": ACTIVE_INDEX_AUTHORITY_SCHEMA_VERSION,
        "activated_at": utc_now_iso(),
        "generation": int(index.get("generation") or 0),
        "index_content_digest": str(index.get("content_digest") or ""),
        "source_manifest_digest": str(index.get("source_manifest_digest") or ""),
        "lifecycle_entry_digest": str(index.get("lifecycle_entry_digest") or ""),
        "indexed_record_count": int(index.get("indexed_record_count") or 0),
        "authority_generation_id": str(index.get("authority_generation_id") or ""),
        "authority_generation_digest": str(index.get("authority_generation_digest") or ""),
    }
    payload["authority_digest"] = _digest(payload)
    return payload


def _authority_issues(
    authority: Mapping[str, Any],
    index: Mapping[str, Any],
) -> list[str]:
    issues: list[str] = []
    if int(authority.get("schema_version") or 0) != ACTIVE_INDEX_AUTHORITY_SCHEMA_VERSION:
        issues.append("active index authority stamp is missing or unsupported")
        return issues
    unsigned = {key: value for key, value in authority.items() if key != "authority_digest"}
    if _digest(unsigned) != str(authority.get("authority_digest") or ""):
        issues.append("active index authority stamp digest mismatch")
    bindings = {
        "generation": int(index.get("generation") or 0),
        "index_content_digest": str(index.get("content_digest") or ""),
        "source_manifest_digest": str(index.get("source_manifest_digest") or ""),
        "lifecycle_entry_digest": str(index.get("lifecycle_entry_digest") or ""),
        "indexed_record_count": int(index.get("indexed_record_count") or 0),
        "authority_generation_id": str(index.get("authority_generation_id") or ""),
        "authority_generation_digest": str(index.get("authority_generation_digest") or ""),
    }
    for key, expected in bindings.items():
        actual = int(authority.get(key) or 0) if isinstance(expected, int) else str(authority.get(key) or "")
        if actual != expected:
            issues.append(f"active index authority stamp does not bind {key}")
    return issues


def _validate_payload(
    payload: Mapping[str, Any],
    *,
    manifest: list[dict[str, Any]],
    entry_digest: str,
    authority_generation: Mapping[str, Any],
) -> list[str]:
    issues: list[str] = []
    if int(payload.get("schema_version") or 0) != ACTIVE_INDEX_SCHEMA_VERSION:
        issues.append("active index schema version is unsupported")
    if str(payload.get("source_manifest_digest") or "") != _digest(manifest):
        issues.append("active index source manifest is stale")
    if str(payload.get("lifecycle_entry_digest") or "") != entry_digest:
        issues.append("active index entry-authority generation is stale")
    generation_id = str(authority_generation.get("generation_id") or "")
    generation_digest = str(authority_generation.get("pointer_digest") or "")
    if str(payload.get("authority_generation_id") or "") != generation_id:
        issues.append("active index does not bind the current LogicGuard authority generation")
    if str(payload.get("authority_generation_digest") or "") != generation_digest:
        issues.append("active index authority-generation digest is stale")
    records = payload.get("records", []) if isinstance(payload.get("records"), list) else []
    identities: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            issues.append("active index contains a non-object record")
            continue
        entry_id = str(record.get("entry_id") or "")
        if not entry_id:
            issues.append("active index contains a record without entry_id")
        if entry_id in identities:
            issues.append(f"active index contains duplicate entry_id {entry_id}")
        identities.add(entry_id)
        status = str(record.get("status") or "").lower()
        if status in TERMINAL_STATUSES or status not in {"trusted", "candidate"}:
            issues.append(f"ineligible status {status} indexed for {entry_id}")
        data = record.get("data", {}) if isinstance(record.get("data"), dict) else {}
        if _digest(data) != str(record.get("content_digest") or ""):
            issues.append(f"content digest mismatch for {entry_id}")
        if str(record.get("authority_generation_id") or "") != generation_id:
            issues.append(f"authority generation mismatch for {entry_id}")
        if str(record.get("projection_digest") or "") != str(data.get("projection_digest") or ""):
            issues.append(f"projection digest binding mismatch for {entry_id}")
        for field in (
            "authority_scope",
            "logicguard_model_id",
            "logicguard_node_id",
            "logicguard_block_id",
            "logicguard_revision_id",
            "logicguard_mesh_id",
            "logicguard_mesh_revision_id",
            "projection_digest",
        ):
            if not str(record.get(field) or ""):
                issues.append(f"exact LogicGuard binding field {field} is missing for {entry_id}")
    if len(records) != int(payload.get("indexed_record_count") or 0):
        issues.append("indexed_record_count does not match records")
    generation_source = {
        "schema_version": ACTIVE_INDEX_SCHEMA_VERSION,
        "source_manifest": payload.get("source_manifest", []),
        "lifecycle_entry_digest": payload.get("lifecycle_entry_digest", ""),
        "authority_generation_id": payload.get("authority_generation_id", ""),
        "authority_generation_digest": payload.get("authority_generation_digest", ""),
        "records": [
            {key: value for key, value in record.items() if key != "data"}
            for record in records
            if isinstance(record, dict)
        ],
        "excluded_status_counts": payload.get("excluded_status_counts", {}),
    }
    if _digest(generation_source) != str(payload.get("content_digest") or ""):
        issues.append("active index content digest is not reproducible")
    return issues


def _source_paths(repo_root: Path, scopes: Iterable[str] = INDEX_SCOPES) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    for scope in scopes:
        root = Path(repo_root) / "kb" / scope
        if not root.exists():
            continue
        paths.extend((scope, path) for path in sorted(root.rglob("*.yaml")))
    return paths


def source_manifest(repo_root: Path) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for scope, path in _source_paths(repo_root):
        stat = path.stat()
        manifest.append(
            {
                "scope": scope,
                "path": str(path.relative_to(repo_root)).replace("\\", "/"),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    return manifest


def source_manifest_digest(repo_root: Path) -> str:
    return _digest(source_manifest(repo_root))


def _validate_indexed_sources_fast(
    repo_root: Path,
    payload: Mapping[str, Any],
) -> list[str]:
    """Recheck only records that could actually be returned.

    A newly added or newly eligible source may be conservatively absent until
    Sleep rebuilds the index, but an indexed source may never change or leave
    the declared scope unnoticed.
    """

    root = Path(repo_root).resolve()
    issues: list[str] = []
    projection_rows: list[tuple[str, dict[str, Any]]] = []
    records = payload.get("records", []) if isinstance(payload.get("records"), list) else []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        entry_id = str(record.get("entry_id") or "")
        scope = str(record.get("scope") or "")
        relative = str(record.get("path") or "")
        if scope not in INDEX_SCOPES:
            issues.append(f"indexed source has unsupported scope for {entry_id}")
            continue
        try:
            path = (root / relative).resolve(strict=True)
            scope_root = (root / "kb" / scope).resolve(strict=False)
            path.relative_to(scope_root)
        except (OSError, ValueError):
            issues.append(f"indexed source is missing or outside its scope for {entry_id}")
            continue
        try:
            source_data = load_yaml_file(path)
        except (OSError, ValueError, TypeError) as exc:
            issues.append(f"indexed source cannot be read for {entry_id}: {type(exc).__name__}")
            continue
        if _digest(_json_safe(dict(source_data))) != str(record.get("source_content_digest") or ""):
            issues.append(f"indexed source content changed for {entry_id}")
        if str(source_data.get("id") or "") != entry_id:
            issues.append(f"indexed source identity changed for {entry_id}")
        try:
            validate_projection_path_scope(repo_root, path, source_data)
        except (ProjectionValidationError, ExactBindingError, ValueError) as exc:
            issues.append(f"indexed source has invalid LogicGuard authority for {entry_id}: {exc}")
            continue
        projection_rows.append((entry_id, source_data))
    if projection_rows:
        try:
            validate_card_projections(
                repo_root,
                [source_data for _entry_id, source_data in projection_rows],
            )
        except (ProjectionValidationError, ExactBindingError, ValueError) as exc:
            issues.append(f"indexed sources have invalid LogicGuard authority: {exc}")
    return issues


def _validate_active_index_fast_payload(
    repo_root: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    started = perf_counter()
    initial_marker = _invalidation_token(repo_root)
    initial_authority = _read_json_object(active_index_authority_path(repo_root))
    initial_source_signature = _indexed_source_content_signature(repo_root, payload)
    issues: list[str] = []
    try:
        authority_generation = load_authority_generation(repo_root)
    except ExactBindingError as exc:
        authority_generation = {}
        issues.append(str(exc))
    if not payload:
        issues.append("active index is missing")
    if initial_marker is not None:
        issues.append("active index is durably invalidated pending rebuild")
    if payload:
        embedded_manifest = payload.get("source_manifest", [])
        manifest = embedded_manifest if isinstance(embedded_manifest, list) else []
        issues.extend(
            _validate_payload(
                payload,
                manifest=manifest,
                entry_digest=str(payload.get("lifecycle_entry_digest") or ""),
                authority_generation=authority_generation,
            )
        )
        issues.extend(_authority_issues(initial_authority, payload))
        issues.extend(
            _validate_indexed_sources_cached(
                repo_root,
                payload,
                invalidation_token=initial_marker,
                authority=initial_authority,
                authority_generation=authority_generation,
                source_signature=initial_source_signature,
            )
        )
    final_marker = _invalidation_token(repo_root)
    final_authority = _read_json_object(active_index_authority_path(repo_root))
    final_source_signature = _indexed_source_content_signature(repo_root, payload)
    if final_marker != initial_marker:
        issues.append("active index invalidation changed during the query snapshot")
    if str(final_authority.get("authority_digest") or "") != str(
        initial_authority.get("authority_digest") or ""
    ):
        issues.append("active index authority changed during the query snapshot")
    if final_source_signature != initial_source_signature:
        issues.append("indexed source content changed during the query snapshot")
    return {
        "ok": not issues,
        "mode": "fast-authority",
        "generation": int(payload.get("generation") or 0),
        "content_digest": str(payload.get("content_digest") or ""),
        "indexed_record_count": len(payload.get("records", [])) if isinstance(payload.get("records"), list) else 0,
        "issues": issues,
        "duration_ms": round((perf_counter() - started) * 1000, 3),
    }


def validate_active_index_fast(repo_root: Path) -> dict[str, Any]:
    payload = _read_json_object(active_index_path(repo_root))
    return {
        "path": str(active_index_path(repo_root)),
        **_validate_active_index_fast_payload(repo_root, payload),
    }


def _activate_built_index(
    repo_root: Path,
    *,
    payload: Mapping[str, Any],
    captured_invalidation_token: str | None,
    publisher_id: str,
) -> dict[str, Any]:
    # The same lock serializes entry transitions. This closes the final
    # check/publish/delete race without holding it during the expensive scan.
    from local_kb.lifecycle import _lifecycle_lock

    if publisher_id not in ACTIVE_INDEX_PUBLISHERS:
        raise PermissionError(
            f"Unauthorized active-index publisher: {publisher_id or '<missing>'}"
        )
    with _lifecycle_lock(repo_root):
        current_token = _invalidation_token(repo_root)
        if current_token != captured_invalidation_token:
            raise RuntimeError("Active-index authority changed during rebuild")
        current_index = _read_json_object(active_index_path(repo_root))
        if (
            int(current_index.get("generation") or 0) != int(payload.get("generation") or 0)
            or str(current_index.get("content_digest") or "")
            != str(payload.get("content_digest") or "")
        ):
            raise RuntimeError("Another active-index publication superseded this rebuild")
        authority = _authority_payload(payload)
        _atomic_write(active_index_authority_path(repo_root), authority)
        active_index_invalidation_path(repo_root).unlink(missing_ok=True)
        _clear_active_index_validation_cache()
        return authority


def rebuild_active_index(
    repo_root: Path,
    *,
    reason: str = "manual",
    authority_generation: Mapping[str, Any] | None = None,
    publisher_id: str,
) -> dict[str, Any]:
    if publisher_id not in ACTIVE_INDEX_PUBLISHERS:
        raise PermissionError(
            f"Unauthorized active-index publisher: {publisher_id or '<missing>'}"
        )
    started = perf_counter()
    candidate_generation = (
        validate_authority_generation_payload(authority_generation)
        if authority_generation is not None
        else load_authority_generation(repo_root)
    )
    authority_generation_id = str(candidate_generation.get("generation_id") or "")
    authority_generation_digest = str(candidate_generation.get("pointer_digest") or "")
    captured_invalidation_token = _invalidation_token(repo_root)
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
        if str(data.get("authority_generation_id") or "") != authority_generation_id:
            raise ValueError(
                f"Card projection {data.get('id') or item['path']} does not bind candidate authority generation"
            )
        source_rows.append((item, path, data, scope))
    validate_card_projections(
        repo_root,
        [data for _item, _path, data, _scope in source_rows],
    )
    for item, path, data, scope in source_rows:
        status = effective_entry_status(repo_root, data, lifecycle_state=lifecycle_state)
        if not entry_is_retrieval_eligible(
            repo_root,
            data,
            scope=scope,
            lifecycle_state=lifecycle_state,
        ):
            excluded[status or "unknown"] = excluded.get(status or "unknown", 0) + 1
            continue
        normalized = _json_safe(dict(data))
        normalized["status"] = status
        if status == "candidate":
            normalized["retrieval_eligible"] = True
        lifecycle_entry = lifecycle_state.get("entries", {}).get(str(normalized.get("id") or ""), {})
        if isinstance(lifecycle_entry, Mapping):
            decision_receipt = lifecycle_entry.get("decision_receipt", {})
            if isinstance(decision_receipt, Mapping) and decision_receipt.get("new_confidence") is not None:
                normalized["confidence"] = float(decision_receipt["new_confidence"])
        records.append(
            {
                "entry_id": str(normalized.get("id") or ""),
                "scope": scope,
                "path": str(item["path"]),
                "status": status,
                "source_content_digest": _digest(_json_safe(dict(data))),
                "content_digest": _digest(normalized),
                **active_index_binding_record(normalized),
                "data": normalized,
            }
        )
    records.sort(key=lambda row: (str(row["entry_id"]), str(row["path"])))
    generation_source = {
        "schema_version": ACTIVE_INDEX_SCHEMA_VERSION,
        "source_manifest": manifest,
        "lifecycle_entry_digest": entry_digest,
        "authority_generation_id": authority_generation_id,
        "authority_generation_digest": authority_generation_digest,
        "records": [
            {key: value for key, value in record.items() if key != "data"}
            for record in records
        ],
        "excluded_status_counts": excluded,
    }
    content_digest = _digest(generation_source)
    previous_generation = 0
    path = active_index_path(repo_root)
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(previous, dict):
                previous_generation = int(previous.get("generation") or 0)
        except (OSError, json.JSONDecodeError):
            previous_generation = 0
    receipt_id = f"active-index:{content_digest[:24]}"
    payload = {
        "schema_version": ACTIVE_INDEX_SCHEMA_VERSION,
        "generation": previous_generation + 1,
        "built_at": utc_now_iso(),
        "reason": reason,
        "source_manifest": manifest,
        "source_manifest_digest": _digest(manifest),
        "lifecycle_entry_digest": entry_digest,
        "authority_generation_id": authority_generation_id,
        "authority_generation_digest": authority_generation_digest,
        "lifecycle_event_digest_at_build": str(lifecycle_state.get("event_digest") or ""),
        "indexed_record_count": len(records),
        "excluded_status_counts": dict(sorted(excluded.items())),
        "records": records,
        "content_digest": content_digest,
        "build_duration_ms": round((perf_counter() - started) * 1000, 3),
        "validation": {"ok": True, "issues": []},
        "receipt_id": receipt_id,
    }
    prepublication_issues = _validate_payload(
        payload,
        manifest=manifest,
        entry_digest=entry_digest,
        authority_generation=candidate_generation,
    )
    if prepublication_issues:
        raise ValueError(
            "Active index pre-publication validation failed: "
            + "; ".join(prepublication_issues)
        )
    _atomic_write(path, payload)
    validation = _validate_active_index_full_payload(
        repo_root,
        payload,
        require_authority=False,
        authority_generation=candidate_generation,
    )
    if not validation.get("ok"):
        raise ValueError("Active index validation failed: " + "; ".join(validation.get("issues", [])))
    authority = _activate_built_index(
        repo_root,
        payload=payload,
        captured_invalidation_token=captured_invalidation_token,
        publisher_id=publisher_id,
    )
    current_generation = None
    try:
        current_generation = load_authority_generation(repo_root)
    except ExactBindingError:
        current_generation = None
    fast_validation: dict[str, Any] = {"ok": True, "duration_ms": None, "deferred": True}
    if current_generation and current_generation.get("pointer_digest") == candidate_generation.get("pointer_digest"):
        fast_validation = validate_active_index_fast(repo_root)
        if not fast_validation.get("ok"):
            raise ValueError(
                "Active index fast-authority validation failed: "
                + "; ".join(fast_validation.get("issues", []))
            )
    return {
        "ok": True,
        "receipt_id": receipt_id,
        "path": str(path),
        "generation": payload["generation"],
        "content_digest": content_digest,
        "indexed_record_count": len(records),
        "excluded_status_counts": payload["excluded_status_counts"],
        "build_duration_ms": payload["build_duration_ms"],
        "authority_digest": str(authority.get("authority_digest") or ""),
        "fast_validation_duration_ms": fast_validation.get("duration_ms"),
        "publisher_id": publisher_id,
    }


def load_active_index(repo_root: Path) -> dict[str, Any]:
    path = active_index_path(repo_root)
    payload = _read_json_object(path)
    validation = _validate_active_index_fast_payload(repo_root, payload)
    stale = not bool(validation.get("ok"))
    payload["stale"] = stale
    payload["validation_mode"] = "fast-authority"
    payload["validation_issues"] = list(validation.get("issues", []))
    payload["validation_duration_ms"] = validation.get("duration_ms")
    return payload


def _validate_active_index_full_payload(
    repo_root: Path,
    payload: Mapping[str, Any],
    *,
    require_authority: bool,
    authority_generation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    started = perf_counter()
    issues: list[str] = []
    if not payload:
        issues.append("active index is missing")
        return {
            "ok": False,
            "mode": "full",
            "issues": issues,
            "duration_ms": round((perf_counter() - started) * 1000, 3),
        }
    manifest = source_manifest(repo_root)
    lifecycle_state = load_lifecycle_state(repo_root)
    entry_digest = lifecycle_entry_digest(lifecycle_state)
    try:
        generation = (
            validate_authority_generation_payload(authority_generation)
            if authority_generation is not None
            else load_authority_generation(repo_root)
        )
    except ExactBindingError as exc:
        generation = {}
        issues.append(str(exc))
    issues.extend(
        _validate_payload(
            payload,
            manifest=manifest,
            entry_digest=entry_digest,
            authority_generation=generation,
        )
    )
    issues.extend(_validate_indexed_sources_fast(repo_root, payload))
    if require_authority:
        issues.extend(
            _authority_issues(
                _read_json_object(active_index_authority_path(repo_root)),
                payload,
            )
        )
        if _invalidation_token(repo_root) is not None:
            issues.append("active index is durably invalidated pending rebuild")
    records = payload.get("records", []) if isinstance(payload.get("records"), list) else []
    return {
        "ok": not issues,
        "mode": "full",
        "path": str(active_index_path(repo_root)),
        "generation": int(payload.get("generation") or 0),
        "content_digest": str(payload.get("content_digest") or ""),
        "indexed_record_count": len(records),
        "issues": issues,
        "duration_ms": round((perf_counter() - started) * 1000, 3),
    }


def validate_active_index(repo_root: Path) -> dict[str, Any]:
    payload = _read_json_object(active_index_path(repo_root))
    return _validate_active_index_full_payload(
        repo_root,
        payload,
        require_authority=True,
    )


def load_active_entries(repo_root: Path) -> tuple[list[Entry], dict[str, Any]]:
    payload = load_active_index(repo_root)
    if payload.get("stale"):
        raise RuntimeError(
            "Active index is unavailable or stale: "
            + "; ".join(str(item) for item in payload.get("validation_issues", []))
        )
    entries: list[Entry] = []
    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue
        path = Path(repo_root) / str(record.get("path") or "")
        scope = str(record.get("scope") or "")
        data = dict(record.get("data") or {})
        entries.append(
            Entry(
                path=path,
                data=data,
                source=build_local_entry_source(Path(repo_root), scope, path),
            )
        )
    return entries, payload
