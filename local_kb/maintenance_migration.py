from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import threading
import time
from typing import Any, Iterable, Iterator, Mapping
from uuid import uuid4

from local_kb.active_index import rebuild_active_index, validate_active_index
from local_kb.common import normalize_string_list, utc_now_iso
from local_kb.lifecycle import (
    build_entry_transition_event,
    build_observation_admission_event,
    build_observation_disposition_event,
    classify_observation,
    commit_lifecycle_events,
    content_fingerprint,
    load_lifecycle_state,
    validate_lifecycle,
)
from local_kb.maintenance_standard import (
    CURRENT_HISTORY_SCHEMA_VERSION,
    CURRENT_MAINTENANCE_STANDARD_VERSION,
    load_maintenance_state,
    maintenance_state_path,
    write_maintenance_state,
)
from local_kb.maintenance_lanes import process_owner_is_alive
from local_kb.history import build_history_event, record_history_event
from local_kb.logicguard_models import (
    ExactBindingError,
    LogicGuardBinding,
    authority_generation_pointer_path,
    authority_root,
    build_authority_generation_payload,
    canonical_digest,
    commit_card_model,
    commit_scope_mesh,
    json_safe,
    load_authority_generation,
    researchguard_logic_dependency_preflight,
    mesh_id_for_scope,
    model_id_for_card,
    open_mesh_store,
    open_model_store,
    open_pinned_model_read_store,
    publish_authority_generation,
    reuse_card_model_if_exact,
)
from local_kb.model_projection import (
    CARD_PROJECTION_SCHEMA_VERSION,
    PROJECTION_BINDING_FIELDS,
    ProjectionValidationError,
    binding_from_projection,
    projection_digest,
    project_cards,
    validate_card_projections,
    write_card_projections_atomic,
)
from local_kb.store import history_events_path, load_yaml_file, write_yaml_file


MIGRATION_SCHEMA_VERSION = 1
MIGRATION_ID = "kb-maintenance-standard-v5-researchguard-logic-native"
MIGRATION_PHASES = (
    "preflight",
    "snapshot",
    "classify",
    "canonicalize-runtime",
    "settle-logical-debt",
    "migrate-logicguard-authority",
    "archive-cold-evidence",
    "prune-derived-data",
    "rebuild-index",
    "validate",
    "committed",
)
MIGRATION_ROOT = Path("kb") / "history" / "migrations" / MIGRATION_ID
COLD_ROOT = Path("kb") / "history" / "cold"
MIGRATION_LOCK_SCHEMA_VERSION = "khaos-brain.migration-lock.v1"
MIGRATION_LOCK_HEARTBEAT_SECONDS = 1.0
MIGRATION_LOCK_LEGACY_STALE_SECONDS = 30.0
MODEL_AUTHORITY_MIGRATION_SCHEMA = (
    "khaos-brain.researchguard-logic-authority-migration.v1"
)
MODEL_AUTHORITY_RECEIPT_NAME = "researchguard-logic-authority-receipt.json"
CURRENT_PROJECTION_BOOTSTRAP_DISPOSITION = "direct-current-projection-bootstrap"
RESEARCHGUARD_LOGIC_SCHEMA_CUTOVER_DISPOSITION = (
    "direct-current-projection-to-researchguard-logic-model"
)
INCOMPATIBLE_CURRENT_PROJECTION_DISPOSITION = (
    "blocked-upgrade-ai-current-projection-authority"
)
UPGRADE_AI_DISPOSITION_SCHEMA = "khaos-brain.upgrade-ai-dispositions.v1"
UPGRADE_AI_DIRECT_CURRENT_ACTION = (
    "direct-current-projection-to-logicguard-model"
)
LEGACY_LOGICGUARD_SCHEMA_PREFIX = b"logicguard.model-"
RESEARCHGUARD_LOGIC_SCHEMA_PREFIX = b"researchguard.logic.model-"
RESEARCHGUARD_LOGIC_MODEL_STORE_SCHEMA = (
    "researchguard.logic.model-store.v1"
)
RESEARCHGUARD_LOGIC_MODEL_MESH_SCHEMA = (
    "researchguard.logic.model-mesh.v1"
)

MANAGED_DIRECTORY_ROOTS = (
    Path("kb") / "history" / "consolidation",
    Path("kb") / "history" / "dream",
    Path("kb") / "history" / "architecture",
    Path(".local") / "architect",
    Path(".local") / "automation-results",
    Path(".local") / "maintenance-lab",
    Path(".local") / "qa",
    Path(".local") / "readme-organization-fixture",
    Path(".local") / "readme-screenshot-fixture",
)
MANAGED_EXACT_FILES = (
    Path("kb") / "history" / "lane-status" / "kb-architect.json",
    Path("kb") / "history" / "lane-status" / "architect.json",
)
MANAGED_LOCAL_PREVIEW_PREFIXES = (
    "khaos_brain_color_sandbox_",
    "ui-cover-title-",
    "ui-source-",
    "ui-typography-",
)
COLD_EVIDENCE_NAMES = {
    "report.json",
    "apply.json",
    "maintenance_rollup.json",
    "proposal_queue.json",
    "trial_result.json",
    "execution_plan.json",
    "experiments.json",
    "decisions.json",
}


def migration_root(repo_root: Path) -> Path:
    return Path(repo_root) / MIGRATION_ROOT


def journal_path(repo_root: Path) -> Path:
    return migration_root(repo_root) / "journal.json"


def inventory_path(repo_root: Path) -> Path:
    return migration_root(repo_root) / "inventory.jsonl"


def inventory_summary_path(repo_root: Path) -> Path:
    return migration_root(repo_root) / "inventory-summary.json"


def archive_manifest_path(repo_root: Path) -> Path:
    return migration_root(repo_root) / "archive-manifest.jsonl"


def prune_manifest_path(repo_root: Path) -> Path:
    return migration_root(repo_root) / "prune-manifest.jsonl"


def migration_receipt_path(repo_root: Path) -> Path:
    return migration_root(repo_root) / "receipt.json"


def reconciliation_state_path(repo_root: Path) -> Path:
    return migration_root(repo_root) / "reconciliation-state.json"


def reconciliation_root(repo_root: Path) -> Path:
    return migration_root(repo_root) / "reconciliations"


def logical_reconciliation_root(repo_root: Path) -> Path:
    return migration_root(repo_root) / "logical-reconciliations"


def rollback_root(repo_root: Path) -> Path:
    return Path(repo_root) / ".local" / "kbrb" / "v4"


def cold_object_root(repo_root: Path) -> Path:
    return Path(repo_root) / COLD_ROOT / "objects"


def cold_manifest_path(repo_root: Path) -> Path:
    return Path(repo_root) / COLD_ROOT / "manifest.jsonl"


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(f"Unsupported migration JSON value: {type(value).__name__}")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
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


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(_canonical_json(dict(payload)) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _strip_windows_extended_prefix(value: str) -> str:
    if value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[8:]
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def _normal_absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(_strip_windows_extended_prefix(str(path))))


def _fs_path(path: Path) -> Path:
    """Return an I/O-safe path, including Win32 extended-length syntax."""
    normal = str(_normal_absolute_path(Path(path)))
    if os.name != "nt" or normal.startswith("\\\\?\\"):
        return Path(normal)
    if normal.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + normal[2:])
    return Path("\\\\?\\" + normal)


def _fs_exists(path: Path) -> bool:
    return _fs_path(path).exists()


def _fs_is_file(path: Path) -> bool:
    return _fs_path(path).is_file()


def _fs_stat(path: Path) -> os.stat_result:
    return _fs_path(path).stat()


def _bounded_chunks(items: Iterable[Any], *, size: int = 256) -> Iterator[list[Any]]:
    chunk: list[Any] = []
    for item in items:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _filesystem_worker_count() -> int:
    return min(16, max(4, (os.cpu_count() or 2) * 2))


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with _fs_path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def authority_schema_inventory(repo_root: Path) -> dict[str, Any]:
    """Hash every authority artifact and count old/current schema identities.

    This is the version-owned upgrade inventory. Normal runtime does not use it
    as a compatibility reader.
    """

    root = Path(repo_root).resolve()
    target = authority_root(root)
    rows: list[tuple[str, int, str]] = []
    scopes: dict[str, dict[str, int]] = {}
    artifact_schema_counts: dict[str, int] = {}
    legacy_schema_file_count = 0
    legacy_schema_occurrence_count = 0
    current_schema_file_count = 0
    current_schema_occurrence_count = 0
    total_bytes = 0
    if target.is_dir():
        for path in sorted(item for item in target.rglob("*") if item.is_file()):
            relative = path.relative_to(target).as_posix()
            data = path.read_bytes()
            size = len(data)
            digest = hashlib.sha256(data).hexdigest()
            legacy_count = data.count(LEGACY_LOGICGUARD_SCHEMA_PREFIX)
            current_count = data.count(RESEARCHGUARD_LOGIC_SCHEMA_PREFIX)
            legacy_schema_file_count += int(legacy_count > 0)
            legacy_schema_occurrence_count += legacy_count
            current_schema_file_count += int(current_count > 0)
            current_schema_occurrence_count += current_count
            scope = relative.split("/", 1)[0] if "/" in relative else "<root>"
            scope_row = scopes.setdefault(scope, {"file_count": 0, "byte_count": 0})
            scope_row["file_count"] += 1
            scope_row["byte_count"] += size
            total_bytes += size
            if path.suffix.lower() == ".json":
                try:
                    payload = json.loads(data)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload = {}
                if isinstance(payload, Mapping):
                    artifact_schema = str(payload.get("artifact_schema") or "")
                    if artifact_schema:
                        artifact_schema_counts[artifact_schema] = (
                            artifact_schema_counts.get(artifact_schema, 0) + 1
                        )
            rows.append((relative, size, digest))
    inventory = hashlib.sha256()
    for relative, size, digest in rows:
        inventory.update(f"{relative}\0{size}\0{digest}\n".encode("utf-8"))
    return {
        "schema_version": "khaos-brain.authority-schema-inventory.v1",
        "authority_root": str(target),
        "file_count": len(rows),
        "byte_count": total_bytes,
        "inventory_digest": "sha256:" + inventory.hexdigest(),
        "scopes": scopes,
        "artifact_schema_counts": dict(sorted(artifact_schema_counts.items())),
        "legacy_schema_file_count": legacy_schema_file_count,
        "legacy_schema_occurrence_count": legacy_schema_occurrence_count,
        "current_schema_file_count": current_schema_file_count,
        "current_schema_occurrence_count": current_schema_occurrence_count,
        "cutover_required": legacy_schema_occurrence_count > 0,
        "mixed_schema": bool(
            legacy_schema_occurrence_count and current_schema_occurrence_count
        ),
    }


def _path_within(path: Path, parent: Path) -> bool:
    try:
        normalized_path = os.path.normcase(str(_normal_absolute_path(path)))
        normalized_parent = os.path.normcase(str(_normal_absolute_path(parent)))
        return os.path.commonpath((normalized_path, normalized_parent)) == normalized_parent
    except (ValueError, OSError):
        return False


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            text = raw_line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSONL at {path}:{line_number}: {exc}") from exc
            if isinstance(payload, dict):
                yield payload


def _migration_lock_owner_is_alive(pid: int) -> bool:
    return process_owner_is_alive(pid)


def _legacy_migration_process_is_running(repo_root: Path) -> bool:
    """Fail safely when an ownerless lock may still belong to an old runtime."""

    root = str(Path(repo_root).resolve())
    markers = ("migrate_kb_maintenance", "install_codex_kb")
    if os.name == "nt":
        executable = shutil.which("powershell") or shutil.which("pwsh")
        if not executable:
            return True
        environment = dict(os.environ)
        environment["KHAOS_MIGRATION_REPO_ROOT"] = root
        environment["KHAOS_MIGRATION_EXCLUDE_PID"] = str(os.getpid())
        script = (
            "$root=$env:KHAOS_MIGRATION_REPO_ROOT; "
            "$excluded=[int]$env:KHAOS_MIGRATION_EXCLUDE_PID; "
            "$rows=@(Get-CimInstance Win32_Process | Where-Object { "
            "$_.ProcessId -ne $excluded -and $_.Name -match '^python(\\.exe)?$' -and "
            "$_.CommandLine -like ('*' + $root + '*') -and "
            "($_.CommandLine -match 'migrate_kb_maintenance|install_codex_kb') }); "
            "[Console]::Out.Write($rows.Count)"
        )
        try:
            completed = subprocess.run(
                [executable, "-NoProfile", "-NonInteractive", "-Command", script],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=environment,
            )
            return completed.returncode != 0 or int(completed.stdout.strip() or "0") > 0
        except (OSError, subprocess.SubprocessError, ValueError):
            return True
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return True
    for command_path in proc_root.glob("[0-9]*/cmdline"):
        try:
            pid = int(command_path.parent.name)
            command = command_path.read_bytes().replace(b"\x00", b" ").decode(
                "utf-8", errors="replace"
            )
        except (OSError, ValueError):
            continue
        if pid != os.getpid() and root in command and any(marker in command for marker in markers):
            return True
    return False


def _write_migration_lock_owner(lock_dir: Path, payload: Mapping[str, Any]) -> bool:
    """Write inside an already-owned directory without ever recreating it."""

    if not lock_dir.is_dir():
        return False
    owner_path = lock_dir / "owner.json"
    temporary = lock_dir / f".owner.{uuid4().hex}.tmp"
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if not lock_dir.is_dir():
            return False
        os.replace(temporary, owner_path)
        return True
    except OSError:
        return False
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _recover_stale_migration_lock(repo_root: Path, lock_dir: Path) -> bool:
    """Atomically quarantine a provably dead V1 or old ownerless lock."""

    if not lock_dir.is_dir():
        return False
    now = time.time()
    owner = _load_json(lock_dir / "owner.json")
    reason = ""
    if owner.get("schema_version") == MIGRATION_LOCK_SCHEMA_VERSION:
        try:
            pid = int(owner.get("pid") or 0)
        except (TypeError, ValueError):
            pid = 0
        if _migration_lock_owner_is_alive(pid):
            return False
        reason = "recorded-owner-not-running"
    else:
        try:
            age_seconds = now - lock_dir.stat().st_mtime
        except OSError:
            return False
        if age_seconds < MIGRATION_LOCK_LEGACY_STALE_SECONDS:
            return False
        if _legacy_migration_process_is_running(repo_root):
            return False
        reason = "legacy-ownerless-lock-without-running-migration"
    quarantine = lock_dir.with_name(f".migration.lock.stale-{uuid4().hex}")
    try:
        os.replace(lock_dir, quarantine)
    except OSError:
        return False
    prior_owner = owner if owner else {}
    try:
        shutil.rmtree(quarantine)
    except OSError:
        # The live lock name is free, but keep failure visible and do not claim
        # cleanup of the quarantined diagnostics.
        pass
    _append_jsonl(
        migration_root(repo_root) / "lock-recovery.jsonl",
        {
            "schema_version": "khaos-brain.migration-lock-recovery.v1",
            "recovered_at": utc_now_iso(),
            "reason": reason,
            "prior_owner": prior_owner,
            "quarantine_removed": not quarantine.exists(),
        },
    )
    return True


@contextmanager
def migration_lock(repo_root: Path, *, timeout_seconds: float = 5.0) -> Iterator[None]:
    lock_dir = migration_root(repo_root) / ".migration.lock"
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    while True:
        try:
            lock_dir.mkdir()
            break
        except FileExistsError:
            if _recover_stale_migration_lock(repo_root, lock_dir):
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Maintenance migration is already running: {lock_dir}")
            time.sleep(0.05)
    owner_token = uuid4().hex
    acquired_at = utc_now_iso()
    owner: dict[str, Any] = {
        "schema_version": MIGRATION_LOCK_SCHEMA_VERSION,
        "owner_token": owner_token,
        "pid": os.getpid(),
        "acquired_at": acquired_at,
        "heartbeat_at": acquired_at,
        "heartbeat_epoch": time.time(),
    }
    if not _write_migration_lock_owner(lock_dir, owner):
        try:
            lock_dir.rmdir()
        except OSError:
            pass
        raise RuntimeError(f"Unable to publish maintenance migration lock owner: {lock_dir}")
    stop_heartbeat = threading.Event()

    def heartbeat() -> None:
        while not stop_heartbeat.wait(MIGRATION_LOCK_HEARTBEAT_SECONDS):
            current = _load_json(lock_dir / "owner.json")
            if current.get("owner_token") != owner_token:
                return
            refreshed = dict(owner)
            refreshed["heartbeat_at"] = utc_now_iso()
            refreshed["heartbeat_epoch"] = time.time()
            if not _write_migration_lock_owner(lock_dir, refreshed):
                return

    heartbeat_thread = threading.Thread(
        target=heartbeat,
        name="khaos-brain-migration-lock-heartbeat",
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        yield
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=max(1.0, MIGRATION_LOCK_HEARTBEAT_SECONDS * 2))
        try:
            current = _load_json(lock_dir / "owner.json")
            if current.get("owner_token") == owner_token:
                (lock_dir / "owner.json").unlink(missing_ok=True)
                for temporary in lock_dir.glob(".owner.*.tmp"):
                    temporary.unlink(missing_ok=True)
                lock_dir.rmdir()
        except OSError:
            pass


