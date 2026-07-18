"""FlowGuard model for bounded predictive-KB postflight terminality.

The active task owns one short history-intake transaction.  Sleep owns every
later lifecycle, candidate, LogicGuard, and active-index mutation.  Each
transition is ``Input x State -> Set(Output x State)``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Workflow,
    run_exact_sequence,
)
from flowguard.explorer import Explorer


@dataclass(frozen=True)
class PostflightInput:
    kind: str
    event_id_stable: bool = True
    durable_history_event_count: int = 1
    terminal_receipt_present: bool = True
    terminal_receipt_matches: bool = True
    lifecycle_replay_count: int = 0
    synchronous_admission_count: int = 0
    runtime_authority_unchanged: bool = True
    writer_lock_release_confirmed: bool = True
    duration_ms: float = 100.0
    terminal_budget_ms: float = 30_000.0
    interrupted: bool = False


@dataclass(frozen=True)
class PostflightOutput:
    status: str
    accepted_history_event_count: int
    deferred_owner: str
    input_obj: PostflightInput


@dataclass(frozen=True)
class PostflightState:
    terminal_statuses: tuple[str, ...] = ()


class PostflightTerminalBlock:
    name = "PostflightTerminalBlock"
    reads = ("terminal_statuses",)
    writes = ("terminal_statuses",)
    accepted_input_type = PostflightInput
    input_description = "one active-task observation-intake attempt"
    output_description = "success, failed, or timeout_unknown"
    idempotency = "caller-stable event id plus exact event fingerprint"

    def apply(
        self,
        input_obj: PostflightInput,
        state: PostflightState,
    ) -> Iterable[FunctionResult]:
        if input_obj.durable_history_event_count == 1 and (
            input_obj.interrupted
            or not input_obj.terminal_receipt_present
            or not input_obj.terminal_receipt_matches
        ):
            status = "timeout_unknown"
        else:
            success = bool(
                input_obj.event_id_stable
                and input_obj.durable_history_event_count == 1
                and input_obj.terminal_receipt_present
                and input_obj.terminal_receipt_matches
                and input_obj.lifecycle_replay_count == 0
                and input_obj.synchronous_admission_count == 0
                and input_obj.runtime_authority_unchanged
                and input_obj.writer_lock_release_confirmed
                and input_obj.duration_ms <= input_obj.terminal_budget_ms
                and not input_obj.interrupted
            )
            status = "success" if success else "failed"
        yield FunctionResult(
            output=PostflightOutput(
                status=status,
                accepted_history_event_count=min(
                    max(input_obj.durable_history_event_count, 0),
                    1,
                ),
                deferred_owner="kb-sleep",
                input_obj=input_obj,
            ),
            new_state=PostflightState((*state.terminal_statuses, status)),
            label=f"{input_obj.kind}__{status}",
            reason=(
                "active-task feedback owns one bounded durable history append; "
                "Sleep owns admission, candidate, model, and index publication"
            ),
        )


WORKFLOW = Workflow(
    (PostflightTerminalBlock(),),
    name="kb_postflight_terminal_flow",
)
INITIAL_STATES = (PostflightState(),)
INPUTS = (
    PostflightInput("bounded_success"),
    PostflightInput(
        "event_without_receipt",
        terminal_receipt_present=False,
        terminal_receipt_matches=False,
        interrupted=True,
    ),
    PostflightInput("duplicate_event", durable_history_event_count=2),
    PostflightInput("synchronous_lifecycle_replay", lifecycle_replay_count=2),
    PostflightInput("synchronous_admission", synchronous_admission_count=1),
    PostflightInput("authority_changed", runtime_authority_unchanged=False),
    PostflightInput("lock_not_released", writer_lock_release_confirmed=False),
    PostflightInput("budget_exceeded", duration_ms=30_001.0),
)


def success_is_fully_licensed(
    state: PostflightState,
    trace: object,
) -> InvariantResult:
    del state
    for step in getattr(trace, "steps", ()):
        output = getattr(step, "output", None)
        if not isinstance(output, PostflightOutput) or output.status != "success":
            continue
        item = output.input_obj
        if not (
            item.event_id_stable
            and item.durable_history_event_count == 1
            and item.terminal_receipt_present
            and item.terminal_receipt_matches
            and item.lifecycle_replay_count == 0
            and item.synchronous_admission_count == 0
            and item.runtime_authority_unchanged
            and item.writer_lock_release_confirmed
            and item.duration_ms <= item.terminal_budget_ms
            and not item.interrupted
        ):
            return InvariantResult.fail(
                "postflight success was claimed without the complete bounded terminal contract"
            )
    return InvariantResult.pass_()


def timeout_unknown_is_not_success(
    state: PostflightState,
    trace: object,
) -> InvariantResult:
    del state
    for step in getattr(trace, "steps", ()):
        output = getattr(step, "output", None)
        if not isinstance(output, PostflightOutput):
            continue
        item = output.input_obj
        if (
            item.durable_history_event_count == 1
            and (
                item.interrupted
                or not item.terminal_receipt_present
                or not item.terminal_receipt_matches
            )
            and output.status != "timeout_unknown"
        ):
            return InvariantResult.fail(
                "a persisted event without a matching terminal receipt was not classified timeout_unknown"
            )
    return InvariantResult.pass_()


def sleep_is_the_only_deferred_owner(
    state: PostflightState,
    trace: object,
) -> InvariantResult:
    del state
    for step in getattr(trace, "steps", ()):
        output = getattr(step, "output", None)
        if not isinstance(output, PostflightOutput):
            continue
        if output.deferred_owner != "kb-sleep":
            return InvariantResult.fail(
                "active-task postflight selected an alternate lifecycle owner"
            )
    return InvariantResult.pass_()


SUCCESS_LICENSED = Invariant(
    name="success_is_fully_licensed",
    description="Success requires one durable event, a matching receipt, unchanged authorities, no synchronous lifecycle work, released lock, and current budget.",
    predicate=success_is_fully_licensed,
)
TIMEOUT_UNKNOWN_VISIBLE = Invariant(
    name="timeout_unknown_is_not_success",
    description="A persisted event without its terminal receipt remains timeout_unknown.",
    predicate=timeout_unknown_is_not_success,
)
SOLE_DEFERRED_OWNER = Invariant(
    name="sleep_is_the_only_deferred_owner",
    description="Sleep is the sole normal-runtime owner of every later lifecycle/model/index stage.",
    predicate=sleep_is_the_only_deferred_owner,
)
INVARIANTS = (
    SUCCESS_LICENSED,
    TIMEOUT_UNKNOWN_VISIBLE,
    SOLE_DEFERRED_OWNER,
)


def _report_dict(report: object) -> dict[str, object]:
    if hasattr(report, "model_report"):
        report = report.model_report
    if hasattr(report, "to_dict"):
        return report.to_dict()
    return json.loads(report.to_json_text())


def _compact_report(report: object) -> dict[str, object]:
    payload = _report_dict(report)
    traces = payload.get("traces", []) or []
    return {
        "ok": payload.get("ok"),
        "summary": payload.get("summary"),
        "violation_count": len(payload.get("violations", []) or []),
        "reachability_failure_count": len(
            payload.get("reachability_failures", []) or []
        ),
        "labels_seen": sorted(
            {
                label
                for trace in traces
                for label in trace.get("labels", [])
            }
        ),
    }


def _run_sequence(input_obj: PostflightInput) -> dict[str, object]:
    report = run_exact_sequence(
        workflow=WORKFLOW,
        initial_state=PostflightState(),
        external_input_sequence=(input_obj,),
        invariants=INVARIANTS,
    )
    return _compact_report(report)


def main() -> int:
    required_labels = tuple(
        f"{item.kind}__"
        + (
            "timeout_unknown"
            if item.kind == "event_without_receipt"
            else "success"
            if item.kind == "bounded_success"
            else "failed"
        )
        for item in INPUTS
    )
    report = Explorer(
        workflow=WORKFLOW,
        initial_states=INITIAL_STATES,
        external_inputs=INPUTS,
        invariants=INVARIANTS,
        max_sequence_length=1,
        required_labels=required_labels,
    ).explore()
    scenarios = {item.kind: _run_sequence(item) for item in INPUTS}
    result = {
        "model": "kb_postflight_terminal_flow",
        "flowguard_schema_version": "1.0",
        "report": _compact_report(report),
        "scenarios": scenarios,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
