from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Iterator, Mapping
from uuid import uuid4

from local_kb.common import utc_now_iso
from local_kb.maintenance_lanes import (
    acquire_lane_lock,
    process_owner_is_alive,
    release_lane_lock,
)
from local_kb.store import history_events_path


LIFECYCLE_SCHEMA_VERSION = 1
EVIDENCE_POLICY_VERSION = 1
SLEEP_POLICY_VERSION = 1
LIFECYCLE_ROOT = Path("kb") / "history" / "lifecycle"
LIFECYCLE_EVENTS_FILENAME = "events.jsonl"
LIFECYCLE_CURRENT_FILENAME = "current.json"
SLEEP_STATE_FILENAME = "sleep_state.json"
SLEEP_RECEIPT_DIRNAME = "sleep-receipts"
RETRIEVAL_RECEIPT_FILENAME = "retrieval_receipts.jsonl"
OUTCOME_RECEIPT_FILENAME = "outcome_receipts.jsonl"
DREAM_HANDOFF_FILENAME = "dream_handoffs.jsonl"
DREAM_HANDOFF_ACK_FILENAME = "dream_handoff_acks.jsonl"
LIFECYCLE_WRITER_LOCK_SCHEMA = "khaos-brain.lifecycle-writer-lock.v1"
LIFECYCLE_WRITER_LOCK_FILENAME = "owner.json"
LIFECYCLE_WRITER_LOCK_TIMEOUT_SECONDS = 120.0
LIFECYCLE_WRITER_LOCK_ORPHAN_GRACE_SECONDS = 2.0
LIFECYCLE_WRITER_LOCK_RELEASE_TIMEOUT_SECONDS = 2.0

_LIFECYCLE_LOCK_STATE_GUARD = threading.Lock()
_LIFECYCLE_LOCK_DEPTHS: dict[tuple[str, int, int], int] = {}

OBSERVATION_DISPOSITIONS = {
    "represented",
    "candidate",
    "dream_pending",
    "history_only",
    "rejected",
    "parked",
}
ACTIONABLE_OBSERVATION_STATES = {"", "new", "missing-admission"}
CANDIDATE_STATES = {"candidate", "trusted", "merged", "rejected", "superseded", "parked"}
TERMINAL_ENTRY_STATES = {"merged", "rejected", "superseded", "parked", "retired", "deprecated"}
ACTIVE_ENTRY_STATES = {"trusted", "candidate"}
EVIDENCE_GRADES = {"strong", "medium", "weak"}
ACTIVE_INDEX_AFFECTING_EVENT_TYPES = {
    "candidate-transition",
    "entry-lifecycle-snapshot",
    "entry-reopened",
}


def lifecycle_root(repo_root: Path) -> Path:
    return Path(repo_root) / LIFECYCLE_ROOT


def lifecycle_events_path(repo_root: Path) -> Path:
    return lifecycle_root(repo_root) / LIFECYCLE_EVENTS_FILENAME


def lifecycle_current_path(repo_root: Path) -> Path:
    return lifecycle_root(repo_root) / LIFECYCLE_CURRENT_FILENAME


def sleep_state_path(repo_root: Path) -> Path:
    return lifecycle_root(repo_root) / SLEEP_STATE_FILENAME


def sleep_receipt_dir(repo_root: Path) -> Path:
    return lifecycle_root(repo_root) / SLEEP_RECEIPT_DIRNAME


def retrieval_receipts_path(repo_root: Path) -> Path:
    return lifecycle_root(repo_root) / RETRIEVAL_RECEIPT_FILENAME


def outcome_receipts_path(repo_root: Path) -> Path:
    return lifecycle_root(repo_root) / OUTCOME_RECEIPT_FILENAME


def dream_handoffs_path(repo_root: Path) -> Path:
    return lifecycle_root(repo_root) / DREAM_HANDOFF_FILENAME


def dream_handoff_acks_path(repo_root: Path) -> Path:
    return lifecycle_root(repo_root) / DREAM_HANDOFF_ACK_FILENAME


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_fingerprint(value: Any) -> str:
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


