"""FlowGuard model for predictive KB postflight observation priority.

Risk purpose:
This FlowGuard model reviews the KB postflight decision rule introduced by the
`prioritize-kb-mistake-observations` OpenSpec change. It guards against two
specific regressions: Codex treating routine success evidence as equal priority
when a mistake/correction episode exists, and Codex suppressing useful success
observations while raising mistake evidence to highest priority. Future agents
should run this file when editing predictive KB postflight prompts or installer
checks. Companion command: `python .flowguard\\kb_postflight_priority_flow.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

from flowguard import (
    Explorer,
    FunctionResult,
    Invariant,
    InvariantResult,
    Workflow,
    run_exact_sequence,
)


@dataclass(frozen=True)
class PostflightEvidence:
    kind: str
    has_success: bool = False
    has_mistake: bool = False
    has_correction: bool = False


@dataclass(frozen=True)
class PostflightState:
    decisions: tuple[str, ...] = ()


@dataclass(frozen=True)
class PriorityDecision:
    selected_priority: str
    success_allowed: bool
    contrastive_required: bool
    evidence: PostflightEvidence


class PostflightPriorityBlock:
    """Input x State -> Set(Output x State) for KB postflight evidence selection."""

    name = "PostflightPriorityBlock"
    reads = ("decisions",)
    writes = ("decisions",)
    accepted_input_type = PostflightEvidence
    input_description = "PostflightEvidence"
    output_description = "PriorityDecision"
    idempotency = "Repeated postflight checks produce the same priority classification for the same evidence."

    def apply(self, input_obj: PostflightEvidence, state: PostflightState) -> Iterable[FunctionResult]:
        has_mistake_signal = input_obj.has_mistake or input_obj.has_correction
        selected_priority = "mistake" if has_mistake_signal else "success" if input_obj.has_success else "none"
        success_allowed = input_obj.has_success
        contrastive_required = input_obj.has_correction
        label_parts = [input_obj.kind, f"priority_{selected_priority}"]
        if success_allowed:
            label_parts.append("success_allowed")
        if contrastive_required:
            label_parts.append("contrastive_required")
        decision = PriorityDecision(
            selected_priority=selected_priority,
            success_allowed=success_allowed,
            contrastive_required=contrastive_required,
            evidence=input_obj,
        )
        yield FunctionResult(
            output=decision,
            new_state=PostflightState(state.decisions + (selected_priority,)),
            label="__".join(label_parts),
            reason="mistake and correction evidence outrank success evidence, while success remains recordable",
        )


WORKFLOW = Workflow((PostflightPriorityBlock(),), name="kb_postflight_priority_flow")
INITIAL_STATES = (PostflightState(),)
INPUTS = (
    PostflightEvidence("no_signal"),
    PostflightEvidence("success_only", has_success=True),
    PostflightEvidence("mistake_only", has_mistake=True),
    PostflightEvidence("correction_only", has_correction=True),
    PostflightEvidence("success_and_mistake", has_success=True, has_mistake=True),
    PostflightEvidence("success_and_correction", has_success=True, has_correction=True),
)


def mistake_signal_has_highest_priority(state: PostflightState, trace: object) -> InvariantResult:
    if not hasattr(trace, "steps"):
        return InvariantResult.pass_()
    for step in trace.steps:
        output = getattr(step, "output", None)
        if not isinstance(output, PriorityDecision):
            continue
        evidence = output.evidence
        if (evidence.has_mistake or evidence.has_correction) and output.selected_priority != "mistake":
            return InvariantResult.fail(
                "Mistake or correction evidence was not selected as the highest-priority KB postflight signal.",
                {"evidence_kind": evidence.kind, "selected_priority": output.selected_priority},
            )
    return InvariantResult.pass_()


def success_evidence_remains_allowed(state: PostflightState, trace: object) -> InvariantResult:
    if not hasattr(trace, "steps"):
        return InvariantResult.pass_()
    for step in trace.steps:
        output = getattr(step, "output", None)
        if not isinstance(output, PriorityDecision):
            continue
        if output.evidence.has_success and not output.success_allowed:
            return InvariantResult.fail(
                "Success evidence was suppressed even though reusable success observations must remain allowed.",
                {"evidence_kind": output.evidence.kind},
            )
    return InvariantResult.pass_()


def correction_requires_contrastive_fields(state: PostflightState, trace: object) -> InvariantResult:
    if not hasattr(trace, "steps"):
        return InvariantResult.pass_()
    for step in trace.steps:
        output = getattr(step, "output", None)
        if not isinstance(output, PriorityDecision):
            continue
        if output.evidence.has_correction and not output.contrastive_required:
            return InvariantResult.fail(
                "Correction evidence did not require contrastive fields.",
                {"evidence_kind": output.evidence.kind},
            )
    return InvariantResult.pass_()


MISTAKE_PRIORITY = Invariant(
    name="mistake_signal_has_highest_priority",
    description="Mistake, weak-path, missed-instruction, validation-failure, and correction evidence must outrank success evidence.",
    predicate=mistake_signal_has_highest_priority,
)
SUCCESS_ALLOWED = Invariant(
    name="success_evidence_remains_allowed",
    description="Successful reusable observations remain recordable even after mistake-first priority is introduced.",
    predicate=success_evidence_remains_allowed,
)
CORRECTION_CONTRASTIVE = Invariant(
    name="correction_requires_contrastive_fields",
    description="Correction episodes require contrastive previous/revised fields whenever possible.",
    predicate=correction_requires_contrastive_fields,
)


def _report_dict(report: object) -> dict[str, object]:
    if hasattr(report, "to_dict"):
        return report.to_dict()
    return json.loads(report.to_json_text())


def _compact_report(report: object) -> dict[str, object]:
    payload = _report_dict(report)
    traces = payload.get("traces", []) or []
    labels_seen = sorted({label for trace in traces for label in trace.get("labels", [])})
    return {
        "ok": payload.get("ok"),
        "summary": payload.get("summary"),
        "violation_count": len(payload.get("violations", []) or []),
        "reachability_failure_count": len(payload.get("reachability_failures", []) or []),
        "labels_seen": labels_seen,
    }


def _run_sequence(input_obj: PostflightEvidence) -> dict[str, object]:
    report = run_exact_sequence(
        workflow=WORKFLOW,
        initial_state=PostflightState(),
        external_input_sequence=(input_obj,),
        invariants=(MISTAKE_PRIORITY, SUCCESS_ALLOWED, CORRECTION_CONTRASTIVE),
    )
    return _compact_report(report)


def main() -> int:
    report = Explorer(
        workflow=WORKFLOW,
        initial_states=INITIAL_STATES,
        external_inputs=INPUTS,
        invariants=(MISTAKE_PRIORITY, SUCCESS_ALLOWED, CORRECTION_CONTRASTIVE),
        max_sequence_length=1,
        required_labels=(
            "success_only__priority_success__success_allowed",
            "mistake_only__priority_mistake",
            "correction_only__priority_mistake__contrastive_required",
            "success_and_mistake__priority_mistake__success_allowed",
            "success_and_correction__priority_mistake__success_allowed__contrastive_required",
        ),
    ).explore()
    scenarios = {item.kind: _run_sequence(item) for item in INPUTS}
    result = {
        "model": "kb_postflight_priority_flow",
        "flowguard_schema_version": "1.0",
        "report": _compact_report(report),
        "scenarios": scenarios,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