def _live_lane_locks(repo_root: Path) -> list[str]:
    lock_root = Path(repo_root) / "kb" / "history" / "lane-status" / "locks"
    if not lock_root.exists():
        return []
    live: list[str] = []
    for lock_file in lock_root.glob("*.lock/lock.json"):
        try:
            payload = json.loads(lock_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            live.append(str(lock_file))
            continue
        heartbeat = payload.get("heartbeat_epoch") if isinstance(payload, dict) else None
        try:
            age = time.time() - float(heartbeat)
        except (TypeError, ValueError):
            age = 0
        if age <= 12 * 60 * 60:
            live.append(str(lock_file))
    return live


def _load_journal(repo_root: Path) -> dict[str, Any]:
    existing = _load_json(journal_path(repo_root))
    if existing:
        return existing
    prior = load_maintenance_state(repo_root)
    return {
        "schema_version": MIGRATION_SCHEMA_VERSION,
        "migration_id": MIGRATION_ID,
        "status": "pending",
        "phase": "pending",
        "completed_phases": [],
        "source_versions": {
            "maintenance_standard_version": int(prior.get("maintenance_standard_version") or 0),
            "history_schema_version": int(prior.get("history_schema_version") or 0),
        },
        "target_versions": {
            "maintenance_standard_version": CURRENT_MAINTENANCE_STANDARD_VERSION,
            "history_schema_version": CURRENT_HISTORY_SCHEMA_VERSION,
        },
        "started_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "checkpoints": {},
        "blockers": [],
    }


def _resolve_active_failure(journal: dict[str, Any]) -> bool:
    """Move a no-longer-active failure into append-only diagnostic history."""
    failure = journal.pop("failure", None)
    if not isinstance(failure, Mapping):
        return False
    resolved = dict(failure)
    resolved["resolved_at"] = utc_now_iso()
    resolved["failure_digest"] = content_fingerprint(
        {
            "type": resolved.get("type"),
            "message": resolved.get("message"),
            "resume_from": resolved.get("resume_from"),
            "failed_at": resolved.get("failed_at"),
        }
    )
    history = list(journal.get("failure_history") or [])
    if not any(
        str(item.get("failure_digest") or "") == resolved["failure_digest"]
        for item in history
        if isinstance(item, Mapping)
    ):
        history.append(resolved)
    journal["failure_history"] = history
    return True


def _checkpoint(
    repo_root: Path,
    journal: dict[str, Any],
    phase: str,
    details: Mapping[str, Any],
) -> dict[str, Any]:
    _resolve_active_failure(journal)
    completed = list(journal.get("completed_phases") or [])
    if phase not in completed:
        completed.append(phase)
    journal.update(
        {
            "status": "running" if phase != "committed" else "committed",
            "phase": phase,
            "completed_phases": completed,
            "updated_at": utc_now_iso(),
        }
    )
    checkpoints = dict(journal.get("checkpoints") or {})
    checkpoints[phase] = {
        "completed_at": journal["updated_at"],
        "details": dict(details),
        "details_digest": content_fingerprint(details),
    }
    journal["checkpoints"] = checkpoints
    _atomic_write_json(journal_path(repo_root), journal)
    return journal


def canonicalize_runtime_state(repo_root: Path) -> dict[str, Any]:
    """Rewrite configured managed inputs to the sole current runtime format.

    This function belongs only to the versioned upgrade transaction. Daily
    retrieval and automation code never calls migration readers.
    """
    from local_kb.org_migration import migrate_organization_repo_to_current
    from local_kb.card_schema_migration import migrate_skill_guidance_fields_to_current
    from local_kb.settings_migration import migrate_desktop_settings_to_current
    from local_kb.settings import load_desktop_settings

    root = Path(repo_root)
    settings_migration = migrate_desktop_settings_to_current(root)
    if not settings_migration.get("ok"):
        raise RuntimeError(
            "desktop settings canonicalization failed: "
            + str(settings_migration.get("error") or settings_migration.get("status") or "unknown error")
        )
    settings = load_desktop_settings(root)
    card_schema_migration = migrate_skill_guidance_fields_to_current(root)
    if not card_schema_migration.get("ok"):
        raise RuntimeError(
            "card schema canonicalization failed: "
            + str(card_schema_migration.get("error") or card_schema_migration.get("status") or "unknown error")
        )
    organization = settings.get("organization") if isinstance(settings.get("organization"), dict) else {}
    mirror_text = str(organization.get("local_mirror_path") or "").strip()
    results: list[dict[str, Any]] = []
    if mirror_text:
        mirror = Path(mirror_text)
        if not mirror.exists():
            raise RuntimeError(f"configured organization mirror does not exist: {mirror}")
        result = migrate_organization_repo_to_current(mirror)
        results.append({"path": str(mirror), **result})
        if not result.get("ok"):
            raise RuntimeError(
                "organization mirror canonicalization failed: "
                + str(result.get("error") or result.get("status") or "unknown error")
            )

    residuals: list[str] = []
    for item in results:
        validation = item.get("validation") if isinstance(item.get("validation"), dict) else {}
        if item.get("status") == "no_delta" and not validation.get("ok"):
            residuals.append(str(item.get("path") or ""))
        receipt = item.get("receipt") if isinstance(item.get("receipt"), dict) else {}
        if int(receipt.get("residual_obsolete_root_count") or 0):
            residuals.append(str(item.get("path") or ""))
        if int(receipt.get("residual_obsolete_field_count") or 0):
            residuals.append(str(item.get("path") or ""))
    if residuals:
        raise RuntimeError("runtime canonicalization left obsolete organization residuals: " + ", ".join(residuals))
    settings_receipt = (
        settings_migration.get("receipt")
        if isinstance(settings_migration.get("receipt"), dict)
        else {}
    )
    if int(settings_receipt.get("residual_obsolete_field_count") or 0):
        raise RuntimeError("runtime canonicalization left obsolete desktop settings fields")
    return {
        "schema_version": 1,
        "current_runtime_only": True,
        "configured_organization_count": len(results),
        "desktop_settings_migration": settings_migration,
        "card_schema_migration": card_schema_migration,
        "organization_migrations": results,
        "residual_obsolete_input_count": 0,
    }


def _managed_files(repo_root: Path) -> Iterator[Path]:
    root = Path(repo_root).resolve()
    seen: set[str] = set()
    for relative in MANAGED_DIRECTORY_ROOTS:
        target = root / relative
        if not _fs_path(target).is_dir():
            continue
        for directory, _directories, files in os.walk(str(_fs_path(target)), followlinks=False):
            for name in files:
                path = _normal_absolute_path(Path(directory) / name)
                key = os.path.normcase(str(path))
                if key in seen:
                    continue
                seen.add(key)
                yield path
    for relative in MANAGED_EXACT_FILES:
        path = root / relative
        key = os.path.normcase(str(_normal_absolute_path(path)))
        if _fs_is_file(path) and key not in seen:
            seen.add(key)
            yield path
    local_root = root / ".local"
    if local_root.exists():
        for path in local_root.iterdir():
            if not path.is_file():
                continue
            if any(path.name.startswith(prefix) for prefix in MANAGED_LOCAL_PREVIEW_PREFIXES):
                key = os.path.normcase(str(_normal_absolute_path(path)))
                if key not in seen:
                    seen.add(key)
                    yield path


def _lab_comparison_path(repo_root: Path, relative: Path) -> Path | None:
    parts = relative.parts
    marker_indexes = [
        index
        for index, value in enumerate(parts)
        if value in {"workspaces", "backups", "real-run-backups"}
    ]
    if not marker_indexes:
        return None
    marker_index = marker_indexes[0]
    if len(parts) <= marker_index + 2:
        return None
    tail = Path(*parts[marker_index + 2 :])
    return Path(repo_root) / tail


def _classification_for(
    repo_root: Path,
    relative: Path,
    *,
    digest: str,
    main_digest_cache: dict[Path, str],
) -> tuple[str, str, str]:
    normalized = relative.as_posix()
    name = relative.name.lower()
    if normalized.startswith(".local/maintenance-lab/"):
        compare = _lab_comparison_path(repo_root, relative)
        if compare is not None and compare.is_file():
            compare_resolved = compare.resolve()
            compare_digest = main_digest_cache.get(compare_resolved)
            if compare_digest is None:
                compare_digest = _sha256_file(compare)
                main_digest_cache[compare_resolved] = compare_digest
            if compare_digest == digest:
                return "derived", "duplicate-maintenance-workspace-copy", str(compare.relative_to(repo_root)).replace("\\", "/")
        if any(part in {".git", "__pycache__", ".pytest_cache", ".mypy_cache"} for part in relative.parts):
            return "derived", "regenerable-maintenance-workspace-control-data", ""
        return "cold", "unique-maintenance-lab-difference", str(compare.relative_to(repo_root)).replace("\\", "/") if compare else ""
    if normalized.startswith("kb/history/architecture/"):
        if name in COLD_EVIDENCE_NAMES or relative.suffix.lower() in {".json", ".jsonl", ".md", ".yaml", ".yml"}:
            return "cold", "retired-architect-audit-evidence", ""
        return "derived", "retired-architect-regenerable-artifact", ""
    if normalized.startswith(".local/architect/"):
        if relative.suffix.lower() in {".json", ".jsonl", ".md", ".yaml", ".yml", ".txt"}:
            return "cold", "retired-architect-local-audit-evidence", ""
        return "derived", "retired-architect-local-sandbox-derivative", ""
    if normalized.startswith("kb/history/dream/"):
        if name in {"report.json", "experiments.json"}:
            return "cold", "dream-result-summary", ""
        return "derived", "dream-sandbox-or-expanded-run-artifact", ""
    if normalized.startswith("kb/history/consolidation/"):
        if name in {"apply.json", "report.json"}:
            return "cold", "maintenance-apply-receipt", ""
        return "derived", "rebuildable-consolidation-snapshot-or-proposal", ""
    if normalized.startswith(".local/automation-results/"):
        if relative.suffix.lower() in {".json", ".jsonl", ".md", ".txt", ".log"}:
            return "cold", "automation-result-evidence", ""
        return "derived", "automation-result-derivative", ""
    if normalized.startswith("kb/history/lane-status/"):
        return "cold", "retired-lane-status", ""
    return "derived", "declared-chaos-brain-test-or-preview-derivative", ""


def build_inventory(
    repo_root: Path,
    *,
    output_path: Path | None = None,
    summary_output_path: Path | None = None,
    migration_id: str = MIGRATION_ID,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    path = Path(output_path) if output_path is not None else inventory_path(root)
    summary_path = (
        Path(summary_output_path)
        if summary_output_path is not None
        else inventory_summary_path(root)
    )
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {"cold": 0, "derived": 0, "unresolved": 0}
    bytes_by_class: dict[str, int] = {"cold": 0, "derived": 0, "unresolved": 0}
    total_files = 0
    total_bytes = 0
    main_digest_cache: dict[Path, str] = {}
    inventory_digest = hashlib.sha256()

    def probe(item: tuple[int, Path]) -> dict[str, Any]:
        item_id, file_path = item
        resolved = _normal_absolute_path(file_path)
        if not _path_within(resolved, root):
            return {
                "item_id": item_id,
                "resolved": resolved,
                "size": 0,
                "mtime_ns": 0,
                "digest": "",
                "outside": True,
            }
        current_stat = _fs_stat(resolved)
        return {
            "item_id": item_id,
            "resolved": resolved,
            "size": int(current_stat.st_size),
            "mtime_ns": int(current_stat.st_mtime_ns),
            "digest": _sha256_file(resolved),
            "outside": False,
        }

    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        numbered_paths = enumerate(_managed_files(root), start=1)
        with ThreadPoolExecutor(max_workers=_filesystem_worker_count()) as executor:
            for chunk in _bounded_chunks(numbered_paths):
                for probed in executor.map(probe, chunk):
                    item_id = int(probed["item_id"])
                    resolved = Path(probed["resolved"])
                    size = int(probed["size"])
                    mtime_ns = int(probed["mtime_ns"])
                    digest = str(probed["digest"])
                    if probed["outside"]:
                        classification, reason, compare_path = (
                            "unresolved",
                            "path-outside-repository",
                            "",
                        )
                        relative_text = str(resolved)
                    else:
                        relative = resolved.relative_to(root)
                        classification, reason, compare_path = _classification_for(
                            root,
                            relative,
                            digest=digest,
                            main_digest_cache=main_digest_cache,
                        )
                        relative_text = str(relative).replace("\\", "/")
                    record = {
                        "item_id": f"artifact:{item_id:09d}",
                        "path": relative_text,
                        "classification": classification,
                        "reason": reason,
                        "compare_path": compare_path,
                        "size": size,
                        "mtime_ns": mtime_ns,
                        "sha256": digest,
                        "ownership": "chaos-brain-managed",
                    }
                    line = _canonical_json(record)
                    handle.write(line + "\n")
                    inventory_digest.update(line.encode("utf-8"))
                    counts[classification] = counts.get(classification, 0) + 1
                    bytes_by_class[classification] = bytes_by_class.get(classification, 0) + size
                    total_files += 1
                    total_bytes += size
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    summary = {
        "schema_version": MIGRATION_SCHEMA_VERSION,
        "migration_id": migration_id,
        "created_at": utc_now_iso(),
        "inventory_path": str(path.relative_to(root)).replace("\\", "/"),
        "inventory_digest": inventory_digest.hexdigest(),
        "file_count": total_files,
        "byte_count": total_bytes,
        "counts_by_class": counts,
        "bytes_by_class": bytes_by_class,
        "unresolved_count": counts.get("unresolved", 0),
    }
    _atomic_write_json(summary_path, summary)
    return summary


def _backup_active_surface(repo_root: Path) -> dict[str, Any]:
    root = Path(repo_root)
    backup = rollback_root(root)
    sources = (
        root / "kb" / "public",
        root / "kb" / "private",
        root / "kb" / "candidates",
        root / "kb" / "history" / "lifecycle",
        root / "kb" / "indexes",
        authority_root(root),
        maintenance_state_path(root),
        root / ".local" / "khaos_brain_desktop_settings.json",
    )
    backed_up: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        relative = source.relative_to(root)
        if not source.exists():
            backed_up.append(
                {
                    "source": str(relative).replace("\\", "/"),
                    "backup": "",
                    "existed": False,
                    "file_count": 0,
                    "byte_count": 0,
                }
            )
            continue
        destination = backup / f"s{index}"
        if source.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
            byte_count = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
            file_count = sum(1 for path in destination.rglob("*") if path.is_file())
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            byte_count = destination.stat().st_size
            file_count = 1
        backed_up.append(
            {
                "source": str(relative).replace("\\", "/"),
                "backup": str(destination.relative_to(root)).replace("\\", "/"),
                "existed": True,
                "file_count": file_count,
                "byte_count": byte_count,
            }
        )
    return {
        "rollback_root": str(backup.relative_to(root)).replace("\\", "/"),
        "backed_up": backed_up,
    }


def _restore_active_surface(repo_root: Path, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    restored: list[str] = []
    removed: list[str] = []
    for item in snapshot.get("backed_up", []) if isinstance(snapshot.get("backed_up"), list) else []:
        if not isinstance(item, Mapping):
            continue
        relative = Path(str(item.get("source") or ""))
        if not str(relative):
            continue
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"Rollback target escaped repository root: {target}") from exc
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if not bool(item.get("existed")):
            removed.append(str(relative).replace("\\", "/"))
            continue
        backup_text = str(item.get("backup") or "")
        if not backup_text:
            raise RuntimeError(f"Rollback backup is missing for {relative}")
        source = (root / backup_text).resolve()
        try:
            source.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"Rollback source escaped repository root: {source}") from exc
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            raise RuntimeError(f"Rollback backup is unavailable: {source}")
        restored.append(str(relative).replace("\\", "/"))
    return {"ok": True, "restored": restored, "removed_new": removed}


def _history_observations(repo_root: Path) -> Iterator[dict[str, Any]]:
    path = history_events_path(repo_root)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            text = raw_line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed history at line {line_number}: {exc}") from exc
            if isinstance(payload, dict) and str(payload.get("event_type") or "").lower() == "observation":
                yield payload


def _entry_paths(repo_root: Path) -> Iterator[tuple[str, Path]]:
    for scope in ("public", "private", "candidates"):
        target = Path(repo_root) / "kb" / scope
        if not target.exists():
            continue
        for path in sorted(target.rglob("*.yaml")):
            yield scope, path


def _entry_provenance(data: Mapping[str, Any], *, fallback: str) -> list[str]:
    provenance: set[str] = set()
    source = data.get("source", [])
    sources = source if isinstance(source, list) else [source]
    for item in sources:
        if not isinstance(item, Mapping):
            continue
        for key in ("event_id", "event_ids", "evidence_event_ids", "observation_ids"):
            value = item.get(key)
            if isinstance(value, list):
                provenance.update(str(entry) for entry in value if str(entry))
            elif str(value or ""):
                provenance.add(str(value))
    if not provenance:
        provenance.add(fallback)
    return sorted(provenance)


def _predictive_complete(data: Mapping[str, Any]) -> bool:
    if_block = data.get("if", {}) if isinstance(data.get("if"), Mapping) else {}
    action = data.get("action", {}) if isinstance(data.get("action"), Mapping) else {}
    predict = data.get("predict", {}) if isinstance(data.get("predict"), Mapping) else {}
    return bool(
        str(if_block.get("notes") or if_block.get("scenario") or "").strip()
        and str(action.get("description") or action.get("action") or "").strip()
        and str(predict.get("expected_result") or predict.get("result") or "").strip()
    )


def _logicguard_migratable(data: Mapping[str, Any]) -> bool:
    """Return whether legacy content can form an evidence-bound root argument.

    An absent applicability context is a visible LogicGuard role gap, not a
    reason to preserve a retired standalone-card authority.  Action and root
    prediction remain mandatory for the direct migration route.
    """

    action = data.get("action", {}) if isinstance(data.get("action"), Mapping) else {}
    predict = data.get("predict", {}) if isinstance(data.get("predict"), Mapping) else {}
    return bool(
        str(action.get("description") or action.get("action") or "").strip()
        and str(predict.get("expected_result") or predict.get("result") or "").strip()
    )


def retired_architect_settlement_path(repo_root: Path) -> Path:
    return migration_root(repo_root) / "retired-architect-proposal-settlement.jsonl"


def _retired_proposal_owner(proposal: Mapping[str, Any]) -> str:
    text = _canonical_json(proposal).lower()
    if any(marker in text for marker in ("candidate", "card content", "taxonomy", "retrieval")):
        return "kb-sleep"
    if any(marker in text for marker in ("dream", "experiment", "sandbox evidence")):
        return "kb-dream"
    return "future-active-development-task"


def settle_retired_architect_queue(repo_root: Path) -> dict[str, Any]:
    """Account for every legacy mechanism proposal before retiring its lane."""

    root = Path(repo_root)
    queue_candidates = (
        root / "kb" / "history" / "architecture" / "proposal_queue.json",
        root / ".local" / "architect" / "proposal_queue.json",
    )
    queue_path = next((path for path in queue_candidates if path.is_file()), None)
    target = retired_architect_settlement_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if queue_path is None:
        existing_rows = list(_read_jsonl(target)) if target.is_file() else []
        source_settlement = target if existing_rows else None
        if not existing_rows:
            migration_parent = root / "kb" / "history" / "migrations"
            prior_candidates = sorted(
                (
                    path
                    for path in migration_parent.glob(
                        "*/retired-architect-proposal-settlement.jsonl"
                    )
                    if path.resolve() != target.resolve()
                ),
                key=lambda path: path.stat().st_mtime_ns,
                reverse=True,
            )
            for prior in prior_candidates:
                prior_rows = list(_read_jsonl(prior))
                if prior_rows:
                    existing_rows = prior_rows
                    source_settlement = prior
                    temporary = target.with_name(
                        f".{target.name}.{uuid4().hex}.tmp"
                    )
                    with temporary.open(
                        "w", encoding="utf-8", newline="\n"
                    ) as handle:
                        for row in existing_rows:
                            handle.write(_canonical_json(row) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, target)
                    break
        if existing_rows:
            return {
                "queue_found": False,
                "settlement_reused": True,
                "source_settlement": str(
                    (source_settlement or target).relative_to(root)
                ).replace("\\", "/"),
                "proposal_count": len(existing_rows),
                "settled_count": len(existing_rows),
                "active_debt_count": 0,
                "hard_debt_count": 0,
                "parked_follow_up_count": sum(
                    1
                    for row in existing_rows
                    if str(row.get("disposition") or "") == "parked"
                ),
                "disposition_counts": {
                    "history_only": sum(
                        1
                        for row in existing_rows
                        if str(row.get("disposition") or "") == "history_only"
                    ),
                    "parked": sum(
                        1
                        for row in existing_rows
                        if str(row.get("disposition") or "") == "parked"
                    ),
                },
                "settlement_path": str(target.relative_to(root)).replace("\\", "/"),
                "settlement_digest": _sha256_file(target),
            }
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        temporary.write_text("", encoding="utf-8")
        os.replace(temporary, target)
        return {
            "queue_found": False,
            "proposal_count": 0,
            "settled_count": 0,
            "active_debt_count": 0,
            "hard_debt_count": 0,
            "parked_follow_up_count": 0,
            "settlement_path": str(target.relative_to(root)).replace("\\", "/"),
            "settlement_digest": hashlib.sha256(b"").hexdigest(),
        }
    queue = _load_json(queue_path)
    proposals = queue.get("proposals", [])
    if not isinstance(proposals, list):
        raise ValueError(f"Retired Architect queue has invalid proposals: {queue_path}")
    terminal_statuses = {"applied", "rejected", "superseded", "closed"}
    rows: list[dict[str, Any]] = []
    parked_follow_up_count = 0
    for index, raw in enumerate(proposals, start=1):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Retired Architect proposal {index} is not an object")
        proposal = dict(raw)
        proposal_id = str(
            proposal.get("proposal_id")
            or proposal.get("id")
            or f"legacy-proposal-{index:04d}"
        )
        execution = proposal.get("execution_state", {}) if isinstance(proposal.get("execution_state"), Mapping) else {}
        prior_status = str(proposal.get("status") or execution.get("state") or "unknown").lower()
        if prior_status in terminal_statuses:
            disposition = "history_only"
            owner = "cold-archive"
            reason = "The proposal already reached a terminal legacy outcome and remains audit evidence only."
            reopen_condition: dict[str, Any] = {}
        else:
            disposition = "parked"
            owner = _retired_proposal_owner(proposal)
            reason = (
                "The mechanism lane is retired. Reconsider only inside the named current owner after a concrete "
                "regression or failed current check reproduces the same bounded issue."
            )
            reopen_condition = {
                "kind": "current-regression-and-owner-check-failure",
                "owner": owner,
                "requires_new_fingerprint": True,
            }
            parked_follow_up_count += 1
        proposal_digest = content_fingerprint(proposal)
        rows.append(
            {
                "schema_version": MIGRATION_SCHEMA_VERSION,
                "proposal_id": proposal_id,
                "prior_status": prior_status,
                "disposition": disposition,
                "owner": owner,
                "reason": reason,
                "reopen_condition": reopen_condition,
                "evidence_fingerprint": proposal_digest,
                "source_queue": str(queue_path.relative_to(root)).replace("\\", "/"),
            }
        )
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    digest = hashlib.sha256()
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            line = _canonical_json(row)
            handle.write(line + "\n")
            digest.update((line + "\n").encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    return {
        "queue_found": True,
        "queue_path": str(queue_path.relative_to(root)).replace("\\", "/"),
        "proposal_count": len(proposals),
        "settled_count": len(rows),
        "active_debt_count": 0,
        "hard_debt_count": 0,
        "parked_follow_up_count": parked_follow_up_count,
        "disposition_counts": {
            "history_only": sum(1 for row in rows if row["disposition"] == "history_only"),
            "parked": sum(1 for row in rows if row["disposition"] == "parked"),
        },
        "settlement_path": str(target.relative_to(root)).replace("\\", "/"),
        "settlement_digest": digest.hexdigest(),
    }


def settle_knowledge_debt(repo_root: Path, *, run_id: str) -> dict[str, Any]:
    from local_kb.candidate_lifecycle import build_candidate_from_observation

    root = Path(repo_root)
    observations = list(_history_observations(root))
    lifecycle_before = load_lifecycle_state(root, repair_projection=False)
    observation_states = lifecycle_before.get("observations", {})
    batch_events: list[dict[str, Any]] = []
    disposition_count = 0
    reused_observation_count = 0
    resumed_observation_count = 0
    candidate_created = 0
    candidate_reused = 0
    candidate_observations: dict[str, set[str]] = {}
    candidate_grades: dict[str, str] = {}
    grade_order = {"weak": 0, "medium": 1, "strong": 2}

    history_event_ids: set[str] = set()
    history_path = history_events_path(root)
    if history_path.exists():
        with history_path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                text = raw_line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed history at line {line_number}: {exc}") from exc
                if isinstance(payload, Mapping) and str(payload.get("event_id") or ""):
                    history_event_ids.add(str(payload["event_id"]))

    entry_records: dict[str, dict[str, Any]] = {}
    for scope, path in _entry_paths(root):
        data = load_yaml_file(path)
        entry_id = str(data.get("id") or "").strip()
        if not entry_id:
            continue
        previous = entry_records.get(entry_id)
        if previous and Path(previous["path"]).resolve() != path.resolve():
            raise ValueError(f"Duplicate entry id {entry_id}: {previous['path']} and {path}")
        entry_records[entry_id] = {"scope": scope, "path": path, "data": data}

    for observation in observations:
        observation_id = str(observation.get("event_id") or "").strip()
        decision = classify_observation(observation)
        if decision.get("disposition") == "candidate":
            candidate_data = build_candidate_from_observation(observation, run_id=run_id)
            candidate_id = str(candidate_data["id"])
            record = entry_records.get(candidate_id)
            created = False
            if record is None:
                target_path = root / "kb" / "candidates" / f"{candidate_id}.yaml"
                if target_path.exists():
                    stored = load_yaml_file(target_path)
                    candidate_data = stored if isinstance(stored, dict) else candidate_data
                else:
                    write_yaml_file(target_path, candidate_data)
                    created = True
                record = {"scope": "candidates", "path": target_path, "data": candidate_data}
                entry_records[candidate_id] = record
            stored_data = record["data"] if isinstance(record.get("data"), Mapping) else candidate_data
            deadline = str(stored_data.get("decision_deadline") or candidate_data["decision_deadline"])
            provenance = _entry_provenance(stored_data, fallback=f"candidate:{candidate_id}")
            candidate_event_id = f"candidate-created:{candidate_id}:{observation_id}"
            if candidate_event_id not in history_event_ids and (created or observation_id in provenance):
                record_history_event(
                    root,
                    build_history_event(
                        "candidate-created",
                        event_id=candidate_event_id,
                        source={"kind": "sleep-lifecycle", "agent": "kb-sleep", "run_id": run_id},
                        target={
                            "kind": "candidate-entry",
                            "entry_id": candidate_id,
                            "entry_path": str(Path(record["path"]).relative_to(root)).replace("\\", "/"),
                            "domain_path": list(stored_data.get("domain_path") or []),
                        },
                        rationale="Sleep created a bounded candidate from an admitted predictive observation.",
                        context={
                            "observation_ids": [observation_id],
                            "decision_deadline": deadline,
                            "retrieval_eligible": False,
                        },
                    ),
                )
                history_event_ids.add(candidate_event_id)
            if created:
                candidate_created += 1
            else:
                candidate_reused += 1
            candidate_observations.setdefault(candidate_id, set()).add(observation_id)
            grade = str(decision.get("evidence_grade") or "weak")
            previous_grade = candidate_grades.get(candidate_id, "weak")
            if grade_order.get(grade, 0) >= grade_order.get(previous_grade, 0):
                candidate_grades[candidate_id] = grade
            decision.update(
                {
                    "target_id": candidate_id,
                    "follow_up_id": candidate_id,
                    "follow_up_deadline": deadline,
                }
            )

        current = observation_states.get(observation_id, {}) if isinstance(observation_states, Mapping) else {}
        current_state = str(current.get("state") or "") if isinstance(current, Mapping) else ""
        needs_admission = not isinstance(current, Mapping) or not str(current.get("admitted_at") or "")
        needs_disposition = needs_admission or current_state in {"", "new", "missing-admission"}
        if not needs_admission and not needs_disposition:
            reused_observation_count += 1
        elif isinstance(current, Mapping) and current:
            resumed_observation_count += 1
        if needs_admission:
            batch_events.append(build_observation_admission_event(observation))
        if needs_disposition:
            batch_events.append(
                build_observation_disposition_event(observation, run_id=run_id, decision=decision)
            )
        disposition_count += 1

    entry_counts: dict[str, int] = {}
    for entry_id, record in sorted(entry_records.items()):
        path = Path(record["path"])
        data = record["data"] if isinstance(record.get("data"), Mapping) else load_yaml_file(path)
        raw_status = str(data.get("status") or "candidate").strip().lower()
        relative = str(path.relative_to(root)).replace("\\", "/")
        file_digest = _sha256_file(path)
        provenance = set(_entry_provenance(data, fallback=f"legacy-file:{relative}@{file_digest}"))
        provenance.update(candidate_observations.get(entry_id, set()))
        provenance_ids = sorted(item for item in provenance if item)
        evidence_grade = candidate_grades.get(entry_id) or ("medium" if _predictive_complete(data) else "weak")
        target_id = str(data.get("merged_into") or data.get("superseded_by") or "").strip()
        if raw_status in {"trusted", "approved"}:
            target_status = "trusted"
            reason = "Legacy trusted entry retained with explicit file provenance."
            reopen: dict[str, Any] = {}
        elif raw_status == "rejected":
            target_status = "rejected"
            reason = "Legacy rejected entry retained as terminal audit evidence."
            reopen = {}
        elif raw_status in {"merged", "superseded"} and target_id:
            target_status = raw_status
            reason = f"Legacy {raw_status} entry linked to its declared survivor."
            reopen = {}
        elif raw_status in {"deprecated", "retired"}:
            target_status = "deprecated"
            reason = "Legacy deprecated entry excluded from active retrieval."
            reopen = {}
        else:
            target_status = "parked"
            reason = (
                "Legacy candidate lacks current independent validation under maintenance standard v1; "
                "it is closed as parked rather than left as active debt."
            )
            reopen = {
                "kind": "new-independent-evidence",
                "minimum_grade": "medium",
                "requires_new_fingerprint": True,
            }
        batch_events.append(
            build_entry_transition_event(
                entry_id=entry_id,
                from_state=raw_status,
                to_state=target_status,
                reason=reason,
                actor=run_id,
                evidence_ids=provenance_ids,
                provenance_ids=provenance_ids,
                evidence_grade=evidence_grade,
                target_id=target_id,
                retrieval_eligible=False,
                reopen_condition=reopen,
                evidence_fingerprint=content_fingerprint([entry_id, provenance_ids, file_digest]),
                event_type="entry-lifecycle-snapshot",
            )
        )
        entry_counts[target_status] = entry_counts.get(target_status, 0) + 1

    batch_result = commit_lifecycle_events(root, batch_events)

    validation = validate_lifecycle(repo_root)
    state = load_lifecycle_state(repo_root)
    hard_observation_debt = [
        item_id
        for item_id, item in state.get("observations", {}).items()
        if str(item.get("state") or "") in {"new", "missing-admission"}
    ]
    retired_queue = settle_retired_architect_queue(repo_root)
    return {
        "observation_count": len(observations),
        "disposition_count": disposition_count,
        "candidate_created_count": candidate_created,
        "candidate_reused_count": candidate_reused,
        "reused_observation_count": reused_observation_count,
        "resumed_observation_count": resumed_observation_count,
        "entry_counts": dict(sorted(entry_counts.items())),
        "lifecycle_batch": {
            "settlement_mode": "atomic-batch",
            "requested_event_count": int(batch_result.get("requested_count") or 0),
            "created_event_count": int(batch_result.get("created_count") or 0),
            "reused_event_count": int(batch_result.get("reused_count") or 0),
            "replay_pass_count": int(batch_result.get("replay_pass_count") or 0),
            "atomic_batch_count": int(batch_result.get("atomic_batch_count") or 0),
            "final_sequence": int(batch_result.get("state", {}).get("last_sequence") or 0),
        },
        "hard_observation_debt_count": len(hard_observation_debt),
        "hard_observation_debt_sample": hard_observation_debt[:20],
        "lifecycle_validation": validation,
        "retired_architect_queue": retired_queue,
    }


def archive_inventory(
    repo_root: Path,
    *,
    inventory_file: Path | None = None,
    archive_manifest_file: Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    inventory_source = (
        Path(inventory_file) if inventory_file is not None else inventory_path(root)
    )
    archive_manifest = (
        Path(archive_manifest_file)
        if archive_manifest_file is not None
        else archive_manifest_path(root)
    )
    temporary = archive_manifest.with_name(f".{archive_manifest.name}.{uuid4().hex}.tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    cold_manifest = cold_manifest_path(root)
    existing_cold = {
        str(item.get("sha256") or "")
        for item in _read_jsonl(cold_manifest)
        if str(item.get("sha256") or "")
    }
    archived_objects = 0
    archived_references = 0
    archived_bytes = 0
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        for item in _read_jsonl(inventory_source):
            classification = str(item.get("classification") or "")
            if classification not in {"cold", "derived"}:
                continue
            source = root / str(item["path"])
            digest = str(item.get("sha256") or "")
            archive_object = ""
            if classification == "cold":
                object_path = cold_object_root(root) / digest[:2] / f"{digest}.gz"
                archive_object = str(object_path.relative_to(root)).replace("\\", "/")
                if digest not in existing_cold or not object_path.is_file():
                    object_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary_object = object_path.with_name(f".{object_path.name}.{uuid4().hex}.tmp")
                    with _fs_path(source).open("rb") as input_handle, gzip.open(temporary_object, "wb", compresslevel=6) as gzip_handle:
                        shutil.copyfileobj(input_handle, gzip_handle, length=1024 * 1024)
                    os.replace(temporary_object, object_path)
                    cold_record = {
                        "schema_version": 1,
                        "sha256": digest,
                        "object_path": archive_object,
                        "original_size": int(item.get("size") or 0),
                        "created_at": utc_now_iso(),
                        "restore": "gzip-decompress-and-verify-sha256",
                    }
                    if digest not in existing_cold:
                        _append_jsonl(cold_manifest, cold_record)
                        existing_cold.add(digest)
                    archived_objects += 1
                    archived_bytes += int(item.get("size") or 0)
                archived_references += 1
            record = {
                **item,
                "archive_object": archive_object,
                "archive_status": "content-retained" if classification == "cold" else "hash-retained-derived",
                "archived_at": utc_now_iso(),
            }
            output.write(_canonical_json(record) + "\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, archive_manifest)
    return {
        "archive_manifest": str(archive_manifest.relative_to(root)).replace("\\", "/"),
        "cold_manifest": str(cold_manifest.relative_to(root)).replace("\\", "/"),
        "archived_object_count": archived_objects,
        "archived_reference_count": archived_references,
        "archived_original_bytes": archived_bytes,
    }


def _verify_cold_object(repo_root: Path, item: Mapping[str, Any]) -> bool:
    object_ref = str(item.get("archive_object") or "")
    if not object_ref:
        return False
    path = Path(repo_root) / object_ref
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    try:
        with gzip.open(path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return False
    return digest.hexdigest() == str(item.get("sha256") or "")


def _prior_prune_records(prune_path: Path) -> tuple[dict[str, dict[str, Any]], list[Path]]:
    records: dict[str, dict[str, Any]] = {}
    stale_paths = sorted(prune_path.parent.glob(f".{prune_path.name}.*.tmp"))
    for stale_path in stale_paths:
        with stale_path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                text = raw_line.strip()
                if not text:
                    continue
                try:
                    item = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Malformed partial prune manifest at {stale_path}:{line_number}: {exc}"
                    ) from exc
                if not isinstance(item, Mapping):
                    raise ValueError(
                        f"Expected object in partial prune manifest at {stale_path}:{line_number}"
                    )
                relative = str(item.get("path") or "")
                status = str(item.get("prune_status") or "")
                if relative and status in {"deleted", "deleted-before-resume"}:
                    records[relative] = {
                        "deleted_at": str(item.get("deleted_at") or ""),
                        "deletion_reason": str(item.get("deletion_reason") or ""),
                        "original_mode": int(item.get("original_mode") or 0),
                        "read_only_cleared": bool(item.get("read_only_cleared")),
                    }
    return records, stale_paths


def _unlink_verified_managed_file(target: Path, *, original_mode: int) -> bool:
    """Delete a verified file, clearing only the Windows read-only attribute."""

    filesystem_target = _fs_path(target)
    try:
        filesystem_target.unlink()
        return False
    except PermissionError:
        if os.name != "nt" or original_mode & stat.S_IWRITE:
            raise
        try:
            filesystem_target.chmod(original_mode | stat.S_IWRITE)
            filesystem_target.unlink()
        except Exception:
            if filesystem_target.exists():
                try:
                    filesystem_target.chmod(original_mode)
                except OSError:
                    pass
            raise
        return True


def _remove_empty_managed_directory_tree(target_root: Path) -> None:
    if not _fs_path(target_root).is_dir():
        return
    for directory, _directories, _files in os.walk(
        str(_fs_path(target_root)),
        topdown=False,
        followlinks=False,
    ):
        try:
            os.rmdir(directory)
        except OSError:
            pass


def prune_inventory(
    repo_root: Path,
    *,
    archive_manifest_file: Path | None = None,
    prune_manifest_file: Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    archive_source = (
        Path(archive_manifest_file)
        if archive_manifest_file is not None
        else archive_manifest_path(root)
    )
    manifest_by_path = {
        str(item.get("path") or ""): item
        for item in _read_jsonl(archive_source)
    }
    prune_path = (
        Path(prune_manifest_file)
        if prune_manifest_file is not None
        else prune_manifest_path(root)
    )
    prior_deleted, stale_prune_paths = _prior_prune_records(prune_path)
    temporary = prune_path.with_name(f".{prune_path.name}.{uuid4().hex}.tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    deleted_files = 0
    deleted_bytes = 0
    resumed_deleted_files = 0
    resumed_deleted_bytes = 0
    already_absent_files = 0
    read_only_cleared_files = 0
    blockers: list[str] = []
    verified_cold_digests: set[str] = set()

    def probe(item_pair: tuple[str, Mapping[str, Any]]) -> dict[str, Any]:
        relative_text, item = item_pair
        target = _normal_absolute_path(root / relative_text)
        if not _path_within(target, root):
            return {"status": "outside", "target": target}
        if not _fs_exists(target):
            return {"status": "missing", "target": target}
        try:
            current_stat = _fs_stat(target)
        except FileNotFoundError:
            return {"status": "missing", "target": target}
        except OSError as exc:
            return {
                "status": "error",
                "target": target,
                "error": f"{type(exc).__name__}: {exc}",
            }
        if (
            int(current_stat.st_size) != int(item.get("size") or 0)
            or int(current_stat.st_mtime_ns) != int(item.get("mtime_ns") or 0)
        ):
            return {
                "status": "concurrent-change",
                "target": target,
                "current_stat": current_stat,
            }
        try:
            current_digest = _sha256_file(target)
        except OSError as exc:
            return {
                "status": "error",
                "target": target,
                "error": f"{type(exc).__name__}: {exc}",
            }
        if current_digest != str(item.get("sha256") or ""):
            return {
                "status": "content-change",
                "target": target,
                "current_stat": current_stat,
            }
        return {
            "status": "verified",
            "target": target,
            "current_stat": current_stat,
        }

    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        items = sorted(manifest_by_path.items())
        with ThreadPoolExecutor(max_workers=_filesystem_worker_count()) as executor:
            for chunk in _bounded_chunks(items):
                for (relative_text, item), probed in zip(
                    chunk,
                    executor.map(probe, chunk),
                ):
                    status = str(probed.get("status") or "error")
                    target = Path(probed["target"])
                    if status == "outside":
                        blockers.append(f"outside mutation boundary: {relative_text}")
                        continue
                    if status == "missing":
                        prior = prior_deleted.get(relative_text)
                        if prior is not None:
                            size = int(item.get("size") or 0)
                            deleted_files += 1
                            deleted_bytes += size
                            resumed_deleted_files += 1
                            resumed_deleted_bytes += size
                            prior_read_only_cleared = bool(
                                prior.get("read_only_cleared")
                            )
                            if prior_read_only_cleared:
                                read_only_cleared_files += 1
                            output.write(
                                _canonical_json(
                                    {
                                        **item,
                                        "prune_status": "deleted-before-resume",
                                        "deleted_at": str(prior.get("deleted_at") or ""),
                                        "deletion_reason": str(
                                            prior.get("deletion_reason")
                                            or item.get("reason")
                                            or "declared derived data"
                                        ),
                                        "original_mode": int(
                                            prior.get("original_mode") or 0
                                        ),
                                        "read_only_cleared": prior_read_only_cleared,
                                    }
                                )
                                + "\n"
                            )
                        else:
                            already_absent_files += 1
                            output.write(
                                _canonical_json(
                                    {**item, "prune_status": "already-absent"}
                                )
                                + "\n"
                            )
                        continue
                    if status == "concurrent-change":
                        blockers.append(f"concurrent change: {relative_text}")
                        output.write(
                            _canonical_json(
                                {**item, "prune_status": "blocked-concurrent-change"}
                            )
                            + "\n"
                        )
                        continue
                    if status == "content-change":
                        blockers.append(f"content changed: {relative_text}")
                        output.write(
                            _canonical_json(
                                {**item, "prune_status": "blocked-content-change"}
                            )
                            + "\n"
                        )
                        continue
                    if status == "error":
                        blockers.append(
                            f"filesystem verification failed: {relative_text}: "
                            + str(probed.get("error") or "unknown error")
                        )
                        output.write(
                            _canonical_json(
                                {**item, "prune_status": "blocked-filesystem-error"}
                            )
                            + "\n"
                        )
                        continue
                    if str(item.get("classification") or "") == "cold":
                        digest = str(item.get("sha256") or "")
                        if digest not in verified_cold_digests:
                            if not _verify_cold_object(root, item):
                                blockers.append(
                                    f"cold object verification failed: {relative_text}"
                                )
                                output.write(
                                    _canonical_json(
                                        {
                                            **item,
                                            "prune_status": "blocked-cold-integrity",
                                        }
                                    )
                                    + "\n"
                                )
                                continue
                            verified_cold_digests.add(digest)
                    current_stat = probed["current_stat"]
                    size = int(item.get("size") or 0)
                    original_mode = int(current_stat.st_mode)
                    read_only_cleared = _unlink_verified_managed_file(
                        target,
                        original_mode=original_mode,
                    )
                    deleted_files += 1
                    deleted_bytes += size
                    if read_only_cleared:
                        read_only_cleared_files += 1
                    output.write(
                        _canonical_json(
                            {
                                **item,
                                "prune_status": "deleted",
                                "deleted_at": utc_now_iso(),
                                "deletion_reason": str(
                                    item.get("reason") or "declared derived data"
                                ),
                                "original_mode": stat.S_IMODE(original_mode),
                                "read_only_cleared": read_only_cleared,
                            }
                        )
                        + "\n"
                    )
                output.flush()
                os.fsync(output.fileno())
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, prune_path)
    for stale_path in stale_prune_paths:
        if stale_path.exists():
            stale_path.unlink()
    if not blockers:
        for relative_root in MANAGED_DIRECTORY_ROOTS:
            target_root = _normal_absolute_path(root / relative_root)
            if not _path_within(target_root, root) or not _fs_path(target_root).is_dir():
                continue
            _remove_empty_managed_directory_tree(target_root)
    return {
        "prune_manifest": str(prune_path.relative_to(root)).replace("\\", "/"),
        "deleted_file_count": deleted_files,
        "deleted_byte_count": deleted_bytes,
        "resumed_deleted_file_count": resumed_deleted_files,
        "resumed_deleted_byte_count": resumed_deleted_bytes,
        "already_absent_file_count": already_absent_files,
        "read_only_cleared_file_count": read_only_cleared_files,
        "blockers": blockers,
        "ok": not blockers,
    }


def _managed_surface_snapshot(repo_root: Path, *, sample_limit: int = 20) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    count = 0
    byte_count = 0
    sample: list[str] = []
    for path in _managed_files(root):
        count += 1
        try:
            byte_count += int(_fs_stat(path).st_size)
        except OSError:
            pass
        if len(sample) < sample_limit:
            sample.append(str(path.relative_to(root)).replace("\\", "/"))
    return {
        "file_count": count,
        "byte_count": byte_count,
        "sample": sample,
    }


def _load_reconciliation_state(repo_root: Path) -> dict[str, Any]:
    payload = _load_json(reconciliation_state_path(repo_root))
    if payload:
        return payload
    return {
        "schema_version": 1,
        "migration_id": MIGRATION_ID,
        "status": "idle",
        "generation": 0,
        "active_pass": {},
        "receipt_history": [],
        "updated_at": utc_now_iso(),
    }


def _write_reconciliation_state(repo_root: Path, state: Mapping[str, Any]) -> None:
    _atomic_write_json(reconciliation_state_path(repo_root), state)


def reconcile_managed_surface(
    repo_root: Path,
    *,
    reason: str,
    max_passes: int = 4,
) -> dict[str, Any]:
    """Converge managed physical debt that appears after the main inventory.

    Each pass owns stable inventory/archive/prune paths so an interrupted prune
    resumes with exact accounting. A later concurrent reintroduction starts a
    new pass and leaves every earlier receipt immutable.
    """

    root = Path(repo_root).resolve()
    state = _load_reconciliation_state(root)
    initial_history_count = len(list(state.get("receipt_history") or []))
    completed_this_call: list[dict[str, Any]] = []

    for _attempt in range(max_passes):
        active = dict(state.get("active_pass") or {})
        if str(state.get("status") or "") == "paused_failed" and active.get("failure"):
            resolved_failure = dict(active.pop("failure"))
            resolved_failure["resolved_at"] = utc_now_iso()
            failure_history = list(active.get("failure_history") or [])
            failure_history.append(resolved_failure)
            active["failure_history"] = failure_history
            active["status"] = "running"
            state.update(
                {
                    "status": "running",
                    "active_pass": active,
                    "updated_at": utc_now_iso(),
                }
            )
            _write_reconciliation_state(root, state)
        if str(state.get("status") or "") not in {"running", "paused_failed"} or not active:
            before = _managed_surface_snapshot(root)
            if int(before.get("file_count") or 0) == 0:
                return {
                    "ok": True,
                    "status": "no_delta" if not completed_this_call else "reconciled",
                    "reason": reason,
                    "pass_count": len(completed_this_call),
                    "receipts": completed_this_call,
                    "residual": before,
                    "receipt_history_count": len(list(state.get("receipt_history") or [])),
                }
            generation = int(state.get("generation") or 0) + 1
            pass_id = f"reconcile-{generation:06d}"
            pass_root = reconciliation_root(root) / pass_id
            active = {
                "pass_id": pass_id,
                "generation": generation,
                "reason": reason,
                "status": "running",
                "phase": "pending",
                "started_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "completed_phases": [],
                "paths": {
                    "root": str(pass_root.relative_to(root)).replace("\\", "/"),
                    "inventory": str((pass_root / "inventory.jsonl").relative_to(root)).replace("\\", "/"),
                    "inventory_summary": str((pass_root / "inventory-summary.json").relative_to(root)).replace("\\", "/"),
                    "archive_manifest": str((pass_root / "archive-manifest.jsonl").relative_to(root)).replace("\\", "/"),
                    "prune_manifest": str((pass_root / "prune-manifest.jsonl").relative_to(root)).replace("\\", "/"),
                    "receipt": str((pass_root / "receipt.json").relative_to(root)).replace("\\", "/"),
                },
                "before": before,
                "checkpoints": {},
            }
            state.update(
                {
                    "status": "running",
                    "generation": generation,
                    "active_pass": active,
                    "updated_at": utc_now_iso(),
                }
            )
            _write_reconciliation_state(root, state)

        paths = dict(active.get("paths") or {})
        inventory_file = root / str(paths["inventory"])
        inventory_summary_file = root / str(paths["inventory_summary"])
        archive_file = root / str(paths["archive_manifest"])
        prune_file = root / str(paths["prune_manifest"])
        receipt_file = root / str(paths["receipt"])
        completed = list(active.get("completed_phases") or [])

        def checkpoint(phase: str, details: Mapping[str, Any]) -> None:
            nonlocal active, completed, state
            if phase not in completed:
                completed.append(phase)
            checkpoints = dict(active.get("checkpoints") or {})
            checkpoints[phase] = {
                "completed_at": utc_now_iso(),
                "details": dict(details),
                "details_digest": content_fingerprint(details),
            }
            active.update(
                {
                    "status": "running" if phase != "committed" else "committed",
                    "phase": phase,
                    "updated_at": utc_now_iso(),
                    "completed_phases": completed,
                    "checkpoints": checkpoints,
                }
            )
            state.update(
                {
                    "status": active["status"],
                    "active_pass": active,
                    "updated_at": active["updated_at"],
                }
            )
            _write_reconciliation_state(root, state)

        try:
            if "inventory" not in completed:
                inventory = build_inventory(
                    root,
                    output_path=inventory_file,
                    summary_output_path=inventory_summary_file,
                    migration_id=f"{MIGRATION_ID}:{active['pass_id']}",
                )
                if int(inventory.get("unresolved_count") or 0):
                    raise RuntimeError(
                        "Reconciliation inventory contains unresolved managed artifacts"
                    )
                checkpoint("inventory", inventory)

            if "archive" not in completed:
                archive = archive_inventory(
                    root,
                    inventory_file=inventory_file,
                    archive_manifest_file=archive_file,
                )
                checkpoint("archive", archive)

            if "prune" not in completed:
                prune = prune_inventory(
                    root,
                    archive_manifest_file=archive_file,
                    prune_manifest_file=prune_file,
                )
                if not prune.get("ok"):
                    raise RuntimeError(
                        "Reconciliation pruning blocked: "
                        + "; ".join(str(item) for item in prune.get("blockers", []))
                    )
                checkpoint("prune", prune)

            after = _managed_surface_snapshot(root)
            receipt = {
                "schema_version": 1,
                "migration_id": MIGRATION_ID,
                "pass_id": active["pass_id"],
                "generation": int(active.get("generation") or 0),
                "reason": str(active.get("reason") or reason),
                "status": "committed",
                "committed_at": utc_now_iso(),
                "before": dict(active.get("before") or {}),
                "checkpoints": dict(active.get("checkpoints") or {}),
                "residual_after_pass": after,
            }
            receipt["receipt_digest"] = content_fingerprint(receipt)
            _atomic_write_json(receipt_file, receipt)
            checkpoint("committed", {"receipt_digest": receipt["receipt_digest"]})
            receipt_ref = {
                "pass_id": active["pass_id"],
                "generation": int(active.get("generation") or 0),
                "receipt": str(receipt_file.relative_to(root)).replace("\\", "/"),
                "receipt_digest": receipt["receipt_digest"],
                "committed_at": receipt["committed_at"],
            }
            history = list(state.get("receipt_history") or [])
            if not any(
                str(item.get("receipt_digest") or "") == receipt_ref["receipt_digest"]
                for item in history
                if isinstance(item, Mapping)
            ):
                history.append(receipt_ref)
            state.update(
                {
                    "status": "committed",
                    "active_pass": {},
                    "receipt_history": history,
                    "updated_at": utc_now_iso(),
                }
            )
            _write_reconciliation_state(root, state)
            completed_this_call.append(receipt_ref)
        except Exception as exc:
            failed_at = utc_now_iso()
            active.update(
                {
                    "status": "paused_failed",
                    "phase": "paused_failed",
                    "updated_at": failed_at,
                    "failure": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "failed_at": failed_at,
                    },
                }
            )
            state.update(
                {
                    "status": "paused_failed",
                    "active_pass": active,
                    "updated_at": failed_at,
                }
            )
            _write_reconciliation_state(root, state)
            return {
                "ok": False,
                "status": "paused_failed",
                "reason": reason,
                "pass_count": len(completed_this_call),
                "receipts": completed_this_call,
                "failure": active["failure"],
            }

    residual = _managed_surface_snapshot(root)
    return {
        "ok": int(residual.get("file_count") or 0) == 0,
        "status": "reconciled" if int(residual.get("file_count") or 0) == 0 else "paused_failed",
        "reason": reason,
        "pass_count": len(completed_this_call),
        "receipts": completed_this_call,
        "residual": residual,
        "receipt_history_count": initial_history_count + len(completed_this_call),
        "failure": (
            {}
            if int(residual.get("file_count") or 0) == 0
            else {"type": "ConvergenceLimit", "message": "managed surface kept changing"}
        ),
    }


def model_authority_receipt_path(repo_root: Path) -> Path:
    return migration_root(repo_root) / MODEL_AUTHORITY_RECEIPT_NAME


def upgrade_ai_disposition_path(repo_root: Path) -> Path:
    return (
        Path(repo_root).resolve()
        / ".local"
        / "khaos-brain"
        / "upgrade-ai-dispositions.json"
    )


def _load_upgrade_ai_dispositions(
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    path = upgrade_ai_disposition_path(repo_root)
    if not path.is_file():
        return {}, []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"upgrade AI disposition registry is unreadable: {type(exc).__name__}"]
    if not isinstance(payload, dict) or payload.get("schema_version") != UPGRADE_AI_DISPOSITION_SCHEMA:
        return {}, ["upgrade AI disposition registry schema is not current"]
    rows = payload.get("dispositions")
    if not isinstance(rows, list):
        return {}, ["upgrade AI disposition registry must contain a dispositions list"]
    dispositions: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for index, value in enumerate(rows):
        if not isinstance(value, Mapping):
            issues.append(f"upgrade AI disposition row {index} is not an object")
            continue
        row = dict(value)
        work_item_id = str(row.get("work_item_id") or "")
        if not work_item_id:
            issues.append(f"upgrade AI disposition row {index} has no work_item_id")
            continue
        if work_item_id in dispositions:
            issues.append(f"duplicate upgrade AI disposition: {work_item_id}")
            continue
        claimed_hash = str(row.get("decision_hash") or "")
        expected_hash = "sha256:" + canonical_digest(
            {key: item for key, item in row.items() if key != "decision_hash"}
        )
        if claimed_hash != expected_hash:
            issues.append(f"upgrade AI disposition hash mismatch: {work_item_id}")
            continue
        dispositions[work_item_id] = row
    return dispositions, issues


def _upgrade_ai_disposition_issues(
    disposition: Mapping[str, Any],
    work_item: Mapping[str, Any],
) -> list[str]:
    evidence = dict(work_item.get("evidence") or {})
    expected_evidence_digest = "sha256:" + canonical_digest(evidence)
    issues: list[str] = []
    if disposition.get("status") != "approved":
        issues.append("status is not approved")
    if disposition.get("action") != UPGRADE_AI_DIRECT_CURRENT_ACTION:
        issues.append("action is not the sole direct-current projection rebuild")
    if disposition.get("evidence_digest") != expected_evidence_digest:
        issues.append("evidence digest does not match the open work item")
    if disposition.get("projection_source_digest") != evidence.get(
        "projection_source_digest"
    ):
        issues.append("projection source digest changed")
    if not str(disposition.get("actor") or "").strip():
        issues.append("AI actor is missing")
    if not str(disposition.get("rationale") or "").strip():
        issues.append("AI rationale is missing")
    return issues


def record_upgrade_ai_disposition(
    repo_root: Path,
    *,
    work_item_id: str,
    actor: str,
    rationale: str,
) -> dict[str, Any]:
    """Record one exact AI judgment without changing cards or model authority."""

    root = Path(repo_root).resolve()
    plan = plan_logicguard_native_migration(root)
    open_items = {
        str(item.get("work_item_id") or ""): dict(item)
        for item in plan.get("upgrade_ai_work_items", [])
        if isinstance(item, Mapping)
    }
    existing, registry_issues = _load_upgrade_ai_dispositions(root)
    if registry_issues:
        raise RuntimeError("; ".join(registry_issues))
    if work_item_id in existing and work_item_id not in open_items:
        return {
            "ok": True,
            "status": "already_recorded",
            "disposition": existing[work_item_id],
            "remaining_work_item_ids": sorted(open_items),
        }
    work_item = open_items.get(work_item_id)
    if work_item is None:
        raise ValueError(f"Current upgrade AI work item is unavailable: {work_item_id}")
    if not actor.strip() or not rationale.strip():
        raise ValueError("Upgrade AI disposition requires actor and rationale")
    evidence = dict(work_item.get("evidence") or {})
    disposition: dict[str, Any] = {
        "work_item_id": work_item_id,
        "status": "approved",
        "action": UPGRADE_AI_DIRECT_CURRENT_ACTION,
        "evidence_digest": "sha256:" + canonical_digest(evidence),
        "projection_source_digest": str(
            evidence.get("projection_source_digest") or ""
        ),
        "actor": actor.strip(),
        "rationale": rationale.strip(),
        "approved_at": utc_now_iso(),
    }
    disposition["decision_hash"] = "sha256:" + canonical_digest(disposition)
    existing[work_item_id] = disposition
    registry = {
        "schema_version": UPGRADE_AI_DISPOSITION_SCHEMA,
        "dispositions": [existing[key] for key in sorted(existing)],
        "updated_at": utc_now_iso(),
        "claim_boundary": (
            "This registry contains explicit evidence-bound upgrade-AI judgments only. "
            "It is not a compatibility reader, projection rebind, or normal-runtime authority."
        ),
    }
    path = upgrade_ai_disposition_path(root)
    _atomic_write_json(path, registry)
    resolved_plan = plan_logicguard_native_migration(root)
    remaining = [
        str(item.get("work_item_id") or "")
        for item in resolved_plan.get("upgrade_ai_work_items", [])
        if isinstance(item, Mapping)
    ]
    if work_item_id in remaining:
        raise RuntimeError(
            f"Recorded upgrade AI disposition did not resolve its exact work item: {work_item_id}"
        )
    receipt = {
        "ok": True,
        "status": "recorded",
        "path": str(path),
        "disposition": disposition,
        "resolved_plan_ok": bool(resolved_plan.get("ok")),
        "remaining_work_item_ids": remaining,
    }
    receipt["receipt_hash"] = "sha256:" + canonical_digest(receipt)
    return receipt


def _binding_from_row(value: Mapping[str, Any]) -> LogicGuardBinding:
    return LogicGuardBinding(
        authority_scope=str(value.get("authority_scope") or ""),
        model_id=str(value.get("logicguard_model_id") or ""),
        node_id=str(value.get("logicguard_node_id") or ""),
        block_id=str(value.get("logicguard_block_id") or ""),
        revision_id=str(value.get("logicguard_revision_id") or ""),
        mesh_id=str(value.get("logicguard_mesh_id") or ""),
        mesh_revision_id=str(value.get("logicguard_mesh_revision_id") or ""),
    )


def _current_projection_bootstrap_semantics(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the semantic payload admitted by the versioned bootstrap owner.

    Exact bindings and derived graph display fields identify a prior local
    generation.  They are verified as package evidence, then removed before
    rebuilding the sole current local model authority.  Normal runtime never
    calls this migration-only adapter.
    """

    excluded = {
        "projection_schema_version",
        "projection_digest",
        "related_cards",
        "logicguard_open_role_gaps",
        *PROJECTION_BINDING_FIELDS,
    }
    return {
        str(key): json_safe(item)
        for key, item in value.items()
        if str(key) not in excluded
    }


def _empty_authority_surface_allows_projection_bootstrap(repo_root: Path) -> bool:
    """Accept an absent or read-created empty store, but no partial authority."""

    root = authority_root(repo_root)
    if authority_generation_pointer_path(repo_root).exists():
        return False
    if not root.exists():
        return True
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative.endswith("/models/manifest.json"):
            payload = _load_json(path)
            if (
                int(payload.get("generation") or 0) == 0
                and not payload.get("models")
                and not payload.get("aliases")
                and not payload.get("idempotency")
                and not payload.get("tombstones")
            ):
                continue
        if relative.endswith("/meshes/mesh-manifest.json"):
            payload = _load_json(path)
            if (
                int(payload.get("generation") or 0) == 0
                and not payload.get("meshes")
                and not payload.get("idempotency")
            ):
                continue
        return False
    return True


def _projection_upgrade_ai_work_item(
    *,
    scope: str,
    relative_path: str,
    card_id: str,
    projection_source_digest: str,
    projection_generation_id: str,
    active_generation_id: str,
    binding: LogicGuardBinding,
    blocker: str,
) -> dict[str, Any]:
    """Describe one incompatible projection without resolving it in software.

    This record is evidence for the AI that owns the interrupted upgrade.  It
    deliberately contains no automatic rebind, compatibility reader, or
    fallback action.  A later retry is valid only after that AI adds or selects
    one bounded direct-to-current migration disposition from captured evidence.
    """

    evidence = {
        "scope": scope,
        "path": relative_path,
        "card_id": card_id,
        "projection_source_digest": projection_source_digest,
        "projection_generation_id": projection_generation_id,
        "active_generation_id": active_generation_id,
        "binding": binding.to_dict(),
        "blocker": blocker,
    }
    work_item_digest = canonical_digest(evidence)
    return {
        "work_item_id": f"upgrade-ai-{work_item_digest[:24]}",
        "status": "open",
        "kind": "incompatible-current-projection-authority",
        "evidence": evidence,
        "required_action": (
            "The upgrade AI must derive or add one evidence-bound direct-to-current "
            "migration disposition, then retry inside the rollbackable upgrade transaction."
        ),
        "prohibited_actions": [
            "automatic projection rebind",
            "normal-runtime compatibility reader",
            "YAML or related_cards fallback",
            "alternate model or authority",
            "silent downgrade",
        ],
        "claim_boundary": (
            "This work item proves only that the current projection and active local authority "
            "cannot be accepted together. It does not authorize a migration decision."
        ),
    }


def plan_logicguard_native_migration(repo_root: Path) -> dict[str, Any]:
    """Inventory every managed card through the sole versioned legacy reader."""

    root = Path(repo_root).resolve()
    toolchain = researchguard_logic_dependency_preflight()
    authority_schema_before = authority_schema_inventory(root)
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    schema_cutover_required = bool(
        authority_schema_before.get("cutover_required")
    )
    if authority_schema_before.get("mixed_schema"):
        issues.append(
            "authority contains mixed legacy LogicGuard and current "
            "ResearchGuard logic schemas"
        )
    upgrade_ai_dispositions, disposition_registry_issues = (
        _load_upgrade_ai_dispositions(root)
    )
    issues.extend(disposition_registry_issues)
    applied_upgrade_ai_dispositions: list[dict[str, Any]] = []
    current_generation_ids: set[str] = set()
    seen_scope_ids: set[tuple[str, str]] = set()
    current_projection_items: list[tuple[int, str, dict[str, Any]]] = []
    upgrade_ai_work_items: list[dict[str, Any]] = []
    projection_bootstrap_allowed = _empty_authority_surface_allows_projection_bootstrap(root)
    active_authority_generation: dict[str, Any] = {}
    active_generation_id = ""
    if not projection_bootstrap_allowed and authority_generation_pointer_path(root).exists():
        try:
            active_authority_generation = load_authority_generation(root)
            active_generation_id = str(
                active_authority_generation.get("generation_id") or ""
            )
        except ExactBindingError as exc:
            issues.append(f"current LogicGuard authority pointer is invalid: {exc}")
    for scope, path in _entry_paths(root):
        relative = str(path.relative_to(root)).replace("\\", "/")
        try:
            data = load_yaml_file(path)
        except Exception as exc:
            issues.append(f"{relative}: unreadable card: {type(exc).__name__}: {exc}")
            continue
        card_id = str(data.get("id") or "").strip()
        if not card_id:
            issues.append(f"{relative}: missing card id")
            continue
        identity = (scope, card_id)
        if identity in seen_scope_ids:
            issues.append(f"{relative}: duplicate card id {card_id} in scope {scope}")
            continue
        seen_scope_ids.add(identity)
        projection_source_digest = "sha256:" + _sha256_file(path)
        source_digest = projection_source_digest
        validation: dict[str, Any] = {}
        if str(data.get("projection_schema_version") or "") == CARD_PROJECTION_SCHEMA_VERSION:
            try:
                binding = binding_from_projection(data)
                if str(data.get("projection_digest") or "") != projection_digest(data):
                    raise ProjectionValidationError("Card projection digest mismatch")
                prior_generation_id = str(data.get("authority_generation_id") or "")
                current_generation_ids.add(prior_generation_id)
            except (ProjectionValidationError, ExactBindingError, ValueError) as exc:
                issues.append(f"{relative}: invalid current projection: {exc}")
                continue
            active_scope_mesh = (
                active_authority_generation.get("scope_meshes", {}).get(
                    scope, {}
                )
                if isinstance(
                    active_authority_generation.get("scope_meshes"), Mapping
                )
                else {}
            )
            pointer_authorizes_exact_mesh = bool(
                isinstance(active_scope_mesh, Mapping)
                and str(active_scope_mesh.get("mesh_id") or "")
                == binding.mesh_id
                and str(active_scope_mesh.get("mesh_revision_id") or "")
                == binding.mesh_revision_id
            )
            if schema_cutover_required:
                if (
                    not active_generation_id
                    or prior_generation_id != active_generation_id
                    or not pointer_authorizes_exact_mesh
                ):
                    issues.append(
                        f"{relative}: legacy schema projection is not bound "
                        "to the exact active authority pointer"
                    )
                    continue
                semantic_payload = _current_projection_bootstrap_semantics(data)
                if not _logicguard_migratable(semantic_payload):
                    issues.append(
                        f"{relative}: current projection lacks the "
                        "action/prediction required for direct ResearchGuard "
                        "logic schema cutover"
                    )
                    continue
                disposition = RESEARCHGUARD_LOGIC_SCHEMA_CUTOVER_DISPOSITION
                binding_payload = {}
                source_digest = "sha256:" + canonical_digest(semantic_payload)
            elif projection_bootstrap_allowed:
                semantic_payload = _current_projection_bootstrap_semantics(data)
                if not _logicguard_migratable(semantic_payload):
                    issues.append(
                        f"{relative}: current bootstrap projection lacks the action/prediction required for a LogicGuard root argument"
                    )
                    continue
                disposition = CURRENT_PROJECTION_BOOTSTRAP_DISPOSITION
                binding_payload = {}
                source_digest = "sha256:" + canonical_digest(semantic_payload)
            if (
                not schema_cutover_required
                and not projection_bootstrap_allowed
                and active_generation_id
                and prior_generation_id != active_generation_id
                and not pointer_authorizes_exact_mesh
            ):
                blocker = (
                    "projection authority generation does not equal the active local authority "
                    f"({prior_generation_id or 'missing'} != {active_generation_id})"
                )
                work_item = _projection_upgrade_ai_work_item(
                    scope=scope,
                    relative_path=relative,
                    card_id=card_id,
                    projection_source_digest=projection_source_digest,
                    projection_generation_id=prior_generation_id,
                    active_generation_id=active_generation_id,
                    binding=binding,
                    blocker=blocker,
                )
                approved = upgrade_ai_dispositions.get(
                    str(work_item.get("work_item_id") or "")
                )
                approval_issues = (
                    _upgrade_ai_disposition_issues(approved, work_item)
                    if approved is not None
                    else ["no explicit AI disposition is recorded"]
                )
                if approval_issues:
                    disposition = INCOMPATIBLE_CURRENT_PROJECTION_DISPOSITION
                    binding_payload = binding.to_dict()
                    issues.append(f"{relative}: {blocker}")
                    if approved is not None:
                        issues.append(
                            f"{relative}: invalid upgrade AI disposition: "
                            + "; ".join(approval_issues)
                        )
                    upgrade_ai_work_items.append(work_item)
                else:
                    semantic_payload = _current_projection_bootstrap_semantics(data)
                    if not _logicguard_migratable(semantic_payload):
                        issues.append(
                            f"{relative}: approved current projection lacks the action/prediction required for a LogicGuard root argument"
                        )
                        disposition = INCOMPATIBLE_CURRENT_PROJECTION_DISPOSITION
                        binding_payload = binding.to_dict()
                        upgrade_ai_work_items.append(work_item)
                    else:
                        disposition = UPGRADE_AI_DIRECT_CURRENT_ACTION
                        binding_payload = {}
                        source_digest = "sha256:" + canonical_digest(semantic_payload)
                        applied_upgrade_ai_dispositions.append(dict(approved))
            elif (
                not schema_cutover_required
                and not projection_bootstrap_allowed
            ):
                disposition = "reuse-current-exact-model"
                binding_payload = binding.to_dict()
        else:
            if not _logicguard_migratable(data):
                issues.append(
                    f"{relative}: legacy card lacks the action/prediction required for a LogicGuard root argument"
                )
                continue
            disposition = "direct-legacy-to-logicguard-model"
            binding_payload = {}
            prior_generation_id = ""
        row_index = len(rows)
        rows.append(
            {
                "scope": scope,
                "path": relative,
                "card_id": card_id,
                "source_content_digest": source_digest,
                "projection_source_content_digest": projection_source_digest,
                "disposition": disposition,
                "prior_generation_id": prior_generation_id,
                "binding": binding_payload,
                "projection_validation": validation,
                "legacy_related_cards": (
                    normalize_string_list(data.get("related_cards", []))
                    if disposition == "direct-legacy-to-logicguard-model"
                    else []
                ),
            }
        )
        if disposition == "reuse-current-exact-model":
            current_projection_items.append((row_index, relative, data))

    if current_projection_items:
        try:
            validations = validate_card_projections(
                root,
                [data for _row_index, _relative, data in current_projection_items],
            )
        except (ProjectionValidationError, ExactBindingError, ValueError) as exc:
            issues.append(f"current LogicGuard projections are invalid: {exc}")
            for row_index, relative, data in current_projection_items:
                binding = binding_from_projection(data)
                upgrade_ai_work_items.append(
                    _projection_upgrade_ai_work_item(
                        scope=str(rows[row_index].get("scope") or ""),
                        relative_path=relative,
                        card_id=str(rows[row_index].get("card_id") or ""),
                        projection_source_digest=str(
                            rows[row_index].get("projection_source_content_digest") or ""
                        ),
                        projection_generation_id=str(
                            rows[row_index].get("prior_generation_id") or ""
                        ),
                        active_generation_id=active_generation_id,
                        binding=binding,
                        blocker=str(exc),
                    )
                )
        else:
            for (row_index, _relative, _data), validation in zip(
                current_projection_items,
                validations,
                strict=True,
            ):
                rows[row_index]["projection_validation"] = validation
    module_root = Path(__file__).resolve().parent
    builder_inputs = {
        "logicguard_models.py": "sha256:" + _sha256_file(module_root / "logicguard_models.py"),
        "model_projection.py": "sha256:" + _sha256_file(module_root / "model_projection.py"),
    }
    identity_payload = {
        "schema_version": MODEL_AUTHORITY_MIGRATION_SCHEMA,
        "cards": [
            {
                "scope": row["scope"],
                "path": row["path"],
                "card_id": row["card_id"],
                "source_content_digest": row["source_content_digest"],
                "disposition": row["disposition"],
            }
            for row in rows
        ],
        "researchguard_version": toolchain["version"],
        "researchguard_logic_model_store_schema": toolchain[
            "model_store_schema"
        ],
        "researchguard_logic_model_mesh_schema": toolchain["mesh_schema"],
        "researchguard_logic_mesh_store_tool_fingerprint": toolchain[
            "mesh_store_tool_fingerprint"
        ],
        "authority_schema_before_digest": authority_schema_before[
            "inventory_digest"
        ],
        "builder_inputs": builder_inputs,
    }
    input_digest = "sha256:" + canonical_digest(identity_payload)
    generation_id = f"generation-{input_digest.removeprefix('sha256:')[:32]}"
    current_only = bool(rows) and all(
        row["disposition"] == "reuse-current-exact-model" for row in rows
    )
    return {
        "ok": not issues,
        "schema_version": MODEL_AUTHORITY_MIGRATION_SCHEMA,
        "generation_id": generation_id,
        "input_digest": input_digest,
        "card_count": len(rows),
        "legacy_card_count": sum(
            row["disposition"] == "direct-legacy-to-logicguard-model" for row in rows
        ),
        "bootstrap_projection_count": sum(
            row["disposition"] == CURRENT_PROJECTION_BOOTSTRAP_DISPOSITION for row in rows
        ),
        "schema_cutover_required": schema_cutover_required,
        "schema_cutover_card_count": sum(
            row["disposition"]
            == RESEARCHGUARD_LOGIC_SCHEMA_CUTOVER_DISPOSITION
            for row in rows
        ),
        "upgrade_ai_work_item_count": len(upgrade_ai_work_items),
        "upgrade_ai_work_items": upgrade_ai_work_items,
        "applied_upgrade_ai_disposition_count": len(
            applied_upgrade_ai_dispositions
        ),
        "applied_upgrade_ai_dispositions": applied_upgrade_ai_dispositions,
        "current_card_count": sum(
            row["disposition"] == "reuse-current-exact-model" for row in rows
        ),
        "current_generation_ids": sorted(item for item in current_generation_ids if item),
        "current_only": current_only,
        "rows": rows,
        "toolchain": toolchain,
        "authority_schema_before": authority_schema_before,
        "builder_inputs": builder_inputs,
        "issues": issues,
        "claim_boundary": (
            "This plan is the sole versioned reader of retired standalone card semantics. "
            "It does not authorize any normal-runtime compatibility reader or relation fallback."
        ),
    }


def migrate_cards_to_models(
    repo_root: Path,
    plan: Mapping[str, Any],
    *,
    actor: str = "local_kb.maintenance_migration",
) -> dict[str, Any]:
    if not plan.get("ok"):
        raise RuntimeError("LogicGuard migration plan is blocked: " + "; ".join(plan.get("issues", [])))
    root = Path(repo_root).resolve()
    generation_id = str(plan.get("generation_id") or "")
    output_rows: list[dict[str, Any]] = []
    plan_rows = [dict(row) for row in plan.get("rows", []) if isinstance(row, Mapping)]
    rows_by_scope: dict[str, list[dict[str, Any]]] = {}
    for row in plan_rows:
        rows_by_scope.setdefault(str(row.get("scope") or ""), []).append(row)

    read_stores = {
        scope: open_pinned_model_read_store(root, scope)[0]
        for scope, scope_rows in rows_by_scope.items()
        if any(
            row.get("disposition")
            != RESEARCHGUARD_LOGIC_SCHEMA_CUTOVER_DISPOSITION
            for row in scope_rows
        )
    }
    write_stores: dict[str, Any] = {}
    canonical_head_reuse_count = 0

    for row in plan_rows:
        path = root / str(row.get("path") or "")
        scope = str(row.get("scope") or "")
        data = load_yaml_file(path)
        if (
            row.get("disposition")
            == RESEARCHGUARD_LOGIC_SCHEMA_CUTOVER_DISPOSITION
        ):
            model_input = _current_projection_bootstrap_semantics(data)
            model_store = write_stores.get(scope)
            if model_store is None:
                model_store = open_model_store(root, scope)
                write_stores[scope] = model_store
            committed = commit_card_model(
                root,
                model_input,
                authority_scope=scope,
                expected_revision=None,
                idempotency_key=(
                    f"{generation_id}:researchguard-logic-model:"
                    f"{scope}:{data.get('id')}"
                ),
                actor=actor,
                source_reference=str(row.get("path") or ""),
                model_store=model_store,
            )
            binding = committed.binding
            receipt = committed.receipt
        elif row.get("disposition") == "reuse-current-exact-model":
            if not row.get("projection_validation", {}).get("ok"):
                raise RuntimeError(
                    f"Current projection {row.get('card_id') or row.get('path')} lacks exact plan validation"
                )
            binding = binding_from_projection(data)
            receipt: Mapping[str, Any] = {
                "status": "reused-current",
                "model_id": binding.model_id,
                "revision": binding.revision_id,
            }
        else:
            model_input = (
                _current_projection_bootstrap_semantics(data)
                if row.get("disposition")
                in {
                    CURRENT_PROJECTION_BOOTSTRAP_DISPOSITION,
                    UPGRADE_AI_DIRECT_CURRENT_ACTION,
                }
                else data
            )
            model_id = model_id_for_card(str(data.get("id") or ""))
            committed = reuse_card_model_if_exact(
                model_input,
                authority_scope=scope,
                actor=actor,
                source_reference=str(row.get("path") or ""),
                model_store=read_stores[scope],
            )
            if committed is None:
                model_store = write_stores.get(scope)
                if model_store is None:
                    model_store = open_model_store(root, scope)
                    write_stores[scope] = model_store
                head = model_store.head(model_id)
                committed = commit_card_model(
                    root,
                    model_input,
                    authority_scope=scope,
                    expected_revision=str(head) if head is not None else None,
                    idempotency_key=f"{generation_id}:model:{scope}:{data.get('id')}",
                    actor=actor,
                    source_reference=str(row.get("path") or ""),
                    model_store=model_store,
                )
            else:
                canonical_head_reuse_count += 1
            binding = committed.binding
            receipt = committed.receipt
        output_rows.append(
            {
                **{key: value for key, value in row.items() if key not in {"binding", "projection_validation"}},
                "binding": binding.to_dict(),
                "model_receipt": dict(receipt),
            }
        )
    return {
        "ok": True,
        "generation_id": generation_id,
        "card_count": len(output_rows),
        "schema_cutover_required": bool(
            plan.get("schema_cutover_required")
        ),
        "authority_schema_before": dict(
            plan.get("authority_schema_before") or {}
        ),
        "canonical_head_reuse_count": canonical_head_reuse_count,
        "new_model_commit_count": len(output_rows) - canonical_head_reuse_count - sum(
            1 for row in output_rows if row.get("disposition") == "reuse-current-exact-model"
        ),
        "rows": output_rows,
    }


def _projection_manifest(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "scope": str(row.get("scope") or ""),
                "path": str(row.get("path") or ""),
                "card_id": str(row.get("card_id") or ""),
                "projection_digest": str(row.get("projection", {}).get("projection_digest") or ""),
                **{
                    key: value
                    for key, value in dict(row.get("binding") or {}).items()
                    if key.startswith("logicguard_") or key == "authority_scope"
                },
            }
            for row in rows
        ),
        key=lambda item: (item["scope"], item["path"], item["card_id"]),
    )


def commit_logicguard_native_generation(
    repo_root: Path,
    model_stage: Mapping[str, Any],
    *,
    actor: str = "local_kb.maintenance_migration",
    fail_after_phase: str = "",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generation_id = str(model_stage.get("generation_id") or "")
    rows = [dict(row) for row in model_stage.get("rows", []) if isinstance(row, Mapping)]
    by_scope: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_scope.setdefault(str(row.get("scope") or ""), []).append(row)
    scope_meshes: dict[str, dict[str, Any]] = {}
    projected_rows: list[dict[str, Any]] = []
    for scope, scope_rows in sorted(by_scope.items()):
        bindings = tuple(_binding_from_row(row.get("binding", {})) for row in scope_rows)
        unresolved = tuple(
            {
                "source_card_id": str(row.get("card_id") or ""),
                "suggested_target_ids": normalize_string_list(row.get("legacy_related_cards", [])),
                "disposition": "unresolved-legacy-relation",
                "reason": "Legacy related_cards has no qualifying non-AI relation provenance.",
            }
            for row in scope_rows
            if row.get("disposition") == "direct-legacy-to-logicguard-model"
            and normalize_string_list(row.get("legacy_related_cards", []))
        )
        mesh_store = open_mesh_store(root, scope)
        mesh_head = mesh_store.head(mesh_id_for_scope(scope))
        mesh_result = commit_scope_mesh(
            root,
            authority_scope=scope,
            model_bindings=bindings,
            expected_revision=str(mesh_head) if mesh_head is not None else None,
            idempotency_key=f"{generation_id}:mesh:{scope}",
            actor=actor,
            unresolved_relationships=unresolved,
        )
        scope_meshes[scope] = {
            "mesh_id": mesh_result.mesh_id,
            "mesh_revision_id": mesh_result.mesh_revision_id,
            "content_digest": mesh_result.content_digest,
            "receipt": dict(mesh_result.receipt),
        }
        rebound = {
            (binding.model_id, binding.revision_id): binding
            for binding in mesh_result.bindings
        }
        rebound_rows: list[tuple[dict[str, Any], LogicGuardBinding]] = []
        for row in scope_rows:
            old_binding = _binding_from_row(row.get("binding", {}))
            binding = rebound[(old_binding.model_id, old_binding.revision_id)]
            rebound_rows.append((row, binding))
        projections = project_cards(
            root,
            [binding for _row, binding in rebound_rows],
            authority_generation_id=generation_id,
        )
        for (row, binding), projection in zip(rebound_rows, projections, strict=True):
            projected_rows.append(
                {
                    **row,
                    "binding": binding.to_dict(),
                    "projection": projection,
                }
            )
    if fail_after_phase == "models-meshes":
        raise RuntimeError("Injected failure after models-meshes")
    manifest = _projection_manifest(projected_rows)
    manifest_digest = "sha256:" + canonical_digest(manifest)
    generation = build_authority_generation_payload(
        generation_id=generation_id,
        scope_meshes=scope_meshes,
        projection_manifest_digest=manifest_digest,
        projection_count=len(projected_rows),
        actor=actor,
    )
    write_card_projections_atomic(
        root,
        [
            (root / str(row.get("path") or ""), row["projection"])
            for row in projected_rows
        ],
    )
    if fail_after_phase == "projections":
        raise RuntimeError("Injected failure after projections")
    index_receipt = rebuild_active_index(
        root,
        reason=f"migration:{MIGRATION_ID}:{generation_id}",
        authority_generation=generation,
    )
    if fail_after_phase == "index":
        raise RuntimeError("Injected failure after index")
    published = publish_authority_generation(
        root,
        generation,
        writer="local_kb.maintenance_migration",
    )
    if fail_after_phase == "pointer":
        raise RuntimeError("Injected failure after pointer")
    validation = validate_logicguard_native_authority(
        root,
        require_full_schema_inventory=True,
    )
    if not validation.get("ok"):
        raise RuntimeError(
            "LogicGuard-native authority validation failed: "
            + "; ".join(validation.get("issues", []))
        )
    receipt = {
        "schema_version": MODEL_AUTHORITY_MIGRATION_SCHEMA,
        "migration_id": MIGRATION_ID,
        "status": "committed",
        "generation_id": generation_id,
        "committed_at": utc_now_iso(),
        "card_count": len(projected_rows),
        "projection_manifest": manifest,
        "projection_manifest_digest": manifest_digest,
        "scope_meshes": scope_meshes,
        "authority_generation": published,
        "active_index": index_receipt,
        "validation": validation,
        "authority_schema_before": dict(
            model_stage.get("authority_schema_before") or {}
        ),
        "authority_schema_after": dict(
            validation.get("authority_schema_inventory") or {}
        ),
        "claim_boundary": (
            "This receipt proves direct model/mesh/projection/index generation publication and zero legacy-card "
            "authority residuals for the captured inventory. It does not establish factual truth."
        ),
    }
    receipt["receipt_digest"] = content_fingerprint(receipt)
    _atomic_write_json(model_authority_receipt_path(root), receipt)
    return {"ok": True, "status": "committed", "receipt": receipt}


def migrate_legacy_card_generation(
    repo_root: Path,
    *,
    fail_after_phase: str = "",
    rollback_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    plan = plan_logicguard_native_migration(root)
    if not plan.get("ok"):
        return {
            "ok": False,
            "status": "blocked",
            "plan": plan,
            "issues": list(plan.get("issues", [])),
            "upgrade_ai_work_items": list(plan.get("upgrade_ai_work_items", [])),
        }
    if plan.get("current_only") and len(plan.get("current_generation_ids", [])) == 1:
        try:
            current = load_authority_generation(root)
            validation = validate_logicguard_native_authority(
                root,
                require_full_schema_inventory=True,
            )
        except (ExactBindingError, ProjectionValidationError, ValueError):
            current = {}
            validation = {"ok": False}
        if (
            validation.get("ok")
            and current.get("generation_id") == plan["current_generation_ids"][0]
        ):
            return {
                "ok": True,
                "status": "no_delta",
                "idempotent_no_delta": True,
                "generation_id": current["generation_id"],
                "plan": plan,
                "validation": validation,
            }
    snapshot = dict(rollback_snapshot or _backup_active_surface(root))
    try:
        if plan.get("schema_cutover_required"):
            frozen_before = dict(plan.get("authority_schema_before") or {})
            current_before = authority_schema_inventory(root)
            if (
                not int(
                    current_before.get("legacy_schema_occurrence_count") or 0
                )
                or current_before.get("mixed_schema")
                or str(current_before.get("inventory_digest") or "")
                != str(frozen_before.get("inventory_digest") or "")
                or int(current_before.get("file_count") or 0)
                != int(frozen_before.get("file_count") or 0)
            ):
                raise RuntimeError(
                    "Legacy authority changed after the direct schema-cutover "
                    "inventory was frozen"
                )
            existing_authority = authority_root(root)
            if existing_authority.is_dir():
                shutil.rmtree(existing_authority)
        model_stage = migrate_cards_to_models(root, plan)
        result = commit_logicguard_native_generation(
            root,
            model_stage,
            fail_after_phase=fail_after_phase,
        )
        return {
            **result,
            "idempotent_no_delta": False,
            "plan": plan,
            "model_stage": model_stage,
            "rollback_reference": snapshot,
        }
    except Exception as exc:
        rollback = _restore_active_surface(root, snapshot)
        return {
            "ok": False,
            "status": "rolled_back",
            "error": f"{type(exc).__name__}: {exc}",
            "plan": plan,
            "rollback": rollback,
            "idempotent_no_delta": False,
        }


def validate_logicguard_native_authority(
    repo_root: Path,
    *,
    require_full_schema_inventory: bool = False,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    issues: list[str] = []
    try:
        generation = load_authority_generation(root)
    except ExactBindingError as exc:
        return {"ok": False, "issues": [str(exc)], "card_count": 0}
    manifest_rows: list[dict[str, Any]] = []
    scopes_seen: set[str] = set()
    projection_rows_by_scope: dict[str, list[tuple[str, dict[str, Any], LogicGuardBinding]]] = {}
    for scope, path in _entry_paths(root):
        relative = str(path.relative_to(root)).replace("\\", "/")
        try:
            data = load_yaml_file(path)
            if "then" in data:
                raise ProjectionValidationError("retired then field remains")
            binding = binding_from_projection(data)
            if str(data.get("authority_generation_id") or "") != str(generation.get("generation_id") or ""):
                raise ProjectionValidationError("projection binds a non-current authority generation")
            scope_mesh = generation.get("scope_meshes", {}).get(scope, {})
            if (
                binding.mesh_id != str(scope_mesh.get("mesh_id") or "")
                or binding.mesh_revision_id != str(scope_mesh.get("mesh_revision_id") or "")
            ):
                raise ProjectionValidationError("projection mesh binding differs from current scoped generation")
            scopes_seen.add(scope)
            projection_rows_by_scope.setdefault(scope, []).append((relative, data, binding))
        except Exception as exc:
            issues.append(f"{relative}: {type(exc).__name__}: {exc}")
    for scope, rows in sorted(projection_rows_by_scope.items()):
        try:
            validations = validate_card_projections(root, [data for _path, data, _binding in rows])
        except Exception as exc:
            issues.append(f"{scope}: {type(exc).__name__}: {exc}")
            continue
        for (relative, data, _binding), validation in zip(rows, validations, strict=True):
            manifest_rows.append(
                {
                    "scope": scope,
                    "path": relative,
                    "card_id": str(data.get("id") or ""),
                    "projection_digest": str(data.get("projection_digest") or ""),
                    **validation["binding"],
                }
            )
    manifest = sorted(manifest_rows, key=lambda item: (item["scope"], item["path"], item["card_id"]))
    manifest_digest = "sha256:" + canonical_digest(manifest)
    if manifest_digest != str(generation.get("projection_manifest_digest") or ""):
        issues.append("current projection manifest digest mismatch")
    if len(manifest) != int(generation.get("projection_count") or 0):
        issues.append("current projection count mismatch")
    missing_scope_meshes = scopes_seen - set(generation.get("scope_meshes", {}))
    if missing_scope_meshes:
        issues.append("current authority lacks scoped meshes: " + ", ".join(sorted(missing_scope_meshes)))
    active_index = validate_active_index(root)
    if not active_index.get("ok"):
        issues.extend(f"active-index: {item}" for item in active_index.get("issues", []))
    schema_inventory: dict[str, Any] = {}
    if require_full_schema_inventory:
        schema_inventory = authority_schema_inventory(root)
        if int(schema_inventory.get("legacy_schema_occurrence_count") or 0):
            issues.append(
                "legacy LogicGuard authority schema residuals remain after "
                "ResearchGuard logic cutover"
            )
        if manifest and not int(
            schema_inventory.get("current_schema_occurrence_count") or 0
        ):
            issues.append(
                "ResearchGuard logic authority schema is absent from the "
                "current model/mesh store"
            )
    return {
        "ok": not issues,
        "generation_id": str(generation.get("generation_id") or ""),
        "generation_digest": str(generation.get("pointer_digest") or ""),
        "card_count": len(manifest),
        "projection_manifest_digest": manifest_digest,
        "scope_count": len(scopes_seen),
        "active_index": active_index,
        "authority_schema_inventory": schema_inventory,
        "zero_legacy_authority_schema_residuals": bool(
            not schema_inventory
            or not int(
                schema_inventory.get("legacy_schema_occurrence_count") or 0
            )
        ),
        "zero_legacy_projection_residuals": not issues,
        "issues": issues,
    }


def validate_migration(repo_root: Path) -> dict[str, Any]:
    lifecycle = validate_lifecycle(repo_root)
    active_index = validate_active_index(repo_root)
    logicguard_authority = validate_logicguard_native_authority(
        repo_root,
        require_full_schema_inventory=True,
    )
    archive_integrity_issues: list[str] = []
    verified_archive_digests: set[str] = set()
    for item in _read_jsonl(archive_manifest_path(repo_root)):
        if str(item.get("classification") or "") == "cold":
            digest = str(item.get("sha256") or "")
            if digest in verified_archive_digests:
                continue
            if not _verify_cold_object(repo_root, item):
                archive_integrity_issues.append(str(item.get("path") or ""))
                if len(archive_integrity_issues) >= 20:
                    break
            else:
                verified_archive_digests.add(digest)
    # This scan is deliberately last: a writer that reintroduces managed debt
    # while cold objects are being verified must invalidate the same run.
    residual = _managed_surface_snapshot(repo_root)
    issues: list[str] = []
    if not lifecycle.get("ok"):
        issues.extend(f"lifecycle: {item}" for item in lifecycle.get("issues", []))
    if not active_index.get("ok"):
        issues.extend(f"active-index: {item}" for item in active_index.get("issues", []))
    if not logicguard_authority.get("ok"):
        issues.extend(
            f"logicguard-authority: {item}"
            for item in logicguard_authority.get("issues", [])
        )
    if int(residual.get("file_count") or 0):
        issues.append(
            f"residual managed physical debt: {int(residual.get('file_count') or 0)} files"
        )
    if archive_integrity_issues:
        issues.append(f"cold archive integrity failures: {len(archive_integrity_issues)}")
    state = load_lifecycle_state(repo_root)
    hard_debt = [
        item_id
        for item_id, item in state.get("observations", {}).items()
        if str(item.get("state") or "") in {"new", "missing-admission"}
    ]
    if hard_debt:
        issues.append(f"unsettled observation debt: {len(hard_debt)}")
    journal = _load_journal(repo_root)
    settlement_details = (
        journal.get("checkpoints", {})
        .get("settle-logical-debt", {})
        .get("details", {})
    )
    queue_details = (
        settlement_details.get("retired_architect_queue", {})
        if isinstance(settlement_details, Mapping)
        else {}
    )
    carryforward_details = journal.get("retired_architect_carryforward", {})
    settlement_rows = list(_read_jsonl(retired_architect_settlement_path(repo_root)))
    expected_proposals = int(queue_details.get("proposal_count") or 0) if isinstance(queue_details, Mapping) else 0
    if isinstance(carryforward_details, Mapping):
        expected_proposals = max(
            expected_proposals,
            int(carryforward_details.get("proposal_count") or 0),
        )
    if len(settlement_rows) != expected_proposals:
        issues.append(
            f"retired Architect proposal settlement mismatch: expected {expected_proposals}, found {len(settlement_rows)}"
        )
    invalid_settlements = [
        str(row.get("proposal_id") or "")
        for row in settlement_rows
        if str(row.get("disposition") or "") not in {"history_only", "parked"}
        or (
            str(row.get("disposition") or "") == "parked"
            and not isinstance(row.get("reopen_condition"), Mapping)
        )
    ]
    if invalid_settlements:
        issues.append(f"invalid retired proposal settlements: {len(invalid_settlements)}")
    return {
        "ok": not issues,
        "lifecycle": lifecycle,
        "active_index": active_index,
        "logicguard_authority": logicguard_authority,
        "residual_managed_file_count": int(residual.get("file_count") or 0),
        "residual_managed_byte_count": int(residual.get("byte_count") or 0),
        "residual_managed_file_sample": list(residual.get("sample") or []),
        "archive_integrity_issue_sample": archive_integrity_issues,
        "hard_debt_count": len(hard_debt),
        "retired_proposal_settlement_count": len(settlement_rows),
        "retired_proposal_parked_count": sum(
            1 for row in settlement_rows if str(row.get("disposition") or "") == "parked"
        ),
        "retired_proposal_settlement_invalid_sample": invalid_settlements[:20],
        "issues": issues,
    }


def converge_precommit_migration(
    repo_root: Path,
    *,
    max_passes: int = 6,
) -> dict[str, Any]:
    """Close bounded concurrent observation drift before migration commit."""

    root = Path(repo_root).resolve()
    passes: list[dict[str, Any]] = []
    for attempt in range(1, max_passes + 1):
        lifecycle_state = load_lifecycle_state(root)
        hard_before = sorted(
            item_id
            for item_id, item in lifecycle_state.get("observations", {}).items()
            if str(item.get("state") or "") in {"new", "missing-admission"}
        )
        settlement: dict[str, Any] | None = None
        authority: dict[str, Any] | None = None
        index: dict[str, Any] | None = None
        if hard_before:
            settlement = settle_knowledge_debt(
                root,
                run_id=f"{MIGRATION_ID}:precommit-logical-{attempt:02d}",
            )
            if (
                not settlement.get("lifecycle_validation", {}).get("ok")
                or int(settlement.get("hard_observation_debt_count") or 0)
            ):
                return {
                    "ok": False,
                    "status": "paused_failed",
                    "pass_count": len(passes),
                    "passes": passes,
                    "failure": {
                        "type": "LogicalSettlementBlocked",
                        "message": "precommit observation debt did not settle",
                    },
                }
            authority = migrate_legacy_card_generation(root)
            if not authority.get("ok"):
                return {
                    "ok": False,
                    "status": "paused_failed",
                    "pass_count": len(passes),
                    "passes": passes,
                    "failure": {
                        "type": "LogicGuardAuthorityConvergenceBlocked",
                        "message": str(
                            authority.get("error")
                            or authority.get("issues")
                            or authority.get("status")
                        ),
                    },
                }
            index = rebuild_active_index(
                root,
                reason=f"precommit-convergence:{MIGRATION_ID}:{attempt}",
            )

        physical = reconcile_managed_surface(
            root,
            reason=f"pre-validate:{MIGRATION_ID}:{attempt}",
        )
        if not physical.get("ok"):
            return {
                "ok": False,
                "status": "paused_failed",
                "pass_count": len(passes),
                "passes": passes,
                "failure": {
                    "type": "ManagedSurfaceConvergenceBlocked",
                    "message": str(physical.get("failure") or physical.get("status")),
                },
            }
        validation = validate_migration(root)
        pass_receipt = {
            "attempt": attempt,
            "hard_observation_debt_before": hard_before,
            "settlement": settlement,
            "authority_generation": authority,
            "active_index": index,
            "managed_surface_reconciliation": physical,
            "validation": validation,
            "ok_after": bool(validation.get("ok")),
        }
        passes.append(pass_receipt)
        if validation.get("ok"):
            return {
                "ok": True,
                "status": "converged" if attempt > 1 or hard_before else "no_delta",
                "pass_count": len(passes),
                "passes": passes,
                "validation": validation,
            }
        non_observation_issues = [
            issue
            for issue in validation.get("issues", [])
            if not str(issue).startswith("unsettled observation debt:")
        ]
        if non_observation_issues:
            return {
                "ok": False,
                "status": "paused_failed",
                "pass_count": len(passes),
                "passes": passes,
                "failure": {
                    "type": "MigrationValidationBlocked",
                    "message": "; ".join(non_observation_issues),
                },
            }
    return {
        "ok": False,
        "status": "paused_failed",
        "pass_count": len(passes),
        "passes": passes,
        "failure": {
            "type": "ObservationConvergenceLimit",
            "message": "concurrent observation debt did not quiesce within the bounded pass limit",
        },
    }


def check_migration_current_authority(repo_root: Path) -> dict[str, Any]:
    """Read the bounded committed migration authority without revalidation.

    This is the installation-currentness owner. It verifies the exact state,
    journal checkpoint, and immutable receipt binding only. Full lifecycle,
    index, LogicGuard, archive, and residual validation remains owned by
    ``check_migration`` during an affected assurance or upgrade.
    """

    state = load_maintenance_state(repo_root)
    journal = _load_journal(repo_root)
    receipt = _load_json(migration_receipt_path(repo_root))
    issues: list[str] = []
    stored_digest = str(receipt.get("receipt_digest") or "")
    unsigned_receipt = {
        key: value for key, value in receipt.items() if key != "receipt_digest"
    }
    calculated_digest = (
        content_fingerprint(unsigned_receipt) if receipt else ""
    )
    committed_checkpoint = (
        journal.get("checkpoints", {}).get("committed", {})
        if isinstance(journal.get("checkpoints"), Mapping)
        else {}
    )
    checkpoint_details = (
        committed_checkpoint.get("details", {})
        if isinstance(committed_checkpoint, Mapping)
        else {}
    )
    expected_receipt_path = str(
        migration_receipt_path(repo_root).relative_to(repo_root)
    ).replace("\\", "/")
    source_version = (
        (Path(repo_root) / "VERSION").read_text(encoding="utf-8").strip()
        if (Path(repo_root) / "VERSION").is_file()
        else ""
    )
    if state.get("committed") is not True or state.get("phase") != "committed":
        issues.append("maintenance state is not committed")
    if state.get("migration_id") != MIGRATION_ID:
        issues.append("maintenance state migration id is not current")
    if state.get("migration_receipt") != expected_receipt_path:
        issues.append("maintenance state does not bind the current receipt path")
    if str(state.get("software_version") or "") != source_version:
        issues.append("maintenance state software version is stale")
    if journal.get("status") != "committed" or journal.get("phase") != "committed":
        issues.append("migration journal is not committed")
    if journal.get("migration_id") != MIGRATION_ID:
        issues.append("migration journal id is not current")
    if journal.get("failure"):
        issues.append("migration journal retains an active failure")
    if receipt.get("status") != "committed":
        issues.append("migration receipt is not committed")
    if receipt.get("migration_id") != MIGRATION_ID:
        issues.append("migration receipt id is not current")
    if not stored_digest or stored_digest != calculated_digest:
        issues.append("migration receipt digest is invalid")
    if str(state.get("receipt_digest") or "") != stored_digest:
        issues.append("maintenance state receipt digest binding is stale")
    if str(checkpoint_details.get("receipt_digest") or "") != stored_digest:
        issues.append("migration journal receipt digest binding is stale")
    return {
        "ok": not issues,
        "status": "current" if not issues else "stale",
        "migration_id": MIGRATION_ID,
        "receipt_path": expected_receipt_path,
        "receipt_digest": stored_digest,
        "issues": issues,
        "claim_boundary": (
            "Bounded read-only committed-authority check. It does not execute "
            "migration or repeat lifecycle, index, LogicGuard, archive, or "
            "residual validation."
        ),
    }


def check_migration(repo_root: Path) -> dict[str, Any]:
    state = load_maintenance_state(repo_root)
    journal = _load_journal(repo_root)
    receipt = _load_json(migration_receipt_path(repo_root))
    validation = validate_migration(repo_root) if receipt else {
        "ok": False,
        "issues": ["migration receipt is missing"],
    }
    active_failure = journal.get("failure")
    issues = list(validation.get("issues", []))
    if active_failure:
        issues.append("migration journal retains an active failure")
    ok = bool(
        state.get("committed")
        and str(state.get("phase") or "") == "committed"
        and journal.get("status") == "committed"
        and receipt.get("status") == "committed"
        and validation.get("ok")
        and not active_failure
    )
    return {
        "ok": ok,
        "migration_id": MIGRATION_ID,
        "maintenance_state": state,
        "journal": journal,
        "receipt": receipt,
        "validation": validation,
        "issues": [] if ok else issues,
    }


def run_maintenance_migration(
    repo_root: Path,
    *,
    fail_after_phase: str = "",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    with migration_lock(root):
        journal = _load_journal(root)
        if journal.get("status") == "committed":
            if _resolve_active_failure(journal):
                journal["updated_at"] = utc_now_iso()
                _atomic_write_json(journal_path(root), journal)
            retired_carryforward = settle_retired_architect_queue(root)
            main_retired_count = int(
                journal.get("checkpoints", {})
                .get("settle-logical-debt", {})
                .get("details", {})
                .get("retired_architect_queue", {})
                .get("proposal_count", 0)
                or 0
            )
            if int(retired_carryforward.get("proposal_count") or 0) > main_retired_count:
                journal.update(
                    {
                        "retired_architect_carryforward": retired_carryforward,
                        "updated_at": utc_now_iso(),
                    }
                )
                _atomic_write_json(journal_path(root), journal)
            check = check_migration(root)
            reconciliation: dict[str, Any] = {
                "ok": True,
                "status": "not_needed",
                "pass_count": 0,
                "receipts": [],
            }
            logical_reconciliation: dict[str, Any] = {
                "ok": True,
                "status": "not_needed",
                "pass_count": 0,
                "receipts": [],
            }
            physical_receipts: list[dict[str, Any]] = []
            logical_receipts: list[dict[str, Any]] = []
            convergence_runs: list[dict[str, Any]] = []
            known_physical_receipts = list(
                _load_reconciliation_state(root).get("receipt_history") or []
            )
            for convergence_attempt in range(1, 5):
                if check.get("ok"):
                    break
                validation = dict(check.get("validation") or {})
                residual_count = int(
                    validation.get("residual_managed_file_count") or 0
                )
                hard_debt_count = int(validation.get("hard_debt_count") or 0)
                authority_repair_required = not bool(
                    dict(validation.get("logicguard_authority") or {}).get("ok")
                )
                index_repair_required = not bool(
                    dict(validation.get("active_index") or {}).get("ok")
                )
                progressed = False
                physical_result: dict[str, Any] = {
                    "ok": True,
                    "status": "not_needed",
                    "pass_count": 0,
                    "receipts": [],
                }
                logical_settlement: dict[str, Any] | None = None

                if residual_count:
                    physical_result = reconcile_managed_surface(
                        root,
                        reason=f"post-commit-drift:{MIGRATION_ID}",
                    )
                    if not physical_result.get("ok"):
                        reconciliation = physical_result
                        break
                    progressed = progressed or bool(
                        physical_result.get("pass_count")
                    )
                    for item in physical_result.get("receipts", []):
                        if item not in physical_receipts:
                            physical_receipts.append(item)

                if hard_debt_count:
                    logical_settlement = settle_knowledge_debt(
                        root,
                        run_id=(
                            f"{MIGRATION_ID}:post-commit-logical-"
                            f"{convergence_attempt:02d}"
                        ),
                    )
                    if (
                        not logical_settlement.get("lifecycle_validation", {}).get(
                            "ok"
                        )
                        or int(
                            logical_settlement.get(
                                "hard_observation_debt_count"
                            )
                            or 0
                        )
                    ):
                        logical_reconciliation = {
                            "ok": False,
                            "status": "paused_failed",
                            "pass_count": len(logical_receipts),
                            "receipts": logical_receipts,
                            "failure": {
                                "type": "LogicalSettlementBlocked",
                                "message": "post-commit observation debt did not settle",
                            },
                        }
                        break
                    progressed = True

                # A writer can publish a new sole authority generation while a
                # long-running upgrade is between its projection/index phases.
                # That drift has no physical residual or observation debt, but
                # it still requires the same direct-to-current convergence.
                progressed = progressed or authority_repair_required or index_repair_required

                if not progressed:
                    break

                authority_convergence = migrate_legacy_card_generation(root)
                if not authority_convergence.get("ok"):
                    logical_reconciliation = {
                        "ok": False,
                        "status": "paused_failed",
                        "pass_count": len(logical_receipts),
                        "receipts": logical_receipts,
                        "failure": {
                            "type": "LogicGuardAuthorityConvergenceBlocked",
                            "message": str(
                                authority_convergence.get("error")
                                or authority_convergence.get("issues")
                                or authority_convergence.get("status")
                            ),
                        },
                    }
                    break
                rebuild_active_index(
                    root,
                    reason=f"post-commit-convergence:{MIGRATION_ID}:{convergence_attempt}",
                )
                check = check_migration(root)

                if logical_settlement is not None:
                    logical_root = logical_reconciliation_root(root)
                    logical_root.mkdir(parents=True, exist_ok=True)
                    existing_receipts = sorted(logical_root.glob("receipt-*.json"))
                    generation = len(existing_receipts) + 1
                    logical_receipt_path = (
                        logical_root / f"receipt-{generation:06d}.json"
                    )
                    logical_receipt = {
                        "schema_version": 1,
                        "migration_id": MIGRATION_ID,
                        "generation": generation,
                        "status": "committed",
                        "reason": "post-commit-observation-debt",
                        "committed_at": utc_now_iso(),
                        "before_hard_debt_count": hard_debt_count,
                        "settlement": logical_settlement,
                        "validation_after": dict(check.get("validation") or {}),
                    }
                    logical_receipt["receipt_digest"] = content_fingerprint(
                        logical_receipt
                    )
                    _atomic_write_json(logical_receipt_path, logical_receipt)
                    logical_ref = {
                        "generation": generation,
                        "receipt": str(logical_receipt_path.relative_to(root)).replace(
                            "\\", "/"
                        ),
                        "receipt_digest": logical_receipt["receipt_digest"],
                        "committed_at": logical_receipt["committed_at"],
                        "before_hard_debt_count": hard_debt_count,
                        "remaining_hard_debt_count": int(
                            check.get("validation", {}).get("hard_debt_count") or 0
                        ),
                    }
                    logical_receipts.append(logical_ref)

                convergence_runs.append(
                    {
                        "attempt": convergence_attempt,
                        "physical": physical_result,
                        "logical_settlement_ran": logical_settlement is not None,
                        "authority_repair_required": authority_repair_required,
                        "index_repair_required": index_repair_required,
                        "ok_after": bool(check.get("ok")),
                    }
                )

            if physical_receipts:
                reconciliation = {
                    "ok": True,
                    "status": "reconciled",
                    "pass_count": len(physical_receipts),
                    "receipts": physical_receipts,
                }
            if logical_receipts and logical_reconciliation.get("ok"):
                logical_reconciliation = {
                    "ok": True,
                    "status": "reconciled",
                    "pass_count": len(logical_receipts),
                    "receipts": logical_receipts,
                }

            physical_history = list(
                journal.get("post_commit_reconciliations") or []
            )
            for item in known_physical_receipts + physical_receipts:
                if item not in physical_history:
                    physical_history.append(item)
            logical_history = list(
                journal.get("post_commit_logical_reconciliations") or []
            )
            for item in logical_receipts:
                if item not in logical_history:
                    logical_history.append(item)
            if known_physical_receipts or physical_receipts or logical_receipts:
                journal.update(
                    {
                        "post_commit_reconciliations": physical_history,
                        "post_commit_logical_reconciliations": logical_history,
                        "updated_at": utc_now_iso(),
                    }
                )
                _atomic_write_json(journal_path(root), journal)

            reconciled_any = bool(
                physical_receipts or logical_receipts or convergence_runs
            )
            if check.get("ok"):
                source_version = (
                    (root / "VERSION").read_text(encoding="utf-8").strip()
                    if (root / "VERSION").is_file()
                    else ""
                )
                current_state = dict(check.get("maintenance_state") or {})
                if str(current_state.get("software_version") or "") != source_version:
                    current_state["software_version"] = source_version
                    current_state["updated_at"] = utc_now_iso()
                    write_maintenance_state(root, current_state)
                    check = {**check, "maintenance_state": current_state}
            return {
                **check,
                "status": (
                    "reconciled"
                    if check.get("ok") and reconciled_any
                    else "no_delta"
                    if check.get("ok")
                    else "paused_failed"
                ),
                "idempotent_no_delta": bool(
                    check.get("ok") and not reconciled_any
                ),
                "managed_surface_reconciliation": reconciliation,
                "logical_debt_reconciliation": logical_reconciliation,
                "post_commit_convergence_runs": convergence_runs,
            }
        try:
            live_locks = _live_lane_locks(root)
            if live_locks:
                raise RuntimeError("Managed maintenance writers are active: " + ", ".join(live_locks))
            if "preflight" not in journal.get("completed_phases", []):
                journal = _checkpoint(
                    root,
                    journal,
                    "preflight",
                    {
                        "live_lane_locks": live_locks,
                        "source_versions": journal["source_versions"],
                        "target_versions": journal["target_versions"],
                    },
                )
                if fail_after_phase == "preflight":
                    raise RuntimeError("Injected failure after preflight")

            if "snapshot" not in journal.get("completed_phases", []):
                snapshot = _backup_active_surface(root)
                journal = _checkpoint(root, journal, "snapshot", snapshot)
                if fail_after_phase == "snapshot":
                    raise RuntimeError("Injected failure after snapshot")

            if "classify" not in journal.get("completed_phases", []):
                inventory = build_inventory(root)
                if int(inventory.get("unresolved_count") or 0):
                    raise RuntimeError(
                        f"Inventory contains {inventory['unresolved_count']} unresolved managed artifacts"
                    )
                journal = _checkpoint(root, journal, "classify", inventory)
                if fail_after_phase == "classify":
                    raise RuntimeError("Injected failure after classify")

            if "canonicalize-runtime" not in journal.get("completed_phases", []):
                canonicalization = canonicalize_runtime_state(root)
                if int(canonicalization.get("residual_obsolete_input_count") or 0):
                    raise RuntimeError("Runtime canonicalization left obsolete inputs")
                journal = _checkpoint(root, journal, "canonicalize-runtime", canonicalization)
                if fail_after_phase == "canonicalize-runtime":
                    raise RuntimeError("Injected failure after canonicalize-runtime")

            if "settle-logical-debt" not in journal.get("completed_phases", []):
                settlement = settle_knowledge_debt(root, run_id=MIGRATION_ID)
                if not settlement.get("lifecycle_validation", {}).get("ok") or int(
                    settlement.get("hard_observation_debt_count") or 0
                ):
                    raise RuntimeError("Knowledge-debt settlement left lifecycle blockers")
                journal = _checkpoint(root, journal, "settle-logical-debt", settlement)
                if fail_after_phase == "settle-logical-debt":
                    raise RuntimeError("Injected failure after settle-logical-debt")

            if "migrate-logicguard-authority" not in journal.get("completed_phases", []):
                snapshot = (
                    journal.get("checkpoints", {})
                    .get("snapshot", {})
                    .get("details", {})
                )
                injected_subphase = ""
                if fail_after_phase.startswith("migrate-logicguard-authority:"):
                    injected_subphase = fail_after_phase.split(":", 1)[1]
                model_authority = migrate_legacy_card_generation(
                    root,
                    fail_after_phase=injected_subphase,
                    rollback_snapshot=snapshot,
                )
                if not model_authority.get("ok"):
                    work_item_ids = [
                        str(item.get("work_item_id") or "")
                        for item in model_authority.get(
                            "upgrade_ai_work_items", []
                        )
                        if isinstance(item, Mapping)
                    ]
                    raise RuntimeError(
                        "LogicGuard authority migration failed: "
                        + str(
                            model_authority.get("error")
                            or model_authority.get("issues")
                            or model_authority.get("status")
                        )
                        + (
                            "; upgrade_ai_work_item_ids="
                            + ",".join(item for item in work_item_ids if item)
                            if work_item_ids
                            else ""
                        )
                    )
                journal = _checkpoint(
                    root,
                    journal,
                    "migrate-logicguard-authority",
                    model_authority,
                )
                if fail_after_phase == "migrate-logicguard-authority":
                    raise RuntimeError("Injected failure after migrate-logicguard-authority")

            if "archive-cold-evidence" not in journal.get("completed_phases", []):
                archive = archive_inventory(root)
                journal = _checkpoint(root, journal, "archive-cold-evidence", archive)
                if fail_after_phase == "archive-cold-evidence":
                    raise RuntimeError("Injected failure after archive-cold-evidence")

            if "prune-derived-data" not in journal.get("completed_phases", []):
                prune = prune_inventory(root)
                if not prune.get("ok"):
                    raise RuntimeError("Physical pruning blocked: " + "; ".join(prune.get("blockers", [])))
                journal = _checkpoint(root, journal, "prune-derived-data", prune)
                if fail_after_phase == "prune-derived-data":
                    raise RuntimeError("Injected failure after prune-derived-data")

            if "rebuild-index" not in journal.get("completed_phases", []):
                index = rebuild_active_index(root, reason=f"migration:{MIGRATION_ID}")
                journal = _checkpoint(root, journal, "rebuild-index", index)
                if fail_after_phase == "rebuild-index":
                    raise RuntimeError("Injected failure after rebuild-index")

            if "validate" not in journal.get("completed_phases", []):
                convergence = converge_precommit_migration(root)
                if not convergence.get("ok"):
                    raise RuntimeError(
                        "Precommit migration convergence failed: "
                        + str(convergence.get("failure") or convergence.get("status"))
                    )
                validation = dict(convergence.get("validation") or {})
                validation["precommit_convergence"] = convergence
                if not validation.get("ok"):
                    raise RuntimeError("Migration validation failed: " + "; ".join(validation.get("issues", [])))
                journal = _checkpoint(root, journal, "validate", validation)
                if fail_after_phase == "validate":
                    raise RuntimeError("Injected failure after validate")

            inventory = _load_json(inventory_summary_path(root))
            prune_checkpoint = journal.get("checkpoints", {}).get("prune-derived-data", {}).get("details", {})
            receipt = {
                "schema_version": MIGRATION_SCHEMA_VERSION,
                "migration_id": MIGRATION_ID,
                "status": "committed",
                "committed_at": utc_now_iso(),
                "source_versions": journal["source_versions"],
                "target_versions": journal["target_versions"],
                "migration_order": list(MIGRATION_PHASES),
                "checkpoints": journal.get("checkpoints", {}),
                "inventory_digest": str(inventory.get("inventory_digest") or ""),
                "before_file_count": int(inventory.get("file_count") or 0),
                "before_byte_count": int(inventory.get("byte_count") or 0),
                "deleted_file_count": int(prune_checkpoint.get("deleted_file_count") or 0),
                "deleted_byte_count": int(prune_checkpoint.get("deleted_byte_count") or 0),
                "active_index": journal.get("checkpoints", {}).get("rebuild-index", {}).get("details", {}),
                "residual_debt": [],
                "rollback_reference": journal.get("checkpoints", {}).get("snapshot", {}).get("details", {}),
                "final_validation": journal.get("checkpoints", {}).get("validate", {}).get("details", {}),
            }
            receipt["receipt_digest"] = content_fingerprint(receipt)
            _atomic_write_json(migration_receipt_path(root), receipt)
            write_maintenance_state(
                root,
                {
                    "software_version": (root / "VERSION").read_text(encoding="utf-8").strip() if (root / "VERSION").exists() else "",
                    "maintenance_standard_version": CURRENT_MAINTENANCE_STANDARD_VERSION,
                    "history_schema_version": CURRENT_HISTORY_SCHEMA_VERSION,
                    "phase": "committed",
                    "committed": True,
                    "migration_id": MIGRATION_ID,
                    "migration_receipt": str(migration_receipt_path(root).relative_to(root)).replace("\\", "/"),
                    "receipt_digest": receipt["receipt_digest"],
                    "updated_at": utc_now_iso(),
                },
            )
            journal = _checkpoint(root, journal, "committed", {"receipt_digest": receipt["receipt_digest"]})
            return {
                "ok": True,
                "status": "committed",
                "migration_id": MIGRATION_ID,
                "receipt": receipt,
                "journal": journal,
                "idempotent_no_delta": False,
            }
        except Exception as exc:
            failed_at = utc_now_iso()
            completed_before_rollback = list(journal.get("completed_phases") or [])
            resume_from = next(
                (
                    phase
                    for phase in MIGRATION_PHASES
                    if phase not in set(completed_before_rollback)
                ),
                "validate",
            )
            snapshot = (
                journal.get("checkpoints", {})
                .get("snapshot", {})
                .get("details", {})
            )
            rollback: dict[str, Any] = {}
            if snapshot:
                try:
                    rollback = _restore_active_surface(root, snapshot)
                except Exception as rollback_exc:
                    rollback = {
                        "ok": False,
                        "error": f"{type(rollback_exc).__name__}: {rollback_exc}",
                    }
            if rollback.get("ok"):
                invalidated_phases = [
                    phase
                    for phase in completed_before_rollback
                    if phase in MIGRATION_PHASES[
                        MIGRATION_PHASES.index("canonicalize-runtime") :
                    ]
                ]
                invalidated_checkpoints = {
                    phase: journal.get("checkpoints", {}).get(phase, {})
                    for phase in invalidated_phases
                    if phase in journal.get("checkpoints", {})
                }
                rollback_history = list(journal.get("rollback_history") or [])
                rollback_history.append(
                    {
                        "rolled_back_at": failed_at,
                        "failed_phase": resume_from,
                        "invalidated_phases": invalidated_phases,
                        "invalidated_checkpoints": invalidated_checkpoints,
                        "rollback": rollback,
                    }
                )
                journal["rollback_history"] = rollback_history
                journal["completed_phases"] = [
                    phase
                    for phase in completed_before_rollback
                    if phase not in invalidated_phases
                ]
                journal["checkpoints"] = {
                    phase: details
                    for phase, details in dict(journal.get("checkpoints") or {}).items()
                    if phase not in invalidated_phases
                }
            journal.update(
                {
                    "status": "paused_failed",
                    "phase": "paused_failed",
                    "updated_at": failed_at,
                    "failure": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "failed_at": failed_at,
                        "rollback": rollback,
                        "resume_from": resume_from,
                    },
                }
            )
            _atomic_write_json(journal_path(root), journal)
            write_maintenance_state(
                root,
                {
                    "maintenance_standard_version": int(journal.get("source_versions", {}).get("maintenance_standard_version") or 0),
                    "history_schema_version": int(journal.get("source_versions", {}).get("history_schema_version") or 0),
                    "phase": "paused_failed",
                    "committed": False,
                    "migration_id": MIGRATION_ID,
                    "failure": journal["failure"],
                    "updated_at": utc_now_iso(),
                },
            )
            return {
                "ok": False,
                "status": "paused_failed",
                "migration_id": MIGRATION_ID,
                "journal": journal,
                "error": str(exc),
                "rollback": rollback,
                "idempotent_no_delta": False,
            }