def _append_jsonl_durable(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(_canonical_json(dict(payload)) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_extend_jsonl(path: Path, payloads: list[Mapping[str, Any]]) -> None:
    """Append a bounded batch without exposing a partial JSONL transaction."""

    if not payloads:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("wb") as output:
        if path.exists():
            with path.open("rb") as source:
                source.seek(0, os.SEEK_END)
                source_size = source.tell()
                final_byte = b""
                if source_size:
                    source.seek(-1, os.SEEK_END)
                    final_byte = source.read(1)
                source.seek(0)
                shutil.copyfileobj(source, output, length=1024 * 1024)
            if source_size and final_byte != b"\n":
                output.write(b"\n")
        for payload in payloads:
            output.write((_canonical_json(dict(payload)) + "\n").encode("utf-8"))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def _atomic_replace_jsonl(path: Path, payloads: list[Mapping[str, Any]]) -> None:
    """Replace one JSONL authority without exposing a partial rewrite."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("wb") as output:
        for payload in payloads:
            output.write((_canonical_json(dict(payload)) + "\n").encode("utf-8"))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def _lifecycle_lock_owner_path(lock_dir: Path) -> Path:
    return lock_dir / LIFECYCLE_WRITER_LOCK_FILENAME


def _read_lifecycle_lock_owner(lock_dir: Path) -> dict[str, Any]:
    owner_path = _lifecycle_lock_owner_path(lock_dir)
    if not owner_path.is_file():
        return {}
    try:
        payload = json.loads(owner_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _lifecycle_lock_owner_is_dead(payload: Mapping[str, Any]) -> bool:
    try:
        pid = int(payload.get("pid") or 0)
    except (TypeError, ValueError):
        return False
    return pid > 0 and not process_owner_is_alive(pid)


def _lifecycle_lock_dir_age_seconds(lock_dir: Path) -> float:
    try:
        return max(0.0, time.time() - lock_dir.stat().st_mtime)
    except OSError:
        return 0.0


def _remove_recoverable_lifecycle_lock(
    lock_dir: Path,
    *,
    expected_token: str,
) -> bool:
    """Remove only the dead or interrupted lock identity already inspected."""

    if not lock_dir.exists():
        return True
    current = _read_lifecycle_lock_owner(lock_dir)
    current_token = str(current.get("token") or "")
    if expected_token:
        if current_token != expected_token or not _lifecycle_lock_owner_is_dead(current):
            return False
    elif current:
        return False
    try:
        shutil.rmtree(lock_dir)
    except OSError:
        return False
    return not lock_dir.exists()


def _release_lifecycle_lock(
    lock_dir: Path,
    *,
    owner: Mapping[str, Any],
    timeout_seconds: float,
) -> None:
    owner_path = _lifecycle_lock_owner_path(lock_dir)
    expected_token = str(owner.get("token") or "")
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    last_error = ""
    while True:
        current = _read_lifecycle_lock_owner(lock_dir)
        if str(current.get("token") or "") != expected_token:
            raise RuntimeError(
                f"Lifecycle writer lock ownership changed before release: {lock_dir}"
            )
        try:
            owner_path.unlink()
            lock_dir.rmdir()
            return
        except OSError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if lock_dir.exists() and not owner_path.exists():
                try:
                    _atomic_write_json(owner_path, owner)
                except OSError as restore_exc:
                    last_error += (
                        "; owner-restore="
                        f"{type(restore_exc).__name__}: {restore_exc}"
                    )
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Lifecycle writer lock release failed without being hidden: "
                    f"{lock_dir}; {last_error}"
                ) from exc
            time.sleep(0.02)


@contextmanager
def _lifecycle_lock(
    repo_root: Path,
    *,
    timeout_seconds: float = LIFECYCLE_WRITER_LOCK_TIMEOUT_SECONDS,
    orphan_grace_seconds: float = LIFECYCLE_WRITER_LOCK_ORPHAN_GRACE_SECONDS,
    release_timeout_seconds: float = LIFECYCLE_WRITER_LOCK_RELEASE_TIMEOUT_SECONDS,
) -> Iterator[None]:
    lock_dir = lifecycle_root(repo_root) / ".writer.lock"
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    lock_key = (str(lock_dir.resolve()), os.getpid(), threading.get_ident())
    with _LIFECYCLE_LOCK_STATE_GUARD:
        current_depth = _LIFECYCLE_LOCK_DEPTHS.get(lock_key, 0)
        if current_depth:
            _LIFECYCLE_LOCK_DEPTHS[lock_key] = current_depth + 1
    if current_depth:
        try:
            yield
        finally:
            with _LIFECYCLE_LOCK_STATE_GUARD:
                next_depth = _LIFECYCLE_LOCK_DEPTHS.get(lock_key, 1) - 1
                if next_depth > 0:
                    _LIFECYCLE_LOCK_DEPTHS[lock_key] = next_depth
                else:
                    _LIFECYCLE_LOCK_DEPTHS.pop(lock_key, None)
        return

    deadline = time.monotonic() + max(0.1, timeout_seconds)
    owner: dict[str, Any] = {}
    while True:
        try:
            lock_dir.mkdir()
            owner = {
                "schema_version": LIFECYCLE_WRITER_LOCK_SCHEMA,
                "token": str(uuid4()),
                "pid": os.getpid(),
                "thread_id": threading.get_ident(),
                "created_at": utc_now_iso(),
            }
            try:
                _atomic_write_json(_lifecycle_lock_owner_path(lock_dir), owner)
            except BaseException:
                shutil.rmtree(lock_dir, ignore_errors=True)
                raise
            break
        except FileExistsError:
            existing = _read_lifecycle_lock_owner(lock_dir)
            existing_token = str(existing.get("token") or "")
            recoverable = (
                bool(existing_token) and _lifecycle_lock_owner_is_dead(existing)
            ) or (
                not existing
                and _lifecycle_lock_dir_age_seconds(lock_dir)
                >= max(0.0, orphan_grace_seconds)
            )
            if recoverable and _remove_recoverable_lifecycle_lock(
                lock_dir,
                expected_token=existing_token,
            ):
                continue
            if time.monotonic() >= deadline:
                owner_summary = (
                    f"pid={existing.get('pid')}, thread_id={existing.get('thread_id')}, "
                    f"token={existing_token}"
                    if existing
                    else "owner=missing-or-invalid"
                )
                raise TimeoutError(
                    f"Lifecycle writer lock is busy: {lock_dir}; {owner_summary}"
                )
            time.sleep(0.02)
    with _LIFECYCLE_LOCK_STATE_GUARD:
        _LIFECYCLE_LOCK_DEPTHS[lock_key] = 1
    body_error: BaseException | None = None
    try:
        yield
    except BaseException as exc:
        body_error = exc
        raise
    finally:
        with _LIFECYCLE_LOCK_STATE_GUARD:
            _LIFECYCLE_LOCK_DEPTHS.pop(lock_key, None)
        try:
            _release_lifecycle_lock(
                lock_dir,
                owner=owner,
                timeout_seconds=release_timeout_seconds,
            )
        except Exception as release_error:
            if body_error is None:
                raise
            raise BaseExceptionGroup(
                "Lifecycle mutation and writer-lock release both failed",
                [body_error, release_error],
            )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            rows.append(payload)
    return rows


def _empty_replay() -> dict[str, Any]:
    return {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "event_count": 0,
        "event_digest": content_fingerprint([]),
        "last_sequence": 0,
        "observations": {},
        "entries": {},
        "idempotency_keys": [],
        "validation": {"ok": True, "issues": []},
    }


def replay_lifecycle(repo_root: Path) -> dict[str, Any]:
    events = _read_jsonl(lifecycle_events_path(repo_root))
    if not events:
        return _empty_replay()
    observations: dict[str, dict[str, Any]] = {}
    entries: dict[str, dict[str, Any]] = {}
    idempotency_keys: list[str] = []
    seen_idempotency_keys: set[str] = set()
    issues: list[str] = []
    expected_sequence = 1
    for event in events:
        sequence = int(event.get("sequence") or 0)
        if sequence != expected_sequence:
            issues.append(f"sequence {sequence} found where {expected_sequence} was expected")
            expected_sequence = max(expected_sequence, sequence)
        expected_sequence += 1
        key = str(event.get("idempotency_key") or "").strip()
        if not key:
            issues.append(f"event sequence {sequence} lacks idempotency_key")
        elif key in seen_idempotency_keys:
            issues.append(f"duplicate idempotency_key: {key}")
        else:
            idempotency_keys.append(key)
            seen_idempotency_keys.add(key)
        event_type = str(event.get("event_type") or "")
        item_id = str(event.get("item_id") or "").strip()
        if event_type == "observation-admitted":
            observations[item_id] = {
                "observation_id": item_id,
                "state": "new",
                "admitted_at": event.get("created_at", ""),
                "source_event": event.get("source_event", {}),
                "source_fingerprint": event.get("source_fingerprint", ""),
                "evidence": event.get("evidence", []),
                "latest_event_id": event.get("lifecycle_event_id", ""),
            }
        elif event_type == "observation-disposition":
            current = observations.setdefault(item_id, {"observation_id": item_id, "state": "missing-admission"})
            current.update(
                {
                    "state": str(event.get("to_state") or ""),
                    "disposition": str(event.get("to_state") or ""),
                    "reason": str(event.get("reason") or ""),
                    "evidence_grade": str(event.get("evidence_grade") or "weak"),
                    "evidence_ids": list(event.get("evidence_ids") or []),
                    "deciding_pass": str(event.get("actor") or ""),
                    "decided_at": str(event.get("created_at") or ""),
                    "target_id": str(event.get("target_id") or ""),
                    "follow_up_id": str(event.get("follow_up_id") or ""),
                    "follow_up_deadline": str(event.get("follow_up_deadline") or ""),
                    "reopen_condition": event.get("reopen_condition", {}),
                    "latest_event_id": event.get("lifecycle_event_id", ""),
                }
            )
        elif event_type in {
            "candidate-transition",
            "entry-lifecycle-snapshot",
            "entry-reopened",
            "entry-calibration-snapshot",
        }:
            previous = entries.get(item_id, {})
            entries[item_id] = {
                **previous,
                "entry_id": item_id,
                "status": str(event.get("to_state") or event.get("status") or "candidate"),
                "previous_status": str(event.get("from_state") or previous.get("status") or ""),
                "reason": str(event.get("reason") or ""),
                "evidence_grade": str(event.get("evidence_grade") or previous.get("evidence_grade") or "weak"),
                "evidence_ids": list(event.get("evidence_ids") or previous.get("evidence_ids") or []),
                "provenance_ids": list(event.get("provenance_ids") or previous.get("provenance_ids") or []),
                "target_id": str(event.get("target_id") or ""),
                "retrieval_eligible": bool(event.get("retrieval_eligible", False)),
                "reopen_condition": event.get("reopen_condition", {}),
                "evidence_fingerprint": str(event.get("evidence_fingerprint") or ""),
                "decision_deadline": str(event.get("decision_deadline") or ""),
                "decision_receipt": event.get("decision_receipt", {}),
                "updated_at": str(event.get("created_at") or ""),
                "latest_event_id": event.get("lifecycle_event_id", ""),
            }
    return {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "event_count": len(events),
        "event_digest": content_fingerprint(events),
        "last_sequence": int(events[-1].get("sequence") or len(events)),
        "observations": observations,
        "entries": entries,
        "idempotency_keys": idempotency_keys,
        "validation": {"ok": not issues, "issues": issues},
    }


def load_lifecycle_state(repo_root: Path, *, repair_projection: bool = True) -> dict[str, Any]:
    state = replay_lifecycle(repo_root)
    projection_path = lifecycle_current_path(repo_root)
    if repair_projection:
        existing: dict[str, Any] = {}
        if projection_path.exists():
            try:
                payload = json.loads(projection_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    existing = payload
            except (OSError, json.JSONDecodeError):
                existing = {}
        if existing.get("event_digest") != state.get("event_digest"):
            # Projection repair is a lifecycle write. Recheck the event log
            # while holding the same identified writer authority so an older
            # replay can never overwrite a newer concurrent lifecycle state.
            with _lifecycle_lock(repo_root):
                state = replay_lifecycle(repo_root)
                current_projection: dict[str, Any] = {}
                if projection_path.exists():
                    try:
                        payload = json.loads(
                            projection_path.read_text(encoding="utf-8")
                        )
                        if isinstance(payload, dict):
                            current_projection = payload
                    except (OSError, json.JSONDecodeError):
                        current_projection = {}
                if current_projection.get("event_digest") != state.get(
                    "event_digest"
                ):
                    _atomic_write_json(projection_path, state)
    return state


def commit_lifecycle_event(repo_root: Path, event: Mapping[str, Any]) -> dict[str, Any]:
    with _lifecycle_lock(repo_root):
        state = replay_lifecycle(repo_root)
        key = str(event.get("idempotency_key") or "").strip()
        if not key:
            raise ValueError("Lifecycle events require idempotency_key")
        if key in set(state.get("idempotency_keys") or []):
            return {
                "created": False,
                "idempotent_reuse": True,
                "idempotency_key": key,
                "state": state,
            }
        payload = {
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "lifecycle_event_id": str(event.get("lifecycle_event_id") or uuid4()),
            "sequence": int(state.get("last_sequence") or 0) + 1,
            "created_at": str(event.get("created_at") or utc_now_iso()),
            **dict(event),
        }
        if str(payload.get("event_type") or "") in ACTIVE_INDEX_AFFECTING_EVENT_TYPES:
            from local_kb.active_index import invalidate_active_index

            invalidate_active_index(
                repo_root,
                reason="entry-lifecycle-event",
                event_type=str(payload.get("event_type") or ""),
                item_id=str(payload.get("item_id") or ""),
            )
        _append_jsonl_durable(lifecycle_events_path(repo_root), payload)
        next_state = replay_lifecycle(repo_root)
        _atomic_write_json(lifecycle_current_path(repo_root), next_state)
        return {
            "created": True,
            "idempotent_reuse": False,
            "event": payload,
            "state": next_state,
        }


def commit_lifecycle_events(
    repo_root: Path,
    events: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    """Commit many lifecycle events with one replay before and after the batch.

    The event log remains the authority.  Existing or intra-batch duplicate
    idempotency keys are reused, and the complete log replacement is atomic so
    interruption cannot expose a partially appended JSON line.
    """

    requested = [dict(event) for event in events]
    with _lifecycle_lock(repo_root, timeout_seconds=30.0):
        state = replay_lifecycle(repo_root)
        known_keys = set(state.get("idempotency_keys") or [])
        next_sequence = int(state.get("last_sequence") or 0)
        created_events: list[dict[str, Any]] = []
        reused_keys: list[str] = []
        for event in requested:
            key = str(event.get("idempotency_key") or "").strip()
            if not key:
                raise ValueError("Lifecycle events require idempotency_key")
            if key in known_keys:
                reused_keys.append(key)
                continue
            next_sequence += 1
            payload = {
                "schema_version": LIFECYCLE_SCHEMA_VERSION,
                "lifecycle_event_id": str(event.get("lifecycle_event_id") or uuid4()),
                "sequence": next_sequence,
                "created_at": str(event.get("created_at") or utc_now_iso()),
                **event,
            }
            created_events.append(payload)
            known_keys.add(key)
        index_affecting = [
            event
            for event in created_events
            if str(event.get("event_type") or "") in ACTIVE_INDEX_AFFECTING_EVENT_TYPES
        ]
        if index_affecting:
            from local_kb.active_index import invalidate_active_index

            invalidate_active_index(
                repo_root,
                reason="entry-lifecycle-batch",
                event_type=str(index_affecting[-1].get("event_type") or ""),
                item_id=str(index_affecting[-1].get("item_id") or ""),
            )
        _atomic_extend_jsonl(lifecycle_events_path(repo_root), created_events)
        next_state = replay_lifecycle(repo_root)
        _atomic_write_json(lifecycle_current_path(repo_root), next_state)
        return {
            "created_count": len(created_events),
            "reused_count": len(reused_keys),
            "requested_count": len(requested),
            "events": created_events,
            "reused_keys": reused_keys,
            "state": next_state,
            "replay_pass_count": 2,
            "atomic_batch_count": 1 if created_events else 0,
        }


def evidence_items_for_observation(observation: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = observation.get("source", {}) if isinstance(observation.get("source"), Mapping) else {}
    context = observation.get("context", {}) if isinstance(observation.get("context"), Mapping) else {}
    predictive = context.get("predictive_observation", {}) if isinstance(context.get("predictive_observation"), Mapping) else {}
    contrastive = predictive.get("contrastive_evidence", {}) if isinstance(predictive.get("contrastive_evidence"), Mapping) else {}
    source_kind = str(source.get("kind") or "task").strip().lower()
    outcome = str(context.get("outcome") or "").strip().lower()
    hit_quality = str(context.get("hit_quality") or "none").strip().lower()
    has_contrast = any(str(contrastive.get(key) or "").strip() for key in ("previous_action", "previous_result", "revised_action", "revised_result"))
    has_predictive_triplet = all(
        str(predictive.get(key) or "").strip()
        for key in ("scenario", "action_taken", "observed_result")
    )
    if source_kind in {"user", "user-correction", "verified-test", "test", "verification"} or has_contrast:
        grade = "strong"
        rationale = "user correction or verified task/test episode"
    elif source_kind.startswith("dream") or has_predictive_triplet or outcome not in {"", "unknown", "none"}:
        grade = "medium"
        rationale = "bounded task episode or Dream result without independent confirmation"
    else:
        grade = "weak"
        rationale = "single unverified observation or AI self-report"
    if hit_quality == "hit" and source_kind in {"agent", "task", "kb-recorder"} and not has_predictive_triplet:
        grade = "weak"
        rationale = "AI-authored retrieval hit without an observable result"
    evidence_payload = {
        "source_kind": source_kind,
        "outcome": outcome,
        "hit_quality": hit_quality,
        "predictive": dict(predictive),
        "target": observation.get("target", {}),
    }
    fingerprint = content_fingerprint(evidence_payload)
    return [
        {
            "evidence_id": f"evidence:{fingerprint[:24]}",
            "fingerprint": fingerprint,
            "grade": grade,
            "rationale": rationale,
            "reference": str(observation.get("event_id") or ""),
            "policy_version": EVIDENCE_POLICY_VERSION,
        }
    ]


def build_observation_admission_event(observation: Mapping[str, Any]) -> dict[str, Any]:
    observation_id = str(observation.get("event_id") or "").strip()
    if not observation_id:
        raise ValueError("Observations require a stable event_id before lifecycle admission")
    evidence = evidence_items_for_observation(observation)
    return {
        "event_type": "observation-admitted",
        "item_id": observation_id,
        "idempotency_key": f"observation-admitted:{observation_id}",
        "actor": "observation-intake",
        "policy_version": EVIDENCE_POLICY_VERSION,
        "source_event": dict(observation),
        "source_fingerprint": content_fingerprint(observation),
        "evidence": evidence,
    }


def admit_observation(repo_root: Path, observation: Mapping[str, Any]) -> dict[str, Any]:
    return commit_lifecycle_event(repo_root, build_observation_admission_event(observation))


def _observation_evidence_grade(observation: Mapping[str, Any]) -> str:
    return str(evidence_items_for_observation(observation)[0]["grade"])


def classify_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    target = observation.get("target", {}) if isinstance(observation.get("target"), Mapping) else {}
    context = observation.get("context", {}) if isinstance(observation.get("context"), Mapping) else {}
    predictive = context.get("predictive_observation", {}) if isinstance(context.get("predictive_observation"), Mapping) else {}
    suggested = str(context.get("suggested_action") or "none").strip().lower()
    entry_ids = [str(item).strip() for item in target.get("entry_ids", []) if str(item).strip()] if isinstance(target.get("entry_ids"), list) else []
    grade = _observation_evidence_grade(observation)
    has_triplet = all(str(predictive.get(key) or "").strip() for key in ("scenario", "action_taken", "observed_result"))
    if suggested == "update-card" and entry_ids:
        return {
            "disposition": "represented",
            "reason": "Observation is owned by an explicit existing-card update review.",
            "target_id": entry_ids[0],
            "evidence_grade": grade,
        }
    if suggested == "new-candidate" and has_triplet and grade in {"strong", "medium"}:
        return {
            "disposition": "candidate",
            "reason": "Bounded predictive evidence is suitable for candidate lifecycle review.",
            "target_id": "",
            "evidence_grade": grade,
        }
    if suggested == "new-candidate":
        return {
            "disposition": "parked",
            "reason": "Candidate signal lacks a complete predictive triplet or independent evidence.",
            "target_id": "",
            "evidence_grade": grade,
            "reopen_condition": {
                "kind": "evidence-grade-at-least",
                "minimum_grade": "medium",
                "requires_new_fingerprint": True,
            },
        }
    if suggested == "taxonomy-change":
        return {
            "disposition": "parked",
            "reason": "A single taxonomy signal is retained until repeated route evidence arrives.",
            "target_id": "",
            "evidence_grade": grade,
            "reopen_condition": {
                "kind": "distinct-episode-count",
                "minimum_count": 2,
                "requires_new_fingerprint": True,
            },
        }
    if entry_ids:
        return {
            "disposition": "represented",
            "reason": "Observation already references active knowledge and remains outcome evidence.",
            "target_id": entry_ids[0],
            "evidence_grade": grade,
        }
    return {
        "disposition": "history_only",
        "reason": "Observation has no defensible reusable action-selection value yet.",
        "target_id": "",
        "evidence_grade": grade,
    }


def build_observation_disposition_event(
    observation: Mapping[str, Any],
    *,
    run_id: str,
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    observation_id = str(observation.get("event_id") or "").strip()
    if not observation_id:
        raise ValueError("Observation disposition requires event_id")
    selected = dict(decision or classify_observation(observation))
    disposition = str(selected.get("disposition") or "").strip()
    if disposition not in OBSERVATION_DISPOSITIONS:
        raise ValueError(f"Unsupported observation disposition: {disposition}")
    evidence = evidence_items_for_observation(observation)
    return {
        "event_type": "observation-disposition",
        "item_id": observation_id,
        "from_state": "new",
        "to_state": disposition,
        "idempotency_key": f"observation-disposition:{observation_id}:{content_fingerprint(selected)}",
        "actor": run_id,
        "reason": str(selected.get("reason") or "").strip(),
        "evidence_grade": str(selected.get("evidence_grade") or evidence[0]["grade"]),
        "evidence_ids": [str(item["evidence_id"]) for item in evidence],
        "target_id": str(selected.get("target_id") or ""),
        "follow_up_id": str(selected.get("follow_up_id") or ""),
        "follow_up_deadline": str(selected.get("follow_up_deadline") or ""),
        "reopen_condition": selected.get("reopen_condition", {}),
        "policy_version": SLEEP_POLICY_VERSION,
    }


def dispose_observation(
    repo_root: Path,
    observation: Mapping[str, Any],
    *,
    run_id: str,
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    observation_id = str(observation.get("event_id") or "").strip()
    if not observation_id:
        raise ValueError("Observation disposition requires event_id")
    current = load_lifecycle_state(repo_root, repair_projection=False).get("observations", {}).get(observation_id, {})
    if isinstance(current, Mapping) and str(current.get("state") or "") not in {"", "new", "missing-admission"}:
        return {
            "created": False,
            "idempotent_reuse": True,
            "idempotency_key": str(current.get("latest_event_id") or f"observation-disposition:{observation_id}"),
            "disposition": dict(current),
        }
    return commit_lifecycle_event(
        repo_root,
        build_observation_disposition_event(observation, run_id=run_id, decision=decision),
    )


def build_entry_transition_event(
    *,
    entry_id: str,
    from_state: str,
    to_state: str,
    reason: str,
    actor: str,
    evidence_ids: list[str] | tuple[str, ...] = (),
    provenance_ids: list[str] | tuple[str, ...] = (),
    evidence_grade: str = "weak",
    target_id: str = "",
    retrieval_eligible: bool = False,
    reopen_condition: Mapping[str, Any] | None = None,
    evidence_fingerprint: str = "",
    decision_deadline: str = "",
    event_type: str = "candidate-transition",
    decision_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_to = str(to_state or "").strip().lower()
    if normalized_to not in CANDIDATE_STATES | {"retired", "deprecated"}:
        raise ValueError(f"Unsupported entry lifecycle state: {normalized_to}")
    normalized_grade = evidence_grade if evidence_grade in EVIDENCE_GRADES else "weak"
    payload = {
        "event_type": event_type,
        "item_id": str(entry_id).strip(),
        "from_state": str(from_state or "").strip().lower(),
        "to_state": normalized_to,
        "actor": actor,
        "reason": reason,
        "evidence_ids": sorted({str(item) for item in evidence_ids if str(item)}),
        "provenance_ids": sorted({str(item) for item in provenance_ids if str(item)}),
        "evidence_grade": normalized_grade,
        "target_id": str(target_id or ""),
        "retrieval_eligible": bool(retrieval_eligible and normalized_to == "candidate"),
        "reopen_condition": dict(reopen_condition or {}),
        "evidence_fingerprint": str(evidence_fingerprint or ""),
        "decision_deadline": str(decision_deadline or ""),
        "policy_version": EVIDENCE_POLICY_VERSION,
        "decision_receipt": dict(decision_receipt or {}),
    }
    payload["idempotency_key"] = (
        f"entry-transition:{entry_id}:{from_state}:{normalized_to}:{content_fingerprint(payload)}"
    )
    return payload


def transition_entry(
    repo_root: Path,
    *,
    entry_id: str,
    from_state: str,
    to_state: str,
    reason: str,
    actor: str,
    evidence_ids: list[str] | tuple[str, ...] = (),
    provenance_ids: list[str] | tuple[str, ...] = (),
    evidence_grade: str = "weak",
    target_id: str = "",
    retrieval_eligible: bool = False,
    reopen_condition: Mapping[str, Any] | None = None,
    evidence_fingerprint: str = "",
    decision_deadline: str = "",
    event_type: str = "candidate-transition",
    decision_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return commit_lifecycle_event(
        repo_root,
        build_entry_transition_event(
            entry_id=entry_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            actor=actor,
            evidence_ids=evidence_ids,
            provenance_ids=provenance_ids,
            evidence_grade=evidence_grade,
            target_id=target_id,
            retrieval_eligible=retrieval_eligible,
            reopen_condition=reopen_condition,
            evidence_fingerprint=evidence_fingerprint,
            decision_deadline=decision_deadline,
            event_type=event_type,
            decision_receipt=decision_receipt,
        ),
    )


def current_entry_lifecycle(repo_root: Path, entry_id: str) -> dict[str, Any]:
    state = load_lifecycle_state(repo_root)
    value = state.get("entries", {}).get(str(entry_id), {})
    return dict(value) if isinstance(value, Mapping) else {}


def effective_entry_status(
    repo_root: Path,
    data: Mapping[str, Any],
    *,
    lifecycle_state: Mapping[str, Any] | None = None,
) -> str:
    entry_id = str(data.get("id") or "").strip()
    if lifecycle_state is not None and entry_id:
        candidate = lifecycle_state.get("entries", {}).get(entry_id, {})
        lifecycle = dict(candidate) if isinstance(candidate, Mapping) else {}
    else:
        lifecycle = current_entry_lifecycle(repo_root, entry_id) if entry_id else {}
    return str(lifecycle.get("status") or data.get("status") or "candidate").strip().lower()


def entry_is_retrieval_eligible(
    repo_root: Path,
    data: Mapping[str, Any],
    *,
    scope: str = "",
    lifecycle_state: Mapping[str, Any] | None = None,
) -> bool:
    del scope
    entry_id = str(data.get("id") or "").strip()
    if not entry_id:
        return False
    if lifecycle_state is not None:
        candidate = lifecycle_state.get("entries", {}).get(entry_id, {})
        lifecycle = dict(candidate) if isinstance(candidate, Mapping) else {}
    else:
        lifecycle = current_entry_lifecycle(repo_root, entry_id)
    status = str(lifecycle.get("status") or data.get("status") or "candidate").strip().lower()
    if status in TERMINAL_ENTRY_STATES:
        return False
    if status == "trusted":
        return not bool(lifecycle.get("suspended"))
    if status == "candidate":
        explicit = lifecycle.get("retrieval_eligible")
        if explicit is None:
            explicit = data.get("retrieval_eligible", False)
        return bool(explicit)
    return False


def _load_sleep_state(repo_root: Path) -> dict[str, Any]:
    path = sleep_state_path(repo_root)
    if not path.exists():
        return {
            "schema_version": SLEEP_POLICY_VERSION,
            "committed_watermark": 0,
            "last_receipt_id": "",
            "last_input_digest": "",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema_version": SLEEP_POLICY_VERSION,
            "committed_watermark": 0,
            "last_receipt_id": "",
            "last_input_digest": "",
            "read_error": True,
        }
    return payload if isinstance(payload, dict) else {}


def _history_rows(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = history_events_path(repo_root)
    if not path.exists():
        return [], []
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            text = raw_line.strip()
            if not text:
                rows.append({"_line_number": line_number, "_blank": True})
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: {exc}")
                rows.append({"_line_number": line_number, "_malformed": True})
                continue
            if not isinstance(payload, dict):
                errors.append(f"line {line_number}: expected object")
                rows.append({"_line_number": line_number, "_malformed": True})
                continue
            payload["_line_number"] = line_number
            rows.append(payload)
    return rows, errors


def _run_incremental_sleep_locked(
    repo_root: Path,
    *,
    run_id: str,
    max_observations: int = 250,
    lane_lock: Mapping[str, Any],
) -> dict[str, Any]:
    from local_kb.active_index import (
        active_index_path,
        load_active_index,
        rebuild_active_index,
        validate_active_index,
    )
    from local_kb.model_maintenance import publish_sleep_model_generation

    clean_run_id = str(run_id)
    prior_sleep = _load_sleep_state(repo_root)
    input_watermark = int(prior_sleep.get("committed_watermark") or 0)
    rows, parse_errors = _history_rows(repo_root)
    known_history_event_ids = {
        str(row.get("event_id") or "")
        for row in rows
        if str(row.get("event_id") or "")
    }
    lifecycle_before = load_lifecycle_state(repo_root)
    observations_before = lifecycle_before.get("observations", {})
    opening_backlog = sum(
        1
        for item in observations_before.values()
        if isinstance(item, Mapping) and str(item.get("state") or "") in {"new", "missing-admission"}
    )
    dispositions: list[str] = []
    newly_admitted = 0
    processed_observations = 0
    output_watermark = input_watermark
    blockers = list(parse_errors)
    handoff_acknowledgements: list[str] = []
    candidate_created = 0
    candidate_reused = 0
    already_terminal_skipped = 0
    handled_observation_ids: set[str] = set()
    lifecycle_batch_events: list[dict[str, Any]] = []
    batch_disposition_keys: list[str] = []
    staged_model_upserts: dict[str, dict[str, Any]] = {}
    deferred_candidate_history: list[dict[str, Any]] = []
    deferred_handoff_acknowledgements: list[dict[str, str]] = []
    candidate_catalog_entries: list[Any] | None = None

    def get_candidate_catalog_entries() -> list[Any]:
        nonlocal candidate_catalog_entries
        if candidate_catalog_entries is None:
            from local_kb.model_maintenance import load_current_model_entries

            candidate_catalog_entries, _generation = load_current_model_entries(
                repo_root
            )
        return candidate_catalog_entries

    from local_kb.history import build_history_event, record_history_event

    for handoff in pending_dream_handoffs(repo_root):
        if processed_observations >= max(0, max_observations):
            break
        handoff_id = str(handoff.get("handoff_id") or "")
        observation_id = f"dream-handoff-observation:{handoff_id}"
        route_ref = str(handoff.get("route_ref") or "")
        requested = str(handoff.get("requested_disposition") or "history_only")
        suggested_action = "update-card" if requested == "update-card" else (
            "new-candidate" if requested == "candidate" else "none"
        )
        result_digest = str(handoff.get("result_digest") or "")
        observation = build_history_event(
            "observation",
            event_id=observation_id,
            source={
                "kind": "dream-result",
                "agent": "kb-dreamer",
                "run_id": str(handoff.get("run_id") or ""),
            },
            target={
                "kind": "task-observation",
                "task_summary": f"Dream evidence handoff for {route_ref or 'unscoped route'}",
                "route_hint": [item for item in route_ref.split("/") if item],
                "entry_ids": list(handoff.get("entry_ids") or []),
            },
            rationale="Sleep consumed a typed Dream evidence handoff.",
            context={
                "suggested_action": suggested_action,
                "outcome": str(handoff.get("classification") or ""),
                "predictive_observation": {
                    "scenario": str(handoff.get("hypothesis") or "Dream found a bounded knowledge gap."),
                    "action_taken": "Sleep reviewed the typed Dream experiment result.",
                    "observed_result": str(handoff.get("result_summary") or result_digest),
                    "operational_use": "Use only through the evidence-gated Sleep lifecycle.",
                    "reuse_judgment": "Reopen only after a decision-relevant evidence delta.",
                },
                "dream_handoff": dict(handoff),
            },
        )
        if observation_id not in known_history_event_ids:
            record_history_event(repo_root, observation)
            known_history_event_ids.add(observation_id)
        selected = classify_observation(observation)
        if selected.get("disposition") == "candidate":
            from local_kb.candidate_lifecycle import create_or_reuse_candidate

            candidate = create_or_reuse_candidate(
                repo_root,
                observation,
                run_id=clean_run_id,
                evidence_grade=str(selected.get("evidence_grade") or "weak"),
                staged_upserts=staged_model_upserts,
                deferred_history_events=deferred_candidate_history,
                catalog_entries=get_candidate_catalog_entries(),
            )
            selected.update(
                {
                    "target_id": candidate["entry_id"],
                    "follow_up_id": candidate["entry_id"],
                    "follow_up_deadline": candidate["decision_deadline"],
                }
            )
            candidate_created += int(bool(candidate.get("created")))
            candidate_reused += int(not bool(candidate.get("created")))
        current = observations_before.get(observation_id, {})
        current_state = (
            str(current.get("state") or "")
            if isinstance(current, Mapping)
            else ""
        )
        if not isinstance(current, Mapping) or current_state in {"", "missing-admission"}:
            lifecycle_batch_events.append(
                build_observation_admission_event(observation)
            )
        disposition_event = build_observation_disposition_event(
            observation,
            run_id=clean_run_id,
            decision=selected,
        )
        disposition_key = str(disposition_event.get("idempotency_key") or "")
        lifecycle_batch_events.append(disposition_event)
        batch_disposition_keys.append(disposition_key)
        handled_observation_ids.add(observation_id)
        deferred_handoff_acknowledgements.append(
            {
                "handoff_id": handoff_id,
                "disposition_key": disposition_key,
            }
        )
        processed_observations += 1

    for observation_id, item in sorted(observations_before.items()):
        if processed_observations >= max(0, max_observations):
            break
        if not isinstance(item, Mapping) or str(item.get("state") or "") not in ACTIONABLE_OBSERVATION_STATES:
            continue
        source_event = item.get("source_event", {}) if isinstance(item.get("source_event"), Mapping) else {}
        if not source_event:
            blockers.append(f"admitted observation {observation_id} lacks source_event")
            continue
        selected = classify_observation(source_event)
        if selected.get("disposition") == "candidate":
            from local_kb.candidate_lifecycle import create_or_reuse_candidate

            candidate = create_or_reuse_candidate(
                repo_root,
                source_event,
                run_id=clean_run_id,
                evidence_grade=str(selected.get("evidence_grade") or "weak"),
                staged_upserts=staged_model_upserts,
                deferred_history_events=deferred_candidate_history,
                catalog_entries=get_candidate_catalog_entries(),
            )
            selected.update(
                {
                    "target_id": candidate["entry_id"],
                    "follow_up_id": candidate["entry_id"],
                    "follow_up_deadline": candidate["decision_deadline"],
                }
            )
            candidate_created += int(bool(candidate.get("created")))
            candidate_reused += int(not bool(candidate.get("created")))
        state = str(item.get("state") or "")
        if state in {"", "missing-admission"}:
            lifecycle_batch_events.append(
                build_observation_admission_event(source_event)
            )
        disposition_event = build_observation_disposition_event(
            source_event,
            run_id=clean_run_id,
            decision=selected,
        )
        lifecycle_batch_events.append(disposition_event)
        batch_disposition_keys.append(
            str(disposition_event.get("idempotency_key") or "")
        )
        handled_observation_ids.add(observation_id)
        processed_observations += 1

    for row_index in range(input_watermark, len(rows)):
        row = rows[row_index]
        if row.get("_malformed"):
            blockers.append(f"history input is malformed at line {row.get('_line_number')}")
            break
        if str(row.get("event_type") or "").lower() == "observation":
            observation_id = str(row.get("event_id") or "").strip()
            current = observations_before.get(observation_id, {})
            current_state = (
                str(current.get("state") or "")
                if isinstance(current, Mapping)
                else ""
            )
            if observation_id in handled_observation_ids:
                output_watermark = row_index + 1
                continue
            if isinstance(current, Mapping) and current_state not in ACTIONABLE_OBSERVATION_STATES:
                already_terminal_skipped += 1
                output_watermark = row_index + 1
                continue
            if processed_observations >= max(0, max_observations):
                break
            selected = classify_observation(row)
            if selected.get("disposition") == "candidate":
                from local_kb.candidate_lifecycle import create_or_reuse_candidate

                candidate = create_or_reuse_candidate(
                    repo_root,
                    row,
                    run_id=clean_run_id,
                    evidence_grade=str(selected.get("evidence_grade") or "weak"),
                    staged_upserts=staged_model_upserts,
                    deferred_history_events=deferred_candidate_history,
                    catalog_entries=get_candidate_catalog_entries(),
                )
                selected.update(
                    {
                        "target_id": candidate["entry_id"],
                        "follow_up_id": candidate["entry_id"],
                        "follow_up_deadline": candidate["decision_deadline"],
                    }
                )
                candidate_created += int(bool(candidate.get("created")))
                candidate_reused += int(not bool(candidate.get("created")))
            if not isinstance(current, Mapping) or current_state in {"", "missing-admission"}:
                lifecycle_batch_events.append(
                    build_observation_admission_event(row)
                )
            disposition_event = build_observation_disposition_event(
                row,
                run_id=clean_run_id,
                decision=selected,
            )
            lifecycle_batch_events.append(disposition_event)
            batch_disposition_keys.append(
                str(disposition_event.get("idempotency_key") or "")
            )
            handled_observation_ids.add(observation_id)
            processed_observations += 1
        output_watermark = row_index + 1

    lifecycle_batch = {
        "requested_count": 0,
        "created_count": 0,
        "reused_count": 0,
        "replay_pass_count": 0,
        "atomic_batch_count": 0,
    }
    if lifecycle_batch_events:
        committed_batch = commit_lifecycle_events(
            repo_root,
            lifecycle_batch_events,
        )
        lifecycle_batch = {
            key: int(committed_batch.get(key) or 0)
            for key in (
                "requested_count",
                "created_count",
                "reused_count",
                "replay_pass_count",
                "atomic_batch_count",
            )
        }
        created_events = committed_batch.get("events", [])
        newly_admitted += sum(
            1
            for event in created_events
            if isinstance(event, Mapping)
            and str(event.get("event_type") or "") == "observation-admitted"
        )
        disposition_ids_by_key = {
            str(event.get("idempotency_key") or ""): str(
                event.get("lifecycle_event_id") or ""
            )
            for event in created_events
            if isinstance(event, Mapping)
            and str(event.get("event_type") or "") == "observation-disposition"
        }
        dispositions.extend(
            disposition_ids_by_key.get(key) or key
            for key in batch_disposition_keys
            if key
        )
        for pending_ack in deferred_handoff_acknowledgements:
            disposition_key = str(pending_ack.get("disposition_key") or "")
            pending_ack["disposition_id"] = (
                disposition_ids_by_key.get(disposition_key)
                or disposition_key
            )

    model_generation = publish_sleep_model_generation(
        repo_root,
        reason=f"sleep:{clean_run_id}",
        card_upserts=staged_model_upserts,
        refresh_index_on_no_delta=False,
        validate_index_on_no_delta=False,
        include_runtime_catalog=True,
    )
    runtime_catalog_entries = model_generation.pop(
        "_runtime_catalog_entries",
        None,
    )
    if not model_generation.get("ok"):
        blockers.append(
            "model generation: "
            + str(model_generation.get("error") or model_generation.get("status"))
        )
    else:
        for history_event in deferred_candidate_history:
            record_history_event(repo_root, history_event)
        for pending_ack in deferred_handoff_acknowledgements:
            acknowledgement = acknowledge_dream_handoff(
                repo_root,
                handoff_id=str(pending_ack.get("handoff_id") or ""),
                disposition_id=str(pending_ack.get("disposition_id") or ""),
                run_id=clean_run_id,
            )
            handoff_acknowledgements.append(
                str(acknowledgement.get("ack_id") or "")
            )

    from local_kb.candidate_lifecycle import review_entry_lifecycles

    lifecycle_review = review_entry_lifecycles(
        repo_root,
        run_id=clean_run_id,
        catalog_entries=runtime_catalog_entries,
    )
    lifecycle_review_issues = [
        str(item)
        for item in lifecycle_review.get("issues", [])
        if str(item).strip()
    ]
    blockers.extend(
        f"lifecycle review: {item}" for item in lifecycle_review_issues
    )
    index_refresh: dict[str, Any] = {}
    if model_generation.get("ok"):
        initial_receipt = (
            model_generation.get("receipt", {})
            if isinstance(model_generation.get("receipt"), Mapping)
            else {}
        )
        initial_validation = (
            initial_receipt.get("index_validation", {})
            if isinstance(initial_receipt.get("index_validation"), Mapping)
            else model_generation.get("index_validation", {})
        )
        initial_index_receipt = (
            initial_receipt.get("index_receipt", {})
            if isinstance(initial_receipt.get("index_receipt"), Mapping)
            else model_generation.get("index_receipt", {})
        )
        index_affecting_review = int(lifecycle_review.get("decision_count") or 0) > 0
        initial_committed_generation_is_final = bool(
            model_generation.get("status") == "committed"
            and initial_validation.get("ok")
            and not initial_validation.get("deferred")
            and not index_affecting_review
        )
        initial_no_delta_generation_is_final = bool(
            model_generation.get("status") == "no_delta"
            and not index_affecting_review
        )
        if initial_committed_generation_is_final:
            index_refresh = {
                "ok": True,
                "status": "reused_current",
                "idempotent_no_delta": True,
                "index_receipt": dict(initial_index_receipt),
                "index_validation": dict(initial_validation),
                "reuse_ticket": {
                    "source": "initial-model-generation",
                    "reason": "no index-affecting lifecycle decision followed publication",
                },
            }
        elif initial_no_delta_generation_is_final:
            current_validation = validate_active_index(repo_root)
            if current_validation.get("ok"):
                current_index = load_active_index(repo_root)
                current_receipt = {
                    "ok": True,
                    "receipt_id": str(current_index.get("receipt_id") or ""),
                    "path": str(active_index_path(repo_root)),
                    "generation": int(current_index.get("generation") or 0),
                    "content_digest": str(current_index.get("content_digest") or ""),
                    "indexed_record_count": int(current_index.get("indexed_record_count") or 0),
                    "excluded_status_counts": dict(current_index.get("excluded_status_counts") or {}),
                }
                index_refresh = {
                    "ok": True,
                    "status": "reused_current",
                    "idempotent_no_delta": True,
                    "index_receipt": current_receipt,
                    "index_validation": current_validation,
                    "reuse_ticket": {
                        "source": "current-no-delta-generation",
                        "reason": "the model and retrieval-affecting lifecycle projection are unchanged",
                    },
                }
            else:
                rebuilt_receipt = rebuild_active_index(
                    repo_root,
                    reason=f"sleep:{clean_run_id}:final-no-delta-index-owner",
                )
                rebuilt_validation = validate_active_index(repo_root)
                index_refresh = {
                    "ok": bool(rebuilt_receipt.get("ok") and rebuilt_validation.get("ok")),
                    "status": "rebuilt_current_authority",
                    "idempotent_no_delta": True,
                    "index_receipt": rebuilt_receipt,
                    "index_validation": rebuilt_validation,
                    "prior_validation": current_validation,
                }
                if not index_refresh.get("ok"):
                    blockers.append(
                        "final no-delta index owner: "
                        + "; ".join(
                            str(item)
                            for item in rebuilt_validation.get("issues", [])
                        )
                    )
        else:
            index_refresh = publish_sleep_model_generation(
                repo_root,
                reason=f"sleep:{clean_run_id}:post-lifecycle-review",
            )
            if not index_refresh.get("ok"):
                blockers.append(
                    "post-review index refresh: "
                    + str(index_refresh.get("error") or index_refresh.get("status"))
                )
    index_receipt = (
        index_refresh.get("index_receipt", {})
        if isinstance(index_refresh.get("index_receipt"), Mapping)
        else {}
    )
    index_validation = (
        index_refresh.get("index_validation", {})
        if isinstance(index_refresh.get("index_validation"), Mapping)
        else {}
    )
    if not index_validation or index_validation.get("deferred"):
        index_validation = validate_active_index(repo_root)
    if not index_validation.get("ok"):
        blockers.extend(str(item) for item in index_validation.get("issues", []))
    lifecycle_after = load_lifecycle_state(repo_root)
    observations_after = lifecycle_after.get("observations", {})
    closing_backlog = sum(
        1
        for item in observations_after.values()
        if isinstance(item, Mapping) and str(item.get("state") or "") in {"new", "missing-admission"}
    )
    terminally_disposed = sum(
        1
        for item in observations_after.values()
        if isinstance(item, Mapping) and str(item.get("state") or "") in {"represented", "candidate", "history_only", "rejected"}
    ) - sum(
        1
        for item in observations_before.values()
        if isinstance(item, Mapping) and str(item.get("state") or "") in {"represented", "candidate", "history_only", "rejected"}
    )
    explicitly_parked = sum(
        1
        for item in observations_after.values()
        if isinstance(item, Mapping) and str(item.get("state") or "") == "parked"
    ) - sum(
        1
        for item in observations_before.values()
        if isinstance(item, Mapping) and str(item.get("state") or "") == "parked"
    )
    input_slice = rows[input_watermark:output_watermark]
    receipt_id = f"sleep-receipt:{content_fingerprint([clean_run_id, input_watermark, output_watermark, lifecycle_after.get('event_digest')])[:24]}"
    final_state = "completed" if not blockers else "blocked"
    receipt = {
        "schema_version": SLEEP_POLICY_VERSION,
        "receipt_id": receipt_id,
        "run_id": clean_run_id,
        "created_at": utc_now_iso(),
        "input_generation": content_fingerprint(rows),
        "input_watermark": input_watermark,
        "output_watermark": output_watermark if not blockers else input_watermark,
        "consumed_range": {"inclusive_start": input_watermark, "exclusive_end": output_watermark},
        "consumed_digest": content_fingerprint(input_slice),
        "opening_actionable_backlog": opening_backlog,
        "newly_admitted": newly_admitted,
        "processed_observations": processed_observations,
        "already_terminal_skipped": already_terminal_skipped,
        "lifecycle_batch": lifecycle_batch,
        "terminally_disposed": max(0, terminally_disposed),
        "explicitly_parked": max(0, explicitly_parked),
        "closing_actionable_backlog": closing_backlog,
        "backlog_delta": closing_backlog - (opening_backlog + newly_admitted),
        "disposition_ids": [item for item in dispositions if item],
        "handoff_acknowledgements": [item for item in handoff_acknowledgements if item],
        "candidate_created": candidate_created,
        "candidate_reused": candidate_reused,
        "lifecycle_review": lifecycle_review,
        "model_generation": model_generation,
        "post_review_index_refresh": index_refresh,
        "model_diagnostics": (
            model_generation.get("receipt", {}).get("model_diagnostics", {})
            if model_generation.get("status") == "committed"
            else model_generation.get("model_diagnostics", {})
        ),
        "index_receipt_id": str(index_receipt.get("receipt_id") or ""),
        "index_validation": index_validation,
        "blockers": blockers,
        "policy_version": SLEEP_POLICY_VERSION,
        "input_digest": content_fingerprint(input_slice),
        "final_run_state": final_state,
        "lane_lock": dict(lane_lock),
        "lock_release": {
            "ok": False,
            "group": str(lane_lock.get("group") or "local-maintenance"),
            "lane": "kb-sleep",
            "run_id": clean_run_id,
            "released": False,
            "reason": "pending-native-receipt-finalization",
        },
    }
    receipt_path = sleep_receipt_dir(repo_root) / f"{clean_run_id}.json"
    _atomic_write_json(receipt_path, receipt)
    if not blockers:
        _atomic_write_json(
            sleep_state_path(repo_root),
            {
                "schema_version": SLEEP_POLICY_VERSION,
                "committed_watermark": output_watermark,
                "last_receipt_id": receipt_id,
                "last_receipt_path": str(receipt_path.relative_to(repo_root)).replace("\\", "/"),
                "last_input_digest": receipt["input_digest"],
                "updated_at": receipt["created_at"],
            },
        )
    return {**receipt, "receipt_path": str(receipt_path)}


def _sleep_retryable_receipt(
    repo_root: Path,
    *,
    run_id: str,
    input_watermark: int,
    lane_lock: Mapping[str, Any],
    lock_release: Mapping[str, Any],
    reason: str,
    error: str = "",
) -> dict[str, Any]:
    """Persist one bounded non-success receipt without advancing Sleep state."""

    empty_digest = content_fingerprint([])
    blockers = [reason]
    if error:
        blockers.append(error)
    receipt = {
        "schema_version": SLEEP_POLICY_VERSION,
        "receipt_id": (
            "sleep-receipt:"
            + content_fingerprint([run_id, input_watermark, reason, error])[:24]
        ),
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "input_generation": "",
        "input_watermark": input_watermark,
        "output_watermark": input_watermark,
        "consumed_range": {
            "inclusive_start": input_watermark,
            "exclusive_end": input_watermark,
        },
        "consumed_digest": empty_digest,
        "opening_actionable_backlog": 0,
        "newly_admitted": 0,
        "terminally_disposed": 0,
        "explicitly_parked": 0,
        "closing_actionable_backlog": 0,
        "backlog_delta": 0,
        "disposition_ids": [],
        "handoff_acknowledgements": [],
        "candidate_created": 0,
        "candidate_reused": 0,
        "lifecycle_review": {
            "issues": [reason],
            "reviewed": 0,
            "promoted": 0,
            "downgraded": 0,
            "reopened": 0,
            "parked": 0,
            "decision_count": 0,
            "decision_ids": [],
            "due_remaining": 0,
            "projection_validation": {"ok": False, "issues": [reason]},
        },
        "index_receipt_id": "",
        "index_validation": {"ok": False, "issues": [reason]},
        "blockers": blockers,
        "policy_version": SLEEP_POLICY_VERSION,
        "input_digest": empty_digest,
        "final_run_state": "retryable" if reason == "maintenance-lane-active" else "blocked",
        "retryable": reason == "maintenance-lane-active",
        "reason": reason,
        "terminal_gate": {
            "gate_id": "shared-maintenance-lane",
            "evaluated": True,
            "applicable": False,
            "reason": reason,
        },
        "lane_lock": dict(lane_lock),
        "lock_release": dict(lock_release),
    }
    receipt_path = sleep_receipt_dir(repo_root) / f"{run_id}.json"
    _atomic_write_json(receipt_path, receipt)
    return {**receipt, "receipt_path": str(receipt_path)}


def run_incremental_sleep(
    repo_root: Path,
    *,
    run_id: str | None = None,
    max_observations: int = 250,
) -> dict[str, Any]:
    """Run one Sleep mutation while owning the shared local-maintenance lane."""

    repo_root = Path(repo_root)
    clean_run_id = str(
        run_id or f"kb-sleep-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    state_path = sleep_state_path(repo_root)
    prior_state_exists = state_path.is_file()
    prior_sleep = _load_sleep_state(repo_root)
    input_watermark = int(prior_sleep.get("committed_watermark") or 0)
    lane_lock = acquire_lane_lock(
        repo_root,
        "kb-sleep",
        run_id=clean_run_id,
        wait=False,
        note="incremental Sleep lifecycle mutation",
    )
    if lane_lock.get("acquired") is not True:
        return _sleep_retryable_receipt(
            repo_root,
            run_id=clean_run_id,
            input_watermark=input_watermark,
            lane_lock=lane_lock,
            lock_release={
                "ok": False,
                "group": str(lane_lock.get("group") or "local-maintenance"),
                "lane": "kb-sleep",
                "run_id": clean_run_id,
                "released": False,
                "reason": "not-acquired",
            },
            reason="maintenance-lane-active",
        )

    recovered_lock = (
        lane_lock.get("recovered_lock", {})
        if isinstance(lane_lock.get("recovered_lock"), Mapping)
        else {}
    )
    recovered_run_id = str(recovered_lock.get("run_id") or "")
    if recovered_run_id:
        lane_lock["dream_handoff_ack_recovery"] = (
            rollback_uncommitted_dream_handoff_acknowledgements(
                repo_root,
                run_id=recovered_run_id,
            )
        )

    receipt: dict[str, Any]
    try:
        receipt = _run_incremental_sleep_locked(
            repo_root,
            run_id=clean_run_id,
            max_observations=max_observations,
            lane_lock=lane_lock,
        )
    except Exception as exc:
        lock_release = release_lane_lock(
            repo_root,
            "kb-sleep",
            run_id=clean_run_id,
        )
        if prior_state_exists:
            _atomic_write_json(state_path, prior_sleep)
        elif state_path.exists():
            state_path.unlink()
        return _sleep_retryable_receipt(
            repo_root,
            run_id=clean_run_id,
            input_watermark=input_watermark,
            lane_lock=lane_lock,
            lock_release=lock_release,
            reason="sleep-native-exception",
            error=f"{type(exc).__name__}: {exc}",
        )

    lock_release = release_lane_lock(
        repo_root,
        "kb-sleep",
        run_id=clean_run_id,
    )
    receipt["lock_release"] = lock_release
    receipt_path = Path(str(receipt["receipt_path"]))
    receipt_body = {key: value for key, value in receipt.items() if key != "receipt_path"}
    if lock_release.get("ok") is not True or lock_release.get("released") is not True:
        receipt_body["blockers"] = [
            *[str(item) for item in receipt_body.get("blockers", [])],
            "shared Sleep lane release failed",
        ]
        receipt_body["final_run_state"] = "blocked"
        receipt_body["output_watermark"] = input_watermark
        if prior_state_exists:
            _atomic_write_json(state_path, prior_sleep)
        elif state_path.exists():
            state_path.unlink()
    _atomic_write_json(receipt_path, receipt_body)
    return {**receipt_body, "receipt_path": str(receipt_path)}


def record_retrieval_receipt(
    repo_root: Path,
    *,
    query: str,
    path_hint: str,
    index_generation: int,
    index_digest: str,
    ranked_entries: list[Mapping[str, Any]],
    thresholds: Mapping[str, Any],
    request_id: str | None = None,
) -> dict[str, Any]:
    normalized = {
        "query": str(query),
        "path_hint": str(path_hint),
        "index_generation": int(index_generation),
        "index_digest": str(index_digest),
        "returned": [
            {
                "entry_id": str(item.get("entry_id") or item.get("id") or ""),
                "rank": int(item.get("rank") or index + 1),
                "score": float(item.get("score") or 0.0),
                "status": str(item.get("status") or ""),
                "logicguard_binding": dict(item.get("logicguard_binding") or {}),
                "materialization_fingerprint": str(
                    item.get("materialization_fingerprint") or ""
                ),
                "logicguard_ranking": dict(
                    item.get("logicguard_ranking") or {}
                ),
            }
            for index, item in enumerate(ranked_entries)
        ],
        "thresholds": dict(thresholds),
    }
    stable_request_id = request_id or f"retrieval:{uuid4()}"
    receipt = {
        "schema_version": 1,
        "request_id": stable_request_id,
        "created_at": utc_now_iso(),
        "query_context_fingerprint": content_fingerprint([query, path_hint]),
        "route_hints": [segment for segment in str(path_hint).replace("\\", "/").split("/") if segment],
        "index_generation": int(index_generation),
        "index_digest": str(index_digest),
        "policy_version": int(thresholds.get("policy_version") or 2),
        "returned_entries": normalized["returned"],
        "used_entry_ids": [],
        "no_card": not bool(normalized["returned"]),
        "abstention_reason": "no eligible entry exceeded the relevance threshold" if not normalized["returned"] else "",
        "thresholds": dict(thresholds),
        "receipt_digest": content_fingerprint(normalized),
    }
    _append_jsonl_durable(retrieval_receipts_path(repo_root), receipt)
    return receipt


def record_outcome_receipt(
    repo_root: Path,
    *,
    request_id: str,
    used_entry_ids: list[str] | tuple[str, ...],
    outcome: str,
    evidence_kind: str,
    evidence_ref: str = "",
    verified: bool = False,
    user_correction: bool = False,
) -> dict[str, Any]:
    retrieval_receipt = next(
        (
            item
            for item in reversed(_read_jsonl(retrieval_receipts_path(repo_root)))
            if str(item.get("request_id") or "") == str(request_id)
        ),
        None,
    )
    if retrieval_receipt is None:
        raise ValueError(f"Unknown retrieval request_id: {request_id}")
    returned_ids = {
        str(item.get("entry_id") or "")
        for item in retrieval_receipt.get("returned_entries", [])
        if isinstance(item, Mapping) and str(item.get("entry_id") or "")
    }
    normalized_used_ids = sorted({str(item) for item in used_entry_ids if str(item)})
    unknown_used = sorted(set(normalized_used_ids) - returned_ids)
    if unknown_used:
        raise ValueError(
            "Outcome used_entry_ids were not returned by the retrieval request: "
            + ", ".join(unknown_used)
        )
    if verified and not str(evidence_ref or "").strip():
        raise ValueError("Verified outcomes require a concrete evidence_ref")
    classification = str(outcome or "unknown").strip().lower() or "unknown"
    if classification not in {"success", "failure", "misleading", "rework", "unknown", "no-card-success"}:
        classification = "unknown"
    grade = "strong" if verified or user_correction else "weak"
    if evidence_kind == "dream" and grade == "weak":
        grade = "medium"
    idempotency_key = content_fingerprint(
        {
            "request_id": str(request_id),
            "used_entry_ids": normalized_used_ids,
            "outcome": classification,
            "evidence_kind": str(evidence_kind),
            "evidence_ref": str(evidence_ref),
            "verified": bool(verified),
            "user_correction": bool(user_correction),
        }
    )
    for existing in reversed(_read_jsonl(outcome_receipts_path(repo_root))):
        if str(existing.get("idempotency_key") or "") == idempotency_key:
            return {**existing, "created": False, "idempotent_reuse": True}
    receipt = {
        "schema_version": 1,
        "outcome_id": f"outcome:{uuid4()}",
        "idempotency_key": idempotency_key,
        "created_at": utc_now_iso(),
        "request_id": str(request_id),
        "used_entry_ids": normalized_used_ids,
        "outcome": classification,
        "evidence_kind": str(evidence_kind),
        "evidence_ref": str(evidence_ref),
        "verified": bool(verified),
        "user_correction": bool(user_correction),
        "evidence_grade": grade,
        "policy_version": 1,
    }
    receipt["receipt_digest"] = content_fingerprint(receipt)
    _append_jsonl_durable(outcome_receipts_path(repo_root), receipt)
    # A verified failure or correction is safety-relevant.  Suspend a trusted
    # entry immediately; the next successful Sleep pass performs the complete
    # calibration review and rebuilds the active index.
    if classification in {"failure", "misleading", "rework"} and grade == "strong":
        lifecycle = load_lifecycle_state(repo_root, repair_projection=False)
        for entry_id in normalized_used_ids:
            entry_state = lifecycle.get("entries", {}).get(entry_id, {})
            if isinstance(entry_state, Mapping) and str(entry_state.get("status") or "") == "trusted":
                transition_entry(
                    repo_root,
                    entry_id=entry_id,
                    from_state="trusted",
                    to_state="parked",
                    reason="Verified contradictory task evidence immediately suspended trusted retrieval.",
                    actor="outcome-calibration",
                    evidence_ids=[str(receipt["outcome_id"])],
                    provenance_ids=[str(evidence_ref)],
                    evidence_grade="strong",
                    retrieval_eligible=False,
                    reopen_condition={
                        "kind": "resolving-independent-validation",
                        "minimum_grade": "strong",
                        "requires_new_fingerprint": True,
                    },
                    evidence_fingerprint=idempotency_key,
                    decision_receipt={"outcome_receipt": receipt},
                )
    return {**receipt, "created": True, "idempotent_reuse": False}


def record_dream_handoff(
    repo_root: Path,
    *,
    run_id: str,
    evidence_fingerprint: str,
    result_digest: str,
    route_ref: str,
    hypothesis: str,
    classification: str,
    result_summary: str,
    entry_ids: list[str] | tuple[str, ...] = (),
    requested_disposition: str = "history_only",
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    stable_key = content_fingerprint(
        [evidence_fingerprint, result_digest, requested_disposition]
    )
    handoff_id = f"dream-handoff:{stable_key[:24]}"
    with _lifecycle_lock(repo_root):
        rows = _read_jsonl(dream_handoffs_path(repo_root))
        for row in rows:
            if str(row.get("handoff_id") or "") == handoff_id:
                return {**row, "created": False, "idempotent_reuse": True}
        payload = {
            "schema_version": 1,
            "handoff_id": handoff_id,
            "idempotency_key": stable_key,
            "created_at": utc_now_iso(),
            "run_id": str(run_id),
            "evidence_fingerprint": str(evidence_fingerprint),
            "result_digest": str(result_digest),
            "route_ref": str(route_ref),
            "hypothesis": str(hypothesis),
            "classification": str(classification),
            "result_summary": str(result_summary),
            "entry_ids": sorted({str(item) for item in entry_ids if str(item)}),
            "requested_disposition": str(requested_disposition),
            "provenance": dict(provenance or {}),
        }
        _append_jsonl_durable(dream_handoffs_path(repo_root), payload)
        return {**payload, "created": True, "idempotent_reuse": False}


def pending_dream_handoffs(repo_root: Path) -> list[dict[str, Any]]:
    handoffs = _read_jsonl(dream_handoffs_path(repo_root))
    acknowledgements = _read_jsonl(dream_handoff_acks_path(repo_root))
    acknowledged = {
        str(item.get("handoff_id") or "")
        for item in acknowledgements
        if str(item.get("handoff_id") or "")
    }
    return [
        item
        for item in handoffs
        if str(item.get("handoff_id") or "") not in acknowledged
    ]


def rollback_uncommitted_dream_handoff_acknowledgements(
    repo_root: Path,
    *,
    run_id: str,
) -> dict[str, Any]:
    """Reopen handoffs acknowledged by a Sleep owner without a completed receipt.

    Candidate/model mutation is staged until model publication succeeds.  A
    terminated owner must therefore not leave an earlier acknowledgement as
    terminal evidence when its Sleep receipt is missing or non-completed.
    """

    clean_run_id = str(run_id or "").strip()
    if not clean_run_id:
        raise ValueError("Dream handoff acknowledgement rollback requires run_id")
    receipt_path = sleep_receipt_dir(repo_root) / f"{clean_run_id}.json"
    terminal_receipt: dict[str, Any] = {}
    if receipt_path.is_file():
        try:
            loaded = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Sleep receipt is unreadable during handoff recovery: {receipt_path}: {exc}"
            ) from exc
        if isinstance(loaded, dict):
            terminal_receipt = loaded
    if str(terminal_receipt.get("final_run_state") or "") == "completed":
        return {
            "ok": True,
            "run_id": clean_run_id,
            "status": "completed-receipt-preserved",
            "removed_count": 0,
            "receipt_path": str(receipt_path),
        }

    with _lifecycle_lock(repo_root):
        path = dream_handoff_acks_path(repo_root)
        rows = _read_jsonl(path)
        retained = [
            row
            for row in rows
            if str(row.get("run_id") or "") != clean_run_id
        ]
        removed = len(rows) - len(retained)
        if removed:
            _atomic_replace_jsonl(path, retained)
    return {
        "ok": True,
        "run_id": clean_run_id,
        "status": "uncommitted-acknowledgements-reopened",
        "removed_count": removed,
        "receipt_path": str(receipt_path),
        "receipt_present": receipt_path.is_file(),
        "prior_final_run_state": str(terminal_receipt.get("final_run_state") or ""),
    }


def acknowledge_dream_handoff(
    repo_root: Path,
    *,
    handoff_id: str,
    disposition_id: str,
    run_id: str,
) -> dict[str, Any]:
    ack_id = f"dream-ack:{content_fingerprint([handoff_id, disposition_id])[:24]}"
    with _lifecycle_lock(repo_root):
        rows = _read_jsonl(dream_handoff_acks_path(repo_root))
        for row in rows:
            if str(row.get("handoff_id") or "") == handoff_id:
                return {**row, "created": False, "idempotent_reuse": True}
        payload = {
            "schema_version": 1,
            "ack_id": ack_id,
            "handoff_id": str(handoff_id),
            "disposition_id": str(disposition_id),
            "run_id": str(run_id),
            "created_at": utc_now_iso(),
        }
        _append_jsonl_durable(dream_handoff_acks_path(repo_root), payload)
        return {**payload, "created": True, "idempotent_reuse": False}


def validate_lifecycle(repo_root: Path) -> dict[str, Any]:
    state = replay_lifecycle(repo_root)
    issues = list(state.get("validation", {}).get("issues", []))
    for observation_id, item in state.get("observations", {}).items():
        if str(item.get("state") or "") == "missing-admission":
            issues.append(f"observation {observation_id} has a disposition without admission")
        if str(item.get("state") or "") == "parked" and not item.get("reopen_condition"):
            issues.append(f"parked observation {observation_id} lacks reopen_condition")
    for entry_id, item in state.get("entries", {}).items():
        status = str(item.get("status") or "")
        if status in {"merged", "superseded"} and not str(item.get("target_id") or ""):
            issues.append(f"{status} entry {entry_id} lacks target_id")
        if status == "parked" and not item.get("reopen_condition"):
            issues.append(f"parked entry {entry_id} lacks reopen_condition")
    return {
        "ok": not issues,
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "event_count": state.get("event_count", 0),
        "event_digest": state.get("event_digest", ""),
        "observation_count": len(state.get("observations", {})),
        "entry_count": len(state.get("entries", {})),
        "issues": issues,
    }
