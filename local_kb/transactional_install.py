"""Recovery-bound whole-tree installation for Chaos Brain managed runtime trees."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Callable, Mapping
from uuid import uuid4

from local_kb.common import utc_now_iso


INSTALL_SCHEMA_VERSION = 5
CONTROL_ROOT_NAME = ".khaos-brain-install"
COMMITTED_BACKUP_RETENTION = 3
TRANSIENT_DIRS = {"__pycache__", ".pytest_cache", "runs", "locks", "bootstrap", "test-results"}
TRANSIENT_SUFFIXES = {".pyc", ".pyo"}
CONSUMER_PROJECTION_POLICY_ID = "khaos-brain.clean-consumer-projection.v1"


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _canonical_hash(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _portable_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if set(relative.parts) & TRANSIENT_DIRS or path.suffix.lower() in TRANSIENT_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def tree_manifest(root: Path) -> dict[str, Any]:
    rows = []
    for path in _portable_files(root):
        body = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    return {
        "file_count": len(rows),
        "byte_count": sum(int(row["size"]) for row in rows),
        "files": rows,
        "digest": _canonical_hash(rows),
    }


def consumer_skill_manifest(root: Path) -> dict[str, Any]:
    """Return the exact control-free projection expected on a consumer machine."""

    rows: list[dict[str, Any]] = []
    leaked: list[str] = []
    forbidden = ("skillguard", ".skillguard", "skillguard.py")
    for path in _portable_files(root):
        relative = path.relative_to(root)
        if ".skillguard" in relative.parts:
            continue
        body = path.read_bytes()
        try:
            text = body.decode("utf-8").lower()
        except UnicodeDecodeError:
            text = ""
        if any(token in text for token in forbidden):
            leaked.append(relative.as_posix())
        rows.append(
            {
                "path": relative.as_posix(),
                "size": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    if leaked:
        raise RuntimeError(
            f"Consumer skill projection leaked author-control tokens: {sorted(leaked)}"
        )
    return {
        "file_count": len(rows),
        "byte_count": sum(int(row["size"]) for row in rows),
        "files": rows,
        "digest": _canonical_hash(rows),
    }


def _copytree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "runs", "locks", "bootstrap", "test-results"),
    )


def _copy_consumer_skill(source: Path, destination: Path) -> None:
    """Project one validated author skill into a control-free consumer tree."""

    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            ".skillguard",
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "runs",
            "locks",
            "bootstrap",
            "test-results",
        ),
    )
    forbidden = ("skillguard", ".skillguard", "skillguard.py")
    leaked: list[str] = []
    for path in _portable_files(destination):
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        if any(token in text for token in forbidden):
            leaked.append(path.relative_to(destination).as_posix())
    if leaked:
        raise RuntimeError(
            f"Consumer skill projection leaked author-control tokens: {sorted(leaked)}"
        )


def _consumer_projection_receipt(skill_id: str, root: Path) -> dict[str, Any]:
    manifest = tree_manifest(root)
    forbidden_paths = [
        path.relative_to(root).as_posix()
        for path in root.rglob(".skillguard")
    ]
    forbidden_files: list[str] = []
    for path in _portable_files(root):
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        if any(token in text for token in ("skillguard", ".skillguard", "skillguard.py")):
            forbidden_files.append(path.relative_to(root).as_posix())
    if forbidden_paths or forbidden_files:
        raise RuntimeError(
            f"Consumer projection for {skill_id} retained author control: "
            f"paths={forbidden_paths}; files={forbidden_files}"
        )
    return {
        "policy_id": CONSUMER_PROJECTION_POLICY_ID,
        "skill_id": skill_id,
        "manifest_digest": str(manifest.get("digest") or ""),
        "author_control_present": False,
        "forbidden_token_count": 0,
    }


def _json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _assert_under(path: Path, root: Path) -> None:
    path.resolve().relative_to(root.resolve())


def _cleanup_staging_root(stages_root: Path) -> list[str]:
    """Remove stage copies left by terminal, pre-journal, or recovered transactions."""

    removed: list[str] = []
    if not stages_root.exists():
        return removed
    for path in sorted(stages_root.iterdir(), key=lambda item: item.name):
        _assert_under(path, stages_root)
        _remove_path(path)
        removed.append(path.name)
    return removed


def _recover_incomplete(control_root: Path, codex_home: Path) -> list[str]:
    recovered: list[str] = []
    transaction_root = control_root / "transactions"
    if not transaction_root.exists():
        return recovered
    for journal_path in sorted(transaction_root.glob("*.json")):
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(journal.get("status") or "") in {"committed", "rolled_back", "recovered"}:
            continue
        for item in reversed(journal.get("operations", [])):
            if not isinstance(item, dict):
                continue
            active = Path(str(item.get("active_path") or ""))
            backup = Path(str(item.get("backup_path") or ""))
            _assert_under(active, codex_home)
            _assert_under(backup, control_root)
            if backup.exists():
                _remove_path(active)
                active.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, active)
            elif not bool(item.get("had_active")):
                _remove_path(active)
        journal["status"] = "recovered"
        journal["recovered_at"] = utc_now_iso()
        transaction_id = str(journal.get("transaction_id") or journal_path.stem)
        stage_path = Path(
            str(journal.get("stage_root") or control_root / "staging" / transaction_id)
        )
        _assert_under(stage_path, control_root / "staging")
        _remove_path(stage_path)
        backup_root = Path(
            str(journal.get("backup_root") or control_root / "backups" / transaction_id)
        )
        _assert_under(backup_root, control_root / "backups")
        _remove_path(backup_root)
        journal["stage_cleanup"] = {
            "ok": not stage_path.exists(),
            "path": str(stage_path),
            "reason": "incomplete-transaction-recovery",
        }
        journal["failed_backup_cleanup"] = {
            "ok": not backup_root.exists(),
            "path": str(backup_root),
            "preserved_for_recovery": False,
        }
        _atomic_json(journal_path, journal)
        recovered.append(transaction_id)
    return recovered


def _backup_retention_receipt(
    *,
    control_root: Path,
    current_transaction_id: str,
    current_backup_root: Path,
    current_created_at: str,
    limit: int,
) -> dict[str, Any]:
    """Retain a bounded set of committed rollback trees and receipt every prune."""

    retention_limit = max(1, int(limit))
    transactions_root = control_root / "transactions"
    backups_root = control_root / "backups"
    candidates: list[dict[str, Any]] = []
    for journal_path in sorted(transactions_root.glob("*.json")):
        try:
            journal = _json_object(journal_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if journal.get("status") != "committed":
            continue
        transaction_id = str(journal.get("transaction_id") or journal_path.stem)
        backup_root = Path(str(journal.get("backup_root") or backups_root / transaction_id))
        try:
            _assert_under(backup_root, backups_root)
        except ValueError:
            continue
        if backup_root.exists():
            candidates.append(
                {
                    "transaction_id": transaction_id,
                    "backup_root": backup_root,
                    "order": str(journal.get("committed_at") or journal.get("created_at") or transaction_id),
                }
            )
    if not any(row["transaction_id"] == current_transaction_id for row in candidates):
        candidates.append(
            {
                "transaction_id": current_transaction_id,
                "backup_root": current_backup_root,
                "order": current_created_at,
            }
        )
    candidates.sort(key=lambda row: (str(row["order"]), str(row["transaction_id"])))
    current_rows = [
        row for row in candidates if str(row["transaction_id"]) == current_transaction_id
    ]
    previous_rows = [
        row for row in candidates if str(row["transaction_id"]) != current_transaction_id
    ]
    previous_limit = max(0, retention_limit - 1)
    retained_previous = previous_rows[-previous_limit:] if previous_limit else []
    retained_rows = retained_previous + current_rows[-1:]
    retained_ids = {str(row["transaction_id"]) for row in retained_rows}
    pruned: list[dict[str, Any]] = []
    for row in candidates:
        transaction_id = str(row["transaction_id"])
        if transaction_id in retained_ids:
            continue
        backup_root = Path(row["backup_root"])
        manifest = tree_manifest(backup_root)
        _remove_path(backup_root)
        pruned.append(
            {
                "transaction_id": transaction_id,
                "backup_root": str(backup_root),
                "backup_manifest": manifest,
                "deleted": not backup_root.exists(),
            }
        )
    retained = []
    for row in retained_rows:
        backup_root = Path(row["backup_root"])
        retained.append(
            {
                "transaction_id": str(row["transaction_id"]),
                "backup_root": str(backup_root),
                "backup_manifest": tree_manifest(backup_root),
            }
        )
    surviving_committed = [row for row in retained if Path(row["backup_root"]).exists()]
    return {
        "policy": "committed-backup-count",
        "limit": retention_limit,
        "generated_at": utc_now_iso(),
        "retained": retained,
        "pruned": pruned,
        "retained_count": len(surviving_committed),
        "pruned_count": len(pruned),
        "bounded": len(surviving_committed) <= retention_limit,
    }


def _install_receipt_payload(journal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": journal.get("schema_version"),
        "transaction_id": journal.get("transaction_id"),
        "repo_root": journal.get("repo_root"),
        "source_manifests": journal.get("source_manifests", {}),
        "staged_manifests": journal.get("staged_manifests", {}),
        "installed_manifests": journal.get("installed_manifests", {}),
        "retired_post_manifests": journal.get("retired_post_manifests", {}),
        "operations": journal.get("operations", []),
        "backup_retention": journal.get("backup_retention", {}),
        "consumer_projection_receipts": journal.get("consumer_projection_receipts", {}),
        "recovered_transactions": journal.get("recovered_transactions", []),
    }


def replay_install_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Replay a persisted receipt without needing the deleted staging tree."""

    issues: list[str] = []
    payload = receipt.get("receipt_payload")
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "issues": ["missing-receipt-payload"],
            "expected_receipt_hash": "",
            "actual_receipt_hash": str(receipt.get("receipt_hash") or ""),
        }
    expected_hash = _canonical_hash(payload)
    actual_hash = str(receipt.get("receipt_hash") or "")
    if expected_hash != actual_hash:
        issues.append("receipt-hash-mismatch")
    source = payload.get("source_manifests", {})
    staged = payload.get("staged_manifests", {})
    installed = payload.get("installed_manifests", {})
    if not all(isinstance(value, dict) for value in (source, staged, installed)):
        issues.append("manifest-map-invalid")
        source, staged, installed = {}, {}, {}
    if set(source) != set(staged) or set(staged) != set(installed):
        issues.append("manifest-key-set-mismatch")
    for key in sorted(set(source) & set(staged) & set(installed)):
        digests = {
            str(source[key].get("digest") or "") if isinstance(source[key], dict) else "",
            str(staged[key].get("digest") or "") if isinstance(staged[key], dict) else "",
            str(installed[key].get("digest") or "") if isinstance(installed[key], dict) else "",
        }
        if len(digests) != 1 or "" in digests:
            issues.append(f"manifest-parity-mismatch:{key}")
    operation_rows = payload.get("operations", [])
    if not isinstance(operation_rows, list):
        issues.append("operations-invalid")
        operation_rows = []
    for row in operation_rows:
        if not isinstance(row, dict):
            issues.append("operation-invalid")
            continue
        key = f"{row.get('kind')}:{row.get('id')}"
        post_manifest = row.get("post_manifest")
        if not isinstance(post_manifest, dict):
            issues.append(f"post-manifest-missing:{key}")
            continue
        if row.get("action") == "replace" and installed.get(key) != post_manifest:
            issues.append(f"installed-post-manifest-mismatch:{key}")
        if row.get("action") == "retire" and int(post_manifest.get("file_count") or 0) != 0:
            issues.append(f"retired-post-manifest-not-empty:{key}")
    retention = payload.get("backup_retention", {})
    if not isinstance(retention, dict) or not bool(retention.get("bounded")):
        issues.append("backup-retention-unbounded")
    projection_receipts = payload.get("consumer_projection_receipts", {})
    if not isinstance(projection_receipts, dict):
        issues.append("consumer-projection-receipts-invalid")
        projection_receipts = {}
    expected_skill_ids = {
        key.split(":", 1)[1] for key in installed if key.startswith("skill:")
    }
    if set(projection_receipts) != expected_skill_ids:
        issues.append("consumer-projection-receipt-inventory-mismatch")
    for skill_id, projection_receipt in projection_receipts.items():
        if not isinstance(projection_receipt, dict):
            issues.append(f"consumer-projection-receipt-invalid:{skill_id}")
            continue
        if projection_receipt.get("policy_id") != CONSUMER_PROJECTION_POLICY_ID:
            issues.append(f"consumer-projection-policy-mismatch:{skill_id}")
        installed_manifest = installed.get(f"skill:{skill_id}", {})
        if (
            not isinstance(installed_manifest, dict)
            or projection_receipt.get("manifest_digest")
            != installed_manifest.get("digest")
        ):
            issues.append(f"consumer-projection-manifest-mismatch:{skill_id}")
        if projection_receipt.get("author_control_present") is not False:
            issues.append(f"consumer-projection-author-control-present:{skill_id}")
        if projection_receipt.get("forbidden_token_count") != 0:
            issues.append(f"consumer-projection-forbidden-token:{skill_id}")
    return {
        "ok": not issues,
        "issues": issues,
        "expected_receipt_hash": expected_hash,
        "actual_receipt_hash": actual_hash,
        "managed_manifest_keys": sorted(installed),
    }


