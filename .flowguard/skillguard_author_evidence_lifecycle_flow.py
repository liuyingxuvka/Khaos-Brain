"""FlowGuard model for the bounded SkillGuard author-control refresh.

This is a development-process model.  It does not execute or model the domain
behavior of Sleep, Dream, organization maintenance, contribution, or manual
software update.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Iterable

from flowguard import (
    FunctionContract,
    FunctionResult,
    Invariant,
    InvariantResult,
    LoopCheckConfig,
    Workflow,
    check_loops,
    check_trace_contracts,
    run_exact_sequence,
)


EXPECTED_UNIT_COUNT = 5
EXPECTED_CHECK_COUNT = 25


@dataclass(frozen=True)
class Event:
    kind: str


@dataclass(frozen=True)
class StepResult:
    event: Event
    action: str


@dataclass(frozen=True)
class State:
    peer_writer_clear: bool = False
    protected_hash_intact: bool = True
    unit_count: int = 0
    check_count: int = 0
    openspec_recorded: bool = False
    flowguard_current: bool = False
    author_adopted: bool = False
    generated_contracts_current: bool = False
    source_only_checks_passed: bool = False
    isolated_evidence_root: bool = False
    evidence_audit_passed: bool = False
    gc_plan_ready: bool = False
    target_business_wrapper_run: bool = False
    kb_business_evidence_touched: bool = False
    evidence_gc_mutated: bool = False
    closure_status: str = "open"

    def boundaries_frozen(self) -> bool:
        return (
            self.peer_writer_clear
            and self.protected_hash_intact
            and self.unit_count == EXPECTED_UNIT_COUNT
            and self.check_count == EXPECTED_CHECK_COUNT
        )

    def author_refresh_complete(self) -> bool:
        return (
            self.boundaries_frozen()
            and self.openspec_recorded
            and self.flowguard_current
            and self.author_adopted
            and self.generated_contracts_current
            and self.source_only_checks_passed
            and self.isolated_evidence_root
            and self.evidence_audit_passed
            and self.gc_plan_ready
            and not self.target_business_wrapper_run
            and not self.kb_business_evidence_touched
            and not self.evidence_gc_mutated
        )


class BoundaryFreezeBlock:
    """Input x State -> Set(Output x State) for ownership and scope gates."""

    name = "BoundaryFreezeBlock"
    reads = ("peer_writer_clear", "protected_hash_intact", "unit_count", "check_count")
    writes = ("peer_writer_clear", "protected_hash_intact", "unit_count", "check_count", "openspec_recorded", "flowguard_current")
    accepted_input_type = Event
    output_description = "StepResult"
    idempotency = "Repeated current boundary observations converge without broadening scope."

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        event = input_obj
        updates = {
            "peer_writer_clear": {"peer_writer_clear": True},
            "protected_hash_changed": {"protected_hash_intact": False},
            "freeze_inventory": {"unit_count": EXPECTED_UNIT_COUNT, "check_count": EXPECTED_CHECK_COUNT},
            "change_check_inventory": {"check_count": EXPECTED_CHECK_COUNT + 1},
            "record_openspec": {"openspec_recorded": True},
            "upgrade_flowguard": {"flowguard_current": True},
        }
        if event.kind in updates:
            yield FunctionResult(
                output=StepResult(event, event.kind),
                new_state=replace(state, **updates[event.kind]),
                label=event.kind,
                reason="Boundary observation was recorded through its sole development-process owner.",
            )
            return
        yield FunctionResult(output=StepResult(event, "boundary_noop"), new_state=state, label="boundary_noop")


class AuthorRefreshBlock:
    """Input x State -> Set(Output x State) for author-only SkillGuard work."""

    name = "AuthorRefreshBlock"
    reads = ("peer_writer_clear", "protected_hash_intact", "unit_count", "check_count", "author_adopted", "generated_contracts_current")
    writes = ("author_adopted", "generated_contracts_current", "source_only_checks_passed", "target_business_wrapper_run", "kb_business_evidence_touched")
    accepted_input_type = StepResult
    output_description = "StepResult"
    idempotency = "Current author adoption and deterministic compilation converge for unchanged inputs."

    def apply(self, input_obj: StepResult, state: State) -> Iterable[FunctionResult]:
        event = input_obj.event
        if event.kind == "adopt_author":
            if state.boundaries_frozen():
                yield FunctionResult(output=StepResult(event, "author_adopted"), new_state=replace(state, author_adopted=True), label="author_adopted")
            else:
                yield FunctionResult(output=StepResult(event, "author_adoption_blocked"), new_state=state, label="author_adoption_blocked")
            return
        if event.kind == "regenerate_contracts":
            ready = state.author_adopted and state.check_count == EXPECTED_CHECK_COUNT
            yield FunctionResult(output=StepResult(event, "contracts_current" if ready else "contract_regeneration_blocked"), new_state=replace(state, generated_contracts_current=ready), label="contracts_current" if ready else "contract_regeneration_blocked")
            return
        if event.kind == "source_only_checks":
            ready = state.generated_contracts_current and state.check_count == EXPECTED_CHECK_COUNT
            yield FunctionResult(output=StepResult(event, "source_only_checks_passed" if ready else "source_only_checks_blocked"), new_state=replace(state, source_only_checks_passed=ready), label="source_only_checks_passed" if ready else "source_only_checks_blocked")
            return
        if event.kind == "run_target_business_wrapper":
            yield FunctionResult(output=StepResult(event, "forbidden_target_wrapper"), new_state=replace(state, target_business_wrapper_run=True), label="forbidden_target_wrapper")
            return
        if event.kind == "touch_kb_business_evidence":
            yield FunctionResult(output=StepResult(event, "forbidden_kb_write"), new_state=replace(state, kb_business_evidence_touched=True), label="forbidden_kb_write")
            return
        yield FunctionResult(output=input_obj, new_state=state, label="author_refresh_noop")


class EvidenceLifecycleBlock:
    """Input x State -> Set(Output x State) for isolated read-only evidence lifecycle."""

    name = "EvidenceLifecycleBlock"
    reads = ("source_only_checks_passed", "isolated_evidence_root", "evidence_audit_passed", "gc_plan_ready")
    writes = ("isolated_evidence_root", "evidence_audit_passed", "gc_plan_ready", "evidence_gc_mutated", "closure_status")
    accepted_input_type = StepResult
    output_description = "StepResult"
    idempotency = "Read-only audit and planning converge on the same evidence snapshot."

    def apply(self, input_obj: StepResult, state: State) -> Iterable[FunctionResult]:
        event = input_obj.event
        if event.kind == "select_isolated_evidence_root":
            yield FunctionResult(output=StepResult(event, "isolated_evidence_root"), new_state=replace(state, isolated_evidence_root=True), label="isolated_evidence_root")
            return
        if event.kind == "evidence_audit":
            passed = state.isolated_evidence_root
            yield FunctionResult(output=StepResult(event, "evidence_audit_passed" if passed else "evidence_audit_blocked"), new_state=replace(state, evidence_audit_passed=passed), label="evidence_audit_passed" if passed else "evidence_audit_blocked")
            return
        if event.kind == "evidence_gc_plan":
            ready = state.isolated_evidence_root and state.evidence_audit_passed
            yield FunctionResult(output=StepResult(event, "gc_plan_ready" if ready else "gc_plan_blocked"), new_state=replace(state, gc_plan_ready=ready), label="gc_plan_ready" if ready else "gc_plan_blocked")
            return
        if event.kind in {"evidence_gc_apply", "evidence_gc_purge"}:
            yield FunctionResult(output=StepResult(event, "forbidden_evidence_mutation"), new_state=replace(state, evidence_gc_mutated=True), label="forbidden_evidence_mutation")
            return
        if event.kind == "close":
            closed = state.author_refresh_complete()
            yield FunctionResult(output=StepResult(event, "closed" if closed else "closure_blocked"), new_state=replace(state, closure_status="closed" if closed else "blocked"), label="closed" if closed else "closure_blocked")
            return
        yield FunctionResult(output=input_obj, new_state=state, label="evidence_lifecycle_noop")


def build_workflow() -> Workflow:
    return Workflow((BoundaryFreezeBlock(), AuthorRefreshBlock(), EvidenceLifecycleBlock()), name="skillguard_author_evidence_lifecycle")


def protected_boundary_holds(state: State, trace: object) -> InvariantResult:
    if not state.protected_hash_intact:
        return InvariantResult.fail("protected KB model fingerprint changed")
    if state.target_business_wrapper_run:
        return InvariantResult.fail("a target business maintenance wrapper was run")
    if state.kb_business_evidence_touched:
        return InvariantResult.fail("KB business evidence was touched")
    if state.evidence_gc_mutated:
        return InvariantResult.fail("evidence was quarantined or purged without separate authority")
    return InvariantResult.pass_()


def check_inventory_is_exact(state: State, trace: object) -> InvariantResult:
    if state.author_adopted and (state.unit_count != EXPECTED_UNIT_COUNT or state.check_count != EXPECTED_CHECK_COUNT):
        return InvariantResult.fail("author adoption changed the five-unit/twenty-five-check boundary")
    return InvariantResult.pass_()


def closure_requires_current_evidence(state: State, trace: object) -> InvariantResult:
    if state.closure_status == "closed" and not state.author_refresh_complete():
        return InvariantResult.fail("closure was licensed without current bounded author evidence")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("protected_boundary_holds", "No target business work or protected KB mutation occurs.", protected_boundary_holds),
    Invariant("check_inventory_is_exact", "SkillGuard preserves the target-declared 5/25 inventory.", check_inventory_is_exact),
    Invariant("closure_requires_current_evidence", "Closure requires current author and read-only lifecycle evidence.", closure_requires_current_evidence),
)


CONTRACTS = (
    FunctionContract(
        function_name="BoundaryFreezeBlock",
        accepted_input_type=Event,
        output_type=StepResult,
        writes=BoundaryFreezeBlock.writes,
        forbidden_writes=("author_adopted", "generated_contracts_current", "source_only_checks_passed", "target_business_wrapper_run", "kb_business_evidence_touched", "evidence_gc_mutated", "closure_status"),
    ),
    FunctionContract(
        function_name="AuthorRefreshBlock",
        accepted_input_type=StepResult,
        output_type=StepResult,
        writes=AuthorRefreshBlock.writes,
        forbidden_writes=("unit_count", "check_count", "openspec_recorded", "flowguard_current", "isolated_evidence_root", "evidence_audit_passed", "gc_plan_ready", "evidence_gc_mutated", "closure_status"),
    ),
    FunctionContract(
        function_name="EvidenceLifecycleBlock",
        accepted_input_type=StepResult,
        output_type=StepResult,
        writes=EvidenceLifecycleBlock.writes,
        forbidden_writes=("unit_count", "check_count", "author_adopted", "generated_contracts_current", "source_only_checks_passed", "target_business_wrapper_run", "kb_business_evidence_touched"),
    ),
)


ACCEPTED_SEQUENCE = tuple(Event(kind) for kind in (
    "peer_writer_clear",
    "freeze_inventory",
    "record_openspec",
    "upgrade_flowguard",
    "adopt_author",
    "regenerate_contracts",
    "source_only_checks",
    "select_isolated_evidence_root",
    "evidence_audit",
    "evidence_gc_plan",
    "close",
))


def _run(sequence: tuple[Event, ...]):
    return run_exact_sequence(build_workflow(), State(), sequence, invariants=INVARIANTS)


def _has_label(run: object, label: str) -> bool:
    return any(trace.has_label(label) for trace in run.traces)


def _progress(state: State):
    order = (
        (not state.peer_writer_clear, "peer_writer_clear"),
        (state.unit_count != EXPECTED_UNIT_COUNT or state.check_count != EXPECTED_CHECK_COUNT, "freeze_inventory"),
        (not state.openspec_recorded, "record_openspec"),
        (not state.flowguard_current, "upgrade_flowguard"),
        (not state.author_adopted, "adopt_author"),
        (not state.generated_contracts_current, "regenerate_contracts"),
        (not state.source_only_checks_passed, "source_only_checks"),
        (not state.isolated_evidence_root, "select_isolated_evidence_root"),
        (not state.evidence_audit_passed, "evidence_audit"),
        (not state.gc_plan_ready, "evidence_gc_plan"),
        (state.closure_status != "closed", "close"),
    )
    for needed, kind in order:
        if needed:
            result = build_workflow().execute(state, Event(kind)).completed_paths[0]
            yield kind, result.state
            return


def main() -> int:
    accepted = _run(ACCEPTED_SEQUENCE)
    altered_inventory = _run((Event("peer_writer_clear"), Event("freeze_inventory"), Event("change_check_inventory"), Event("adopt_author")))
    business_wrapper = _run((Event("run_target_business_wrapper"),))
    business_write = _run((Event("touch_kb_business_evidence"),))
    gc_apply = _run((Event("evidence_gc_apply"),))
    protected_change = _run((Event("protected_hash_changed"),))
    contracts = [check_trace_contracts(trace, CONTRACTS) for trace in accepted.traces]
    loop = check_loops(
        LoopCheckConfig(
            initial_states=(State(),),
            transition_fn=_progress,
            is_terminal=lambda state: state.closure_status == "closed",
            is_success=lambda state: state.closure_status == "closed",
            required_success=True,
            max_depth=12,
            max_states=32,
            report_terminal_outgoing=False,
        )
    )
    questions = {
        "accepted_refresh_closes": accepted.observed_status == "ok" and _has_label(accepted, "closed"),
        "check_inventory_change_is_rejected": (
            _has_label(altered_inventory, "author_adoption_blocked")
            and not _has_label(altered_inventory, "author_adopted")
        ),
        "target_business_wrapper_is_rejected": business_wrapper.observed_status != "ok",
        "kb_business_write_is_rejected": business_write.observed_status != "ok",
        "evidence_gc_mutation_is_rejected": gc_apply.observed_status != "ok",
        "protected_hash_change_is_rejected": protected_change.observed_status != "ok",
        "function_contracts_hold": all(report.ok for report in contracts),
        "progress_reaches_bounded_closure": loop.ok,
    }
    result = {
        "model": "skillguard_author_evidence_lifecycle_flow",
        "flowguard_schema_version": "1.0",
        "expected_maintenance_units": EXPECTED_UNIT_COUNT,
        "expected_declared_checks": EXPECTED_CHECK_COUNT,
        "question_results": questions,
        "accepted_status": accepted.observed_status,
        "loop_summary": loop.to_dict().get("graph_summary", {}),
        "claim_boundary": "Development-process proof only; no KB business maintenance, installed consumer activation, release, or native scheduled/manual completion is claimed.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(questions.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
