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
    ConsumerInput("third_party_overlap"),
)


# Stable owner names retained for the surrounding LogicGuard mesh.
LifecycleConvergenceBlock = ConsumerIndependenceBlock
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
    "CONSUMER_INVARIANTS",
    "CONSUMER_INITIAL_STATES",
    "CONSUMER_INPUTS",
    "automation_manifest_check_ids",
    "consumer_independence_workflow",
]