def install_managed_runtime(
    *,
    repo_root: Path,
    codex_home: Path,
    global_skill_name: str,
    global_skill_files: Mapping[str, str],
    skill_sources: Mapping[str, Path],
    automation_payloads: Mapping[str, Mapping[str, Any]],
    automation_renderer: Callable[[Mapping[str, Any]], str],
    retired_skill_ids: tuple[str, ...],
    retired_automation_ids: tuple[str, ...],
    fail_after_activation: int | None = None,
    backup_retention: int = COMMITTED_BACKUP_RETENTION,
) -> dict[str, Any]:
    """Stage, compare, activate, verify, and rollback all managed trees together."""

    repo_root = Path(repo_root).resolve()
    codex_home = Path(codex_home).resolve()
    codex_home.mkdir(parents=True, exist_ok=True)
    control_root = codex_home / CONTROL_ROOT_NAME
    stages_root = control_root / "staging"
    backups_root = control_root / "backups"
    transactions_root = control_root / "transactions"
    lock_path = control_root / "install.lock"
    for path in (stages_root, backups_root, transactions_root):
        path.mkdir(parents=True, exist_ok=True)
    stage_root: Path | None = None
    backup_root: Path | None = None
    journal_path: Path | None = None
    journal: dict[str, Any] | None = None
    transaction_committed = False
    try:
        lock_path.mkdir()
    except FileExistsError as exc:
        raise RuntimeError(f"Another Chaos Brain installation owns {lock_path}") from exc
    try:
        recovered = _recover_incomplete(control_root, codex_home)
        orphan_stages_removed = _cleanup_staging_root(stages_root)
        transaction_id = f"install-{int(time.time() * 1000)}-{uuid4().hex[:8]}"
        stage_root = stages_root / transaction_id
        backup_root = backups_root / transaction_id
        stage_root.mkdir(parents=True)
        backup_root.mkdir(parents=True)

        source_manifests: dict[str, dict[str, Any]] = {}
        staged_manifests: dict[str, dict[str, Any]] = {}
        consumer_projection_receipts: dict[str, dict[str, Any]] = {}
        managed: list[dict[str, Any]] = []

        global_stage = stage_root / "skills" / global_skill_name
        for relative, text in sorted(global_skill_files.items()):
            target = global_stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(text), encoding="utf-8")
        global_manifest = tree_manifest(global_stage)
        consumer_projection_receipts[global_skill_name] = _consumer_projection_receipt(
            global_skill_name, global_stage
        )
        source_manifests[f"skill:{global_skill_name}"] = global_manifest
        staged_manifests[f"skill:{global_skill_name}"] = global_manifest
        managed.append(
            {
                "kind": "skill",
                "id": global_skill_name,
                "active": codex_home / "skills" / global_skill_name,
                "stage": global_stage,
            }
        )

        for skill_id, source in sorted(skill_sources.items()):
            source = Path(source).resolve()
            before = tree_manifest(source)
            stage = stage_root / "skills" / skill_id
            _copy_consumer_skill(source, stage)
            after_source = tree_manifest(source)
            staged = tree_manifest(stage)
            if before["digest"] != after_source["digest"]:
                raise RuntimeError(f"Concurrent source drift while staging skill {skill_id}")
            if (stage / ".skillguard").exists():
                raise RuntimeError(
                    f"Consumer projection retained author control for skill {skill_id}"
                )
            active = codex_home / "skills" / skill_id
            consumer_projection_receipts[skill_id] = _consumer_projection_receipt(
                str(skill_id), stage
            )
            key = f"skill:{skill_id}"
            source_manifests[key] = staged
            staged_manifests[key] = staged
            managed.append({"kind": "skill", "id": skill_id, "active": active, "stage": stage})

        for automation_id, payload in sorted(automation_payloads.items()):
            stage = stage_root / "automations" / automation_id
            stage.mkdir(parents=True)
            (stage / "automation.toml").write_text(automation_renderer(payload), encoding="utf-8")
            manifest = tree_manifest(stage)
            key = f"automation:{automation_id}"
            source_manifests[key] = manifest
            staged_manifests[key] = manifest
            managed.append(
                {
                    "kind": "automation",
                    "id": automation_id,
                    "active": codex_home / "automations" / automation_id,
                    "stage": stage,
                }
            )

        operations: list[dict[str, Any]] = []
        for item in managed:
            active = Path(item["active"])
            backup = backup_root / str(item["kind"]) / str(item["id"])
            operations.append(
                {
                    "kind": item["kind"],
                    "id": item["id"],
                    "action": "replace",
                    "active_path": str(active),
                    "stage_path": str(item["stage"]),
                    "backup_path": str(backup),
                    "had_active": active.exists(),
                    "pre_manifest": tree_manifest(active) if active.exists() else {},
                }
            )
        for kind, retired_ids in (("skill", retired_skill_ids), ("automation", retired_automation_ids)):
            for retired_id in retired_ids:
                active = codex_home / ("skills" if kind == "skill" else "automations") / retired_id
                backup = backup_root / "retired" / kind / retired_id
                operations.append(
                    {
                        "kind": kind,
                        "id": retired_id,
                        "action": "retire",
                        "active_path": str(active),
                        "stage_path": "",
                        "backup_path": str(backup),
                        "had_active": active.exists(),
                        "pre_manifest": tree_manifest(active) if active.exists() else {},
                    }
                )

        journal_path = transactions_root / f"{transaction_id}.json"
        journal = {
            "schema_version": INSTALL_SCHEMA_VERSION,
            "transaction_id": transaction_id,
            "status": "prepared",
            "created_at": utc_now_iso(),
            "repo_root": str(repo_root),
            "stage_root": str(stage_root),
            "backup_root": str(backup_root),
            "source_manifests": source_manifests,
            "staged_manifests": staged_manifests,
            "installed_manifests": {},
            "retired_post_manifests": {},
            "consumer_projection_receipts": consumer_projection_receipts,
            "operations": operations,
            "activated_count": 0,
            "recovered_transactions": recovered,
            "orphan_stages_removed": orphan_stages_removed,
        }
        _atomic_json(journal_path, journal)

        activated = 0
        try:
            installed_manifests: dict[str, dict[str, Any]] = {}
            retired_post_manifests: dict[str, dict[str, Any]] = {}
            journal["status"] = "activating"
            _atomic_json(journal_path, journal)
            for operation in operations:
                active = Path(operation["active_path"])
                backup = Path(operation["backup_path"])
                active.parent.mkdir(parents=True, exist_ok=True)
                backup.parent.mkdir(parents=True, exist_ok=True)
                if active.exists():
                    os.replace(active, backup)
                if operation["action"] == "replace":
                    os.replace(Path(operation["stage_path"]), active)
                    expected = staged_manifests[f"{operation['kind']}:{operation['id']}"]
                    installed = tree_manifest(active)
                    if installed["digest"] != expected["digest"]:
                        raise RuntimeError(f"Post-activation parity failed for {operation['kind']} {operation['id']}")
                    installed_manifests[f"{operation['kind']}:{operation['id']}"] = installed
                    operation["post_manifest"] = installed
                else:
                    retired = tree_manifest(active)
                    if int(retired.get("file_count") or 0):
                        raise RuntimeError(
                            f"Post-retirement absence failed for {operation['kind']} {operation['id']}"
                        )
                    retired_post_manifests[f"{operation['kind']}:{operation['id']}"] = retired
                    operation["post_manifest"] = retired
                activated += 1
                journal["activated_count"] = activated
                journal["installed_manifests"] = installed_manifests
                journal["retired_post_manifests"] = retired_post_manifests
                journal["operations"] = operations
                _atomic_json(journal_path, journal)
                if fail_after_activation is not None and activated >= fail_after_activation:
                    raise RuntimeError("Injected installation failure")

            managed_keys = set(source_manifests)
            if managed_keys != set(staged_manifests) or managed_keys != set(installed_manifests):
                raise RuntimeError("Source/stage/installed manifest key sets do not match")
            for key in sorted(managed_keys):
                digests = {
                    str(source_manifests[key].get("digest") or ""),
                    str(staged_manifests[key].get("digest") or ""),
                    str(installed_manifests[key].get("digest") or ""),
                }
                if len(digests) != 1 or "" in digests:
                    raise RuntimeError(f"Source/stage/installed manifest parity failed for {key}")

            journal["status"] = "verifying"
            journal["installed_manifests"] = installed_manifests
            journal["retired_post_manifests"] = retired_post_manifests
            _atomic_json(journal_path, journal)
            retention_receipt = _backup_retention_receipt(
                control_root=control_root,
                current_transaction_id=transaction_id,
                current_backup_root=backup_root,
                current_created_at=str(journal["created_at"]),
                limit=backup_retention,
            )
            if not retention_receipt["bounded"]:
                raise RuntimeError("Committed backup retention did not converge")
            journal["backup_retention"] = retention_receipt
            journal["receipt_payload"] = _install_receipt_payload(journal)
            journal["receipt_hash"] = _canonical_hash(journal["receipt_payload"])
            replay = replay_install_receipt(journal)
            if not replay["ok"]:
                raise RuntimeError(f"Install receipt replay failed: {replay['issues']}")
            journal["status"] = "committed"
            journal["committed_at"] = utc_now_iso()
            _atomic_json(journal_path, journal)
            transaction_committed = True
        except Exception:
            rollback_issues: list[str] = []
            for operation in reversed(operations):
                try:
                    active = Path(operation["active_path"])
                    backup = Path(operation["backup_path"])
                    if backup.exists():
                        _remove_path(active)
                        active.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(backup, active)
                    elif not bool(operation["had_active"]):
                        _remove_path(active)
                except OSError as rollback_error:
                    rollback_issues.append(
                        f"{operation.get('kind')}:{operation.get('id')}:{rollback_error}"
                    )
            journal["status"] = "rollback_failed" if rollback_issues else "rolled_back"
            journal["rolled_back_at"] = utc_now_iso()
            journal["rollback_issues"] = rollback_issues
            journal["rollback_manifests"] = {
                f"{operation['kind']}:{operation['id']}": tree_manifest(
                    Path(operation["active_path"])
                )
                for operation in operations
            }
            journal.pop("receipt_hash", None)
            journal.pop("receipt_payload", None)
            _atomic_json(journal_path, journal)
            raise

        _remove_path(stage_root)
        journal["stage_cleanup"] = {
            "ok": not stage_root.exists(),
            "path": str(stage_root),
            "reason": "committed-transaction-finally",
        }
        _atomic_json(journal_path, journal)
        return {
            "ok": True,
            "schema_version": INSTALL_SCHEMA_VERSION,
            "transaction_id": transaction_id,
            "journal_path": str(journal_path),
            "backup_root": str(backup_root),
            "receipt_hash": journal["receipt_hash"],
            "receipt_payload": journal["receipt_payload"],
            "source_manifests": source_manifests,
            "staged_manifests": staged_manifests,
            "installed_manifests": journal["installed_manifests"],
            "retired_post_manifests": journal["retired_post_manifests"],
            "backup_retention": journal["backup_retention"],
            "consumer_projection_receipts": journal["consumer_projection_receipts"],
            "retired_skill_ids": list(retired_skill_ids),
            "retired_automation_ids": list(retired_automation_ids),
            "recovered_transactions": recovered,
            "orphan_stages_removed": orphan_stages_removed,
            "operations": operations,
        }
    finally:
        if stage_root is not None:
            try:
                _assert_under(stage_root, stages_root)
                _remove_path(stage_root)
            except (OSError, ValueError):
                pass
        if backup_root is not None and not transaction_committed:
            should_remove_backup = journal is None or journal.get("status") == "rolled_back"
            if should_remove_backup:
                try:
                    _assert_under(backup_root, backups_root)
                    _remove_path(backup_root)
                except (OSError, ValueError):
                    pass
        if journal is not None and journal_path is not None and journal_path.exists():
            try:
                journal["stage_cleanup"] = {
                    "ok": stage_root is None or not stage_root.exists(),
                    "path": str(stage_root or ""),
                    "reason": "transaction-finally",
                }
                if backup_root is not None and not transaction_committed:
                    journal["failed_backup_cleanup"] = {
                        "ok": not backup_root.exists() if journal.get("status") == "rolled_back" else False,
                        "path": str(backup_root),
                        "preserved_for_recovery": journal.get("status") != "rolled_back",
                    }
                _atomic_json(journal_path, journal)
            except (OSError, ValueError):
                pass
        try:
            lock_path.rmdir()
        except OSError:
            pass


def latest_install_receipt(codex_home: Path) -> dict[str, Any]:
    transaction_root = Path(codex_home) / CONTROL_ROOT_NAME / "transactions"
    if not transaction_root.exists():
        return {}
    for path in sorted(transaction_root.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("status") == "committed":
            return {**payload, "journal_path": str(path)}
    return {}
