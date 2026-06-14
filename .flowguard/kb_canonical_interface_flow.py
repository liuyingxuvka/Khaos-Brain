"""FlowGuard model for KB canonical machine interfaces and localized display projection."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Iterable

from flowguard import Explorer, FunctionResult, Invariant, InvariantResult, Workflow, run_exact_sequence


@dataclass(frozen=True)
class Event:
    kind: str


@dataclass(frozen=True)
class State:
    canonical_route: tuple[str, ...] = ("system", "knowledge-library", "retrieval")
    has_zh_cn_display: bool = False
    storage_unicode_preserved: bool = True
    cli_output_surface: str = "none"
    ui_output_surface: str = "none"
    raw_unicode_cli_output: bool = False
    canonical_route_mutated: bool = False


@dataclass(frozen=True)
class StepOutput:
    event: Event
    label: str


class CanonicalDataBlock:
    """Input x State -> Set(Output x State) for canonical card and route ownership."""

    name = "CanonicalDataBlock"
    reads = ("canonical_route", "has_zh_cn_display", "storage_unicode_preserved")
    writes = ("canonical_route", "has_zh_cn_display", "storage_unicode_preserved", "canonical_route_mutated")

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.kind == "create_canonical_card":
            yield FunctionResult(
                output=StepOutput(input_obj, "canonical_card_created"),
                new_state=state,
                label="canonical_card_created",
                reason="Card top-level fields and route remain English canonical data.",
            )
            return
        if input_obj.kind == "apply_zh_cn_display_plan":
            yield FunctionResult(
                output=StepOutput(input_obj, "zh_cn_display_added"),
                new_state=replace(state, has_zh_cn_display=True),
                label="zh_cn_display_added",
                reason="AI-authored display plan writes optional i18n.zh-CN data.",
            )
            return
        if input_obj.kind == "bad_translate_canonical_route":
            yield FunctionResult(
                output=StepOutput(input_obj, "canonical_route_mutated"),
                new_state=replace(state, canonical_route=("系统", "知识库", "检索"), canonical_route_mutated=True),
                label="canonical_route_mutated",
                reason="Broken path: localized labels were written back into canonical route fields.",
            )
            return
        yield FunctionResult(
            output=StepOutput(input_obj, "canonical_noop"),
            new_state=state,
            label="canonical_noop",
            reason="Event does not affect canonical storage.",
        )


class MachineCliBlock:
    """Input x State -> Set(Output x State) for CLI and automation machine output."""

    name = "MachineCliBlock"
    reads = ("has_zh_cn_display", "cli_output_surface")
    writes = ("cli_output_surface", "raw_unicode_cli_output")

    def apply(self, input_obj: Event | StepOutput, state: State) -> Iterable[FunctionResult]:
        event = input_obj.event if isinstance(input_obj, StepOutput) else input_obj
        if event.kind == "emit_machine_json":
            yield FunctionResult(
                output=StepOutput(event, "ascii_safe_machine_json"),
                new_state=replace(state, cli_output_surface="ascii_safe_json", raw_unicode_cli_output=False),
                label="ascii_safe_machine_json",
                reason="Machine JSON is serialized with ASCII-safe escaping at the console boundary.",
            )
            return
        if event.kind == "bad_emit_raw_localized_json":
            yield FunctionResult(
                output=StepOutput(event, "raw_unicode_cli_output"),
                new_state=replace(state, cli_output_surface="raw_localized_json", raw_unicode_cli_output=True),
                label="raw_unicode_cli_output",
                reason="Broken path: localized Unicode reached a Windows-hostile console boundary.",
            )
            return
        yield FunctionResult(
            output=StepOutput(event, "cli_noop"),
            new_state=state,
            label="cli_noop",
            reason="Event does not emit CLI machine output.",
        )


class UiDisplayBlock:
    """Input x State -> Set(Output x State) for localized human UI projection."""

    name = "UiDisplayBlock"
    reads = ("has_zh_cn_display", "ui_output_surface")
    writes = ("ui_output_surface",)

    def apply(self, input_obj: StepOutput, state: State) -> Iterable[FunctionResult]:
        event = input_obj.event
        if event.kind == "render_zh_cn_ui" and state.has_zh_cn_display:
            yield FunctionResult(
                output="localized_ui_rendered",
                new_state=replace(state, ui_output_surface="zh_cn_display_projection"),
                label="localized_ui_rendered",
                reason="UI display projection can render zh-CN without mutating canonical data.",
            )
            return
        if event.kind == "render_zh_cn_ui":
            yield FunctionResult(
                output="ui_falls_back_to_english",
                new_state=replace(state, ui_output_surface="english_fallback_display"),
                label="ui_falls_back_to_english",
                reason="UI falls back to canonical English when display text is missing.",
            )
            return
        yield FunctionResult(
            output="ui_noop",
            new_state=state,
            label="ui_noop",
            reason="Event does not render UI display.",
        )


WORKFLOW = Workflow(
    (CanonicalDataBlock(), MachineCliBlock(), UiDisplayBlock()),
    name="kb_canonical_interface_flow",
)

INITIAL_STATES = (State(),)
OBSERVED_INPUTS = (
    Event("create_canonical_card"),
    Event("apply_zh_cn_display_plan"),
    Event("emit_machine_json"),
    Event("render_zh_cn_ui"),
    Event("bad_translate_canonical_route"),
    Event("bad_emit_raw_localized_json"),
)


def no_localized_route_in_canonical_state(state: State, trace: object) -> InvariantResult:
    if state.canonical_route_mutated:
        return InvariantResult.fail("Localized display labels were written into canonical route state.")
    return InvariantResult.pass_()


def no_raw_unicode_at_cli_boundary(state: State, trace: object) -> InvariantResult:
    if state.raw_unicode_cli_output:
        return InvariantResult.fail("Raw localized Unicode reached the CLI machine-output boundary.")
    return InvariantResult.pass_()


def localized_ui_does_not_require_cli_unicode(state: State, trace: object) -> InvariantResult:
    if state.ui_output_surface == "zh_cn_display_projection" and state.raw_unicode_cli_output:
        return InvariantResult.fail("Localized UI rendering depended on raw Unicode CLI output.")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        name="no_localized_route_in_canonical_state",
        description="Route display labels must not rename canonical route state.",
        predicate=no_localized_route_in_canonical_state,
    ),
    Invariant(
        name="no_raw_unicode_at_cli_boundary",
        description="CLI machine output must be encoding-stable at the console boundary.",
        predicate=no_raw_unicode_at_cli_boundary,
    ),
    Invariant(
        name="localized_ui_does_not_require_cli_unicode",
        description="Chinese UI display projection must not depend on raw localized CLI output.",
        predicate=localized_ui_does_not_require_cli_unicode,
    ),
)


def _report_dict(report: object) -> dict[str, object]:
    if hasattr(report, "to_dict"):
        return report.to_dict()
    return json.loads(report.to_json_text())


def _compact_report(report: object) -> dict[str, object]:
    payload = _report_dict(report)
    ok = payload.get("ok")
    if ok is None and payload.get("observed_status") is not None:
        ok = payload.get("observed_status") == "ok"
    if ok is None and isinstance(payload.get("model_report"), dict):
        ok = payload["model_report"].get("ok")
    violations = payload.get("violations", []) or []
    if not violations and isinstance(payload.get("model_report"), dict):
        violations = payload["model_report"].get("violations", []) or []
    traces = payload.get("traces", []) or []
    if not traces and isinstance(payload.get("model_report"), dict):
        traces = payload["model_report"].get("traces", []) or []
    labels_seen = sorted({label for trace in traces for label in trace.get("labels", [])})
    compact: dict[str, object] = {
        "ok": ok,
        "observed_status": payload.get("observed_status"),
        "summary": payload.get("summary"),
        "violation_count": len(violations),
        "labels_seen": labels_seen,
    }
    if violations:
        first = violations[0]
        compact["first_violation"] = {
            "invariant_name": first.get("invariant_name"),
            "message": first.get("message"),
            "trace_labels": first.get("trace", {}).get("labels", []),
        }
    return compact


def _run_sequence(sequence: tuple[Event, ...]) -> dict[str, object]:
    return _compact_report(
        run_exact_sequence(
            workflow=WORKFLOW,
            initial_state=State(),
            external_input_sequence=sequence,
            invariants=INVARIANTS,
        )
    )


def main() -> int:
    accepted_sequence = _run_sequence(
        (
            Event("create_canonical_card"),
            Event("apply_zh_cn_display_plan"),
            Event("emit_machine_json"),
            Event("render_zh_cn_ui"),
        )
    )
    bad_route_sequence = _run_sequence((Event("bad_translate_canonical_route"),))
    bad_cli_sequence = _run_sequence((Event("apply_zh_cn_display_plan"), Event("bad_emit_raw_localized_json")))
    exploration = Explorer(
        workflow=WORKFLOW,
        initial_states=INITIAL_STATES,
        external_inputs=OBSERVED_INPUTS,
        invariants=INVARIANTS,
        max_sequence_length=2,
        required_labels=(
            "canonical_card_created",
            "zh_cn_display_added",
            "ascii_safe_machine_json",
            "localized_ui_rendered",
            "canonical_route_mutated",
            "raw_unicode_cli_output",
        ),
    ).explore()
    exploration_summary = _compact_report(exploration)
    result = {
        "model": "kb_canonical_interface_flow",
        "flowguard_schema_version": "1.0",
        "accepted_sequence": accepted_sequence,
        "bad_route_sequence": bad_route_sequence,
        "bad_cli_sequence": bad_cli_sequence,
        "exploration": exploration_summary,
        "ok": bool(accepted_sequence["ok"])
        and not bool(bad_route_sequence["ok"])
        and not bool(bad_cli_sequence["ok"])
        and not bool(exploration_summary["ok"]),
    }
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
