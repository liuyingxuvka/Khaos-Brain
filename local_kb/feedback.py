from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any

from local_kb.common import csv_to_list, parse_route_segments
from local_kb.history import build_history_event, record_history_event
from local_kb.lifecycle import LIFECYCLE_WRITER_LOCK_TIMEOUT_SECONDS


POSTFLIGHT_RECEIPT_SCHEMA = "khaos-brain.postflight-observation-receipt.v1"
POSTFLIGHT_RECEIPT_ROOT = Path("kb") / "history" / "postflight-receipts"
POSTFLIGHT_COMPLETION_HEADROOM_MS = 30_000.0
POSTFLIGHT_TERMINAL_BUDGET_MS = (
    LIFECYCLE_WRITER_LOCK_TIMEOUT_SECONDS * 1_000.0
    + POSTFLIGHT_COMPLETION_HEADROOM_MS
)
POSTFLIGHT_LAUNCHER_TIMEOUT_SECONDS = (
    POSTFLIGHT_TERMINAL_BUDGET_MS / 1_000.0 + 30.0
)


def _default_observation_rationale(
    hit_quality: str,
    suggested_action: str,
    exposed_gap: bool,
) -> str:
    parts: list[str] = []
    if hit_quality and hit_quality != "none":
        parts.append(f"retrieval={hit_quality}")
    if suggested_action and suggested_action != "none":
        parts.append(f"next={suggested_action}")
    if exposed_gap:
        parts.append("gap-exposed")
    return ", ".join(parts)


def build_observation(
    task_summary: str,
    route_hint: str = "",
    entry_ids: str = "",
    hit_quality: str = "none",
    outcome: str = "",
    comment: str = "",
    suggested_action: str = "none",
    exposed_gap: bool = False,
    scenario: str = "",
    action_taken: str = "",
    observed_result: str = "",
    previous_action: str = "",
    previous_result: str = "",
    revised_action: str = "",
    revised_result: str = "",
    operational_use: str = "",
    reuse_judgment: str = "",
    source_kind: str = "task",
    agent_name: str = "kb-recorder",
    thread_ref: str = "",
    project_ref: str = "",
    workspace_root: str = "",
    event_id: str = "",
) -> dict[str, Any]:
    rationale = comment.strip() or _default_observation_rationale(
        hit_quality=hit_quality,
        suggested_action=suggested_action,
        exposed_gap=exposed_gap,
    )
    return build_history_event(
        "observation",
        source={
            "kind": source_kind,
            "agent": agent_name,
            "thread_ref": thread_ref,
            "project_ref": project_ref,
            "workspace_root": workspace_root,
        },
        target={
            "kind": "task-observation",
            "task_summary": task_summary,
            "route_hint": parse_route_segments(route_hint),
            "entry_ids": csv_to_list(entry_ids),
        },
        rationale=rationale,
        context={
            "hit_quality": hit_quality,
            "outcome": outcome,
            "suggested_action": suggested_action,
            "exposed_gap": exposed_gap,
            "predictive_observation": {
                "scenario": scenario,
                "action_taken": action_taken,
                "observed_result": observed_result,
                "contrastive_evidence": {
                    "previous_action": previous_action,
                    "previous_result": previous_result,
                    "revised_action": revised_action,
                    "revised_result": revised_result,
                },
                "operational_use": operational_use,
                "reuse_judgment": reuse_judgment,
            },
        },
        event_id=event_id or None,
    )


