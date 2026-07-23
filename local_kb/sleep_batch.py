from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from uuid import uuid4


SLEEP_BATCH_ROOT = Path(".local") / "khaos-brain" / "sleep-batches"
SLEEP_BATCH_HEAD_SCHEMA = "khaos-brain.sleep-batch-head.v1"
SLEEP_BATCH_PLAN_SCHEMA = "khaos-brain.sleep-batch-plan.v1"
SLEEP_BATCH_CHECKPOINT_SCHEMA = "khaos-brain.sleep-batch-checkpoint.v1"
SLEEP_BATCH_ITEM_RESULT_SCHEMA = "khaos-brain.sleep-batch-item-result.v1"

DEFAULT_MIN_BATCH_ITEMS = 25
DEFAULT_MAX_BATCH_ITEMS = 250

_BATCH_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TERMINAL_ITEM_STATUSES = {"completed", "blocked"}


class SleepBatchError(RuntimeError):
    """Raised when persisted Sleep batch authority is invalid or inconsistent."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SleepBatchError(f"Missing {label}: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SleepBatchError(f"Unreadable {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SleepBatchError(f"Invalid {label}: expected a JSON object at {path}")
    return payload


def sleep_batch_root(repo_root: Path) -> Path:
    return Path(repo_root) / SLEEP_BATCH_ROOT


def sleep_batch_head_path(repo_root: Path) -> Path:
    return sleep_batch_root(repo_root) / "HEAD.json"


def sleep_batch_dir(repo_root: Path, batch_id: str) -> Path:
    _validate_batch_id(batch_id)
    return sleep_batch_root(repo_root) / batch_id


def sleep_batch_plan_path(repo_root: Path, batch_id: str) -> Path:
    return sleep_batch_dir(repo_root, batch_id) / "plan.json"


def sleep_batch_checkpoint_path(repo_root: Path, batch_id: str) -> Path:
    return sleep_batch_dir(repo_root, batch_id) / "checkpoint.json"


def sleep_batch_result_dir(repo_root: Path, batch_id: str) -> Path:
    return sleep_batch_dir(repo_root, batch_id) / "results"


def _result_path(repo_root: Path, batch_id: str, item_id: str) -> Path:
    filename = hashlib.sha256(item_id.encode("utf-8")).hexdigest() + ".json"
    return sleep_batch_result_dir(repo_root, batch_id) / filename


def _validate_batch_id(batch_id: str) -> None:
    if not isinstance(batch_id, str) or not _BATCH_ID_PATTERN.fullmatch(batch_id):
        raise ValueError("batch_id must be a safe 1-128 character identifier")


def _normalize_item_ids(values: Sequence[str], *, label: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"{label} must contain only non-empty strings")
        item_id = raw.strip()
        if item_id in seen:
            raise ValueError(f"{label} contains duplicate item_id {item_id!r}")
        seen.add(item_id)
        normalized.append(item_id)
    return normalized


def calculate_sleep_batch_target(
    opening_remaining_count: int,
    newly_eligible_count: int,
    *,
    min_items: int = DEFAULT_MIN_BATCH_ITEMS,
    max_items: int = DEFAULT_MAX_BATCH_ITEMS,
) -> int:
    """Return ``min(opening, clamp(2 * new, min, max))``.

    A non-empty backlog therefore still receives at least the tested minimum
    even when no new item arrived since the preceding Sleep cycle.
    """

    values = {
        "opening_remaining_count": opening_remaining_count,
        "newly_eligible_count": newly_eligible_count,
        "min_items": min_items,
        "max_items": max_items,
    }
    if any(not isinstance(value, int) or isinstance(value, bool) for value in values.values()):
        raise TypeError("Sleep batch counts and bounds must be integers")
    if opening_remaining_count < 0 or newly_eligible_count < 0:
        raise ValueError("Sleep batch counts must be non-negative")
    if min_items <= 0 or max_items <= 0 or min_items > max_items:
        raise ValueError("Sleep batch bounds require 0 < min_items <= max_items")
    desired = max(min_items, min(max_items, 2 * newly_eligible_count))
    return min(opening_remaining_count, desired)


def _new_batch_id(now: str) -> str:
    compact = re.sub(r"[^0-9]", "", now)[:14] or "batch"
    return f"sleep-{compact}-{uuid4().hex[:12]}"


def _validate_plan(plan: Mapping[str, Any], *, batch_id: str) -> None:
    if plan.get("schema_version") != SLEEP_BATCH_PLAN_SCHEMA:
        raise SleepBatchError("Sleep batch plan schema is not current")
    if plan.get("batch_id") != batch_id:
        raise SleepBatchError("Sleep batch plan identity does not match HEAD")
    eligible = _normalize_item_ids(list(plan.get("eligible_item_ids") or []), label="eligible_item_ids")
    selected = _normalize_item_ids(list(plan.get("selected_item_ids") or []), label="selected_item_ids")
    deferred = _normalize_item_ids(list(plan.get("deferred_item_ids") or []), label="deferred_item_ids")
    newly_eligible = _normalize_item_ids(
        list(plan.get("newly_eligible_item_ids") or []),
        label="newly_eligible_item_ids",
    )
    eligible_set = set(eligible)
    if not set(newly_eligible).issubset(eligible_set):
        raise SleepBatchError("Newly eligible item ids are outside the frozen boundary")
    if selected + deferred != eligible:
        raise SleepBatchError("Selected and deferred item ids do not preserve the frozen boundary")
    expected_counts = {
        "opening_remaining_count": len(eligible),
        "newly_eligible_count": len(newly_eligible),
        "target_item_count": len(selected),
        "deferred_item_count": len(deferred),
    }
    for field, expected in expected_counts.items():
        if plan.get(field) != expected:
            raise SleepBatchError(f"Sleep batch plan field {field} is inconsistent")
    expected_target = calculate_sleep_batch_target(
        len(eligible),
        len(newly_eligible),
        min_items=int(plan.get("min_items") or 0),
        max_items=int(plan.get("max_items") or 0),
    )
    if len(selected) != expected_target:
        raise SleepBatchError("Sleep batch target does not match the current bounded formula")
    prior = plan.get("prior_remaining_count")
    if not isinstance(prior, int) or isinstance(prior, bool) or prior < 0:
        raise SleepBatchError("Sleep batch prior_remaining_count must be non-negative")
    prior_streak = plan.get("prior_no_reduction_streak")
    if not isinstance(prior_streak, int) or isinstance(prior_streak, bool) or prior_streak < 0:
        raise SleepBatchError("Sleep batch prior_no_reduction_streak must be non-negative")
    if not isinstance(plan.get("current_generation_id"), str):
        raise SleepBatchError("Sleep batch current_generation_id must be a string")
    if not str(plan.get("input_digest") or "").strip():
        raise SleepBatchError("Sleep batch input_digest is required")


def _load_results(
    repo_root: Path,
    *,
    batch_id: str,
    selected_item_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    result_dir = sleep_batch_result_dir(repo_root, batch_id)
    if not result_dir.exists():
        return {}
    selected = set(selected_item_ids)
    results: dict[str, dict[str, Any]] = {}
    for path in sorted(result_dir.glob("*.json")):
        payload = _read_json(path, label="Sleep batch item result")
        if payload.get("schema_version") != SLEEP_BATCH_ITEM_RESULT_SCHEMA:
            raise SleepBatchError(f"Sleep batch item result schema is not current: {path}")
        if payload.get("batch_id") != batch_id:
            raise SleepBatchError(f"Sleep batch item result has foreign batch identity: {path}")
        item_id = payload.get("item_id")
        if not isinstance(item_id, str) or item_id not in selected:
            raise SleepBatchError(f"Sleep batch item result is outside the frozen selection: {path}")
        if path != _result_path(repo_root, batch_id, item_id):
            raise SleepBatchError(f"Sleep batch item result filename does not match its item id: {path}")
        status = payload.get("status")
        if status not in _TERMINAL_ITEM_STATUSES:
            raise SleepBatchError(f"Sleep batch item result has invalid status: {path}")
        if status == "blocked":
            if not str(payload.get("owner") or "").strip():
                raise SleepBatchError(f"Blocked Sleep item has no owner: {path}")
            if not str(payload.get("reopen_condition") or "").strip():
                raise SleepBatchError(f"Blocked Sleep item has no reopen condition: {path}")
        if item_id in results:
            raise SleepBatchError(f"Duplicate immutable result for Sleep item {item_id!r}")
        results[item_id] = payload
    return results


def _build_checkpoint(
    plan: Mapping[str, Any],
    results: Mapping[str, Mapping[str, Any]],
    *,
    revision: int,
    created_at: str,
    updated_at: str,
) -> dict[str, Any]:
    selected = list(plan["selected_item_ids"])
    completed = [item_id for item_id in selected if results.get(item_id, {}).get("status") == "completed"]
    blocked = [item_id for item_id in selected if results.get(item_id, {}).get("status") == "blocked"]
    pending = [item_id for item_id in selected if item_id not in results]
    deferred = list(plan["deferred_item_ids"])
    opening = int(plan["opening_remaining_count"])
    closing = len(deferred) + len(pending)
    prior = int(plan["prior_remaining_count"])
    if closing < prior:
        trend = "shrinking"
    elif closing > prior:
        trend = "growing"
    else:
        trend = "flat"
    no_reduction_streak = 0 if trend == "shrinking" else int(plan["prior_no_reduction_streak"]) + 1
    settled = not pending
    if settled and blocked:
        state = "settled_with_blocks"
    elif settled:
        state = "completed"
    else:
        state = "in_progress"
    return {
        "schema_version": SLEEP_BATCH_CHECKPOINT_SCHEMA,
        "batch_id": plan["batch_id"],
        "revision": revision,
        "created_at": created_at,
        "updated_at": updated_at,
        "state": state,
        "settled": settled,
        "completed_item_ids": completed,
        "blocked_item_ids": blocked,
        "pending_item_ids": pending,
        "deferred_item_ids": deferred,
        "completed_count": len(completed),
        "blocked_count": len(blocked),
        "pending_count": len(pending),
        "processed_count": len(completed) + len(blocked),
        "opening_remaining_count": opening,
        "closing_remaining_count": closing,
        "net_reduction": opening - closing,
        "prior_remaining_count": prior,
        "remainder_delta_from_prior": closing - prior,
        "remainder_trend": trend,
        "no_reduction_streak": no_reduction_streak,
        "backlog_growing": no_reduction_streak >= 2,
    }


def _checkpoint_matches_results(
    checkpoint: Mapping[str, Any],
    plan: Mapping[str, Any],
    results: Mapping[str, Mapping[str, Any]],
) -> bool:
    if checkpoint.get("schema_version") != SLEEP_BATCH_CHECKPOINT_SCHEMA:
        return False
    try:
        expected = _build_checkpoint(
            plan,
            results,
            revision=int(checkpoint.get("revision") or 0),
            created_at=str(checkpoint.get("created_at") or ""),
            updated_at=str(checkpoint.get("updated_at") or ""),
        )
    except (TypeError, ValueError, KeyError):
        return False
    return dict(checkpoint) == expected


def _write_head(
    repo_root: Path,
    *,
    batch_id: str,
    plan: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    previous_generation: int,
    now: str,
) -> dict[str, Any]:
    head = {
        "schema_version": SLEEP_BATCH_HEAD_SCHEMA,
        "generation": previous_generation + 1,
        "batch_id": batch_id,
        "plan_ref": f"{batch_id}/plan.json",
        "plan_digest": _digest(plan),
        "checkpoint_ref": f"{batch_id}/checkpoint.json",
        "checkpoint_digest": _digest(checkpoint),
        "checkpoint_revision": checkpoint["revision"],
        "settled": checkpoint["settled"],
        "updated_at": now,
    }
    _atomic_write_json(sleep_batch_head_path(repo_root), head)
    return head


def load_current_sleep_batch(
    repo_root: Path,
    *,
    reconcile: bool = True,
) -> dict[str, Any] | None:
    """Load and validate the active batch, rebuilding derived state if needed.

    The immutable plan and item-result files are authority.  ``checkpoint.json``
    and ``HEAD.json`` are restart-safe projections and may be reconciled after a
    process stopped between those atomic writes.
    """

    head_path = sleep_batch_head_path(repo_root)
    if not head_path.exists():
        return None
    head = _read_json(head_path, label="Sleep batch HEAD")
    if head.get("schema_version") != SLEEP_BATCH_HEAD_SCHEMA:
        raise SleepBatchError("Sleep batch HEAD schema is not current")
    batch_id = head.get("batch_id")
    if not isinstance(batch_id, str):
        raise SleepBatchError("Sleep batch HEAD has no batch identity")
    _validate_batch_id(batch_id)
    expected_plan_ref = f"{batch_id}/plan.json"
    expected_checkpoint_ref = f"{batch_id}/checkpoint.json"
    if head.get("plan_ref") != expected_plan_ref or head.get("checkpoint_ref") != expected_checkpoint_ref:
        raise SleepBatchError("Sleep batch HEAD references an unexpected path")
    plan = _read_json(sleep_batch_plan_path(repo_root, batch_id), label="Sleep batch plan")
    _validate_plan(plan, batch_id=batch_id)
    if head.get("plan_digest") != _digest(plan):
        raise SleepBatchError("Sleep batch immutable plan digest does not match HEAD")
    checkpoint = _read_json(
        sleep_batch_checkpoint_path(repo_root, batch_id),
        label="Sleep batch checkpoint",
    )
    results = _load_results(
        repo_root,
        batch_id=batch_id,
        selected_item_ids=list(plan["selected_item_ids"]),
    )
    checkpoint_current = _checkpoint_matches_results(checkpoint, plan, results)
    head_current = (
        head.get("checkpoint_digest") == _digest(checkpoint)
        and head.get("checkpoint_revision") == checkpoint.get("revision")
        and head.get("settled") == checkpoint.get("settled")
    )
    if not checkpoint_current:
        if not reconcile:
            raise SleepBatchError("Sleep batch checkpoint does not match immutable item results")
        previous_revision = checkpoint.get("revision")
        if not isinstance(previous_revision, int) or isinstance(previous_revision, bool):
            previous_revision = 0
        now = _utc_now_iso()
        checkpoint = _build_checkpoint(
            plan,
            results,
            revision=max(0, previous_revision) + 1,
            created_at=str(checkpoint.get("created_at") or now),
            updated_at=now,
        )
        _atomic_write_json(sleep_batch_checkpoint_path(repo_root, batch_id), checkpoint)
        head_current = False
    if not head_current:
        if not reconcile:
            raise SleepBatchError("Sleep batch HEAD does not match the current checkpoint")
        generation = head.get("generation")
        if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
            generation = 0
        head = _write_head(
            repo_root,
            batch_id=batch_id,
            plan=plan,
            checkpoint=checkpoint,
            previous_generation=generation,
            now=_utc_now_iso(),
        )
    return {
        "head": head,
        "plan": plan,
        "checkpoint": checkpoint,
        "results": results,
    }


def start_or_resume_sleep_batch(
    repo_root: Path,
    *,
    eligible_item_ids: Sequence[str],
    newly_eligible_item_ids: Sequence[str],
    prior_remaining_count: int | None = None,
    input_watermark: Mapping[str, Any] | int | str | None = None,
    input_digest: str = "",
    current_generation_id: str = "",
    min_items: int = DEFAULT_MIN_BATCH_ITEMS,
    max_items: int = DEFAULT_MAX_BATCH_ITEMS,
    batch_id: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Resume the unsettled active batch or atomically freeze a new batch."""

    current = load_current_sleep_batch(repo_root)
    if current is not None and not current["checkpoint"]["settled"]:
        return {**current, "resumed": True}

    eligible = _normalize_item_ids(eligible_item_ids, label="eligible_item_ids")
    newly_eligible = _normalize_item_ids(
        newly_eligible_item_ids,
        label="newly_eligible_item_ids",
    )
    if not set(newly_eligible).issubset(set(eligible)):
        raise ValueError("newly_eligible_item_ids must be inside eligible_item_ids")
    target = calculate_sleep_batch_target(
        len(eligible),
        len(newly_eligible),
        min_items=min_items,
        max_items=max_items,
    )
    if prior_remaining_count is None:
        if current is not None:
            prior_remaining_count = int(current["checkpoint"]["closing_remaining_count"])
        else:
            prior_remaining_count = max(0, len(eligible) - len(newly_eligible))
    prior_no_reduction_streak = (
        int(current["checkpoint"].get("no_reduction_streak") or 0)
        if current is not None
        else 0
    )
    if (
        not isinstance(prior_remaining_count, int)
        or isinstance(prior_remaining_count, bool)
        or prior_remaining_count < 0
    ):
        raise ValueError("prior_remaining_count must be a non-negative integer")

    timestamp = now or _utc_now_iso()
    selected_batch_id = batch_id or _new_batch_id(timestamp)
    _validate_batch_id(selected_batch_id)
    batch_path = sleep_batch_dir(repo_root, selected_batch_id)
    if batch_path.exists():
        raise SleepBatchError(f"Sleep batch already exists: {selected_batch_id}")
    selected = eligible[:target]
    deferred = eligible[target:]
    frozen_input_digest = input_digest.strip() or _digest(
        {
            "input_watermark": input_watermark,
            "eligible_item_ids": eligible,
            "newly_eligible_item_ids": newly_eligible,
            "prior_remaining_count": prior_remaining_count,
        }
    )
    plan = {
        "schema_version": SLEEP_BATCH_PLAN_SCHEMA,
        "batch_id": selected_batch_id,
        "created_at": timestamp,
        "input_watermark": input_watermark,
        "input_digest": frozen_input_digest,
        "current_generation_id": str(current_generation_id),
        "prior_remaining_count": prior_remaining_count,
        "prior_no_reduction_streak": prior_no_reduction_streak,
        "opening_remaining_count": len(eligible),
        "newly_eligible_count": len(newly_eligible),
        "newly_eligible_item_ids": newly_eligible,
        "min_items": min_items,
        "max_items": max_items,
        "target_formula": "min(opening_remaining_count, clamp(2 * newly_eligible_count, min_items, max_items))",
        "target_item_count": target,
        "eligible_item_ids": eligible,
        "selected_item_ids": selected,
        "deferred_item_ids": deferred,
        "deferred_item_count": len(deferred),
    }
    _validate_plan(plan, batch_id=selected_batch_id)
    checkpoint = _build_checkpoint(
        plan,
        {},
        revision=0,
        created_at=timestamp,
        updated_at=timestamp,
    )
    _atomic_write_json(sleep_batch_plan_path(repo_root, selected_batch_id), plan)
    _atomic_write_json(sleep_batch_checkpoint_path(repo_root, selected_batch_id), checkpoint)
    previous_generation = int(current["head"]["generation"]) if current is not None else 0
    head = _write_head(
        repo_root,
        batch_id=selected_batch_id,
        plan=plan,
        checkpoint=checkpoint,
        previous_generation=previous_generation,
        now=timestamp,
    )
    return {
        "head": head,
        "plan": plan,
        "checkpoint": checkpoint,
        "results": {},
        "resumed": False,
    }


