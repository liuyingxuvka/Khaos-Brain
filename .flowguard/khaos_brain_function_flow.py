"""Executable model-first review for Khaos Brain stateful workflows.

This is a project-local model used by the model-first-function-flow skill.
It keeps the finite-state discipline in a small standard-library explorer;
migrating this older model to the real flowguard Workflow/Explorer API remains
future work.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
import json
from typing import Callable, Iterable

try:
    import flowguard as _flowguard
except Exception:  # pragma: no cover - model remains runnable without the package.
    _flowguard = None


LOCAL_LANES = ("kb-sleep", "kb-dream")
ORG_LANES = ("kb-org-contribute", "kb-org-maintenance")


@dataclass(frozen=True)
class Input:
    kind: str
    lane: str = ""
    card_hash: str = ""
    ui_running: bool = False
    explicit_user_request: bool = False


@dataclass(frozen=True)
class Output:
    label: str
    detail: str = ""


@dataclass(frozen=True)
class State:
    local_lock: str = ""
    org_lock: str = ""
    local_status: str = ""
    org_status: str = ""
    org_imports: tuple[str, ...] = ()
    org_main: tuple[str, ...] = ()
    local_known: tuple[str, ...] = ()
    upload_effects: tuple[str, ...] = ()
    download_effects: tuple[str, ...] = ()
    update_status: str = "unavailable"
    update_available: bool = False
    ui_running: bool = False


@dataclass(frozen=True)
class Step:
    block: str
    input: Input
    output: Output
    old_state: State
    new_state: State


@dataclass(frozen=True)
class Trace:
    inputs: tuple[Input, ...]
    steps: tuple[Step, ...]
    final_state: State


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    trace: Trace | None = None


def _append_unique(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else values + (value,)


def _remove(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return tuple(item for item in values if item != value)


class MaintenanceLaneBlock:
    """Input x State -> Set(Output x State) for local and organization locks."""

    name = "MaintenanceLaneBlock"
    reads = ("local_lock", "org_lock", "local_status", "org_status")
    writes = ("local_lock", "org_lock", "local_status", "org_status")
    idempotency = "Repeated start for the same lane heartbeats; different lane in the same group waits. Finish/failure releases the owned lock and clears running status."

    def apply(self, event: Input, state: State) -> Iterable[tuple[Output, State]]:
        if event.kind not in {"start_lane", "finish_lane", "fail_lane"}:
            return
        lanes = LOCAL_LANES if event.lane in LOCAL_LANES else ORG_LANES if event.lane in ORG_LANES else ()
        if not lanes:
            yield Output("unknown_lane", event.lane), state
            return
        lock_field = "local_lock" if lanes == LOCAL_LANES else "org_lock"
        status_field = "local_status" if lanes == LOCAL_LANES else "org_status"
        held = getattr(state, lock_field)
        group = "local" if lock_field == "local_lock" else "org"
        if event.kind == "start_lane":
            if held in {"", event.lane}:
                yield Output(f"{group}_lane_acquired", event.lane), replace(
                    state,
                    **{lock_field: event.lane, status_field: "running"},
                )
            else:
                yield Output(f"{group}_lane_wait", f"{event.lane} waits for {held}"), state
            return
        if held == event.lane:
            label = f"{group}_lane_failed_release" if event.kind == "fail_lane" else f"{group}_lane_released"
            status = "failed" if event.kind == "fail_lane" else "completed"
            yield Output(label, event.lane), replace(state, **{lock_field: "", status_field: status})
        else:
            yield Output(f"{group}_lane_release_ignored", event.lane), state


class OrganizationExchangeBlock:
    """Input x State -> Set(Output x State) for imports/main exchange."""

    name = "OrganizationExchangeBlock"
    reads = ("org_imports", "org_main", "local_known", "upload_effects", "download_effects")
    writes = ("org_imports", "org_main", "local_known", "upload_effects", "download_effects")
    idempotency = "A content hash can be uploaded, promoted, or downloaded once; repeats are no-op outputs."

    def __init__(self, *, broken: bool = False) -> None:
        self.broken = broken

    def apply(self, event: Input, state: State) -> Iterable[tuple[Output, State]]:
        if event.kind == "contribute":
            card_hash = event.card_hash
            if not card_hash:
                yield Output("upload_rejected", "missing hash"), state
                return
            if not self.broken and (
                card_hash in state.org_imports
                or card_hash in state.org_main
                or card_hash in state.upload_effects
                or card_hash in state.local_known
            ):
                yield Output("upload_duplicate_skipped", card_hash), state
                return
            yield Output("uploaded_to_imports", card_hash), replace(
                state,
                org_imports=_append_unique(state.org_imports, card_hash),
                upload_effects=state.upload_effects + (card_hash,),
            )
            return
        if event.kind == "promote_import":
            card_hash = event.card_hash
            if card_hash not in state.org_imports:
                yield Output("promote_missing_import", card_hash), state
                return
            yield Output("promoted_to_main", card_hash), replace(
                state,
                org_imports=_remove(state.org_imports, card_hash),
                org_main=_append_unique(state.org_main, card_hash),
            )
            return
        if event.kind == "download":
            card_hash = event.card_hash
            if card_hash in state.local_known:
                yield Output("download_duplicate_skipped", card_hash), state
                return
            if card_hash in state.org_main:
                yield Output("downloaded_from_main", card_hash), replace(
                    state,
                    local_known=state.local_known + (card_hash,),
                    download_effects=state.download_effects + (card_hash,),
                )
                return
            if self.broken and card_hash in state.org_imports:
                yield Output("downloaded_from_imports", card_hash), replace(
                    state,
                    local_known=state.local_known + (card_hash,),
                    download_effects=state.download_effects + (card_hash,),
                )
                return
            yield Output("download_no_main_card", card_hash), state


class SoftwareUpdateBlock:
    """Input x State -> Set(Output x State) for status-only UI and manual update."""

    name = "SoftwareUpdateBlock"
    reads = ("update_status", "update_available", "ui_running")
    writes = ("update_status", "update_available", "ui_running")
    idempotency = (
        "Remote inspection only projects topology. Manual update marks upgrading once and only "
        "for an explicit current request, a fast-forward target, and a closed UI."
    )

    def __init__(self, *, broken_mode: str = "") -> None:
        self.broken_mode = broken_mode

    def apply(self, event: Input, state: State) -> Iterable[tuple[Output, State]]:
        if event.kind == "remote_current":
            yield Output("remote_update_current"), replace(
                state,
                update_status="current",
                update_available=False,
            )
            return
        if event.kind == "remote_available":
            yield Output("remote_update_available"), replace(
                state,
                update_status="available",
                update_available=True,
            )
            return
        if event.kind == "remote_local_ahead":
            if self.broken_mode == "topology_misclassified":
                yield Output("remote_update_available"), replace(
                    state,
                    update_status="available",
                    update_available=True,
                )
                return
            yield Output("remote_update_local_ahead"), replace(
                state,
                update_status="local_ahead",
                update_available=False,
            )
            return
        if event.kind == "remote_diverged":
            if self.broken_mode == "topology_misclassified":
                yield Output("remote_update_available"), replace(
                    state,
                    update_status="available",
                    update_available=True,
                )
                return
            yield Output("remote_update_diverged"), replace(
                state,
                update_status="diverged",
                update_available=False,
            )
            return
        if event.kind == "remote_unavailable":
            yield Output("remote_update_unavailable"), replace(
                state,
                update_status="unavailable",
                update_available=False,
            )
            return
        if event.kind == "ui_state":
            yield Output("ui_state_changed", str(event.ui_running)), replace(state, ui_running=event.ui_running)
            return
        if event.kind == "status_surface_interaction":
            next_state = (
                replace(state, update_status="upgrading", update_available=False)
                if self.broken_mode == "ui_status_mutates"
                else state
            )
            yield Output("status_surface_read_only"), next_state
            return
        if event.kind == "manual_update_check":
            if not event.explicit_user_request and self.broken_mode != "missing_explicit_request":
                yield Output("update_requires_explicit_request"), state
                return
            if state.update_status == "upgrading":
                yield Output("update_already_upgrading"), state
                return
            if state.update_status == "current":
                yield Output("update_noop_no_update"), state
                return
            if state.update_status in {"local_ahead", "diverged"}:
                yield Output("update_blocked_non_fast_forward", state.update_status), state
                return
            if state.update_status == "unavailable":
                yield Output("update_blocked_status_unavailable"), state
                return
            if state.update_status == "failed":
                yield Output("update_blocked_previous_failure"), state
                return
            if state.ui_running and self.broken_mode != "ui_open_applies":
                yield Output("update_blocked_ui_running"), state
                return
            if state.update_status != "available" or not state.update_available:
                yield Output("update_blocked_invalid_status"), state
                return
            yield Output("apply_update"), replace(
                state,
                update_status="upgrading",
                update_available=False,
            )
            return
        if event.kind == "update_done":
            if state.update_status != "upgrading":
                yield Output("update_done_ignored"), state
                return
            yield Output("update_marked_current"), replace(
                state,
                update_status="current",
                update_available=False,
            )
            return
        if event.kind == "update_failed":
            if state.update_status != "upgrading":
                yield Output("update_failed_ignored"), state
                return
            yield Output("update_marked_failed"), replace(state, update_status="failed", update_available=False)


BLOCKS = (MaintenanceLaneBlock(), OrganizationExchangeBlock(), SoftwareUpdateBlock())


EXTERNAL_INPUTS = (
    Input("start_lane", lane="kb-sleep"),
    Input("start_lane", lane="kb-dream"),
    Input("finish_lane", lane="kb-sleep"),
    Input("finish_lane", lane="kb-dream"),
    Input("fail_lane", lane="kb-sleep"),
    Input("fail_lane", lane="kb-dream"),
    Input("start_lane", lane="kb-org-contribute"),
    Input("start_lane", lane="kb-org-maintenance"),
    Input("finish_lane", lane="kb-org-contribute"),
    Input("finish_lane", lane="kb-org-maintenance"),
    Input("fail_lane", lane="kb-org-contribute"),
    Input("fail_lane", lane="kb-org-maintenance"),
    Input("contribute", card_hash="h1"),
    Input("promote_import", card_hash="h1"),
    Input("download", card_hash="h1"),
    Input("remote_current"),
    Input("remote_available"),
    Input("remote_local_ahead"),
    Input("remote_diverged"),
    Input("remote_unavailable"),
    Input("ui_state", ui_running=True),
    Input("ui_state", ui_running=False),
    Input("status_surface_interaction"),
    Input("manual_update_check", explicit_user_request=False),
    Input("manual_update_check", explicit_user_request=True),
    Input("update_done"),
    Input("update_failed"),
)

INITIAL_STATES = (
    State(),
    State(org_imports=("h1",)),
    State(org_main=("h1",)),
    State(update_status="current"),
    State(update_status="available", update_available=True, ui_running=True),
    State(update_status="available", update_available=True, ui_running=False),
    State(update_status="local_ahead"),
    State(update_status="diverged"),
)


def run_sequence(inputs: tuple[Input, ...], initial: State, *, broken_mode: str = "") -> Trace:
    state = initial
    steps: list[Step] = []
    blocks = (
        MaintenanceLaneBlock(),
        OrganizationExchangeBlock(broken=broken_mode == "duplicate_upload"),
        SoftwareUpdateBlock(broken_mode=broken_mode),
    ) if broken_mode else BLOCKS
    for event in inputs:
        emitted = False
        for block in blocks:
            results = list(block.apply(event, state))
            if not results:
                continue
            if len(results) != 1:
                raise AssertionError(f"{block.name} produced nondeterministic results in this model")
            output, new_state = results[0]
            steps.append(Step(block.name, event, output, state, new_state))
            state = new_state
            emitted = True
            break
        if not emitted:
            steps.append(Step("Noop", event, Output("ignored"), state, state))
    return Trace(inputs=inputs, steps=tuple(steps), final_state=state)


def invariant_no_duplicate_side_effects(trace: Trace) -> CheckResult:
    state = trace.final_state
    for field in ("upload_effects", "download_effects"):
        values = getattr(state, field)
        if len(values) != len(set(values)):
            return CheckResult(field, False, f"duplicate side effects in {field}", trace)
    return CheckResult("no_duplicate_side_effects", True)


def invariant_download_only_from_main(trace: Trace) -> CheckResult:
    for step in trace.steps:
        if step.output.label == "downloaded_from_imports":
            return CheckResult("download_only_from_main", False, "downloaded from imports", trace)
        if step.output.label == "downloaded_from_main" and step.input.card_hash not in step.old_state.org_main:
            return CheckResult("download_only_from_main", False, "main download lacked prior main card", trace)
    return CheckResult("download_only_from_main", True)


def invariant_lock_groups_are_exclusive(trace: Trace) -> CheckResult:
    for step in trace.steps:
        if step.output.label == "local_lane_acquired":
            held = step.old_state.local_lock
            if held and held != step.input.lane:
                return CheckResult("local_lock_exclusive", False, "local lane acquired while another local lane held lock", trace)
        if step.output.label == "org_lane_acquired":
            held = step.old_state.org_lock
            if held and held != step.input.lane:
                return CheckResult("org_lock_exclusive", False, "org lane acquired while another org lane held lock", trace)
    return CheckResult("lock_groups_are_exclusive", True)


def invariant_released_locks_do_not_leave_running_status(trace: Trace) -> CheckResult:
    state = trace.final_state
    if not state.local_lock and state.local_status == "running":
        return CheckResult("local_status_completed_after_release", False, "local lock released but status stayed running", trace)
    if not state.org_lock and state.org_status == "running":
        return CheckResult("org_status_completed_after_release", False, "organization lock released but status stayed running", trace)
    return CheckResult("released_locks_do_not_leave_running_status", True)


def invariant_update_apply_gate(trace: Trace) -> CheckResult:
    for step in trace.steps:
        if step.output.label != "apply_update":
            continue
        old = step.old_state
        if (
            old.update_status != "available"
            or not old.update_available
            or old.ui_running
            or not step.input.explicit_user_request
        ):
            return CheckResult(
                "update_apply_gate",
                False,
                "update applied without an explicit request, fast-forward availability, and closed UI",
                trace,
            )
    return CheckResult("update_apply_gate", True)


def invariant_status_surface_is_read_only(trace: Trace) -> CheckResult:
    for step in trace.steps:
        if step.output.label == "status_surface_read_only" and step.old_state != step.new_state:
            return CheckResult(
                "status_surface_is_read_only",
                False,
                "status interaction changed update state",
                trace,
            )
    return CheckResult("status_surface_is_read_only", True)


def invariant_update_available_matches_status(trace: Trace) -> CheckResult:
    for step in trace.steps:
        state = step.new_state
        if state.update_available != (state.update_status == "available"):
            return CheckResult(
                "update_available_matches_status",
                False,
                "update_available is true outside the sole fast-forward-available status",
                trace,
            )
    return CheckResult("update_available_matches_status", True)


def invariant_remote_topology_is_not_collapsed(trace: Trace) -> CheckResult:
    expected = {
        "remote_local_ahead": ("remote_update_local_ahead", "local_ahead"),
        "remote_diverged": ("remote_update_diverged", "diverged"),
        "remote_unavailable": ("remote_update_unavailable", "unavailable"),
    }
    for step in trace.steps:
        if step.input.kind not in expected:
            continue
        label, status = expected[step.input.kind]
        if step.output.label != label or step.new_state.update_status != status or step.new_state.update_available:
            return CheckResult(
                "remote_topology_is_not_collapsed",
                False,
                f"{step.input.kind} was collapsed into an actionable update state",
                trace,
            )
    return CheckResult("remote_topology_is_not_collapsed", True)


INVARIANTS: tuple[Callable[[Trace], CheckResult], ...] = (
    invariant_no_duplicate_side_effects,
    invariant_download_only_from_main,
    invariant_lock_groups_are_exclusive,
    invariant_released_locks_do_not_leave_running_status,
    invariant_update_apply_gate,
    invariant_status_surface_is_read_only,
    invariant_update_available_matches_status,
    invariant_remote_topology_is_not_collapsed,
)

REQUIRED_LABELS = {
    "local_lane_acquired",
    "local_lane_wait",
    "local_lane_failed_release",
    "org_lane_acquired",
    "org_lane_wait",
    "org_lane_failed_release",
    "uploaded_to_imports",
    "upload_duplicate_skipped",
    "promoted_to_main",
    "downloaded_from_main",
    "download_duplicate_skipped",
    "remote_update_current",
    "remote_update_available",
    "remote_update_local_ahead",
    "remote_update_diverged",
    "remote_update_unavailable",
    "status_surface_read_only",
    "update_requires_explicit_request",
    "update_noop_no_update",
    "update_blocked_non_fast_forward",
    "update_blocked_status_unavailable",
    "update_blocked_ui_running",
    "apply_update",
}


def explore(*, max_sequence_length: int = 3, broken_mode: str = "") -> dict[str, object]:
    traces: list[Trace] = []
    labels: set[str] = set()
    for initial in INITIAL_STATES:
        for length in range(1, max_sequence_length + 1):
            for sequence in product(EXTERNAL_INPUTS, repeat=length):
                trace = run_sequence(tuple(sequence), initial, broken_mode=broken_mode)
                traces.append(trace)
                labels.update(step.output.label for step in trace.steps)
                for invariant in INVARIANTS:
                    result = invariant(trace)
                    if not result.ok:
                        return {
                            "ok": False,
                            "broken_model": bool(broken_mode),
                            "broken_mode": broken_mode,
                            "failure": result.name,
                            "detail": result.detail,
                            "trace": trace_to_dict(result.trace or trace),
                            "checked_traces": len(traces),
                        }
    missing = sorted(REQUIRED_LABELS - labels)
    if missing:
        return {
            "ok": False,
            "broken_model": bool(broken_mode),
            "broken_mode": broken_mode,
            "failure": "missing_required_labels",
            "detail": ", ".join(missing),
            "checked_traces": len(traces),
        }
    return {
        "ok": True,
        "broken_model": bool(broken_mode),
        "broken_mode": broken_mode,
        "checked_traces": len(traces),
        "labels_seen": sorted(labels),
        "scenario_review": {
            "repeated_inputs": "covered by repeated sequence exploration up to length 3",
            "human_expectation": (
                "maintenance lanes wait inside their group, org imports are not downloaded, "
                "duplicate hashes do not create duplicate exchange side effects, released lanes "
                "do not leave running statuses, the update surface is read-only, upstream "
                "topology is explicit, and software updates apply only for a current explicit "
                "request with a fast-forward target and the UI closed"
            ),
        },
        "loop_stuck_review": {
            "local_lock": "lock states have explicit finish_lane escape edges; progress still depends on the running lane finishing",
            "organization_lock": "organization lock states have explicit finish_lane escape edges; progress still depends on the running lane finishing",
            "update_upgrading": "upgrading blocks UI startup until the update skill marks current or failed; this model treats that external completion as a fairness assumption",
            "status": "known_limitations_documented",
        },
    }


def trace_to_dict(trace: Trace) -> dict[str, object]:
    return {
        "inputs": [input_obj.__dict__ for input_obj in trace.inputs],
        "steps": [
            {
                "block": step.block,
                "input": step.input.__dict__,
                "output": step.output.__dict__,
                "old_state": step.old_state.__dict__,
                "new_state": step.new_state.__dict__,
            }
            for step in trace.steps
        ],
        "final_state": trace.final_state.__dict__,
    }


def main() -> int:
    expected = explore()
    broken_modes = (
        "duplicate_upload",
        "missing_explicit_request",
        "ui_status_mutates",
        "topology_misclassified",
        "ui_open_applies",
    )
    broken = {mode: explore(broken_mode=mode) for mode in broken_modes}
    report = {
        "model": "khaos_brain_function_flow",
        "flowguard_package_available": _flowguard is not None,
        "flowguard_schema_version": getattr(_flowguard, "SCHEMA_VERSION", "") if _flowguard is not None else "",
        "model_engine": "project_local_standard_library_explorer",
        "correct_model": expected,
        "broken_variants": broken,
        "broken_variant_expected_to_fail": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if expected.get("ok") and all(not result.get("ok") for result in broken.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
