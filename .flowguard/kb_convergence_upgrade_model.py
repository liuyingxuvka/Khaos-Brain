"""FlowGuard model for independent Khaos Brain skill consumers.

The model separates two worlds:

* author maintenance may certify one skill at a time;
* consumer installation and ordinary execution never load that author control.

Every transition implements ``Input x State -> Set(Output x State)``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow

from local_kb.automation_contracts import (
    AUTOMATION_COMPLETION_CONTRACTS,
    check_id,
    expected_obligation_ids,
)


UPDATE_SKILL_ID = "khaos-brain-update"
AUTOMATION_TARGET_OBLIGATIONS = {
    skill_id: expected_obligation_ids(skill_id)
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS
}
AUTOMATION_TARGET_IDS = tuple(AUTOMATION_TARGET_OBLIGATIONS)
SCHEDULED_SKILL_IDS = tuple(
    skill_id for skill_id in AUTOMATION_TARGET_IDS if skill_id != UPDATE_SKILL_ID
)
MANUAL_ONLY_SKILL_IDS = (UPDATE_SKILL_ID,)
AUTOMATION_CHECK_KINDS = (
    "intake-runtime",
    "native-runtime",
    "terminal-runtime",
    "depth-positive",
    "depth-shallow",
)
FINAL_READINESS_OWNER_IDS = (
    "flowguard-models",
    "flowguard-meshes",
    "logicguard-authority-cutover-model",
    "logicguard-field-lifecycle",
    "logicguard-model-mesh",
    "logicguard-code-structure",
    "logicguard-model-test-contract",
    "logicguard-test-mesh",
    "logicguard-runtime-model-miss",
    "logicguard-runtime",
    "logicguard-openspec",
    "author-contract-assurance",
    "retired-architect-absence",
    "current-runtime-only",
    "retrieval-quality",
    "full-regression",
    "install-health",
)


def automation_manifest_check_ids(skill_id: str) -> tuple[str, ...]:
    return tuple(check_id(skill_id, kind) for kind in AUTOMATION_CHECK_KINDS)


@dataclass(frozen=True)
class ConsumerInput:
    kind: str
    skill_id: str = ""
    obligation_ids: tuple[str, ...] = ()
    contains_author_control: bool = False
    receipt_current: bool = True
    explicit_user_request: bool = False
    update_available: bool = True
    native_gates_ok: bool = True
    restoration_ok: bool = True
    final_health_ok: bool = True
    mark_current_ok: bool = True
    maintained_skill_ids: tuple[str, ...] = ()
    scheduled_skill_ids: tuple[str, ...] = ()
    manual_only_skill_ids: tuple[str, ...] = ()
    activation_checks_ok: bool = True
    activation_transaction_completed: bool = True
    attempt_head_current: bool = True
    attempt_projection_bounded: bool = True
    attempt_manifest_binding_current: bool = True
    attempt_history_scan_count: int = 0
    attempt_manifest_fallback_used: bool = False
    currentness_read_only: bool = True
    currentness_owner_execution_count: int = 0
    toolchain_content_matches: bool = True
    toolchain_location_differs: bool = False
    assurance_receipt_bounded: bool = True
    automation_runtime_status: str = "ACTIVE"
    automation_user_paused: bool = False
    recoverable_upgrade_attempt: bool = False
    recovery_snapshot_current: bool = True
    changed_component_ids: tuple[str, ...] = ()
    declared_owner_ids: tuple[str, ...] = ()
    affected_owner_ids: tuple[str, ...] = ()
    reusable_owner_ids: tuple[str, ...] = ()
    executed_owner_ids: tuple[str, ...] = ()
    unknown_component_ids: tuple[str, ...] = ()
    ambiguous_component_ids: tuple[str, ...] = ()
    late_affected_owner_ids: tuple[str, ...] = ()
    late_executed_owner_ids: tuple[str, ...] = ()
    timeout_cleanup_confirmed: bool = True
    tag_matches_main: bool = True
    main_validation_receipt_current: bool = True
    tag_suite_execution_count: int = 0


@dataclass(frozen=True)
class ConsumerOutput:
    label: str
    skill_id: str = ""


@dataclass(frozen=True)
class ConsumerState:
    clean_installed_skills: tuple[str, ...] = ()
    completed_skills: tuple[str, ...] = ()
    blocked_skills: tuple[str, ...] = ()
    project_author_control_write_count: int = 0
    shared_test_evidence_count: int = 0
    update_status: str = "idle"
    update_explicitly_authorized: bool = False
    update_native_gates_ok: bool = False
    update_restoration_ok: bool = False
    update_final_health_ok: bool = False
    update_mark_current_ok: bool = False
    update_survivors_paused: bool = False
    activation_inventory_validated: bool = False
    active_scheduled_skills: tuple[str, ...] = ()
    manual_only_skills: tuple[str, ...] = ()
    activation_survivors_paused: bool = False
    upgrade_attempt_authority_status: str = "unknown"
    upgrade_attempt_manifest_binding_current: bool = False
    upgrade_attempt_history_scan_count: int = 0
    upgrade_attempt_manifest_fallback_used: bool = False
    installation_currentness_status: str = "unknown"
    installation_currentness_owner_execution_count: int = 0
    toolchain_receipt_status: str = "unknown"
    toolchain_content_matches: bool = False
    toolchain_location_differs: bool = False
    assurance_receipt_bounded: bool = False
    restored_automation_status: str = ""
    restored_automation_user_paused: bool = False
    automation_recovery_snapshot_status: str = "not_applicable"
    assurance_plan_status: str = "unknown"
    assurance_changed_component_ids: tuple[str, ...] = ()
    assurance_declared_owner_ids: tuple[str, ...] = ()
    assurance_affected_owner_ids: tuple[str, ...] = ()
    assurance_reused_owner_ids: tuple[str, ...] = ()
    assurance_executed_owner_ids: tuple[str, ...] = ()
    assurance_unknown_component_ids: tuple[str, ...] = ()
    assurance_ambiguous_component_ids: tuple[str, ...] = ()
    late_replan_status: str = "unknown"
    late_affected_owner_ids: tuple[str, ...] = ()
    late_executed_owner_ids: tuple[str, ...] = ()
    timed_out_owner_evidence_reusable: bool = False
    timeout_cleanup_status: str = "not_applicable"
    release_tag_status: str = "unknown"
    tag_suite_execution_count: int = 0


def _append_unique(values: tuple[str, ...], item: str) -> tuple[str, ...]:
    return values if item in values else (*values, item)


class ConsumerIndependenceBlock:
    name = "ConsumerIndependenceBlock"
    reads = tuple(ConsumerState.__dataclass_fields__)
    writes = reads
    accepted_input_type = ConsumerInput
    input_description = "one installation, native completion, update, or scope-boundary event"
    output_description = "one clean completion or fail-closed decision"
    idempotency = "skill id, exact obligation inventory, and current native receipt"

    def apply(
        self, input_obj: ConsumerInput, state: ConsumerState
    ) -> Iterable[FunctionResult]:
        if input_obj.kind == "install_projection":
            if (
                input_obj.skill_id not in AUTOMATION_TARGET_OBLIGATIONS
                or input_obj.contains_author_control
            ):
                new_state = replace(
                    state,
                    blocked_skills=_append_unique(
                        state.blocked_skills, input_obj.skill_id or "<unknown>"
                    ),
                )
                return (
                    FunctionResult(
                        ConsumerOutput(
                            "author_control_rejected", input_obj.skill_id
                        ),
                        new_state,
                        label="author_control_rejected",
                    ),
                )
            new_state = replace(
                state,
                clean_installed_skills=_append_unique(
                    state.clean_installed_skills, input_obj.skill_id
                ),
            )
            return (
                FunctionResult(
                    ConsumerOutput(
                        "clean_consumer_projection_installed",
                        input_obj.skill_id,
                    ),
                    new_state,
                    label="clean_consumer_projection_installed",
                ),
            )

        if input_obj.kind == "native_complete":
            expected = AUTOMATION_TARGET_OBLIGATIONS.get(
                input_obj.skill_id, ()
            )
            complete = (
                input_obj.skill_id in state.clean_installed_skills
                and input_obj.receipt_current
                and tuple(input_obj.obligation_ids) == tuple(expected)
            )
            if not complete:
                new_state = replace(
                    state,
                    blocked_skills=_append_unique(
                        state.blocked_skills, input_obj.skill_id or "<unknown>"
                    ),
                )
                return (
                    FunctionResult(
                        ConsumerOutput(
                            "native_completion_blocked", input_obj.skill_id
                        ),
                        new_state,
                        label="native_completion_blocked",
                    ),
                )
            new_state = replace(
                state,
                completed_skills=_append_unique(
                    state.completed_skills, input_obj.skill_id
                ),
            )
            return (
                FunctionResult(
                    ConsumerOutput(
                        "target_native_terminal_completed",
                        input_obj.skill_id,
                    ),
                    new_state,
                    label="target_native_terminal_completed",
                ),
            )

        if input_obj.kind == "manual_update":
            if not input_obj.explicit_user_request:
                return (
                    FunctionResult(
                        ConsumerOutput(
                            "manual_update_requires_explicit_request",
                            UPDATE_SKILL_ID,
                        ),
                        replace(
                            state,
                            update_status="blocked",
                            update_survivors_paused=False,
                        ),
                        label="manual_update_requires_explicit_request",
                    ),
                )
            if not input_obj.update_available:
                return (
                    FunctionResult(
                        ConsumerOutput("manual_update_no_update", UPDATE_SKILL_ID),
                        replace(
                            state,
                            update_status="no-update",
                            update_explicitly_authorized=True,
                            update_survivors_paused=False,
                        ),
                        label="manual_update_no_update",
                    ),
                )
            succeeded = bool(
                input_obj.native_gates_ok
                and input_obj.restoration_ok
                and input_obj.final_health_ok
                and input_obj.mark_current_ok
            )
            new_state = replace(
                state,
                update_status="current" if succeeded else "failed",
                update_explicitly_authorized=True,
                update_native_gates_ok=input_obj.native_gates_ok,
                update_restoration_ok=input_obj.restoration_ok,
                update_final_health_ok=input_obj.final_health_ok,
                update_mark_current_ok=input_obj.mark_current_ok,
                update_survivors_paused=not succeeded,
            )
            label = (
                "manual_update_current_and_restored"
                if succeeded
                else "manual_update_failed_survivors_paused"
            )
            return (
                FunctionResult(
                    ConsumerOutput(label, UPDATE_SKILL_ID),
                    new_state,
                    label=label,
                ),
            )

        if input_obj.kind == "operator_activate":
            maintained = tuple(sorted(input_obj.maintained_skill_ids))
            scheduled = tuple(sorted(input_obj.scheduled_skill_ids))
            manual_only = tuple(sorted(input_obj.manual_only_skill_ids))
            inventory_ok = bool(
                maintained == tuple(sorted(AUTOMATION_TARGET_IDS))
                and scheduled == tuple(sorted(SCHEDULED_SKILL_IDS))
                and manual_only == tuple(sorted(MANUAL_ONLY_SKILL_IDS))
                and not set(scheduled).intersection(manual_only)
                and set(scheduled).union(manual_only) == set(maintained)
            )
            if not inventory_ok:
                return (
                    FunctionResult(
                        ConsumerOutput("activation_inventory_blocked"),
                        replace(
                            state,
                            activation_inventory_validated=False,
                            active_scheduled_skills=(),
                            manual_only_skills=(),
                            activation_survivors_paused=True,
                        ),
                        label="activation_inventory_blocked",
                    ),
                )
            if not (
                input_obj.activation_checks_ok
                and input_obj.activation_transaction_completed
            ):
                return (
                    FunctionResult(
                        ConsumerOutput(
                            "activation_failed_survivors_paused"
                        ),
                        replace(
                            state,
                            activation_inventory_validated=True,
                            active_scheduled_skills=(),
                            manual_only_skills=tuple(
                                sorted(MANUAL_ONLY_SKILL_IDS)
                            ),
                            activation_survivors_paused=True,
                        ),
                        label="activation_failed_survivors_paused",
                    ),
                )
            return (
                FunctionResult(
                    ConsumerOutput(
                        "scheduled_automations_activated_manual_update_unscheduled"
                    ),
                    replace(
                        state,
                        activation_inventory_validated=True,
                        active_scheduled_skills=tuple(sorted(SCHEDULED_SKILL_IDS)),
                        manual_only_skills=tuple(sorted(MANUAL_ONLY_SKILL_IDS)),
                        activation_survivors_paused=False,
                    ),
                    label="scheduled_automations_activated_manual_update_unscheduled",
                ),
            )

        if input_obj.kind == "check_upgrade_attempt_current":
            current = bool(
                input_obj.attempt_head_current
                and input_obj.attempt_projection_bounded
                and input_obj.attempt_manifest_binding_current
                and input_obj.attempt_history_scan_count == 0
                and not input_obj.attempt_manifest_fallback_used
            )
            return (
                FunctionResult(
                    ConsumerOutput(
                        "upgrade_attempt_current_authority"
                        if current
                        else "upgrade_attempt_current_authority_blocked"
                    ),
                    replace(
                        state,
                        upgrade_attempt_authority_status=(
                            "current" if current else "blocked"
                        ),
                        upgrade_attempt_manifest_binding_current=(
                            input_obj.attempt_manifest_binding_current
                        ),
                        upgrade_attempt_history_scan_count=(
                            input_obj.attempt_history_scan_count
                        ),
                        upgrade_attempt_manifest_fallback_used=(
                            input_obj.attempt_manifest_fallback_used
                        ),
                    ),
                    label=(
                        "upgrade_attempt_current_authority"
                        if current
                        else "upgrade_attempt_current_authority_blocked"
                    ),
                ),
            )

        if input_obj.kind == "audit_install_currentness":
            current = bool(
                input_obj.currentness_read_only
                and input_obj.currentness_owner_execution_count == 0
            )
            label = (
                "installation_currentness_read_only"
                if current
                else "installation_currentness_executed_owner_blocked"
            )
            return (
                FunctionResult(
                    ConsumerOutput(label),
                    replace(
                        state,
                        installation_currentness_status=(
                            "current" if current else "blocked"
                        ),
                        installation_currentness_owner_execution_count=(
                            input_obj.currentness_owner_execution_count
                        ),
                    ),
                    label=label,
                ),
            )

        if input_obj.kind == "audit_toolchain_receipt":
            current = bool(
                input_obj.toolchain_content_matches
                and input_obj.assurance_receipt_bounded
            )
            label = (
                "content_bound_toolchain_receipt_current"
                if current
                else "toolchain_receipt_blocked"
            )
            return (
                FunctionResult(
                    ConsumerOutput(label),
                    replace(
                        state,
                        toolchain_receipt_status=(
                            "current" if current else "blocked"
                        ),
                        toolchain_content_matches=(
                            input_obj.toolchain_content_matches
                        ),
                        toolchain_location_differs=(
                            input_obj.toolchain_location_differs
                        ),
                        assurance_receipt_bounded=(
                            input_obj.assurance_receipt_bounded
                        ),
                    ),
                    label=label,
                ),
            )

        if input_obj.kind == "restore_automation_intent":
            if (
                input_obj.recoverable_upgrade_attempt
                and not input_obj.recovery_snapshot_current
            ):
                return (
                    FunctionResult(
                        ConsumerOutput(
                            "missing_recovery_snapshot_direct_repair_blocked"
                        ),
                        replace(
                            state,
                            restored_automation_status="",
                            restored_automation_user_paused=False,
                            automation_recovery_snapshot_status="blocked",
                        ),
                        label="missing_recovery_snapshot_direct_repair_blocked",
                    ),
                )
            target_status = (
                "PAUSED" if input_obj.automation_user_paused else "ACTIVE"
            )
            label = (
                "user_pause_intent_restored"
                if input_obj.automation_user_paused
                else "system_pause_reactivated"
            )
            return (
                FunctionResult(
                    ConsumerOutput(label),
                    replace(
                        state,
                        restored_automation_status=target_status,
                        restored_automation_user_paused=(
                            input_obj.automation_user_paused
                        ),
                        automation_recovery_snapshot_status=(
                            "current"
                            if input_obj.recoverable_upgrade_attempt
                            else "not_applicable"
                        ),
                    ),
                    label=label,
                ),
            )

        if input_obj.kind == "plan_affected_assurance":
            declared = tuple(sorted(set(input_obj.declared_owner_ids)))
            affected = tuple(sorted(set(input_obj.affected_owner_ids)))
            reusable = tuple(sorted(set(input_obj.reusable_owner_ids)))
            executed = tuple(sorted(set(input_obj.executed_owner_ids)))
            unknown = tuple(sorted(set(input_obj.unknown_component_ids)))
            ambiguous = tuple(sorted(set(input_obj.ambiguous_component_ids)))
            valid = bool(
                not unknown
                and not ambiguous
                and executed == affected
                and not set(executed).intersection(reusable)
                and (
                    not declared
                    or set(declared) == set(affected).union(reusable)
                )
            )
            label = (
                "affected_assurance_plan_stable"
                if valid
                else "affected_assurance_plan_blocked"
            )
            return (
                FunctionResult(
                    ConsumerOutput(label),
                    replace(
                        state,
                        assurance_plan_status="stable" if valid else "blocked",
                        assurance_changed_component_ids=tuple(
                            sorted(set(input_obj.changed_component_ids))
                        ),
                        assurance_declared_owner_ids=declared,
                        assurance_affected_owner_ids=affected,
                        assurance_reused_owner_ids=reusable,
                        assurance_executed_owner_ids=executed,
                        assurance_unknown_component_ids=unknown,
                        assurance_ambiguous_component_ids=ambiguous,
                    ),
                    label=label,
                ),
            )

        if input_obj.kind == "replan_late_assurance_inputs":
            affected = tuple(sorted(set(input_obj.late_affected_owner_ids)))
            executed = tuple(sorted(set(input_obj.late_executed_owner_ids)))
            valid = executed == affected
            label = (
                "late_inputs_affected_only_replanned"
                if valid
                else "late_inputs_run_all_blocked"
            )
            return (
                FunctionResult(
                    ConsumerOutput(label),
                    replace(
                        state,
                        late_replan_status="stable" if valid else "blocked",
                        late_affected_owner_ids=affected,
                        late_executed_owner_ids=executed,
                    ),
                    label=label,
                ),
            )

        if input_obj.kind == "validation_owner_timeout":
            label = (
                "timeout_descendants_zero_evidence_invalid"
                if input_obj.timeout_cleanup_confirmed
                else "timeout_cleanup_unconfirmed_blocked"
            )
            return (
                FunctionResult(
                    ConsumerOutput(label),
                    replace(
                        state,
                        timed_out_owner_evidence_reusable=False,
                        timeout_cleanup_status=(
                            "descendants_zero"
                            if input_obj.timeout_cleanup_confirmed
                            else "cleanup_unconfirmed"
                        ),
                    ),
                    label=label,
                ),
            )

        if input_obj.kind == "verify_release_tag":
            current = bool(
                input_obj.tag_matches_main
                and input_obj.main_validation_receipt_current
                and input_obj.tag_suite_execution_count == 0
            )
            label = (
                "release_tag_consumed_main_receipt"
                if current
                else "release_tag_receipt_gate_blocked"
            )
            return (
                FunctionResult(
                    ConsumerOutput(label),
                    replace(
                        state,
                        release_tag_status="verified" if current else "blocked",
                        tag_suite_execution_count=input_obj.tag_suite_execution_count,
                    ),
                    label=label,
                ),
            )

        if input_obj.kind == "third_party_overlap":
            return (
                FunctionResult(
                    ConsumerOutput("third_party_overlap_outside_guarantee"),
                    state,
                    label="third_party_overlap_outside_guarantee",
                ),
            )

        return ()


def consumer_independence_workflow() -> Workflow:
    return Workflow(
        (ConsumerIndependenceBlock(),),
        name="khaos_brain_consumer_independence",
    )


@dataclass(frozen=True)
class LifecycleInput:
    """One bounded Sleep lifecycle or active-index publication action."""

    kind: str
    planned_event_count: int = 0
    created_event_count: int = 0
    reused_event_count: int = 0
    snapshot_current: bool = True
    publisher_id: str = "local_kb.lifecycle.run_incremental_sleep"
    marker_token_current: bool = True
    validation_complete: bool = True
    cleanup_confirmed: bool = True


@dataclass(frozen=True)
class LifecycleOutput:
    label: str


@dataclass(frozen=True)
class LifecycleState:
    """Authoritative lifecycle/index state owned by LifecycleConvergenceBlock."""

    active_index_state: str = "valid_current"
    invalidation_token: str = ""
    staged_event_count: int = 0
    committed_event_count: int = 0
    reused_event_count: int = 0
    lifecycle_batch_count: int = 0
    lifecycle_replay_pass_count: int = 0
    authority_stamp_published: bool = True
    watermark_committed: bool = True
    watermark_version: int = 1
    failure_visible: bool = False
    wrapper_failure_receipt_present: bool = False
    target_terminal_receipt_present: bool = True
    timeout_cleanup_confirmed: bool = True
    unauthorized_publication_count: int = 0


ACTIVE_INDEX_PUBLISHERS = (
    "local_kb.lifecycle.run_incremental_sleep",
    "local_kb.maintenance_migration",
)


class LifecycleConvergenceBlock:
    """Input x State -> Set(Output x State) for bounded lifecycle convergence."""

    name = "LifecycleConvergenceBlock"
    reads = tuple(LifecycleState.__dataclass_fields__)
    writes = reads
    accepted_input_type = LifecycleInput
    input_description = "one staged batch, timeout, or authorized index publication"
    output_description = "one bounded commit, visible failure, or current index"
    idempotency = "stable lifecycle event ids plus the exact invalidation token"

    def apply(
        self, input_obj: LifecycleInput, state: LifecycleState
    ) -> Iterable[FunctionResult]:
        if input_obj.kind == "stage_lifecycle_batch":
            return (
                FunctionResult(
                    LifecycleOutput("lifecycle_batch_staged"),
                    replace(
                        state,
                        staged_event_count=input_obj.planned_event_count,
                    ),
                    label="lifecycle_batch_staged",
                ),
            )

        if input_obj.kind == "commit_lifecycle_batch":
            if not input_obj.snapshot_current:
                return (
                    FunctionResult(
                        LifecycleOutput("stale_lifecycle_snapshot_blocked"),
                        replace(state, failure_visible=True),
                        label="stale_lifecycle_snapshot_blocked",
                    ),
                )
            return (
                FunctionResult(
                    LifecycleOutput("lifecycle_batch_committed_once"),
                    replace(
                        state,
                        active_index_state="invalidated_pending_rebuild",
                        invalidation_token="sleep-cycle-token",
                        committed_event_count=(
                            state.committed_event_count
                            + input_obj.created_event_count
                        ),
                        reused_event_count=(
                            state.reused_event_count
                            + input_obj.reused_event_count
                        ),
                        lifecycle_batch_count=state.lifecycle_batch_count + 1,
                        lifecycle_replay_pass_count=(
                            state.lifecycle_replay_pass_count + 2
                        ),
                        authority_stamp_published=False,
                        watermark_committed=False,
                        target_terminal_receipt_present=False,
                    ),
                    label="lifecycle_batch_committed_once",
                ),
            )

        if input_obj.kind == "native_timeout_after_lifecycle_commit":
            return (
                FunctionResult(
                    LifecycleOutput("timeout_visible_index_remains_invalid"),
                    replace(
                        state,
                        failure_visible=True,
                        wrapper_failure_receipt_present=True,
                        target_terminal_receipt_present=False,
                        timeout_cleanup_confirmed=input_obj.cleanup_confirmed,
                    ),
                    label="timeout_visible_index_remains_invalid",
                ),
            )

        if input_obj.kind in {"publish_active_index", "next_sleep_recovery"}:
            authorized = input_obj.publisher_id in ACTIVE_INDEX_PUBLISHERS
            can_publish = bool(
                authorized
                and state.active_index_state == "invalidated_pending_rebuild"
                and state.invalidation_token
                and input_obj.marker_token_current
                and input_obj.validation_complete
            )
            if not can_publish:
                return (
                    FunctionResult(
                        LifecycleOutput("active_index_publication_blocked"),
                        replace(
                            state,
                            failure_visible=True,
                            unauthorized_publication_count=(
                                state.unauthorized_publication_count
                                + (0 if authorized else 1)
                            ),
                        ),
                        label="active_index_publication_blocked",
                    ),
                )
            return (
                FunctionResult(
                    LifecycleOutput("active_index_rebuilt_and_watermark_committed"),
                    replace(
                        state,
                        active_index_state="valid_current",
                        invalidation_token="",
                        authority_stamp_published=True,
                        watermark_committed=True,
                        watermark_version=state.watermark_version + 1,
                        failure_visible=False,
                        wrapper_failure_receipt_present=False,
                        target_terminal_receipt_present=True,
                    ),
                    label="active_index_rebuilt_and_watermark_committed",
                ),
            )

        return ()


def lifecycle_convergence_workflow() -> Workflow:
    return Workflow(
        (LifecycleConvergenceBlock(),),
        name="khaos_brain_lifecycle_convergence",
    )


def _active_index_is_fail_closed(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.active_index_state == "valid_current" and state.invalidation_token:
        return InvariantResult.fail(
            "active index is current while a durable invalidation token remains"
        )
    if state.active_index_state == "invalidated_pending_rebuild" and (
        state.authority_stamp_published or state.watermark_committed
    ):
        return InvariantResult.fail(
            "invalidated index published authority or advanced the Sleep watermark"
        )
    return InvariantResult.pass_()


def _lifecycle_batches_have_bounded_replay(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.lifecycle_replay_pass_count != state.lifecycle_batch_count * 2:
        return InvariantResult.fail(
            "lifecycle replay count is not exactly two per atomic batch"
        )
    return InvariantResult.pass_()


def _active_index_publication_has_one_authorized_owner(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.unauthorized_publication_count:
        return InvariantResult.fail(
            "an unauthorized caller attempted active-index publication"
        )
    return InvariantResult.pass_()


def _lifecycle_event_idempotency_is_monotonic(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.committed_event_count < 0 or state.reused_event_count < 0:
        return InvariantResult.fail(
            "lifecycle idempotency accounting became negative"
        )
    return InvariantResult.pass_()


def _timeout_never_becomes_success(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.wrapper_failure_receipt_present and not state.failure_visible:
        return InvariantResult.fail(
            "a timed-out wrapper episode was represented as current success"
        )
    if state.wrapper_failure_receipt_present and state.target_terminal_receipt_present:
        return InvariantResult.fail(
            "a wrapper failure receipt was substituted for the target Sleep terminal"
        )
    return InvariantResult.pass_()


LIFECYCLE_INVARIANTS = (
    Invariant(
        "active_index_is_fail_closed",
        "Invalidated index state remains unavailable until exact publication closes.",
        _active_index_is_fail_closed,
    ),
    Invariant(
        "lifecycle_batches_have_bounded_replay",
        "Each atomic lifecycle batch performs exactly one pre/post replay pair.",
        _lifecycle_batches_have_bounded_replay,
    ),
    Invariant(
        "active_index_publication_has_one_authorized_owner",
        "Only canonical Sleep and versioned migration publish the active index.",
        _active_index_publication_has_one_authorized_owner,
    ),
    Invariant(
        "lifecycle_event_idempotency_is_monotonic",
        "Created and reused stable lifecycle event identities are monotonic.",
        _lifecycle_event_idempotency_is_monotonic,
    ),
    Invariant(
        "timeout_never_becomes_success",
        "A native timeout stays a visible non-success until a later Sleep closes.",
        _timeout_never_becomes_success,
    ),
)


LIFECYCLE_INPUTS = (
    LifecycleInput("stage_lifecycle_batch", planned_event_count=500),
    LifecycleInput(
        "commit_lifecycle_batch",
        planned_event_count=500,
        created_event_count=500,
    ),
    LifecycleInput(
        "commit_lifecycle_batch",
        planned_event_count=500,
        created_event_count=0,
        reused_event_count=500,
    ),
    LifecycleInput(
        "commit_lifecycle_batch",
        planned_event_count=1,
        snapshot_current=False,
    ),
    LifecycleInput("native_timeout_after_lifecycle_commit"),
    LifecycleInput("next_sleep_recovery"),
    LifecycleInput("publish_active_index", marker_token_current=False),
)


def _no_author_control_in_consumer(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if state.project_author_control_write_count:
        return InvariantResult.fail(
            "ordinary project or consumer installation wrote author control"
        )
    return InvariantResult.pass_()


def _no_cross_unit_evidence_reuse(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if state.shared_test_evidence_count:
        return InvariantResult.fail(
            "two maintenance units reused the same test evidence"
        )
    return InvariantResult.pass_()


def _completion_requires_clean_projection(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if not set(state.completed_skills).issubset(
        set(state.clean_installed_skills)
    ):
        return InvariantResult.fail(
            "a skill completed without a clean consumer projection"
        )
    return InvariantResult.pass_()


def _current_update_requires_native_completion(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if state.update_status != "current":
        return InvariantResult.pass_()
    if not (
        state.update_explicitly_authorized
        and state.update_native_gates_ok
        and state.update_restoration_ok
        and state.update_final_health_ok
        and state.update_mark_current_ok
        and not state.update_survivors_paused
    ):
        return InvariantResult.fail(
            "CURRENT was marked before direct target-native completion"
        )
    return InvariantResult.pass_()


def _activation_excludes_manual_only_skill(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if not state.activation_inventory_validated:
        return InvariantResult.pass_()
    if state.activation_survivors_paused:
        if state.active_scheduled_skills:
            return InvariantResult.fail(
                "failed operator activation left scheduled automations active"
            )
        return InvariantResult.pass_()
    if (
        set(state.active_scheduled_skills) != set(SCHEDULED_SKILL_IDS)
        or set(state.manual_only_skills) != set(MANUAL_ONLY_SKILL_IDS)
        or set(state.active_scheduled_skills).intersection(
            state.manual_only_skills
        )
    ):
        return InvariantResult.fail(
            "operator activation did not preserve the exact four scheduled "
            "plus one manual-only inventory"
        )
    return InvariantResult.pass_()


def _attempt_currentness_has_no_history_or_manifest_fallback(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if state.upgrade_attempt_authority_status != "current":
        return InvariantResult.pass_()
    if (
        not state.upgrade_attempt_manifest_binding_current
        or
        state.upgrade_attempt_history_scan_count != 0
        or state.upgrade_attempt_manifest_fallback_used
    ):
        return InvariantResult.fail(
            "upgrade-attempt currentness lacks the exact committed manifest binding, "
            "scanned history, or used manifest fallback"
        )
    return InvariantResult.pass_()


def _installation_currentness_never_executes_owner(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if (
        state.installation_currentness_status == "current"
        and state.installation_currentness_owner_execution_count != 0
    ):
        return InvariantResult.fail(
            "installation currentness launched a validation owner"
        )
    return InvariantResult.pass_()


def _toolchain_receipt_is_content_bound_and_bounded(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if state.toolchain_receipt_status != "current":
        return InvariantResult.pass_()
    if (
        not state.toolchain_content_matches
        or not state.assurance_receipt_bounded
    ):
        return InvariantResult.fail(
            "current toolchain receipt is path-bound, content-stale, or unbounded"
        )
    return InvariantResult.pass_()


def _automation_restoration_follows_user_pause_intent(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if not state.restored_automation_status:
        return InvariantResult.pass_()
    if state.automation_recovery_snapshot_status == "blocked":
        return InvariantResult.fail(
            "automation restored despite a missing recovery snapshot"
        )
    expected = (
        "PAUSED" if state.restored_automation_user_paused else "ACTIVE"
    )
    if state.restored_automation_status != expected:
        return InvariantResult.fail(
            "transient runtime pause overrode the current user-pause intent"
        )
    return InvariantResult.pass_()


def _assurance_executes_only_affected_owners(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if state.assurance_plan_status != "stable":
        return InvariantResult.pass_()
    if (
        state.assurance_unknown_component_ids
        or state.assurance_ambiguous_component_ids
        or (
            state.assurance_declared_owner_ids
            and set(state.assurance_declared_owner_ids)
            != set(state.assurance_affected_owner_ids).union(
                state.assurance_reused_owner_ids
            )
        )
        or set(state.assurance_executed_owner_ids)
        != set(state.assurance_affected_owner_ids)
        or set(state.assurance_executed_owner_ids).intersection(
            state.assurance_reused_owner_ids
        )
    ):
        return InvariantResult.fail(
            "stable assurance plan did not execute exactly the affected owners"
        )
    return InvariantResult.pass_()


def _late_inputs_never_trigger_run_all(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if state.late_replan_status != "stable":
        return InvariantResult.pass_()
    if set(state.late_executed_owner_ids) != set(state.late_affected_owner_ids):
        return InvariantResult.fail(
            "late input replanning executed an unaffected owner"
        )
    return InvariantResult.pass_()


def _release_tag_is_receipt_only(
    state: ConsumerState, trace: object
) -> InvariantResult:
    del trace
    if (
        state.release_tag_status == "verified"
        and state.tag_suite_execution_count != 0
    ):
        return InvariantResult.fail(
            "release tag reran the repository suite"
        )
    return InvariantResult.pass_()


CONSUMER_INVARIANTS = (
    Invariant(
        "consumer_has_no_author_control",
        "Consumer execution never writes or loads author-side control.",
        _no_author_control_in_consumer,
    ),
    Invariant(
        "maintenance_units_do_not_share_test_evidence",
        "Each maintained skill owns its own evidence subject.",
        _no_cross_unit_evidence_reuse,
    ),
    Invariant(
        "completion_requires_clean_projection",
        "A target can complete only after its clean consumer projection exists.",
        _completion_requires_clean_projection,
    ),
    Invariant(
        "manual_update_closes_natively",
        "CURRENT requires explicit authorization, restoration, final health, and mark-current.",
        _current_update_requires_native_completion,
    ),
    Invariant(
        "operator_activation_excludes_manual_only_skill",
        "Operator activation binds four scheduled skills and keeps the update skill manual-only.",
        _activation_excludes_manual_only_skill,
    ),
    Invariant(
        "upgrade_attempt_currentness_is_pointer_only",
        "Currentness reads one bounded HEAD/current binding, requires the committed "
        "install state to bind its exact receipt, and uses no history scan or manifest fallback.",
        _attempt_currentness_has_no_history_or_manifest_fallback,
    ),
    Invariant(
        "installation_currentness_is_read_only",
        "Installation currentness launches zero validation owners.",
        _installation_currentness_never_executes_owner,
    ),
    Invariant(
        "toolchain_receipt_is_content_bound_and_bounded",
        "Toolchain currentness ignores absolute location when portable content "
        "matches and never embeds complete owner traces.",
        _toolchain_receipt_is_content_bound_and_bounded,
    ),
    Invariant(
        "automation_restoration_follows_user_pause_intent",
        "A safety pause never becomes a permanent user pause.",
        _automation_restoration_follows_user_pause_intent,
    ),
    Invariant(
        "assurance_executes_only_affected_owners",
        "A stable assurance plan executes exactly its affected owners.",
        _assurance_executes_only_affected_owners,
    ),
    Invariant(
        "late_inputs_never_trigger_run_all",
        "Late input drift replans only owners with changed declared inputs.",
        _late_inputs_never_trigger_run_all,
    ),
    Invariant(
        "release_tag_is_receipt_only",
        "A verified release tag consumes exact-main evidence without test execution.",
        _release_tag_is_receipt_only,
    ),
)


CONSUMER_INITIAL_STATES = (
    ConsumerState(),
    ConsumerState(project_author_control_write_count=1),
    ConsumerState(shared_test_evidence_count=1),
)
CONSUMER_INPUTS = (
    *(
        ConsumerInput("install_projection", skill_id=skill_id)
        for skill_id in AUTOMATION_TARGET_IDS
    ),
    ConsumerInput(
        "install_projection",
        skill_id="kb-sleep-maintenance",
        contains_author_control=True,
    ),
    ConsumerInput(
        "native_complete",
        skill_id="kb-sleep-maintenance",
        obligation_ids=AUTOMATION_TARGET_OBLIGATIONS[
            "kb-sleep-maintenance"
        ],
    ),
    ConsumerInput(
        "native_complete",
        skill_id="kb-sleep-maintenance",
        obligation_ids=(),
    ),
    ConsumerInput("manual_update"),
    ConsumerInput(
        "manual_update",
        explicit_user_request=True,
        update_available=False,
    ),
    ConsumerInput(
        "manual_update",
        explicit_user_request=True,
    ),
    ConsumerInput(
        "manual_update",
        explicit_user_request=True,
        restoration_ok=False,
    ),
    ConsumerInput(
        "operator_activate",
        maintained_skill_ids=AUTOMATION_TARGET_IDS,
        scheduled_skill_ids=SCHEDULED_SKILL_IDS,
        manual_only_skill_ids=MANUAL_ONLY_SKILL_IDS,
    ),
    ConsumerInput(
        "operator_activate",
        maintained_skill_ids=AUTOMATION_TARGET_IDS,
        scheduled_skill_ids=AUTOMATION_TARGET_IDS,
        manual_only_skill_ids=(),
    ),
    ConsumerInput(
        "operator_activate",
        maintained_skill_ids=AUTOMATION_TARGET_IDS,
        scheduled_skill_ids=SCHEDULED_SKILL_IDS,
        manual_only_skill_ids=MANUAL_ONLY_SKILL_IDS,
        activation_checks_ok=False,
        activation_transaction_completed=False,
    ),
    ConsumerInput("check_upgrade_attempt_current"),
    ConsumerInput(
        "check_upgrade_attempt_current",
        attempt_history_scan_count=1,
        attempt_manifest_fallback_used=True,
    ),
    ConsumerInput(
        "check_upgrade_attempt_current",
        attempt_manifest_binding_current=False,
    ),
    ConsumerInput("audit_install_currentness"),
    ConsumerInput(
        "audit_install_currentness",
        currentness_owner_execution_count=1,
    ),
    ConsumerInput(
        "audit_toolchain_receipt",
        toolchain_content_matches=True,
        toolchain_location_differs=True,
        assurance_receipt_bounded=True,
    ),
    ConsumerInput(
        "audit_toolchain_receipt",
        toolchain_content_matches=False,
        toolchain_location_differs=False,
        assurance_receipt_bounded=True,
    ),
    ConsumerInput(
        "audit_toolchain_receipt",
        toolchain_content_matches=True,
        toolchain_location_differs=False,
        assurance_receipt_bounded=False,
    ),
    ConsumerInput(
        "restore_automation_intent",
        automation_runtime_status="PAUSED",
        automation_user_paused=False,
        recoverable_upgrade_attempt=True,
        recovery_snapshot_current=True,
    ),
    ConsumerInput(
        "restore_automation_intent",
        automation_runtime_status="PAUSED",
        automation_user_paused=True,
    ),
    ConsumerInput(
        "restore_automation_intent",
        automation_runtime_status="PAUSED",
        automation_user_paused=False,
        recoverable_upgrade_attempt=True,
        recovery_snapshot_current=False,
    ),
    ConsumerInput(
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
    ConsumerInput(
        "plan_affected_assurance",
        changed_component_ids=("unknown",),
        unknown_component_ids=("unknown",),
        executed_owner_ids=(
            "consumer-projections",
            "current-runtime",
            "flow-model",
            "reasoning-runtime",
            "retrieval-quality",
        ),
    ),
    ConsumerInput(
        "replan_late_assurance_inputs",
        late_affected_owner_ids=("retrieval-quality",),
        late_executed_owner_ids=("retrieval-quality",),
    ),
    ConsumerInput(
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
    ConsumerInput("validation_owner_timeout"),
    ConsumerInput(
        "validation_owner_timeout",
        timeout_cleanup_confirmed=False,
    ),
    ConsumerInput("verify_release_tag"),
    ConsumerInput(
        "verify_release_tag",
        tag_suite_execution_count=1,
    ),
    ConsumerInput("third_party_overlap"),
)


# Stable owner names retained for the surrounding LogicGuard mesh.
UpgradeMigrationBlock = ConsumerIndependenceBlock
AutomationRuntimeAssuranceBlock = ConsumerIndependenceBlock


__all__ = [
    "AUTOMATION_TARGET_OBLIGATIONS",
    "AUTOMATION_TARGET_IDS",
    "AUTOMATION_CHECK_KINDS",
    "SCHEDULED_SKILL_IDS",
    "MANUAL_ONLY_SKILL_IDS",
    "UPDATE_SKILL_ID",
    "ConsumerInput",
    "ConsumerOutput",
    "ConsumerState",
    "ConsumerIndependenceBlock",
    "LifecycleInput",
    "LifecycleOutput",
    "LifecycleState",
    "LifecycleConvergenceBlock",
    "LIFECYCLE_INVARIANTS",
    "LIFECYCLE_INPUTS",
    "CONSUMER_INVARIANTS",
    "CONSUMER_INITIAL_STATES",
    "CONSUMER_INPUTS",
    "automation_manifest_check_ids",
    "consumer_independence_workflow",
    "lifecycle_convergence_workflow",
]