def _result_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "batch_id": payload.get("batch_id"),
        "item_id": payload.get("item_id"),
        "status": payload.get("status"),
        "owner": payload.get("owner"),
        "reopen_condition": payload.get("reopen_condition"),
        "details": payload.get("details"),
    }


def record_sleep_batch_item_result(
    repo_root: Path,
    *,
    batch_id: str,
    item_id: str,
    status: str,
    details: Mapping[str, Any] | None = None,
    owner: str = "",
    reopen_condition: str = "",
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Durably record one terminal item result and advance the derived checkpoint.

    Existing results are immutable.  An exact semantic retry is idempotent;
    trying to change the result for the same item fails visibly.
    """

    if status not in _TERMINAL_ITEM_STATUSES:
        raise ValueError("status must be 'completed' or 'blocked'")
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("item_id must be a non-empty string")
    item_id = item_id.strip()
    if details is not None and not isinstance(details, Mapping):
        raise TypeError("details must be a mapping")
    owner = owner.strip()
    reopen_condition = reopen_condition.strip()
    if status == "blocked" and (not owner or not reopen_condition):
        raise ValueError("blocked results require both owner and reopen_condition")
    if status == "completed" and (owner or reopen_condition):
        raise ValueError("completed results cannot carry blocked-item ownership")

    current = load_current_sleep_batch(repo_root)
    if current is None or current["plan"]["batch_id"] != batch_id:
        raise SleepBatchError("The requested Sleep batch is not the active batch")
    if item_id not in set(current["plan"]["selected_item_ids"]):
        raise SleepBatchError("The item is outside the active batch's frozen selection")
    payload = {
        "schema_version": SLEEP_BATCH_ITEM_RESULT_SCHEMA,
        "batch_id": batch_id,
        "item_id": item_id,
        "status": status,
        "owner": owner,
        "reopen_condition": reopen_condition,
        "details": dict(details or {}),
        "recorded_at": recorded_at or _utc_now_iso(),
    }
    path = _result_path(repo_root, batch_id, item_id)
    if path.exists():
        existing = _read_json(path, label="Sleep batch item result")
        if _result_identity(existing) != _result_identity(payload):
            raise SleepBatchError(f"Immutable Sleep result already exists for {item_id!r}")
        return {
            **current,
            "item_result": existing,
        }
    else:
        _atomic_write_json(path, payload)

    results = _load_results(
        repo_root,
        batch_id=batch_id,
        selected_item_ids=list(current["plan"]["selected_item_ids"]),
    )
    old_checkpoint = current["checkpoint"]
    timestamp = recorded_at or _utc_now_iso()
    checkpoint = _build_checkpoint(
        current["plan"],
        results,
        revision=int(old_checkpoint["revision"]) + 1,
        created_at=str(old_checkpoint["created_at"]),
        updated_at=timestamp,
    )
    _atomic_write_json(sleep_batch_checkpoint_path(repo_root, batch_id), checkpoint)
    head = _write_head(
        repo_root,
        batch_id=batch_id,
        plan=current["plan"],
        checkpoint=checkpoint,
        previous_generation=int(current["head"]["generation"]),
        now=timestamp,
    )
    return {
        "head": head,
        "plan": current["plan"],
        "checkpoint": checkpoint,
        "results": results,
        "item_result": payload,
    }
