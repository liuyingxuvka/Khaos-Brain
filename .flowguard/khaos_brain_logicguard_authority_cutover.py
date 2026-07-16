"""Executable FlowGuard child model for Khaos Brain LogicGuard authority.

This model owns only the authority-cutover boundary. Existing lifecycle,
governance, search, index-publication, migration, and UI models remain the
primary product owners. Every block below implements
``Input x State -> Set(Output x State)`` through ``FunctionResult``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import (
    BoundedEventuallyProperty,
    FunctionContract,
    FunctionResult,
    Invariant,
    InvariantResult,
    LoopCheckConfig,
    ProgressCheckConfig,
    ScenarioRun,
    Workflow,
    check_loops,
    check_progress,
    check_refinement_projection,
    check_trace_contracts,
    run_exact_sequence,
)


MODEL_ID = "khaos_brain_logicguard_authority_cutover"


@dataclass(frozen=True)
class Event:
    kind: str


@dataclass(frozen=True)
class StepResult:
    event: Event
    action: str


@dataclass(frozen=True)
class State:
    cutover_started: bool = False
    sleep_planned: bool = False
    model_revision: str = ""
    mesh_revision: str = ""
    projection_validated: bool = False
    projection_published: bool = False
    index_published: bool = False
    zero_legacy_residuals: bool = False
    generation_current: bool = False
    prior_generation_authoritative: bool = True
    automations_paused: bool = False
    migration_failed: bool = False
    model_commit_without_owner: bool = False
    unauthorized_authority_write: bool = False
    duplicate_sleep_owner: bool = False
    duplicate_search_owner: bool = False
    dream_pinned_revision: str = ""
    dream_simulated: bool = False
    dream_handoff_published: bool = False
    dream_mutated_authority: bool = False
    bound_index_loaded: bool = False
    read_session_generation_current: bool = False
    cross_generation_read_session_reused: bool = False
    exact_revision_loaded: bool = False
    neighborhood_materialized: bool = False
    retrieval_returned: bool = False
    flat_yaml_fallback_used: bool = False
    head_substitution_used: bool = False
    projection_digest_mismatch: bool = False
    legacy_reader_active: bool = False
    cross_scope_reference: bool = False
    done: bool = False


CURRENT_STATE = State(
    model_revision="model-revision:current",
    mesh_revision="mesh-revision:current",
    projection_validated=True,
    projection_published=True,
    index_published=True,
    zero_legacy_residuals=True,
    generation_current=True,
    prior_generation_authoritative=False,
)


def _event(input_obj: Event | StepResult) -> Event:
    return input_obj.event if isinstance(input_obj, StepResult) else input_obj


def _result(event: Event, action: str, old: State, new: State, reason: str) -> FunctionResult:
    return FunctionResult(
        output=StepResult(event, action),
        new_state=new,
        label=action,
        reason=reason,
    )


class BindCardModelBlock:
    """Input x State -> Set(Output x State) for canonical model binding."""

    name = "BindCardModelBlock"
    reads = ("cutover_started", "sleep_planned", "model_revision")
    writes = (
        "cutover_started",
        "sleep_planned",
        "model_revision",
        "automations_paused",
        "model_commit_without_owner",
        "legacy_reader_active",
    )
    accepted_input_type = Event
    output_type = StepResult

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        event = _event(input_obj)
        new = state
        action = "bind_model_noop"
        reason = "Event does not change canonical card-model binding."
        if event.kind == "begin_cutover":
            new = replace(state, cutover_started=True, automations_paused=True)
            action = "cutover_started"
            reason = "Direct migration starts under a paused managed-writer boundary."
        elif event.kind == "plan_sleep_change":
            new = replace(state, sleep_planned=True)
            action = "sleep_change_planned"
            reason = "The existing Sleep owner selected a bounded model change."
        elif event.kind == "commit_model":
            owned = state.cutover_started or state.sleep_planned
            new = replace(
                state,
                model_revision="model-revision:new",
                model_commit_without_owner=not owned,
            )
            action = "model_revision_committed"
            reason = "Canonical model revision committed with an expected owner and CAS boundary."
        elif event.kind == "legacy_reader_used":
            new = replace(state, legacy_reader_active=True)
            action = "legacy_reader_used"
            reason = "Broken path: normal runtime interpreted YAML as semantic authority."
        yield _result(event, action, state, new, reason)


class ValidateCardBindingBlock:
    """Input x State -> Set(Output x State) for exact projection binding."""

    name = "ValidateCardBindingBlock"
    reads = ("model_revision", "mesh_revision", "projection_validated")
    writes = (
        "projection_validated",
        "projection_digest_mismatch",
        "head_substitution_used",
    )
    accepted_input_type = StepResult
    output_type = StepResult

    def apply(self, input_obj: StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event(input_obj)
        new = state
        action = "binding_validation_noop"
        reason = "Event does not change exact card binding validation."
        if event.kind == "validate_projection":
            new = replace(state, projection_validated=True)
            action = "projection_binding_validated"
            reason = "Projection matches the exact model, block, root node, mesh, scope, and digest."
        elif event.kind == "projection_digest_mismatch":
            new = replace(state, projection_digest_mismatch=True)
            action = "projection_digest_mismatch"
            reason = "Broken path: displayed fields differ from canonical projection content."
        elif event.kind == "head_substitution":
            new = replace(state, head_substitution_used=True)
            action = "head_substitution_used"
            reason = "Broken path: a floating head replaced the exact bound revision."
        yield _result(event, action, state, new, reason)


class PlanSleepModelChangeBlock:
    """Input x State -> Set(Output x State) for Sleep-owned planning."""

    name = "PlanSleepModelChangeBlock"
    reads = ("sleep_planned", "duplicate_sleep_owner")
    writes = ("duplicate_sleep_owner",)
    accepted_input_type = StepResult
    output_type = StepResult

    def apply(self, input_obj: StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event(input_obj)
        new = state
        action = "sleep_plan_noop"
        reason = "Event does not change Sleep decision ownership."
        if event.kind == "duplicate_sleep_owner":
            new = replace(state, duplicate_sleep_owner=True)
            action = "duplicate_sleep_owner_registered"
            reason = "Broken path: a LogicGuard controller duplicated the Khaos Sleep owner."
        yield _result(event, action, state, new, reason)


class CommitSleepModelChangeBlock:
    """Input x State -> Set(Output x State) for model-first generation publication."""

    name = "CommitSleepModelChangeBlock"
    reads = (
        "model_revision",
        "mesh_revision",
        "projection_validated",
        "projection_published",
        "index_published",
    )
    writes = (
        "mesh_revision",
        "projection_published",
        "index_published",
        "unauthorized_authority_write",
    )
    accepted_input_type = StepResult
    output_type = StepResult

    def apply(self, input_obj: StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event(input_obj)
        new = state
        action = "commit_generation_noop"
        reason = "Event does not change the staged authority generation."
        if event.kind == "commit_mesh":
            new = replace(state, mesh_revision="mesh-revision:new")
            action = "mesh_revision_committed"
            reason = "The affected scoped ModelMesh pins the exact committed card model."
        elif event.kind == "publish_projection":
            new = replace(state, projection_published=True)
            action = "projection_published"
            reason = "The verified projection is staged after canonical commits."
        elif event.kind == "publish_index":
            new = replace(state, index_published=True)
            action = "active_index_published"
            reason = "The active index generation binds the exact projection/model/mesh authority."
        elif event.kind == "unauthorized_authority_write":
            new = replace(state, unauthorized_authority_write=True)
            action = "unauthorized_authority_write"
            reason = "Broken path: a non-Sleep/non-migration route wrote canonical authority."
        yield _result(event, action, state, new, reason)


class ValidateDreamMeshBlock:
    """Input x State -> Set(Output x State) for exact read-only Dream experiments."""

    name = "ValidateDreamMeshBlock"
    reads = ("mesh_revision", "dream_pinned_revision", "dream_simulated")
    writes = (
        "dream_pinned_revision",
        "dream_simulated",
        "dream_handoff_published",
        "dream_mutated_authority",
    )
    accepted_input_type = StepResult
    output_type = StepResult

    def apply(self, input_obj: StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event(input_obj)
        new = state
        action = "dream_validation_noop"
        reason = "Event does not change Dream experiment state."
        if event.kind == "pin_dream_mesh":
            new = replace(state, dream_pinned_revision=state.mesh_revision)
            action = "dream_mesh_revision_pinned"
            reason = "Dream pins one exact current mesh revision before simulation."
        elif event.kind == "simulate_dream":
            new = replace(state, dream_simulated=True)
            action = "dream_simulation_completed"
            reason = "A bounded LogicGuard perturbation produced immutable experiment evidence."
        elif event.kind == "publish_dream_handoff":
            new = replace(state, dream_handoff_published=True)
            action = "dream_sleep_handoff_published"
            reason = "Dream emitted one typed idempotent handoff for the existing Sleep owner."
        elif event.kind == "dream_mutates_authority":
            new = replace(state, dream_mutated_authority=True)
            action = "dream_mutated_authority"
            reason = "Broken path: Dream changed a canonical model, mesh, projection, or index."
        yield _result(event, action, state, new, reason)


class RetrieveModelNeighborhoodBlock:
    """Input x State -> Set(Output x State) for model-native retrieval."""

    name = "RetrieveModelNeighborhoodBlock"
    reads = (
        "generation_current",
        "bound_index_loaded",
        "read_session_generation_current",
        "exact_revision_loaded",
        "neighborhood_materialized",
    )
    writes = (
        "bound_index_loaded",
        "read_session_generation_current",
        "cross_generation_read_session_reused",
        "exact_revision_loaded",
        "neighborhood_materialized",
        "retrieval_returned",
        "flat_yaml_fallback_used",
        "duplicate_search_owner",
    )
    accepted_input_type = StepResult
    output_type = StepResult

    def apply(self, input_obj: StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event(input_obj)
        new = state
        action = "model_retrieval_noop"
        reason = "Event does not change model-native retrieval."
        if event.kind == "load_bound_index":
            new = replace(state, bound_index_loaded=True)
            action = "bound_index_loaded"
            reason = "The current active index exposes exact card/model/mesh bindings."
        elif event.kind == "open_generation_read_session":
            new = replace(state, read_session_generation_current=True)
            action = "generation_read_session_opened"
            reason = "The read-only model and mesh stores are pinned to the current authority pointer digest."
        elif event.kind == "reuse_stale_read_session":
            new = replace(state, cross_generation_read_session_reused=True)
            action = "stale_generation_read_session_reused"
            reason = "Broken path: a read session from another authority pointer digest was reused."
        elif event.kind == "load_exact_revision":
            new = replace(state, exact_revision_loaded=True)
            action = "exact_revision_loaded"
            reason = "Retrieval loaded the exact bound revision without head substitution."
        elif event.kind == "materialize_neighborhood":
            new = replace(state, neighborhood_materialized=True)
            action = "bounded_neighborhood_materialized"
            reason = "The exact root-centered graph was materialized within hard budgets."
        elif event.kind == "return_retrieval":
            new = replace(state, retrieval_returned=True)
            action = "model_native_result_returned"
            reason = "The existing search facade returned the projection plus exact neighborhood."
        elif event.kind == "flat_yaml_fallback":
            new = replace(state, flat_yaml_fallback_used=True)
            action = "flat_yaml_fallback_used"
            reason = "Broken path: retrieval bypassed current model/index authority."
        elif event.kind == "duplicate_search_owner":
            new = replace(state, duplicate_search_owner=True)
            action = "duplicate_search_owner_registered"
            reason = "Broken path: a second LogicGuard search API duplicated the existing facade."
        yield _result(event, action, state, new, reason)


class PublishAuthorityGenerationBlock:
    """Input x State -> Set(Output x State) for atomic cutover or rollback."""

    name = "PublishAuthorityGenerationBlock"
    reads = (
        "model_revision",
        "mesh_revision",
        "projection_published",
        "index_published",
        "zero_legacy_residuals",
        "prior_generation_authoritative",
    )
    writes = (
        "zero_legacy_residuals",
        "cross_scope_reference",
        "migration_failed",
        "prior_generation_authoritative",
        "generation_current",
        "projection_published",
        "index_published",
        "automations_paused",
        "done",
    )
    accepted_input_type = StepResult
    output_type = StepResult

    def apply(self, input_obj: StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event(input_obj)
        new = state
        action = "authority_publication_noop"
        reason = "Event does not change the authority pointer or rollback state."
        if event.kind == "verify_zero_residual":
            new = replace(state, zero_legacy_residuals=True)
            action = "zero_legacy_residual_verified"
            reason = "No normal-runtime legacy authority, fallback, or unbound current card remains."
        elif event.kind == "cross_scope_reference":
            new = replace(state, cross_scope_reference=True)
            action = "cross_scope_reference_detected"
            reason = "Broken path: public/candidate authority referenced private graph material."
        elif event.kind == "migration_failed":
            new = replace(state, migration_failed=True, automations_paused=True)
            action = "migration_failed_paused"
            reason = "A hard migration failure keeps retained automations paused."
        elif event.kind == "rollback_prior":
            new = replace(
                state,
                prior_generation_authoritative=True,
                generation_current=False,
                projection_published=False,
                index_published=False,
                automations_paused=True,
            )
            action = "prior_generation_restored"
            reason = "Rollback restored the prior complete generation without a dual runtime."
        elif event.kind == "mark_current":
            new = replace(
                state,
                generation_current=True,
                prior_generation_authoritative=False,
                automations_paused=False,
                done=True,
            )
            action = "logicguard_generation_current"
            reason = "The complete exact model/mesh/projection/index generation became current."
        elif event.kind == "finish_readonly":
            new = replace(state, done=True)
            action = "readonly_operation_finished"
            reason = "Read-only Dream or retrieval work reached a terminal state."
        elif event.kind == "finalize_blocked":
            new = replace(state, done=True, automations_paused=True)
            action = "cutover_blocked_terminal"
            reason = "The failed migration terminated with prior authority preserved and automations paused."
        yield _result(event, action, state, new, reason)


def build_workflow() -> Workflow:
    return Workflow(
        (
            BindCardModelBlock(),
            ValidateCardBindingBlock(),
            PlanSleepModelChangeBlock(),
            CommitSleepModelChangeBlock(),
            ValidateDreamMeshBlock(),
            RetrieveModelNeighborhoodBlock(),
            PublishAuthorityGenerationBlock(),
        ),
        name=MODEL_ID,
    )


def exact_current_authority(state: State, _trace: object) -> InvariantResult:
    if state.generation_current and not (
        state.model_revision
        and state.mesh_revision
        and state.projection_validated
        and state.projection_published
        and state.index_published
        and state.zero_legacy_residuals
    ):
        return InvariantResult.fail("Current generation lacks exact complete model/mesh/projection/index authority.")
    if state.projection_digest_mismatch or state.head_substitution_used or state.legacy_reader_active:
        return InvariantResult.fail("Exact binding was replaced by mismatched, floating-head, or legacy authority.")
    return InvariantResult.pass_()


def model_first_publication(state: State, _trace: object) -> InvariantResult:
    if state.mesh_revision and not state.model_revision:
        return InvariantResult.fail("Mesh committed before its exact card model revision.")
    if state.projection_published and not (
        state.model_revision and state.mesh_revision and state.projection_validated
    ):
        return InvariantResult.fail("Projection published before exact model/mesh commit and validation.")
    if state.index_published and not state.projection_published:
        return InvariantResult.fail("Active index published before the verified projection generation.")
    return InvariantResult.pass_()


def sole_owner_boundaries(state: State, _trace: object) -> InvariantResult:
    if state.model_commit_without_owner or state.unauthorized_authority_write:
        return InvariantResult.fail("Canonical authority changed outside migration or the existing Sleep owner.")
    if state.duplicate_sleep_owner or state.duplicate_search_owner:
        return InvariantResult.fail("A parallel Sleep or search authority duplicated an existing Khaos owner.")
    if state.dream_mutated_authority:
        return InvariantResult.fail("Dream mutated canonical authority instead of emitting evidence and a handoff.")
    return InvariantResult.pass_()


def dream_exact_read_only(state: State, _trace: object) -> InvariantResult:
    if state.dream_simulated and (
        not state.dream_pinned_revision or state.dream_pinned_revision != state.mesh_revision
    ):
        return InvariantResult.fail("Dream simulation did not consume the exact pinned mesh revision.")
    if state.dream_handoff_published and not state.dream_simulated:
        return InvariantResult.fail("Dream published a Sleep handoff without a completed exact simulation.")
    return InvariantResult.pass_()


def retrieval_model_native(state: State, _trace: object) -> InvariantResult:
    if state.flat_yaml_fallback_used:
        return InvariantResult.fail("Foreground retrieval used a flat YAML fallback.")
    if state.retrieval_returned and not (
        state.generation_current
        and state.bound_index_loaded
        and state.read_session_generation_current
        and state.exact_revision_loaded
        and state.neighborhood_materialized
    ):
        return InvariantResult.fail("Retrieval returned before exact current model-neighborhood authority was ready.")
    if state.cross_generation_read_session_reused:
        return InvariantResult.fail(
            "Retrieval reused a pinned read session across authority-generation digests."
        )
    return InvariantResult.pass_()


def privacy_scope_closed(state: State, _trace: object) -> InvariantResult:
    if state.cross_scope_reference:
        return InvariantResult.fail("A scoped model, mesh, projection, or retrieval result crossed privacy authority.")
    return InvariantResult.pass_()


def migration_atomic_or_blocked(state: State, _trace: object) -> InvariantResult:
    if state.done and state.cutover_started and not state.generation_current:
        if not (
            state.migration_failed
            and state.prior_generation_authoritative
            and state.automations_paused
            and not state.projection_published
            and not state.index_published
        ):
            return InvariantResult.fail("Cutover ended without a complete current generation or safe paused rollback.")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "exact_current_authority",
        "Every current card generation binds exact model, mesh, projection, index, and zero-residual authority.",
        exact_current_authority,
    ),
    Invariant(
        "model_first_publication",
        "Canonical model and mesh commit and projection validation precede projection/index publication.",
        model_first_publication,
    ),
    Invariant(
        "sole_owner_boundaries",
        "Migration/Sleep are the only authority writers; Dream and search remain their existing read/handoff owners.",
        sole_owner_boundaries,
    ),
    Invariant(
        "dream_exact_read_only",
        "Dream pins and simulates one exact mesh revision and can publish only a typed handoff.",
        dream_exact_read_only,
    ),
    Invariant(
        "retrieval_model_native",
        "Retrieval returns only from exact current bound index and bounded model neighborhood authority.",
        retrieval_model_native,
    ),
    Invariant(
        "privacy_scope_closed",
        "Scoped canonical graphs and projections do not cross public/private/candidate authority.",
        privacy_scope_closed,
    ),
    Invariant(
        "migration_atomic_or_blocked",
        "Migration ends either current and complete or rolled back to one prior generation with automations paused.",
        migration_atomic_or_blocked,
    ),
)


CONTRACTS = (
    FunctionContract(
        "BindCardModelBlock",
        accepted_input_type=Event,
        output_type=StepResult,
        reads=BindCardModelBlock.reads,
        writes=BindCardModelBlock.writes,
        idempotency_rule="Stable model ids and transaction keys make repeated matching input no-delta.",
        traceability_rule="Every model commit binds migration or existing Sleep ownership.",
    ),
    FunctionContract(
        "ValidateCardBindingBlock",
        accepted_input_type=StepResult,
        output_type=StepResult,
        reads=ValidateCardBindingBlock.reads,
        writes=ValidateCardBindingBlock.writes,
        forbidden_writes=("model_revision", "mesh_revision", "index_published"),
        idempotency_rule="Exact validation is read-only for canonical authority.",
        traceability_rule="Validation exposes mismatch and head-substitution failures.",
    ),
    FunctionContract(
        "PlanSleepModelChangeBlock",
        accepted_input_type=StepResult,
        output_type=StepResult,
        reads=PlanSleepModelChangeBlock.reads,
        writes=PlanSleepModelChangeBlock.writes,
        forbidden_writes=("model_revision", "mesh_revision", "projection_published", "index_published"),
        idempotency_rule="Planning cannot publish authority.",
        traceability_rule="Duplicate Sleep ownership is an explicit model failure.",
    ),
    FunctionContract(
        "CommitSleepModelChangeBlock",
        accepted_input_type=StepResult,
        output_type=StepResult,
        reads=CommitSleepModelChangeBlock.reads,
        writes=CommitSleepModelChangeBlock.writes,
        idempotency_rule="CAS and idempotency keys prevent duplicate semantic generations.",
        traceability_rule="Model-first publication labels every authority boundary.",
    ),
    FunctionContract(
        "ValidateDreamMeshBlock",
        accepted_input_type=StepResult,
        output_type=StepResult,
        reads=ValidateDreamMeshBlock.reads,
        writes=ValidateDreamMeshBlock.writes,
        forbidden_writes=("model_revision", "mesh_revision", "projection_published", "index_published"),
        idempotency_rule="Stable evidence fingerprints suppress repeated terminal experiments.",
        traceability_rule="Simulation and handoff retain the exact pinned mesh revision.",
    ),
    FunctionContract(
        "RetrieveModelNeighborhoodBlock",
        accepted_input_type=StepResult,
        output_type=StepResult,
        reads=RetrieveModelNeighborhoodBlock.reads,
        writes=RetrieveModelNeighborhoodBlock.writes,
        forbidden_writes=("model_revision", "mesh_revision", "projection_published", "index_published"),
        idempotency_rule="Exact query and authority inputs produce deterministic bounded results.",
        traceability_rule="Every result exposes binding and neighborhood steps.",
    ),
    FunctionContract(
        "PublishAuthorityGenerationBlock",
        accepted_input_type=StepResult,
        output_type=StepResult,
        reads=PublishAuthorityGenerationBlock.reads,
        writes=PublishAuthorityGenerationBlock.writes,
        idempotency_rule="The authority pointer changes only after one complete generation or safe rollback.",
        traceability_rule="Terminal labels distinguish current, read-only, and blocked rollback outcomes.",
    ),
)


CUTOVER_SEQUENCE = (
    Event("begin_cutover"),
    Event("commit_model"),
    Event("commit_mesh"),
    Event("validate_projection"),
    Event("publish_projection"),
    Event("publish_index"),
    Event("verify_zero_residual"),
    Event("mark_current"),
)

DREAM_SEQUENCE = (
    Event("pin_dream_mesh"),
    Event("simulate_dream"),
    Event("publish_dream_handoff"),
    Event("finish_readonly"),
)

RETRIEVAL_SEQUENCE = (
    Event("load_bound_index"),
    Event("open_generation_read_session"),
    Event("load_exact_revision"),
    Event("materialize_neighborhood"),
    Event("return_retrieval"),
    Event("finish_readonly"),
)

SAFE_ROLLBACK_SEQUENCE = (
    Event("begin_cutover"),
    Event("commit_model"),
    Event("migration_failed"),
    Event("rollback_prior"),
    Event("finalize_blocked"),
)

KNOWN_BADS: dict[str, tuple[State, tuple[Event, ...]]] = {
    "standalone_yaml_authority": (CURRENT_STATE, (Event("legacy_reader_used"),)),
    "projection_before_model": (State(), (Event("publish_projection"),)),
    "index_before_projection": (State(), (Event("publish_index"),)),
    "partial_migration_marked_current": (
        State(),
        (Event("begin_cutover"), Event("commit_model"), Event("mark_current")),
    ),
    "unowned_model_writer": (State(), (Event("commit_model"),)),
    "duplicate_sleep_owner": (CURRENT_STATE, (Event("duplicate_sleep_owner"),)),
    "duplicate_search_owner": (CURRENT_STATE, (Event("duplicate_search_owner"),)),
    "dream_mutates_authority": (
        CURRENT_STATE,
        (Event("pin_dream_mesh"), Event("simulate_dream"), Event("dream_mutates_authority")),
    ),
    "dream_handoff_without_simulation": (
        CURRENT_STATE,
        (Event("pin_dream_mesh"), Event("publish_dream_handoff")),
    ),
    "flat_yaml_retrieval_fallback": (CURRENT_STATE, (Event("flat_yaml_fallback"),)),
    "floating_head_substitution": (CURRENT_STATE, (Event("head_substitution"),)),
    "projection_digest_mismatch": (CURRENT_STATE, (Event("projection_digest_mismatch"),)),
    "private_cross_scope_reference": (CURRENT_STATE, (Event("cross_scope_reference"),)),
    "retrieval_without_neighborhood": (
        CURRENT_STATE,
        (
            Event("load_bound_index"),
            Event("open_generation_read_session"),
            Event("load_exact_revision"),
            Event("return_retrieval"),
        ),
    ),
    "cross_generation_read_session_reuse": (
        CURRENT_STATE,
        (
            Event("load_bound_index"),
            Event("reuse_stale_read_session"),
            Event("load_exact_revision"),
            Event("materialize_neighborhood"),
            Event("return_retrieval"),
        ),
    ),
}


def _scenario_summary(run: ScenarioRun) -> dict[str, object]:
    payload = run.to_dict()
    labels = sorted(
        {
            label
            for trace in payload.get("traces", []) or []
            for label in trace.get("labels", [])
        }
    )
    return {
        "observed_status": payload.get("observed_status"),
        "model_ok": payload.get("model_report", {}).get("ok"),
        "violation_names": payload.get("observed_violation_names", []),
        "labels_seen": labels,
        "final_states": payload.get("final_states", []),
    }


def _contract_summary(runs: tuple[ScenarioRun, ...]) -> dict[str, object]:
    reports = [
        check_trace_contracts(trace, CONTRACTS)
        for run in runs
        for trace in run.traces
    ]
    return {
        "ok": all(report.ok for report in reports),
        "checked_steps": sum(report.checked_steps for report in reports),
        "violation_count": sum(len(report.violations) for report in reports),
        "summaries": [report.summary for report in reports],
    }


def _progress_transition(state: State) -> Iterable[tuple[str, State]]:
    if state.done:
        return
    if not state.cutover_started:
        yield "begin_cutover", replace(state, cutover_started=True, automations_paused=True)
    elif not state.model_revision:
        yield "commit_model", replace(state, model_revision="model-revision:new")
    elif not state.mesh_revision:
        yield "commit_mesh", replace(state, mesh_revision="mesh-revision:new")
    elif not state.projection_validated:
        yield "validate_projection", replace(state, projection_validated=True)
    elif not state.projection_published:
        yield "publish_projection", replace(state, projection_published=True)
    elif not state.index_published:
        yield "publish_index", replace(state, index_published=True)
    elif not state.zero_legacy_residuals:
        yield "verify_zero_residual", replace(state, zero_legacy_residuals=True)
    else:
        yield "mark_current", replace(
            state,
            generation_current=True,
            prior_generation_authoritative=False,
            automations_paused=False,
            done=True,
        )


def _remaining_steps(state: State) -> int:
    return sum(
        (
            not state.cutover_started,
            not bool(state.model_revision),
            not bool(state.mesh_revision),
            not state.projection_validated,
            not state.projection_published,
            not state.index_published,
            not state.zero_legacy_residuals,
            not state.done,
        )
    )


def _loop_and_progress() -> tuple[dict[str, object], dict[str, object]]:
    loop = check_loops(
        LoopCheckConfig(
            initial_states=(State(),),
            transition_fn=_progress_transition,
            is_terminal=lambda state: state.done,
            is_success=lambda state: state.generation_current,
            required_success=True,
            max_depth=8,
            max_states=16,
        )
    )
    progress = check_progress(
        ProgressCheckConfig(
            initial_states=(State(),),
            transition_fn=_progress_transition,
            is_terminal=lambda state: state.done,
            is_success=lambda state: state.generation_current,
            ranking_fn=_remaining_steps,
            bounded_eventually=(
                BoundedEventuallyProperty(
                    "cutover_reaches_current_generation",
                    trigger=lambda state: not state.done,
                    target=lambda state: state.generation_current,
                    description="A valid cutover reaches one complete current generation within eight steps.",
                    max_steps=8,
                ),
            ),
            max_depth=8,
            max_states=16,
        )
    )
    loop_payload = loop.to_dict()
    progress_payload = progress.to_dict()
    return (
        {
            "ok": loop.ok,
            "graph_summary": loop_payload.get("graph_summary"),
            "stuck_state_count": len(loop_payload.get("stuck_states", []) or []),
            "non_terminating_component_count": len(
                loop_payload.get("non_terminating_components", []) or []
            ),
            "unreachable_success": loop_payload.get("unreachable_success"),
        },
        {
            "ok": progress.ok,
            "graph_summary": progress_payload.get("graph_summary"),
            "finding_count": len(progress_payload.get("findings", []) or []),
            "findings": progress_payload.get("findings", []),
        },
    )


def _refinement_summary(final_state: State) -> dict[str, object]:
    expected = {
        "authority": "logicguard-current",
        "projection": "verified",
        "retrieval": "model-bound-index",
    }

    def project(state: State) -> dict[str, str]:
        return {
            "authority": "logicguard-current" if state.generation_current else "not-current",
            "projection": "verified" if state.projection_validated else "unverified",
            "retrieval": "model-bound-index" if state.index_published else "unavailable",
        }

    report = check_refinement_projection(
        expected_abstract_state=expected,
        real_state=final_state,
        projection=project,
        function_name="khaos_brain_current_generation_projection",
    )
    return {
        "ok": report.ok,
        "checked_steps": report.checked_steps,
        "violation_count": len(report.violations),
        "summary": report.summary,
    }


def main() -> int:
    workflow = build_workflow()
    cutover = run_exact_sequence(workflow, State(), CUTOVER_SEQUENCE, invariants=INVARIANTS)
    dream = run_exact_sequence(workflow, CURRENT_STATE, DREAM_SEQUENCE, invariants=INVARIANTS)
    retrieval = run_exact_sequence(workflow, CURRENT_STATE, RETRIEVAL_SEQUENCE, invariants=INVARIANTS)
    rollback = run_exact_sequence(workflow, State(), SAFE_ROLLBACK_SEQUENCE, invariants=INVARIANTS)
    bad_runs = {
        name: run_exact_sequence(workflow, initial, sequence, invariants=INVARIANTS)
        for name, (initial, sequence) in KNOWN_BADS.items()
    }
    bad_rejected = {name: run.observed_status != "ok" for name, run in bad_runs.items()}
    contracts = _contract_summary((cutover, dream, retrieval, rollback))
    loop, progress = _loop_and_progress()
    final_state = cutover.final_states[0] if cutover.final_states else State()
    refinement = _refinement_summary(final_state)

    checks = {
        "cutover_sequence_passes": cutover.observed_status == "ok",
        "dream_readonly_sequence_passes": dream.observed_status == "ok",
        "retrieval_sequence_passes": retrieval.observed_status == "ok",
        "safe_rollback_sequence_passes": rollback.observed_status == "ok",
        "all_known_bad_variants_rejected": all(bad_rejected.values()),
        "function_contracts_pass": contracts["ok"],
        "loop_and_stuck_review_pass": loop["ok"],
        "progress_and_bounded_eventually_pass": progress["ok"],
        "refinement_projection_pass": refinement["ok"],
    }
    payload = {
        "artifact_type": "khaos_brain_logicguard_authority_cutover_flowguard_report",
        "model_id": MODEL_ID,
        "function_blocks": [block.name for block in workflow.blocks],
        "existing_owner_handoffs": {
            "lifecycle_and_index": "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
            "sleep_dream_governance": "khaos_brain_governance_flow.GovernanceBlock",
            "retrieval_facade": "local_kb.search.search_with_receipt",
            "desktop_projection": "card_visual_merge_flow.ProductionVisualMergeBlock",
            "argument_runtime": "logicguard-p0-p2-runtime",
        },
        "checks": checks,
        "correct": {
            "cutover": _scenario_summary(cutover),
            "dream": _scenario_summary(dream),
            "retrieval": _scenario_summary(retrieval),
            "rollback": _scenario_summary(rollback),
        },
        "known_bad_rejections": bad_rejected,
        "known_bad": {name: _scenario_summary(run) for name, run in bad_runs.items()},
        "contracts": contracts,
        "loop_review": loop,
        "progress_review": progress,
        "refinement": refinement,
        "claim_boundary": (
            "This executable child model proves the declared abstract authority-cutover, ownership, "
            "ordering, privacy, fallback, Dream, retrieval, rollback, progress, contract, and refinement "
            "properties only. It does not prove production implementation, migration, UI, package, "
            "SkillGuard, performance, or release readiness."
        ),
        "ok": all(checks.values()),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
