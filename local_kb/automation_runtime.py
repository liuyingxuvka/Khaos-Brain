"""Immutable per-run receipts for target-owned KB maintenance routes.

Regression tests prove that a software version can perform the work.  This
module proves a different fact: one concrete native maintenance run reached a
declared terminal and produced enough target-owned evidence to close that
exact run independently.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from local_kb.automation_contracts import (
    AGGREGATE_ASSURANCE_TIMEOUT_SECONDS,
    AUTOMATION_COMPLETION_CONTRACTS,
    PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS,
    STANDARD_NATIVE_TIMEOUT_SECONDS,
    STANDARD_OWNER_TIMEOUT_SECONDS,
    UPDATE_NATIVE_TIMEOUT_SECONDS,
    UPDATE_OWNER_TIMEOUT_SECONDS,
    obligation_id,
)
from local_kb.software_update import LEGAL_MANUAL_UPDATE_NOOP_REASONS


RUNTIME_RECEIPT_SCHEMA = "khaos-brain.automation-native-receipt.v1"
RUNTIME_WRAPPER_SCHEMA = "khaos-brain.automation-execution-result.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def content_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def _command_identity_issues(
    skill_id: str,
    command: object,
    *,
    run_id: str,
    fixture: str,
) -> list[str]:
    parts = [str(item) for item in _list(command)]
    if fixture:
        expected = ["fixture", fixture, skill_id]
        return [] if parts == expected else ["fixture-command-identity-mismatch"]
    if len(parts) < 2:
        return ["native-command-missing"]
    expected_script = str(
        AUTOMATION_COMPLETION_CONTRACTS[skill_id]["entrypoint_path"]
    ).replace("\\", "/")
    actual_script = parts[1].replace("\\", "/")
    issues: list[str] = []
    if not actual_script.endswith(expected_script):
        issues.append(
            f"native-entrypoint-mismatch:expected={expected_script};actual={actual_script}"
        )
    if parts.count("--run-id") != 1:
        issues.append("native-command-run-id-flag-count-mismatch")
    else:
        index = parts.index("--run-id")
        actual_run_id = parts[index + 1] if index + 1 < len(parts) else ""
        if actual_run_id != run_id:
            issues.append(
                f"native-command-run-id-mismatch:expected={run_id};actual={actual_run_id or '<missing>'}"
            )
    if skill_id in {"kb-organization-contribute", "kb-organization-maintenance"}:
        if parts.count("--automation") != 1:
            issues.append("native-command-automation-mode-missing")
    elif skill_id == "khaos-brain-update":
        if parts.count("--explicit-user-request") != 1:
            issues.append("manual-update-explicit-request-flag-count-mismatch")
        if "--automation" in parts:
            issues.append("manual-update-automation-mode-forbidden")
        if "--json" not in parts:
            issues.append("native-command-json-mode-missing")
    elif "--json" not in parts:
        issues.append("native-command-json-mode-missing")
    return issues


def _read_json_mapping(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _real_artifact_issues(
    skill_id: str,
    payload: Mapping[str, Any],
    *,
    receipt_path: Path,
) -> list[str]:
    """Validate target-owned durable artifacts for non-fixture maintenance runs."""

    issues: list[str] = []

    def require_file(raw: object, code: str) -> Path | None:
        text = str(raw or "").strip()
        if not text:
            issues.append(f"{code}:path-missing")
            return None
        candidate = Path(text)
        if not candidate.is_absolute():
            try:
                repo_root = receipt_path.resolve().parents[4]
            except IndexError:
                repo_root = Path.cwd()
            candidate = repo_root / candidate
        if not candidate.is_file():
            issues.append(f"{code}:file-missing")
            return None
        return candidate

    terminal_status = str(payload.get("status") or "")
    gated_noop = (
        payload.get("skipped") is True
        or terminal_status == "no-op"
    )
    if gated_noop:
        return issues
    if skill_id == "kb-sleep-maintenance":
        native = require_file(payload.get("receipt_path"), "sleep-native-receipt")
        if native is not None:
            recorded = _read_json_mapping(native)
            for key, value in payload.items():
                if (
                    key not in {"receipt_path", "_owner_timeout_policy"}
                    and recorded.get(key) != value
                ):
                    issues.append(f"sleep-native-receipt-content-mismatch:{key}")
                    break
    elif skill_id == "kb-dream-pass":
        artifacts = _mapping(payload.get("artifact_paths"))
        report = require_file(artifacts.get("report_path"), "dream-report")
        run_dir = Path(str(artifacts.get("run_dir") or ""))
        if not run_dir.is_dir():
            issues.append("dream-run-dir-missing")
        if report is not None:
            recorded = _read_json_mapping(report)
            if str(recorded.get("run_id") or "") != str(payload.get("run_id") or ""):
                issues.append("dream-report-run-id-mismatch")
    elif skill_id in {"kb-organization-contribute", "kb-organization-maintenance"}:
        postflight = require_file(payload.get("postflight_path"), "organization-postflight")
        if postflight is not None and postflight.stat().st_size <= 0:
            issues.append("organization-postflight-empty")
    elif skill_id == "khaos-brain-update":
        if terminal_status == "current-and-restored":
            finalization = _mapping(payload.get("update_finalization"))
            if _mapping(finalization.get("restoration")).get("ok") is not True:
                issues.append("update-restoration-receipt-missing")
            if _mapping(finalization.get("final_install_check")).get("ok") is not True:
                issues.append("update-final-install-check-missing")
            if _mapping(payload.get("snapshot_cleanup")).get("ok") is not True:
                issues.append("update-snapshot-cleanup-missing")
        else:
            snapshot = _mapping(payload.get("automation_state_snapshot"))
            snapshot_path = require_file(
                snapshot.get("path"), "update-automation-snapshot"
            )
            if snapshot_path is not None:
                recorded = _read_json_mapping(snapshot_path)
                if _mapping(recorded.get("states")) != _mapping(
                    snapshot.get("states")
                ):
                    issues.append("update-automation-snapshot-content-mismatch")
    return issues


def automation_run_root(repo_root: Path, skill_id: str, run_id: str) -> Path:
    return Path(repo_root) / ".local" / "automation-runs" / skill_id / run_id


def _evidence(
    ok: bool,
    detail: str,
    *source_fields: str,
    outcome: str = "performed",
    branch_id: str = "full-route",
) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "detail": detail,
        "source_fields": list(source_fields),
        "outcome": outcome if ok else "failed",
        "branch_id": branch_id,
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _is_github_repo_url(value: object) -> bool:
    text = str(value or "").strip().lower()
    return "github.com/" in text or text.startswith("git@github.com:")


def _organization_materialization_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _organization_materialization_ok(
    branch: Mapping[str, Any],
    *,
    required: bool,
    require_readback: bool,
) -> bool:
    if not required:
        return True
    materialization = _mapping(branch.get("materialization_receipt"))
    readback = _mapping(branch.get("pre_push_readback"))
    organization_check = _mapping(branch.get("organization_check"))
    checks = _mapping(organization_check.get("checks"))
    declared = [
        str(item) for item in _list(materialization.get("declared_changed_files"))
    ]
    materialized_rows = [
        _mapping(item) for item in _list(materialization.get("materialized_files"))
    ]
    materialized_paths = [str(item.get("path") or "") for item in materialized_rows]
    file_sha256 = _mapping(materialization.get("file_sha256"))
    checked_files = [str(item) for item in _list(organization_check.get("changed_files"))]
    materialization_content = {
        "declared_changed_files": sorted(set(declared)),
        "materialized_files": [dict(item) for item in materialized_rows],
        "file_sha256": dict(file_sha256),
    }
    materialization_body = {
        **materialization_content,
        "head_commit": str(materialization.get("head_commit") or ""),
    }
    materialized_complete = bool(
        materialization.get("ok") is True
        and not _list(materialization.get("issues"))
        and str(materialization.get("schema_version") or "")
        == "khaos-brain.organization-materialization.v1"
        and materialization.get("manifest_hash")
        == _organization_materialization_hash(materialization_content)
        and materialization.get("receipt_hash")
        == _organization_materialization_hash(materialization_body)
        and declared
        and len(declared) == len(set(declared))
        and sorted(declared) == sorted(materialized_paths)
        and set(file_sha256) == set(declared)
        and all(
            path
            and (
                str(row.get("sha256") or "")
                if row.get("deleted") is not True
                else "__deleted__"
            )
            == str(file_sha256.get(path) or "")
            and isinstance(row.get("bytes"), int)
            and int(row.get("bytes")) >= 0
            for path, row in zip(materialized_paths, materialized_rows)
        )
        and organization_check.get("ok") is True
        and sorted(checked_files) == sorted(declared)
        and _mapping(checks.get("path_policy")).get("ok") is True
        and _mapping(checks.get("privacy_scan")).get("ok") is True
        and _mapping(checks.get("skill_registry")).get("ok") is True
    )
    if not materialized_complete:
        return False
    if not require_readback:
        return True
    readback_declared = [
        str(item) for item in _list(readback.get("declared_changed_files"))
    ]
    readback_rows = [
        _mapping(item) for item in _list(readback.get("materialized_files"))
    ]
    readback_file_sha256 = _mapping(readback.get("file_sha256"))
    readback_content = {
        "declared_changed_files": sorted(set(readback_declared)),
        "materialized_files": [dict(item) for item in readback_rows],
        "file_sha256": dict(readback_file_sha256),
    }
    readback_body = {
        **readback_content,
        "head_commit": str(readback.get("head_commit") or ""),
    }
    return bool(
        readback.get("ok") is True
        and not _list(readback.get("issues"))
        and readback.get("manifest_hash")
        == _organization_materialization_hash(readback_content)
        and readback.get("receipt_hash")
        == _organization_materialization_hash(readback_body)
        and str(readback.get("head_commit") or "")
        and readback.get("manifest_hash") == materialization.get("manifest_hash")
        and readback_file_sha256 == file_sha256
        and sorted(readback_declared) == sorted(declared)
    )


def _all_domain_suffixes(skill_id: str) -> tuple[str, ...]:
    return tuple(
        str(row["suffix"])
        for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]
        if str(row["suffix"]) != "depth-calibration"
        and str(row.get("evidence_source") or "native-receipt") == "native-receipt"
    )


def _not_applicable_evidence(
    skill_id: str,
    suffix: str,
    detail: str,
    branch_id: str,
    *source_fields: str,
    gate_facts: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_gate_facts = {
        "run_id": str(gate_facts.get("run_id") or ""),
        "gate_id": str(gate_facts.get("gate_id") or ""),
        "evaluated": gate_facts.get("evaluated") is True,
        "applicable": gate_facts.get("applicable") is True,
        "reason": str(gate_facts.get("reason") or ""),
        "mutation_performed": gate_facts.get("mutation_performed") is True,
        "terminal_status": str(gate_facts.get("terminal_status") or ""),
    }
    if (
        not normalized_gate_facts["run_id"]
        or not normalized_gate_facts["gate_id"]
        or normalized_gate_facts["evaluated"] is not True
        or normalized_gate_facts["applicable"] is not False
        or not normalized_gate_facts["reason"]
        or normalized_gate_facts["mutation_performed"] is not False
        or normalized_gate_facts["terminal_status"] not in {"completed", "no-op"}
        or not source_fields
    ):
        return _evidence(
            False,
            (
                "The native owner did not provide a complete terminal gate and "
                f"non-mutation basis for not-applicable disposition: {skill_id}:{suffix}:{branch_id}"
            ),
            *source_fields,
            branch_id=branch_id,
        )
    row = _evidence(
        True,
        detail,
        *source_fields,
        outcome="not_applicable",
        branch_id=branch_id,
    )
    proof_id = content_hash(
        {
            "skill_id": skill_id,
            "obligation_suffix": suffix,
            "branch_id": branch_id,
            "source_fields": list(source_fields),
            "gate_facts": normalized_gate_facts,
        }
    )
    row["applicability"] = {
        "gate_id": normalized_gate_facts["gate_id"],
        "evaluated": True,
        "applicable": False,
        "reason": normalized_gate_facts["reason"],
        "proof_id": proof_id,
    }
    row["non_mutation"] = {
        "proven": True,
        "mutation_performed": False,
        "gate_facts_hash": content_hash(normalized_gate_facts),
        "proof_id": proof_id,
    }
    row["terminal_gate"] = dict(normalized_gate_facts)
    return row


def _timeout_tree_cleanup_evidence(
    skill_id: str,
    payload: Mapping[str, Any],
    exit_code: int,
) -> dict[str, Any]:
    policy = _mapping(payload.get("_owner_timeout_policy"))
    expected_native = (
        UPDATE_NATIVE_TIMEOUT_SECONDS
        if skill_id == "khaos-brain-update"
        else STANDARD_NATIVE_TIMEOUT_SECONDS
    )
    expected_guarded = (
        UPDATE_OWNER_TIMEOUT_SECONDS
        if skill_id == "khaos-brain-update"
        else STANDARD_OWNER_TIMEOUT_SECONDS
    )
    timed_out = policy.get("timed_out") is True or int(exit_code) == 124
    cleanup_ok = bool(
        not timed_out
        or (
            policy.get("cleanup_confirmed") is True
            and _nonnegative_int(policy.get("remaining_process_count")) == 0
        )
    )
    configured_hierarchy_ok = bool(
        expected_native
        < expected_guarded
        < AGGREGATE_ASSURANCE_TIMEOUT_SECONDS
        < PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS
    )
    hierarchy_ok = bool(
        configured_hierarchy_ok
        and (
            not policy
            and not timed_out
            or (
                _nonnegative_int(policy.get("native_timeout_seconds"))
                == expected_native
                and _nonnegative_int(policy.get("owner_timeout_seconds"))
                == expected_guarded
                and _nonnegative_int(policy.get("aggregate_timeout_seconds"))
                == AGGREGATE_ASSURANCE_TIMEOUT_SECONDS
                and _nonnegative_int(policy.get("installer_timeout_seconds"))
                == PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS
            )
        )
    )
    if not timed_out and hierarchy_ok and cleanup_ok:
        terminal_status = (
            "no-op"
            if payload.get("skipped") is True
            or payload.get("status") == "no-op"
            or payload.get("final_run_state") == "no_delta"
            else "completed"
        )
        return _not_applicable_evidence(
            skill_id,
            "timeout-tree-cleanup",
            "No timeout occurred; the ordered timeout hierarchy proves that process-tree cleanup was not applicable to this run.",
            "timeout-not-observed",
            "_owner_timeout_policy",
            gate_facts={
                "run_id": payload.get("run_id"),
                "gate_id": "owned-process-tree-timeout",
                "evaluated": True,
                "applicable": False,
                "reason": "timeout-not-observed",
                "mutation_performed": False,
                "terminal_status": terminal_status,
            },
        )
    return _evidence(
        hierarchy_ok and cleanup_ok,
        "The guarded native owner is bound to an ordered timeout hierarchy and any observed timeout has zero remaining descendants.",
        "_owner_timeout_policy",
        branch_id="timeout-cleanup",
    )


def _gated_noop_evidence(
    skill_id: str,
    reason: str,
    branch_id: str,
    obligation_sources: Mapping[str, tuple[str, ...]],
    *,
    gate_facts: Mapping[str, Any],
    performed_suffixes: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    expected_suffixes = set(_all_domain_suffixes(skill_id))
    if set(obligation_sources) != expected_suffixes:
        raise ValueError(
            f"gated no-op evidence map mismatch for {skill_id}: "
            f"{sorted(expected_suffixes ^ set(obligation_sources))}"
        )
    performed = set(performed_suffixes)
    if len(performed) != 1 or not performed.issubset(expected_suffixes):
        raise ValueError(
            f"gated no-op must have exactly one performed gate obligation for {skill_id}: "
            f"{sorted(performed)}"
        )
    normalized_gate_facts = {
        "run_id": str(gate_facts.get("run_id") or ""),
        "gate_id": str(gate_facts.get("gate_id") or ""),
        "evaluated": gate_facts.get("evaluated") is True,
        "applicable": gate_facts.get("applicable") is True,
        "reason": str(gate_facts.get("reason") or ""),
        "mutation_performed": gate_facts.get("mutation_performed") is True,
        "terminal_status": str(gate_facts.get("terminal_status") or ""),
    }
    if (
        not normalized_gate_facts["run_id"]
        or not normalized_gate_facts["gate_id"]
        or normalized_gate_facts["evaluated"] is not True
        or normalized_gate_facts["applicable"] is not False
        or normalized_gate_facts["reason"] != reason
        or normalized_gate_facts["mutation_performed"] is not False
        or normalized_gate_facts["terminal_status"] != "no-op"
    ):
        raise ValueError(
            f"gated no-op facts are incomplete or inconsistent for {skill_id}:{branch_id}"
        )
    evidence: dict[str, dict[str, Any]] = {}
    for suffix in _all_domain_suffixes(skill_id):
        sources = obligation_sources[suffix]
        if not sources:
            raise ValueError(
                f"gated no-op evidence has no source fields for {skill_id}:{suffix}"
            )
        if suffix in performed:
            row = _evidence(
                True,
                f"The native owner performed the {suffix} gate for branch {branch_id}: {reason}",
                "native_payload.reason",
                *sources,
                branch_id=branch_id,
            )
        else:
            row = _not_applicable_evidence(
                skill_id,
                suffix,
                f"The native owner proved {suffix} was not applicable in branch {branch_id} without performing its mutation: {reason}",
                branch_id,
                "native_payload.reason",
                *sources,
                gate_facts=normalized_gate_facts,
            )
        evidence[obligation_id(skill_id, suffix)] = row
    return evidence


def _blocked_branch_evidence(
    skill_id: str,
    reason: str,
    branch_id: str,
    *source_fields: str,
) -> dict[str, dict[str, Any]]:
    return {
        obligation_id(skill_id, suffix): _evidence(
            False,
            f"The {branch_id} branch is retryable and cannot close {suffix}: {reason}",
            "native_payload.reason",
            *source_fields,
            branch_id=branch_id,
        )
        for suffix in _all_domain_suffixes(skill_id)
    }


def _sleep_lock_facts(payload: Mapping[str, Any]) -> tuple[bool, bool]:
    run_id = str(payload.get("run_id") or "")
    lane_lock = _mapping(payload.get("lane_lock"))
    lock_release = _mapping(payload.get("lock_release"))
    released_lock = _mapping(lock_release.get("lock"))
    acquired = bool(
        run_id
        and lane_lock.get("group") == "local-maintenance"
        and lane_lock.get("lane") == "kb-sleep"
        and lane_lock.get("run_id") == run_id
        and lane_lock.get("acquired") is True
    )
    released = bool(
        acquired
        and lock_release.get("ok") is True
        and lock_release.get("released") is True
        and lock_release.get("group") == "local-maintenance"
        and lock_release.get("lane") == "kb-sleep"
        and lock_release.get("run_id") == run_id
        and released_lock.get("group") == "local-maintenance"
        and released_lock.get("lane") == "kb-sleep"
        and released_lock.get("run_id") == run_id
    )
    return acquired, released


def _sleep_lifecycle_review_complete(review: Mapping[str, Any]) -> bool:
    decision_ids = [str(item) for item in _list(review.get("decision_ids"))]
    count_fields = (
        "reviewed",
        "promoted",
        "downgraded",
        "reopened",
        "parked",
        "decision_count",
        "due_remaining",
    )
    counts = {key: _nonnegative_int(review.get(key)) for key in count_fields}
    return bool(
        all(value is not None for value in counts.values())
        and not _list(review.get("issues"))
        and counts["decision_count"] == len(decision_ids)
        and len(decision_ids) == len(set(decision_ids))
        and counts["decision_count"]
        == counts["promoted"]
        + counts["downgraded"]
        + counts["reopened"]
        + counts["parked"]
        and counts["due_remaining"] == 0
        and _mapping(review.get("projection_validation")).get("ok") is True
    )


def _sleep_evidence(payload: Mapping[str, Any], exit_code: int) -> dict[str, dict[str, Any]]:
    skill_id = "kb-sleep-maintenance"
    run_id = str(payload.get("run_id") or "")
    lane_lock = _mapping(payload.get("lane_lock"))
    lock_release = _mapping(payload.get("lock_release"))
    terminal_gate = _mapping(payload.get("terminal_gate"))
    reason = str(payload.get("reason") or "")
    if (
        payload.get("final_run_state") == "retryable"
        and payload.get("retryable") is True
        and reason == "maintenance-lane-active"
        and terminal_gate.get("gate_id") == "shared-maintenance-lane"
        and terminal_gate.get("evaluated") is True
        and terminal_gate.get("applicable") is False
        and terminal_gate.get("reason") == reason
        and lane_lock.get("group") == "local-maintenance"
        and lane_lock.get("lane") == "kb-sleep"
        and lane_lock.get("run_id") == run_id
        and lane_lock.get("acquired") is False
        and bool(_mapping(lane_lock.get("blocked_by")))
        and lock_release.get("released") is False
    ):
        return _blocked_branch_evidence(
            skill_id,
            reason,
            "maintenance-lane-contention",
            "native_payload.run_id",
            "native_payload.lane_lock",
            "native_payload.lock_release",
            "native_payload.terminal_gate",
        )
    consumed_range = _mapping(payload.get("consumed_range"))
    lifecycle_review = _mapping(payload.get("lifecycle_review"))
    lifecycle_review_complete = _sleep_lifecycle_review_complete(lifecycle_review)
    lock_acquired, lock_released = _sleep_lock_facts(payload)
    acknowledgements = [str(item) for item in _list(payload.get("handoff_acknowledgements"))]
    blockers = _list(payload.get("blockers"))
    input_watermark = payload.get("input_watermark")
    output_watermark = payload.get("output_watermark")
    completed = exit_code == 0 and payload.get("final_run_state") == "completed"
    opening_backlog = payload.get("opening_actionable_backlog")
    newly_admitted = payload.get("newly_admitted")
    terminally_disposed = payload.get("terminally_disposed")
    explicitly_parked = payload.get("explicitly_parked")
    closing_backlog = payload.get("closing_actionable_backlog")
    disposition_ids = [str(item) for item in _list(payload.get("disposition_ids"))]
    backlog_delta = payload.get("backlog_delta")
    model_generation = _mapping(payload.get("model_generation"))
    model_receipt = _mapping(model_generation.get("receipt"))
    model_diagnostics = _mapping(payload.get("model_diagnostics"))
    generation_id = str(
        model_receipt.get("generation_id")
        or model_generation.get("generation_id")
        or ""
    )
    scope_meshes = _mapping(
        model_receipt.get("scope_meshes") or model_generation.get("scope_meshes")
    )
    model_generation_current = bool(
        model_generation.get("ok") is True
        and str(model_generation.get("status") or "") in {"committed", "no_delta"}
        and generation_id
        and isinstance(model_diagnostics.get("cards_with_gaps"), int)
        and isinstance(model_diagnostics.get("gap_counts"), Mapping)
        and model_diagnostics.get("all_gaps_dispositioned") is True
        and isinstance(model_diagnostics.get("reviewed_gap_count"), int)
        and int(model_diagnostics.get("reviewed_gap_count") or 0)
        == len(_list(model_diagnostics.get("gap_ledger")))
    )
    valid_counts = all(
        isinstance(value, int) and value >= 0
        for value in (
            opening_backlog,
            newly_admitted,
            terminally_disposed,
            explicitly_parked,
            closing_backlog,
        )
    ) and isinstance(backlog_delta, int)
    actionable_before = (
        int(opening_backlog) + int(newly_admitted) if valid_counts else -1
    )
    convergence_ok = bool(
        valid_counts
        and int(backlog_delta)
        == int(closing_backlog) - actionable_before
        and int(closing_backlog) <= actionable_before
        and (
            actionable_before == 0
            or int(closing_backlog) < actionable_before
        )
    )
    return {
        obligation_id(skill_id, "lane-delta-intake"): _evidence(
            bool(
                run_id
                and lock_acquired
                and isinstance(input_watermark, int)
                and isinstance(output_watermark, int)
                and isinstance(consumed_range.get("inclusive_start"), int)
                and isinstance(consumed_range.get("exclusive_end"), int)
                and consumed_range.get("inclusive_start") == input_watermark
                and int(consumed_range.get("exclusive_end")) >= int(input_watermark)
                and output_watermark == consumed_range.get("exclusive_end")
                and str(payload.get("consumed_digest") or "")
                and payload.get("input_digest") == payload.get("consumed_digest")
                and str(payload.get("input_generation") or "")
                and str(payload.get("policy_version") or "")
            ),
            "Native Sleep receipt binds the run id, committed watermark range, and consumed digest.",
            "run_id",
            "lane_lock",
            "input_watermark",
            "output_watermark",
            "consumed_range",
            "consumed_digest",
        ),
        obligation_id(skill_id, "observation-disposition"): _evidence(
            valid_counts
            and convergence_ok
            and len(disposition_ids) == len(set(disposition_ids))
            and (int(newly_admitted) == 0 or bool(disposition_ids)),
            "Native Sleep receipt reports admission, disposition, parking, and closing backlog counts.",
            "newly_admitted",
            "terminally_disposed",
            "explicitly_parked",
            "closing_actionable_backlog",
            "disposition_ids",
        ),
        obligation_id(skill_id, "candidate-outcomes"): _evidence(
            lifecycle_review_complete
            and isinstance(payload.get("candidate_created"), int)
            and int(payload.get("candidate_created") or 0) >= 0
            and isinstance(payload.get("candidate_reused"), int)
            and int(payload.get("candidate_reused") or 0) >= 0,
            "Native lifecycle review and candidate create/reuse counts are present.",
            "lifecycle_review",
            "candidate_created",
            "candidate_reused",
        ),
        obligation_id(skill_id, "evidence-calibration"): _evidence(
            lifecycle_review_complete,
            "The native lifecycle review contains current promotion, suspension, and downgrade decisions.",
            "lifecycle_review",
        ),
        obligation_id(skill_id, "logicguard-model-revision"): _evidence(
            model_generation_current,
            "Sleep bound its lifecycle batch to one exact LogicGuard authority generation and reported explicit typed role gaps.",
            "model_generation",
            "model_diagnostics",
        ),
        obligation_id(skill_id, "grounded-model-mesh"): _evidence(
            model_generation_current
            and (
                int(
                    model_receipt.get("projection_count")
                    or model_generation.get("projection_count")
                    or 0
                )
                == 0
                or bool(scope_meshes)
            ),
            "The exact Sleep generation carries its scoped ModelMesh revisions; a zero-card generation is the only mesh-free case.",
            "model_generation.receipt.scope_meshes",
            "model_generation.scope_meshes",
            "model_generation.projection_count",
        ),
        obligation_id(skill_id, "dream-handoff-once"): _evidence(
            len(acknowledgements) == len(set(acknowledgements)),
            "Dream handoff acknowledgement ids are unique in the native receipt.",
            "handoff_acknowledgements",
        ),
        obligation_id(skill_id, "atomic-model-generation"): _evidence(
            model_generation_current
            and _mapping(payload.get("post_review_index_refresh")).get("ok") is True
            and _mapping(payload.get("index_validation")).get("ok") is True,
            "Sleep completed the model/mesh/projection/index generation before the exact active-index validation and terminal watermark commit.",
            "model_generation",
            "post_review_index_refresh",
            "index_validation",
        ),
        obligation_id(skill_id, "index-watermark-commit"): _evidence(
            bool(
                completed
                and lock_released
                and str(payload.get("index_receipt_id") or "")
                and _mapping(payload.get("index_validation")).get("ok") is True
                and isinstance(input_watermark, int)
                and isinstance(output_watermark, int)
                and output_watermark >= input_watermark
            ),
            "The native terminal proves validated index publication before a non-regressing watermark commit.",
            "index_receipt_id",
            "index_validation",
            "input_watermark",
            "output_watermark",
            "final_run_state",
            "lock_release",
        ),
        obligation_id(skill_id, "failure-fail-closed"): _evidence(
            completed and not blockers and lock_acquired and lock_released,
            "This successful native terminal has no blocker; failure-path watermark preservation is separately regression-tested.",
            "blockers",
            "final_run_state",
            "input_watermark",
            "output_watermark",
            "lane_lock",
            "lock_release",
        ),
    }


def _dream_evidence(payload: Mapping[str, Any], exit_code: int) -> dict[str, dict[str, Any]]:
    skill_id = "kb-dream-pass"
    status = str(payload.get("status") or "")
    reason = str(payload.get("reason") or "")
    lane_guard = _mapping(payload.get("lane_guard"))
    terminal_gate = _mapping(payload.get("terminal_gate"))
    if (
        exit_code == 0
        and status == "skipped"
        and reason == "maintenance-lane-active"
        and str(payload.get("run_id") or "")
        and lane_guard.get("blocked") is True
        and bool(_list(lane_guard.get("blocking_lanes")))
        and terminal_gate.get("gate_id") == "maintenance-lane"
        and terminal_gate.get("evaluated") is True
        and terminal_gate.get("applicable") is False
        and terminal_gate.get("reason") == reason
    ):
        return _blocked_branch_evidence(
            skill_id,
            reason,
            "maintenance-lane-contention",
            "native_payload.run_id",
            "native_payload.lane_guard",
            "native_payload.terminal_gate",
        )
    fingerprints = [str(item) for item in _list(payload.get("evaluated_fingerprints"))]
    handoffs = [str(item) for item in _list(payload.get("emitted_handoff_ids"))]
    experiments = _list(payload.get("experiments"))
    execution_plan = _mapping(payload.get("execution_plan"))
    artifacts = _mapping(payload.get("artifact_paths"))
    evidence_deltas = [str(item) for item in _list(payload.get("evidence_deltas"))]
    opportunity_count = payload.get("opportunity_count")
    executable_count = payload.get("executable_opportunity_count")
    valuable_count = payload.get("valuable_opportunity_count")
    selected_count = payload.get("selected_experiment_count")
    valid_counts = all(
        isinstance(value, int) and value >= 0
        for value in (
            opportunity_count,
            executable_count,
            valuable_count,
            selected_count,
            payload.get("suppressed_duplicate_count"),
            payload.get("no_delta_closed_count"),
        )
    )
    completed = exit_code == 0 and status == "completed"
    authority_pin = _mapping(payload.get("authority_pin"))
    simulation_rows = [
        _mapping(_mapping(item).get("logicguard_simulation"))
        for item in experiments
    ]
    exact_simulations = bool(
        int(selected_count or 0) == 0
        or (
            len(simulation_rows) == int(selected_count or 0)
            and all(
                row.get("authority") == "simulation-only"
                and row.get("canonical_authority_mutated") is False
                and str(
                    _mapping(row.get("binding")).get("logicguard_model_id") or ""
                )
                and str(
                    _mapping(row.get("binding")).get("logicguard_revision_id") or ""
                )
                and str(
                    _mapping(row.get("binding")).get("logicguard_mesh_revision_id")
                    or ""
                )
                and str(_mapping(row.get("simulation_receipt")).get("receipt_id") or "")
                and {
                    "evidence-removal",
                    "assumption-removal",
                    "rebuttal-strengthening",
                    "boundary-pressure",
                    "cross-edge-removal",
                    "neighbor-pin-replacement",
                }.issubset(
                    set(
                        str(item)
                        for item in _list(row.get("planned_perturbation_kinds"))
                    )
                )
                and bool(_list(row.get("perturbations")))
                and set(
                    str(item)
                    for item in _list(row.get("executed_perturbation_kinds"))
                )
                == {
                    str(_mapping(item).get("kind") or "")
                    for item in _list(row.get("perturbations"))
                }
                and all(
                    str(
                        _mapping(_mapping(item).get("simulation_receipt")).get(
                            "receipt_id"
                        )
                        or ""
                    )
                    for item in _list(row.get("perturbations"))
                )
                for row in simulation_rows
            )
        )
    )
    return {
        obligation_id(skill_id, "lane-evidence-intake"): _evidence(
            bool(
                str(payload.get("run_id") or "")
                and lane_guard.get("lane") in {None, "", "kb-dream"}
                and lane_guard.get("blocked") is False
            ),
            "Native Dream receipt binds its run id and lane guard.",
            "run_id",
            "lane_guard",
        ),
        obligation_id(skill_id, "stable-fingerprint"): _evidence(
            bool(str(payload.get("input_digest") or ""))
            and len(fingerprints) == len(set(fingerprints))
            and all(fingerprints)
            and valid_counts
            and int(opportunity_count) == len(fingerprints),
            "Evaluated evidence fingerprints are present as a unique stable set.",
            "evaluated_fingerprints",
            "input_digest",
        ),
        obligation_id(skill_id, "bounded-selection"): _evidence(
            valid_counts
            and int(selected_count) == len(experiments)
            and int(selected_count) == len(evidence_deltas)
            and 0 <= int(selected_count) <= int(valuable_count) <= int(executable_count) <= int(opportunity_count)
            and set(evidence_deltas).issubset(set(fingerprints)),
            "Native Dream selection count matches its bounded experiment records.",
            "selected_experiment_count",
            "experiments",
        ),
        obligation_id(skill_id, "sandbox-experiment"): _evidence(
            bool(
                execution_plan.get("status") == "completed"
                and artifacts.get("run_dir")
                and artifacts.get("report_path")
                and (
                    int(selected_count or 0) == 0
                    or all(isinstance(item, Mapping) and item for item in experiments)
                )
            ),
            "The native execution plan closed and identifies its bounded run artifacts.",
            "execution_plan",
            "artifact_paths",
        ),
        obligation_id(skill_id, "exact-model-simulation"): _evidence(
            bool(
                str(authority_pin.get("generation_id") or "")
                and str(authority_pin.get("pointer_digest") or "")
                and authority_pin.get("unchanged_after_run") is True
                and exact_simulations
            ),
            "Dream pinned one immutable LogicGuard generation and every selected experiment carries an exact model/mesh simulation receipt.",
            "authority_pin",
            "experiments.logicguard_simulation",
        ),
        obligation_id(skill_id, "no-delta-closure"): _evidence(
            valid_counts
            and str(payload.get("final_run_state") or "") in {"no_delta", "completed"}
            and (
                (int(selected_count) == 0 and str(payload.get("final_run_state")) == "no_delta")
                or (int(selected_count) > 0 and str(payload.get("final_run_state")) == "completed")
            ),
            "The native terminal distinguishes no-delta convergence from a material completed pass.",
            "final_run_state",
            "no_delta_closed_count",
        ),
        obligation_id(skill_id, "typed-handoff-once"): _evidence(
            len(handoffs) == len(set(handoffs))
            and len(handoffs) == int(selected_count or 0),
            "Typed Sleep handoff ids are unique in this native Dream run.",
            "emitted_handoff_ids",
        ),
        obligation_id(skill_id, "no-direct-knowledge-write"): _evidence(
            not _list(payload.get("history_event_ids"))
            and int(payload.get("created_candidate_count") or 0) == 0,
            "The native Dream receipt reports no central history event and no direct candidate creation.",
            "history_event_ids",
            "created_candidate_count",
        ),
        obligation_id(skill_id, "canonical-generation-unchanged"): _evidence(
            bool(
                authority_pin.get("unchanged_after_run") is True
                and str(authority_pin.get("generation_id") or "")
                and not _list(payload.get("history_event_ids"))
                and int(payload.get("created_candidate_count") or 0) == 0
            ),
            "Dream proved the pinned canonical generation was unchanged and emitted no direct knowledge mutation.",
            "authority_pin",
            "history_event_ids",
            "created_candidate_count",
        ),
        obligation_id(skill_id, "terminal-receipt"): _evidence(
            completed
            and not _list(payload.get("blockers"))
            and bool(artifacts.get("report_path"))
            and _mapping(payload.get("lock_release")).get("ok") is True
            and _mapping(payload.get("lock_release")).get("released") is True,
            "The native Dream report reached a complete terminal and names its durable report.",
            "status",
            "blockers",
            "artifact_paths.report_path",
        ),
    }


def _org_contribution_evidence(
    payload: Mapping[str, Any], exit_code: int
) -> dict[str, dict[str, Any]]:
    skill_id = "kb-organization-contribute"
    gate = _mapping(payload.get("settings_gate"))
    reason = str(payload.get("reason") or "")
    terminal_gate = _mapping(payload.get("terminal_gate"))
    if (
        exit_code == 0
        and payload.get("ok") is True
        and payload.get("skipped") is True
        and reason == "organization mode is not connected to a validated repository"
        and str(payload.get("run_id") or "")
        and gate.get("available") is False
        and terminal_gate.get("gate_id") == "organization-settings"
        and terminal_gate.get("evaluated") is True
        and terminal_gate.get("applicable") is False
        and terminal_gate.get("reason") == reason
    ):
        return _gated_noop_evidence(
            skill_id,
            reason,
            "organization-settings-inapplicable",
            {
                "settings-noop-gate": (
                    "native_payload.run_id",
                    "native_payload.settings_gate",
                    "native_payload.terminal_gate",
                ),
                "sync-preflight": (
                    "native_payload.settings_gate.available",
                    "native_payload.terminal_gate.applicable",
                ),
                "privacy-shareability": (
                    "native_payload.settings_gate",
                    "native_payload.skipped",
                ),
                "content-hash-dedup": (
                    "native_payload.settings_gate",
                    "native_payload.skipped",
                ),
                "skill-bundle-author-version": (
                    "native_payload.settings_gate",
                    "native_payload.skipped",
                ),
                "branch-pr-auto-merge": (
                    "native_payload.terminal_gate",
                    "native_payload.skipped",
                ),
                "postflight-terminal": (
                    "native_payload.ok",
                    "native_payload.skipped",
                    "native_payload.terminal_gate",
                ),
                "lane-failure-recovery": (
                    "native_payload.settings_gate.available",
                    "native_payload.terminal_gate.applicable",
                ),
            },
            gate_facts={
                "run_id": payload.get("run_id"),
                "gate_id": terminal_gate.get("gate_id"),
                "evaluated": terminal_gate.get("evaluated"),
                "applicable": terminal_gate.get("applicable"),
                "reason": terminal_gate.get("reason"),
                "mutation_performed": False,
                "terminal_status": "no-op",
            },
            performed_suffixes=(
                "settings-noop-gate",
            ),
        )
    sync = _mapping(payload.get("sync"))
    preflight = _mapping(payload.get("preflight"))
    outbox = _mapping(payload.get("outbox"))
    branch = _mapping(payload.get("branch"))
    lock_release = _mapping(payload.get("lock_release"))
    requested = _mapping(payload.get("requested_actions"))
    source = _mapping(payload.get("source"))
    privacy_checkpoint = _mapping(outbox.get("privacy_checkpoint"))
    skill_bundle_checkpoint = _mapping(outbox.get("skill_bundle_checkpoint"))
    pending_count_value = (
        outbox.get("pending_count")
        if "pending_count" in outbox
        else outbox.get("created_count")
    )
    pending_count = int(pending_count_value or 0)
    push_result = _mapping(branch.get("push"))
    pull_request = _mapping(branch.get("pull_request"))
    organization_check = _mapping(branch.get("organization_check"))
    restore_base = _mapping(branch.get("restore_base"))
    github_repo = _is_github_repo_url(source.get("repo_url"))
    pull_request_closed = (
        pull_request.get("ok") is True
        and (not github_repo or pull_request.get("attempted") is True)
    )
    push_closed = requested.get("push") is not True or (
        push_result.get("pushed") is True and pull_request_closed
    )
    label_closed = (
        organization_check.get("auto_merge_eligible") is not True
        or not github_repo
        or "org-kb:auto-merge" in _list(pull_request.get("labels"))
    )
    materialization_closed = _organization_materialization_ok(
        branch,
        required=pending_count > 0,
        require_readback=pending_count > 0 and requested.get("push") is True,
    )
    branch_closed = pending_count == 0 or (
        branch.get("attempted") is True
        and branch.get("ok") is True
        and organization_check.get("ok") is True
        and restore_base.get("ok") is True
        and materialization_closed
        and push_closed
        and label_closed
    )
    created_rows = _list(outbox.get("created"))
    skipped_rows = _list(outbox.get("skipped"))
    created_count = outbox.get("created_count")
    skipped_count = outbox.get("skipped_count")
    reviewed_count = privacy_checkpoint.get("reviewed_count")
    blocked_sensitive_count = privacy_checkpoint.get("blocked_sensitive_count")
    valid_outbox_counts = bool(
        isinstance(created_count, int)
        and created_count >= 0
        and isinstance(skipped_count, int)
        and skipped_count >= 0
        and created_count == len(created_rows)
        and skipped_count == len(skipped_rows)
        and isinstance(reviewed_count, int)
        and reviewed_count >= 0
        and reviewed_count == created_count + skipped_count
        and isinstance(blocked_sensitive_count, int)
        and 0 <= blocked_sensitive_count <= skipped_count
    )
    if pending_count == 0:
        branch_route_evidence = _not_applicable_evidence(
            skill_id,
            "branch-pr-auto-merge",
            "The native owner proved that branch, pull-request, and label mutation was not applicable because the current outbox contained no pending proposal.",
            "no-pending-organization-proposal",
            "outbox.pending_count",
            "branch.attempted",
            gate_facts={
                "run_id": payload.get("run_id"),
                "gate_id": "organization-pending-proposals",
                "evaluated": True,
                "applicable": False,
                "reason": "no-pending-organization-proposal",
                "mutation_performed": branch.get("attempted") is True,
                "terminal_status": "completed",
            },
        )
    else:
        branch_source_fields = [
            "outbox.pending_count",
            "branch.attempted",
            "branch.ok",
            "branch.materialization_receipt",
            "branch.organization_check",
            "branch.restore_base",
        ]
        if requested.get("push") is True:
            branch_source_fields.extend(
                (
                    "branch.pre_push_readback",
                    "branch.push",
                    "branch.pull_request",
                )
            )
        branch_route_evidence = _evidence(
            branch_closed,
            "The native branch, materialization, organization-check, optional push, pull-request, and label route closed for the current pending proposals.",
            *branch_source_fields,
        )
    return {
        obligation_id(skill_id, "settings-noop-gate"): _evidence(
            gate.get("available") is True and gate.get("organization_validated") is True,
            "Validated organization settings admitted the native contribution route.",
            "settings_gate",
        ),
        obligation_id(skill_id, "sync-preflight"): _evidence(
            sync.get("ok") is True and bool(preflight),
            "The native receipt proves organization sync and KB preflight before export.",
            "sync",
            "preflight",
        ),
        obligation_id(skill_id, "privacy-shareability"): _evidence(
            outbox.get("ok") is True
            and privacy_checkpoint.get("complete") is True
            and valid_outbox_counts,
            "The native outbox records a completed pre-materialization privacy checkpoint.",
            "outbox.privacy_checkpoint",
        ),
        obligation_id(skill_id, "content-hash-dedup"): _evidence(
            outbox.get("ok") is True
            and valid_outbox_counts,
            "The native outbox reports created and content-hash-skipped decisions.",
            "outbox.created_count",
            "outbox.skipped_count",
        ),
        obligation_id(skill_id, "skill-bundle-author-version"): _evidence(
            skill_bundle_checkpoint.get("complete") is True
            and all(
                isinstance(skill_bundle_checkpoint.get(key), int)
                and int(skill_bundle_checkpoint.get(key)) >= 0
                for key in (
                    "dependency_count",
                    "bundle_count",
                    "dependency_evidence_reviewed_count",
                    "dependency_evidence_blocked_count",
                )
            )
            and int(skill_bundle_checkpoint.get("bundle_count"))
            <= int(skill_bundle_checkpoint.get("dependency_count"))
            and int(skill_bundle_checkpoint.get("dependency_evidence_blocked_count"))
            <= int(skill_bundle_checkpoint.get("dependency_evidence_reviewed_count"))
            and not _list(skill_bundle_checkpoint.get("errors")),
            "The native outbox records a complete Skill bundle author/version policy checkpoint.",
            "outbox.skill_bundle_checkpoint",
        ),
        obligation_id(skill_id, "branch-pr-auto-merge"): branch_route_evidence,
        obligation_id(skill_id, "postflight-terminal"): _evidence(
            payload.get("ok") is True and payload.get("postflight_recorded") is True,
            "A non-skipped scheduled contribution has a structured postflight terminal.",
            "postflight_recorded",
            "postflight_path",
        ),
        obligation_id(skill_id, "lane-failure-recovery"): _evidence(
            exit_code == 0
            and payload.get("ok") is True
            and lock_release.get("ok") is True
            and lock_release.get("released") is True,
            "The native lane closed successfully and returned its lock-release receipt.",
            "ok",
            "lock_release",
        ),
    }


def _org_maintenance_evidence(
    payload: Mapping[str, Any], exit_code: int
) -> dict[str, dict[str, Any]]:
    skill_id = "kb-organization-maintenance"
    gate = _mapping(payload.get("settings_gate"))
    reason = str(payload.get("reason") or "")
    participation = _mapping(payload.get("participation"))
    terminal_gate = _mapping(payload.get("terminal_gate"))
    if (
        exit_code == 0
        and payload.get("ok") is True
        and payload.get("skipped") is True
        and reason
        in {
            "organization mode is not connected to a validated repository",
            "organization maintenance participation is not requested",
            "organization maintenance participation is not available",
        }
        and str(payload.get("run_id") or "")
        and gate.get("available") is False
        and participation.get("available") is False
        and participation.get("reason") == reason
        and terminal_gate.get("gate_id") == "organization-maintenance-participation"
        and terminal_gate.get("evaluated") is True
        and terminal_gate.get("applicable") is False
        and terminal_gate.get("reason") == reason
    ):
        return _gated_noop_evidence(
            skill_id,
            reason,
            "organization-maintenance-inapplicable",
            {
                "settings-participation-gate": (
                    "native_payload.run_id",
                    "native_payload.settings_gate",
                    "native_payload.participation",
                    "native_payload.terminal_gate",
                ),
                "manifest-git-preflight": (
                    "native_payload.settings_gate.available",
                    "native_payload.participation.available",
                ),
                "card-candidate-intake": (
                    "native_payload.participation",
                    "native_payload.skipped",
                ),
                "card-decision-coverage": (
                    "native_payload.participation",
                    "native_payload.skipped",
                ),
                "merge-split-decisions": (
                    "native_payload.participation",
                    "native_payload.skipped",
                ),
                "skill-safety-version": (
                    "native_payload.participation",
                    "native_payload.skipped",
                ),
                "exact-selected-apply": (
                    "native_payload.terminal_gate",
                    "native_payload.skipped",
                ),
                "postapply-merge-readiness": (
                    "native_payload.terminal_gate",
                    "native_payload.skipped",
                ),
                "postflight-terminal": (
                    "native_payload.ok",
                    "native_payload.skipped",
                    "native_payload.terminal_gate",
                ),
            },
            gate_facts={
                "run_id": payload.get("run_id"),
                "gate_id": terminal_gate.get("gate_id"),
                "evaluated": terminal_gate.get("evaluated"),
                "applicable": terminal_gate.get("applicable"),
                "reason": terminal_gate.get("reason"),
                "mutation_performed": False,
                "terminal_status": "no-op",
            },
            performed_suffixes=(
                "settings-participation-gate",
            ),
        )
    report = _mapping(payload.get("report"))
    validation = _mapping(report.get("validation"))
    organization_check = _mapping(report.get("organization_check"))
    cleanup = _mapping(report.get("cleanup"))
    review = _mapping(cleanup.get("review"))
    apply_result = _mapping(cleanup.get("apply"))
    post_apply = _mapping(cleanup.get("post_apply_check"))
    card_decision_checkpoint = _mapping(cleanup.get("card_decision_checkpoint"))
    merge_split = _mapping(cleanup.get("merge_split_checkpoint"))
    skill_safety = _mapping(cleanup.get("skill_safety_checkpoint"))
    exact_apply = _mapping(cleanup.get("exact_selected_apply"))
    merge_readiness = _mapping(cleanup.get("github_merge_readiness"))
    proposal_counts = _mapping(cleanup.get("proposal_counts"))
    branch = _mapping(payload.get("maintenance_branch"))
    lock_release = _mapping(payload.get("lock_release"))
    selected_ids = [str(item) for item in _list(review.get("selected_action_ids"))]
    applied_ids = [str(item) for item in _list(apply_result.get("applied_action_ids"))]
    proposal_count_values = {
        str(key): _nonnegative_int(value) for key, value in proposal_counts.items()
    }
    proposal_counts_valid = all(value is not None for value in proposal_count_values.values())
    expected_merge_count = int(proposal_count_values.get("merge-cards") or 0)
    expected_split_count = int(proposal_count_values.get("split-card") or 0)
    expected_skill_count = sum(
        int(proposal_count_values.get(key) or 0)
        for key in (
            "skill-version-select",
            "skill-bundle-safety-block",
            "skill-bundle-fork-required",
        )
    )
    expected_skill_blockers = sum(
        int(proposal_count_values.get(key) or 0)
        for key in ("skill-bundle-safety-block", "skill-bundle-fork-required")
    )
    merge_ids = [str(item) for item in _list(merge_split.get("merge_decision_ids"))]
    split_ids = [str(item) for item in _list(merge_split.get("split_decision_ids"))]
    skill_decision_ids = [str(item) for item in _list(skill_safety.get("decision_ids"))]
    skill_blocking_ids = [str(item) for item in _list(skill_safety.get("blocking_decision_ids"))]
    github_repo = _is_github_repo_url(_mapping(payload.get("source")).get("repo_url"))
    branch_push = _mapping(branch.get("push"))
    branch_pr = _mapping(branch_push.get("pull_request"))
    card_decisions = [
        _mapping(item) for item in _list(card_decision_checkpoint.get("decisions"))
    ]
    card_decision_ids = [str(item.get("decision_id") or "") for item in card_decisions]
    card_decision_paths = [str(item.get("target_path") or "") for item in card_decisions]
    required_card_dimensions = {"scenario", "action", "prediction", "route", "evidence"}
    apply_closed = not selected_ids or (
        apply_result.get("attempted") is True
        and apply_result.get("ok") is True
    )
    postapply_closed = not selected_ids or post_apply.get("ok") is True
    maintenance_materialization_closed = _organization_materialization_ok(
        branch,
        required=bool(selected_ids),
        require_readback=bool(selected_ids),
    )
    main_active_count = _nonnegative_int(report.get("main_active_count"))
    imports_count = _nonnegative_int(report.get("imports_count"))
    proposal_action_count = _nonnegative_int(cleanup.get("proposal_action_count"))
    reviewed_card_count = _nonnegative_int(card_decision_checkpoint.get("card_count"))
    inventory_counts_valid = bool(
        main_active_count is not None
        and imports_count is not None
        and proposal_action_count is not None
        and reviewed_card_count is not None
        and reviewed_card_count >= main_active_count + imports_count
        and proposal_counts_valid
        and proposal_action_count == sum(
            int(value or 0) for value in proposal_count_values.values()
        )
    )
    postapply_source_fields = [
        "report.cleanup.post_apply_check",
        "report.cleanup.github_merge_readiness",
        "maintenance_branch",
    ]
    if selected_ids:
        postapply_source_fields.extend(
            (
                "maintenance_branch.materialization_receipt",
                "maintenance_branch.pre_push_readback",
                "maintenance_branch.organization_check",
                "maintenance_branch.restore_base",
            )
        )
    postapply_evidence = _evidence(
        postapply_closed
        and maintenance_materialization_closed
        and (
            not selected_ids
            or (
                branch.get("attempted") is True
                and branch.get("ok") is True
                and _mapping(branch.get("restore_base")).get("ok") is True
            )
        )
        and merge_readiness.get("complete") is True
        and (
            merge_readiness.get("eligible") is not True
            or (
                str(merge_readiness.get("label") or "") == "org-kb:auto-merge"
                and (
                    not github_repo
                    or (
                        branch_push.get("pushed") is True
                        and branch_pr.get("attempted") is True
                        and branch_pr.get("ok") is True
                    )
                )
                and (
                    not github_repo
                    or "org-kb:auto-merge" in _list(branch_pr.get("labels"))
                )
            )
        ),
        "Post-apply validation produced a complete GitHub readiness decision that gates the label.",
        *postapply_source_fields,
    )
    return {
        obligation_id(skill_id, "settings-participation-gate"): _evidence(
            gate.get("available") is True
            and gate.get("organization_validated") is True
            and gate.get("maintenance_requested") is True,
            "Validated organization settings and explicit maintenance participation admitted the route.",
            "settings_gate",
            "participation",
        ),
        obligation_id(skill_id, "manifest-git-preflight"): _evidence(
            _mapping(payload.get("sync")).get("ok") is True
            and validation.get("ok") is True
            and organization_check.get("ok") is True
            and bool(_mapping(payload.get("preflight"))),
            "Native sync, preflight, manifest/layout validation, and organization checks passed.",
            "sync",
            "preflight",
            "report.validation",
            "report.organization_check",
        ),
        obligation_id(skill_id, "card-candidate-intake"): _evidence(
            inventory_counts_valid,
            "The native report inventories main, imports, and cleanup proposals.",
            "report.main_active_count",
            "report.imports_count",
            "report.cleanup.proposal_action_count",
        ),
        obligation_id(skill_id, "card-decision-coverage"): _evidence(
            card_decision_checkpoint.get("complete") is True
            and inventory_counts_valid
            and _nonnegative_int(card_decision_checkpoint.get("decision_count")) == len(card_decisions)
            and reviewed_card_count == len(card_decisions)
            and len(card_decision_ids) == len(set(card_decision_ids))
            and all(card_decision_paths)
            and len(card_decision_paths) == len(set(card_decision_paths))
            and set(_list(card_decision_checkpoint.get("decision_ids"))) == set(card_decision_ids)
            and all(
                str(item.get("decision") or "") in {"keep", "watch", "change"}
                and bool(str(item.get("reason") or "").strip())
                and set(_list(item.get("reviewed_dimensions"))) == required_card_dimensions
                for item in card_decisions
            ),
            "Every native reviewed card has exactly one reasoned decision across all required dimensions.",
            "report.cleanup.card_decision_checkpoint",
        ),
        obligation_id(skill_id, "merge-split-decisions"): _evidence(
            merge_split.get("complete") is True
            and _nonnegative_int(merge_split.get("reviewed_card_count")) == reviewed_card_count
            and proposal_counts_valid
            and isinstance(merge_split.get("merge_decision_ids"), list)
            and isinstance(merge_split.get("split_decision_ids"), list)
            and len(merge_ids) == len(set(merge_ids)) == expected_merge_count
            and len(split_ids) == len(set(split_ids)) == expected_split_count,
            "The native report records an explicit merge and overloaded-card split checkpoint.",
            "report.cleanup.merge_split_checkpoint",
        ),
        obligation_id(skill_id, "skill-safety-version"): _evidence(
            skill_safety.get("complete") is True
            and skill_safety.get("passed") is True
            and proposal_counts_valid
            and isinstance(skill_safety.get("decision_ids"), list)
            and len(skill_decision_ids) == len(set(skill_decision_ids)) == expected_skill_count
            and len(skill_blocking_ids) == expected_skill_blockers == 0,
            "The native report records a passed Skill registry, hash, author, fork, and version checkpoint.",
            "report.cleanup.skill_safety_checkpoint",
        ),
        obligation_id(skill_id, "exact-selected-apply"): _evidence(
            len(selected_ids) == len(set(selected_ids))
            and len(applied_ids) == len(set(applied_ids))
            and apply_closed
            and exact_apply.get("complete") is True
            and exact_apply.get("exact") is True
            and set(selected_ids) == set(applied_ids)
            and set(_list(exact_apply.get("selected_action_ids"))) == set(selected_ids)
            and set(_list(exact_apply.get("applied_action_ids"))) == set(applied_ids),
            "The report proves the applied action-id set exactly equals the unique selected set.",
            "report.cleanup.exact_selected_apply",
        ),
        obligation_id(skill_id, "postapply-merge-readiness"): postapply_evidence,
        obligation_id(skill_id, "postflight-terminal"): _evidence(
            exit_code == 0
            and payload.get("ok") is True
            and payload.get("postflight_recorded") is True
            and lock_release.get("ok") is True
            and lock_release.get("released") is True,
            "The non-skipped native maintenance run recorded postflight and released its lane.",
            "ok",
            "postflight_recorded",
            "postflight_path",
            "lock_release",
        ),
    }


def _update_evidence(payload: Mapping[str, Any], exit_code: int) -> dict[str, dict[str, Any]]:
    skill_id = "khaos-brain-update"
    status = str(payload.get("status") or "")
    manual_check = _mapping(payload.get("manual_check"))
    reason = str(payload.get("reason") or "")
    terminal_gate = _mapping(payload.get("terminal_gate"))
    if (
        exit_code == 0
        and status == "no-op"
        and reason in LEGAL_MANUAL_UPDATE_NOOP_REASONS
        and manual_check.get("ok") is True
        and manual_check.get("apply_ready") is False
        and manual_check.get("reason") == reason
        and str(payload.get("run_id") or "")
        and terminal_gate.get("gate_id") == "manual-update-check"
        and terminal_gate.get("evaluated") is True
        and terminal_gate.get("applicable") is False
        and terminal_gate.get("reason") == reason
    ):
        return _gated_noop_evidence(
            skill_id,
            reason,
            "manual-update-check-only",
            {
                "authorization-system-check": (
                    "native_payload.run_id",
                    "native_payload.manual_check",
                    "native_payload.terminal_gate",
                ),
                "preserve-state-rollback": (
                    "native_payload.manual_check.apply_ready",
                    "native_payload.terminal_gate.applicable",
                ),
                "fast-forward-only": (
                    "native_payload.manual_check",
                    "native_payload.terminal_gate",
                ),
                "migration-debt-settlement": (
                    "native_payload.manual_check",
                    "native_payload.terminal_gate",
                ),
                "logicguard-authority-cutover": (
                    "native_payload.manual_check.apply_ready",
                    "native_payload.terminal_gate.applicable",
                ),
                "transaction-retirement": (
                    "native_payload.manual_check",
                    "native_payload.terminal_gate",
                ),
                "zero-retired-authority": (
                    "native_payload.manual_check.apply_ready",
                    "native_payload.terminal_gate.applicable",
                ),
                "aggregate-hard-gates": (
                    "native_payload.manual_check",
                    "native_payload.terminal_gate",
                ),
                "restore-or-stay-paused": (
                    "native_payload.manual_check.apply_ready",
                    "native_payload.terminal_gate.applicable",
                ),
                "final-machine-receipt": (
                    "native_payload.status",
                    "native_payload.reason",
                    "native_payload.manual_check",
                    "native_payload.terminal_gate",
                ),
            },
            gate_facts={
                "run_id": payload.get("run_id"),
                "gate_id": terminal_gate.get("gate_id"),
                "evaluated": terminal_gate.get("evaluated"),
                "applicable": terminal_gate.get("applicable"),
                "reason": terminal_gate.get("reason"),
                "mutation_performed": False,
                "terminal_status": "no-op",
            },
            performed_suffixes=(
                "authorization-system-check",
            ),
        )
    install = _mapping(payload.get("install"))
    install_check = _mapping(payload.get("install_check"))
    git_update = _mapping(payload.get("git_update"))
    migration = _mapping(install.get("history_migration"))
    migration_validation = _mapping(
        migration.get("validation")
        or _mapping(migration.get("receipt")).get("final_validation")
    )
    logicguard_authority = _mapping(
        migration_validation.get("logicguard_authority")
    )
    paused_transaction = _mapping(install.get("paused_install_transaction"))
    install_transaction = _mapping(install.get("install_transaction"))
    checked_transaction = _mapping(install_check.get("install_transaction"))
    automation_snapshot = _mapping(payload.get("automation_state_snapshot"))
    snapshot_states = _mapping(automation_snapshot.get("states"))
    snapshot_user_paused = _mapping(automation_snapshot.get("user_paused"))
    pause_before_mutation = _mapping(payload.get("pause_before_mutation"))
    update_finalization = _mapping(payload.get("update_finalization"))
    restoration_plan = _mapping(update_finalization.get("restoration_plan"))
    deferred_install_check = _mapping(
        update_finalization.get("deferred_install_check")
    )
    restoration = _mapping(update_finalization.get("restoration"))
    final_install_check = _mapping(
        update_finalization.get("final_install_check")
    )
    update_state = _mapping(payload.get("update_state"))
    snapshot_cleanup = _mapping(payload.get("snapshot_cleanup"))
    retired_skill_ids = {str(item) for item in _list(install.get("retired_skill_ids"))}
    retired_automation_ids = {str(item) for item in _list(install.get("retired_automation_ids"))}
    automations = [
        _mapping(item) for item in _list(install.get("automations"))
    ]
    survivor_ids = {
        "kb-sleep",
        "kb-dream",
        "kb-org-contribute",
        "kb-org-maintenance",
    }
    return {
        obligation_id(skill_id, "authorization-system-check"): _evidence(
            manual_check.get("apply_ready") is True
            and manual_check.get("reason") == "explicit-request-and-ui-closed",
            "The native manual gate proves an explicit current user request with the UI closed.",
            "manual_check",
        ),
        obligation_id(skill_id, "preserve-state-rollback"): _evidence(
            paused_transaction.get("ok") is True
            and install_transaction.get("ok") is True
            and bool(str(paused_transaction.get("transaction_id") or ""))
            and bool(str(install_transaction.get("transaction_id") or ""))
            and paused_transaction.get("transaction_id") != install_transaction.get("transaction_id")
            and bool(str(paused_transaction.get("receipt_hash") or ""))
            and bool(str(install_transaction.get("receipt_hash") or ""))
            and set(snapshot_states) == survivor_ids
            and all(str(value) in {"ACTIVE", "PAUSED"} for value in snapshot_states.values())
            and pause_before_mutation.get("ok") is True,
            "The transactional installer reports paused-state preservation and activation/rollback authority.",
            "install.paused_install_transaction",
            "install.install_transaction",
        ),
        obligation_id(skill_id, "fast-forward-only"): _evidence(
            git_update.get("ok") is True and git_update.get("mode") == "ff-only",
            "The source update completed only through the declared fast-forward route.",
            "git_update",
        ),
        obligation_id(skill_id, "migration-debt-settlement"): _evidence(
            migration.get("ok") is True
            and str(migration.get("status") or "")
            in {"committed", "current", "no_delta", "reconciled"},
            "The install receipt includes a successful/current versioned maintenance migration.",
            "install.history_migration",
        ),
        obligation_id(skill_id, "logicguard-authority-cutover"): _evidence(
            migration.get("ok") is True
            and str(migration.get("migration_id") or "")
            == "kb-maintenance-standard-v4-logicguard-native"
            and logicguard_authority.get("ok") is True
            and bool(str(logicguard_authority.get("generation_id") or "")),
            "The versioned update owner published and validated one exact current LogicGuard authority generation.",
            "install.history_migration.migration_id",
            "install.history_migration.validation.logicguard_authority",
        ),
        obligation_id(skill_id, "transaction-retirement"): _evidence(
            install_transaction.get("ok") is True
            and retired_skill_ids == {"kb-architect-pass"}
            and retired_automation_ids
            == {"kb-architect", "khaos-brain-system-update"},
            "The native update used a committed transaction whose retirement set contains the exact Architect and system-update automation surfaces.",
            "install.install_transaction",
            "install.retired_skill_ids",
            "install.retired_automation_ids",
        ),
        obligation_id(skill_id, "zero-retired-authority"): _evidence(
            migration_validation.get("ok") is True
            and logicguard_authority.get("zero_legacy_projection_residuals") is True
            and int(migration_validation.get("residual_managed_file_count") or 0) == 0,
            "The terminal migration validation found no retired semantic authority or managed physical residual.",
            "install.history_migration.validation",
        ),
        obligation_id(skill_id, "aggregate-hard-gates"): _evidence(
            install_check.get("ok") is True
            and install.get("automation_restore_deferred") is True
            and install_check.get("automation_restore_deferred") is True
            and install_check.get("deferred_automation_restore_allowed") is True
            and _mapping(install.get("upgrade_assurance")).get("ok") is True
            and checked_transaction.get("status") == "committed"
            and checked_transaction.get("transaction_id") == install_transaction.get("transaction_id")
            and checked_transaction.get("receipt_hash") == install_transaction.get("receipt_hash"),
            "Install health and aggregate upgrade assurance both passed.",
            "install_check",
            "install.upgrade_assurance",
        ),
        obligation_id(skill_id, "restore-or-stay-paused"): _evidence(
            install_transaction.get("ok") is True
            and restoration_plan.get("ok") is True
            and restoration.get("ok") is True
            and restoration.get("plan_hash") == restoration_plan.get("plan_hash")
            and _mapping(restoration.get("restored")) == {
                str(key): str(value) for key, value in snapshot_states.items()
            }
            and _mapping(restoration.get("restored_user_paused"))
            == {
                str(key): bool(value)
                for key, value in snapshot_user_paused.items()
            }
            and deferred_install_check.get("ok") is True
            and final_install_check.get("ok") is True
            and set(snapshot_states) == survivor_ids
            and all(
                str(item.get("id") or "") != "kb-architect"
                for item in automations
            ),
            "The native route restored the exact captured status and user-pause state only after every target-owned gate passed.",
            "automation_state_snapshot",
            "update_finalization.restoration_plan",
            "update_finalization.restoration",
            "update_finalization.final_install_check",
        ),
        obligation_id(skill_id, "final-machine-receipt"): _evidence(
            exit_code == 0
            and status == "current-and-restored"
            and install_check.get("ok") is True
            and final_install_check.get("ok") is True
            and update_state.get("status") == "current"
            and snapshot_cleanup.get("ok") is True
            and _mapping(payload.get("lock_release")).get("ok") is True,
            "The native update reached its final terminal only after exact restoration, final installed-health readback, CURRENT state, snapshot cleanup, and lock release.",
            "status",
            "install_check",
            "update_finalization.final_install_check",
            "update_state",
            "snapshot_cleanup",
            "lock_release",
        ),
    }


def evaluate_native_payload(
    skill_id: str,
    payload: Mapping[str, Any],
    *,
    exit_code: int,
    expected_run_id: str = "",
) -> dict[str, Any]:
    evaluators = {
        "kb-sleep-maintenance": _sleep_evidence,
        "kb-dream-pass": _dream_evidence,
        "kb-organization-contribute": _org_contribution_evidence,
        "kb-organization-maintenance": _org_maintenance_evidence,
        "khaos-brain-update": _update_evidence,
    }
    if skill_id not in evaluators:
        return {"ok": False, "terminal_status": "failed", "evidence": {}, "issues": ["unknown skill"]}
    evidence = evaluators[skill_id](payload, int(exit_code))
    expected = {
        obligation_id(skill_id, suffix) for suffix in _all_domain_suffixes(skill_id)
    }
    actual = set(evidence)
    issues = []
    if actual != expected:
        issues.append(f"evidence-set-mismatch:{sorted(expected ^ actual)}")
    failed = sorted(item for item, row in evidence.items() if row.get("ok") is not True)
    if failed:
        issues.append(f"obligations-failed:{failed}")
    payload_run_id = str(payload.get("run_id") or "")
    if expected_run_id and payload_run_id != expected_run_id:
        issues.append(
            f"native-run-id-mismatch:expected={expected_run_id};actual={payload_run_id or '<missing>'}"
        )
    ok = not issues and int(exit_code) == 0
    noop = (
        payload.get("skipped") is True
        or payload.get("status") == "no-op"
        or payload.get("final_run_state") == "no_delta"
    )
    return {
        "ok": ok,
        "terminal_status": "no-op" if ok and noop else "completed" if ok else "failed",
        "evidence": evidence,
        "issues": issues,
    }


def build_native_receipt(
    skill_id: str,
    *,
    run_id: str,
    command: list[str],
    native_payload: Mapping[str, Any],
    exit_code: int,
    started_at: str,
    finished_at: str | None = None,
    fixture: str = "",
) -> dict[str, Any]:
    evaluation = evaluate_native_payload(
        skill_id,
        native_payload,
        exit_code=exit_code,
        expected_run_id=run_id,
    )
    command_issues = _command_identity_issues(
        skill_id,
        command,
        run_id=run_id,
        fixture=fixture,
    )
    if command_issues:
        evaluation = {
            **evaluation,
            "ok": False,
            "terminal_status": "failed",
            "issues": [*evaluation.get("issues", []), *command_issues],
        }
    receipt: dict[str, Any] = {
        "schema_version": RUNTIME_RECEIPT_SCHEMA,
        "skill_id": skill_id,
        "automation_id": AUTOMATION_COMPLETION_CONTRACTS[skill_id]["automation_id"],
        "execution_kind": AUTOMATION_COMPLETION_CONTRACTS[skill_id][
            "execution_kind"
        ],
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at or _utc_now(),
        "command": list(command),
        "command_fingerprint": content_hash(command),
        "exit_code": int(exit_code),
        "native_payload": dict(native_payload),
        "native_payload_hash": content_hash(native_payload),
        "terminal_status": evaluation["terminal_status"],
        "obligation_evidence": evaluation["evidence"],
        "evaluation_issues": evaluation["issues"],
        "fixture": fixture,
        "claim_boundary": (
            "This immutable record proves only the captured native process output and target-specific "
            "terminal validation for this run. Author-side maintenance certification and version capability regression are separate."
        ),
    }
    receipt["receipt_hash"] = content_hash(receipt)
    return receipt


def write_native_receipt(path: Path, receipt: Mapping[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def validate_native_receipt(
    path: Path,
    *,
    skill_id: str,
    phase: str = "all",
    expected_run_id: str = "",
    expected_receipt_hash: str = "",
    allow_fixture: bool = False,
) -> dict[str, Any]:
    path = Path(path)
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "issues": [f"receipt-unreadable:{type(exc).__name__}"], "path": str(path)}
    if not isinstance(receipt, dict):
        return {"ok": False, "issues": ["receipt-not-object"], "path": str(path)}
    issues: list[str] = []
    supplied_hash = str(receipt.get("receipt_hash") or "")
    unsigned = dict(receipt)
    unsigned.pop("receipt_hash", None)
    if supplied_hash != content_hash(unsigned):
        issues.append("receipt-hash-mismatch")
    if expected_receipt_hash and supplied_hash != expected_receipt_hash:
        issues.append("receipt-not-current-for-supervised-run")
    if receipt.get("schema_version") != RUNTIME_RECEIPT_SCHEMA:
        issues.append("receipt-schema-mismatch")
    if receipt.get("skill_id") != skill_id:
        issues.append("receipt-skill-mismatch")
    spec = AUTOMATION_COMPLETION_CONTRACTS[skill_id]
    if receipt.get("automation_id") != spec["automation_id"]:
        issues.append("receipt-automation-binding-mismatch")
    if receipt.get("execution_kind") != spec["execution_kind"]:
        issues.append("receipt-execution-kind-mismatch")
    if expected_run_id and receipt.get("run_id") != expected_run_id:
        issues.append("receipt-run-id-mismatch")
    command = _list(receipt.get("command"))
    if str(receipt.get("command_fingerprint") or "") != content_hash(command):
        issues.append("command-fingerprint-mismatch")
    fixture = str(receipt.get("fixture") or "")
    if fixture and not allow_fixture:
        issues.append("fixture-receipt-not-allowed-for-live-run")
    issues.extend(
        _command_identity_issues(
            skill_id,
            command,
            run_id=str(receipt.get("run_id") or ""),
            fixture=fixture,
        )
    )
    payload = _mapping(receipt.get("native_payload"))
    if str(receipt.get("native_payload_hash") or "") != content_hash(payload):
        issues.append("native-payload-hash-mismatch")
    evaluation = evaluate_native_payload(
        skill_id,
        payload,
        exit_code=int(receipt.get("exit_code") or 0),
        expected_run_id=str(receipt.get("run_id") or ""),
    )
    if evaluation["terminal_status"] != receipt.get("terminal_status"):
        issues.append("terminal-status-drift")
    if evaluation["evidence"] != receipt.get("obligation_evidence"):
        issues.append("obligation-evidence-drift")
    phases = {
        str(row["suffix"]): str(row["phase"])
        for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]
        if str(row["suffix"]) != "depth-calibration"
        and str(row.get("evidence_source") or "native-receipt") == "native-receipt"
    }
    selected_ids = {
        obligation_id(skill_id, suffix)
        for suffix, owner_phase in phases.items()
        if phase == "all" or owner_phase == phase
    }
    selected = {
        item: row
        for item, row in evaluation["evidence"].items()
        if item in selected_ids
    }
    if set(selected) != selected_ids:
        issues.append(f"phase-evidence-set-mismatch:{sorted(selected_ids ^ set(selected))}")
    failed = sorted(item for item, row in selected.items() if row.get("ok") is not True)
    if failed:
        issues.append(f"phase-obligations-failed:{failed}")
    if receipt.get("terminal_status") not in {"completed", "no-op"}:
        issues.append("native-terminal-not-successful")
    if not fixture:
        issues.extend(
            _real_artifact_issues(
                skill_id,
                payload,
                receipt_path=path,
            )
        )
    return {
        "ok": not issues,
        "skill_id": skill_id,
        "run_id": str(receipt.get("run_id") or ""),
        "phase": phase,
        "receipt_hash": supplied_hash,
        "terminal_status": receipt.get("terminal_status"),
        "selected_obligation_ids": sorted(selected_ids),
        "issues": issues,
        "path": str(path),
        "claim_boundary": "Current immutable native receipt integrity and target-specific phase evidence only.",
    }


def build_fixture_payload(
    skill_id: str,
    *,
    shallow: bool = False,
    run_id: str = "",
) -> dict[str, Any]:
    fixture_changed_files = ["kb/imports/fixture/card.yaml"]
    fixture_file_sha256 = {fixture_changed_files[0]: "fixture-file-sha256"}
    fixture_materialization = {
        "schema_version": "khaos-brain.organization-materialization.v1",
        "declared_changed_files": fixture_changed_files,
        "materialized_files": [
            {
                "path": fixture_changed_files[0],
                "sha256": "fixture-file-sha256",
                "bytes": 128,
                "deleted": False,
            }
        ],
        "file_sha256": fixture_file_sha256,
        "manifest_hash": "",
        "receipt_hash": "",
        "head_commit": "fixture-head-commit",
        "ok": True,
        "issues": [],
    }
    fixture_materialization_content = {
        "declared_changed_files": fixture_materialization[
            "declared_changed_files"
        ],
        "materialized_files": fixture_materialization["materialized_files"],
        "file_sha256": fixture_materialization["file_sha256"],
    }
    fixture_materialization["manifest_hash"] = _organization_materialization_hash(
        fixture_materialization_content
    )
    fixture_materialization["receipt_hash"] = _organization_materialization_hash(
        {
            **fixture_materialization_content,
            "head_commit": fixture_materialization["head_commit"],
        }
    )
    fixture_readback = {
        **fixture_materialization,
        "receipt_hash": fixture_materialization["receipt_hash"],
    }
    fixture_organization_check = {
        "ok": True,
        "auto_merge_eligible": True,
        "changed_files": fixture_changed_files,
        "checks": {
            "path_policy": {"ok": True},
            "privacy_scan": {"ok": True},
            "skill_registry": {"ok": True},
        },
    }
    if skill_id == "kb-sleep-maintenance":
        payload: dict[str, Any] = {
            "run_id": "fixture-sleep",
            "input_watermark": 4,
            "output_watermark": 6,
            "input_generation": "fixture-generation",
            "consumed_range": {"inclusive_start": 4, "exclusive_end": 6},
            "consumed_digest": "fixture-digest",
            "input_digest": "fixture-digest",
            "policy_version": "fixture-policy",
            "receipt_id": "fixture-sleep-receipt",
            "opening_actionable_backlog": 1,
            "newly_admitted": 1,
            "terminally_disposed": 1,
            "explicitly_parked": 1,
            "closing_actionable_backlog": 0,
            "backlog_delta": -2,
            "disposition_ids": ["fixture-disposition-a", "fixture-disposition-b"],
            "handoff_acknowledgements": ["fixture-dream-handoff"],
            "candidate_created": 1,
            "candidate_reused": 0,
            "lifecycle_review": {
                "issues": [],
                "reviewed": 1,
                "promoted": 0,
                "downgraded": 0,
                "reopened": 0,
                "parked": 0,
                "decision_count": 0,
                "decision_ids": [],
                "due_remaining": 0,
                "projection_validation": {"ok": True, "issues": []},
            },
            "model_generation": {
                "ok": True,
                "status": "committed",
                "receipt": {
                    "generation_id": "fixture-generation",
                    "projection_count": 1,
                    "scope_meshes": {
                        "candidates": {
                            "mesh_id": "fixture-mesh",
                            "mesh_revision_id": "fixture-mesh-revision",
                        }
                    },
                },
            },
            "post_review_index_refresh": {
                "ok": True,
                "status": "no_delta",
                "generation_id": "fixture-generation",
            },
            "model_diagnostics": {
                "cards_with_gaps": 1,
                "gap_counts": {"evidence": 1},
                "gap_ledger": [
                    {
                        "gap_id": "fixture-gap",
                        "gap_kind": "evidence",
                        "disposition": "open-awaiting-grounded-input",
                    }
                ],
                "reviewed_gap_count": 1,
                "all_gaps_dispositioned": True,
            },
            "index_receipt_id": "fixture-index-receipt",
            "index_validation": {"ok": True, "issues": []},
            "blockers": [],
            "final_run_state": "completed",
            "lane_lock": {
                "group": "local-maintenance",
                "lane": "kb-sleep",
                "run_id": "fixture-sleep",
                "acquired": True,
            },
            "lock_release": {
                "ok": True,
                "group": "local-maintenance",
                "lane": "kb-sleep",
                "run_id": "fixture-sleep",
                "released": True,
                "lock": {
                    "group": "local-maintenance",
                    "lane": "kb-sleep",
                    "run_id": "fixture-sleep",
                },
            },
        }
    elif skill_id == "kb-dream-pass":
        payload = {
            "run_id": "fixture-dream",
            "status": "completed",
            "lane_guard": {"lane": "kb-dream", "blocked": False},
            "execution_plan": {"status": "completed"},
            "opportunity_count": 1,
            "executable_opportunity_count": 1,
            "valuable_opportunity_count": 1,
            "evaluated_fingerprints": ["fixture-fingerprint"],
            "evidence_deltas": ["fixture-fingerprint"],
            "selected_experiment_count": 1,
            "experiments": [{"sleep_handoff_id": "fixture-sleep-handoff", "status": "passed"}],
            "suppressed_duplicate_count": 0,
            "no_delta_closed_count": 0,
            "emitted_handoff_ids": ["fixture-sleep-handoff"],
            "history_event_ids": [],
            "created_candidate_count": 0,
            "final_run_state": "completed",
            "input_digest": "fixture-input",
            "blockers": [],
            "artifact_paths": {"run_dir": "fixture/run", "report_path": "fixture/report.json"},
            "lock_release": {"ok": True, "released": True},
        }
        payload["authority_pin"] = {
            "generation_id": "fixture-generation",
            "pointer_digest": "sha256:fixture-generation",
            "unchanged_after_run": True,
        }
        payload["experiments"][0]["logicguard_simulation"] = {
            "authority": "simulation-only",
            "canonical_authority_mutated": False,
            "binding": {
                "logicguard_model_id": "fixture-model",
                "logicguard_revision_id": "fixture-model-revision",
                "logicguard_mesh_revision_id": "fixture-mesh-revision",
            },
            "simulation_receipt": {"receipt_id": "fixture-simulation-receipt"},
            "planned_perturbation_kinds": [
                "evidence-removal",
                "assumption-removal",
                "rebuttal-strengthening",
                "boundary-pressure",
                "cross-edge-removal",
                "neighbor-pin-replacement",
            ],
            "executed_perturbation_kinds": ["boundary-pressure"],
            "perturbations": [
                {
                    "kind": "boundary-pressure",
                    "simulation_receipt": {
                        "receipt_id": "fixture-simulation-receipt"
                    },
                }
            ],
        }
    elif skill_id == "kb-organization-contribute":
        payload = {
            "ok": True,
            "skipped": False,
            "settings_gate": {"available": True, "mode": "organization", "organization_validated": True},
            "sync": {"ok": True, "attempted": True},
            "preflight": {"route_hint": "system/knowledge-library/organization", "matched_entry_count": 0},
            "source": {"repo_url": "https://github.com/example/organization-kb.git"},
            "outbox": {
                "ok": True,
                "created_count": 1,
                "skipped_count": 0,
                "created": [{"entry_id": "fixture-card", "content_hash": "sha256:fixture"}],
                "skipped": [],
                "pending_count": 1,
                "privacy_checkpoint": {"complete": True, "reviewed_count": 1, "blocked_sensitive_count": 0},
                "skill_bundle_checkpoint": {
                    "complete": True,
                    "dependency_count": 1,
                    "bundle_count": 1,
                    "dependency_evidence_reviewed_count": 1,
                    "dependency_evidence_blocked_count": 0,
                    "errors": [],
                },
            },
            "requested_actions": {"prepare_branch": True, "commit": True, "push": True},
            "branch": {
                "attempted": True,
                "ok": True,
                "organization_check": fixture_organization_check,
                "materialization_receipt": fixture_materialization,
                "pre_push_readback": fixture_readback,
                "restore_base": {"ok": True},
                "push": {"pushed": True},
                "pull_request": {
                    "attempted": True,
                    "ok": True,
                    "labels": ["org-kb:auto-merge"],
                },
            },
            "postflight_recorded": True,
            "postflight_path": "fixture/postflight.jsonl",
            "lock_release": {"ok": True, "released": True},
        }
    elif skill_id == "kb-organization-maintenance":
        payload = {
            "ok": True,
            "skipped": False,
            "settings_gate": {
                "available": True,
                "mode": "organization",
                "organization_validated": True,
                "maintenance_requested": True,
            },
            "participation": {"available": True, "requested": True},
            "sync": {"ok": True, "attempted": True},
            "preflight": {"route_hint": "system/knowledge-library/organization", "matched_entry_count": 0},
            "report": {
                "ok": True,
                "validation": {"ok": True},
                "organization_check": {"ok": True},
                "main_active_count": 1,
                "imports_count": 0,
                "cleanup": {
                    "proposal_action_count": 2,
                    "proposal_counts": {"rewrite-card": 1, "skill-version-select": 1},
                    "review": {"selected_action_ids": ["fixture-action"], "decisions": []},
                    "apply": {"attempted": True, "ok": True, "applied_action_ids": ["fixture-action"]},
                    "post_apply_check": {"ok": True},
                    "card_decision_checkpoint": {
                        "complete": True,
                        "card_count": 1,
                        "decision_count": 1,
                        "decision_ids": ["fixture-card-decision"],
                        "decisions": [{
                            "decision_id": "fixture-card-decision",
                            "target_path": "kb/main/fixture-card.yaml",
                            "decision": "change",
                            "reason": "fixture evidence supports a bounded rewrite",
                            "reviewed_dimensions": ["action", "evidence", "prediction", "route", "scenario"],
                        }],
                        "required_dimensions": ["action", "evidence", "prediction", "route", "scenario"],
                    },
                    "merge_split_checkpoint": {
                        "complete": True,
                        "reviewed_card_count": 1,
                        "merge_decision_ids": [],
                        "split_decision_ids": [],
                    },
                    "skill_safety_checkpoint": {
                        "complete": True,
                        "passed": True,
                        "decision_ids": ["fixture-skill-version"],
                        "blocking_decision_ids": [],
                    },
                    "exact_selected_apply": {
                        "complete": True,
                        "exact": True,
                        "selected_action_ids": ["fixture-action"],
                        "applied_action_ids": ["fixture-action"],
                    },
                    "github_merge_readiness": {
                        "complete": True,
                        "eligible": True,
                        "label": "org-kb:auto-merge",
                        "blockers": [],
                    },
                },
            },
            "source": {"repo_url": "https://github.com/example/organization-kb.git"},
            "maintenance_branch": {
                "attempted": True,
                "ok": True,
                "organization_check": fixture_organization_check,
                "materialization_receipt": fixture_materialization,
                "pre_push_readback": fixture_readback,
                "restore_base": {"ok": True},
                "push": {
                    "pushed": True,
                    "pull_request": {
                        "attempted": True,
                        "ok": True,
                        "labels": ["org-kb:auto-merge"],
                    },
                },
            },
            "postflight_recorded": True,
            "postflight_path": "fixture/postflight.jsonl",
            "lock_release": {"ok": True, "released": True},
        }
    elif skill_id == "khaos-brain-update":
        payload = {
            "ok": True,
            "status": "current-and-restored",
            "manual_check": {
                "ok": True,
                "apply_ready": True,
                "reason": "explicit-request-and-ui-closed",
            },
            "git_update": {"ok": True, "mode": "ff-only"},
            "automation_state_snapshot": {
                "states": {
                    "kb-sleep": "ACTIVE",
                    "kb-dream": "ACTIVE",
                    "kb-org-contribute": "ACTIVE",
                    "kb-org-maintenance": "PAUSED",
                },
                "user_paused": {
                    "kb-sleep": False,
                    "kb-dream": False,
                    "kb-org-contribute": False,
                    "kb-org-maintenance": True,
                },
            },
            "pause_before_mutation": {"ok": True},
            "lock_release": {"ok": True},
            "install": {
                "paused_install_transaction": {
                    "ok": True,
                    "transaction_id": "fixture-pause-transaction",
                    "receipt_hash": "fixture-pause-hash",
                },
                "install_transaction": {
                    "ok": True,
                    "transaction_id": "fixture-restore-transaction",
                    "receipt_hash": "fixture-restore-hash",
                },
                "history_migration": {
                    "ok": True,
                    "status": "current",
                    "migration_id": "kb-maintenance-standard-v4-logicguard-native",
                    "validation": {
                        "ok": True,
                        "residual_managed_file_count": 0,
                        "logicguard_authority": {
                            "ok": True,
                            "generation_id": "fixture-generation",
                            "zero_legacy_projection_residuals": True,
                        },
                    },
                },
                "upgrade_assurance": {"ok": True},
                "automation_restore_deferred": True,
                "retired_skill_ids": ["kb-architect-pass"],
                "retired_automation_ids": [
                    "kb-architect",
                    "khaos-brain-system-update",
                ],
                "automations": [
                    {"id": "kb-sleep", "status": "ACTIVE"},
                    {"id": "kb-dream", "status": "ACTIVE"},
                    {"id": "kb-org-contribute", "status": "ACTIVE"},
                    {"id": "kb-org-maintenance", "status": "PAUSED"},
                ],
            },
            "install_check": {
                "ok": True,
                "automation_restore_deferred": True,
                "deferred_automation_restore_allowed": True,
                "strong_session_defaults": True,
                "install_transaction": {
                    "status": "committed",
                    "transaction_id": "fixture-restore-transaction",
                    "receipt_hash": "fixture-restore-hash",
                },
            },
            "update_finalization": {
                "restoration_plan": {
                    "ok": True,
                    "plan_hash": "fixture-restoration-plan",
                },
                "deferred_install_check": {"ok": True},
                "restoration": {
                    "ok": True,
                    "plan_hash": "fixture-restoration-plan",
                    "restored": {
                        "kb-sleep": "ACTIVE",
                        "kb-dream": "ACTIVE",
                        "kb-org-contribute": "ACTIVE",
                        "kb-org-maintenance": "PAUSED",
                    },
                    "restored_user_paused": {
                        "kb-sleep": False,
                        "kb-dream": False,
                        "kb-org-contribute": False,
                        "kb-org-maintenance": True,
                    },
                },
                "final_install_check": {"ok": True},
            },
            "update_state": {"status": "current"},
            "snapshot_cleanup": {"ok": True, "deleted": True},
        }
    else:
        raise KeyError(skill_id)
    payload["run_id"] = run_id or str(payload.get("run_id") or f"fixture-{skill_id}")
    payload["_owner_timeout_policy"] = {
        "native_timeout_seconds": (
            UPDATE_NATIVE_TIMEOUT_SECONDS
            if skill_id == "khaos-brain-update"
            else STANDARD_NATIVE_TIMEOUT_SECONDS
        ),
        "owner_timeout_seconds": (
            UPDATE_OWNER_TIMEOUT_SECONDS
            if skill_id == "khaos-brain-update"
            else STANDARD_OWNER_TIMEOUT_SECONDS
        ),
        "aggregate_timeout_seconds": AGGREGATE_ASSURANCE_TIMEOUT_SECONDS,
        "installer_timeout_seconds": PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS,
        "timed_out": False,
        "cleanup_confirmed": True,
        "remaining_process_count": 0,
    }
    if skill_id == "kb-sleep-maintenance":
        payload["lane_lock"]["run_id"] = payload["run_id"]
        payload["lock_release"]["run_id"] = payload["run_id"]
        payload["lock_release"]["lock"]["run_id"] = payload["run_id"]
    if shallow:
        if skill_id == "kb-sleep-maintenance":
            payload.pop("index_validation", None)
        elif skill_id == "kb-dream-pass":
            payload["execution_plan"] = {"status": "planned"}
        elif skill_id == "kb-organization-contribute":
            payload["outbox"]["privacy_checkpoint"]["complete"] = False
        elif skill_id == "kb-organization-maintenance":
            payload["report"]["cleanup"].pop("merge_split_checkpoint", None)
        elif skill_id == "khaos-brain-update":
            payload["install"]["upgrade_assurance"]["ok"] = False
    return payload


def write_fixture_receipt(
    repo_root: Path,
    skill_id: str,
    *,
    shallow: bool,
    run_id: str,
) -> Path:
    payload = build_fixture_payload(skill_id, shallow=shallow, run_id=run_id)
    receipt = build_native_receipt(
        skill_id,
        run_id=run_id,
        command=["fixture", "shallow" if shallow else "positive", skill_id],
        native_payload=payload,
        exit_code=0,
        started_at=_utc_now(),
        fixture="shallow" if shallow else "positive",
    )
    path = automation_run_root(repo_root, skill_id, run_id) / "native-receipt.json"
    return write_native_receipt(path, receipt)
