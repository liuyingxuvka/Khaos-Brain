"""Bind every Chaos Brain upgrade obligation to one code owner and current tests."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import flowguard  # noqa: E402


RECEIPT_PATH = REPO_ROOT / ".flowguard" / "evidence" / "kb_model_test_alignment.json"
DEFAULT_EVIDENCE_MANIFEST = (
    REPO_ROOT / ".local" / "assurance" / "validation-evidence" / "current.json"
)


OBLIGATIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "req.lifecycle.timely-disposition",
        "path": "local_kb/lifecycle.py",
        "symbol": "run_incremental_sleep",
        "test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_observation_is_admitted_and_disposed_by_next_sleep",
    },
    {
        "id": "req.lifecycle.evidence-provenance",
        "path": "local_kb/lifecycle.py",
        "symbol": "replay_lifecycle",
        "test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_candidate_terminal_transition_is_replayable",
    },
    {
        "id": "req.lifecycle.bounded-outcomes",
        "path": "local_kb/candidate_lifecycle.py",
        "symbol": "review_entry_lifecycles",
        "test": "tests/test_kb_sleep_convergence.py::KbSleepConvergenceTests::test_candidate_promotes_only_with_independent_support_and_validation",
    },
    {
        "id": "req.lifecycle.writer-lock-owner",
        "path": "local_kb/lifecycle.py",
        "symbol": "_lifecycle_lock",
        "test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_lifecycle_writer_lock_recovers_dead_owner",
        "same_class_test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_lifecycle_writer_lock_release_failure_is_visible",
        "model_miss": True,
    },
    {
        "id": "req.retrieval.active-only",
        "path": "local_kb/active_index.py",
        "symbol": "load_active_entries",
        "test": "tests/test_kb_retrieval_calibration.py::KbRetrievalCalibrationTests::test_active_index_excludes_terminal_states_and_serializes_dates",
    },
    {
        "id": "req.retrieval.index-outcomes",
        "path": "local_kb/calibration.py",
        "symbol": "calibrate_entry",
        "test": "tests/test_kb_retrieval_calibration.py::KbRetrievalCalibrationTests::test_outcome_receipt_rejects_unreturned_card_and_requires_evidence",
    },
    {
        "id": "req.retrieval.fast-authority",
        "path": "local_kb/active_index.py",
        "symbol": "validate_active_index_fast",
        "test": "tests/test_kb_retrieval_calibration.py::KbRetrievalCalibrationTests::test_fast_authority_avoids_full_replay_and_observation_only_events_do_not_stale_it",
        "same_class_test": "tests/test_kb_retrieval_calibration.py::KbRetrievalCalibrationTests::test_stale_index_is_a_visible_failure_without_scan_alternative",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.current-only-runtime",
        "path": "scripts/check_current_runtime_only.py",
        "symbol": "check_current_runtime_only",
        "test": "tests/test_current_runtime_only.py::test_repository_has_only_current_runtime_authority",
        "same_class_test": "tests/test_current_runtime_only.py::test_retired_runtime_authority_is_a_hard_failure",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.desktop-launcher-current-runtime",
        "path": "scripts/open_khaos_brain_ui.py",
        "symbol": "_launch_command",
        "test": "tests/test_desktop_launcher_current_runtime.py::DesktopLauncherCurrentRuntimeTests::test_source_runtime_is_explicit_and_never_probes_release_paths",
        "same_class_test": "tests/test_desktop_launcher_current_runtime.py::DesktopLauncherCurrentRuntimeTests::test_release_runtime_requires_the_one_current_executable",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.desktop-settings-current-runtime",
        "path": "local_kb/settings_migration.py",
        "symbol": "migrate_desktop_settings_to_current",
        "test": "tests/test_desktop_settings.py::DesktopSettingsTests::test_upgrade_ai_resolution_selects_one_exact_value_and_records_receipt",
        "same_class_test": "tests/test_desktop_settings.py::DesktopSettingsTests::test_upgrade_blocks_conflicting_old_and_current_settings_without_mutation",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.card-skill-guidance-current-runtime",
        "path": "local_kb/card_schema_migration.py",
        "symbol": "migrate_skill_guidance_fields_to_current",
        "test": "tests/test_card_schema_migration.py::CardSchemaMigrationTests::test_upgrade_rewrites_old_skill_guidance_field_and_repeat_is_no_delta",
        "same_class_test": "tests/test_card_schema_migration.py::CardSchemaMigrationTests::test_upgrade_blocks_conflicting_old_and_current_skill_guidance",
        "model_miss": True,
    },
    {
        "id": "req.sleep.incremental",
        "path": "local_kb/lifecycle.py",
        "symbol": "run_incremental_sleep",
        "test": "tests/test_kb_sleep_convergence.py::KbSleepConvergenceTests::test_second_sleep_is_bounded_noop_without_duplicate_events",
    },
    {
        "id": "req.sleep.interrupted-watermark-scale-recovery",
        "path": "local_kb/lifecycle.py",
        "symbol": "_run_incremental_sleep_locked",
        "test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_sleep_recovers_zero_watermark_by_skipping_terminal_history",
        "same_class_test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_sleep_batches_new_history_admission_and_disposition",
        "model_miss": True,
    },
    {
        "id": "req.runtime.dead-lane-owner-recovery",
        "path": "local_kb/maintenance_lanes.py",
        "symbol": "acquire_lane_lock",
        "test": "tests/test_maintenance_lanes.py::MaintenanceLaneLockTests::test_fresh_lane_lock_with_dead_owner_is_recovered_immediately",
        "same_class_test": "tests/test_maintenance_lanes.py::MaintenanceLaneLockTests::test_stale_lane_lock_is_recovered",
        "model_miss": True,
    },
    {
        "id": "req.sleep.shared-calibration-evidence-index",
        "path": "local_kb/calibration.py",
        "symbol": "build_calibration_evidence_index",
        "test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_candidate_review_reuses_one_calibration_evidence_index",
        "same_class_test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_calibration_consumes_a_supplied_evidence_index_without_reloading",
        "model_miss": True,
    },
    {
        "id": "req.sleep.parked-calibration-watermark",
        "path": "local_kb/candidate_lifecycle.py",
        "symbol": "review_entry_lifecycles",
        "test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_parked_calibration_snapshot_persists_the_delta_watermark_once",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "parked_delta_not_checkpointed",
        "model_miss": True,
    },
    {
        "id": "req.sleep.no-delta-single-publication-owner",
        "path": "local_kb/lifecycle.py",
        "symbol": "_run_incremental_sleep_locked",
        "test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_no_delta_sleep_reuses_one_model_publication_and_one_final_index_validation_owner",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "duplicate_sleep_model_publication",
        "model_miss": True,
    },
    {
        "id": "req.sleep.handoff-ack-after-model-publication",
        "path": "local_kb/lifecycle.py",
        "symbol": "_run_incremental_sleep_locked",
        "test": "tests/test_kb_sleep_convergence.py::KbSleepConvergenceTests::test_dream_handoff_is_not_acknowledged_when_model_publication_fails",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "handoff_ack_before_model_publication",
        "model_miss": True,
    },
    {
        "id": "req.sleep.handoff-lifecycle-atomic-batch",
        "path": "local_kb/lifecycle.py",
        "symbol": "_run_incremental_sleep_locked",
        "test": "tests/test_kb_sleep_convergence.py::KbSleepConvergenceTests::test_pending_dream_handoffs_share_one_atomic_lifecycle_batch",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "dream_handoff_per_item_replay",
        "model_miss": True,
    },
    {
        "id": "req.lifecycle.linear-idempotency-replay",
        "path": "local_kb/lifecycle.py",
        "symbol": "replay_lifecycle",
        "test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_replay_lifecycle_uses_a_linear_idempotency_index",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "quadratic_lifecycle_idempotency_lookup",
        "model_miss": True,
    },
    {
        "id": "req.validation.timeout-tree-cleanup",
        "path": "local_kb/process_control.py",
        "symbol": "run_with_timeout_cleanup",
        "test": "tests/test_process_control.py::test_timeout_terminates_the_complete_descendant_tree",
        "same_class_test": "tests/test_process_control.py::test_timeout_hierarchy_preserves_cleanup_margin",
        "model_miss": True,
    },
    {
        "id": "req.dream.no-delta",
        "path": "local_kb/dream.py",
        "symbol": "run_dream_maintenance",
        "test": "tests/test_kb_dream.py::DreamMaintenanceTests::test_dream_run_noops_when_no_opportunity_clears_value_gate",
    },
    {
        "id": "req.history.versioned-migration",
        "path": "local_kb/maintenance_migration.py",
        "symbol": "run_maintenance_migration",
        "test": "tests/test_kb_history_migration.py::KbHistoryMigrationTests::test_migration_resumes_cold_archives_prunes_and_is_idempotent",
        "same_class_test": "tests/test_kb_history_migration.py::KbHistoryMigrationTests::test_batch_settlement_resumes_partial_per_item_attempt_without_duplicates",
        "model_miss": True,
    },
    {
        "id": "req.history.logical-settlement",
        "path": "local_kb/maintenance_migration.py",
        "symbol": "settle_knowledge_debt",
        "test": "tests/test_kb_history_migration.py::KbHistoryMigrationTests::test_post_commit_observation_debt_is_settled_with_its_own_receipt",
        "same_class_test": "tests/test_kb_history_migration.py::KbHistoryMigrationTests::test_large_settlement_batches_replay_and_closes_every_observation",
        "model_miss": True,
    },
    {
        "id": "req.history.scale-bounded-settlement",
        "path": "local_kb/maintenance_migration.py",
        "symbol": "settle_knowledge_debt",
        "test": "tests/test_kb_history_migration.py::KbHistoryMigrationTests::test_large_settlement_batches_replay_and_closes_every_observation",
        "same_class_test": "tests/test_kb_lifecycle.py::KbLifecycleTests::test_large_lifecycle_batch_uses_two_replays_and_is_idempotent",
        "model_miss": True,
    },
    {
        "id": "req.history.archive-prune-index",
        "path": "local_kb/maintenance_migration.py",
        "symbol": "validate_migration",
        "test": "tests/test_kb_history_migration.py::KbHistoryMigrationTests::test_prune_resume_merges_partial_manifest_and_preserves_accounting",
        "same_class_test": "tests/test_kb_history_migration.py::KbHistoryMigrationTests::test_migration_resumes_cold_archives_prunes_and_is_idempotent",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.retire-architect",
        "path": "local_kb/install.py",
        "symbol": "install_codex_integration",
        "test": "tests/test_codex_install.py::CodexInstallTests::test_install_is_transactional_current_and_retires_exact_architect",
    },
    {
        "id": "req.upgrade.architect-active-registry-scope",
        "path": "local_kb/codex_registry.py",
        "symbol": "discover_active_registry",
        "test": "tests/test_codex_install.py::CodexInstallTests::test_architect_retirement_checks_only_the_active_codex_registry",
        "same_class_test": "tests/test_codex_install.py::CodexInstallTests::test_router_live_check_uses_canonical_registry_not_display_projection",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.transactional",
        "path": "local_kb/transactional_install.py",
        "symbol": "install_managed_runtime",
        "test": "tests/test_kb_upgrade_migration.py::TransactionalUpgradeMigrationTests::test_injected_failure_rolls_back_replacements_and_retirement",
    },
    {
        "id": "req.upgrade.validation-toolchain-snapshot",
        "path": "local_kb/install.py",
        "symbol": "_freeze_skillguard_validation_toolchain",
        "test": "tests/test_codex_install.py::CodexInstallTests::test_skillguard_validation_toolchain_is_a_stable_snapshot",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "authority_validation_snapshot_missing",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.flowguard-toolchain-snapshot",
        "path": "local_kb/install.py",
        "symbol": "_freeze_flowguard_validation_toolchain",
        "test": "tests/test_codex_install.py::CodexInstallTests::test_flowguard_validation_toolchain_is_a_stable_snapshot",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "authority_validation_snapshot_missing",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.logicguard-toolchain-snapshot",
        "path": "local_kb/install.py",
        "symbol": "_freeze_logicguard_validation_toolchain",
        "test": "tests/test_codex_install.py::CodexInstallTests::test_logicguard_validation_toolchain_is_a_stable_snapshot",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "authority_validation_snapshot_missing",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.current-machine-operator-activation",
        "path": "local_kb/operator_activation.py",
        "symbol": "activate_all_for_current_machine",
        "test": "tests/test_kb_operator_activation.py::test_current_machine_override_repauses_group_when_final_check_fails",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "readback_failure_not_repaused",
        "model_miss": True,
    },
    {
        "id": "req.upgrade.cross-machine-receipt",
        "path": "local_kb/transactional_install.py",
        "symbol": "latest_install_receipt",
        "test": "tests/test_kb_upgrade_migration.py::TransactionalUpgradeMigrationTests::test_repeat_upgrade_converges_and_keeps_similarly_named_user_assets",
    },
    {
        "id": "req.assurance.flowguard-current",
        "path": ".flowguard/run_kb_convergence_checks.py",
        "symbol": "main",
        "test": ".flowguard/run_kb_convergence_checks.py",
    },
    {
        "id": "req.assurance.entrypoint-owner-current",
        "path": "scripts/check_chaos_brain_readiness.py",
        "symbol": "_alignment_from_manifest",
        "test": "tests/test_chaos_brain_readiness.py::ChaosBrainReadinessTests::test_direct_script_context_resolves_the_repo_alignment_owner",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "aggregate_script_import_ambiguous",
        "model_miss": True,
    },
    {
        "id": "req.assurance.skillguard-current",
        "path": "scripts/check_kb_skillguard.py",
        "symbol": "build_report",
        "test": "scripts/check_kb_skillguard.py",
    },
    {
        "id": "req.assurance.former-runtime-absent",
        "path": "scripts/build_kb_automation_skillguard_contracts.py",
        "symbol": "build_contract_source",
        "test": "tests/test_kb_skillguard_current_authority.py::test_all_five_skills_expose_only_the_current_runtime_authority",
    },
    {
        "id": "req.assurance.automation-skillguard-depth",
        "path": "scripts/run_kb_guarded_automation.py",
        "symbol": "run_guarded_automation",
        "test": "tests/test_kb_automation_skillguard.py::test_partial_native_run_receipt_cannot_reach_terminal_closure",
        "same_class_test": "tests/test_kb_automation_activation.py::test_activation_receipt_is_immutable_and_bound_to_both_prior_receipts",
        "model_miss": True,
    },
    {
        "id": "req.assurance.scheduled-production-domain",
        "path": "scripts/check_kb_skillguard.py",
        "symbol": "_report_claim_boundary",
        "test": "tests/test_kb_automation_skillguard.py::test_skillguard_report_claim_boundary_matches_executed_scope",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "source_capability_closes_scheduled_production",
        "model_miss": True,
    },
    {
        "id": "req.assurance.scheduled-six-field-identity",
        "path": "scripts/check_kb_skillguard.py",
        "symbol": "_build_current_scheduled_production_identity",
        "test": "tests/test_kb_automation_skillguard.py::test_scheduled_identity_comes_from_installed_skillguard_six_field_builder",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "scheduled_identity_missing_root_ref",
        "model_miss": True,
    },
    {
        "id": "req.assurance.scheduled-installation-currentness",
        "path": "scripts/check_kb_skillguard.py",
        "symbol": "_build_current_scheduled_production_identity",
        "test": "tests/test_kb_automation_skillguard.py::test_guarded_runner_reports_installed_identity_failure_as_guard_block",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "scheduled_identity_installation_stale",
        "model_miss": True,
    },
    {
        "id": "req.assurance.scheduled-start-frozen-supervision",
        "description": (
            "one official SkillGuard installation context, runtime projection, target-control "
            "projection, and six-field identity are frozen before native execution and reused "
            "for that run; a newer live installation is eligible only for a later run"
        ),
        "path": "scripts/check_kb_skillguard.py",
        "symbol": "_InstalledSupervisionSession",
        "test": "tests/test_kb_automation_skillguard.py::test_supervision_reuses_start_frozen_identity_without_live_recheck",
        "run_name": "focused_tests",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "scheduled_supervision_live_reloaded_after_native",
        "model_miss": True,
    },
    {
        "id": "req.assurance.scheduled-dynamic-evidence-channel",
        "description": (
            "after native execution, the exact current receipt evidence is projected into "
            "the retained start-frozen supervisor through the sole declared dynamic key set; "
            "missing keys clear inherited values and undeclared keys never cross the boundary"
        ),
        "path": "scripts/check_kb_skillguard.py",
        "symbol": "_InstalledSupervisionSession.run_packet",
        "test": "tests/test_kb_automation_skillguard.py::test_frozen_session_protocol_filters_dynamic_environment",
        "run_name": "focused_tests",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "scheduled_dynamic_evidence_not_projected",
        "model_miss": True,
    },
    {
        "id": "req.assurance.scheduled-production-exclusive-lane",
        "description": (
            "real scheduled production owns an exclusive aggregate resource lane after "
            "ordinary child checks, and one Sleep cycle has one final active-index owner"
        ),
        "path": "scripts/check_chaos_brain_readiness.py",
        "symbol": "_execute_plan",
        "test": "tests/test_chaos_brain_readiness.py::ChaosBrainReadinessTests::test_full_regression_has_an_exclusive_validation_lane",
        "run_name": "focused_tests",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "scheduled_production_resource_competition",
        "model_miss": True,
    },
    {
        "id": "req.assurance.resource-sensitive-lanes",
        "description": (
            "LogicGuard performance validation runs on an exclusive lane after "
            "ordinary children and before the separate real scheduled-production lane"
        ),
        "path": "scripts/check_chaos_brain_readiness.py",
        "symbol": "_execute_plan",
        "test": "tests/test_chaos_brain_readiness.py::ChaosBrainReadinessTests::test_full_regression_has_an_exclusive_validation_lane",
        "run_name": "focused_tests",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "performance_validation_resource_competition",
        "model_miss": True,
    },
    {
        "id": "req.assurance.declared-check-reconciliation",
        "path": "scripts/run_kb_guarded_automation.py",
        "symbol": "run_guarded_automation",
        "test": "tests/test_kb_automation_skillguard.py::test_update_supervision_stages_nonterminal_or_closes_enforced",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "close_reruns_target_checks",
        "model_miss": True,
    },
    {
        "id": "req.assurance.update-target-owned-terminal",
        "description": (
            "prepared-update consumes a target-owned non_terminal_authorization "
            "receipt without emitting a closure; legal no-ops and composed finalization "
            "consume target-owned terminal_completion receipts under the sole enforced closure"
        ),
        "path": "scripts/check_kb_skillguard.py",
        "symbol": "_build_and_write_target_native_terminal",
        "test": "tests/test_kb_automation_skillguard.py::test_target_terminal_builder_consumes_run_snapshot_and_native_artifact",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "update_terminal_receipt_not_consumed",
        "model_miss": True,
    },
    {
        "id": "req.assurance.automation-dream-active-lane",
        "path": "local_kb/automation_runtime.py",
        "symbol": "_dream_evidence",
        "test": "tests/test_kb_automation_skillguard.py::test_dream_maintenance_lane_skip_is_not_success",
        "run_name": "semantic_dream_lane",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "dream_active_lane_skipped",
        "model_miss": True,
    },
    {
        "id": "req.assurance.automation-phase-semantic-receipts",
        "path": "local_kb/automation_runtime.py",
        "symbol": "build_native_receipt",
        "test": "tests/test_kb_automation_skillguard.py::test_positive_native_run_receipt_covers_every_domain_phase",
        "run_name": "semantic_phase_receipts",
        "same_class_test": "tests/test_kb_automation_skillguard.py::test_partial_native_run_receipt_cannot_reach_terminal_closure",
        "same_class_run_name": "semantic_phase_receipts",
        "model_miss": True,
    },
    {
        "id": "req.assurance.installed-skillguard-runtime-projection",
        "path": "scripts/run_installed_skillguard_supervision.py",
        "symbol": "_materialize_skillguard_runtime_projection",
        "test": "tests/test_kb_automation_skillguard.py::test_skillguard_runtime_projection_excludes_receipts_and_caches",
        "run_name": "focused_tests",
        "same_class_test": "tests/test_kb_automation_skillguard.py::test_skillguard_runtime_projection_rejects_tampered_behavior",
        "same_class_run_name": "focused_tests",
        "model_miss": True,
    },
    {
        "id": "req.assurance.installed-skillguard-runtime-projection-immutable",
        "description": (
            "importing the content-addressed SkillGuard runtime suppresses bytecode "
            "writes in the supervisor and child Python processes so exact reuse cannot "
            "fail from projection-created __pycache__ files"
        ),
        "path": "scripts/run_installed_skillguard_supervision.py",
        "symbol": "_prevent_runtime_projection_bytecode_mutation",
        "test": "tests/test_kb_automation_skillguard.py::test_skillguard_runtime_projection_stays_cache_free_after_import",
        "run_name": "focused_tests",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "runtime_projection_bytecode_mutated",
        "model_miss": True,
    },
    {
        "id": "req.assurance.supervision-exact-root-authority",
        "description": (
            "source-vs-installed supervision authority comes only from the exact managed "
            "target root; the display surface label is non-authoritative and unknown roots block"
        ),
        "path": "scripts/check_kb_skillguard.py",
        "symbol": "_supervision_target_authority",
        "test": "tests/test_kb_automation_skillguard.py::test_supervision_authority_comes_from_exact_root_not_surface_label",
        "run_name": "focused_tests",
        "same_class_test": "tests/test_kb_automation_skillguard.py::test_supervision_authority_rejects_unknown_or_ambiguous_root",
        "same_class_run_name": "focused_tests",
        "same_class_proof_id": "surface_label_selects_supervision_authority",
        "model_miss": True,
    },
    {
        "id": "req.assurance.target-owned-positive-shallow-fixtures",
        "path": "scripts/check_kb_automation_skillguard_depth.py",
        "symbol": "build_report",
        "test": "tests/test_kb_skillguard_contract_generation.py::AutomationSkillGuardContractGenerationTests::test_target_owned_positive_and_shallow_checks_remain_executable",
        "run_name": "semantic_target_fixtures",
        "same_class_test": "tests/test_kb_skillguard_contract_generation.py::AutomationSkillGuardContractGenerationTests::test_fixture_checks_are_target_owned_and_not_skillguard_protocols",
        "same_class_run_name": "semantic_target_fixtures",
        "model_miss": True,
    },
    {
        "id": "req.assurance.logical-validation-owner-binding",
        "path": "scripts/check_kb_model_test_alignment.py",
        "symbol": "_missing_alignment_run",
        "test": "tests/test_kb_validation_evidence_reuse.py::test_unknown_alignment_run_is_a_failed_gate_not_an_exception",
        "run_name": "focused_tests",
        "same_class_test": "tests/test_kb_validation_evidence_reuse.py::test_alignment_consumes_four_leaf_receipts_without_running_commands",
        "same_class_run_name": "focused_tests",
        "model_miss": True,
    },
    *(
        {
            "id": f"req.assurance.target-owned-fixtures.{target_id}",
            "path": "scripts/check_kb_automation_skillguard_depth.py",
            "symbol": "build_report",
            "test": "tests/test_kb_skillguard_contract_generation.py::AutomationSkillGuardContractGenerationTests::test_target_owned_positive_and_shallow_checks_remain_executable",
            "run_name": "semantic_target_fixtures",
            "same_class_test": ".flowguard/run_kb_convergence_checks.py",
            "same_class_run_name": "flowguard_models",
            "same_class_proof_id": "generic_fixture_targets_substitute_exact_obligations",
            "shared_target_matrix": True,
            "model_miss": True,
            "target_skill_id": target_id,
        }
        for target_id in (
            "kb-sleep-maintenance",
            "kb-dream-pass",
            "kb-organization-contribute",
            "kb-organization-maintenance",
            "khaos-brain-update",
        )
    ),
    {
        "id": "req.assurance.automation-gated-noop-scope",
        "path": "local_kb/automation_runtime.py",
        "symbol": "_gated_noop_evidence",
        "test": "tests/test_kb_automation_native_receipts.py::test_organization_contribution_noop_performs_only_settings_gate",
        "run_name": "semantic_gated_noop",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "gated_noop_overclaims_obligations",
        "model_miss": True,
    },
    {
        "id": "req.assurance.update-noop-exact-receipt",
        "path": "local_kb/automation_runtime.py",
        "symbol": "_update_evidence",
        "test": "tests/test_software_update.py::SoftwareUpdateStateTests::test_update_noop_requires_enforced_exact_receipt",
        "run_name": "semantic_update_noop",
        "same_class_test": ".flowguard/run_kb_convergence_checks.py",
        "same_class_run_name": "flowguard_models",
        "same_class_proof_id": "update_noop_authorization_only",
        "model_miss": True,
    },
    {
        "id": "req.assurance.model-test-ci",
        "path": "scripts/check_kb_model_test_alignment.py",
        "symbol": "build_report",
        "test": "scripts/run_flowguard_suite.py",
    },
    {
        "id": "req.assurance.final-gate",
        "path": "local_kb/install.py",
        "symbol": "build_installation_check",
        "test": "tests/test_codex_install.py::CodexInstallTests::test_real_upgrade_wrapper_keeps_pause_until_final_restore_transaction",
    },
    {
        "id": "req.assurance.no-recursive-install",
        "path": "scripts/install_codex_kb.py",
        "symbol": "main",
        "test": "tests/test_cli_output_contract.py::CliOutputContractTests::test_installer_and_check_json_are_safe_under_cp1252",
        "same_class_test": "tests/test_cli_output_contract.py::CliOutputContractTests::test_aggregate_assurance_child_cannot_recursively_run_upgrade_gates",
        "model_miss": True,
    },
    {
        "id": "req.retrieval.source-boundary",
        "path": "local_kb/search.py",
        "symbol": "search_multi_source_entries",
        "test": "tests/test_e2e_two_machine_cache_pool_lifecycle.py::TwoMachineCachePoolLifecycleE2ETests::test_machine_b_syncs_org_cache_adopts_skill_card_and_exports_diverged_feedback",
        "same_class_test": "tests/test_multi_source_search.py::MultiSourceSearchTests::test_untrusted_organization_candidate_is_visible_without_leaking_local_candidate",
        "model_miss": True,
    },
)


_RUN_ALIASES = {
    "focused_tests": "full_regression",
    "flowguard_models": "flowguard_models",
    "flowguard_meshes": "flowguard_meshes",
    "skillguard_sources": "skillguard_source_assurance",
    "semantic_dream_lane": "full_regression",
    "semantic_phase_receipts": "full_regression",
    "semantic_target_fixtures": "full_regression",
    "semantic_gated_noop": "full_regression",
    "semantic_update_noop": "full_regression",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _artifact_ref_current(ref: dict[str, Any]) -> bool:
    path = Path(str(ref.get("path") or ""))
    if not path.is_file() or not str(ref.get("sha256") or ""):
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == str(ref["sha256"])


def _receipt_current(
    receipt: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    before = manifest.get("source_snapshot_before", {})
    verifier = manifest.get("verifier_fingerprint", {})
    inputs = receipt.get("input_fingerprints", {})
    if receipt.get("terminal_status") != "passed" or receipt.get("ok") is not True:
        failures.append("receipt_not_passed")
    if receipt.get("timed_out") is True:
        failures.append("receipt_timed_out")
    if inputs.get("source") != before.get("digest"):
        failures.append("source_fingerprint_mismatch")
    if inputs.get("verifier") != verifier.get("digest"):
        failures.append("verifier_fingerprint_mismatch")
    if receipt.get("inventory_revision") != manifest.get("inventory_revision"):
        failures.append("inventory_revision_mismatch")
    if not _artifact_ref_current(receipt.get("proof_artifact_ref", {})):
        failures.append("proof_artifact_missing_or_changed")
    return not failures, failures


def _manifest_runs(
    manifest: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    findings: list[str] = []
    if manifest.get("schema_version") != "khaos-brain.validation-evidence.v1":
        findings.append("unsupported_or_missing_evidence_manifest")
    if manifest.get("source_stable_during_leaf_execution") is not True:
        findings.append("source_changed_during_leaf_execution")
    if manifest.get("duplicate_exact_executions"):
        findings.append("duplicate_exact_leaf_execution")
    entries = manifest.get("entries", {})
    if not isinstance(entries, dict):
        return {}, [*findings, "evidence_entries_missing"]
    runs: dict[str, dict[str, Any]] = {}
    for consumer_name, producer_name in _RUN_ALIASES.items():
        receipt = entries.get(producer_name, {})
        if not isinstance(receipt, dict) or not receipt:
            findings.append(f"missing_receipt:{producer_name}")
            runs[consumer_name] = {
                "ok": False,
                "command": [],
                "receipt_failures": ["missing_receipt"],
            }
            continue
        current, failures = _receipt_current(receipt, manifest)
        if not current:
            findings.extend(
                f"stale_receipt:{producer_name}:{failure}" for failure in failures
            )
        runs[consumer_name] = {
            **receipt,
            "ok": current,
            "receipt_failures": failures,
            "producer_name": producer_name,
        }
    return runs, sorted(set(findings))


def _current_runs(
    *,
    evidence_manifest: dict[str, Any] | Path | None = None,
    run_missing: bool = False,
) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, Any]]:
    if isinstance(evidence_manifest, Path):
        manifest = _load_json(evidence_manifest)
    elif isinstance(evidence_manifest, dict):
        manifest = evidence_manifest
    else:
        manifest = _load_json(DEFAULT_EVIDENCE_MANIFEST)
    runs, findings = _manifest_runs(manifest)
    if run_missing and (not manifest or findings):
        # Explicit standalone repair mode delegates execution to the sole
        # release owner.  The resulting alignment is then consumed below; no
        # focused or semantic pytest command is launched a second time.
        from scripts import check_chaos_brain_readiness as readiness

        readiness.build_report(REPO_ROOT, Path.home() / ".codex", pre_restore=True)
        manifest = _load_json(DEFAULT_EVIDENCE_MANIFEST)
        runs, findings = _manifest_runs(manifest)
    return runs, findings, manifest


def _matching_passed_nodes(
    run: dict[str, Any],
    target: str,
    *,
    parameter: str = "",
) -> tuple[str, ...]:
    passed = tuple(str(item) for item in run.get("junit", {}).get("passed_node_ids", []))
    target = target.replace("\\", "/")
    if "::" not in target:
        return tuple(item for item in passed if item.startswith(target + "::"))
    matches = tuple(
        item for item in passed if item == target or item.startswith(target + "[")
    )
    if parameter:
        parameterized = tuple(
            item
            for item in matches
            if f"[{parameter}]" in item or parameter in item.rsplit("::", 1)[-1]
        )
        return parameterized
    return matches


def _contract_id(obligation_id: str) -> str:
    return "owner:" + obligation_id.removeprefix("req.")


def _missing_alignment_run(run_name: str) -> dict[str, Any]:
    """Represent an invalid logical owner without crashing the aggregate gate."""

    return {
        "ok": False,
        "command": ["missing-alignment-run", run_name],
        "junit": {"passed_node_ids": []},
        "proof_artifact": {},
        "missing_alignment_run": run_name,
    }


def _alignment_report(runs: dict[str, dict[str, Any]]):
    obligations = tuple(
        flowguard.ModelObligation(
            item["id"],
            description=str(
                item.get("description")
                or f"Chaos Brain verification obligation {item['id']}"
            ),
            # A broad green command can support one positive external-contract
            # row, never both a happy and a failure-path claim.  Model-miss
            # obligations separately require exact observed and same-class
            # node evidence below.
            required_test_kinds=(
                (
                    flowguard.TEST_KIND_FAILURE_PATH,
                    flowguard.TEST_KIND_HAPPY_PATH,
                )
                if item.get("model_miss")
                else (flowguard.TEST_KIND_HAPPY_PATH,)
            ),
            risk_level="high",
            model_miss_origin=bool(item.get("model_miss")),
            requires_same_class_test_evidence=bool(item.get("model_miss")),
        )
        for item in OBLIGATIONS
    )
    contracts = tuple(
        flowguard.CodeContract(
            _contract_id(item["id"]),
            path=item["path"],
            symbol=item["symbol"],
            role=flowguard.CODE_CONTRACT_ROLE_OWNER,
            implements_obligations=(item["id"],),
        )
        for item in OBLIGATIONS
    )
    evidence: list[flowguard.TestEvidence] = []
    for item in OBLIGATIONS:
        if item.get("run_name"):
            run_name = str(item["run_name"])
        elif item["id"] == "req.assurance.flowguard-current":
            run_name = "flowguard_models"
        elif item["id"] == "req.assurance.skillguard-current":
            run_name = "skillguard_sources"
        elif item["id"] == "req.assurance.model-test-ci":
            run_name = "flowguard_meshes"
        else:
            run_name = "focused_tests"
        run = runs.get(run_name, _missing_alignment_run(run_name))
        if item.get("model_miss"):
            for suffix, test_kind, closure_role, path, evidence_run_name in (
                (
                    "observed",
                    flowguard.TEST_KIND_FAILURE_PATH,
                    flowguard.TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
                    item["test"],
                    run_name,
                ),
                (
                    "same-class",
                    flowguard.TEST_KIND_HAPPY_PATH,
                    flowguard.TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
                    item["same_class_test"],
                    str(item.get("same_class_run_name") or run_name),
                ),
            ):
                evidence_run = runs.get(
                    evidence_run_name,
                    _missing_alignment_run(evidence_run_name),
                )
                proof_id = (
                    str(item.get("same_class_proof_id") or "")
                    if suffix == "same-class"
                    else ""
                )
                if proof_id and evidence_run_name == "flowguard_models":
                    proof_status = (
                        evidence_run.get("json_payload", {})
                        .get("known_bad_proofs", {})
                        .get(proof_id)
                    )
                    matches = (
                        (f"{path}#known-bad:{proof_id}",)
                        if proof_status == "failed" and evidence_run.get("ok")
                        else ()
                    )
                else:
                    matches = _matching_passed_nodes(
                        evidence_run,
                        path,
                        parameter=(
                            ""
                            if item.get("shared_target_matrix")
                            else str(item.get("target_skill_id") or "")
                        ),
                    )
                # Model-miss closure must bind an exact external-contract node;
                # a whole-file green result is intentionally not promoted.
                if (
                    (not proof_id and "::" not in path)
                    or not matches
                    or not evidence_run.get("ok")
                ):
                    continue
                command = " ".join(
                    str(part) for part in evidence_run["command"]
                )
                evidence.append(
                    flowguard.TestEvidence(
                        f"{evidence_run_name}:{item['id']}:{suffix}",
                        test_name=f"{item['id']} {suffix}",
                        path=matches[0],
                        command=command,
                        result_status="passed",
                        evidence_current=evidence_run.get("ok") is True,
                        test_kind=test_kind,
                        closure_evidence_role=closure_role,
                        covered_obligations=(item["id"],),
                        covered_code_contracts=(_contract_id(item["id"]),),
                        assertion_scope=flowguard.TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                    )
                )
            continue
        command = " ".join(str(part) for part in run["command"])
        is_pytest_evidence = run_name in {
            "focused_tests",
            "semantic_dream_lane",
            "semantic_phase_receipts",
            "semantic_target_fixtures",
            "semantic_gated_noop",
            "semantic_update_noop",
        }
        matches = (
            _matching_passed_nodes(
                run,
                item["test"],
                parameter=(
                    ""
                    if item.get("shared_target_matrix")
                    else str(item.get("target_skill_id") or "")
                ),
            )
            if is_pytest_evidence
            else (item["test"],) if run.get("ok") else ()
        )
        if not matches or not run.get("ok"):
            continue
        evidence.append(
            flowguard.TestEvidence(
                f"{run_name}:{item['id']}:happy",
                test_name=f"{item['id']} exact current evidence",
                path=matches[0],
                command=command,
                result_status="passed",
                evidence_current=True,
                test_kind=flowguard.TEST_KIND_HAPPY_PATH,
                covered_obligations=(item["id"],),
                covered_code_contracts=(_contract_id(item["id"]),),
                assertion_scope=flowguard.TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            )
        )
    return flowguard.review_model_test_alignment(
        flowguard.ModelTestAlignmentPlan(
            "kb-convergence-upgrade",
            obligations=obligations,
            code_contracts=contracts,
            test_evidence=tuple(evidence),
            allow_orphan_tests=False,
            allow_orphan_code_contracts=False,
        )
    )


def build_report(
    *,
    evidence_manifest: dict[str, Any] | Path | None = None,
    run_missing: bool = False,
) -> dict[str, Any]:
    runs, receipt_findings, manifest = _current_runs(
        evidence_manifest=evidence_manifest,
        run_missing=run_missing,
    )
    alignment = _alignment_report(runs)
    owner_counts: dict[str, int] = {}
    for item in OBLIGATIONS:
        owner_counts[item["id"]] = owner_counts.get(item["id"], 0) + 1
    exactly_one_owner = all(count == 1 for count in owner_counts.values())
    all_commands_passed = all(run.get("ok") is True for run in runs.values())
    return {
        "schema_version": 1,
        "check": "kb-model-code-test-alignment",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": (
            alignment.ok
            and exactly_one_owner
            and all_commands_passed
            and not receipt_findings
        ),
        "flowguard_schema_version": flowguard.SCHEMA_VERSION,
        "alignment": alignment.to_dict(),
        "owner_counts": owner_counts,
        "exactly_one_primary_owner": exactly_one_owner,
        "current_runs": runs,
        "receipt_findings": receipt_findings,
        "evidence_manifest_run_id": str(manifest.get("run_id") or ""),
        "consumed_receipt_ids": sorted(
            {
                str(run.get("receipt_id") or "")
                for run in runs.values()
                if run.get("receipt_id")
            }
        ),
        "obligation_ids": [item["id"] for item in OBLIGATIONS],
        "claim_boundary": (
            "Current exact leaf receipts composed by the release owner. Pytest evidence "
            "comes from the one JUnit-backed full regression; broad green commands are "
            "not duplicated into multiple test kinds. Live-machine migration remains a "
            "separate final gate."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write-receipt", action="store_true")
    parser.add_argument("--evidence-manifest", type=Path)
    parser.add_argument(
        "--run-missing",
        action="store_true",
        help="Explicitly delegate missing leaf execution to aggregate readiness.",
    )
    args = parser.parse_args()
    report = build_report(
        evidence_manifest=args.evidence_manifest,
        run_missing=args.run_missing,
    )
    if not args.no_write_receipt:
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Model-code-test alignment:", "PASS" if report["ok"] else "FAIL")
        for name, run in report["current_runs"].items():
            print(("PASS" if run["ok"] else "FAIL"), name, run["duration_seconds"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
