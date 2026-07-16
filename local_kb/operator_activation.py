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


SCHEMA_VERSION = "khaos-brain.operator-automation-activation.v1"
REQUIRED_READINESS_CHECKS = frozenset(
    {
        "flowguard_models",
        "flowguard_meshes",
        "skillguard_source_install_parity",
        "skillguard_source_assurance",
        "retired_architect_absence",
        "retrieval_quality",
        "full_regression",
        "model_code_test_alignment",
    }
)


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
    """Verify the exact pre-restore aggregate and five scheduled completions."""

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

    scheduled_refs: dict[str, dict[str, str]] = {}
    installed_entry = checks.get("skillguard_source_install_parity", {})
    installed_report = (
        installed_entry.get("json_payload", {})
        if isinstance(installed_entry, Mapping)
        else {}
    )
    skills = (
        installed_report.get("skills", {})
        if isinstance(installed_report, Mapping)
        else {}
    )
    expected_skills = set(MAINTENANCE_SKILL_NAMES)
    if not isinstance(skills, Mapping) or set(skills) != expected_skills:
        issues.append("scheduled-production-skill-set-mismatch")
        skills = {}
    proof_root = repo_root / ".local" / "automation-runs"
    for skill_id in sorted(expected_skills):
        skill = skills.get(skill_id, {})
        execution = (
            skill.get("executed_supervision", {})
            if isinstance(skill, Mapping)
            else {}
        )
        production = (
            execution.get("scheduled_production", {})
            if isinstance(execution, Mapping)
            else {}
        )
        proof_path = _safe_proof_path(
            Path(str(production.get("guarded_result_path") or "")),
            proof_root,
        ) if isinstance(production, Mapping) else None
        proof = _load_json(proof_path) if proof_path is not None else {}
        if not (
            isinstance(execution, Mapping)
            and execution.get("ok") is True
            and isinstance(production, Mapping)
            and production.get("ok") is True
            and proof.get("ok") is True
            and proof.get("skill_id") == skill_id
        ):
            issues.append(f"scheduled-production-terminal-missing:{skill_id}")
            continue
        scheduled_refs[skill_id] = {
            "path": str(proof_path),
            "sha256": _sha256(proof_path),
            "run_id": str(proof.get("run_id") or ""),
            "status": str(proof.get("status") or ""),
        }

    binding = {
        "aggregate_receipt_sha256": _sha256(receipt_path) if receipt_path.is_file() else "",
        "evidence_manifest_path": str(evidence_path or ""),
        "evidence_manifest_sha256": _sha256(evidence_path) if evidence_path else "",
        "source_digest": str(current_source.get("digest") or ""),
        "verifier_digest": str(current_verifier.get("digest") or ""),
        "scheduled_production_refs": scheduled_refs,
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
    scheduled_refs = readiness_binding.get("scheduled_production_refs", {})
    expected_skills = set(MAINTENANCE_SKILL_NAMES)
    if not isinstance(scheduled_refs, Mapping) or set(scheduled_refs) != expected_skills:
        issues.append("operator-activation-scheduled-proof-set-mismatch")
        scheduled_refs = {}
    proof_root = Path(repo_root).resolve() / ".local" / "automation-runs"
    for skill_id in sorted(expected_skills):
        ref = scheduled_refs.get(skill_id, {})
        proof_path = (
            _safe_proof_path(Path(str(ref.get("path") or "")), proof_root)
            if isinstance(ref, Mapping)
            else None
        )
        proof = _load_json(proof_path) if proof_path is not None else {}
        if not (
            proof_path is not None
            and _sha256(proof_path) == str(ref.get("sha256") or "")
            and proof.get("ok") is True
            and proof.get("skill_id") == skill_id
            and str(proof.get("run_id") or "") == str(ref.get("run_id") or "")
            and str(proof.get("status") or "") == str(ref.get("status") or "")
        ):
            issues.append(f"operator-activation-scheduled-proof-stale:{skill_id}")
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
    if content_hash(final_check) != str(receipt.get("final_install_check_hash") or ""):
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
    restoration = apply_repo_automation_restoration_plan(codex_home, plan)
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
    final_check = build_installation_check(repo_root=repo_root, codex_home=codex_home)
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
        "final_install_check_hash": content_hash(final_check),
        "claim_boundary": (
            "This receipt authorizes only the user's explicit all-active, user_paused=false "
            "override on this Codex home after the bound aggregate and five scheduled "
            "SkillGuard completions. Portable installers still preserve each machine's prior state."
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
        head = {
            "schema_version": "khaos-brain.operator-automation-activation-head.v1",
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "receipt_ref": {
                "relative_path": f"receipts/{record_path.name}",
                "sha256": _sha256(record_path),
            },
        }
        _write_text_atomic(
            root / "HEAD.json",
            json.dumps(head, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        validation = validate_operator_activation_receipt(
            repo_root,
            codex_home,
            record_path,
        )
    except Exception as exc:
        pause = pause_repo_automations(codex_home)
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
