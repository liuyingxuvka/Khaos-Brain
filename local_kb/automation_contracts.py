"""Target-specific completion contracts for Chaos Brain automations.

The scheduled prompt selects the native Skill; it is not itself completion
evidence.  These records bind each surviving automation to the important
target-owned obligations, production entrypoint, native regression evidence,
and fail-closed SkillGuard depth profile used by release assurance.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping


STANDARD_NATIVE_TIMEOUT_SECONDS = 900
UPDATE_NATIVE_TIMEOUT_SECONDS = 10800
STANDARD_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS = 1200
UPDATE_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS = 11100
AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS = 16200
PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS = 16800


SKILLGUARD_COMPLETION_MARKER = "enforced SkillGuard closure receipt"
SKILLGUARD_PARTIAL_MARKER = "intake, planning, or proposal-only output is incomplete"

# One target-neutral policy surface is shared by contract generation, upgrade
# cross-surface parity checks, and runtime assurance. Keeping these values here
# prevents a newly generated contract from advertising capabilities that the
# installer forgot to require (or the reverse).
SKILLGUARD_AUTOMATION_PROVIDER_ID = "skillguard-local-provider"
SKILLGUARD_AUTOMATION_RUNTIME_CONTRACT_ID = (
    "skillguard-declared-check-supervision-current"
)
SKILLGUARD_AUTOMATION_RUNTIME_CAPABILITY_IDS = (
    "declared-check-inventory.v1",
    "declared-check-receipt-reconciliation.v1",
    "installation-receipt-binding.v1",
    "installation-currentness-replay.v1",
    "provider-runtime-enrollment.v1",
    "single-flight-check-execution.v1",
)


def _obligation(
    suffix: str,
    phase: str,
    dimension: str,
    summary: str,
    *evidence_tests: str,
    evidence_source: str = "native-receipt",
) -> dict[str, Any]:
    return {
        "suffix": suffix,
        "phase": phase,
        "dimension": dimension,
        "summary": summary,
        "evidence_tests": list(evidence_tests),
        "evidence_source": evidence_source,
        "important": True,
    }


AUTOMATION_COMPLETION_CONTRACTS: dict[str, dict[str, Any]] = {
    "kb-sleep-maintenance": {
        "automation_id": "kb-sleep",
        "entrypoint_path": ".agents/skills/local-kb-retrieve/scripts/kb_sleep.py",
        "native_test_files": [
            "tests/test_kb_lifecycle.py",
            "tests/test_kb_sleep_convergence.py",
            "tests/test_kb_retrieval_calibration.py",
            "tests/test_khaos_logicguard_models.py",
            "tests/test_khaos_model_projection.py",
            "tests/test_khaos_sleep_model_maintenance.py",
            "tests/test_maintenance_lanes.py",
            "tests/test_process_control.py",
        ],
        "prompt_markers": [
            "committed increment",
            "explicit disposition",
            "executable reopen conditions",
            "promotion or downgrade review",
            "Dream handoffs exactly once",
            "sole canonical model-generation publisher",
            "LogicGuard model revision",
            "grounded ModelMesh",
            "explicit model gaps",
            "rebuild and validate the active index",
            "watermark unchanged",
        ],
        "obligations": [
            _obligation("lane-delta-intake", "intake", "input", "Acquire or safely recover the lane, then read only actionable work after the committed watermark while skipping already-terminal history.", "test_observation_is_admitted_and_disposed_by_next_sleep", "test_sleep_recovers_zero_watermark_by_skipping_terminal_history", "test_fresh_lane_lock_with_dead_owner_is_recovered_immediately"),
            _obligation("observation-disposition", "execute", "workflow", "Give every admitted observation one durable current disposition through one bounded lifecycle batch.", "test_observation_is_admitted_and_disposed_by_next_sleep", "test_sleep_batches_new_history_admission_and_disposition"),
            _obligation("candidate-outcomes", "execute", "branch", "Resolve candidates through bounded evidence-backed terminal or reopenable outcomes.", "test_candidate_promotes_only_with_independent_support_and_validation", "test_candidate_terminal_transition_is_replayable"),
            _obligation("evidence-calibration", "execute", "semantic", "Use verified outcomes and contradictions for promotion, suspension, and downgrade through one shared evidence index per review cycle.", "test_verified_contradiction_immediately_suspends_trusted_retrieval", "test_candidate_review_reuses_one_calibration_evidence_index"),
            _obligation("logicguard-model-revision", "execute", "workflow", "Represent every admitted card as an exact LogicGuard model revision with a root claim, context and method, typed support or challenge nodes, and an explicit disposition ledger for gaps instead of invented support.", "test_argument_block_is_deterministic_and_missing_roles_are_explicit", "test_explicit_evidence_requires_and_preserves_typed_provenance", "test_sleep_upserts_models_and_preserves_projection_extensions"),
            _obligation("grounded-model-mesh", "execute", "semantic", "Assemble exact model revisions into a scoped ModelMesh and admit canonical cross-model relations only with qualifying non-AI provenance; co-use and legacy links remain unresolved proposals.", "test_mesh_pins_exact_models_and_materializes_grounded_relation", "test_ai_only_relation_and_cross_scope_relation_are_rejected", "test_model_revision_moves_old_relation_to_revalidation_queue"),
            _obligation("dream-handoff-once", "execute", "side_effect", "Consume each typed Dream handoff at most once.", "test_dream_handoff_is_acknowledged_once_by_sleep"),
            _obligation("atomic-model-generation", "verify", "closure", "Publish the complete model, mesh, deterministic projection, active index, generation manifest, and pointer as one rollbackable generation with the pointer last.", "test_empty_library_publishes_a_valid_zero_model_generation", "test_failed_index_publication_restores_prior_generation_and_projection", "test_projection_is_deterministic_and_exactly_validated"),
            _obligation("index-watermark-commit", "verify", "closure", "Publish a validated active index and advance the watermark only after durable success.", "test_second_sleep_is_bounded_noop_without_duplicate_events", "test_active_index_excludes_terminal_states_and_serializes_dates"),
            _obligation("failure-fail-closed", "verify", "recovery", "Keep the watermark unchanged and report failure on any blocker.", "test_failed_history_parse_does_not_advance_watermark"),
            _obligation("timeout-tree-cleanup", "verify", "recovery", "On timeout terminate the complete owned process tree, prove zero descendants, and preserve parent cleanup margin.", "test_timeout_terminates_the_complete_descendant_tree", "test_timeout_hierarchy_preserves_cleanup_margin"),
            _obligation("depth-calibration", "verify", "validation", "Reject shallow proposal-only completion and require the full native receipt.", "test_all_automation_contracts_are_deep_and_current", "test_shallow_automation_contract_is_rejected"),
        ],
    },
    "kb-dream-pass": {
        "automation_id": "kb-dream",
        "entrypoint_path": ".agents/skills/local-kb-retrieve/scripts/kb_dream.py",
        "native_test_files": [
            "tests/test_kb_dream.py",
            "tests/test_khaos_logicguard_models.py",
            "tests/test_process_control.py",
        ],
        "prompt_markers": [
            "stable fingerprints",
            "no_delta_closed",
            "small valuable",
            "route-deduplicated",
            "pin the exact LogicGuard generation",
            "evidence removal",
            "assumption removal",
            "rebuttal strengthening",
            "typed idempotent Sleep handoffs",
            "must not directly write cards",
        ],
        "obligations": [
            _obligation("lane-evidence-intake", "intake", "input", "Acquire the Dream lane and load current opportunity evidence.", "test_dream_run_recovers_stale_lane_lock_instead_of_skipping"),
            _obligation("stable-fingerprint", "execute", "semantic", "Fingerprint decision-relevant evidence without volatile run metadata.", "test_dream_run_skips_prior_passed_sandbox_validation"),
            _obligation("bounded-selection", "execute", "branch", "Select a small valuable route-deduplicated experiment batch.", "test_dream_selection_uses_bounded_route_deduped_batch"),
            _obligation("sandbox-experiment", "execute", "workflow", "Execute the native bounded experiment or candidate-validation path.", "test_dream_run_can_validate_existing_candidate_entry"),
            _obligation("exact-model-simulation", "execute", "semantic", "Pin one exact LogicGuard generation, model revision, root block, and mesh revision, then run a bounded applicable suite covering evidence removal, assumption removal, rebuttal strengthening, boundary pressure, cross-edge removal, and neighbor-pin replacement only against that immutable snapshot.", "test_dream_simulation_is_exact_and_does_not_advance_mesh", "test_dream_probe_covers_model_roles_cross_edge_and_neighbor_pin"),
            _obligation("no-delta-closure", "execute", "reuse", "Close unchanged evidence as a deterministic successful no-op.", "test_dream_run_noops_when_no_opportunity_clears_value_gate"),
            _obligation("typed-handoff-once", "execute", "side_effect", "Emit at most one typed idempotent Sleep handoff for a material delta.", "test_dream_hands_single_adjacent_observation_to_sleep"),
            _obligation("no-direct-knowledge-write", "verify", "scope", "Never mutate cards, candidates, confidence, or central predictive history directly.", "test_dream_run_records_history_only_for_taxonomy_gap"),
            _obligation("canonical-generation-unchanged", "verify", "scope", "Prove that Dream did not advance or rewrite canonical model or mesh authority and hand only typed model-gap findings to Sleep.", "test_dream_simulation_is_exact_and_does_not_advance_mesh", "test_dream_hands_single_adjacent_observation_to_sleep"),
            _obligation("terminal-receipt", "verify", "closure", "Return a bounded no-op, handoff, or failure receipt rather than partial progress.", "test_dream_selects_multiple_valuable_experiments_in_plan_order"),
            _obligation("timeout-tree-cleanup", "verify", "recovery", "On timeout terminate the complete owned process tree, prove zero descendants, and preserve parent cleanup margin.", "test_timeout_terminates_the_complete_descendant_tree", "test_timeout_hierarchy_preserves_cleanup_margin"),
            _obligation("depth-calibration", "verify", "validation", "Reject shallow selection-only completion and require the full native receipt.", "test_all_automation_contracts_are_deep_and_current", "test_shallow_automation_contract_is_rejected"),
        ],
    },
    "kb-organization-contribute": {
        "automation_id": "kb-org-contribute",
        "entrypoint_path": "scripts/kb_org_outbox.py",
        "native_test_files": [
            "tests/test_org_automation.py",
            "tests/test_org_outbox.py",
            "tests/test_skill_sharing.py",
            "tests/test_e2e_skill_bundle_contribution_flow.py",
            "tests/test_github_repo_config.py",
            "tests/test_org_checks.py",
            "tests/test_process_control.py",
        ],
        "prompt_markers": [
            "successful no-op",
            "sync the organization mirror first",
            "content-hash-gated outbox",
            "do not export private cards",
            "Skill bundles",
            "open a GitHub PR",
            "Run KB postflight",
        ],
        "obligations": [
            _obligation("settings-noop-gate", "intake", "input", "Treat missing or invalid organization settings as a receipt-backed successful no-op.", "test_contribution_noops_without_valid_organization_settings", "test_automation_scripts_noop_successfully_without_settings"),
            _obligation("sync-preflight", "intake", "route", "Sync the validated organization mirror and run organization preflight before export.", "test_contribution_syncs_and_uploads_created_outbox_to_import_branch"),
            _obligation("privacy-shareability", "execute", "scope", "Export only shareable public models and exclude private or machine-specific material before any branch or push.", "test_outbox_blocks_machine_specific_payloads_before_materialization", "test_contribution_blocks_machine_specific_public_payload_before_branch"),
            _obligation("content-hash-dedup", "execute", "reuse", "Block every previously exchanged or currently present content hash.", "test_contribution_ignores_stale_outbox_when_hash_exists_in_organization", "test_outbox_skips_hashes_previously_downloaded_from_organization"),
            _obligation("skill-bundle-author-version", "execute", "semantic", "Bundle dependent Skills with hash, author, version, and original-author update policy.", "test_contribution_skill_bundle_receipt_preserves_author_version_hash_policy", "test_dependency_manifest_builds_card_bound_skill_bundle_metadata", "test_latest_skill_bundle_version_is_selected_by_version_time"),
            _obligation("branch-pr-auto-merge", "execute", "side_effect", "Use the import branch, push/PR path, and auto-merge label only when checks allow.", "test_contribution_pr_and_label_are_check_gated", "test_create_pull_request_posts_pr_then_labels"),
            _obligation("postflight-terminal", "verify", "closure", "Record postflight and return a complete created/skipped/error receipt.", "test_contribution_records_postflight_on_non_skipped_success"),
            _obligation("lane-failure-recovery", "verify", "recovery", "Close the lane correctly and surface errors without partial success claims.", "test_contribution_sync_failure_releases_lane_and_returns_failed_terminal"),
            _obligation("timeout-tree-cleanup", "verify", "recovery", "On timeout terminate the complete owned process tree, prove zero descendants, and preserve parent cleanup margin.", "test_timeout_terminates_the_complete_descendant_tree", "test_timeout_hierarchy_preserves_cleanup_margin"),
            _obligation("depth-calibration", "verify", "validation", "Reject shallow outbox-only completion and require the full native receipt.", "test_all_automation_contracts_are_deep_and_current", "test_shallow_automation_contract_is_rejected"),
        ],
    },
    "kb-organization-maintenance": {
        "automation_id": "kb-org-maintenance",
        "entrypoint_path": "scripts/kb_org_maintainer.py",
        "native_test_files": [
            "tests/test_org_automation.py",
            "tests/test_org_maintenance.py",
            "tests/test_org_cleanup.py",
            "tests/test_skill_sharing.py",
            "tests/test_org_checks.py",
            "tests/test_github_repo_config.py",
            "tests/test_process_control.py",
        ],
        "prompt_markers": [
            "successful no-op",
            "manifest",
            "similar-card merge checkpoint",
            "overloaded-card split checkpoint",
            "Skill safety checkpoint",
            "exact selected action ids",
            "post-apply organization check",
            "GitHub merge-readiness checkpoint",
        ],
        "obligations": [
            _obligation("settings-participation-gate", "intake", "input", "Require validated settings and explicit organization-maintenance participation.", "test_maintenance_noops_until_participation_is_requested"),
            _obligation("manifest-git-preflight", "intake", "route", "Validate organization layout, manifest, repository state, and entry lanes.", "test_maintenance_runs_when_participation_is_requested", "test_maintenance_sync_failure_releases_lane_and_returns_failed_terminal"),
            _obligation("card-candidate-intake", "execute", "workflow", "Inspect main cards, imports, candidates, hashes, and cleanup proposals.", "test_maintenance_runs_when_participation_is_requested"),
            _obligation("card-decision-coverage", "execute", "semantic", "Give every reviewed card exactly one keep, watch, or change decision with a reason and complete review dimensions.", "test_maintenance_records_one_decision_for_every_reviewed_card"),
            _obligation("merge-split-decisions", "execute", "branch", "Record merge, split, promotion, rejection, watch, or rewrite decisions.", "test_maintenance_records_merge_and_split_checkpoint_decisions"),
            _obligation("skill-safety-version", "execute", "scope", "Enforce Skill safety, hash, original-author, fork, and latest-version boundaries.", "test_maintenance_enforces_skill_author_hash_version_and_fork_policy", "test_skill_registry_rejects_unknown_state_and_unpinned_approved_skill"),
            _obligation("exact-selected-apply", "execute", "side_effect", "Apply only exact selected action ids and preserve local adoption authority.", "test_maintenance_applies_exact_selected_ids"),
            _obligation("postapply-merge-readiness", "verify", "validation", "Run post-apply organization checks and use their decision to gate the GitHub label.", "tests/test_org_maintenance.py::OrganizationMaintenanceTests::test_maintenance_postapply_readiness_controls_pr_and_label"),
            _obligation("postflight-terminal", "verify", "closure", "Record a complete no-op, applied, blocked, or failure receipt.", "test_maintenance_records_postflight_on_non_skipped_success"),
            _obligation("timeout-tree-cleanup", "verify", "recovery", "On timeout terminate the complete owned process tree, prove zero descendants, and preserve parent cleanup margin.", "test_timeout_terminates_the_complete_descendant_tree", "test_timeout_hierarchy_preserves_cleanup_margin"),
            _obligation("depth-calibration", "verify", "recovery", "Reject inspection-only completion and require the full native receipt.", "test_all_automation_contracts_are_deep_and_current", "test_shallow_automation_contract_is_rejected"),
        ],
    },
    "khaos-brain-update": {
        "automation_id": "khaos-brain-system-update",
        "entrypoint_path": "scripts/run_khaos_brain_system_update.py",
        "native_test_files": [
            "tests/test_software_update.py",
            "tests/test_kb_automation_native_receipts.py",
            "tests/test_codex_install.py",
            "tests/test_khaos_logicguard_migration.py",
            "tests/test_kb_upgrade_migration.py",
            "tests/test_kb_automation_activation.py",
            "tests/test_process_control.py",
        ],
        "prompt_markers": [
            "successful terminal no-op",
            "explicitly prepared update",
            "Git fast-forward only",
            "transactional installer",
            "versioned maintenance migration",
            "direct-to-current LogicGuard authority",
            "zero retired authority residuals",
            "every hard gate passes",
            "keep surviving automations paused",
        ],
        "obligations": [
            _obligation("authorization-system-check", "intake", "input", "Require an explicit prepared update and a safe system-check result.", "test_system_check_marks_upgrading_when_prepared_and_ui_closed", "test_system_check_waits_when_ui_is_running", "test_all_legal_update_noops_perform_only_system_gate", "test_native_update_runner_keeps_operational_blockers_unfinished"),
            _obligation("preserve-state-rollback", "intake", "recovery", "Snapshot local knowledge, settings, automation state, and rollback authority.", "test_update_snapshot_is_not_reused_for_a_different_target_revision", "test_update_guarded_runner_preserves_status_and_user_pause_independently"),
            _obligation("fast-forward-only", "execute", "scope", "Update only through the authorized Git fast-forward path.", "test_prepared_update_uses_only_ff_only_and_waits_for_skillguard_before_current"),
            _obligation("migration-debt-settlement", "execute", "workflow", "Run the versioned resumable history and maintenance-debt migration.", "test_repeat_upgrade_converges_and_keeps_similarly_named_user_assets"),
            _obligation("logicguard-authority-cutover", "execute", "workflow", "Use the versioned upgrade owner to convert every valid legacy card directly into current LogicGuard models, scoped meshes, deterministic projections, the exact active index, and the generation pointer with no normal-runtime legacy reader.", "test_direct_migration_publishes_scoped_exact_authority_and_zero_legacy_semantics", "test_second_run_is_an_exact_no_delta"),
            _obligation("transaction-retirement", "execute", "side_effect", "Install complete trees transactionally and retire exact Architect surfaces.", "test_install_is_transactional_current_and_retires_exact_architect"),
            _obligation("zero-retired-authority", "verify", "validation", "Reject activation when legacy semantic authority, an incomplete exact binding, or any incompatible residual survives; migration failure restores the complete pre-upgrade surface.", "test_failures_after_each_publication_boundary_restore_the_pre_migration_surface", "test_malformed_legacy_card_blocks_before_any_authority_write", "test_incomplete_current_authority_is_rejected_before_activation"),
            _obligation("aggregate-hard-gates", "verify", "validation", "Require current migration, parity, FlowGuard, SkillGuard, retrieval, and regression evidence before restoration is authorized.", "test_prepared_update_uses_only_ff_only_and_waits_for_skillguard_before_current", "test_update_skillguard_failure_keeps_survivors_paused_and_marks_failed"),
            _obligation("restore-or-stay-paused", "verify", "branch", "Authorize restoration only after the native hard gates pass; until then, and on authorization failure, every survivor remains paused.", "test_prepared_update_uses_only_ff_only_and_waits_for_skillguard_before_current", "test_update_skillguard_failure_keeps_survivors_paused_and_marks_failed"),
            _obligation("final-machine-receipt", "verify", "closure", "End the native route at awaiting-skillguard without marking CURRENT; only no-update, waiting-for-user, and ui-running may be successful native no-op terminals.", "test_prepared_update_uses_only_ff_only_and_waits_for_skillguard_before_current", "test_all_legal_update_noops_perform_only_system_gate", "test_update_operational_blockers_cannot_close_as_successful_noops", "test_native_update_runner_keeps_operational_blockers_unfinished"),
            _obligation("timeout-tree-cleanup", "verify", "recovery", "On timeout terminate the complete owned process tree, prove zero descendants, and preserve parent cleanup margin.", "test_timeout_terminates_the_complete_descendant_tree", "test_timeout_hierarchy_preserves_cleanup_margin"),
            _obligation(
                "staged-restoration-authorization",
                "finalize",
                "closure",
                "Consume an immutable staged-restoration authorization receipt binding the snapshot statuses and user-pause bits, every planned automation.toml hash, the native receipt, the non-terminal declared-check authorization receipt, and the deferred installation check before any live restoration.",
                "test_update_guarded_runner_restores_only_after_skillguard_closure",
                "test_update_guarded_runner_preserves_status_and_user_pause_independently",
                "test_update_final_skillguard_failure_repauses_every_survivor_and_marks_failed",
                "test_update_restoration_failure_stops_before_final_skillguard_and_repauses",
                "test_restoration_plan_does_not_activate_live_automations",
                "test_restoration_apply_rejects_any_post_authorization_source_change",
                "test_finalization_receipt_rejects_a_live_active_source",
                "test_activation_receipt_is_immutable_and_bound_to_both_prior_receipts",
                evidence_source="update-finalization-receipt",
            ),
            _obligation("depth-calibration", "verify", "reuse", "Reject check-only or install-only completion and require the full native receipt.", "test_all_automation_contracts_are_deep_and_current", "test_shallow_automation_contract_is_rejected"),
        ],
    },
}


def obligation_id(skill_id: str, suffix: str) -> str:
    return f"obligation:{skill_id}:{suffix}"


def step_id(skill_id: str, phase: str) -> str:
    return f"step:{skill_id}:{phase}"


def check_id(skill_id: str, kind: str) -> str:
    return f"check:{skill_id}:{kind}"


def native_receipt_artifact_id(skill_id: str) -> str:
    return f"artifact:{skill_id}:native-receipt"


def update_finalization_artifact_id() -> str:
    return "artifact:khaos-brain-update:finalization-receipt"


def expected_obligation_ids(skill_id: str) -> tuple[str, ...]:
    return tuple(
        obligation_id(skill_id, str(row["suffix"]))
        for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]
    )


def obligation_ids_by_phase(skill_id: str) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]:
        grouped[str(row["phase"])].append(obligation_id(skill_id, str(row["suffix"])))
    return {phase: tuple(values) for phase, values in grouped.items()}


def _evidence_test_files(skill_id: str) -> tuple[str, ...]:
    """Return the exact files allowed to prove this target's test mappings."""

    return tuple(
        dict.fromkeys(
            (
                *[
                    str(item)
                    for item in AUTOMATION_COMPLETION_CONTRACTS[skill_id][
                        "native_test_files"
                    ]
                ],
                "tests/test_kb_automation_skillguard.py",
            )
        )
    )


