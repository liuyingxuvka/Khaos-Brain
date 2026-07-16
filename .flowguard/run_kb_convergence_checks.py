"""Run current FlowGuard checks for the KB convergence upgrade."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flowguard import (  # noqa: E402
    BoundedEventuallyProperty,
    FlowGuardCheckPlan,
    GraphEdge,
    KnownBadProof,
    MinimumModelContract,
    ProgressCheckConfig,
    RiskIntent,
    RiskProfile,
    Scenario,
    ScenarioExpectation,
    TemplateHarvestReview,
    TemplateReuseReview,
    check_progress,
    review_scenarios,
    run_model_first_checks,
)

import kb_convergence_upgrade_model as model  # noqa: E402


MODEL_PATH = Path(__file__).with_name("kb_convergence_upgrade_model.py")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _projection_digest() -> str:
    paths = (
        REPO_ROOT / "local_kb" / "lifecycle.py",
        REPO_ROOT / "local_kb" / "active_index.py",
        REPO_ROOT / "local_kb" / "dream.py",
        REPO_ROOT / "local_kb" / "maintenance_migration.py",
        REPO_ROOT / "local_kb" / "transactional_install.py",
        REPO_ROOT / "local_kb" / "install.py",
        REPO_ROOT / "local_kb" / "automation_contracts.py",
        REPO_ROOT / "local_kb" / "automation_runtime.py",
        REPO_ROOT / "local_kb" / "codex_registry.py",
        REPO_ROOT / "local_kb" / "search.py",
        REPO_ROOT / "scripts" / "install_codex_kb.py",
        REPO_ROOT / "scripts" / "check_chaos_brain_readiness.py",
        REPO_ROOT / "scripts" / "check_kb_skillguard.py",
        REPO_ROOT / "scripts" / "run_kb_guarded_automation.py",
        REPO_ROOT / "scripts" / "check_retired_kb_architect.py",
        REPO_ROOT / "tests" / "test_kb_lifecycle.py",
        REPO_ROOT / "tests" / "test_kb_upgrade_migration.py",
        REPO_ROOT / "tests" / "test_cli_output_contract.py",
        REPO_ROOT / "tests" / "test_multi_source_search.py",
        REPO_ROOT / "tests" / "test_kb_automation_skillguard.py",
    )
    rows = [f"{path.relative_to(REPO_ROOT).as_posix()}={_digest(path)}" for path in paths]
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _automation_target_bindings() -> dict[str, dict[str, object]]:
    """Bind the abstract FlowGuard child to current compiled SkillGuard targets."""

    bindings: dict[str, dict[str, object]] = {}
    for skill_id, expected_obligations in model.AUTOMATION_TARGET_OBLIGATIONS.items():
        root = REPO_ROOT / ".agents" / "skills" / skill_id / ".skillguard"
        compiled_path = root / "compiled-contract.json"
        manifest_path = root / "check-manifest.json"
        issues: list[str] = []
        try:
            compiled = json.loads(compiled_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            compiled = {}
            issues.append(f"compiled-contract-unavailable:{exc}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            manifest = {}
            issues.append(f"check-manifest-unavailable:{exc}")
        actual_obligations = tuple(
            str(row.get("obligation_id") or "")
            for row in compiled.get("obligations", [])
            if isinstance(row, dict)
        )
        expected_checks = model.automation_manifest_check_ids(skill_id)
        actual_checks = tuple(
            str(row.get("check_id") or "")
            for row in manifest.get("checks", [])
            if isinstance(row, dict)
        )
        contract_digest = str(compiled.get("contract_hash") or "")
        if str(compiled.get("skill_id") or "") != skill_id:
            issues.append("compiled-skill-id-mismatch")
        if set(actual_obligations) != set(expected_obligations):
            issues.append("compiled-obligation-set-mismatch")
        if (
            len(actual_obligations) != len(expected_obligations)
            or len(actual_obligations) != len(set(actual_obligations))
        ):
            issues.append("compiled-obligation-count-mismatch")
        if not contract_digest:
            issues.append("compiled-contract-digest-missing")
        if str(manifest.get("skill_id") or "") != skill_id:
            issues.append("manifest-skill-id-mismatch")
        if str(manifest.get("contract_hash") or "") != contract_digest:
            issues.append("manifest-contract-digest-mismatch")
        if set(actual_checks) != set(expected_checks):
            issues.append("manifest-check-id-set-mismatch")
        if len(actual_checks) != len(expected_checks) or len(actual_checks) != len(
            set(actual_checks)
        ):
            issues.append("manifest-check-ids-not-exactly-once")
        bindings[skill_id] = {
            "ok": not issues,
            "skill_id": skill_id,
            "expected_obligation_count": len(expected_obligations),
            "expected_obligation_ids": list(expected_obligations),
            "actual_obligation_ids": list(actual_obligations),
            "contract_digest": contract_digest,
            "expected_check_ids": list(expected_checks),
            "actual_check_ids": list(actual_checks),
            "issues": issues,
        }
    return bindings


def lifecycle_plan(workflow, *, proofs: tuple[KnownBadProof, ...] = ()):
    return FlowGuardCheckPlan(
        workflow=workflow,
        initial_states=model.LIFECYCLE_INITIAL_STATES,
        external_inputs=model.LIFECYCLE_INPUTS,
        invariants=model.LIFECYCLE_INVARIANTS,
        max_sequence_length=2,
        terminal_predicate=model.lifecycle_terminal,
        required_labels=(
            "observation_admitted",
            "sleep_committed",
            "sleep_failed",
            "candidate_set_trusted",
            "candidate_set_candidate",
            "candidate_set_rejected",
            "organization_candidate_visible_untrusted",
            "index_rebuilt",
            "query_fast_authority",
            "dream_handoff_emitted",
            "handoff_model_committed",
            "handoff_acknowledged",
            "no_delta_closed",
            "sleep_resume_terminal_fast_path",
            "sleep_resume_atomic_batch",
            "lifecycle_replay_linear_idempotency_index",
            "dead_lane_lock_recovered",
            "timed_out_process_tree_cleaned",
            "candidate_review_shared_evidence_index",
            "sleep_index_finalized_once",
        ),
        risk_profile=RiskProfile(
            modeled_boundary="observation-to-retrieval lifecycle and Sleep/Dream convergence",
            risk_classes=("state", "idempotency", "retrieval", "side_effect"),
            risk_intent=RiskIntent(
                failure_modes=(
                    "Sleep hides input by advancing its watermark before disposition commit",
                    "Dream writes or hands off unchanged evidence more than once",
                    "terminal knowledge leaks into active retrieval",
                    "an ineligible candidate enters active retrieval",
                    "a read-only organization candidate is either hidden or leaks into the local active index",
                    "a Dream handoff disappears without Sleep acknowledgement",
                    "a Dream handoff is acknowledged before its model publication commits",
                    "foreground retrieval replays the complete card manifest and lifecycle history",
                    "Sleep recovery replays the lifecycle ledger once per historical observation",
                    "Sleep replays the lifecycle ledger separately for every pending Dream handoff",
                    "one lifecycle replay scans every prior idempotency key again for every event",
                    "a dead lane-lock owner blocks until age expiry",
                    "a validation timeout leaves descendants or has no parent cleanup margin",
                    "candidate review reloads the full lifecycle and outcome evidence for every entry",
                    "one Sleep cycle rebuilds or validates the same final active-index generation more than once",
                    "a standard YAML date crashes organization shareability validation",
                    "the privacy scanner reports its own declared path patterns as leaked machine data",
                ),
                protected_error_classes=(
                    "premature_watermark",
                    "duplicate_dream_effect",
                    "terminal_status_leak",
                    "candidate_eligibility_leak",
                    "candidate_source_boundary_collapse",
                    "missing_handoff_ack",
                    "foreground_full_authority_replay",
                    "sleep_per_item_lifecycle_replay",
                    "dream_handoff_per_item_lifecycle_replay",
                    "lifecycle_replay_quadratic_lookup",
                    "dead_lane_lock_retained",
                    "lifecycle_writer_orphan_retained",
                    "lifecycle_writer_self_deadlock",
                    "lifecycle_writer_release_failure_hidden",
                    "orphan_process_tree",
                    "timeout_hierarchy_collapse",
                    "candidate_per_item_calibration_reload",
                    "parked_recalibrated_without_evidence_delta",
                    "parked_delta_not_checkpointed",
                    "handoff_ack_before_model_publication",
                    "duplicate_sleep_model_publication",
                    "duplicate_sleep_index_validation",
                    "date_serialization_failure",
                    "scanner_self_match",
                ),
                protected_harms=(
                    "observations disappear without decisions or stale knowledge influences future work",
                ),
                must_model_state=(
                    "admitted",
                    "dispositions",
                    "watermark",
                    "dream_closed",
                    "active_index",
                    "candidate_eligibility_evidence",
                    "organization_candidates",
                    "pending_handoffs",
                    "handoff_model_commits",
                    "handoff_acks",
                    "foreground_full_replays",
                    "sleep_resume_replay_passes",
                    "sleep_resume_batch_count",
                    "lifecycle_replay_event_count",
                    "lifecycle_replay_membership_checks",
                    "dead_lane_lock_recovered",
                    "remaining_process_count",
                    "calibration_evidence_load_count",
                    "sleep_index_rebuild_count",
                    "sleep_index_validation_count",
                    "shareability_serialization_ok",
                    "privacy_false_positive_count",
                ),
                must_model_side_effects=("dream_write", "sleep_handoff", "index_publish", "process_tree_cleanup"),
                completion_evidence=("dispositions", "active_index", "watermark", "cleanup_confirmed"),
                adversarial_inputs=("failed Sleep", "repeated fingerprint", "terminal status"),
                hard_invariants=(
                    "watermark follows committed disposition",
                    "Dream evidence fingerprint is at most once",
                    "active index contains only eligible status",
                ),
                known_bad_cases=(
                    "premature_watermark",
                    "repeat_dream_write",
                    "candidate_leak",
                    "candidate_source_collapse",
                    "missing_ack",
                    "foreground_full_replay",
                    "sleep_per_item_replay",
                    "dream_handoff_per_item_replay",
                    "quadratic_lifecycle_idempotency_lookup",
                    "dead_lane_lock_retained",
                    "lifecycle_writer_orphan_retained",
                    "lifecycle_writer_self_deadlock",
                    "lifecycle_writer_release_failure_hidden",
                    "orphan_process_tree",
                    "timeout_hierarchy_collapse",
                    "candidate_per_item_calibration_reload",
                    "parked_recalibrated_without_evidence_delta",
                    "parked_delta_not_checkpointed",
                    "handoff_ack_before_model_publication",
                    "duplicate_sleep_model_publication",
                    "duplicate_sleep_index_validation",
                    "date_serialization_failure",
                    "scanner_self_match",
                ),
                used_template_ids=("side_effect_at_most_once",),
                blindspots=("semantic evidence quality remains code-and-test validated",),
            ),
            confidence_goal="model_level",
        ),
        template_reuse_review=TemplateReuseReview(
            used_template_ids=("side_effect_at_most_once",),
            searched_layers=("public", "local"),
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=(
                "premature_watermark",
                "duplicate_dream_effect",
                "terminal_status_leak",
                "candidate_eligibility_leak",
                "candidate_source_boundary_collapse",
                "missing_handoff_ack",
                "foreground_full_authority_replay",
                "dream_handoff_per_item_lifecycle_replay",
                "lifecycle_replay_quadratic_lookup",
            ),
            modeled_state=(
                "admitted",
                "dispositions",
                "watermark",
                "dream_closed",
                "active_index",
                "candidate_eligibility_evidence",
                "organization_candidates",
                "pending_handoffs",
                "handoff_model_commits",
                "handoff_acks",
                "foreground_full_replays",
                "sleep_resume_replay_passes",
                "sleep_resume_batch_count",
                "lifecycle_replay_event_count",
                "lifecycle_replay_membership_checks",
                "dead_lane_lock_recovered",
                "remaining_process_count",
                "calibration_evidence_load_count",
                "sleep_index_rebuild_count",
                "sleep_index_validation_count",
                "shareability_serialization_ok",
                "privacy_false_positive_count",
            ),
            modeled_side_effects=("dream_write", "sleep_handoff", "index_publish", "process_tree_cleanup"),
            completion_evidence=("dispositions", "active_index", "watermark", "cleanup_confirmed"),
            known_bad_cases=(
                "premature_watermark",
                "repeat_dream_write",
                "candidate_leak",
                "candidate_source_collapse",
                "missing_ack",
                "foreground_full_replay",
                "sleep_per_item_replay",
                "dream_handoff_per_item_replay",
                "quadratic_lifecycle_idempotency_lookup",
                "dead_lane_lock_retained",
                "lifecycle_writer_orphan_retained",
                "lifecycle_writer_self_deadlock",
                "lifecycle_writer_release_failure_hidden",
                "orphan_process_tree",
                "timeout_hierarchy_collapse",
                "candidate_per_item_calibration_reload",
                "parked_recalibrated_without_evidence_delta",
                "parked_delta_not_checkpointed",
                "handoff_ack_before_model_publication",
                "duplicate_sleep_model_publication",
                "duplicate_sleep_index_validation",
                "date_serialization_failure",
                "scanner_self_match",
            ),
        ),
        known_bad_proofs=proofs,
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        scenario_matrix_config={"enabled": False},
    )


def migration_plan(workflow, *, proofs: tuple[KnownBadProof, ...] = ()):
    return FlowGuardCheckPlan(
        workflow=workflow,
        initial_states=model.MIGRATION_INITIAL_STATES,
        external_inputs=model.MIGRATION_INPUTS,
        invariants=model.MIGRATION_INVARIANTS,
        max_sequence_length=2,
        terminal_predicate=model.migration_terminal,
        required_labels=(
            "migration_begun",
            "snapshot_committed",
            "classification_committed",
            "runtime_canonicalization_committed",
            "debt_settlement_committed",
            "cold_archive_committed",
            "derived_data_pruned",
            "active_index_committed",
            "architect_removed",
            "installation_staged",
            "installation_committed",
            "installation_rolled_back",
            "migration_validated",
            "migration_committed",
            "survivors_restored",
            "migration_paused_failed",
            "migration_resumed",
            "managed_debt_reopened",
            "managed_debt_reconciled",
            "managed_path_inventoried",
            "post_commit_observation_reopened",
            "logical_debt_reconciled",
            "assurance_outer_started",
            "assurance_child_isolated",
            "aggregate_assurance_current",
        ),
        risk_profile=RiskProfile(
            modeled_boundary="versioned KB history and cross-machine installation migration",
            risk_classes=("ordering", "rollback", "idempotency", "retirement"),
            risk_intent=RiskIntent(
                failure_modes=(
                    "physical pruning precedes archive coverage",
                    "surviving automations resume before validation",
                    "migration commits with active Architect surfaces",
                    "installation activates from drifted or downgraded source",
                    "a safe contract reorganization is rejected because anti-downgrade compares check names instead of obligation and evidence coverage",
                    "installation records a receipt while its generator, compiler, or managed Skill source identity changes",
                    "installation activates without a verified rollback copy",
                    "restoration overwrites a user's paused automation state",
                    "aggregate assurance recursively launches migration while the outer lock is held",
                    "an aggregate-assurance fixture writes shared global shell tools",
                    "observations admitted during aggregate assurance are not drained and revalidated before restore",
                    "historical settlement replays and rewrites the full lifecycle authority once per item",
                    "verified Windows read-only artifacts are left undeleted or ACL failures are bypassed",
                    "a resolved retry failure remains marked active after migration commit",
                    "managed physical debt is reintroduced during validation or after commit without reopening the gate",
                    "Windows paths beyond the legacy length limit are invisible to inventory and pruning",
                    "observations admitted during a long upgrade remain hard debt after commit",
                    "surviving automations restore after commit but before current aggregate assurance",
                    "a later aggregate reruns a still-current full-regression owner instead of reusing its immutable receipt",
                    "model-test alignment binds an obligation to a raw or unknown receipt owner name and crashes instead of returning a failed gate",
                    "direct-file aggregate execution resolves a sibling owner through an unrelated scripts namespace",
                    "real scheduled production competes with performance-sensitive aggregate siblings and times out despite a healthy isolated route",
                    "a long upgrade reads mutable SkillGuard, FlowGuard, or LogicGuard package authority instead of three frozen toolchain snapshots",
                    "obsolete runtime formats remain readable or executable after the one-time upgrade boundary",
                ),
                protected_error_classes=(
                    "prune_before_archive",
                    "early_restore",
                    "residual_architect",
                    "concurrent_source_drift",
                    "skillguard_downgrade",
                    "anti_downgrade_check_id_monotonicity",
                    "authority_validation_identity_drift",
                    "authority_validation_snapshot_missing",
                    "missing_install_rollback",
                    "pause_state_loss",
                    "recursive_assurance",
                    "fixture_isolation_breach",
                    "post_assurance_data_skip",
                    "per_item_lifecycle_replay",
                    "verified_readonly_delete_unhandled",
                    "stale_committed_failure",
                    "late_managed_debt_unchecked",
                    "long_path_invisible",
                    "post_commit_logical_debt_unchecked",
                    "postcommit_preassurance_restore",
                    "duplicate_current_full_regression",
                    "aggregate_script_import_ambiguous",
                    "performance_validation_resource_competition",
                    "scheduled_production_resource_competition",
                    "runtime_compatibility_residual",
                ),
                protected_harms=(
                    "irreversible history loss or an old computer silently recreates retired maintenance",
                ),
                must_model_state=(
                    "phase",
                    "checkpoint",
                    "runtime_canonicalized",
                    "obsolete_runtime_residual_count",
                    "canonicalization_receipt_count",
                    "archive_ready",
                    "architect_present",
                    "automations_paused",
                    "committed_version",
                    "staged_manifests_match",
                    "source_fingerprint_current",
                    "authority_install_policy_id",
                    "incoming_current_compiler_validated",
                    "authority_validation_identity_stable",
                    "authority_validation_snapshot_current",
                    "authority_validation_toolchains",
                    "active_managed_tree_class",
                    "whole_tree_replacement_staged",
                    "active_semantic_comparison_performed",
                    "anti_downgrade_comparison_basis",
                    "semantic_hard_authority_preserved",
                    "current_to_current_anti_downgrade_passed",
                    "authority_install_receipt_replay_current",
                    "authority_install_member_count",
                    "rollback_verified",
                    "install_transaction_committed",
                    "prior_automation_states",
                    "restored_automation_states",
                    "assurance_context",
                    "assurance_depth",
                    "fixture_gates_skipped",
                    "fixture_shell_isolated",
                    "post_assurance_data_current",
                    "settlement_mode",
                    "settlement_event_count",
                    "settlement_replay_passes",
                    "settlement_batch_count",
                    "settlement_reused_count",
                    "prune_verified_read_only_count",
                    "prune_read_only_cleared_count",
                    "prune_resumed_deleted_count",
                    "prune_permission_blocker_count",
                    "active_failure",
                    "resolved_failure_count",
                    "migration_lock_recovery_receipt_count",
                    "migration_lock_recovery_reason",
                    "live_migration_lock_stolen",
                    "recent_ownerless_lock_stolen",
                    "managed_surface_reintroduced_count",
                    "managed_surface_residual_count",
                    "reconciliation_receipt_count",
                    "managed_long_path_count",
                    "managed_enumerated_path_count",
                    "post_commit_observation_debt_count",
                    "logical_reconciliation_receipt_count",
                    "aggregate_assurance_passed",
                    "aggregate_assurance_current",
                    "aggregate_assurance_receipt",
                    "full_regression_execution_count",
                    "full_regression_reuse_count",
                    "full_regression_duplicate_current_execution_count",
                    "full_regression_receipt_current",
                    "aggregate_script_import_current",
                    "performance_validation_lane_exclusive",
                    "scheduled_production_validation_lane_exclusive",
                ),
                must_model_side_effects=(
                    "cold_archive",
                    "physical_prune",
                    "architect_tombstone",
                    "automation_restore",
                    "managed_install",
                    "install_rollback",
                    "migration_lock_recovery",
                    "aggregate_assurance_current",
                ),
                completion_evidence=(
                    "validation_passed",
                    "committed_version",
                    "aggregate_assurance_current",
                    "side_effects",
                ),
                adversarial_inputs=(
                    "interruption",
                    "repeat",
                    "missing Architect manifest",
                    "raw or unknown model-test validation owner name",
                ),
                hard_invariants=(
                    "archive before prune",
                    "all gates before commit",
                    "restore only after commit",
                    "side effects at most once",
                    "historical settlement uses bounded atomic batches",
                    "read-only clearing follows verification and ACL blockers stop pruning",
                    "committed journal has no active failure",
                    "late managed debt reopens the gate and receives a reconciliation receipt",
                    "Windows extended-length managed paths remain visible",
                    "post-commit observation debt reopens and converges",
                    "restore requires a current aggregate-assurance receipt",
                    "only current-validated incoming trees may replace the five exact managed Skill trees",
                    "SkillGuard, FlowGuard, and LogicGuard identities stay frozen and complete throughout receipt-producing validation",
                    "non-current active trees are opaque rollback material and current active trees receive semantic comparison",
                    "live and recent ownerless migration locks are never stolen",
                    "dead and stale legacy locks recover only with a durable receipt",
                    "aggregate-assurance fixtures cannot write shared global shell tools",
                    "late observation debt is drained and retrieval revalidated before restore",
                    "a current immutable full-regression owner receipt is reused; owner input or proof drift forces exactly one new execution",
                    "model-test obligations consume only declared logical validation owners; an unknown owner becomes explicit failed evidence rather than an exception",
                    "package import and direct-file execution resolve the same repository-owned alignment module",
                    "one canonicalization receipt proves every obsolete runtime input is gone before settlement",
                ),
                known_bad_cases=(
                    "prune_before_archive",
                    "early_restore",
                    "residual_architect",
                    "concurrent_drift",
                    "install_downgrade",
                    "anti_downgrade_check_id_monotonicity",
                    "incoming_authority_not_current",
                    "authority_validation_identity_drift",
                    "authority_validation_snapshot_missing",
                    "partial_tree_overlay",
                    "current_anti_downgrade_skipped",
                    "opaque_noncurrent_interpreted",
                    "active_tree_scan_failed",
                    "authority_install_receipt_replay_mismatch",
                    "authority_install_member_missing",
                    "live_migration_lock_stolen",
                    "recent_ownerless_lock_stolen",
                    "rollback_missing",
                    "pause_state_lost",
                    "recursive_assurance",
                    "fixture_global_shell_side_effect",
                    "post_assurance_data_skip",
                    "per_item_replay",
                    "read_only_prune_unhandled",
                    "stale_committed_failure",
                    "late_managed_debt_unchecked",
                    "long_path_invisible",
                    "post_commit_logical_debt_unchecked",
                    "postcommit_preassurance_restore",
                    "duplicate_current_full_regression",
                    "aggregate_script_import_ambiguous",
                    "performance_validation_resource_competition",
                    "scheduled_production_resource_competition",
                    "runtime_compatibility_residual",
                ),
                used_template_ids=("side_effect_at_most_once",),
                blindspots=("filesystem byte accounting remains migration-runner evidence",),
            ),
            confidence_goal="model_level",
        ),
        template_reuse_review=TemplateReuseReview(
            used_template_ids=("side_effect_at_most_once",),
            searched_layers=("public", "local"),
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=(
                "prune_before_archive",
                "early_restore",
                "residual_architect",
                "concurrent_source_drift",
                "skillguard_downgrade",
                "anti_downgrade_check_id_monotonicity",
                "incoming_authority_not_current",
                "authority_validation_identity_drift",
                "authority_validation_snapshot_missing",
                "partial_tree_overlay",
                "current_anti_downgrade_skipped",
                "opaque_noncurrent_interpreted",
                "active_tree_scan_failed",
                "authority_install_receipt_replay_mismatch",
                "authority_install_member_missing",
                "live_migration_lock_stolen",
                "recent_ownerless_lock_stolen",
                "missing_install_rollback",
                "pause_state_loss",
                "recursive_assurance",
                "fixture_isolation_breach",
                "post_assurance_data_skip",
                "per_item_lifecycle_replay",
                "verified_readonly_delete_unhandled",
                "stale_committed_failure",
                "late_managed_debt_unchecked",
                "long_path_invisible",
                "post_commit_logical_debt_unchecked",
                "postcommit_preassurance_restore",
                "duplicate_current_full_regression",
                "aggregate_script_import_ambiguous",
                "performance_validation_resource_competition",
                "scheduled_production_resource_competition",
            ),
            modeled_state=(
                "phase",
                "checkpoint",
                "runtime_canonicalized",
                "obsolete_runtime_residual_count",
                "canonicalization_receipt_count",
                "archive_ready",
                "architect_present",
                "automations_paused",
                "committed_version",
                "staged_manifests_match",
                "source_fingerprint_current",
                "authority_install_policy_id",
                "incoming_current_compiler_validated",
                "authority_validation_identity_stable",
                "authority_validation_snapshot_current",
                "active_managed_tree_class",
                "whole_tree_replacement_staged",
                "active_semantic_comparison_performed",
                "anti_downgrade_comparison_basis",
                "semantic_hard_authority_preserved",
                "current_to_current_anti_downgrade_passed",
                "authority_install_receipt_replay_current",
                "authority_install_member_count",
                "rollback_verified",
                "install_transaction_committed",
                "prior_automation_states",
                "restored_automation_states",
                "assurance_context",
                "assurance_depth",
                "fixture_gates_skipped",
                "fixture_shell_isolated",
                "post_assurance_data_current",
                "settlement_mode",
                "settlement_event_count",
                "settlement_replay_passes",
                "settlement_batch_count",
                "settlement_reused_count",
                "prune_verified_read_only_count",
                "prune_read_only_cleared_count",
                "prune_resumed_deleted_count",
                "prune_permission_blocker_count",
                "active_failure",
                "resolved_failure_count",
                "migration_lock_recovery_receipt_count",
                "migration_lock_recovery_reason",
                "live_migration_lock_stolen",
                "recent_ownerless_lock_stolen",
                "managed_surface_reintroduced_count",
                "managed_surface_residual_count",
                "reconciliation_receipt_count",
                "managed_long_path_count",
                "managed_enumerated_path_count",
                "post_commit_observation_debt_count",
                "logical_reconciliation_receipt_count",
                "aggregate_assurance_passed",
                "aggregate_assurance_current",
                "aggregate_assurance_receipt",
                "full_regression_execution_count",
                "full_regression_reuse_count",
                "full_regression_duplicate_current_execution_count",
                "full_regression_receipt_current",
                "aggregate_script_import_current",
                "performance_validation_lane_exclusive",
                "scheduled_production_validation_lane_exclusive",
            ),
            modeled_side_effects=(
                "cold_archive",
                "physical_prune",
                "architect_tombstone",
                "automation_restore",
                "managed_install",
                "install_rollback",
                "migration_lock_recovery",
                "aggregate_assurance_current",
            ),
            completion_evidence=(
                "validation_passed",
                "committed_version",
                "aggregate_assurance_current",
                "side_effects",
            ),
            known_bad_cases=(
                "prune_before_archive",
                "early_restore",
                "residual_architect",
                "concurrent_drift",
                "install_downgrade",
                "anti_downgrade_check_id_monotonicity",
                "incoming_authority_not_current",
                "authority_validation_identity_drift",
                "authority_validation_snapshot_missing",
                "partial_tree_overlay",
                "current_anti_downgrade_skipped",
                "opaque_noncurrent_interpreted",
                "active_tree_scan_failed",
                "authority_install_receipt_replay_mismatch",
                "authority_install_member_missing",
                "live_migration_lock_stolen",
                "recent_ownerless_lock_stolen",
                "rollback_missing",
                "pause_state_lost",
                "recursive_assurance",
                "fixture_global_shell_side_effect",
                "post_assurance_data_skip",
                "per_item_replay",
                "read_only_prune_unhandled",
                "stale_committed_failure",
                "late_managed_debt_unchecked",
                "long_path_invisible",
                "post_commit_logical_debt_unchecked",
                "postcommit_preassurance_restore",
                "duplicate_current_full_regression",
                "aggregate_script_import_ambiguous",
                "performance_validation_resource_competition",
                "scheduled_production_resource_competition",
                "runtime_compatibility_residual",
            ),
        ),
        known_bad_proofs=proofs,
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        scenario_matrix_config={"enabled": False},
    )


def automation_plan(
    workflow,
    *,
    proofs: tuple[KnownBadProof, ...] = (),
    initial_states: tuple[model.AutomationState, ...] | None = None,
    external_inputs: tuple[model.AutomationInput, ...] | None = None,
    max_sequence_length: int = 2,
    required_labels: tuple[str, ...] | None = None,
):
    known_bad_cases = (
        "shallow_automation_completion",
        "static_contract_only_completion",
        "wrong_target_obligation_set",
        "wrong_target_receipt",
        "missing_check_id",
        "duplicate_check_id",
        "run_id_mismatch",
        "receipt_hash_mismatch",
        "stale_depth_or_closure",
        "source_capability_closes_scheduled_production",
        "fixture_closes_scheduled_production",
        "scheduled_identity_missing_root_ref",
        "scheduled_identity_installation_stale",
        "runtime_projection_bytecode_mutated",
        "scheduled_supervision_live_reloaded_after_native",
        "scheduled_dynamic_evidence_not_projected",
        "scheduled_dynamic_evidence_not_isolated",
        "surface_label_selects_supervision_authority",
        "not_applicable_without_gate_proof",
        "branch_projection_requires_inapplicable_fields",
        "conditional_finalize_in_generic_depth_denominator",
        "depth_receipt_hash_mismatch",
        "close_reruns_target_checks",
        "native_update_prematurely_current",
        "authorization_overclaims_complete",
        "authorization_unpauses",
        "prepared_authorization_not_nonterminal",
        "update_terminal_receipt_wrong_owner",
        "update_terminal_receipt_depth_mismatch",
        "update_terminal_receipt_not_consumed",
        "legacy_update_close_bypass",
        "staging_state_mismatch",
        "staging_pause_bits_mismatch",
        "staging_hash_set_incomplete",
        "staging_not_bound_native",
        "staging_not_bound_authorization_receipt",
        "staging_unpauses_live",
        "finalize_without_staged_authorization",
        "finalization_reuses_authorization_run",
        "finalization_missing_composition",
        "finalization_skips_authorize_rerun",
        "finalization_not_enforced",
        "finalization_missing_check_id",
        "finalization_not_bound_native",
        "finalization_not_bound_staging",
        "finalization_close_reruns_target_checks",
        "finalization_unpauses_live",
        "live_restore_before_final_closure",
        "preclosure_update_restore",
        "restore_state_mismatch",
        "readback_state_mismatch",
        "readback_pause_bits_mismatch",
        "readback_hash_mismatch",
        "restore_failure_not_repaused",
        "readback_failure_not_repaused",
        "install_check_failure_not_repaused",
        "mark_current_before_restore",
        "mark_current_failure_not_repaused",
        "dream_active_lane_skipped",
        "phase_single_source_overclaims_full_semantics",
        "update_noop_authorization_only",
        "generic_fixture_targets_substitute_exact_obligations",
        "sleep_shared_lock_unheld",
        "sleep_fixture_masks_real_lifecycle_failure",
        "gated_noop_overclaims_obligations",
        *model.TARGET_SHALLOW_BROKEN_MODES.values(),
    )
    protected_error_classes = known_bad_cases
    modeled_state = (
        "target_skill_id",
        "receipt_skill_id",
        "obligation_ids",
        "required_obligation_ids",
        "contract_digest",
        "supervisor_contract_digest",
        "run_id",
        "expected_run_id",
        "receipt_hash",
        "expected_receipt_hash",
        "native_receipt_origin",
        "evidence_domain",
        "scheduler_or_trigger_id",
        "scheduled_execution_id",
        "installation_receipt_id",
        "installation_receipt_hash",
        "installation_receipt_root_ref",
        "installed_runtime_fingerprint",
        "installation_receipt_current",
        "runtime_projection_exact_inventory",
        "runtime_projection_bytecode_writes_suppressed",
        "scheduled_supervision_snapshot_frozen_before_native",
        "scheduled_supervision_snapshot_reused_after_native",
        "scheduled_supervision_live_reloaded_after_native",
        "scheduled_dynamic_evidence_projected_after_native",
        "scheduled_dynamic_evidence_whitelist_exact",
        "scheduled_inherited_dynamic_evidence_cleared",
        "supervision_target_root_class",
        "supervision_surface_label",
        "native_disposition_proofs_current",
        "maintenance_lane_active",
        "maintenance_lane_executed",
        "shared_maintenance_lock_required",
        "shared_maintenance_lock_acquired",
        "shared_maintenance_lock_released",
        "real_lifecycle_review_ok",
        "fixture_lifecycle_review_ok",
        "selected_obligation_ids",
        "evaluated_obligation_ids",
        "validated_obligation_ids",
        "semantic_validation_receipt_ids",
        "semantic_range_receipt_ids",
        "positive_fixture_target_ids",
        "shallow_fixture_target_ids",
        "gated_noop",
        "noop_applicable_obligation_ids",
        "noop_executed_obligation_ids",
        "noop_passed_obligation_ids",
        "noop_receipt_hash",
        "noop_consumed_receipt_hash",
        "noop_closure_profile",
        "expected_check_ids",
        "executed_check_ids",
        "depth_obligation_ids",
        "depth_status",
        "depth_current",
        "depth_receipt_id",
        "depth_receipt_hash",
        "target_check_execution_count",
        "closure_profile",
        "closure_current",
        "consumed_depth_receipt_id",
        "consumed_depth_receipt_hash",
        "close_target_check_execution_count",
        "target_native_terminal_receipt_owner",
        "target_native_terminal_receipt_id",
        "target_native_terminal_receipt_hash",
        "target_native_terminal_depth_receipt_id",
        "target_native_terminal_depth_receipt_hash",
        "consumed_target_native_terminal_receipt_id",
        "consumed_target_native_terminal_receipt_hash",
        "closure_completion_scope",
        "overall_complete",
        "enforced_closed",
        "closure_consumed_depth",
        "update_phase",
        "update_status",
        "authorization_run_id",
        "authorization_declared_check_receipt_id",
        "authorization_route_ids",
        "authorization_staged",
        "authorization_consumed_depth_receipt_id",
        "authorization_consumed_depth_receipt_hash",
        "authorization_reconciliation_target_check_execution_count",
        "authorization_consumed_native_terminal_receipt_id",
        "authorization_consumed_native_terminal_receipt_hash",
        "authorization_completion_scope",
        "authorization_overall_complete",
        "survivor_snapshot",
        "survivor_user_pause_bits",
        "current_survivor_states",
        "staged_target_states",
        "staged_user_pause_bits",
        "staged_automation_hashes",
        "staged_consumed_native_receipt_hash",
        "staged_consumed_authorization_receipt_id",
        "restoration_staged",
        "finalization_run_id",
        "finalization_depth_receipt_id",
        "finalization_depth_receipt_hash",
        "finalization_executed_check_ids",
        "finalization_route_ids",
        "finalization_target_check_execution_count",
        "finalization_close_target_check_execution_count",
        "finalization_native_terminal_receipt_owner",
        "finalization_native_terminal_receipt_id",
        "finalization_native_terminal_receipt_hash",
        "finalization_native_terminal_depth_receipt_id",
        "finalization_native_terminal_depth_receipt_hash",
        "finalization_consumed_native_terminal_receipt_id",
        "finalization_consumed_native_terminal_receipt_hash",
        "restored_survivor_states",
        "survivors_paused",
        "restored_after_closure",
        "live_restore_applied",
        "live_restore_readback_ok",
        "normal_install_check_ok",
        "marked_current_after_closure",
        "failure_repaused",
        "guarded_terminal",
    )
    side_effects = (
        "scheduled-supervision-start-snapshot",
        "native-receipt",
        "scheduled-dynamic-evidence-projection",
        "depth-receipt",
        "target-native-terminal-receipt",
        "closure-receipt",
        "authorization-declared-check-receipt",
        "stage-restoration-authorization",
        "finalization-depth-receipt",
        "finalization-target-native-terminal-receipt",
        "finalization-enforced-closure",
        "restore-survivors",
        "readback-survivors",
        "normal-install-check",
        "mark-current",
        "guarded-terminal",
    )
    completion_evidence = (
        "target-specific exact obligation set and count",
        "contract digest plus native run id and immutable receipt hash",
        "official six-field scheduled-production identity plus one verified installation/runtime/control snapshot frozen before native execution and reused after it",
        "one exact post-native dynamic-evidence projection into the frozen supervisor, with stale inherited values cleared and no undeclared environment key admitted",
        "exact supervision target-root authority derived from the managed root while the surface label remains display-only",
        "every route-selected manifest check id exactly once",
        "one unique target-native semantic receipt and bound contribution range per obligation",
        "target-owned positive and shallow fixtures for each retained target",
        "active Dream lane and Sleep shared-lock plus real lifecycle-review closure",
        "gated no-op evidence limited to declared gates while functional obligations execute",
        "update no-op exact receipt consumed by enforced closure",
        "current EXECUTION_DEPTH_PASS",
        "same-run prepared-update declared-check authorization consuming the exact depth id/hash and target-owned non-terminal receipt without rerunning target checks",
        "immutable staged restoration authorization for states, user pause bits, file hashes, and deferred install check",
        "a distinct composed enforced run whose stage_depth executes the exact checks once and whose close consumes the exact depth/terminal receipts with zero target-check executions",
        "post-closure exact live apply, readback, and normal install check",
        "guarded finalization",
    )
    default_required_labels = (
        "native_terminal_receipted",
        "partial_native_receipt",
        "execution_depth_passed",
        "execution_depth_blocked",
        "target_native_terminal_built",
        "enforced_closed",
        "enforced_closure_blocked",
        "authorization_declared_checks_staged",
        "restoration_authorization_staged",
        "finalization_execution_depth_staged",
        "finalization_native_terminal_built",
        "enforced_closure_closed_still_paused",
        "update_restore_readback_install_verified",
        "update_restore_failed_repaused",
        "update_marked_current",
        "update_mark_current_failed_repaused",
        "guarded_terminal_finalized",
        "guarded_finalization_blocked",
    )
    return FlowGuardCheckPlan(
        workflow=workflow,
        initial_states=(
            model.AUTOMATION_INITIAL_STATES
            if initial_states is None
            else initial_states
        ),
        external_inputs=(
            model.AUTOMATION_INPUTS
            if external_inputs is None
            else external_inputs
        ),
        invariants=model.AUTOMATION_INVARIANTS,
        max_sequence_length=max_sequence_length,
        terminal_predicate=model.automation_terminal,
        required_labels=(
            default_required_labels if required_labels is None else required_labels
        ),
        risk_profile=RiskProfile(
            modeled_boundary="one scheduled native automation run through SkillGuard closure and guarded finalization",
            risk_classes=("completion", "evidence", "staleness", "closure", "finalization"),
            risk_intent=RiskIntent(
                failure_modes=(
                    "a prompt, plan, regression, or partial native payload is reported as completed",
                    "a receipt for one retained Skill is accepted against another target or obligation set",
                    "a contract digest, run id, or immutable receipt hash is not bound end to end",
                    "one of the route-selected manifest checks is missing, duplicated, or not current",
                    "one source check mechanically marks every phase obligation selected, evaluated, and validated",
                    "generic obligation:one/two fixtures substitute for the exact five target-owned fixture targets",
                    "an active Dream lane is skipped or Sleep closes without its shared lock and real lifecycle review",
                    "a gated no-op passes unrelated functional obligations or update no-op stops at non-terminal declared-check authorization",
                    "source-only capability evidence or a fixture closes a scheduled-production run",
                    "scheduled production lacks one official identity field, uses the wrong portable receipt root, or cannot replay current installation",
                    "scheduled supervision reopens live SkillGuard currentness after native execution instead of retaining the start-frozen official authority",
                    "the start-frozen supervisor cannot see the current native receipt, inherits stale run evidence, or accepts an undeclared dynamic environment key",
                    "installed supervision imports runtime state or caches, omits the global-router sibling, accepts a runtime fingerprint mismatch, or makes correctness depend on a deep Windows run path",
                    "a display surface label selects source-vs-installed supervision instead of the exact managed target root",
                    "a target-owned positive or shallow fixture check is absent from the exact manifest or readiness inventory",
                    "close reruns target checks instead of consuming the exact same-run depth receipt id and hash",
                    "prepared-update authorization uses the wrong profile/disposition, or a no-op/finalization terminal closure omits the target-owned receipt",
                    "enforced closure does not consume the current execution-depth receipt",
                    "system update restores live automations before the second composed closure, or marks CURRENT before exact apply/readback/install-check",
                    "a system-update failure does not return all five retained automations to PAUSED and FAILED",
                ),
                protected_error_classes=protected_error_classes,
                protected_harms=(
                    "a background task appears green although its designed native work did not reach a terminal",
                ),
                must_model_state=modeled_state,
                must_model_side_effects=side_effects,
                completion_evidence=completion_evidence,
                adversarial_inputs=(
                    "wrong target or obligation set",
                    "missing or duplicate check id",
                    "mismatched run id or receipt hash",
                    "stale depth or closure",
                    "source-capability or fixture evidence domain",
                    "missing root ref or stale installation receipt",
                    "a post-native live SkillGuard reload or a missing start-frozen supervision snapshot",
                    "missing post-native receipt projection, stale inherited evidence, or an undeclared dynamic supervision key",
                    "runtime-state/cache pollution, missing router sibling, installed-runtime fingerprint drift, or deep path-dependent runtime projection",
                    "installed target under a scheduled display label, misleading installed-looking source label, or unknown target root",
                    "missing, duplicated, or misowned target fixture check binding",
                    "depth hash mismatch or close-time target-check execution",
                    "partial native receipt for each of five Skills",
                    "legacy one-closure bypass or pre-finalization live restore",
                    "staging, finalization composition, readback, install-check, or mark-current failure",
                    "active-lane skip, synthetic lifecycle masking, fabricated semantic ranges, generic fixture targets, or broad no-op pass",
                ),
                hard_invariants=(
                    "each retained Skill has its exact 8/9/9/10/10 obligation set",
                    "contract, run, receipt, check ids, depth, and closure remain one current chain",
                    "scheduled production carries all six official identity fields and replay-proven installation currentness frozen before native execution",
                    "the same official SkillGuard installation context, runtime projection, and target-control projection are reused after native execution; a newer live installation affects only a later run",
                    "post-native receipt evidence crosses into the frozen supervisor only through the exact declared dynamic key set; absent keys clear inherited values and unrelated environment state cannot become receipt authority",
                    "installed supervision uses short repository-local content-addressed control and behavior projections; behavior excludes runtime state/caches, includes the current global-router sibling, and exactly matches the verified installed runtime fingerprint",
                    "supervision authority is derived only from the exact source or exact active installed root; display labels never select execution and unknown or ambiguous roots block",
                    "each target-owned positive and shallow fixture check appears exactly once in the manifest and current readiness inventory",
                    "stage_depth executes target checks once; close reuses the exact same-run depth id/hash and executes zero target checks",
                    "prepared-update stages declared-check authorization without closure; legal no-ops plus composed finalization close enforced/terminal_completion",
                    "every phase obligation binds unique semantic evidence instead of one shared source-check result",
                    "all five targets keep target-owned positive/shallow fixtures and explicit lane, lock, lifecycle, and no-op semantics",
                    "system update orders scoped authorization, immutable staging while paused, a new composed enforced closure while paused, exact live apply/readback/install-check, CURRENT, then guarded terminal",
                    "every system-update failure returns all five retained automations to PAUSED and FAILED",
                ),
                known_bad_cases=known_bad_cases,
                used_template_ids=(),
                blindspots=("domain semantics remain owned by native receipt validators and capability regressions",),
            ),
            confidence_goal="model_level",
        ),
        template_reuse_review=TemplateReuseReview(
            used_template_ids=(),
            no_match_reason=(
                "No installed template binds five target-specific SkillGuard receipts "
                "to the system-update staged-authorization and post-closure restore transaction."
            ),
            searched_layers=("public", "local"),
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=protected_error_classes,
            modeled_state=modeled_state,
            modeled_side_effects=side_effects,
            completion_evidence=completion_evidence,
            known_bad_cases=known_bad_cases,
        ),
        known_bad_proofs=proofs,
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        scenario_matrix_config={"enabled": False},
    )


def _automation_known_bad_plan(case_id: str, workflow):
    """Use the smallest exact witness surface for each automation defect."""

    sleep = "kb-sleep-maintenance"
    inverse_shallow = {
        broken_mode: skill_id
        for skill_id, broken_mode in model.TARGET_SHALLOW_BROKEN_MODES.items()
    }
    semantic_native_skill = {
        "dream_active_lane_skipped": "kb-dream-pass",
        "phase_single_source_overclaims_full_semantics": "kb-sleep-maintenance",
        "update_noop_authorization_only": model.UPDATE_SKILL_ID,
        "generic_fixture_targets_substitute_exact_obligations": "kb-sleep-maintenance",
        "sleep_shared_lock_unheld": "kb-sleep-maintenance",
        "sleep_fixture_masks_real_lifecycle_failure": "kb-sleep-maintenance",
        "gated_noop_overclaims_obligations": "kb-organization-contribute",
        "source_capability_closes_scheduled_production": "kb-sleep-maintenance",
        "fixture_closes_scheduled_production": "kb-sleep-maintenance",
        "scheduled_identity_missing_root_ref": "kb-sleep-maintenance",
        "scheduled_identity_installation_stale": "kb-sleep-maintenance",
        "runtime_projection_bytecode_mutated": "kb-dream-pass",
        "scheduled_supervision_live_reloaded_after_native": "kb-dream-pass",
        "scheduled_dynamic_evidence_not_projected": "kb-dream-pass",
        "scheduled_dynamic_evidence_not_isolated": "kb-dream-pass",
        "surface_label_selects_supervision_authority": "kb-sleep-maintenance",
        "not_applicable_without_gate_proof": "kb-organization-contribute",
        "branch_projection_requires_inapplicable_fields": "kb-organization-maintenance",
    }
    if case_id in semantic_native_skill:
        skill_id = semantic_native_skill[case_id]
        return automation_plan(
            workflow,
            initial_states=(model.AutomationState(),),
            external_inputs=(model.automation_native_input(skill_id),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id in inverse_shallow:
        skill_id = inverse_shallow[case_id]
        return automation_plan(
            workflow,
            initial_states=(model.AutomationState(),),
            external_inputs=(
                model.automation_native_input(skill_id, partial=True),
                model.AutomationInput("depth_evaluate"),
            ),
            max_sequence_length=2,
            required_labels=(),
        )
    if case_id in {
        "shallow_automation_completion",
        "wrong_target_obligation_set",
        "wrong_target_receipt",
    }:
        native = model.automation_native_input(
            sleep, partial=case_id == "shallow_automation_completion"
        )
        return automation_plan(
            workflow,
            initial_states=(model.AutomationState(),),
            external_inputs=(native, model.AutomationInput("depth_evaluate")),
            max_sequence_length=2,
            required_labels=(),
        )
    if case_id in {
        "missing_check_id",
        "duplicate_check_id",
        "run_id_mismatch",
        "receipt_hash_mismatch",
        "stale_depth_or_closure",
        "depth_receipt_hash_mismatch",
    }:
        return automation_plan(
            workflow,
            initial_states=(model._native_state(sleep),),
            external_inputs=(model.AutomationInput("depth_evaluate"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "conditional_finalize_in_generic_depth_denominator":
        return automation_plan(
            workflow,
            initial_states=(model._native_state(model.UPDATE_SKILL_ID),),
            external_inputs=(model.AutomationInput("depth_evaluate"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "static_contract_only_completion":
        return automation_plan(
            workflow,
            initial_states=(model._native_state(sleep),),
            external_inputs=(model.AutomationInput("close"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "close_reruns_target_checks":
        return automation_plan(
            workflow,
            initial_states=(model._depth_state(sleep),),
            external_inputs=(model.AutomationInput("close"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "native_update_prematurely_current":
        return automation_plan(
            workflow,
            initial_states=(model.AutomationState(),),
            external_inputs=(model.automation_native_input(model.UPDATE_SKILL_ID),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id in {
        "authorization_overclaims_complete",
        "authorization_unpauses",
        "prepared_authorization_not_nonterminal",
        "update_terminal_receipt_not_consumed",
    }:
        return automation_plan(
            workflow,
            initial_states=(model._terminal_ready_update_state(),),
            external_inputs=(
                model.AutomationInput(
                    "reconcile_update_checks",
                    supervision_stage="declared_check_authorization",
                    authorization_route_ids=(model.UPDATE_AUTHORIZE_ROUTE_ID,),
                ),
            ),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id in {
        "update_terminal_receipt_wrong_owner",
        "update_terminal_receipt_depth_mismatch",
    }:
        return automation_plan(
            workflow,
            initial_states=(model._depth_state(model.UPDATE_SKILL_ID),),
            external_inputs=(model.AutomationInput("build_native_terminal"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "legacy_update_close_bypass":
        return automation_plan(
            workflow,
            initial_states=(model._depth_state(model.UPDATE_SKILL_ID),),
            external_inputs=(model.AutomationInput("close"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id in {
        "staging_state_mismatch",
        "staging_pause_bits_mismatch",
        "staging_hash_set_incomplete",
        "staging_not_bound_native",
        "staging_not_bound_authorization_receipt",
        "staging_unpauses_live",
    }:
        return automation_plan(
            workflow,
            initial_states=(model._authorized_update_state(),),
            external_inputs=(model.AutomationInput("stage_restoration"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "finalize_without_staged_authorization":
        return automation_plan(
            workflow,
            initial_states=(model._authorized_update_state(),),
            external_inputs=(model.AutomationInput("finalization_stage_depth"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id in {
        "finalization_reuses_authorization_run",
        "finalization_missing_composition",
        "finalization_skips_authorize_rerun",
        "finalization_missing_check_id",
    }:
        return automation_plan(
            workflow,
            initial_states=(model._staged_update_state(),),
            external_inputs=(
                model.AutomationInput(
                    "finalization_stage_depth",
                    finalization_route_ids=model.UPDATE_COMPOSED_ROUTE_IDS,
                ),
            ),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id in {
        "finalization_not_enforced",
        "finalization_not_bound_native",
        "finalization_not_bound_staging",
        "finalization_unpauses_live",
        "finalization_close_reruns_target_checks",
    }:
        return automation_plan(
            workflow,
            initial_states=(model._finalization_terminal_ready_state(),),
            external_inputs=(model.AutomationInput("finalization_close"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "live_restore_before_final_closure":
        return automation_plan(
            workflow,
            initial_states=(model._staged_update_state(),),
            external_inputs=(model.AutomationInput("restore"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "preclosure_update_restore":
        return automation_plan(
            workflow,
            initial_states=(model._native_state(model.UPDATE_SKILL_ID),),
            external_inputs=(model.AutomationInput("finalize"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id in {
        "restore_state_mismatch",
        "readback_state_mismatch",
        "readback_pause_bits_mismatch",
        "readback_hash_mismatch",
        "restore_failure_not_repaused",
        "readback_failure_not_repaused",
        "install_check_failure_not_repaused",
    }:
        event = model.AutomationInput("apply_restore")
        if case_id == "readback_failure_not_repaused":
            event = model.AutomationInput("apply_restore", readback_ok=False)
        elif case_id == "install_check_failure_not_repaused":
            event = model.AutomationInput(
                "apply_restore", normal_install_check_ok=False
            )
        return automation_plan(
            workflow,
            initial_states=(model._finalized_update_state(),),
            external_inputs=(event,),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "mark_current_before_restore":
        return automation_plan(
            workflow,
            initial_states=(model._finalized_update_state(),),
            external_inputs=(model.AutomationInput("mark_current"),),
            max_sequence_length=1,
            required_labels=(),
        )
    if case_id == "mark_current_failure_not_repaused":
        return automation_plan(
            workflow,
            initial_states=(model._restored_update_state(),),
            external_inputs=(model.AutomationInput("mark_current"),),
            max_sequence_length=1,
            required_labels=(),
        )
    raise KeyError(f"no automation known-bad witness for {case_id}")


def _proof(case_id: str, error_class: str, summary) -> KnownBadProof:
    sections = {section.name: section for section in summary.sections}
    caught = sections["model_check"].status == "failed"
    return KnownBadProof(
        case_id,
        protected_error_class=error_class,
        method="broken_workflow_variant",
        expected_failure="failed",
        observed_status="failed" if caught else "passed",
        observed_failure=(
            f"{case_id} violated a declared invariant"
            if caught
            else f"{case_id} unexpectedly passed"
        ),
        evidence_id=f"kb-convergence:{case_id}",
    )


def _section_statuses(summary) -> dict[str, str]:
    return {section.name: section.status for section in summary.sections}


def _scenario_reports() -> dict[str, object]:
    lifecycle = review_scenarios(
        (
            Scenario(
                "observation_failure_then_commit",
                "A failed Sleep pass leaves the observation actionable until commit.",
                model.LifecycleState(),
                (
                    model.LifecycleInput("admit", item_id="obs-scenario"),
                    model.LifecycleInput("sleep_fail", item_id="obs-scenario"),
                    model.LifecycleInput(
                        "sleep_commit",
                        item_id="obs-scenario",
                        disposition="candidate",
                    ),
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "observation_admitted",
                        "sleep_failed",
                        "sleep_committed",
                    )
                ),
            ),
            Scenario(
                "candidate_eligibility_and_terminal_exclusion",
                "Only an explicitly eligible candidate enters the index and rejection removes it.",
                model.LifecycleState(),
                (
                    model.LifecycleInput(
                        "candidate_transition",
                        item_id="card-scenario",
                        status="candidate",
                        retrieval_eligible=False,
                    ),
                    model.LifecycleInput(
                        "candidate_transition",
                        item_id="card-scenario",
                        status="candidate",
                        retrieval_eligible=True,
                    ),
                    model.LifecycleInput(
                        "candidate_transition",
                        item_id="card-scenario",
                        status="rejected",
                    ),
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "candidate_set_candidate",
                        "candidate_set_rejected",
                    )
                ),
            ),
            Scenario(
                "organization_candidate_boundary",
                "A read-only organization candidate is visible as untrusted input without entering the local active index.",
                model.LifecycleState(),
                (
                    model.LifecycleInput(
                        "candidate_observe",
                        item_id="org-candidate-scenario",
                        status="candidate",
                        retrieval_eligible=False,
                        source_boundary="organization-read-only",
                    ),
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "organization_candidate_visible_untrusted",
                    )
                ),
            ),
            Scenario(
                "dream_handoff_ack_and_no_delta",
                "A Dream result is acknowledged once and unchanged evidence closes without another write.",
                model.LifecycleState(),
                (
                    model.LifecycleInput("dream_complete", fingerprint="dream-scenario"),
                    model.LifecycleInput("commit_handoff_model", fingerprint="dream-scenario"),
                    model.LifecycleInput("ack_handoff", fingerprint="dream-scenario"),
                    model.LifecycleInput("dream_complete", fingerprint="dream-scenario"),
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "dream_handoff_emitted",
                        "handoff_model_committed",
                        "handoff_acknowledged",
                        "no_delta_closed",
                    )
                ),
            ),
        ),
        default_workflow=model.lifecycle_workflow(),
        default_invariants=model.LIFECYCLE_INVARIANTS,
    )
    migration = review_scenarios(
        (
            Scenario(
                "transactional_upgrade_and_exact_restore",
                "The full ordered migration commits before restoring exact survivor states.",
                model.MigrationState(),
                tuple(
                    model.MigrationInput(kind)
                    for kind in (
                        "begin",
                        "snapshot",
                        "classify",
                        "canonicalize_runtime",
                        "settle",
                        "archive",
                        "prune",
                        "rebuild",
                        "remove_architect",
                        "stage_install",
                        "activate_install",
                        "validate",
                        "commit",
                        "assurance_pass",
                        "restore",
                    )
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "migration_begun",
                        "cold_archive_committed",
                        "architect_removed",
                        "installation_staged",
                        "installation_committed",
                        "migration_validated",
                        "migration_committed",
                        "aggregate_assurance_current",
                        "survivors_restored",
                    )
                ),
            ),
            Scenario(
                "large_history_atomic_settlement",
                "Thousands of historical events settle through one atomic batch with two lifecycle replays.",
                next(
                    state
                    for state in model.MIGRATION_INITIAL_STATES
                    if state.phase == "canonicalize-runtime"
                ),
                (
                    model.MigrationInput(
                        "settle",
                        item_count=8000,
                        replay_passes=2,
                        batch_count=1,
                        reused_count=600,
                    ),
                ),
                ScenarioExpectation(
                    required_trace_labels=("debt_settlement_committed",)
                ),
            ),
            Scenario(
                "verified_read_only_prune",
                "A verified read-only managed file has only its read-only attribute cleared before deletion.",
                next(
                    state
                    for state in model.MIGRATION_INITIAL_STATES
                    if state.phase == "archive-cold-evidence"
                ),
                (
                    model.MigrationInput("prune", context="read-only-managed"),
                ),
                ScenarioExpectation(required_trace_labels=("derived_data_pruned",)),
            ),
            Scenario(
                "windows_extended_length_path_inventory",
                "A managed file beyond the legacy Win32 path limit remains visible to inventory.",
                model.MigrationState(),
                (model.MigrationInput("inventory_managed_path", context="windows-long"),),
                ScenarioExpectation(required_trace_labels=("managed_path_inventoried",)),
            ),
            Scenario(
                "partial_prune_accounting_resume",
                "A resumed prune carries prior deleted-file accounting into its final receipt state.",
                next(
                    state
                    for state in model.MIGRATION_INITIAL_STATES
                    if state.phase == "archive-cold-evidence"
                ),
                (model.MigrationInput("prune", context="partial-prune-resume"),),
                ScenarioExpectation(required_trace_labels=("derived_data_pruned",)),
            ),
            Scenario(
                "acl_denial_blocks_prune",
                "A real ACL denial remains a blocker instead of being treated as a read-only attribute.",
                next(
                    state
                    for state in model.MIGRATION_INITIAL_STATES
                    if state.phase == "archive-cold-evidence"
                ),
                (model.MigrationInput("prune", context="acl-denied"),),
                ScenarioExpectation(required_trace_labels=("prune_permission_blocked",)),
            ),
            Scenario(
                "interruption_resume",
                "An interrupted checkpoint remains paused and resumes from its durable phase.",
                model.MigrationState(),
                tuple(
                    model.MigrationInput(kind)
                    for kind in ("begin", "snapshot", "fail", "resume")
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "migration_paused_failed",
                        "migration_resumed",
                    )
                ),
            ),
            Scenario(
                "post_commit_managed_debt_reconciliation",
                "Managed physical debt reintroduced after commit reopens the gate and is closed by a receipt-backed pass.",
                next(
                    state
                    for state in model.MIGRATION_INITIAL_STATES
                    if state.phase == "committed"
                ),
                (
                    model.MigrationInput("reintroduce_managed_debt"),
                    model.MigrationInput("reconcile_managed_debt"),
                    model.MigrationInput("assurance_pass"),
                    model.MigrationInput("restore"),
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "managed_debt_reopened",
                        "managed_debt_reconciled",
                        "aggregate_assurance_current",
                        "survivors_restored",
                    )
                ),
            ),
            Scenario(
                "post_commit_observation_reconciliation",
                "An observation admitted by another AI during upgrade reopens the gate and receives a logical settlement receipt.",
                next(
                    state
                    for state in model.MIGRATION_INITIAL_STATES
                    if state.phase == "committed"
                ),
                (
                    model.MigrationInput("admit_post_commit_observation"),
                    model.MigrationInput("reconcile_logical_debt"),
                    model.MigrationInput("assurance_pass"),
                    model.MigrationInput("restore"),
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "post_commit_observation_reopened",
                        "logical_debt_reconciled",
                        "aggregate_assurance_current",
                        "survivors_restored",
                    )
                ),
            ),
            Scenario(
                "staged_install_rollback",
                "A staged installation can roll back while all automations remain paused.",
                next(
                    state
                    for state in model.MIGRATION_INITIAL_STATES
                    if state.phase == "rebuild-index"
                ),
                (
                    model.MigrationInput("stage_install"),
                    model.MigrationInput("rollback_install"),
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "installation_staged",
                        "installation_rolled_back",
                    )
                ),
            ),
            Scenario(
                "aggregate_assurance_child_isolation",
                "An aggregate assurance child exercises installer fixtures without re-entering the real migration.",
                model.MigrationState(),
                (
                    model.MigrationInput(
                        "assurance_invoke", context="aggregate-child"
                    ),
                    model.MigrationInput("begin"),
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "assurance_child_isolated",
                        "fixture_migration_blocked",
                    )
                ),
            ),
        ),
        default_workflow=model.migration_workflow(),
        default_invariants=model.MIGRATION_INVARIANTS,
    )
    target_bindings = _automation_target_bindings()
    automation_scenarios: list[Scenario] = []
    for skill_id in model.AUTOMATION_TARGET_OBLIGATIONS:
        native = model.automation_native_input(
            skill_id,
            contract_digest=str(target_bindings[skill_id]["contract_digest"]),
        )
        events: tuple[model.AutomationInput, ...] = (
            native,
            model.AutomationInput("depth_evaluate"),
        )
        labels = (
            "native_terminal_receipted",
            "execution_depth_passed",
        )
        if skill_id == model.UPDATE_SKILL_ID:
            events += (
                model.AutomationInput("build_native_terminal"),
                model.AutomationInput(
                    "reconcile_update_checks",
                    supervision_stage="declared_check_authorization",
                    authorization_route_ids=(model.UPDATE_AUTHORIZE_ROUTE_ID,),
                ),
                model.AutomationInput("stage_restoration"),
                model.AutomationInput(
                    "finalization_stage_depth",
                    finalization_route_ids=model.UPDATE_COMPOSED_ROUTE_IDS,
                ),
                model.AutomationInput("finalization_build_native_terminal"),
                model.AutomationInput(
                    "finalization_close",
                    finalization_route_ids=model.UPDATE_COMPOSED_ROUTE_IDS,
                ),
                model.AutomationInput("apply_restore"),
                model.AutomationInput("mark_current"),
            )
            labels += (
                "target_native_terminal_built",
                "authorization_declared_checks_staged",
                "restoration_authorization_staged",
                "finalization_execution_depth_staged",
                "finalization_native_terminal_built",
                "enforced_closure_closed_still_paused",
                "update_restore_readback_install_verified",
                "update_marked_current",
            )
        else:
            events += (model.AutomationInput("close"),)
            labels += ("enforced_closed",)
        events += (model.AutomationInput("finalize"),)
        labels += ("guarded_terminal_finalized",)
        automation_scenarios.append(
            Scenario(
                f"target_exact_depth_{skill_id}",
                f"{skill_id} binds its exact obligations, digest, run receipt, route-selected checks, current depth, and required SkillGuard closure path.",
                model.AutomationState(),
                events,
                ScenarioExpectation(required_trace_labels=labels),
            )
        )
    automation_scenarios.extend(
        (
            Scenario(
                "partial_native_is_blocked",
                "Intake or proposal-only native evidence cannot pass execution depth.",
                model.AutomationState(),
                (
                    model.automation_native_input(
                        "kb-sleep-maintenance", partial=True
                    ),
                    model.AutomationInput("depth_evaluate"),
                ),
                ScenarioExpectation(
                    required_trace_labels=(
                        "partial_native_receipt",
                        "execution_depth_blocked",
                    )
                ),
            ),
            Scenario(
                "system_update_restore_failure_repauses_all",
                "A failed post-closure exact-snapshot restore returns every retained automation to PAUSED and FAILED.",
                model._finalized_update_state(),
                (
                    model.AutomationInput(
                        "apply_restore",
                        operation_ok=False,
                    ),
                ),
                ScenarioExpectation(
                    required_trace_labels=("update_restore_failed_repaused",)
                ),
            ),
            Scenario(
                "system_update_readback_failure_repauses_all",
                "A failed live readback returns every retained automation to PAUSED and FAILED.",
                model._finalized_update_state(),
                (model.AutomationInput("apply_restore", readback_ok=False),),
                ScenarioExpectation(
                    required_trace_labels=("update_restore_failed_repaused",)
                ),
            ),
            Scenario(
                "system_update_mark_current_failure_repauses_all",
                "A failed mark-current step re-pauses all retained automations and records FAILED.",
                model._restored_update_state(),
                (model.AutomationInput("mark_current", operation_ok=False),),
                ScenarioExpectation(
                    required_trace_labels=("update_mark_current_failed_repaused",)
                ),
            ),
        )
    )
    automation = review_scenarios(
        tuple(automation_scenarios),
        default_workflow=model.automation_workflow(),
        default_invariants=model.AUTOMATION_INVARIANTS,
    )
    return {"lifecycle": lifecycle, "migration": migration, "automation": automation}


def _next_state(workflow, state, input_obj):
    run = workflow.execute(state, input_obj)
    if not run.completed_paths:
        return ()
    return tuple(
        GraphEdge(
            old_state=state,
            new_state=path.state,
            label=path.trace.steps[-1].label if path.trace.steps else input_obj.kind,
        )
        for path in run.completed_paths
    )


def _progress_reports() -> dict[str, object]:
    lifecycle_workflow = model.lifecycle_workflow()

    def lifecycle_transition(state):
        if not state.admitted:
            event = model.LifecycleInput("admit", item_id="obs-progress")
        elif state.actionable_backlog:
            event = model.LifecycleInput(
                "sleep_commit", item_id="obs-progress", disposition="history_only"
            )
        else:
            return ()
        return _next_state(lifecycle_workflow, state, event)

    lifecycle = check_progress(
        ProgressCheckConfig(
            initial_states=(model.LifecycleState(),),
            transition_fn=lifecycle_transition,
            is_terminal=lambda state: bool(state.admitted) and state.actionable_backlog == 0,
            is_success=lambda state: bool(state.dispositions),
            bounded_eventually=(
                BoundedEventuallyProperty(
                    "observation_disposed_within_two_transitions",
                    trigger=lambda state: not state.admitted,
                    target=lambda state: bool(state.dispositions),
                    max_steps=2,
                ),
            ),
        )
    )

    migration_workflow = model.migration_workflow()

    def migration_transition(state):
        event_by_phase = {
            "idle": "begin",
            "preflight": "snapshot",
            "snapshot": "classify",
            "classify": "canonicalize_runtime",
            "canonicalize-runtime": "settle",
            "settle-logical-debt": "archive",
            "archive-cold-evidence": "prune",
            "prune-derived-data": "rebuild",
            "stage-install": "activate_install",
            "activate-install": "validate",
            "validate": "commit",
        }
        if state.phase == "rebuild-index":
            event = "remove_architect" if state.architect_present else "stage_install"
        elif state.phase == "committed":
            if not state.aggregate_assurance_current:
                event = "assurance_pass"
            elif state.automations_paused:
                event = "restore"
            else:
                return ()
        else:
            event = event_by_phase.get(state.phase)
        if not event:
            return ()
        return _next_state(migration_workflow, state, model.MigrationInput(event))

    migration = check_progress(
        ProgressCheckConfig(
            initial_states=(model.MigrationState(),),
            transition_fn=migration_transition,
            is_terminal=lambda state: (
                state.phase == "committed" and not state.automations_paused
            ),
            is_success=lambda state: (
                state.committed_version == 1
                and state.aggregate_assurance_current
                and state.restored_automation_states == state.prior_automation_states
            ),
            bounded_eventually=(
                BoundedEventuallyProperty(
                    "upgrade_assures_and_restores_within_fifteen_transitions",
                    trigger=lambda state: state.phase == "idle",
                    target=lambda state: (
                        state.committed_version == 1
                        and state.aggregate_assurance_current
                        and not state.automations_paused
                    ),
                    max_steps=15,
                ),
            ),
        )
    )
    automation_workflow = model.automation_workflow()
    target_bindings = _automation_target_bindings()

    def automation_transition(state):
        if not state.native_terminal:
            skill_id = state.target_skill_id or "kb-sleep-maintenance"
            event = model.automation_native_input(
                skill_id,
                contract_digest=str(target_bindings[skill_id]["contract_digest"]),
            )
        elif state.depth_status != "EXECUTION_DEPTH_PASS":
            event = model.AutomationInput("depth_evaluate")
        elif (
            state.update_requires_restore
            and not state.target_native_terminal_receipt_id
        ):
            event = model.AutomationInput("build_native_terminal")
        elif state.update_requires_restore and not state.authorization_staged:
            event = model.AutomationInput(
                "reconcile_update_checks",
                supervision_stage="declared_check_authorization",
                authorization_route_ids=(model.UPDATE_AUTHORIZE_ROUTE_ID,),
            )
        elif state.update_requires_restore and not state.restoration_staged:
            event = model.AutomationInput("stage_restoration")
        elif (
            state.update_requires_restore
            and state.finalization_depth_status != "EXECUTION_DEPTH_PASS"
        ):
            event = model.AutomationInput(
                "finalization_stage_depth",
                finalization_route_ids=model.UPDATE_COMPOSED_ROUTE_IDS,
            )
        elif (
            state.update_requires_restore
            and not state.finalization_native_terminal_receipt_id
        ):
            event = model.AutomationInput("finalization_build_native_terminal")
        elif state.update_requires_restore and not state.enforced_closed:
            event = model.AutomationInput(
                "finalization_close",
                finalization_route_ids=model.UPDATE_COMPOSED_ROUTE_IDS,
            )
        elif not state.update_requires_restore and not state.enforced_closed:
            event = model.AutomationInput("close")
        elif state.update_requires_restore and not state.restored_after_closure:
            event = model.AutomationInput("apply_restore")
        elif state.update_requires_restore and not state.marked_current_after_closure:
            event = model.AutomationInput("mark_current")
        elif not state.guarded_terminal:
            event = model.AutomationInput("finalize")
        else:
            return ()
        return _next_state(automation_workflow, state, event)

    automation = check_progress(
        ProgressCheckConfig(
            initial_states=tuple(
                model.AutomationState(target_skill_id=skill_id)
                for skill_id in model.AUTOMATION_TARGET_OBLIGATIONS
            ),
            transition_fn=automation_transition,
            is_terminal=lambda state: state.guarded_terminal,
            is_success=lambda state: (
                state.guarded_terminal
                and state.enforced_closed
                and state.closure_consumed_depth
                and (
                    not state.update_requires_restore
                    or (
                        state.restored_after_closure
                        and state.live_restore_applied
                        and state.live_restore_readback_ok
                        and state.normal_install_check_ok
                        and state.marked_current_after_closure
                    )
                )
            ),
            bounded_eventually=(
                BoundedEventuallyProperty(
                    "scheduled_run_finalizes_with_depth_within_twelve_transitions",
                    trigger=lambda state: not state.native_terminal,
                    target=lambda state: state.guarded_terminal,
                    max_steps=12,
                ),
            ),
        )
    )
    return {"lifecycle": lifecycle, "migration": migration, "automation": automation}


def main() -> int:
    lifecycle_bad = (
        _proof(
            "premature_watermark",
            "premature_watermark",
            run_model_first_checks(
                lifecycle_plan(model.lifecycle_workflow(broken_mode="premature_watermark"))
            ),
        ),
        _proof(
            "repeat_dream_write",
            "duplicate_dream_effect",
            run_model_first_checks(
                lifecycle_plan(model.lifecycle_workflow(broken_mode="repeat_dream_write"))
            ),
        ),
        _proof(
            "candidate_leak",
            "candidate_eligibility_leak",
            run_model_first_checks(
                lifecycle_plan(model.lifecycle_workflow(broken_mode="candidate_leak"))
            ),
        ),
        _proof(
            "candidate_source_collapse",
            "candidate_source_boundary_collapse",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(broken_mode="candidate_source_collapse")
                )
            ),
        ),
        _proof(
            "missing_ack",
            "missing_handoff_ack",
            run_model_first_checks(
                lifecycle_plan(model.lifecycle_workflow(broken_mode="missing_ack"))
            ),
        ),
        _proof(
            "foreground_full_replay",
            "foreground_full_authority_replay",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(broken_mode="foreground_full_replay")
                )
            ),
        ),
        _proof(
            "sleep_per_item_replay",
            "sleep_per_item_lifecycle_replay",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(broken_mode="sleep_per_item_replay")
                )
            ),
        ),
        _proof(
            "dream_handoff_per_item_replay",
            "dream_handoff_per_item_lifecycle_replay",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="dream_handoff_per_item_replay"
                    )
                )
            ),
        ),
        _proof(
            "quadratic_lifecycle_idempotency_lookup",
            "lifecycle_replay_quadratic_lookup",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="quadratic_lifecycle_idempotency_lookup"
                    )
                )
            ),
        ),
        _proof(
            "dead_lane_lock_retained",
            "dead_lane_lock_retained",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(broken_mode="dead_lane_lock_retained")
                )
            ),
        ),
        _proof(
            "lifecycle_writer_orphan_retained",
            "lifecycle_writer_orphan_retained",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="lifecycle_writer_orphan_retained"
                    )
                )
            ),
        ),
        _proof(
            "lifecycle_writer_self_deadlock",
            "lifecycle_writer_self_deadlock",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="lifecycle_writer_self_deadlock"
                    )
                )
            ),
        ),
        _proof(
            "lifecycle_writer_release_failure_hidden",
            "lifecycle_writer_release_failure_hidden",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="lifecycle_writer_release_failure_hidden"
                    )
                )
            ),
        ),
        _proof(
            "orphan_process_tree",
            "orphan_process_tree",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(broken_mode="orphan_process_tree")
                )
            ),
        ),
        _proof(
            "timeout_hierarchy_collapse",
            "timeout_hierarchy_collapse",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(broken_mode="timeout_hierarchy_collapse")
                )
            ),
        ),
        _proof(
            "candidate_per_item_calibration_reload",
            "candidate_per_item_calibration_reload",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="candidate_per_item_calibration_reload"
                    )
                )
            ),
        ),
        _proof(
            "parked_recalibrated_without_evidence_delta",
            "parked_recalibrated_without_evidence_delta",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="parked_recalibrated_without_evidence_delta"
                    )
                )
            ),
        ),
        _proof(
            "parked_delta_not_checkpointed",
            "parked_delta_not_checkpointed",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="parked_delta_not_checkpointed"
                    )
                )
            ),
        ),
        _proof(
            "handoff_ack_before_model_publication",
            "handoff_ack_before_model_publication",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="handoff_ack_before_model_publication"
                    )
                )
            ),
        ),
        _proof(
            "duplicate_sleep_model_publication",
            "duplicate_sleep_model_publication",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="duplicate_sleep_model_publication"
                    )
                )
            ),
        ),
        _proof(
            "duplicate_sleep_index_validation",
            "duplicate_sleep_index_validation",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="duplicate_sleep_index_validation"
                    )
                )
            ),
        ),
        _proof(
            "date_serialization_failure",
            "date_serialization_failure",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(
                        broken_mode="date_serialization_failure"
                    )
                )
            ),
        ),
        _proof(
            "scanner_self_match",
            "scanner_self_match",
            run_model_first_checks(
                lifecycle_plan(
                    model.lifecycle_workflow(broken_mode="scanner_self_match")
                )
            ),
        ),
    )
    migration_bad = tuple(
        _proof(
            case_id,
            error_class,
            run_model_first_checks(
                migration_plan(model.migration_workflow(broken_mode=case_id))
            ),
        )
        for case_id, error_class in (
            ("prune_before_archive", "prune_before_archive"),
            ("early_restore", "early_restore"),
            ("residual_architect", "residual_architect"),
            ("concurrent_drift", "concurrent_source_drift"),
            ("install_downgrade", "skillguard_downgrade"),
            (
                "anti_downgrade_check_id_monotonicity",
                "anti_downgrade_check_id_monotonicity",
            ),
            (
                "incoming_authority_not_current",
                "incoming_authority_not_current",
            ),
            (
                "authority_validation_identity_drift",
                "authority_validation_identity_drift",
            ),
            (
                "authority_validation_snapshot_missing",
                "authority_validation_snapshot_missing",
            ),
            (
                "duplicate_current_full_regression",
                "duplicate_current_full_regression",
            ),
            (
                "aggregate_script_import_ambiguous",
                "aggregate_script_import_ambiguous",
            ),
            (
                "scheduled_production_resource_competition",
                "scheduled_production_resource_competition",
            ),
            (
                "performance_validation_resource_competition",
                "performance_validation_resource_competition",
            ),
            (
                "runtime_compatibility_residual",
                "runtime_compatibility_residual",
            ),
            (
                "partial_tree_overlay",
                "partial_tree_overlay",
            ),
            (
                "current_anti_downgrade_skipped",
                "current_anti_downgrade_skipped",
            ),
            (
                "opaque_noncurrent_interpreted",
                "opaque_noncurrent_interpreted",
            ),
            (
                "active_tree_scan_failed",
                "active_tree_scan_failed",
            ),
            (
                "authority_install_receipt_replay_mismatch",
                "authority_install_receipt_replay_mismatch",
            ),
            (
                "authority_install_member_missing",
                "authority_install_member_missing",
            ),
            ("live_migration_lock_stolen", "live_migration_lock_stolen"),
            (
                "recent_ownerless_lock_stolen",
                "recent_ownerless_lock_stolen",
            ),
            ("rollback_missing", "missing_install_rollback"),
            ("pause_state_lost", "pause_state_loss"),
            ("recursive_assurance", "recursive_assurance"),
            (
                "fixture_global_shell_side_effect",
                "fixture_isolation_breach",
            ),
            ("post_assurance_data_skip", "post_assurance_data_skip"),
            ("per_item_replay", "per_item_lifecycle_replay"),
            ("read_only_prune_unhandled", "verified_readonly_delete_unhandled"),
            ("stale_committed_failure", "stale_committed_failure"),
            ("late_managed_debt_unchecked", "late_managed_debt_unchecked"),
            ("long_path_invisible", "long_path_invisible"),
            (
                "post_commit_logical_debt_unchecked",
                "post_commit_logical_debt_unchecked",
            ),
            (
                "postcommit_preassurance_restore",
                "postcommit_preassurance_restore",
            ),
        )
    )
    automation_known_bad_cases = (
        "shallow_automation_completion",
        "static_contract_only_completion",
        "wrong_target_obligation_set",
        "wrong_target_receipt",
        "missing_check_id",
        "duplicate_check_id",
        "run_id_mismatch",
        "receipt_hash_mismatch",
        "stale_depth_or_closure",
        "source_capability_closes_scheduled_production",
        "fixture_closes_scheduled_production",
        "scheduled_identity_missing_root_ref",
        "scheduled_identity_installation_stale",
        "runtime_projection_bytecode_mutated",
        "scheduled_supervision_live_reloaded_after_native",
        "scheduled_dynamic_evidence_not_projected",
        "scheduled_dynamic_evidence_not_isolated",
        "surface_label_selects_supervision_authority",
        "not_applicable_without_gate_proof",
        "branch_projection_requires_inapplicable_fields",
        "conditional_finalize_in_generic_depth_denominator",
        "depth_receipt_hash_mismatch",
        "close_reruns_target_checks",
        "native_update_prematurely_current",
        "authorization_overclaims_complete",
        "authorization_unpauses",
        "prepared_authorization_not_nonterminal",
        "update_terminal_receipt_wrong_owner",
        "update_terminal_receipt_depth_mismatch",
        "update_terminal_receipt_not_consumed",
        "legacy_update_close_bypass",
        "staging_state_mismatch",
        "staging_pause_bits_mismatch",
        "staging_hash_set_incomplete",
        "staging_not_bound_native",
        "staging_not_bound_authorization_receipt",
        "staging_unpauses_live",
        "finalize_without_staged_authorization",
        "finalization_reuses_authorization_run",
        "finalization_missing_composition",
        "finalization_skips_authorize_rerun",
        "finalization_not_enforced",
        "finalization_missing_check_id",
        "finalization_not_bound_native",
        "finalization_not_bound_staging",
        "finalization_close_reruns_target_checks",
        "finalization_unpauses_live",
        "live_restore_before_final_closure",
        "preclosure_update_restore",
        "restore_state_mismatch",
        "readback_state_mismatch",
        "readback_pause_bits_mismatch",
        "readback_hash_mismatch",
        "restore_failure_not_repaused",
        "readback_failure_not_repaused",
        "install_check_failure_not_repaused",
        "mark_current_before_restore",
        "mark_current_failure_not_repaused",
        "dream_active_lane_skipped",
        "phase_single_source_overclaims_full_semantics",
        "update_noop_authorization_only",
        "generic_fixture_targets_substitute_exact_obligations",
        "sleep_shared_lock_unheld",
        "sleep_fixture_masks_real_lifecycle_failure",
        "gated_noop_overclaims_obligations",
        *model.TARGET_SHALLOW_BROKEN_MODES.values(),
    )
    automation_bad = tuple(
        _proof(
            case_id,
            case_id,
            run_model_first_checks(
                _automation_known_bad_plan(
                    case_id, model.automation_workflow(broken_mode=case_id)
                )
            ),
        )
        for case_id in automation_known_bad_cases
    )
    lifecycle = run_model_first_checks(
        lifecycle_plan(model.lifecycle_workflow(), proofs=lifecycle_bad)
    )
    migration = run_model_first_checks(
        migration_plan(model.migration_workflow(), proofs=migration_bad)
    )
    automation = run_model_first_checks(
        automation_plan(model.automation_workflow(), proofs=automation_bad)
    )
    lifecycle_sections = _section_statuses(lifecycle)
    migration_sections = _section_statuses(migration)
    automation_sections = _section_statuses(automation)
    scenario_reports = _scenario_reports()
    progress_reports = _progress_reports()
    target_bindings = _automation_target_bindings()
    lifecycle_sections["scenario_review"] = (
        "pass" if scenario_reports["lifecycle"].ok else "failed"
    )
    migration_sections["scenario_review"] = (
        "pass" if scenario_reports["migration"].ok else "failed"
    )
    lifecycle_sections["progress_check"] = (
        "pass" if progress_reports["lifecycle"].ok else "failed"
    )
    migration_sections["progress_check"] = (
        "pass" if progress_reports["migration"].ok else "failed"
    )
    automation_sections["scenario_review"] = (
        "pass" if scenario_reports["automation"].ok else "failed"
    )
    automation_sections["progress_check"] = (
        "pass" if progress_reports["automation"].ok else "failed"
    )
    proofs = lifecycle_bad + migration_bad + automation_bad
    ok = (
        lifecycle_sections.get("model_check") == "pass"
        and lifecycle_sections.get("known_bad_proof") == "pass"
        and migration_sections.get("model_check") == "pass"
        and migration_sections.get("known_bad_proof") == "pass"
        and automation_sections.get("model_check") == "pass"
        and automation_sections.get("known_bad_proof") == "pass"
        and all(report.ok for report in scenario_reports.values())
        and all(report.ok for report in progress_reports.values())
        and all(bool(binding["ok"]) for binding in target_bindings.values())
        and all(proof.observed_status == "failed" for proof in proofs)
    )
    report = {
        "ok": ok,
        "model": "kb-convergence-upgrade",
        "model_digest": _digest(MODEL_PATH),
        "projection_digest": f"production-source:{_projection_digest()}",
        "flowguard_schema_version": __import__("flowguard").SCHEMA_VERSION,
        "children": {
            "lifecycle": lifecycle_sections,
            "migration": migration_sections,
            "automation": automation_sections,
        },
        "known_bad_proofs": {
            proof.case_id: proof.observed_status for proof in proofs
        },
        "automation_target_bindings": target_bindings,
        "scenario_reviews": {
            name: report.to_dict() for name, report in scenario_reports.items()
        },
        "progress_checks": {
            name: report.to_dict() for name, report in progress_reports.items()
        },
        "skipped_checks": [
            "production conformance replay is owned by check_kb_model_test_alignment.py",
            "field lifecycle and finite contract exhaustion are owned by run_flowguard_suite.py",
        ],
        "blockers": [] if ok else ["one or more model or known-bad checks failed"],
        "claim_boundary": (
            "Current executable model-level evidence. Production conformance, field, "
            "contract-exhaustion, model-test, SkillGuard, migration, and full-regression "
            "receipts remain separate required gates."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