def _postflight_receipt_path(repo_root: Path, event_id: str) -> Path:
    digest = hashlib.sha256(str(event_id).encode("utf-8")).hexdigest()
    return Path(repo_root) / POSTFLIGHT_RECEIPT_ROOT / f"{digest}.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "path": str(path)}
    payload = path.read_bytes()
    return {
        "exists": True,
        "path": str(path),
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _runtime_authority_snapshot(repo_root: Path) -> dict[str, Any]:
    root = Path(repo_root)
    return {
        "lifecycle_current": _file_identity(
            root / "kb" / "history" / "lifecycle" / "current.json"
        ),
        "logicguard_current": _file_identity(
            root
            / ".local"
            / "khaos-brain"
            / "logicguard-authority"
            / "current-generation.json"
        ),
        "active_index": _file_identity(root / "kb" / "indexes" / "active.json"),
        "active_index_authority": _file_identity(
            root / "kb" / "indexes" / "active-authority.json"
        ),
        "active_index_invalidation": _file_identity(
            root / "kb" / "indexes" / "active-invalidated.json"
        ),
    }


def _history_event_matches(
    repo_root: Path,
    event_id: str,
) -> list[dict[str, Any]]:
    from local_kb.store import history_events_path

    path = history_events_path(repo_root)
    if not path.is_file():
        return []
    matches: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            text = raw_line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed history at {path}:{line_number}: {exc}"
                ) from exc
            if (
                isinstance(payload, dict)
                and str(payload.get("event_id") or "") == event_id
            ):
                matches.append(payload)
    return matches


def _terminal_receipt(
    payload: dict[str, Any],
) -> dict[str, Any]:
    from local_kb.lifecycle import content_fingerprint

    body = dict(payload)
    body["receipt_digest"] = content_fingerprint(body)
    return body


def inspect_observation_postflight(
    repo_root: Path,
    event_id: str,
) -> dict[str, Any]:
    from local_kb.lifecycle import content_fingerprint
    from local_kb.store import history_events_path

    root = Path(repo_root)
    clean_event_id = str(event_id or "").strip()
    if not clean_event_id:
        raise ValueError("Postflight inspection requires event_id")
    receipt_path = _postflight_receipt_path(root, clean_event_id)
    receipt = _read_json_object(receipt_path)
    stored_digest = str(receipt.get("receipt_digest") or "")
    digest_body = dict(receipt)
    digest_body.pop("receipt_digest", None)
    receipt_valid = bool(
        receipt
        and stored_digest
        and stored_digest == content_fingerprint(digest_body)
        and str(receipt.get("schema_version") or "") == POSTFLIGHT_RECEIPT_SCHEMA
        and str(receipt.get("event_id") or "") == clean_event_id
    )
    matches = _history_event_matches(root, clean_event_id)
    fingerprints = [content_fingerprint(item) for item in matches]
    unique = len(matches) == 1
    receipt_status = str(receipt.get("status") or "") if receipt_valid else ""
    receipt_event_fingerprint = (
        str(receipt.get("event_fingerprint") or "") if receipt_valid else ""
    )
    event_matches_receipt = bool(
        unique
        and receipt_event_fingerprint
        and fingerprints[0] == receipt_event_fingerprint
    )
    if receipt_status == "success" and event_matches_receipt:
        status = "success"
        ok = True
    elif receipt_status == "failed":
        status = "failed"
        ok = False
    elif len(matches) > 1:
        status = "failed"
        ok = False
    elif matches:
        status = "timeout_unknown"
        ok = False
    else:
        status = "failed"
        ok = False
    return {
        "schema_version": "khaos-brain.postflight-observation-inspection.v1",
        "ok": ok,
        "status": status,
        "event_id": clean_event_id,
        "history_path": str(history_events_path(root)),
        "history_event_count": len(matches),
        "history_event_unique": unique,
        "history_event_fingerprints": fingerprints,
        "receipt_path": str(receipt_path),
        "receipt_exists": bool(receipt),
        "receipt_valid": receipt_valid,
        "receipt_status": receipt_status,
        "event_matches_receipt": event_matches_receipt,
        "receipt": receipt if receipt_valid else {},
        "claim_boundary": (
            "success means one durable history event and one matching terminal "
            "receipt; a persisted event without that receipt is timeout_unknown, "
            "never inferred success"
        ),
    }


