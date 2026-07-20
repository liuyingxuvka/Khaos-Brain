"""Execute the Khaos Brain consumer-independence FlowGuard model."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
FLOWGUARD_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

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
    review_scenarios,
    run_model_first_checks,
)

import kb_convergence_upgrade_model as model  # noqa: E402
from kb_skill_contract_model_common import review_current_model  # noqa: E402
from local_kb.automation_contracts import evidence_test_node_ids  # noqa: E402
from local_kb.install import maintenance_skill_source_dir  # noqa: E402
from local_kb.transactional_install import consumer_skill_manifest  # noqa: E402


MODEL_PATH = FLOWGUARD_ROOT / "kb_convergence_upgrade_model.py"
EVIDENCE_PATH = FLOWGUARD_ROOT / "evidence" / "kb_convergence_suite.json"
CHILD_MODEL_PATHS = {
    "kb-sleep-maintenance": FLOWGUARD_ROOT
    / "kb_sleep_skill_contract_model.py",
    "kb-dream-pass": FLOWGUARD_ROOT / "kb_dream_skill_contract_model.py",
    "kb-organization-contribute": FLOWGUARD_ROOT
    / "kb_org_contribute_skill_contract_model.py",
    "kb-organization-maintenance": FLOWGUARD_ROOT
    / "kb_org_maintenance_skill_contract_model.py",
    "khaos-brain-update": FLOWGUARD_ROOT
    / "khaos_brain_update_skill_contract_model.py",
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _projection_digest() -> str:
    paths = (
        MODEL_PATH,
        Path(__file__),
        FLOWGUARD_ROOT / "kb_skill_contract_model_common.py",
        REPO_ROOT / "local_kb" / "automation_contracts.py",
        REPO_ROOT / "local_kb" / "automation_runtime.py",
        REPO_ROOT / "local_kb" / "transactional_install.py",
        REPO_ROOT / "local_kb" / "install.py",
        REPO_ROOT / "scripts" / "run_kb_automation.py",
        REPO_ROOT / "scripts" / "run_khaos_brain_manual_update.py",
        REPO_ROOT / "scripts" / "check_consumer_install_assurance.py",
        REPO_ROOT / "tests" / "test_kb_automation_skillguard.py",
        *CHILD_MODEL_PATHS.values(),
    )
    rows = [
        f"{path.relative_to(REPO_ROOT).as_posix()}={_digest(path)}"
        for path in paths
    ]
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _scenarios() -> tuple[Scenario, ...]:
    sleep = "kb-sleep-maintenance"
    return (
        Scenario(
            "clean_projection_then_native_completion",
            "A consumer installs clean bytes and closes through its target-native receipt.",
            model.ConsumerState(),
            (
                model.ConsumerInput("install_projection", skill_id=sleep),
                model.ConsumerInput(
                    "native_complete",
                    skill_id=sleep,
                    obligation_ids=model.AUTOMATION_TARGET_OBLIGATIONS[sleep],
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "clean_consumer_projection_installed",
                    "target_native_terminal_completed",
                )
            ),
        ),
        Scenario(
            "author_control_is_rejected_from_consumer",
            "A projection containing author control cannot be installed.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "install_projection",
                    skill_id=sleep,
                    contains_author_control=True,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("author_control_rejected",),
                forbidden_trace_labels=("clean_consumer_projection_installed",),
            ),
        ),
        Scenario(
            "partial_native_receipt_is_blocked",
            "A consumer receipt missing target obligations cannot complete.",
            model.ConsumerState(clean_installed_skills=(sleep,)),
            (
                model.ConsumerInput(
                    "native_complete",
                    skill_id=sleep,
                    obligation_ids=(),
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("native_completion_blocked",),
                forbidden_trace_labels=("target_native_terminal_completed",),
            ),
        ),
        Scenario(
            "manual_update_closes_natively",
            "The explicit manual update restores state, checks health, and marks CURRENT itself.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "manual_update",
                    explicit_user_request=True,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "manual_update_current_and_restored",
                )
            ),
        ),
        Scenario(
            "manual_update_failure_stays_paused",
            "A failed restoration keeps every surviving automation paused.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "manual_update",
                    explicit_user_request=True,
                    restoration_ok=False,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "manual_update_failed_survivors_paused",
                )
            ),
        ),
        Scenario(
            "operator_activation_separates_scheduled_and_manual_skills",
            "The complete five-skill inventory activates only the four scheduled members.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "operator_activate",
                    maintained_skill_ids=model.AUTOMATION_TARGET_IDS,
                    scheduled_skill_ids=model.SCHEDULED_SKILL_IDS,
                    manual_only_skill_ids=model.MANUAL_ONLY_SKILL_IDS,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "scheduled_automations_activated_manual_update_unscheduled",
                )
            ),
        ),
        Scenario(
            "ambiguous_activation_inventory_is_blocked",
            "Treating all five maintained skills as scheduled is rejected.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "operator_activate",
                    maintained_skill_ids=model.AUTOMATION_TARGET_IDS,
                    scheduled_skill_ids=model.AUTOMATION_TARGET_IDS,
                    manual_only_skill_ids=(),
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("activation_inventory_blocked",),
                forbidden_trace_labels=(
                    "scheduled_automations_activated_manual_update_unscheduled",
                ),
            ),
        ),
        Scenario(
            "operator_activation_exception_repauses_every_survivor",
            "A failed activation check cannot leave an unreceipted ACTIVE automation.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "operator_activate",
                    maintained_skill_ids=model.AUTOMATION_TARGET_IDS,
                    scheduled_skill_ids=model.SCHEDULED_SKILL_IDS,
                    manual_only_skill_ids=model.MANUAL_ONLY_SKILL_IDS,
                    activation_checks_ok=False,
                    activation_transaction_completed=False,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "activation_failed_survivors_paused",
                ),
                forbidden_trace_labels=(
                    "scheduled_automations_activated_manual_update_unscheduled",
                ),
            ),
        ),
        Scenario(
            "upgrade_attempt_currentness_is_pointer_only",
            "Currentness accepts one bounded HEAD/current authority without history scanning.",
            model.ConsumerState(),
            (model.ConsumerInput("check_upgrade_attempt_current"),),
            ScenarioExpectation(
                required_trace_labels=("upgrade_attempt_current_authority",)
            ),
        ),
        Scenario(
            "upgrade_attempt_history_fallback_is_blocked",
            "Attempt-history scanning and manifest fallback cannot satisfy currentness.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "check_upgrade_attempt_current",
                    attempt_history_scan_count=1,
                    attempt_manifest_fallback_used=True,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "upgrade_attempt_current_authority_blocked",
                ),
                forbidden_trace_labels=("upgrade_attempt_current_authority",),
            ),
        ),
        Scenario(
            "installation_currentness_is_read_only",
            "A normal installation check reads current authority without launching an owner.",
            model.ConsumerState(),
            (model.ConsumerInput("audit_install_currentness"),),
            ScenarioExpectation(
                required_trace_labels=("installation_currentness_read_only",)
            ),
        ),
        Scenario(
            "installation_currentness_owner_execution_is_blocked",
            "A currentness path that launches even one validation owner is rejected.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "audit_install_currentness",
                    currentness_owner_execution_count=1,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "installation_currentness_executed_owner_blocked",
                ),
                forbidden_trace_labels=("installation_currentness_read_only",),
            ),
        ),
        Scenario(
            "toolchain_identity_ignores_absolute_snapshot_path",
            "A frozen copy and live package remain one toolchain when portable content matches.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "audit_toolchain_receipt",
                    toolchain_content_matches=True,
                    toolchain_location_differs=True,
                    assurance_receipt_bounded=True,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "content_bound_toolchain_receipt_current",
                )
            ),
        ),
        Scenario(
            "failed_upgrade_restores_attempt_bound_automation_intent",
            "A safety-paused runtime restores the pre-pause ACTIVE intent from the failed attempt.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "restore_automation_intent",
                    automation_runtime_status="PAUSED",
                    automation_user_paused=False,
                    recoverable_upgrade_attempt=True,
                    recovery_snapshot_current=True,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("system_pause_reactivated",)
            ),
        ),
        Scenario(
            "missing_recovery_snapshot_blocks_direct_repair",
            "A recoverable attempt without its original state snapshot cannot infer intent.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "restore_automation_intent",
                    automation_runtime_status="PAUSED",
                    automation_user_paused=False,
                    recoverable_upgrade_attempt=True,
                    recovery_snapshot_current=False,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "missing_recovery_snapshot_direct_repair_blocked",
                ),
                forbidden_trace_labels=("system_pause_reactivated",),
            ),
        ),
        Scenario(
            "one_changed_component_executes_one_owner",
            "A retrieval-only input change reuses every unrelated owner.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "plan_affected_assurance",
                    changed_component_ids=("retrieval-data",),
                    affected_owner_ids=("retrieval-quality",),
                    reusable_owner_ids=(
                        "consumer-projections",
                        "current-runtime",
                        "flow-model",
                        "reasoning-runtime",
                    ),
                    executed_owner_ids=("retrieval-quality",),
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("affected_assurance_plan_stable",)
            ),
        ),
        Scenario(
            "final_readiness_reuses_every_unaffected_owner",
            "A readiness-planner fix executes only full regression while every other declared owner is reused.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "plan_affected_assurance",
                    changed_component_ids=("readiness-planner",),
                    declared_owner_ids=model.FINAL_READINESS_OWNER_IDS,
                    affected_owner_ids=("full-regression",),
                    reusable_owner_ids=tuple(
                        owner
                        for owner in model.FINAL_READINESS_OWNER_IDS
                        if owner != "full-regression"
                    ),
                    executed_owner_ids=("full-regression",),
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("affected_assurance_plan_stable",)
            ),
        ),
        Scenario(
            "missing_final_readiness_owner_blocks",
            "A declared readiness owner without an affected execution or reusable receipt keeps the plan blocked.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "plan_affected_assurance",
                    changed_component_ids=("readiness-planner",),
                    declared_owner_ids=model.FINAL_READINESS_OWNER_IDS,
                    affected_owner_ids=("full-regression",),
                    reusable_owner_ids=tuple(
                        owner
                        for owner in model.FINAL_READINESS_OWNER_IDS
                        if owner not in {"full-regression", "retrieval-quality"}
                    ),
                    executed_owner_ids=("full-regression",),
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("affected_assurance_plan_blocked",),
                forbidden_trace_labels=("affected_assurance_plan_stable",),
            ),
        ),
        Scenario(
            "unmapped_component_blocks_without_run_all",
            "An unmapped component cannot select a broad validation fallback.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "plan_affected_assurance",
                    changed_component_ids=("unmapped",),
                    unknown_component_ids=("unmapped",),
                    executed_owner_ids=(
                        "consumer-projections",
                        "current-runtime",
                        "flow-model",
                        "reasoning-runtime",
                        "retrieval-quality",
                    ),
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("affected_assurance_plan_blocked",),
                forbidden_trace_labels=("affected_assurance_plan_stable",),
            ),
        ),
        Scenario(
            "late_retrieval_input_replans_retrieval_only",
            "Data admitted during assurance invalidates only its declared owner.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "replan_late_assurance_inputs",
                    late_affected_owner_ids=("retrieval-quality",),
                    late_executed_owner_ids=("retrieval-quality",),
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("late_inputs_affected_only_replanned",)
            ),
        ),
        Scenario(
            "late_input_run_all_is_blocked",
            "Late input drift cannot trigger an unconditional aggregate rerun.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "replan_late_assurance_inputs",
                    late_affected_owner_ids=("retrieval-quality",),
                    late_executed_owner_ids=(
                        "consumer-projections",
                        "current-runtime",
                        "flow-model",
                        "reasoning-runtime",
                        "retrieval-quality",
                    ),
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("late_inputs_run_all_blocked",),
                forbidden_trace_labels=("late_inputs_affected_only_replanned",),
            ),
        ),
        Scenario(
            "timeout_cleanup_invalidates_evidence",
            "A timed-out owner remains invalid after its descendants reach zero.",
            model.ConsumerState(),
            (model.ConsumerInput("validation_owner_timeout"),),
            ScenarioExpectation(
                required_trace_labels=(
                    "timeout_descendants_zero_evidence_invalid",
                )
            ),
        ),
        Scenario(
            "release_tag_consumes_exact_main_receipt",
            "A release tag verifies main evidence and launches no repository suite.",
            model.ConsumerState(),
            (model.ConsumerInput("verify_release_tag"),),
            ScenarioExpectation(
                required_trace_labels=("release_tag_consumed_main_receipt",)
            ),
        ),
        Scenario(
            "release_tag_test_rerun_is_blocked",
            "A tag lane that executes tests is not a receipt-only release gate.",
            model.ConsumerState(),
            (
                model.ConsumerInput(
                    "verify_release_tag",
                    tag_suite_execution_count=1,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("release_tag_receipt_gate_blocked",),
                forbidden_trace_labels=(
                    "release_tag_consumed_main_receipt",
                ),
            ),
        ),
        Scenario(
            "third_party_overlap_is_outside_guarantee",
            "Unknown third-party overlap does not create cross-skill proof sharing.",
            model.ConsumerState(),
            (model.ConsumerInput("third_party_overlap"),),
            ScenarioExpectation(
                required_trace_labels=(
                    "third_party_overlap_outside_guarantee",
                )
            ),
        ),
    )


def _model_report() -> dict[str, Any]:
    risk_intent = RiskIntent(
        failure_modes=(
            "author control installed with a consumer skill",
            "partial native receipt accepted",
            "manual update marks CURRENT before restoration",
            "cross-skill evidence reuse",
            "manual-only update skill treated as a scheduled automation",
            "upgrade currentness scans attempt history or falls back to manifest state",
            "installation currentness launches a validation owner",
            "one changed component triggers every assurance owner",
            "late data admission triggers an unconditional second campaign",
            "release tag reruns repository validation",
        ),
        protected_error_classes=(
            "consumer_author_control_leak",
            "shallow_native_completion",
            "premature_update_current",
            "shared_test_evidence",
            "ambiguous_activation_inventory",
            "unbounded_attempt_currentness",
            "currentness_execution",
            "run_all_invalidation",
            "late_input_run_all",
            "tag_validation_duplication",
        ),
        protected_harms=(
            "ordinary projects gain hidden maintenance control",
            "a skill cannot work independently after distribution",
        ),
        must_model_state=tuple(model.ConsumerState.__dataclass_fields__),
        must_model_side_effects=(
            "consumer projection activation",
            "native terminal completion",
            "manual update restoration and CURRENT",
            "four-automation activation from a five-skill classified inventory",
            "bounded HEAD-to-current attempt lookup",
            "read-only installation currentness",
            "affected-owner assurance planning and exact receipt reuse",
            "receipt-only release-tag verification",
        ),
        completion_evidence=(
            "clean consumer projection",
            "exact target obligation inventory",
            "current target-native receipt",
            "exact scheduled/manual-only skill inventory",
            "bounded hash-bound current attempt authority",
            "zero currentness owner executions",
            "exact changed-component to affected-owner plan",
            "exact successful main validation receipt",
        ),
        hard_invariants=tuple(item.name for item in model.CONSUMER_INVARIANTS),
        known_bad_cases=(
            "project_author_control_write",
            "cross_unit_shared_test_evidence",
        ),
        adversarial_inputs=(
            "consumer projection containing author-control files",
            "partial or stale native receipt",
            "manual update restoration failure",
            "five maintained skills incorrectly treated as five scheduled tasks",
            "missing current pointer with a readable historical attempt",
            "unmapped assurance component",
            "late retrieval input with broad rerun",
            "tag event with a repository test execution",
        ),
        blindspots=(
            "third-party skills on other machines are outside the guarantee",
        ),
        template_no_match_reason=(
            "The existing project-specific consumer boundary model is smaller "
            "and more exact than a generic template."
        ),
    )
    plan = FlowGuardCheckPlan(
        workflow=model.consumer_independence_workflow(),
        initial_states=(model.ConsumerState(),),
        external_inputs=model.CONSUMER_INPUTS,
        invariants=model.CONSUMER_INVARIANTS,
        max_sequence_length=2,
        required_labels=(
            "clean_consumer_projection_installed",
            "author_control_rejected",
            "native_completion_blocked",
            "manual_update_current_and_restored",
            "manual_update_failed_survivors_paused",
            "scheduled_automations_activated_manual_update_unscheduled",
            "activation_inventory_blocked",
            "upgrade_attempt_current_authority",
            "upgrade_attempt_current_authority_blocked",
            "installation_currentness_read_only",
            "installation_currentness_executed_owner_blocked",
            "affected_assurance_plan_stable",
            "affected_assurance_plan_blocked",
            "late_inputs_affected_only_replanned",
            "late_inputs_run_all_blocked",
            "timeout_descendants_zero_evidence_invalid",
            "release_tag_consumed_main_receipt",
            "release_tag_receipt_gate_blocked",
        ),
        risk_profile=RiskProfile(
            modeled_boundary=(
                "author maintenance to clean consumer distribution and target-native completion"
            ),
            risk_classes=("module_boundary", "conformance", "side_effect"),
            risk_intent=risk_intent,
        ),
        template_reuse_review=TemplateReuseReview(
            no_match_reason=risk_intent.template_no_match_reason,
            searched_layers=("project-local",),
        ),
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=risk_intent.protected_error_classes,
            modeled_state=risk_intent.must_model_state,
            modeled_side_effects=risk_intent.must_model_side_effects,
            completion_evidence=risk_intent.completion_evidence,
            known_bad_cases=risk_intent.known_bad_cases,
        ),
        known_bad_proofs=(
            KnownBadProof(
                "project_author_control_write",
                protected_error_class="consumer_author_control_leak",
                method="invalid_initial_state_invariant",
                observed_status="failed",
                observed_failure="consumer_has_no_author_control",
                evidence_id="kb-consumer-boundary:author-control-write",
            ),
            KnownBadProof(
                "cross_unit_shared_test_evidence",
                protected_error_class="shared_test_evidence",
                method="invalid_initial_state_invariant",
                observed_status="failed",
                observed_failure="maintenance_units_do_not_share_test_evidence",
                evidence_id="kb-consumer-boundary:shared-evidence",
            ),
        ),
        progress_config=_progress_config(),
        metadata={
            "model_path": str(MODEL_PATH.relative_to(REPO_ROOT)),
            "projection_digest": _projection_digest(),
        },
    )
    summary = run_model_first_checks(plan)
    return summary.to_dict()


def _progress_config() -> ProgressCheckConfig:
    skill_id = "kb-sleep-maintenance"
    workflow = model.consumer_independence_workflow()

    def transition(state: model.ConsumerState):
        if skill_id not in state.clean_installed_skills:
            event = model.ConsumerInput(
                "install_projection", skill_id=skill_id
            )
        elif skill_id not in state.completed_skills:
            event = model.ConsumerInput(
                "native_complete",
                skill_id=skill_id,
                obligation_ids=model.AUTOMATION_TARGET_OBLIGATIONS[skill_id],
            )
        else:
            return ()
        run = workflow.execute(state, event)
        return tuple(
            GraphEdge(
                old_state=state,
                new_state=path.state,
                label=(
                    path.trace.steps[-1].label
                    if path.trace.steps
                    else event.kind
                ),
            )
            for path in run.completed_paths
        )

    return ProgressCheckConfig(
        initial_states=(model.ConsumerState(),),
        transition_fn=transition,
        is_terminal=lambda state: skill_id in state.completed_skills,
        is_success=lambda state: skill_id in state.completed_skills,
        ranking_fn=lambda state: (
            0
            if skill_id in state.completed_skills
            else 1
            if skill_id in state.clean_installed_skills
            else 2
        ),
        bounded_eventually=(
            BoundedEventuallyProperty(
                "clean_projection_reaches_native_terminal",
                trigger=lambda state: True,
                target=lambda state: skill_id in state.completed_skills,
                max_steps=2,
            ),
        ),
        max_states=8,
        max_depth=3,
    )


def _scenario_report() -> dict[str, Any]:
    return review_scenarios(
        _scenarios(),
        default_workflow=model.consumer_independence_workflow(),
        default_invariants=model.CONSUMER_INVARIANTS,
    ).to_dict()


def _lifecycle_scenarios() -> tuple[Scenario, ...]:
    workflow = model.lifecycle_convergence_workflow()
    stage = model.LifecycleInput("stage_lifecycle_batch", planned_event_count=500)
    commit = model.LifecycleInput(
        "commit_lifecycle_batch",
        planned_event_count=500,
        created_event_count=500,
    )
    return (
        Scenario(
            "candidate_events_commit_in_one_bounded_batch",
            "Candidate and observation lifecycle events share one atomic batch.",
            model.LifecycleState(),
            (stage, commit),
            ScenarioExpectation(
                required_trace_labels=(
                    "lifecycle_batch_staged",
                    "lifecycle_batch_committed_once",
                )
            ),
            workflow=workflow,
            invariants=model.LIFECYCLE_INVARIANTS,
        ),
        Scenario(
            "timeout_after_commit_stays_fail_closed",
            "A native timeout after durable lifecycle mutation leaves the index invalid.",
            model.LifecycleState(),
            (
                stage,
                commit,
                model.LifecycleInput(
                    "native_timeout_after_lifecycle_commit",
                    cleanup_confirmed=True,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "lifecycle_batch_committed_once",
                    "timeout_visible_index_remains_invalid",
                ),
                forbidden_trace_labels=(
                    "active_index_rebuilt_and_watermark_committed",
                ),
            ),
            workflow=workflow,
            invariants=model.LIFECYCLE_INVARIANTS,
        ),
        Scenario(
            "next_sleep_recovers_exact_invalidated_state",
            "The next authorized Sleep rebuilds and commits one final watermark.",
            model.LifecycleState(),
            (
                stage,
                commit,
                model.LifecycleInput(
                    "native_timeout_after_lifecycle_commit",
                    cleanup_confirmed=True,
                ),
                model.LifecycleInput("next_sleep_recovery"),
            ),
            ScenarioExpectation(
                required_trace_labels=(
                    "timeout_visible_index_remains_invalid",
                    "active_index_rebuilt_and_watermark_committed",
                )
            ),
            workflow=workflow,
            invariants=model.LIFECYCLE_INVARIANTS,
        ),
        Scenario(
            "stale_planning_snapshot_writes_nothing",
            "A batch planned from stale lifecycle state fails before invalidation.",
            model.LifecycleState(),
            (
                model.LifecycleInput(
                    "commit_lifecycle_batch",
                    planned_event_count=1,
                    snapshot_current=False,
                ),
            ),
            ScenarioExpectation(
                required_trace_labels=("stale_lifecycle_snapshot_blocked",),
                forbidden_trace_labels=("lifecycle_batch_committed_once",),
            ),
            workflow=workflow,
            invariants=model.LIFECYCLE_INVARIANTS,
        ),
        Scenario(
            "unauthorized_index_publisher_is_rejected",
            "A retrieval caller cannot publish or clear the active-index marker.",
            model.LifecycleState(
                active_index_state="invalidated_pending_rebuild",
                invalidation_token="sleep-cycle-token",
                authority_stamp_published=False,
                watermark_committed=False,
                target_terminal_receipt_present=False,
            ),
            (
                model.LifecycleInput(
                    "publish_active_index",
                    publisher_id="local_kb.search.search_with_receipt",
                ),
            ),
            ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=(
                    "active_index_publication_has_one_authorized_owner",
                ),
                required_trace_labels=("active_index_publication_blocked",),
                forbidden_trace_labels=(
                    "active_index_rebuilt_and_watermark_committed",
                ),
            ),
            workflow=workflow,
            invariants=model.LIFECYCLE_INVARIANTS,
        ),
    )


def _lifecycle_model_report() -> dict[str, Any]:
    risk_intent = RiskIntent(
        failure_modes=(
            "per-candidate full lifecycle replay",
            "timeout after durable invalidation before index publication",
            "unauthorized active-index publication",
            "stale planning snapshot committed",
        ),
        protected_error_classes=(
            "unbounded_lifecycle_replay",
            "stale_index_success",
            "unauthorized_index_publisher",
            "lifecycle_snapshot_drift",
        ),
        protected_harms=(
            "Sleep exceeds its native timeout",
            "retrieval consumes an invalidated index",
        ),
        must_model_state=tuple(model.LifecycleState.__dataclass_fields__),
        must_model_side_effects=(
            "atomic lifecycle batch commit",
            "durable active-index invalidation",
            "validated active-index publication",
            "Sleep watermark commit",
        ),
        completion_evidence=(
            "two replay passes per lifecycle batch",
            "exact invalidation token",
            "authorized publisher identity",
            "current authority stamp and watermark",
        ),
        hard_invariants=tuple(item.name for item in model.LIFECYCLE_INVARIANTS),
        known_bad_cases=("unauthorized_index_publisher",),
        adversarial_inputs=(
            "250 new candidates",
            "stale lifecycle snapshot",
            "native timeout after lifecycle commit",
            "marker-token race",
        ),
        blindspots=("physical storage throughput remains production evidence",),
        template_no_match_reason=(
            "The existing LifecycleConvergenceBlock is the exact product owner."
        ),
    )
    plan = FlowGuardCheckPlan(
        workflow=model.lifecycle_convergence_workflow(),
        initial_states=(model.LifecycleState(),),
        external_inputs=model.LIFECYCLE_INPUTS,
        invariants=model.LIFECYCLE_INVARIANTS,
        max_sequence_length=4,
        required_labels=(
            "lifecycle_batch_staged",
            "lifecycle_batch_committed_once",
            "stale_lifecycle_snapshot_blocked",
            "timeout_visible_index_remains_invalid",
            "active_index_publication_blocked",
            "active_index_rebuilt_and_watermark_committed",
        ),
        scenarios=_lifecycle_scenarios(),
        risk_profile=RiskProfile(
            modeled_boundary=(
                "Sleep lifecycle staging through active-index/watermark closure"
            ),
            risk_classes=("conformance", "performance", "side_effect"),
            risk_intent=risk_intent,
        ),
        template_reuse_review=TemplateReuseReview(
            no_match_reason=risk_intent.template_no_match_reason,
            searched_layers=("project-local",),
        ),
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=risk_intent.protected_error_classes,
            modeled_state=risk_intent.must_model_state,
            modeled_side_effects=risk_intent.must_model_side_effects,
            completion_evidence=risk_intent.completion_evidence,
            known_bad_cases=risk_intent.known_bad_cases,
        ),
        known_bad_proofs=(
            KnownBadProof(
                "unauthorized_index_publisher",
                protected_error_class="unauthorized_index_publisher",
                method="scenario_expected_invariant_violation",
                observed_status="failed",
                observed_failure=(
                    "active_index_publication_has_one_authorized_owner"
                ),
                evidence_id=(
                    "sleep-timeout:unauthorized-active-index-publication"
                ),
            ),
        ),
        metadata={
            "observed_timeout_run_id": (
                "native-kb-sleep-maintenance-20260720T100219848122Z-58af370c"
            ),
            "model_miss_types": ("state_too_coarse", "evidence_overclaimed"),
        },
    )
    return run_model_first_checks(plan).to_dict()


def _lifecycle_scenario_report() -> dict[str, Any]:
    return review_scenarios(
        _lifecycle_scenarios(),
        default_workflow=model.lifecycle_convergence_workflow(),
        default_invariants=model.LIFECYCLE_INVARIANTS,
    ).to_dict()


def _contract_report() -> dict[str, Any]:
    skills: dict[str, dict[str, Any]] = {}
    evidence_owners: dict[str, str] = {}
    overlaps: list[dict[str, str]] = []
    for skill_id, path in CHILD_MODEL_PATHS.items():
        namespace = runpy.run_path(str(path))
        child = namespace["export_contract_model"]()
        review = review_current_model(child)
        source_root = maintenance_skill_source_dir(REPO_ROOT, skill_id)
        projection = consumer_skill_manifest(source_root)
        nodes = evidence_test_node_ids(skill_id, repo_root=REPO_ROOT)
        for node_id in nodes.values():
            prior = evidence_owners.get(node_id)
            if prior is not None:
                overlaps.append(
                    {
                        "node_id": node_id,
                        "first_unit": prior,
                        "second_unit": skill_id,
                    }
                )
            evidence_owners[node_id] = skill_id
        skills[skill_id] = {
            "ok": review["ok"],
            "model_review": review,
            "consumer_projection_digest": projection["digest"],
            "consumer_file_count": projection["file_count"],
            "test_evidence_count": len(nodes),
        }
    return {
        "ok": all(row["ok"] for row in skills.values()) and not overlaps,
        "skills": skills,
        "cross_unit_test_evidence_overlaps": overlaps,
    }


def _report_ok(report: dict[str, Any]) -> bool:
    sections = report.get("sections")
    if not isinstance(sections, list):
        return False
    return all(
        isinstance(row, dict)
        and row.get("status")
        not in {"failed", "blocked", "error", "unexpected_violation"}
        for row in sections
    )


def build_report() -> dict[str, Any]:
    model_report = _model_report()
    scenarios = _scenario_report()
    lifecycle_model = _lifecycle_model_report()
    lifecycle_scenarios = _lifecycle_scenario_report()
    contracts = _contract_report()
    scenario_ok = scenarios.get("ok") is True
    report = {
        "schema_version": "khaos-brain.flowguard-convergence.v2",
        "ok": (
            _report_ok(model_report)
            and scenario_ok
            and _report_ok(lifecycle_model)
            and lifecycle_scenarios.get("ok") is True
            and contracts["ok"]
        ),
        "projection_digest": _projection_digest(),
        "model": model_report,
        "scenarios": scenarios,
        "lifecycle_model": lifecycle_model,
        "lifecycle_scenarios": lifecycle_scenarios,
        "contracts": contracts,
        "claim_boundary": (
            "Executable FlowGuard evidence for clean consumer distribution, "
            "target-native completion, independent test ownership, and direct "
            "manual-update closure, exact scheduled/manual-only activation inventory, "
            "and bounded pointer-only upgrade currentness. It does not guarantee "
            "third-party skill compatibility or current production recovery."
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write-evidence", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if not args.no_write_evidence:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("FlowGuard consumer independence:", "PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