def discover_pytest_nodes(path: Path, *, relative_path: str) -> dict[str, tuple[str, ...]]:
    """Discover collectable top-level and class test functions with exact AST nodes.

    Deliberately do not recurse into arbitrary control-flow or function bodies:
    text in comments, strings, nested helpers, and ``if False`` dead branches is
    not executable pytest evidence.  Both synchronous and asynchronous tests
    are admitted.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
    discovered: dict[str, list[str]] = defaultdict(list)

    def add_function(node: ast.AST, class_names: tuple[str, ...] = ()) -> None:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return
        if not node.name.startswith("test_"):
            return
        node_id = "::".join((relative_path.replace("\\", "/"), *class_names, node.name))
        discovered[node.name].append(node_id)

    def base_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            owner = base_name(node.value)
            return f"{owner}.{node.attr}" if owner else node.attr
        return ""

    def add_class(node: ast.ClassDef, parents: tuple[str, ...] = ()) -> None:
        collectable = node.name.startswith("Test") or any(
            base_name(base).split(".")[-1] == "TestCase" for base in node.bases
        )
        if not collectable:
            return
        class_names = (*parents, node.name)
        for child in node.body:
            add_function(child, class_names)
            if isinstance(child, ast.ClassDef):
                add_class(child, class_names)

    for node in tree.body:
        add_function(node)
        if isinstance(node, ast.ClassDef):
            add_class(node)
    return {name: tuple(node_ids) for name, node_ids in discovered.items()}


def evidence_test_node_ids(skill_id: str, *, repo_root: Path) -> dict[str, str]:
    """Resolve every declared evidence marker to one unique pytest node id.

    A marker may be an unqualified test function name when that name is unique
    across the target's declared evidence files, or an exact pytest node id
    when two files intentionally use the same function name.  Missing,
    ambiguous, syntactically invalid, or non-function text fails closed.
    """

    if skill_id not in AUTOMATION_COMPLETION_CONTRACTS:
        raise KeyError(skill_id)
    repo_root = Path(repo_root)
    by_name: dict[str, list[str]] = defaultdict(list)
    all_node_ids: set[str] = set()
    problems: list[str] = []
    for relative in _evidence_test_files(skill_id):
        path = repo_root / relative
        if not path.is_file():
            problems.append(f"native_test_file_missing:{relative}")
            continue
        try:
            discovered = discover_pytest_nodes(path, relative_path=relative)
        except (OSError, SyntaxError, UnicodeError) as exc:
            problems.append(f"native_test_ast_unreadable:{relative}:{type(exc).__name__}")
            continue
        for name, node_ids in discovered.items():
            by_name[name].extend(node_ids)
            all_node_ids.update(node_ids)

    requested = tuple(
        dict.fromkeys(
            str(marker)
            for obligation in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]
            for marker in obligation.get("evidence_tests", [])
        )
    )
    resolved: dict[str, str] = {}
    for marker in requested:
        normalized = marker.replace("\\", "/")
        if "::" in normalized:
            if normalized not in all_node_ids:
                problems.append(f"obligation_test_node_missing:{marker}")
            else:
                resolved[marker] = normalized
            continue
        matches = tuple(dict.fromkeys(by_name.get(marker, ())))
        if not matches:
            problems.append(f"obligation_test_function_missing:{marker}")
        elif len(matches) != 1:
            problems.append(
                f"obligation_test_function_ambiguous:{marker}:{','.join(matches)}"
            )
        else:
            resolved[marker] = matches[0]
    if problems:
        raise ValueError(";".join(problems))
    return resolved


def validate_completion_surface(
    skill_id: str,
    *,
    repo_root: Path,
    automation_prompt: str,
    skill_text: str,
    compiled_contract: Mapping[str, Any],
    check_manifest: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Validate the sole current declared-check supervision contract.

    Khaos Brain owns its automation obligations, positive/shallow fixtures, and
    terminal receipts.  SkillGuard owns only exact declared-check execution,
    receipt reconciliation, and the single ``enforced`` closure.
    """

    spec = AUTOMATION_COMPLETION_CONTRACTS[skill_id]
    findings: list[dict[str, str]] = []

    def fail(code: str, detail: str) -> None:
        findings.append({"code": code, "detail": detail})

    for marker in (
        SKILLGUARD_COMPLETION_MARKER,
        SKILLGUARD_PARTIAL_MARKER,
        *spec["prompt_markers"],
    ):
        if str(marker).lower() not in automation_prompt.lower():
            fail("automation_prompt_marker_missing", str(marker))
    for marker in (
        SKILLGUARD_COMPLETION_MARKER,
        SKILLGUARD_PARTIAL_MARKER,
        str(spec["entrypoint_path"]),
    ):
        if marker.lower() not in skill_text.lower():
            fail("skill_completion_marker_missing", marker)
    entrypoint = Path(repo_root) / str(spec["entrypoint_path"])
    if not entrypoint.is_file():
        fail("native_entrypoint_missing", str(spec["entrypoint_path"]))

    expected = set(expected_obligation_ids(skill_id))
    actual = {
        str(row.get("obligation_id") or "")
        for row in compiled_contract.get("obligations", [])
        if isinstance(row, Mapping)
    }
    if actual != expected:
        fail(
            "compiled_obligation_set_mismatch",
            f"missing={sorted(expected - actual)};extra={sorted(actual - expected)}",
        )

    profiles = [
        row
        for row in compiled_contract.get("closure_profiles", [])
        if isinstance(row, Mapping)
    ]
    if len(profiles) != 1 or profiles[0].get("profile_id") != "enforced":
        fail("sole_enforced_closure_missing", skill_id)
        enforced: Mapping[str, Any] = {}
    else:
        enforced = profiles[0]
    enforced_ids = {
        str(item) for item in enforced.get("required_obligation_ids", [])
    }
    if enforced_ids != expected:
        fail(
            "enforced_obligation_gap",
            f"missing={sorted(expected - enforced_ids)};extra={sorted(enforced_ids - expected)}",
        )

    finalize_ids = set(obligation_ids_by_phase(skill_id).get("finalize", ()))
    expected_native_checks = {
        check_id(skill_id, "intake-runtime"),
        check_id(skill_id, "native-runtime"),
        check_id(skill_id, "terminal-runtime"),
        check_id(skill_id, "depth-positive"),
        check_id(skill_id, "depth-shallow"),
    }
    expected_checks = set(expected_native_checks)
    if finalize_ids:
        expected_native_checks.add(check_id(skill_id, "branch-terminal-runtime"))
        expected_checks.update(
            {
                check_id(skill_id, "branch-terminal-runtime"),
                check_id(skill_id, "finalization-runtime"),
            }
        )

    depth = compiled_contract.get("depth_profile", {})
    if not isinstance(depth, Mapping):
        depth = {}
        fail("declared_check_profile_missing", skill_id)
    expected_depth_fields = {
        "schema_version",
        "profile_id",
        "target_skill_id",
        "integration_mode",
        "native_owner_id",
        "native_route_ids",
        "native_check_ids",
        "skillguard_adds_domain_route",
        "enforcement_level",
        "required_closure_profiles",
        "provider_runtime",
        "claim_boundary",
    }
    if set(depth) != expected_depth_fields:
        fail(
            "declared_check_profile_fields_invalid",
            f"missing={sorted(expected_depth_fields - set(depth))};extra={sorted(set(depth) - expected_depth_fields)}",
        )
    expected_route = (
        f"route:{skill_id}:authorize" if finalize_ids else f"route:{skill_id}:run"
    )
    if (
        depth.get("schema_version") != "skillguard.depth_profile.v2"
        or depth.get("profile_id")
        != f"profile:{skill_id}:declared-check-supervision"
        or depth.get("target_skill_id") != skill_id
        or depth.get("integration_mode") != "native-integrated"
        or depth.get("native_owner_id") != skill_id
        or depth.get("native_route_ids") != [expected_route]
        or depth.get("skillguard_adds_domain_route") is not False
        or depth.get("enforcement_level") != "enforced"
        or depth.get("required_closure_profiles") != ["enforced"]
        or not str(depth.get("claim_boundary") or "")
    ):
        fail("declared_check_profile_invalid", skill_id)
    if {str(item) for item in depth.get("native_check_ids", [])} != expected_native_checks:
        fail("declared_check_inventory_invalid", skill_id)
    provider = depth.get("provider_runtime", {})
    if not isinstance(provider, Mapping) or (
        provider.get("provider_id") != SKILLGUARD_AUTOMATION_PROVIDER_ID
        or provider.get("required_runtime_contract_id")
        != SKILLGUARD_AUTOMATION_RUNTIME_CONTRACT_ID
        or tuple(provider.get("required_capability_ids", ()))
        != SKILLGUARD_AUTOMATION_RUNTIME_CAPABILITY_IDS
        or provider.get("required_enrollment_status") != "enrolled"
        or not set(provider.get("readiness_check_ids", ())).issubset(
            expected_native_checks
        )
    ):
        fail("declared_check_provider_runtime_invalid", skill_id)

    checks = {
        str(row.get("check_id") or ""): row
        for row in compiled_contract.get("checks", [])
        if isinstance(row, Mapping)
    }
    manifest_checks = {
        str(row.get("check_id") or "")
        for row in check_manifest.get("checks", [])
        if isinstance(row, Mapping)
    }
    if set(checks) != expected_checks:
        fail(
            "declared_check_set_invalid",
            f"missing={sorted(expected_checks - set(checks))};extra={sorted(set(checks) - expected_checks)}",
        )
    if manifest_checks != expected_checks:
        fail("check_manifest_set_invalid", skill_id)
    covered = {
        str(item)
        for row in checks.values()
        for item in row.get("covers_obligation_ids", [])
    }
    if not expected.issubset(covered):
        fail("check_coverage_gap", str(sorted(expected - covered)))

    phases = obligation_ids_by_phase(skill_id)
    depth_id = obligation_id(skill_id, "depth-calibration")
    for phase, kind in (
        ("intake", "intake-runtime"),
        ("execute", "native-runtime"),
        ("verify", "terminal-runtime"),
    ):
        expected_phase_ids = set(phases.get(phase, ())) - {depth_id}
        actual_phase_ids = {
            str(item)
            for item in checks.get(check_id(skill_id, kind), {}).get(
                "covers_obligation_ids", []
            )
        }
        if actual_phase_ids != expected_phase_ids:
            fail("runtime_phase_check_mismatch", f"{skill_id}:{phase}")
    for case_kind in ("positive", "shallow"):
        row = checks.get(check_id(skill_id, f"depth-{case_kind}"), {})
        if (
            set(row.get("covers_obligation_ids", [])) != {depth_id}
            or row.get("native_route_id") != expected_route
            or row.get("evidence_domain_id")
            != f"target:{skill_id}:fixture-calibration"
            or row.get("command") != "python"
            or row.get("args")
            != [
                "scripts/check_kb_automation_run_receipt.py",
                "--skill",
                skill_id,
                "--phase",
                "all",
                "--fixture",
                case_kind,
                "--json",
            ]
        ):
            fail("target_fixture_check_invalid", f"{skill_id}:{case_kind}")

    if finalize_ids:
        if compiled_contract.get("route_branch_closure_required") is not True:
            fail("update_route_branch_closure_missing", skill_id)
        rows = [
            row
            for row in enforced.get("route_branch_requirements", [])
            if isinstance(row, Mapping)
        ]
        observed = {
            (str(row.get("native_route_id") or ""), str(branch))
            for row in rows
            for branch in row.get("branch_ids", [])
        }
        expected_pairs = {
            (expected_route, branch)
            for branch in (
                "no-update",
                "waiting-for-user",
                "ui-running",
                "prepared-update",
            )
        }
        if observed != expected_pairs:
            fail("update_route_branch_contract_invalid", skill_id)
        noop_rows = [
            row
            for row in rows
            if set(row.get("branch_ids", []))
            == {"no-update", "waiting-for-user", "ui-running"}
        ]
        expected_rule = [
            {
                "obligation_id": next(iter(finalize_ids)),
                "allowed_disposition": "not_applicable",
                "verifier_check_id": check_id(
                    skill_id, "branch-terminal-runtime"
                ),
            }
        ]
        if len(noop_rows) != 1 or noop_rows[0].get("applicability_rules") != expected_rule:
            fail("update_noop_applicability_contract_invalid", skill_id)
        if check_id(skill_id, "finalization-runtime") in expected_native_checks:
            fail("conditional_finalization_claimed_as_required_declared_check", skill_id)

    artifact_index = {
        str(row.get("artifact_id") or ""): row
        for row in compiled_contract.get("artifacts", [])
        if isinstance(row, Mapping)
    }
    step_index = {
        str(row.get("step_id") or ""): row
        for row in compiled_contract.get("steps", [])
        if isinstance(row, Mapping)
    }
    native_artifact_id = native_receipt_artifact_id(skill_id)
    native_artifact = artifact_index.get(native_artifact_id, {})
    native_obligation_ids = {
        obligation_id(skill_id, str(row["suffix"]))
        for row in spec["obligations"]
        if str(row.get("evidence_source") or "native-receipt")
        == "native-receipt"
        and str(row.get("suffix") or "") != "depth-calibration"
    }
    native_validator_ids = {
        check_id(skill_id, kind)
        for kind in ("intake-runtime", "native-runtime", "terminal-runtime")
    }
    if finalize_ids:
        native_validator_ids.add(check_id(skill_id, "branch-terminal-runtime"))
    execute_binding = step_index.get(step_id(skill_id, "execute"), {}).get(
        "binding", {}
    )
    if not isinstance(execute_binding, Mapping):
        execute_binding = {}
    if (
        set(execute_binding.get("output_artifact_ids", []))
        != {native_artifact_id}
        or native_artifact.get("kind") != "native_output"
        or native_artifact.get("producer_step_id")
        != step_id(skill_id, "execute")
        or set(native_artifact.get("validator_check_ids", []))
        != native_validator_ids
        or set(native_artifact.get("covers_obligation_ids", []))
        != native_obligation_ids
    ):
        fail("native_receipt_artifact_binding_invalid", native_artifact_id)

    if finalize_ids:
        final_artifact_id = update_finalization_artifact_id()
        final_artifact = artifact_index.get(final_artifact_id, {})
        finalize_binding = step_index.get(step_id(skill_id, "finalize"), {}).get(
            "binding", {}
        )
        if not isinstance(finalize_binding, Mapping):
            finalize_binding = {}
        if (
            set(finalize_binding.get("output_artifact_ids", []))
            != {final_artifact_id}
            or final_artifact.get("kind") != "native_output"
            or final_artifact.get("producer_step_id")
            != step_id(skill_id, "finalize")
            or set(final_artifact.get("validator_check_ids", []))
            != {check_id(skill_id, "finalization-runtime")}
            or set(final_artifact.get("covers_obligation_ids", []))
            != finalize_ids
        ):
            fail("finalization_receipt_artifact_binding_invalid", final_artifact_id)

    try:
        resolved_test_nodes = evidence_test_node_ids(skill_id, repo_root=repo_root)
    except (KeyError, ValueError) as exc:
        fail("obligation_test_evidence_invalid", str(exc))
    else:
        declared_markers = {
            str(marker)
            for obligation in spec["obligations"]
            for marker in obligation.get("evidence_tests", [])
        }
        if set(resolved_test_nodes) != declared_markers:
            fail("obligation_test_evidence_set_mismatch", skill_id)
    return findings