def record_observation_result(
    repo_root: Path,
    observation: dict[str, Any],
) -> dict[str, Any]:
    from local_kb.lifecycle import (
        _atomic_write_json,
        _lifecycle_lock,
        content_fingerprint,
        lifecycle_root,
    )
    from local_kb.store import history_events_path

    root = Path(repo_root)
    event_id = str(observation.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("Observation postflight requires a stable event_id")
    if str(observation.get("event_type") or "") != "observation":
        raise ValueError("Observation postflight accepts only observation events")
    event_fingerprint = content_fingerprint(observation)
    receipt_path = _postflight_receipt_path(root, event_id)
    started = time.perf_counter()

    existing = inspect_observation_postflight(root, event_id)
    if existing["status"] == "success":
        return {
            **existing,
            "created": False,
            "idempotent_reuse": True,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    if existing["history_event_count"]:
        return {
            **existing,
            "created": False,
            "idempotent_reuse": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    lock_owner: dict[str, Any] = {}
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    created = False
    try:
        with _lifecycle_lock(root) as owner:
            lock_owner = dict(owner)
            matches = _history_event_matches(root, event_id)
            if matches:
                return {
                    **inspect_observation_postflight(root, event_id),
                    "created": False,
                    "idempotent_reuse": False,
                    "duration_ms": round(
                        (time.perf_counter() - started) * 1000, 3
                    ),
                }
            before = _runtime_authority_snapshot(root)
            record_history_event(root, observation)
            created = True
            after = _runtime_authority_snapshot(root)
        lock_path = lifecycle_root(root) / ".writer.lock" / "owner.json"
        remaining_owner = _read_json_object(lock_path)
        lock_release_confirmed = (
            str(remaining_owner.get("token") or "")
            != str(lock_owner.get("token") or "")
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        receipt = _terminal_receipt(
            {
                "schema_version": POSTFLIGHT_RECEIPT_SCHEMA,
                "status": "success",
                "event_id": event_id,
                "event_fingerprint": event_fingerprint,
                "history_path": str(history_events_path(root)),
                "history_event_count": 1,
                "history_event_unique": True,
                "runtime_authority_before": before,
                "runtime_authority_after": after,
                "runtime_authority_unchanged": before == after,
                "lifecycle_admission": "deferred_to_sleep_primary_path",
                "lifecycle_writer_lock_token": str(lock_owner.get("token") or ""),
                "lifecycle_writer_lock_release_confirmed": lock_release_confirmed,
                "duration_ms": duration_ms,
                "terminal_budget_ms": POSTFLIGHT_TERMINAL_BUDGET_MS,
                "within_terminal_budget": duration_ms <= POSTFLIGHT_TERMINAL_BUDGET_MS,
            }
        )
        _atomic_write_json(receipt_path, receipt)
    except Exception as exc:
        matches = _history_event_matches(root, event_id)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        receipt = _terminal_receipt(
            {
                "schema_version": POSTFLIGHT_RECEIPT_SCHEMA,
                "status": "failed",
                "event_id": event_id,
                "event_fingerprint": event_fingerprint,
                "history_path": str(history_events_path(root)),
                "history_event_count": len(matches),
                "history_event_unique": len(matches) == 1,
                "effect_persisted": bool(matches),
                "error": f"{type(exc).__name__}: {exc}",
                "lifecycle_writer_lock_token": str(lock_owner.get("token") or ""),
                "duration_ms": duration_ms,
                "terminal_budget_ms": POSTFLIGHT_TERMINAL_BUDGET_MS,
                "within_terminal_budget": duration_ms <= POSTFLIGHT_TERMINAL_BUDGET_MS,
            }
        )
        _atomic_write_json(receipt_path, receipt)
        return {
            "schema_version": "khaos-brain.postflight-observation-result.v1",
            "ok": False,
            "status": "failed",
            "event_id": event_id,
            "created": created,
            "idempotent_reuse": False,
            "history_path": str(history_events_path(root)),
            "receipt_path": str(receipt_path),
            "receipt": receipt,
            "duration_ms": duration_ms,
        }

    inspected = inspect_observation_postflight(root, event_id)
    return {
        **inspected,
        "created": created,
        "idempotent_reuse": False,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def record_observation(repo_root, observation: dict[str, Any]):
    result = record_observation_result(Path(repo_root), observation)
    if not result.get("ok"):
        raise RuntimeError(
            "Observation postflight did not reach terminal success: "
            f"{result.get('status')}"
        )
    return Path(result["history_path"])
