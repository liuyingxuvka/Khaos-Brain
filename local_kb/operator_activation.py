"""Current-machine all-active rollout after one current Chaos Brain readiness gate."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from local_kb.automation_runtime import content_hash
from local_kb.install import (
    MAINTENANCE_SKILL_NAMES,
    REPO_AUTOMATION_SPECS,
    _write_text_atomic,
    apply_repo_automation_restoration_plan,
    build_installation_check,
    capture_repo_automation_state_snapshot,
    pause_repo_automations,
    plan_repo_automation_restoration,
)
from scripts import check_chaos_brain_readiness as readiness


SCHEMA_VERSION = "khaos-brain.operator-automation-activation.v3"
HEAD_SCHEMA_VERSION = "khaos-brain.operator-automation-activation-head.v3"
INSTALLATION_IDENTITY_SCHEMA_VERSION = (
    "khaos-brain.operator-installation-currentness.v1"
)
SKILL_INVENTORY_SCHEMA_VERSION = (
    "khaos-brain.operator-activation-skill-inventory.v1"
)
SCHEDULED_SKILL_IDS = tuple(
    str(spec["skill_name"]) for spec in REPO_AUTOMATION_SPECS
)
MANUAL_ONLY_SKILL_IDS = tuple(
    skill_id
    for skill_id in MAINTENANCE_SKILL_NAMES
    if skill_id not in SCHEDULED_SKILL_IDS
)
REQUIRED_READINESS_CHECKS = frozenset(
    {
        "flowguard_models",
        "flowguard_meshes",
        "logicguard_authority_cutover_model",
        "logicguard_field_lifecycle",
        "logicguard_model_mesh",
        "logicguard_code_structure",
        "logicguard_model_test_contract",
        "logicguard_test_mesh",
        "logicguard_runtime_model_miss",
        "logicguard_runtime",
        "logicguard_openspec",
        "author_contract_assurance",
        "retired_architect_absence",
        "current_runtime_only",
        "retrieval_quality",
        "full_regression",
        "model_code_test_alignment",
    }
)


def _expected_skill_inventory() -> dict[str, Any]:
    return {
        "schema_version": SKILL_INVENTORY_SCHEMA_VERSION,
        "maintained_skill_ids": sorted(MAINTENANCE_SKILL_NAMES),
        "scheduled_skill_ids": sorted(SCHEDULED_SKILL_IDS),
        "manual_only_skill_ids": sorted(MANUAL_ONLY_SKILL_IDS),
    }


def _skill_inventory_issues(value: object) -> list[str]:
    if not isinstance(value, Mapping):
        return ["activation-skill-inventory-missing"]
    expected = _expected_skill_inventory()
    issues: list[str] = []
    if value.get("schema_version") != SKILL_INVENTORY_SCHEMA_VERSION:
        issues.append("activation-skill-inventory-schema-mismatch")
    for key in (
        "maintained_skill_ids",
        "scheduled_skill_ids",
        "manual_only_skill_ids",
    ):
        rows = value.get(key)
        if not isinstance(rows, list) or rows != expected[key]:
            issues.append(f"activation-skill-inventory-{key}-mismatch")
    scheduled = set(value.get("scheduled_skill_ids") or [])
    manual_only = set(value.get("manual_only_skill_ids") or [])
    maintained = set(value.get("maintained_skill_ids") or [])
    if scheduled.intersection(manual_only):
        issues.append("activation-skill-inventory-overlap")
    if scheduled.union(manual_only) != maintained:
        issues.append("activation-skill-inventory-not-exhaustive")
    return issues


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def installation_currentness_projection(
    installation_check: Mapping[str, Any],
) -> dict[str, Any]:
    """Project stable installed authority without hashing runtime diagnostics."""

    history = (
        installation_check.get("history_migration_check", {})
        if isinstance(installation_check.get("history_migration_check"), Mapping)
        else {}
    )
    history_state = (
        history.get("maintenance_state", {})
        if isinstance(history.get("maintenance_state"), Mapping)
        else {}
    )
    history_journal = (
        history.get("journal", {})
        if isinstance(history.get("journal"), Mapping)
        else {}
    )
    history_receipt = (
        history.get("receipt", {})
        if isinstance(history.get("receipt"), Mapping)
        else {}
    )
    assurance = (
        installation_check.get("upgrade_assurance", {})
        if isinstance(installation_check.get("upgrade_assurance"), Mapping)
        else {}
    )
    source_after = (
        assurance.get("source_snapshot_after", {})
        if isinstance(assurance.get("source_snapshot_after"), Mapping)
        else {}
    )
    verifier = (
        assurance.get("verifier_fingerprint", {})
        if isinstance(assurance.get("verifier_fingerprint"), Mapping)
        else {}
    )
    stable_keys = (
        "ok",
        "repo_root",
        "manifest_repo_root",
        "codex_home",
        "skill_dir",
        "skill_path",
        "launcher_path",
        "openai_path",
        "global_agents_path",
        "install_state_path",
        "env_var_name",
        "env_var_value",
        "maintenance_skill_names",
        "shell_tools",
        "automation_runtime",
        "checklist",
        "canonical_interface_checks",
        "maintenance_skill_checks",
        "automation_checks",
        "automation_restore_deferred",
        "deferred_automation_restore_allowed",
        "obsolete_update_state_settled",
        "update_state_source_current",
        "current_update_state",
        "upgrade_attempt_authority",
        "upgrade_attempt",
        "install_transaction",
        "retired_paths",
        "issues",
        "warnings",
    )
    return {
        "schema_version": INSTALLATION_IDENTITY_SCHEMA_VERSION,
        **{key: installation_check.get(key) for key in stable_keys},
        "history_migration_gate": {
            "required": installation_check.get("history_migration_required"),
            "ok": history.get("ok"),
            "migration_id": history.get("migration_id"),
            "maintenance_committed": history_state.get("committed"),
            "maintenance_phase": history_state.get("phase"),
            "journal_status": history_journal.get("status"),
            "receipt_status": history_receipt.get("status"),
            "receipt_hash": history_receipt.get("receipt_hash"),
        },
        "upgrade_assurance_gate": {
            "required": installation_check.get("upgrade_assurance_required"),
            "ok": assurance.get("ok"),
            "evidence_run_id": assurance.get("evidence_run_id"),
            "failed_checks": assurance.get("failed_checks"),
            "source_digest": source_after.get("digest"),
            "verifier_digest": verifier.get("digest"),
        },
    }


def _safe_proof_path(path: Path, root: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def validate_activation_readiness(
    repo_root: Path,
    codex_home: Path,
    readiness_receipt_path: Path,
) -> dict[str, Any]:
    """Verify the exact pre-restore aggregate and its five-skill classification."""

    repo_root = Path(repo_root).resolve()
    codex_home = Path(codex_home).resolve()
    receipt_path = Path(readiness_receipt_path).resolve()
    payload = _load_json(receipt_path)
    issues: list[str] = []
    if not payload or payload.get("ok") is not True:
        issues.append("aggregate-readiness-not-passed")
    if payload.get("pre_restore") is not True:
        issues.append("aggregate-readiness-is-not-pre-restore-gate")
    if Path(str(payload.get("repo_root") or "")).resolve() != repo_root:
        issues.append("aggregate-readiness-repo-root-mismatch")
    if Path(str(payload.get("codex_home") or "")).resolve() != codex_home:
        issues.append("aggregate-readiness-codex-home-mismatch")

    current_source = readiness._source_snapshot(repo_root)
    stored_source = payload.get("source_snapshot_after", {})
    if (
        not isinstance(stored_source, Mapping)
        or stored_source.get("digest") != current_source.get("digest")
        or payload.get("source_stable_during_checks") is not True
    ):
        issues.append("aggregate-readiness-source-stale")
    current_verifier = readiness._verifier_fingerprint()
    stored_verifier = payload.get("verifier_fingerprint", {})
    if (
        not isinstance(stored_verifier, Mapping)
        or stored_verifier.get("digest") != current_verifier.get("digest")
    ):
        issues.append("aggregate-readiness-verifier-stale")

    checks = payload.get("checks", {})
    if not isinstance(checks, Mapping):
        checks = {}
    missing_checks = sorted(REQUIRED_READINESS_CHECKS - set(checks))
    if missing_checks:
        issues.append("aggregate-readiness-checks-missing:" + ",".join(missing_checks))
    for check_id in sorted(REQUIRED_READINESS_CHECKS & set(checks)):
        row = checks.get(check_id)
        if not isinstance(row, Mapping) or row.get("ok") is not True:
            issues.append(f"aggregate-readiness-check-not-passed:{check_id}")

    evidence_ref = payload.get("evidence_manifest", {})
    evidence_path = _safe_proof_path(
        Path(str(evidence_ref.get("path") or "")),
        repo_root / ".local" / "assurance" / "validation-evidence",
    ) if isinstance(evidence_ref, Mapping) else None
    if (
        evidence_path is None
        or _sha256(evidence_path) != str(evidence_ref.get("sha256") or "")
    ):
        issues.append("aggregate-evidence-manifest-not-current")

    maintained_refs: dict[str, dict[str, Any]] = {}
    author_entry = checks.get("author_contract_assurance", {})
    author_report = (
        author_entry.get("json_payload", {})
        if isinstance(author_entry, Mapping)
        else {}
    )
    skills = (
        author_report.get("skills", {})
        if isinstance(author_report, Mapping)
        else {}
    )
    expected_skills = set(MAINTENANCE_SKILL_NAMES)
    if (
        not isinstance(author_report, Mapping)
        or author_report.get("schema_version")
        != "khaos-brain.skill-author-maintenance.v1"
        or author_report.get("source_only") is not True
    ):
        issues.append("author-maintenance-report-schema-mismatch")
    if not isinstance(skills, Mapping) or set(skills) != expected_skills:
        issues.append("maintained-skill-set-mismatch")
        skills = {}
    for skill_id in sorted(expected_skills):
        skill = skills.get(skill_id, {})
        projection = (
            skill.get("consumer_projection", {})
            if isinstance(skill, Mapping)
            else {}
        )
        if (
            not isinstance(skill, Mapping)
            or skill.get("ok") is not True
            or skill.get("skill_id") != skill_id
            or skill.get("maintenance_unit_id") != f"unit:{skill_id}"
            or not isinstance(projection, Mapping)
            or projection.get("ok") is not True
            or not str(projection.get("manifest_digest") or "")
        ):
            issues.append(f"maintained-skill-author-evidence-invalid:{skill_id}")
            continue
        maintained_refs[skill_id] = {
            "maintenance_unit_id": str(skill.get("maintenance_unit_id") or ""),
            "consumer_projection_digest": str(
                projection.get("manifest_digest") or ""
            ),
            "consumer_file_count": int(projection.get("file_count") or 0),
        }

    binding = {
        "aggregate_receipt_path": str(receipt_path),
        "aggregate_receipt_sha256": _sha256(receipt_path) if receipt_path.is_file() else "",
        "evidence_manifest_path": str(evidence_path or ""),
        "evidence_manifest_sha256": _sha256(evidence_path) if evidence_path else "",
        "source_digest": str(current_source.get("digest") or ""),
        "verifier_digest": str(current_verifier.get("digest") or ""),
        "skill_inventory": _expected_skill_inventory(),
        "maintained_skill_refs": maintained_refs,
    }
    return {
        "ok": not issues,
        "issues": issues,
        "readiness_receipt_path": str(receipt_path),
        "binding": binding,
    }


def _activation_root(codex_home: Path) -> Path:
    return Path(codex_home).resolve() / ".khaos-brain-install" / "operator-activation"


def validate_operator_activation_receipt(
    repo_root: Path,
    codex_home: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    receipt_path = Path(receipt_path).resolve()
    receipt = _load_json(receipt_path)
    issues: list[str] = []
    body = dict(receipt)
    stored_hash = str(body.pop("receipt_hash", ""))
    if receipt.get("schema_version") != SCHEMA_VERSION:
        issues.append("operator-activation-schema-mismatch")
    if stored_hash != content_hash(body):
        issues.append("operator-activation-receipt-hash-mismatch")
    readiness_binding = (
        receipt.get("readiness", {})
        if isinstance(receipt.get("readiness"), Mapping)
        else {}
    )
    evidence_path = _safe_proof_path(
        Path(str(readiness_binding.get("evidence_manifest_path") or "")),
        Path(repo_root).resolve() / ".local" / "assurance" / "validation-evidence",
    )
    if (
        evidence_path is None
        or _sha256(evidence_path)
        != str(readiness_binding.get("evidence_manifest_sha256") or "")
    ):
        issues.append("operator-activation-evidence-manifest-stale")
    issues.extend(
        f"operator-{issue}"
        for issue in _skill_inventory_issues(
            readiness_binding.get("skill_inventory")
        )
    )
    maintained_refs = readiness_binding.get("maintained_skill_refs", {})
    expected_skills = set(MAINTENANCE_SKILL_NAMES)
    if not isinstance(maintained_refs, Mapping) or set(maintained_refs) != expected_skills:
        issues.append("operator-activation-maintained-skill-ref-set-mismatch")
    aggregate_path = _safe_proof_path(
        Path(str(readiness_binding.get("aggregate_receipt_path") or "")),
        Path(repo_root).resolve() / ".local" / "assurance",
    )
    if (
        aggregate_path is None
        or _sha256(aggregate_path)
        != str(readiness_binding.get("aggregate_receipt_sha256") or "")
    ):
        issues.append("operator-activation-aggregate-receipt-stale")
    else:
        current_gate = validate_activation_readiness(
            Path(repo_root).resolve(),
            Path(codex_home).resolve(),
            aggregate_path,
        )
        if (
            current_gate.get("ok") is not True
            or current_gate.get("binding") != dict(readiness_binding)
        ):
            issues.append("operator-activation-readiness-binding-stale")
    snapshot = capture_repo_automation_state_snapshot(Path(codex_home))
    expected_ids = {str(spec["id"]) for spec in REPO_AUTOMATION_SPECS}
    if not (
        snapshot.get("ok") is True
        and snapshot.get("states") == {key: "ACTIVE" for key in expected_ids}
        and snapshot.get("user_paused") == {key: False for key in expected_ids}
    ):
        issues.append("operator-activation-live-readback-mismatch")
    final_check = build_installation_check(
        repo_root=Path(repo_root).resolve(),
        codex_home=Path(codex_home).resolve(),
    )
    if final_check.get("ok") is not True:
        issues.append("operator-activation-install-check-failed")
    if content_hash(installation_currentness_projection(final_check)) != str(
        receipt.get("final_install_identity_hash") or ""
    ):
        issues.append("operator-activation-install-check-changed")
    return {
        "ok": not issues,
        "issues": issues,
        "receipt_hash": stored_hash,
        "live_snapshot": snapshot,
        "final_install_check": final_check,
    }


def _current_operator_activation_record(codex_home: Path) -> Path | None:
    root = _activation_root(codex_home)
    head = _load_json(root / "HEAD.json")
    head_body = dict(head)
    stored_head_hash = str(head_body.pop("head_hash", ""))
    if (
        head.get("schema_version") != HEAD_SCHEMA_VERSION
        or not stored_head_hash
        or stored_head_hash != content_hash(head_body)
    ):
        return None
    ref = head.get("receipt_ref", {}) if isinstance(head.get("receipt_ref"), Mapping) else {}
    relative = str(ref.get("relative_path") or "")
    if not relative:
        return None
    path = _safe_proof_path(root / Path(relative), root)
    if path is None or _sha256(path) != str(ref.get("sha256") or ""):
        return None
    receipt = _load_json(path)
    if (
        receipt.get("receipt_id") != head.get("receipt_id")
        or receipt.get("receipt_hash") != head.get("receipt_hash")
    ):
        return None
    return path


def activate_all_for_current_machine(
    repo_root: Path,
    codex_home: Path,
    readiness_receipt_path: Path,
) -> dict[str, Any]:
    """Apply one hash-bound all-active override or fail back to all PAUSED."""

    repo_root = Path(repo_root).resolve()
    codex_home = Path(codex_home).resolve()
    gate = validate_activation_readiness(
        repo_root,
        codex_home,
        readiness_receipt_path,
    )
    if gate.get("ok") is not True:
        return {"ok": False, "status": "readiness-blocked", "gate": gate}
    before = capture_repo_automation_state_snapshot(codex_home)
    expected_ids = {str(spec["id"]) for spec in REPO_AUTOMATION_SPECS}
    already_active = bool(
        before.get("ok") is True
        and before.get("states") == {key: "ACTIVE" for key in expected_ids}
        and before.get("user_paused") == {key: False for key in expected_ids}
    )
    if already_active:
        current_record = _current_operator_activation_record(codex_home)
        validation = (
            validate_operator_activation_receipt(
                repo_root,
                codex_home,
                current_record,
            )
            if current_record is not None
            else {"ok": False, "issues": ["operator-activation-head-missing"]}
        )
        if validation.get("ok") is True:
            return {
                "ok": True,
                "status": "current-machine-all-active-reused",
                "receipt_path": str(current_record),
                "validation": validation,
            }
        pause = pause_repo_automations(codex_home)
        return {
            "ok": False,
            "status": "active-without-current-receipt-repaused",
            "validation": validation,
            "pause": pause,
        }
    if not (
        before.get("ok") is True
        and set(before.get("states", {})) == expected_ids
        and all(value == "PAUSED" for value in before.get("states", {}).values())
    ):
        pause = pause_repo_automations(codex_home)
        return {
            "ok": False,
            "status": "precondition-blocked-repaused",
            "gate": gate,
            "before": before,
            "pause": pause,
        }
    target_states = {key: "ACTIVE" for key in expected_ids}
    target_user_paused = {key: False for key in expected_ids}
    plan = plan_repo_automation_restoration(
        codex_home,
        target_states,
        user_paused_states=target_user_paused,
    )
    if plan.get("ok") is not True:
        return {
            "ok": False,
            "status": "plan-blocked",
            "gate": gate,
            "before": before,
            "plan": plan,
        }
    try:
        restoration = apply_repo_automation_restoration_plan(codex_home, plan)
    except BaseException as exc:
        pause = pause_repo_automations(codex_home)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return {
            "ok": False,
            "status": "apply-exception-repaused",
            "error": f"{type(exc).__name__}:{exc}",
            "gate": gate,
            "before": before,
            "plan": plan,
            "pause": pause,
        }
    exact = bool(
        restoration.get("ok") is True
        and restoration.get("restored") == target_states
        and restoration.get("restored_user_paused") == target_user_paused
        and restoration.get("plan_hash") == plan.get("plan_hash")
    )
    if not exact:
        pause = pause_repo_automations(codex_home)
        return {
            "ok": False,
            "status": "apply-blocked-repaused",
            "gate": gate,
            "before": before,
            "plan": plan,
            "restoration": restoration,
            "pause": pause,
        }
    try:
        final_check = build_installation_check(
            repo_root=repo_root,
            codex_home=codex_home,
        )
    except BaseException as exc:
        pause = pause_repo_automations(codex_home)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return {
            "ok": False,
            "status": "install-check-exception-repaused",
            "error": f"{type(exc).__name__}:{exc}",
            "gate": gate,
            "before": before,
            "plan": plan,
            "restoration": restoration,
            "pause": pause,
        }
    if final_check.get("ok") is not True:
        pause = pause_repo_automations(codex_home)
        return {
            "ok": False,
            "status": "install-check-blocked-repaused",
            "gate": gate,
            "before": before,
            "plan": plan,
            "restoration": restoration,
            "final_install_check": final_check,
            "pause": pause,
        }

    receipt_body = {
        "schema_version": SCHEMA_VERSION,
        "status": "current-machine-all-active",
        "created_at": _utc_now(),
        "repo_root": str(repo_root),
        "codex_home": str(codex_home),
        "readiness": dict(gate.get("binding") or {}),
        "before_states": dict(before.get("states") or {}),
        "before_user_paused": dict(before.get("user_paused") or {}),
        "plan_hash": str(plan.get("plan_hash") or ""),
        "target_hashes": dict(plan.get("target_hashes") or {}),
        "applied_hashes": dict(restoration.get("applied_hashes") or {}),
        "restored_states": dict(restoration.get("restored") or {}),
        "restored_user_paused": dict(restoration.get("restored_user_paused") or {}),
        "final_install_identity_hash": content_hash(
            installation_currentness_projection(final_check)
        ),
        "claim_boundary": (
            "This receipt authorizes only the user's explicit all-active, "
            "user_paused=false override for the four scheduled automations on this "
            "Codex home. It binds the complete five-skill inventory and keeps "
            "khaos-brain-update manual-only. Installed currentness binds only the "
            "stable installation authority projection; history-migration diagnostics "
            "must still pass but are not receipt identity. It does not prove a future "
            "scheduled run completed. Portable installers still preserve each "
            "machine's prior state."
        ),
    }
    receipt = {**receipt_body, "receipt_hash": content_hash(receipt_body)}
    receipt["receipt_id"] = "operator-activation-" + receipt["receipt_hash"][:24].lower()
    unsigned = dict(receipt)
    unsigned.pop("receipt_hash")
    receipt["receipt_hash"] = content_hash(unsigned)
    root = _activation_root(codex_home)
    record_path = root / "receipts" / f"{receipt['receipt_hash'][:24].lower()}.json"
    record_text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        if record_path.exists() and record_path.read_text(encoding="utf-8") != record_text:
            raise RuntimeError("operator activation receipt collision")
        if not record_path.exists():
            _write_text_atomic(record_path, record_text)
        head_body = {
            "schema_version": HEAD_SCHEMA_VERSION,
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "receipt_ref": {
                "relative_path": f"receipts/{record_path.name}",
                "sha256": _sha256(record_path),
            },
        }
        head = {**head_body, "head_hash": content_hash(head_body)}
        _write_text_atomic(
            root / "HEAD.json",
            json.dumps(head, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        validation = validate_operator_activation_receipt(
            repo_root,
            codex_home,
            record_path,
        )
    except BaseException as exc:
        pause = pause_repo_automations(codex_home)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return {
            "ok": False,
            "status": "receipt-write-blocked-repaused",
            "error": f"{type(exc).__name__}:{exc}",
            "pause": pause,
        }
    if validation.get("ok") is not True:
        pause = pause_repo_automations(codex_home)
        return {
            "ok": False,
            "status": "receipt-validation-blocked-repaused",
            "receipt_path": str(record_path),
            "validation": validation,
            "pause": pause,
        }
    return {
        "ok": True,
        "status": "current-machine-all-active",
        "receipt_id": receipt["receipt_id"],
        "receipt_hash": receipt["receipt_hash"],
        "receipt_path": str(record_path),
        "head_path": str(root / "HEAD.json"),
        "validation": validation,
    }
